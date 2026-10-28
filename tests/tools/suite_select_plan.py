#!/usr/bin/env python3
"""Which tests the Smoke full suite runs for a pull request (#6278 item 3): the classifier's area() picks the mode.

    python tests/tools/suite_select_plan.py [--event pull_request] [--base origin/main] [--files FILE ...]
                                            [--labels a,b] [--github-output PATH]
    python tests/tools/suite_select_plan.py --replay 50     # how many recent merged PRs skip / select / run the full suite

`full-suite` is a required check, so it always starts and reports; this planner says how much it runs (as
ground_truth_plan.py does for `ground-truth`):

* `skip`   every changed file is `prose` (docs / Markdown no test or engine code opens): nothing to run, report success.
* `select` every changed file is `prose`, `test-read-doc`, `agent-config` or a test module, and each reader the classifier lists for the
           test-read ones is a test: run only those (`paths`, pytest arguments).
* `select` also when a changed file is a test module (`tests/**/test_*.py`, #6278 item 5): that module, the test modules
           that import it by name, and TREE_GUARDS (the tests that scan the tests/ tree for a repo rule) run. Any other
           `tests/` file (conftest, fixtures, data, a helper) is full: a test file cannot be mapped to what reads it.
* `full`   anything else, any reader that is the engine or a root-level script (it cannot be mapped to a test), an
           unreadable or empty diff, the `shepherd:full` label, and every event that is not a pull_request.

A reader scope maps to a test as the classifier names it: `tests/tools/test_x.py` is that file, `tests/<dir>` is that
directory, a non-test `tests/tools/<helper>` is the tests/tools tests that name it.
Prints JSON {mode, reason, paths}; with --github-output appends mode=, paths= (space-separated). Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECTABLE = ("prose", "test-read-doc", "agent-config")
FULL_LABEL = "shepherd:full"
# Tests that read the whole tests/ tree, so any new or edited test file can trip them (the worker pre-PR guard list).
TREE_GUARDS = (
    "tests/test_source_reads.py",
    "tests/test_unicode_gauntlet.py",
    "tests/test_golden_store.py",
    "tests/cobol_mainframe/test_java_subprocess_utf8.py",
    "tests/cobol_mainframe/test_proof_reach.py",
    "tests/tools/test_posix_only_imports_4934.py",
)


def is_test_module(f: str) -> bool:
    return f.startswith("tests/") and f.endswith(".py") and Path(f).name.startswith("test_")


def test_module_targets(f: str, root: Path = REPO_ROOT) -> list[str]:
    """A changed test module (when it still exists), plus every test module that imports it by its bare name."""
    stem = Path(f).stem
    rx = re.compile(rf"^[ \t]*(?:from|import)[ \t]+{re.escape(stem)}\b", re.M)
    hits = [f] if (root / f).exists() else []
    for t in sorted((root / "tests").rglob("test_*.py")):
        rel = t.relative_to(root).as_posix()
        if rel != f and rx.search(change_classifier._text(t)):
            hits.append(rel)
    return hits


def test_target(scope: str, root: Path = REPO_ROOT) -> list[str] | None:
    """The pytest arguments for a reader scope, or None when no test maps to it (the engine, a root script). A
    non-test `tests/tools/<helper>` runs every tests/tools test that names it (its own `test_<helper>.py` among them)."""
    parts = scope.split("/")
    if parts[0] != "tests" or len(parts) < 2:
        return None
    if parts[1] != "tools":
        return [scope] if len(parts) == 2 and "." not in parts[1] else None
    if len(parts) != 3:
        return None
    if parts[2].startswith("test_"):
        return [scope]
    stem = parts[2].rsplit(".", 1)[0]
    rx = re.compile(rf"\b{re.escape(stem)}\b" if "." in parts[2] else re.escape(parts[2]) + "/")
    hits = []
    for t in sorted((root / "tests" / "tools").glob("test_*.py")):
        if t.name != Path(scope).name and rx.search(change_classifier._text(t)):
            hits.append(f"tests/tools/{t.name}")
    return hits


def plan(
    files: list[str], event: str, labels: tuple[str, ...] = (), refs: dict | None = None, root: Path = REPO_ROOT
) -> dict:
    full = {"mode": "full", "paths": []}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always the full suite"}
    if FULL_LABEL in labels:
        return {**full, "reason": f"label {FULL_LABEL}"}
    if not files:
        return {**full, "reason": "no changed files found (the diff is unreadable or empty)"}
    refs = change_classifier.load() if refs is None else refs
    areas = {f: change_classifier.area(f, refs) for f in files}
    modules = [f for f in files if is_test_module(f)]
    other = sorted(f for f, a in areas.items() if a not in SELECTABLE and f not in modules)
    if other:
        return {**full, "reason": f"{len(other)} changed file(s) are not docs / agent config, first: {other[0]}"}
    targets: set[str] = set()
    for f in modules:
        targets.update(test_module_targets(f, root))
    if modules:
        targets.update(g for g in TREE_GUARDS if (root / g).exists())
    for f, a in areas.items():
        if a == "prose" or f in modules:
            continue
        for scope in change_classifier.readers_of(f, refs):
            t = test_target(scope, root)
            if t is None:
                return {**full, "reason": f"{f} is read by {scope}, which no test selection covers"}
            targets.update(t)
    if not targets:
        return {"mode": "skip", "reason": "every changed file is prose no test or engine code opens", "paths": []}
    paths = sorted(t for t in targets if not any(t != u and t.startswith(u + "/") for u in targets))
    return {"mode": "select", "reason": f"docs / agent config / test modules only: the {len(paths)} reader(s) run", "paths": paths}


def replay(prs: list[dict], refs: dict | None = None, root: Path = REPO_ROOT) -> dict:
    """Plan the pull requests in `prs` (`gh pr list --json number,files`) and count each mode. A PR whose `files` list
    holds 100 entries may be cut short by gh, and one with no files is unreadable: both count as full (when in doubt, run)."""
    refs = change_classifier.load() if refs is None else refs
    modes: dict[str, list[int]] = {"skip": [], "select": [], "full": []}
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or [] if f.get("path")]
        mode = "full" if len(files) >= 100 else plan(files, "pull_request", (), refs, root)["mode"]
        modes[mode].append(pr["number"])
    n = len(prs)
    out: dict = {"prs": n}
    for m, nums in modes.items():
        out[m] = len(nums)
        out[f"{m}_share"] = round(len(nums) / n, 3) if n else 0.0
    out["skipped_prs"] = modes["skip"]
    out["selected_prs"] = modes["select"]
    return out


def run_replay(n: int) -> dict:
    proc = subprocess.run(["gh", "pr", "list", "--state", "merged", "-L", str(n), "--json", "number,files"],  # noqa: S603, S607
                          cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    return replay(json.loads(proc.stdout))


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT,  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--labels", default="", help="comma-separated PR labels")
    ap.add_argument("--github-output", type=Path, help="append mode=skip|select|full and paths= for later steps")
    ap.add_argument(
        "--replay", type=int, metavar="N", help="plan the last N merged PRs (needs gh), report the mode shares"
    )
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(run_replay(args.replay), indent=1))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"replay failed: {e}", file=sys.stderr)
            return 1
        return 0
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event, tuple(x for x in args.labels.split(",") if x))
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "reason": f"cannot diff ({e})", "paths": []}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\npaths={' '.join(p['paths'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
