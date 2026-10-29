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
* `select` also when a changed file is a `tests/tools` helper (a `.py` that is not a test module and not conftest /
           `__init__`, #6278 item 5): every test file in `tests/` that names it as a word, found transitively through the
           non-test helpers that name it, plus TREE_GUARDS. More than HELPER_MAX such tests (a helper most of the
           suite leans on) is `full`.
* `select` also when a changed file is a `gitgalaxy/**.py` engine module (#6278 item 5) and the nightly per-test
           coverage map (coverage_map.py, `--coverage-map`) holds it: the test files that executed it, plus the tests that
           read the engine tree, plus TREE_GUARDS. A module the map lacks, one only import-time lines cover, or one most of
           the suite covers (`core`, `standards`) is `full`, and so is a missing map.
* `select` also when a changed file is data under tests/doom_rosetta or tests/golden_doom_rosetta (#6278 item 5): the
           tests that name the doom tree as a word, transitively through helpers, plus TREE_GUARDS. tests/equivalence
           case data stays `full` (every case-enumerating test and helper reads it; see DATA_TREES).
* `select` also when a changed file is the det Java runtime `DetCics.java` or `Sort.java` (slice 6): the tests naming the class
           as the emitted call, plus the tests that hash / compile the runtime tree, plus TREE_GUARDS. Other runtime files stay `full`.
* `select` also when a changed file is a baseline / ledger JSON (`tests/*.json`, `tests/cobol_mainframe/*.json`) or a
           `det_sweep_coverage` record (slice 8): the tests that name it directly, plus TREE_GUARDS; none naming it is `full`.
* `select` also for a per-case record `tests/equivalence/infeasible_outcomes/*.json` or `det_mutation/*.json` (slice 9): the
           tests that name the directory or the case id, plus TREE_GUARDS.
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
import coverage_map  # noqa: E402

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


HELPER_MAX = 120  # a helper named by more test files than this is part of the suite's spine: run it all
NOT_HELPERS = ("conftest", "__init__")


def is_helper_module(f: str) -> bool:
    """A non-test Python file under tests/tools (any depth): the kind a name search can map to its tests."""
    p = Path(f)
    return (
        f.startswith("tests/tools/")
        and p.suffix == ".py"
        and not p.name.startswith("test_")
        and p.stem not in NOT_HELPERS
    )


def _closure(seeds: set[str], skip: str, root: Path, limit: int, direct: bool = False) -> list[str] | None:
    """Every test file that names a seed as a word, or a non-test file that (transitively) names one; None when that is
    more than `limit` test files. `direct`: only the tests that name a seed, no helper expansion."""
    files = [
        (t.relative_to(root).as_posix(), change_classifier._text(t)) for t in sorted((root / "tests").rglob("*.py"))
    ]
    names, seen, tests = set(seeds), set(), set()
    while names:
        name = names.pop()
        seen.add(name)
        rx = re.compile(rf"\b{re.escape(name)}\b")
        for rel, text in files:
            if (
                rel == skip or name not in text or not rx.search(text)
            ):  # the substring test is far cheaper than the regex
                continue
            if is_test_module(rel):
                tests.add(rel)
            elif not direct and (stem := Path(rel).stem) not in seen and stem not in NOT_HELPERS:
                names.add(stem)
        if len(tests) > limit:  # a spine name: stop at the cap instead of scanning every name
            return None
    return sorted(tests)


def helper_targets(f: str, root: Path = REPO_ROOT, limit: int = HELPER_MAX) -> list[str] | None:
    """Every test file that names the helper `f` or a non-test helper that (transitively) names it, as a word; None when
    that is more than `limit` files (the caller runs everything). A deleted helper maps by its old name the same way."""
    return _closure({Path(f).stem}, f, root, limit)


# The data trees whose files tests open by directory name. tests/equivalence is NOT here: its cases are read by every test
# that globs them or names a helper that does (equivalence.py, evidence.py, det_port.py ...), 170+ test files by direct
# naming and 650+ transitively, so a case file stays `full` (a per-case coverage map would be needed, #6278 item 5).
DATA_TREES = ("tests/doom_rosetta/", "tests/golden_doom_rosetta/")


def is_data_file(f: str) -> bool:
    """A non-Python file inside a mapped data tree (the doom manifest or a golden)."""
    return f.startswith(DATA_TREES) and not f.endswith(".py") and f.count("/") >= 2


DOOM_READERS = {"doom_rosetta", "golden_doom_rosetta", "doom_rosetta_check", "doom_speedrun", "crucible_shard_plan"}


def data_targets(f: str, root: Path = REPO_ROOT, limit: int = HELPER_MAX) -> list[str] | None:
    """The tests that read data file `f`: those naming the doom_rosetta tree or a tool that reads it (DOOM_READERS) as a
    word. Direct only: doom_speedrun / bugfix_kit are named by most of the suite, so expanding through helpers is full."""
    return _closure(DOOM_READERS, f, root, limit, direct=True)


# Baseline / ledger JSON and the det sweep coverage records (#6278 item 5, slice 8): a test or tool opens one by its file
# name, so the tests that name it (as a word: the file name, its stem, or the stem without `_baseline` / `_ledger`) read
# it. Direct only, like DOOM_READERS: a helper that names the file is named by most of the suite (654 test files).
# No direct reader at all means the file is read some way a name search cannot see (a glob), so it stays `full`.
SWEEP_COVERAGE_DIR = "tests/equivalence/det_sweep_coverage/"
# Slice 9: the per-case records beside the sweep coverage. A test opens one through its directory name (`infeasible_outcomes`,
# `det_mutation`: 16 and 5 test files name each) or its case id; the readers that glob all of tests/equivalence are
# case-agnostic helpers (a closure through them is 654 files), so direct naming is the map, as for the sweep records.
RECORD_DIRS = ("tests/equivalence/infeasible_outcomes", "tests/equivalence/det_mutation")
NAMED_DATA_DIRS = ("tests", "tests/cobol_mainframe") + RECORD_DIRS


def is_named_data_file(f: str) -> bool:
    p = Path(f)
    return f.endswith(".json") and (f.startswith(SWEEP_COVERAGE_DIR) or p.parent.as_posix() in NAMED_DATA_DIRS)


def named_data_targets(f: str, root: Path = REPO_ROOT, limit: int = HELPER_MAX) -> list[str] | None:
    """The tests that name data file `f`; None when none do or more than `limit` do (the caller runs everything)."""
    p = Path(f)
    if f.startswith(SWEEP_COVERAGE_DIR):
        seeds = {"det_sweep_coverage"}
    elif p.parent.as_posix() in RECORD_DIRS:
        seeds = {p.parent.name, p.stem}
    else:
        seeds = {p.name, p.stem, re.sub(r"_(?:baseline|ledger)$", "", p.stem)}
    hit = _closure(seeds, f, root, limit, direct=True)
    return hit or None


RUNTIME_DIR = "gitgalaxy/tools/cobol_to_java/det/cobolrt/"
# The det Java runtime files a test reaches by naming their class (#6278 item 5, slice 6): a translated port or a test
# asserts on the emitted `DetCics.` / `Sort.Key` call, so the word search is sound for these two. Slice 7 adds the
# `Det*` / `QueueManager` classes, whose names occur in at most 10 test files each. Every other file under the runtime
# stays `full` (a bare class name like `Field` or `Cobol` is a word in half the suite).
RUNTIME_READERS = {
    "cics/DetCics.java": r"\bDetCics\b",
    "cics/DetJustify.java": r"\bDetJustify\b",
    "cics/DetMq.java": r"\bDetMq\b",
    "mq/QueueManager.java": r"\bQueueManager\b",
    "dli/DetDli.java": r"\bDetDli\b",
    "sql/DetSql.java": r"\bDetSql\b",
    "batch/DetFiles.java": r"\bDetFiles\b",
    "DetMvs.java": r"\bDetMvs\b",
    "Sort.java": r"\bSort\.(?:Key|Collating|NotModelled|active|expect|finished)\b|\bcobolrt[./]Sort\b|\bdfsort\b",
}
# These read the whole runtime tree (they hash it, compile it or drive its self-test), so any mapped file runs them too.
RUNTIME_TREE_READERS = (
    "tests/cobol_mainframe/test_cobolrt.py",
    "tests/cics_crucible/test_port_provenance.py",
    "tests/cics_crucible/test_ports_compile_check.py",
)


def is_runtime_file(f: str) -> bool:
    return f.startswith(RUNTIME_DIR) and f[len(RUNTIME_DIR) :] in RUNTIME_READERS


def runtime_targets(f: str, root: Path = REPO_ROOT, limit: int = HELPER_MAX) -> list[str] | None:
    """The test files that name runtime file `f`'s class as RUNTIME_READERS says, plus RUNTIME_TREE_READERS; None when
    more than `limit` (the caller runs everything). Direct only: a port test names the class, not a helper that does."""
    rx = re.compile(RUNTIME_READERS[f[len(RUNTIME_DIR) :]])
    tests = {
        rel
        for t in sorted((root / "tests").rglob("test_*.py"))
        if rx.search(change_classifier._text(t)) and (rel := t.relative_to(root).as_posix())
    }
    tests.update(g for g in RUNTIME_TREE_READERS if (root / g).exists())
    return sorted(tests) if len(tests) <= limit else None


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


def is_engine_module(f: str) -> bool:
    return f.startswith("gitgalaxy/") and f.endswith(".py")


def plan(
    files: list[str],
    event: str,
    labels: tuple[str, ...] = (),
    refs: dict | None = None,
    root: Path = REPO_ROOT,
    cmap: dict | None = None,
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
    helpers = [f for f in files if is_helper_module(f)]
    data = [f for f in files if is_data_file(f)]
    runtime = [f for f in files if is_runtime_file(f)]
    named = [f for f in files if is_named_data_file(f)]
    engine = [f for f in files if is_engine_module(f)]
    other = sorted(
        f
        for f, a in areas.items()
        if a not in SELECTABLE
        and f not in modules
        and f not in helpers
        and f not in engine
        and f not in data
        and f not in runtime
        and f not in named
    )
    if other:
        return {**full, "reason": f"{len(other)} changed file(s) are not docs / agent config, first: {other[0]}"}
    targets: set[str] = set()
    for f in modules:
        targets.update(test_module_targets(f, root))
    for f in helpers:
        hit = helper_targets(f, root)
        if hit is None:
            return {**full, "reason": f"{f} is named by more than {HELPER_MAX} test files"}
        targets.update(hit)
    for f in data:
        hit = data_targets(f, root)
        if hit is None:
            return {**full, "reason": f"{f} is read by more than {HELPER_MAX} test files"}
        targets.update(hit)
    for f in runtime:
        hit = runtime_targets(f, root)
        if hit is None:
            return {**full, "reason": f"{f} is named by more than {HELPER_MAX} test files"}
        targets.update(hit)
    for f in named:
        hit = named_data_targets(f, root)
        if hit is None:
            return {**full, "reason": f"{f} has no test that names it, or more than {HELPER_MAX}"}
        targets.update(hit)
    if engine:
        hit, why = coverage_map.select(engine, cmap, root)
        if hit is None:
            return {**full, "reason": why}
        targets.update(hit)
    if modules or helpers or engine or data or runtime or named:
        targets.update(g for g in TREE_GUARDS if (root / g).exists())
    for f, a in areas.items():
        if a == "prose" or f in modules or f in helpers or f in engine or f in data or f in runtime or f in named:
            continue
        for scope in change_classifier.readers_of(f, refs):
            t = test_target(scope, root)
            if t is None:
                return {**full, "reason": f"{f} is read by {scope}, which no test selection covers"}
            targets.update(t)
    if not targets:
        return {"mode": "skip", "reason": "every changed file is prose no test or engine code opens", "paths": []}
    paths = sorted(t for t in targets if not any(t != u and t.startswith(u + "/") for u in targets))
    return {
        "mode": "select",
        "reason": f"docs / agent config / test modules / tests/tools helpers / mapped engine modules only: the {len(paths)} reader(s) run",
        "paths": paths,
    }


def replay(prs: list[dict], refs: dict | None = None, root: Path = REPO_ROOT, cmap: dict | None = None) -> dict:
    """Plan the pull requests in `prs` (`gh pr list --json number,files`) and count each mode. A PR whose `files` list
    holds 100 entries may be cut short by gh, and one with no files is unreadable: both count as full (when in doubt, run).
    With `cmap` (the coverage map) an engine-touching PR may select; `engine_prs` / `engine_select` count the PRs that
    change a `gitgalaxy/**.py` file and how many of them select, the share the map exists to move."""
    refs = change_classifier.load() if refs is None else refs
    modes: dict[str, list[int]] = {"skip": [], "select": [], "full": []}
    engine_prs = engine_select = 0
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or [] if f.get("path")]
        mode = "full" if len(files) >= 100 else plan(files, "pull_request", (), refs, root, cmap)["mode"]
        modes[mode].append(pr["number"])
        if any(is_engine_module(f) for f in files):
            engine_prs += 1
            engine_select += mode == "select"
    n = len(prs)
    out: dict = {"prs": n}
    for m, nums in modes.items():
        out[m] = len(nums)
        out[f"{m}_share"] = round(len(nums) / n, 3) if n else 0.0
    out["engine_prs"] = engine_prs
    out["engine_select"] = engine_select
    out["skipped_prs"] = modes["skip"]
    out["selected_prs"] = modes["select"]
    return out


def run_replay(n: int, cmap: dict | None = None) -> dict:
    proc = subprocess.run(["gh", "pr", "list", "--state", "merged", "-L", str(n), "--json", "number,files"],  # noqa: S603, S607
                          cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    return replay(json.loads(proc.stdout), cmap=cmap)


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
    ap.add_argument(
        "--coverage-map", type=Path, help="the nightly per-test coverage map (default: .engine_test_map.json)"
    )
    ap.add_argument("--github-output", type=Path, help="append mode=skip|select|full and paths= for later steps")
    ap.add_argument(
        "--replay", type=int, metavar="N", help="plan the last N merged PRs (needs gh), report the mode shares"
    )
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(run_replay(args.replay, coverage_map.load(args.coverage_map)), indent=1))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"replay failed: {e}", file=sys.stderr)
            return 1
        return 0
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        cmap = coverage_map.load(args.coverage_map)
        p = plan(files, args.event, tuple(x for x in args.labels.split(",") if x), cmap=cmap)
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "reason": f"cannot diff ({e})", "paths": []}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\npaths={' '.join(p['paths'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
