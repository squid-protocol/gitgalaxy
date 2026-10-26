#!/usr/bin/env python3
"""#6732: merge origin/main into this branch with no model -- conflicts in regenerated files are resolved by their writers.

    python tests/tools/merge_main.py              # fetch, merge origin/main, resolve, commit (never rebase, never push)
    python tests/tools/merge_main.py --dry-run    # classify the conflicts a merge would hit (git merge-tree), change nothing
    python tests/tools/merge_main.py --base origin/main --no-fetch
    python ~/main-checkout/tests/tools/merge_main.py --repo WORKTREE   # churn: main's copy on a PR branch's worktree

Churn fix runs 2026-10-18..26: 25% were a conflict with main or a branch gone stale (41 on 10-24 alone), each a model
run of 0.3-1 h plus a CI round, though many conflicted only in files no one writes by hand. A clean merge is GitHub's
update-branch (promoter-bot #20); this is the next step, the merge whose conflicts are all in files a tool writes.

Each conflicted path is one of:
  REGENERATED  main's side is taken, then its writer re-runs on the merged tree (golden masters: crucible_check.py
               --update; lint baselines: audit_check.py --regenerate; docs_read_by_tests.txt; the graph coverage chart;
               .test_durations has no writer: main's side stands)
  REGION       a hand-written file with one generated region (mutation_testing.md's score table): the prose merges
               with the region blanked on every side, then the region's writer re-renders it; prose that itself
               conflicts is HAND-WRITTEN after all (the merge is aborted)
  RECORD       a proof record a tool measures (det-sweep ledger entry, evidence record, graph comparison ledger): main's
               side is taken; if this branch's own change stales it, derived_check.py (#6731) names the re-prove
  HAND-WRITTEN anything else: the merge is aborted and the paths printed -- that conflict is a worker's job

Exit 0: merged (or already up to date) and committed. 2: a hand-written conflict, nothing changed. 3: merged and
committed, but a record needs re-proving (the commands are printed). 1: git or a writer failed; the merge is aborted.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "tests" / "tools"))
import golden_store  # noqa: E402

# (pattern, writer argv or None). A writer runs once however many of its paths conflicted.
REGENERATED: tuple[tuple[re.Pattern[str], list[str] | None], ...] = (
    (re.compile(r"^tests/(ruff|mypy)_audit_baseline\.json$"), [PY, "tests/tools/audit_check.py", "--regenerate"]),
    (re.compile(r"^tests/tools/docs_read_by_tests\.txt$"), [PY, "tests/tools/change_classifier.py", "--write"]),
    (re.compile(r"^docs/self_scan/graph_coverage_chart\.svg$"), [PY, "tests/tools/graph_coverage_chart.py", "--write"]),
    (re.compile(r"^\.test_durations$"), None),
)
GOLDEN_WRITER = [PY, "tests/tools/crucible_check.py", "--update", "--yes"]
# A hand-written file with one generated region between markers: the prose merges (git merge-file, the region blanked
# on all three sides), then the region's writer re-renders it. path -> (begin, end, writer).
REGIONS: dict[str, tuple[str, str, list[str]]] = {
    "docs/language_status/mutation_testing.md": (
        "<!-- mutation-scores -->", "<!-- /mutation-scores -->", [PY, "tests/tools/mutation_scores.py", "table"]),
}
RECORDS = re.compile(r"^tests/equivalence/(det_sweep_coverage/[^/]+\.json|[^/]+/evidence\.json)$"
                     r"|^docs/self_scan/graph_comparison_ledger\.json$")  # fmt: skip


def classify(path: str) -> tuple[str, list[str] | None]:
    """("regenerated", its writer or None) / ("record", None) / ("hand", None)."""
    if golden_store.is_golden_master_path(path):
        return "regenerated", GOLDEN_WRITER
    for pattern, writer in REGENERATED:
        if pattern.search(path):
            return "regenerated", writer
    if RECORDS.search(path):
        return "record", None
    if path in REGIONS:
        return "region", REGIONS[path][2]
    return "hand", None


def blank_region(text: str, begin: str, end: str) -> str:
    """`text` with everything between the markers dropped (the markers stay, so the merge keeps their place)."""
    a, b = text.find(begin), text.find(end)
    return text if a < 0 or b < a else text[: a + len(begin)] + "\n" + text[b:]


def merge_region_file(path: str) -> bool:
    """Merge a REGIONS file's prose (stages 1/2/3 of the conflicted index); True and staged when it merges clean."""
    begin, end, _ = REGIONS[path]
    sides = []
    for stage in (2, 1, 3):  # ours, base, theirs: git merge-file's order
        r = git("show", f":{stage}:{path}")
        if r.returncode:
            return False
        sides.append(blank_region(r.stdout, begin, end))
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for name, text in zip(("ours", "base", "theirs"), sides):
            f = Path(tmp) / name
            f.write_text(text, encoding="utf-8")
            files.append(str(f))
        r = subprocess.run(["git", "merge-file", "-p", *files], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if r.returncode:
        return False
    (REPO / path).write_text(r.stdout, encoding="utf-8")
    git("add", "--", path, check=True)
    return True


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=check)  # noqa: S603, S607


def conflicts_in(merge_tree_stdout: str) -> list[str]:
    """The conflicted paths in `git merge-tree --write-tree --name-only` output (line 1 is the tree)."""
    out = []
    for ln in merge_tree_stdout.splitlines()[1:]:
        if not ln.strip():  # the informational messages follow a blank line
            break
        out.append(ln)
    return sorted(set(out))


def plan(paths: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"regenerated": [], "region": [], "record": [], "hand": []}
    for p in paths:
        out[classify(p)[0]].append(p)
    return out


def writers_for(paths: list[str]) -> list[list[str]]:
    """The writers to run, once each, in a fixed order (goldens last: the slowest, and they read the merged code)."""
    seen: list[list[str]] = []
    for p in paths:
        w = classify(p)[1]
        if w and w not in seen:
            seen.append(w)
    return sorted(seen, key=lambda w: w == GOLDEN_WRITER)


def take_main(path: str) -> None:
    """Main's side of a conflicted path (`--theirs` in a merge); a path main deleted is deleted."""
    if git("checkout", "--theirs", "--", path).returncode == 0:
        git("add", "--", path, check=True)
    else:
        git("rm", "-q", "--ignore-unmatch", "--", path, check=True)


def writer_env() -> dict[str, str]:
    """pr_gates' environment: the corpora beside the main checkout (a golden re-bless needs the crucibles), the licence
    key, the interpreter's bin on PATH -- the same setup the gates run with."""
    import pr_gates  # noqa: PLC0415

    return {**pr_gates.environment(False), "PYTHONPATH": str(REPO)}  # the checkout being merged, not the tool's own


def stale_records() -> list[str]:
    """derived_check.py's lines (#6731) when it is on this tree; [] without it."""
    tool = REPO / "tests" / "tools" / "derived_check.py"
    if not tool.exists():
        return []
    r = subprocess.run([PY, str(tool)], cwd=REPO, env=writer_env(), capture_output=True, text=True, check=False)  # noqa: S603
    return [ln for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("derived:")] if r.returncode else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="classify the conflicts a merge would hit; change nothing")
    ap.add_argument("--repo", type=Path, help="the checkout to merge in (default: this tool's own); churn runs main's "
                    "copy of the tool on a PR branch that may predate it")  # fmt: skip
    args = ap.parse_args(argv)
    if args.repo:
        global REPO  # noqa: PLW0603 -- every git call and writer runs in the chosen checkout
        REPO = args.repo.resolve()
    if not args.no_fetch and args.base.startswith("origin/"):
        git("fetch", "-q", "origin", args.base.split("/", 1)[1])
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        print("merge_main: the working tree has uncommitted changes; commit or stash them first")
        return 1
    mt = git("merge-tree", "--write-tree", "--name-only", args.base, "HEAD")
    paths = conflicts_in(mt.stdout) if mt.returncode == 1 else []
    p = plan(paths)
    for kind in ("regenerated", "region", "record", "hand"):
        for path in p[kind]:
            print(f"  {kind:11} {path}")
    if p["hand"]:
        print(f"merge_main: {len(p['hand'])} hand-written conflict(s): a worker resolves those (merge origin/main, "
              "never rebase); nothing changed")  # fmt: skip
        return 2
    if args.dry_run:
        print(f"merge_main: dry run, {len(paths)} conflict(s), all resolvable" if paths else "merge_main: dry run, merges clean")
        return 0
    m = git("merge", "--no-edit", "--no-ff", args.base)
    if m.returncode == 0:
        print("merge_main: merged clean" if "Already up to date" not in m.stdout else "merge_main: already up to date")
    else:
        unmerged = sorted(set(git("diff", "--name-only", "--diff-filter=U").stdout.split()))
        if [u for u in unmerged if classify(u)[0] == "hand"]:  # merge-tree and merge disagree: be safe
            git("merge", "--abort")
            print(f"merge_main: unexpected hand-written conflict(s) {unmerged}; merge aborted")
            return 2
        for path in unmerged:
            if classify(path)[0] != "region":
                take_main(path)
            elif not merge_region_file(path):  # the prose itself conflicts: a worker's job
                git("merge", "--abort")
                print(f"merge_main: {path}: its hand-written part conflicts; merge aborted")
                return 2
        for writer in writers_for(unmerged):
            print("merge_main: regenerating with " + " ".join(writer[1:]), flush=True)
            if subprocess.run(writer, cwd=REPO, env=writer_env(), check=False).returncode:  # noqa: S603
                git("merge", "--abort")
                print("merge_main: the writer failed; merge aborted")
                return 1
            git("add", "-u", check=True)  # tracked files only, plus the golden fixtures' new parts
            git("add", "-A", "--", *golden_store.GOLDEN_MASTERS, check=False)
        c = git("commit", "--no-edit")
        if c.returncode:
            git("merge", "--abort")
            print("merge_main: commit failed; merge aborted\n" + c.stdout + c.stderr)
            return 1
        print(f"merge_main: merged with {len(unmerged)} conflict(s) resolved by main's side + their writers")
    if lines := stale_records():
        print("\n".join(lines))
        print("merge_main: merged, but this branch's change stales the records above: re-prove them (#6731)")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
