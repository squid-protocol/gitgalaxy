#!/usr/bin/env python3
"""Whether a pull request runs the EQUIVALENCE_E2E shards (the "plan" job of equivalence-e2e.yml, #5954 slice 2).

    python tests/tools/equivalence_e2e_plan.py [--event pull_request] [--base origin/main] [--files FILE ...]
                                               [--labels a,b] [--github-output PATH]

The shards run tests/cobol_mainframe under EQUIVALENCE_E2E=1 (Docker oracle image, JDK 17, Maven): minutes of runner time
a PR should pay only when it can move a proof. Gated through the #6278 change classifier (owner, 2026-10-24):

* `run`  a changed file is in the COBOL / mainframe / equivalence area: a COBOL, CICS, JCL, Db2 or equivalence module under
         gitgalaxy/, tests/cobol_mainframe, tests/equivalence, a tests/tools module the ground-truth job's tests reach
         (`change_classifier.runs_in_ground_truth`), a docs / agent-config file those tests open (`readers_of`), the
         workflow itself, the dependency pins; also the `shepherd:full` label, an unreadable or empty diff, and every event
         that is neither a pull_request nor a push to main (nightly, manual). A main push (post-merge, #5954 slice 4) is
         planned from the files the push brought in, as a PR is.
* `none` anything else: the job reports success without starting a shard.

`db2` (#6664) plans the `db2` job, one runner of about 20 min for the five files that need a Db2 container (DB2_FILES): on
a pull request it is `run` only when a changed file is one of their inputs (`db2_input`): a repo module in their import
closure (computed here with `ast`, so a new import is picked up without an edit), a non-Python file under gitgalaxy/ (a
runtime or data file some module reads), an equivalence case they name or shared harness data under tests/equivalence,
or the job's own files. The required `det` check re-proves the Db2 det ports on every PR; push, nightly and manual runs
always run the job, and Main Watch watches the workflow on main.

It fails open: any doubt is `run`. Prints JSON {mode, db2, reason}; with --github-output appends mode=none|run and
db2=none|run. Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_LABEL = "shepherd:full"

# fnmatch (`*` crosses `/`): the engine files that can move an equivalence proof, named by what they are about.
ENGINE_AREA = (
    "gitgalaxy/tools/cobol_to_java/*",
    "gitgalaxy/tools/cobol_to_cobol/*",
    "gitgalaxy/standards/cics/*",
    "gitgalaxy/*cobol*",
    "gitgalaxy/*cics*",
    "gitgalaxy/*mainframe*",
    "gitgalaxy/*copybook*",
    "gitgalaxy/*jcl*",
    "gitgalaxy/*db2*",
    "gitgalaxy/*equivalence*",
    "gitgalaxy/core/source_text.py",
)
# The test code the shards run and what they run on.
TEST_AREA = (
    "tests/cobol_mainframe/*",
    "tests/equivalence/*",
    "tests/tools/test_zos_probes.py",  # the one tests/tools file the shards add to tests/cobol_mainframe ...
    "tests/tools/zos_probes.py",  # ... and the module it tests (ground_truth_scopes does not know it)
    "tests/conftest.py",
    "tests/crucible_pins.toml",
)
# Whatever installs or schedules the job.
JOB_AREA = (
    ".github/workflows/equivalence-e2e.yml",
    "tests/tools/equivalence_e2e_plan.py",
    "tests/tools/equivalence_e2e_select.py",  # which files the shards run (#6664)
    "tests/tools/change_classifier.py",
    "tests/tools/docs_read_by_tests.txt",
    "pyproject.toml",
    "ci/requirements/*",
    ".test_durations",
    "tests/equivalence_e2e_durations.json",  # the shard split (#6664)
)


# The five files the shards `--ignore` and the `db2` job runs (#5954 slice 3). tests/tools/test_equivalence_e2e_plan.py
# pins this tuple to the workflow's two pytest lines.
DB2_FILES = (
    "tests/cobol_mainframe/test_equivalence_db2_rows.py",
    "tests/cobol_mainframe/test_regional_options.py",
    "tests/cobol_mainframe/test_sql_dynamic.py",
    "tests/cobol_mainframe/test_sql_unit_of_work.py",
    "tests/cobol_mainframe/test_sql_whenever.py",
)
# What installs, schedules or configures the db2 job, besides the import closure.
DB2_JOB_AREA = (
    ".github/workflows/equivalence-e2e.yml",
    "tests/tools/equivalence_e2e_plan.py",
    "tests/tools/db2_image_cache.py",
    "tests/conftest.py",
    "tests/cobol_mainframe/conftest.py",
    "tests/cobol_mainframe/corpora.json",  # the pinned corpora the generated-row cases read
    "pyproject.toml",
    "ci/requirements/*",
)
# Where a bare `import x` in a test resolves (each test puts tests/tools on sys.path), after the importing file's own dir.
_BARE_DIRS = ("tests/tools", "tests/cobol_mainframe", "tests")
_TOOL_SCRIPT = re.compile(r"[\"']([a-z0-9_]+\.py)[\"']")  # a tests/tools script a test runs as a subprocess
_CASE_NAME = re.compile(r"[\"']([a-z0-9]+(?:-[a-z0-9]+)+)[\"']")


def _module_files(name: str, importer: Path, root: Path) -> list[Path]:
    parts = name.split(".")
    if parts[0] == "gitgalaxy":
        base = root.joinpath(*parts)
        return [c for c in (base.with_suffix(".py"), base / "__init__.py") if c.is_file()][:1]
    for d in (importer.parent, *(root / b for b in _BARE_DIRS)):
        c = d.joinpath(*parts).with_suffix(".py")
        if c.is_file():
            return [c]
    return []


def _imports(path: Path, root: Path) -> list[Path]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    found: list[Path] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found += _module_files(a.name, path, root)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found += _module_files(node.module, path, root)
            for a in node.names:  # `from gitgalaxy.x import module`
                found += _module_files(f"{node.module}.{a.name}", path, root)
    return found


def db2_inputs(root: Path = REPO_ROOT) -> tuple[frozenset[str], frozenset[str]]:
    """(the repo .py files the DB2_FILES reach: their import closure plus the tests/tools scripts they run, and its
    closure; the tests/equivalence cases they name, with each `-generated` case's base case)."""
    roots = [root / f for f in DB2_FILES]
    cases: set[str] = set()
    for f in roots[:]:
        text = f.read_text(encoding="utf-8") if f.is_file() else ""
        roots += [
            root / "tests" / "tools" / m for m in _TOOL_SCRIPT.findall(text) if (root / "tests" / "tools" / m).is_file()
        ]
        for name in _CASE_NAME.findall(text):
            for case in (name, name.removesuffix("-generated")):
                if (root / "tests" / "equivalence" / case / "case.json").is_file():
                    cases.add(case)
    seen: set[Path] = set()
    todo = list(roots)
    while todo:
        f = todo.pop()
        if f not in seen and f.is_file():
            seen.add(f)
            todo += _imports(f, root)
    return frozenset(p.relative_to(root).as_posix() for p in seen), frozenset(cases)


def db2_input(path: str, modules: frozenset[str], cases: frozenset[str], root: Path = REPO_ROOT) -> bool:
    """Can a change to `path` move a test the db2 job runs? Any doubt answers yes."""
    if path in modules or _matches(path, DB2_JOB_AREA):
        return True
    if path.startswith("gitgalaxy/"):
        return not path.endswith(".py")  # a module outside the closure cannot; a runtime / data file might
    if path.startswith("tests/equivalence/"):
        parts = path.split("/")
        if len(parts) >= 3 and (root / "tests" / "equivalence" / parts[2] / "case.json").is_file():
            return parts[2] in cases  # tests/equivalence/<case>/...
        stem = parts[3].split(".")[0] if len(parts) == 4 else ""
        if stem and (root / "tests" / "equivalence" / stem / "case.json").is_file():
            return stem in cases  # tests/equivalence/<ledger>/<case>.json (det_sweep_coverage, det_mutation, ...)
        return True  # shared harness or data (db2/, cics/, le/, the Dockerfile), or a deleted case: run
    return False


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def in_area(path: str, refs: dict[str, list[str]] | None = None) -> bool:
    """Can a change to `path` move a proof the shards run? Any doubt answers yes."""
    if _matches(path, (*ENGINE_AREA, *TEST_AREA, *JOB_AREA)):
        return True
    kind = change_classifier.area(path, refs)
    if kind in ("agent-config", "test-read-doc") or path.startswith(("docs/", ".claude/")):
        # a docs / agent-config file (a .json under docs/ too) test code opens: run when a reader is one the shards run
        readers = change_classifier.readers_of(path, refs)
        return bool({"tests/cobol_mainframe", "tests/tools/test_zos_probes.py", "gitgalaxy"} & readers)
    if kind == "test-tooling":  # a tools module (a test_*.py there is not one the shards run, unless listed above)
        name = path.rsplit("/", 1)[-1]
        return not name.startswith("test_") and path.count("/") == 2 and change_classifier.runs_in_ground_truth(path)
    return False


def plan(files: list[str], event: str, labels: tuple[str, ...] = (), refs: dict | None = None,
         db2: tuple[frozenset[str], frozenset[str]] | None = None) -> dict:  # fmt: skip
    if event not in ("pull_request", "push"):
        return {"mode": "run", "db2": "run", "reason": f"{event}: always the shards and db2"}
    if FULL_LABEL in labels:
        return {"mode": "run", "db2": "run", "reason": f"label {FULL_LABEL}"}
    if not files:
        return {"mode": "run", "db2": "run", "reason": "no changed files found (the diff is unreadable or empty)"}
    refs = change_classifier.load() if refs is None else refs
    hit = next((f for f in files if in_area(f, refs)), None)
    if not hit:
        return {
            "mode": "none",
            "db2": "none",
            "reason": f"none of {len(files)} changed file(s) can move an equivalence proof",
        }
    modules, cases = db2_inputs() if db2 is None else db2
    db2_hit = next((f for f in files if db2_input(f, modules, cases)), None)
    reason = f"{hit} is in the COBOL / mainframe / equivalence area; " + (
        f"db2: {db2_hit} is an input of the Db2 files"
        if db2_hit
        else "db2: no changed file is an input of the Db2 files"
    )
    return {"mode": "run", "db2": "run" if db2_hit else "none", "reason": reason}


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
    ap.add_argument("--github-output", type=Path, help="append mode=none|run and db2=none|run for later steps")
    args = ap.parse_args()
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event, tuple(x for x in args.labels.split(",") if x))
    except (RuntimeError, OSError, ValueError, KeyError) as e:  # cannot tell what changed: run
        p = {"mode": "run", "db2": "run", "reason": f"cannot plan ({e})"}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\ndb2={p['db2']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
