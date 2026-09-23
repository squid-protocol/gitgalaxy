#!/usr/bin/env python3
"""
One-command rebase + re-bless for a parser/channel PR sitting behind a sibling
merge that already landed on main (#3385).

Automates the manual procedure every such PR needed by hand (see #3369/#3375
for two real examples of the commit sequence this replaces):

    1. rebase onto origin/main, taking main's side for golden masters/baselines;
    2. regenerate (bless) those artifact files against the rebased tree;
    3. verify the resulting golden-master diff against main is limited to this
       branch's OWN new keys -- fail loudly on any other ("foreign") drift;
    4. refresh baseline entries for moved lines in files this branch touched;
    5. run ruff check/format and a fast, touched-file-scoped test selection;
    6. optionally `git push --force-with-lease` (never plain force).

Usage:
    python tests/tools/rebase_rebless.py                       # dry run (default,
                                                                 # see below) -- no
                                                                 # branch mutation
    python tests/tools/rebase_rebless.py --execute              # actually rebase +
                                                                 # re-bless + verify +
                                                                 # refresh + test
    python tests/tools/rebase_rebless.py --execute --push       # ...then push
    python tests/tools/rebase_rebless.py --expect-keys "CICS Resources,cics_resource_data"

DRY RUN (the default): fetches origin and previews, via a read-only
`git merge-tree` (no working-tree/index/HEAD mutation), which files would
conflict and how they'd be classified -- artifact files (resolved
automatically) vs. code files (would stop the run). Nothing else runs. Pass
--execute to actually perform the rebase and the rest of the pipeline; a
successful --execute never pushes unless --push is also given.

ARTIFACT FILES (conflicts resolve to main's side, then get regenerated --
never hand-merged):
    tests/golden_master_audit.json, tests/golden_master_zero_dep_audit.json,
    tests/ruff_audit_baseline.json, tests/mypy_audit_baseline.json,
    tests/dead_key_audit_baseline.json
Any OTHER conflicted file is a code conflict: the run stops (rebase left
mid-flight, not aborted) and prints the list -- resolve by hand, `git add`,
`git rebase --continue`, then re-run this script.

OWN KEYS: auto-detected from the pre-rebase diff between the merge-base and
the branch tip (i.e. what THIS branch already changed in the golden masters,
before touching main's side at all) -- the leaf dict-key name of every
difference, same "segments" concept tests/golden_diff.py's deep_compare and
tests/tools/bless_scope.py already use. Pass --expect-keys to override
(comma-separated leaf key names) instead of relying on auto-detection.

Topological X/Y/Z coordinate diffs are never treated as foreign drift -- see
CLAUDE.md's "Scoping a bless": the corpus-wide 3D layout re-solves whenever
ANY node's mass changes, so they ride along with every key addition and are
not evidence of anything unrelated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# tests/ has no __init__.py anywhere in this repo -- import golden_diff as a
# bare top-level module, same convention as bless_scope.py/audit_check.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import golden_diff

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable

GOLDEN_MASTERS = [
    "tests/golden_master_audit.json",
    "tests/golden_master_zero_dep_audit.json",
]
LINT_BASELINES = [
    "tests/ruff_audit_baseline.json",
    "tests/mypy_audit_baseline.json",
]
# Conflicts on these resolve to main's side (in `git rebase`, "--ours" means
# upstream -- the reverse of what it means in `git merge`) and are then
# regenerated. Everything else is a code conflict and stops the run.
ARTIFACT_FILES = set(GOLDEN_MASTERS) | set(LINT_BASELINES) | {"tests/dead_key_audit_baseline.json"}

# Same filter bless_scope.py applies before bucketing a diff -- the corpus-wide
# 3D re-solve, not foreign drift. See this module's docstring.
_TOPO_RE = re.compile(r"/[XYZ]$")


class RebaseReblessError(RuntimeError):
    """A condition that should stop the run outright (not a resolvable conflict)."""


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    # GIT_EDITOR=true: `rebase --continue` must never block on an interactive
    # commit-message editor in an automated run.
    env = {**os.environ, "GIT_EDITOR": "true"}
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, env=env)
    if check and result.returncode != 0:
        raise RebaseReblessError(f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result


def current_branch(repo: Path) -> str:
    return git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def working_tree_clean(repo: Path) -> bool:
    return git(repo, "status", "--porcelain").stdout.strip() == ""


def merge_base(repo: Path, onto: str) -> str:
    return git(repo, "merge-base", "HEAD", onto).stdout.strip()


def show(repo: Path, rev: str, path: str) -> str | None:
    """`git show rev:path`, or None if that path doesn't exist at that rev."""
    result = git(repo, "show", f"{rev}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def touched_files(repo: Path, onto: str, head_ref: str = "HEAD") -> set[str]:
    """Files this branch has changed relative to `onto`, triple-dot (against
    their merge-base) same as contract_pr_check.py's touched_languages()."""
    result = git(repo, "diff", "--name-only", f"{onto}...{head_ref}", check=False)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


# --------------------------------------------------------------------------
# golden-master diffing helpers
# --------------------------------------------------------------------------


def _sanitized(text: str | None) -> dict:
    """golden_diff.load_and_sanitize takes a file path -- round-trip through a
    temp file rather than duplicating its sanitize rules here."""
    if text is None:
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return golden_diff.load_and_sanitize(path)
    finally:
        os.unlink(path)


def _is_topological(diff_line) -> bool:
    segs = getattr(diff_line, "segments", None)
    if not segs:
        return False
    return bool(_TOPO_RE.search("/" + "/".join(str(s) for s in segs))) or "Topological Coordinates" in diff_line


def leaf_keys(diffs: list) -> set[str]:
    """The leaf dict-key name (segments[-1]) of every non-topological diff line."""
    keys = set()
    for d in diffs:
        segs = getattr(d, "segments", None)
        if not segs or _is_topological(d):
            continue
        keys.add(segs[-1])
    return keys


def detect_owned_keys(repo: Path, base_ref: str, branch_ref: str = "HEAD") -> set[str]:
    """Auto-detects this branch's own golden-master keys: what changed between
    the merge-base and the branch tip, BEFORE the rebase touches main's side
    at all. Call this before mutating the branch."""
    owned: set[str] = set()
    for fixture in GOLDEN_MASTERS:
        base = _sanitized(show(repo, base_ref, fixture))
        branch = _sanitized(show(repo, branch_ref, fixture))
        if not base and not branch:
            continue
        owned |= leaf_keys(golden_diff.deep_compare(base, branch))
    return owned


def verify_no_foreign_drift(repo: Path, expect_keys: set[str], onto: str) -> list[str]:
    """Diffs the freshly-reblessed working-tree golden masters against `onto`'s
    committed ones. Any non-topological diff whose leaf key isn't in
    expect_keys is foreign drift."""
    foreign: list[str] = []
    for fixture in GOLDEN_MASTERS:
        main_side = _sanitized(show(repo, onto, fixture))
        path = repo / fixture
        ours = _sanitized(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not main_side and not ours:
            continue
        for d in golden_diff.deep_compare(main_side, ours):
            if _is_topological(d):
                continue
            segs = getattr(d, "segments", None)
            key = segs[-1] if segs else None
            if key not in expect_keys:
                foreign.append(str(d))
    return foreign


# --------------------------------------------------------------------------
# rebase + conflict classification
# --------------------------------------------------------------------------


def conflicted_files(repo: Path) -> list[str]:
    result = git(repo, "diff", "--name-only", "--diff-filter=U", check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def classify(paths: list[str]) -> tuple[list[str], list[str]]:
    artifact = [p for p in paths if p in ARTIFACT_FILES]
    code = [p for p in paths if p not in ARTIFACT_FILES]
    return artifact, code


def rebase_in_progress(repo: Path) -> bool:
    # REBASE_HEAD can outlive the rebase itself (e.g. git silently drops a
    # commit that became empty after conflict resolution, without cleaning up
    # the ref) -- the state directory is what git itself checks, and is
    # reliably removed on completion. --git-dir is resolved per-worktree.
    git_dir = Path(git(repo, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def dry_run_preview(repo: Path, onto: str) -> list[str]:
    """Read-only: a single `git merge-tree` real merge of HEAD against onto,
    written to a throwaway tree object with no working-tree/index/HEAD
    mutation. Not a full per-commit rebase simulation, but enough to classify
    artifact vs. code conflicts before committing to --execute."""
    result = git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", "HEAD", onto, check=False)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[1:] if result.returncode != 0 else []


def resolve_artifact_conflicts(repo: Path, paths: list[str]) -> None:
    for path in paths:
        git(repo, "checkout", "--ours", "--", path)
        git(repo, "add", "--", path)


def run_real_rebase(repo: Path, onto: str) -> list[str] | None:
    """Runs `git rebase onto`, auto-resolving artifact-file conflicts to onto's
    side and regenerating them once the rebase completes. Stops -- WITHOUT
    aborting -- the first time a conflict touches a code file, leaving the
    rebase mid-flight for a human/agent to resolve normally. Returns None on a
    clean, fully-applied rebase, or the list of conflicting code files."""
    result = git(repo, "rebase", onto, check=False)
    while True:
        if result.returncode == 0 and not rebase_in_progress(repo):
            return None

        paths = conflicted_files(repo)
        artifact, code = classify(paths)
        if code:
            return code
        if not artifact:
            raise RebaseReblessError(
                f"git rebase {onto} stopped with no conflicted files to resolve:\n{result.stdout}{result.stderr}"
            )

        resolve_artifact_conflicts(repo, artifact)
        staged = git(repo, "diff", "--cached", "--name-only", check=False).stdout.strip()
        if staged:
            result = git(repo, "rebase", "--continue", check=False)
        else:
            # Resolving to main's side left this commit with nothing left to
            # apply (main's side already matched) -- skip it rather than
            # leaving `rebase --continue` stuck asking for `git add`.
            result = git(repo, "rebase", "--skip", check=False)


# --------------------------------------------------------------------------
# regeneration -- overridable by tests, which have no real corpus/venvs
# --------------------------------------------------------------------------


def regenerate_golden_masters(repo: Path) -> None:
    subprocess.run([PY, "tests/tools/crucible_check.py", "--update", "--yes"], cwd=repo, check=True)


def refresh_lint_baselines(repo: Path) -> bool:
    """audit_check.py --regenerate only rewrites a baseline when EVERY new
    finding is a pure line-shift (same file/code/message, just moved) -- a
    genuine new finding anywhere is left untouched and still fails. Its exit
    code also doubles as our ruff check/format gate."""
    result = subprocess.run([PY, "tests/tools/audit_check.py", "--regenerate"], cwd=repo)
    return result.returncode == 0


def verify_baseline_refresh_scope(repo: Path, before: dict[str, dict], touched: set[str]) -> list[str]:
    """Refreshing must only move entries for files THIS branch touched. Any
    changed baseline key whose file isn't in `touched` is foreign scope creep."""
    foreign = []
    for rel_path, old in before.items():
        path = repo / rel_path
        new = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        for key in set(old) ^ set(new):
            file_part = key.split(":", 1)[0]
            if file_part not in touched:
                foreign.append(f"{rel_path}: {key}")
    return foreign


# --------------------------------------------------------------------------
# fast, touched-file-scoped test selection
# --------------------------------------------------------------------------


def fast_test_selection(repo: Path, touched: set[str]) -> list[str]:
    """Same shape as contract_pr_check.py's touched_languages(): map each
    touched source file to its directly-corresponding test file(s), rather
    than guessing which slice of the full suite is relevant."""
    tests: set[str] = set()
    for f in touched:
        p = Path(f)
        if p.suffix != ".py":
            continue
        if p.parent.as_posix().endswith("language_standards/languages"):
            for cand in (
                f"tests/extraction/languages/test_{p.stem}.py",
                f"tests/extraction/languages/test_{p.stem}_strict.py",
            ):
                if (repo / cand).is_file():
                    tests.add(cand)
        elif p.parts and p.parts[0] == "gitgalaxy":
            for cand in repo.glob(f"tests/**/test_{p.stem}.py"):
                tests.add(str(cand.relative_to(repo)))
    return sorted(tests)


def run_fast_tests(repo: Path, tests: list[str]) -> bool:
    if not tests:
        print("[fast-tests] no directly-matching test file for the touched files -- skipping.")
        return True
    result = subprocess.run([PY, "-m", "pytest", *tests, "-q"], cwd=repo)
    return result.returncode == 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rebase + re-bless + verify + refresh + test (mutates the local branch). Default is a dry run.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="After a successful --execute, `git push --force-with-lease` (requires --execute).",
    )
    parser.add_argument("--onto", default="origin/main", help="Ref to rebase onto (default: origin/main).")
    parser.add_argument(
        "--expect-keys",
        help="Comma-separated golden-master leaf keys allowed to drift (overrides auto-detection).",
    )
    parser.add_argument("--repo", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.push and not args.execute:
        parser.error("--push requires --execute")

    repo = Path(args.repo).resolve()

    branch = current_branch(repo)
    if branch in ("main", "HEAD"):
        print(f"[rebase-rebless] refusing to run from {branch!r} -- check out your feature branch first.")
        return 1
    if not working_tree_clean(repo):
        print("[rebase-rebless] working tree is not clean -- commit or stash before rebasing.")
        return 1

    git(repo, "fetch", "origin")

    base = merge_base(repo, args.onto)
    expect_keys = (
        {k.strip() for k in args.expect_keys.split(",") if k.strip()}
        if args.expect_keys
        else detect_owned_keys(repo, base)
    )
    print(f"[plan] rebase {branch} onto {args.onto} (merge-base {base[:12]})")
    print(
        f"[plan] own keys ({'--expect-keys' if args.expect_keys else 'auto-detected'}): {sorted(expect_keys) or '(none)'}"
    )

    if not args.execute:
        conflicted = dry_run_preview(repo, args.onto)
        artifact, code = classify(conflicted)
        if code:
            print(f"[dry run] {len(code)} code-file conflict(s) would stop the run:")
            for p in code:
                print(f"    {p}")
            print("[dry run] Re-run with --execute once these are expected to be resolved by hand.")
            return 1
        if artifact:
            print(
                f"[dry run] {len(artifact)} artifact-file conflict(s) would resolve to {args.onto}'s side and regenerate:"
            )
            for p in artifact:
                print(f"    {p}")
        else:
            print("[dry run] no conflicts previewed -- rebase would apply cleanly.")
        print("[dry run] Re-run with --execute to actually rebase + re-bless (add --push to push when clean).")
        return 0

    code_conflicts = run_real_rebase(repo, args.onto)
    if code_conflicts:
        print(f"[rebase-rebless] {len(code_conflicts)} code-file conflict(s) -- resolve by hand, then re-run:")
        for p in code_conflicts:
            print(f"    {p}")
        print(
            "(the rebase was left in progress; `git status` shows the conflict, `git rebase --abort` backs out entirely)"
        )
        return 1

    print("[rebless] regenerating golden masters ...")
    regenerate_golden_masters(repo)

    touched = touched_files(repo, args.onto)
    before_baselines = {}
    for rel_path in LINT_BASELINES:
        path = repo / rel_path
        before_baselines[rel_path] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    print("[baselines] refreshing ruff/mypy baseline entries for moved lines, running ruff check/format ...")
    lint_ok = refresh_lint_baselines(repo)
    scope_violations = verify_baseline_refresh_scope(repo, before_baselines, touched)

    print(f"[verify] checking golden-master diff against {args.onto} is limited to this branch's own keys ...")
    foreign = verify_no_foreign_drift(repo, expect_keys, args.onto)

    if foreign or scope_violations:
        if foreign:
            print(f"[verify] FOREIGN DRIFT -- {len(foreign)} difference(s) are not among this branch's own keys:")
            for d in foreign[:50]:
                print(f"    {d}")
            if len(foreign) > 50:
                print(f"    ... and {len(foreign) - 50} more.")
        if scope_violations:
            print(
                f"[verify] baseline refresh touched {len(scope_violations)} entr(y/ies) outside this branch's own diff:"
            )
            for d in scope_violations:
                print(f"    {d}")
        print("[rebase-rebless] FAILED -- not pushing. The rebase is applied locally; inspect before retrying.")
        return 1

    print("[test] running fast test selection for touched files ...")
    tests = fast_test_selection(repo, touched)
    tests_ok = run_fast_tests(repo, tests)

    if not (lint_ok and tests_ok):
        print("[rebase-rebless] FAILED -- lint/format or the fast test selection didn't pass. See output above.")
        return 1

    print("[rebase-rebless] clean: only this branch's own keys drifted, lint/format clean, fast tests passed.")

    if args.push:
        print(f"[push] git push --force-with-lease origin {branch} ...")
        git(repo, "push", "--force-with-lease", "origin", branch)
        print("[push] done.")
    else:
        print(f"[push] not pushed (pass --push to run: git push --force-with-lease origin {branch}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
