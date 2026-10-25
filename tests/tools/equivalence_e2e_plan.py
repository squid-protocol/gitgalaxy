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

It fails open: any doubt is `run`. Prints JSON {mode, reason}; with --github-output appends mode=none|run. Stdlib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
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
    "tests/tools/change_classifier.py",
    "tests/tools/docs_read_by_tests.txt",
    "pyproject.toml",
    "ci/requirements/*",
    ".test_durations",  # the shard split
)


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


def plan(files: list[str], event: str, labels: tuple[str, ...] = (), refs: dict | None = None) -> dict:
    if event not in ("pull_request", "push"):
        return {"mode": "run", "reason": f"{event}: always the shards"}
    if FULL_LABEL in labels:
        return {"mode": "run", "reason": f"label {FULL_LABEL}"}
    if not files:
        return {"mode": "run", "reason": "no changed files found (the diff is unreadable or empty)"}
    refs = change_classifier.load() if refs is None else refs
    hit = next((f for f in files if in_area(f, refs)), None)
    if hit:
        return {"mode": "run", "reason": f"{hit} is in the COBOL / mainframe / equivalence area"}
    return {"mode": "none", "reason": f"none of {len(files)} changed file(s) can move an equivalence proof"}


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
    ap.add_argument("--github-output", type=Path, help="append mode=none|run for later steps")
    args = ap.parse_args()
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event, tuple(x for x in args.labels.split(",") if x))
    except (RuntimeError, OSError, ValueError, KeyError) as e:  # cannot tell what changed: run
        p = {"mode": "run", "reason": f"cannot plan ({e})"}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
