#!/usr/bin/env python3
"""Re-prove every port after a change that can move them all (the runtime, the harness, an oracle model).

    python tests/tools/proof_sweep.py --work DIR [--det-only | --model-only] [--jobs 2] [--faults all] [--skip-db2]

Two sweeps, as the det-port skill's checklists ask after a runtime or harness change:
  det    every equivalence case translated and proven (det_port.py run --all-cases);
  model  every committed model-written port (a case with port/) proven as committed (equivalence.py run --faults).

DIR/sweep.json holds each case's verdict and coverage line; the summary compares them with tests/equivalence/det_sweep_baseline.json
(KNOWN_UNPROVEN at import), the cases not proven yet, each with its reason and issue: a two-way ratchet, exit 1 when a case not
listed there is not proven, or a listed one now is (--update-baseline drops those entries). Db2 cases each take a database of the pool (equivalence_db2.hold_lock), waiting when every one is taken.
--skip-db2 leaves out the cases with a "db2" section (IBM's Db2 container is slow to start): CI's det-sweep workflow (#4463).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.core.source_text import read_source  # noqa: E402

CASES = REPO_ROOT / "tests" / "equivalence"

BASELINE = CASES / "det_sweep_baseline.json"


def load_baseline(path: Path = BASELINE) -> dict[tuple[str, str], str]:
    """(sweep, case) -> "why (issue)" for every case not proven on purpose (tests/equivalence/det_sweep_baseline.json)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(sweep, case): f"{e['why']} ({e['issue'] or 'no issue'})"
            for sweep in ("det", "model") for case, e in data.get(sweep, {}).items()}  # fmt: skip


KNOWN_UNPROVEN = load_baseline()


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")
    return env


def _coverage(log: Path) -> str:
    """The proof's coverage line ("... proven on N scenarios ..." or "... not proven ..."), or ""."""
    if not log.is_file():
        return ""
    lines = [ln for ln in read_source(log).text.splitlines() if "COBOL coverage:" in ln]
    return lines[-1].split("COBOL coverage:", 1)[-1].strip() if lines else ""


def is_db2(case: str) -> bool:
    """A case with a "db2" section: its proof needs IBM's Db2 container."""
    return "db2" in json.loads((CASES / case / "case.json").read_text(encoding="utf-8"))


def det_sweep(work: Path, jobs: int, faults: str, skip_db2: bool = False) -> dict[str, dict]:
    which = ["--all-cases"]
    if skip_db2:
        which = sorted(p.parent.name for p in CASES.glob("*/case.json") if not is_db2(p.parent.name))
    argv = [sys.executable, str(TOOLS / "det_port.py"), "run", *which, "--jobs", str(jobs), "--faults", faults,
            "--work", str(work)]  # fmt: skip
    subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=subprocess.DEVNULL)  # noqa: S603
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    out = {}
    for row in summary:
        cov = _coverage(work / row["case"] / "proof.log")
        out[row["case"]] = {"proved": bool(row.get("proved")), "coverage": cov,
                            "translated": f"{row.get('translated_statements')}/{row.get('statements')}"}  # fmt: skip
    return out


def model_sweep(work: Path, faults: str, skip_db2: bool = False) -> dict[str, dict]:
    out = {}
    for port in sorted(CASES.glob("*/port")):
        case = port.parent.name
        if skip_db2 and is_db2(case):
            continue
        keep, log = work / case, work / f"{case}.log"
        argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case, "--keep", str(keep), "--faults", faults]
        with log.open("wb") as fh:
            rc = subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=fh, stderr=subprocess.STDOUT,  # noqa: S603
                                timeout=3600).returncode  # fmt: skip
        out[case] = {"proved": rc == 0, "coverage": _coverage(log)}
        print(f"model {case:<30} {'PROVED' if rc == 0 else 'NOT PROVEN'}", flush=True)
    return out


def verdict(results: dict[str, dict[str, dict]], known_unproven: dict[tuple[str, str], str] | None = None) -> list[str]:
    """What the sweep says against KNOWN_UNPROVEN: the cases that are not proven and should be, and the listed ones
    that now are (the list is stale)."""
    baseline = KNOWN_UNPROVEN if known_unproven is None else known_unproven
    problems = []
    for sweep, cases in results.items():
        for case, r in sorted(cases.items()):
            known = (sweep, case) in baseline
            if not r["proved"] and not known:
                problems.append(
                    f"{sweep} {case}: NOT PROVEN ({r['coverage'] or 'no coverage line'}); a new failure: fix it, "
                    f"or (only with its true cause and issue) add it to {BASELINE.relative_to(REPO_ROOT)}"
                )
            elif r["proved"] and known:
                problems.append(
                    f"{sweep} {case}: now proven -- update the baseline: python tests/tools/proof_sweep.py "
                    f"--update-baseline --work <the same DIR> (or remove it from {BASELINE.relative_to(REPO_ROOT)})"
                )
    return problems


def prune_baseline(results: dict[str, dict[str, dict]], path: Path = BASELINE) -> list[str]:
    """Drop the baseline entries that now prove (never adds one); returns the cases dropped."""
    data = json.loads(path.read_text(encoding="utf-8"))
    dropped = []
    for sweep, cases in results.items():
        for case, r in cases.items():
            if r["proved"] and case in data.get(sweep, {}):
                del data[sweep][case]
                dropped.append(f"{sweep} {case}")
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--faults", default="all")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--det-only", action="store_true")
    which.add_argument("--model-only", action="store_true")
    ap.add_argument("--skip-db2", action="store_true", help='leave out the cases with a "db2" section')
    ap.add_argument(
        "--update-baseline", action="store_true", help="after the sweep, drop the baseline entries that now prove"
    )
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, dict]] = {}
    if not args.model_only:
        results["det"] = det_sweep(args.work / "det", args.jobs, args.faults, args.skip_db2)
    if not args.det_only:
        (args.work / "model").mkdir(exist_ok=True)
        results["model"] = model_sweep(args.work / "model", args.faults, args.skip_db2)
    (args.work / "sweep.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for sweep, cases in results.items():
        n = sum(r["proved"] for r in cases.values())
        print(f"{sweep}: {n}/{len(cases)} proven")
    if args.update_baseline:
        for d in prune_baseline(results):
            print(f"baseline: dropped {d}")
    problems = verdict(results, load_baseline())
    for p in problems:
        print(p)
    print("sweep: as expected" if not problems else f"sweep: {len(problems)} unexpected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
