#!/usr/bin/env python3
"""Re-prove every port after a change that can move them all (the runtime, the harness, an oracle model).

    python tests/tools/proof_sweep.py --work DIR [--det-only | --model-only] [--jobs 2] [--faults all]

Two sweeps, as the det-port skill's checklists ask after a runtime or harness change:
  det    every equivalence case translated and proven (det_port.py run --all-cases);
  model  every committed model-written port (a case with port/) proven as committed (equivalence.py run --faults).

DIR/sweep.json holds each case's verdict and coverage line; the summary compares them with KNOWN_UNPROVEN, the cases
not proven on purpose (each with its reason): exit 1 when a case not listed there is not proven, or a listed one now
is (the list is then stale). Db2 cases each take a database of the pool (equivalence_db2.hold_lock), waiting when every one is taken.
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

# (sweep, case) -> why it is not proven, on purpose
KNOWN_UNPROVEN = {
    ("det", "carddemo-cardupdate"): "COCRDUPC writes blanks into a PIC 9(3) CVV a typed DTO field cannot hold (#4085)",
    ("det", "carddemo-intcalc-generated"): "generated card numbers mix letters and digits: ASCII vs EBCDIC key order "
    "picks different duplicates (oracle_assumptions.md D1)",
    ("det", "mortgage-mpmt"): "IBM DBB EPSMPMT computes its payment through a COMP-1 item: z/OS evaluates both "
    "COMPUTEs in hexadecimal floating point, GnuCOBOL in truncated decimal, so the det translator refuses float items "
    "by name (oracle_assumptions.md C6, #4271; its CBL NUMPROC(MIG) is now modelled, C5)",
}


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


def det_sweep(work: Path, jobs: int, faults: str) -> dict[str, dict]:
    argv = [sys.executable, str(TOOLS / "det_port.py"), "run", "--all-cases", "--jobs", str(jobs), "--faults", faults,
            "--work", str(work)]  # fmt: skip
    subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=subprocess.DEVNULL)  # noqa: S603
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    out = {}
    for row in summary:
        cov = _coverage(work / row["case"] / "proof.log")
        out[row["case"]] = {"proved": bool(row.get("proved")), "coverage": cov,
                            "translated": f"{row.get('translated_statements')}/{row.get('statements')}"}  # fmt: skip
    return out


def model_sweep(work: Path, faults: str) -> dict[str, dict]:
    out = {}
    for port in sorted(CASES.glob("*/port")):
        case = port.parent.name
        keep, log = work / case, work / f"{case}.log"
        argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case, "--keep", str(keep), "--faults", faults]
        with log.open("wb") as fh:
            rc = subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=fh, stderr=subprocess.STDOUT,  # noqa: S603
                                timeout=3600).returncode  # fmt: skip
        out[case] = {"proved": rc == 0, "coverage": _coverage(log)}
        print(f"model {case:<30} {'PROVED' if rc == 0 else 'NOT PROVEN'}", flush=True)
    return out


def verdict(results: dict[str, dict[str, dict]]) -> list[str]:
    """What the sweep says against KNOWN_UNPROVEN: the cases that are not proven and should be, and the listed ones
    that now are (the list is stale)."""
    problems = []
    for sweep, cases in results.items():
        for case, r in sorted(cases.items()):
            known = (sweep, case) in KNOWN_UNPROVEN
            if not r["proved"] and not known:
                problems.append(f"{sweep} {case}: NOT PROVEN ({r['coverage'] or 'no coverage line'})")
            elif r["proved"] and known:
                problems.append(f"{sweep} {case}: now proven -- remove it from KNOWN_UNPROVEN")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--faults", default="all")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--det-only", action="store_true")
    which.add_argument("--model-only", action="store_true")
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, dict]] = {}
    if not args.model_only:
        results["det"] = det_sweep(args.work / "det", args.jobs, args.faults)
    if not args.det_only:
        (args.work / "model").mkdir(exist_ok=True)
        results["model"] = model_sweep(args.work / "model", args.faults)
    (args.work / "sweep.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for sweep, cases in results.items():
        n = sum(r["proved"] for r in cases.values())
        print(f"{sweep}: {n}/{len(cases)} proven")
    problems = verdict(results)
    for p in problems:
        print(p)
    print("sweep: as expected" if not problems else f"sweep: {len(problems)} unexpected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
