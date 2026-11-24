#!/usr/bin/env python3
"""rebless-batch: fold several PRs that each carry golden snapshots into ONE draft PR with ONE re-bless.

    python tests/tools/rebless_batch.py --prs 9053,9054,9055 [--branch NAME] [--dry-run] [--push] [--no-bless]

Why (2026-11-23): nine open engine PRs (#9053-#9059, #9061, #9067 -> #9111) each fixed one language and each committed
the same golden-master snapshot files, so every merge re-conflicted the rest and all nine sat red behind a main-wide
rosetta-audit blocker. Merging them one at a time means nine blesses in series; one combined branch means one. This is
the recipe that was done by hand for #9111, made repeatable:

  1. fetch origin/main and each `pull/N/head`;
  2. per PR, take `merge-base..head` WITHOUT the snapshot paths (tests/golden_master_audit,
     tests/golden_master_zero_dep_audit, tests/golden_doom_rosetta) and apply it to a fresh worktree off origin/main with
     `git apply --3way --index`, one commit per PR. A diff that does not apply, or two PRs whose hunks overlap in the
     same hand-written file, is REFUSED (exit 2) naming the PRs and file: a human decides;
  3. unless --no-bless, bless once: `golden-lock.sh crucible_check.py --update --yes` (both legs, CI-matched venvs),
     then `doom_rosetta_check.py --update --yes`; a file outside the snapshot paths that the bless touched is refused
     (untracked-file poisoning, .claude/rules/golden-master-guidelines.md);
  4. with --push: push the branch and open a DRAFT PR that lists every PR it supersedes.

It never marks the PR ready, never merges and never closes the originals: it prints the `gh pr close` commands for a
human (or churn) to run once the batch PR is green. --dry-run does steps 1-2 in a throwaway worktree and removes it.
Exit codes: 0 ok, 2 refused (nothing pushed), 1 a command failed.
"""

# ruff: noqa: S603, S607  (fixed git/gh/bash commands built from validated PR numbers, never from free text)
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIRS = ("tests/golden_master_audit/", "tests/golden_master_zero_dep_audit/", "tests/golden_doom_rosetta/")
ATTRIBUTION = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
TRAILER = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
CRUCIBLES = Path(os.environ.get("GITGALAXY_CRUCIBLE_ROOT", "/srv/storage_16tb/projects/gitgalaxy"))
VENV_BIN = Path(os.environ.get("GITGALAXY_SELFSCAN_BIN", "/srv/storage_16tb/projects/gitgalaxy/venvs/selfscan/bin"))
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


class Refused(Exception):
    """The batch cannot be built safely; the message says why (exit 2)."""


@dataclass
class PrInfo:
    number: int
    title: str = ""
    files: list[str] = field(default_factory=list)  # hand-written files the PR changes


# ---- pure logic --------------------------------------------------------------------------------------------------


def is_snapshot(path: str) -> bool:
    """A generated golden snapshot file (never hand-merged; re-blessed once for the batch)."""
    return path.startswith(SNAPSHOT_DIRS)


def split_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """(hand-written, snapshot) paths, order kept."""
    hand = [p for p in paths if not is_snapshot(p)]
    return hand, [p for p in paths if is_snapshot(p)]


def exclude_pathspecs() -> list[str]:
    return [f":(exclude){d.rstrip('/')}" for d in SNAPSHOT_DIRS]


def parse_hunks(diff: str) -> dict[str, list[tuple[int, int]]]:
    """File -> old-side line ranges (inclusive) of each hunk in a unified diff. A pure insertion is the one line it follows."""
    out: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current = line.split(" b/", 1)[1] if " b/" in line else None
            if current:
                out.setdefault(current, [])
        elif current and (m := HUNK_RE.match(line)):
            start, count = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            out[current].append((start, start + max(count, 1) - 1))
    return out


def find_overlaps(per_pr: dict[int, dict[str, list[tuple[int, int]]]]) -> list[tuple[str, int, int]]:
    """(file, pr_a, pr_b) for each pair of PRs that change overlapping old-side lines of the same file. Ranges are read
    against each PR's own merge-base, so this is a screen, not a proof: `git apply --3way` is the real test."""
    hits: list[tuple[str, int, int]] = []
    prs = sorted(per_pr)
    for i, a in enumerate(prs):
        for b in prs[i + 1 :]:
            for path, ranges_a in per_pr[a].items():
                ranges_b = per_pr[b].get(path)
                if ranges_b and any(x0 <= y1 and y0 <= x1 for x0, x1 in ranges_a for y0, y1 in ranges_b):
                    hits.append((path, a, b))
    return hits


def batch_title(prs: list[PrInfo]) -> str:
    nums = " ".join(f"#{p.number}" for p in prs)
    return f"Rebless once for {len(prs)} stacked engine fixes (supersedes {nums})"


def render_body(prs: list[PrInfo], blessed: bool) -> str:
    """The draft PR's description, in plain words."""
    lines = [
        f"{len(prs)} open PRs each carry golden-master snapshots, so merging them one at a time re-conflicts the rest "
        "every time. This applies each one's hand-written change (source, tests, docs) to one branch off main and "
        + ("blesses the snapshots once." if blessed else "leaves the snapshots for one bless (not run yet)."),
        "",
        "What each one changes:",
    ]
    for p in prs:
        files = ", ".join(f"`{f}`" for f in p.files[:4]) + (" ..." if len(p.files) > 4 else "")
        lines.append(f"- #{p.number} {p.title or '(title unknown)'}: {files or 'no hand-written files'}")
    lines += [
        "",
        "The originals stay open until this is green. Then close them as superseded:",
        "",
        *[f"    {c}" for c in close_commands(prs, "<this PR>")],
        "",
        "Built by `tests/tools/rebless_batch.py`.",
        "",
        ATTRIBUTION,
    ]
    return "\n".join(lines)


def close_commands(prs: list[PrInfo], batch_ref: str) -> list[str]:
    return [
        f"gh pr close {p.number} -c \"Superseded by {batch_ref}, which carries this PR's hand-written change with the "
        'golden snapshots re-blessed once for the whole batch."'
        for p in prs
    ]


def parse_prs(text: str) -> list[int]:
    nums = sorted({int(x) for x in re.split(r"[,\s]+", text.strip()) if x})
    if len(nums) < 2:
        raise Refused("--prs needs at least two PR numbers: there is nothing to batch")
    return nums


# ---- git plumbing ------------------------------------------------------------------------------------------------


def run(*cmd: str, cwd: Path, check: bool = True, env: dict[str, str] | None = None, raw: bool = False) -> str:
    """Run a command, return its stdout (stripped unless raw: a patch must keep its trailing bytes)."""
    # bytes, decoded without newline translation: text=True turns a patch's LF into CRLF (and back) on Windows
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, check=False)
    out = r.stdout.decode("utf-8", errors="surrogateescape")
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, cmd, out, r.stderr.decode("utf-8", errors="surrogateescape"))
    return out if raw else out.strip()


def hand_written_diff(repo: Path, base: str, head: str) -> str:
    """`git diff --binary base head` without the snapshot paths."""
    return run("git", "diff", "--binary", base, head, "--", ".", *exclude_pathspecs(), cwd=repo, raw=True)


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    out = run("git", "diff", "--name-only", base, head, cwd=repo)
    return [x for x in out.splitlines() if x]


def apply_diff(worktree: Path, diff: str) -> tuple[bool, str]:
    """`git apply --3way --index` of a diff; (ok, git's complaint). On failure the tree holds conflict markers: the
    caller discards the worktree, it never commits or continues from it."""
    r = subprocess.run(
        ["git", "apply", "--3way", "--index", "--binary", "-"],
        cwd=worktree, input=diff.encode("utf-8", errors="surrogateescape"), capture_output=True, check=False,
    )  # fmt: skip
    msg = (r.stderr or r.stdout).decode("utf-8", errors="surrogateescape")
    return r.returncode == 0, msg.strip()


def gh_title(number: int) -> str:
    r = subprocess.run(
        ["gh", "pr", "view", str(number), "--json", "title", "--jq", ".title"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    return r.stdout.strip() if r.returncode == 0 else ""


def bless_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{VENV_BIN}{os.pathsep}{env.get('PATH', '')}"
    for var, name in (
        ("LANGUAGE_CRUCIBLE_PATH", "language-crucible"),
        ("CICS_CRUCIBLE_PATH", "cics-crucible"),
        ("ESTATE_CRUCIBLE_PATH", "estate-crucible"),
    ):
        env.setdefault(var, str(CRUCIBLES / name))
    return env


def bless(worktree: Path, doom_work: Path) -> None:
    env = bless_env()
    print("bless: syncing pins, then the golden masters (both legs) ...", flush=True)
    run("tests/tools/box/sync-pins.sh", cwd=worktree, env=env)
    run(
        "tests/tools/box/golden-lock.sh",
        "python",
        "tests/tools/crucible_check.py",
        "--update",
        "--yes",
        cwd=worktree,
        env=env,
    )
    print("bless: DOOM-port goldens ...", flush=True)
    env["PYTHONPATH"] = str(worktree)
    run(
        "python",
        "tests/tools/doom_rosetta_check.py",
        "--update",
        "--yes",
        "--work",
        str(doom_work),
        cwd=worktree,
        env=env,
    )
    stray = [
        line[3:] for line in run("git", "status", "--porcelain", cwd=worktree).splitlines() if not is_snapshot(line[3:])
    ]
    if stray:
        raise Refused(
            "the bless touched files outside the snapshot paths (scratch files poison goldens): " + ", ".join(stray[:8])
        )


# ---- the batch ---------------------------------------------------------------------------------------------------


def build(args: argparse.Namespace) -> int:
    numbers = parse_prs(args.prs)
    branch = args.branch or f"rebless-batch-{numbers[0]}-{len(numbers)}"
    run("git", "fetch", "-q", "origin", "main", cwd=REPO_ROOT)
    prs: list[PrInfo] = []
    diffs: dict[int, str] = {}
    hunks: dict[int, dict[str, list[tuple[int, int]]]] = {}
    for n in numbers:
        run("git", "fetch", "-q", "origin", f"pull/{n}/head:refs/rebless/{n}", cwd=REPO_ROOT)
        base = run("git", "merge-base", "origin/main", f"refs/rebless/{n}", cwd=REPO_ROOT)
        hand, snap = split_paths(changed_files(REPO_ROOT, base, f"refs/rebless/{n}"))
        diffs[n] = hand_written_diff(REPO_ROOT, base, f"refs/rebless/{n}")
        hunks[n] = parse_hunks(diffs[n])
        prs.append(PrInfo(n, gh_title(n), hand))
        print(f"#{n}: {len(hand)} hand-written file(s), {len(snap)} snapshot file(s) set aside")
    if overlaps := find_overlaps(hunks):
        raise Refused(
            "these PRs change the same lines of the same file; decide by hand which wins:\n"
            + "\n".join(f"  {path}: #{a} and #{b}" for path, a, b in overlaps)
        )
    path = REPO_ROOT.parent / branch
    if run("git", "branch", "--list", branch, cwd=REPO_ROOT) or path.exists():
        raise Refused(f"branch or directory '{branch}' already exists: pick another --branch")
    run("git", "worktree", "add", "-q", "-b", branch, str(path), "origin/main", cwd=REPO_ROOT)
    keep = False
    try:
        for p in prs:
            if not diffs[p.number].strip():
                print(f"#{p.number}: no hand-written change (snapshots only): nothing to apply")
                continue
            ok, why = apply_diff(path, diffs[p.number])
            if not ok:
                raise Refused(f"#{p.number}'s hand-written change does not apply on current main:\n{why}")
            if not run("git", "diff", "--cached", "--name-only", cwd=path):
                print(f"#{p.number}: its hand-written change is already on main: nothing to commit")
                continue
            run(
                "git",
                "commit",
                "-q",
                "-m",
                f"apply #{p.number}: {p.title} (non-snapshot changes)\n\n{TRAILER}",
                cwd=path,
            )
        if args.dry_run:
            print(f"dry run: all {len(prs)} PRs apply cleanly and none overlap. Nothing blessed, pushed or kept.")
            return 0
        blessed = not args.no_bless
        if blessed:
            bless(path, REPO_ROOT.parent / f"_doom-work-{branch}")
            if run("git", "status", "--porcelain", cwd=path):
                run("git", "add", "-A", cwd=path)
                run(
                    "git",
                    "commit",
                    "-q",
                    "-m",
                    f"golden: re-bless once for {len(prs)} stacked engine fixes\n\n{TRAILER}",
                    cwd=path,
                )
        keep = True
        print(f"batch branch '{branch}' is at {path}")
        if args.push:
            run("git", "push", "-q", "-u", "origin", branch, cwd=path)
            url = run("gh", "pr", "create", "--draft", "--head", branch, "--base", "main", "--title", batch_title(prs),
                      "--body", render_body(prs, blessed), cwd=path)  # fmt: skip
            print(f"draft PR: {url}")
            print("when it is green, close the originals:")
            print("\n".join("  " + c for c in close_commands(prs, "#" + url.rsplit("/", 1)[-1])))
        else:
            print("not pushed (no --push). Commands for later:")
            print("\n".join("  " + c for c in close_commands(prs, "<the batch PR>")))
        return 0
    finally:
        if not keep:
            run("git", "worktree", "remove", "--force", str(path), cwd=REPO_ROOT, check=False)
            run("git", "branch", "-D", branch, cwd=REPO_ROOT, check=False)
            shutil.rmtree(path, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prs", required=True, help="comma-separated PR numbers to fold together")
    ap.add_argument("--branch", help="batch branch name (default rebless-batch-<first PR>-<count>)")
    ap.add_argument(
        "--dry-run", action="store_true", help="check that every PR applies and none overlap, then clean up"
    )
    ap.add_argument("--push", action="store_true", help="push the branch and open a DRAFT PR")
    ap.add_argument("--no-bless", action="store_true", help="apply the hand-written changes only; do not bless")
    args = ap.parse_args(argv)
    try:
        return build(args)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"failed: {' '.join(map(str, e.cmd))}\n{(e.stderr or e.stdout or '')[-2000:]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
