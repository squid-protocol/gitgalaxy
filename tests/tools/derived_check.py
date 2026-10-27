#!/usr/bin/env python3
"""#6731: the derived records this branch stales, found before CI does -- fingerprints only, no sweep (~5 s).

    python tests/tools/derived_check.py          # exit 1 and print each refresh command when one is stale or missing
    python tests/tools/pr_gates.py --only derived

The churn's fix runs of 2026-10-18..26 (436): 28% were a derived record a PR changed the inputs of and did not
refresh, found one push later by a check `pr_gates --fast` does not run (tests/cobol_mainframe/ is left out of the PR
smoke suite; the det-sweep ledger is checked only inside det-sweep's `--aggregate`). This applies the same BLOCKING rules:

  evidence      a record whose port / case / corpus / differences / options changed since its proof
                (tests/cobol_mainframe/test_evidence.py::test_every_committed_record_is_current) -> evidence.py prove KEY
  det ledger    a non-Db2 case whose case / corpus changed since its det_sweep_coverage entry, or a non-Db2 case with
                no entry that det_sweep_baseline.json does not list as unproven (a new case) -> a det sweep of it, then
                det_coverage_ledger.py update (det-sweep skips Db2 on a PR; the scheduled Evidence Refresh sweeps those)

A harness / oracle / generator change only stales records for the scheduled refresh, as in CI: not reported here.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import det_coverage_ledger as dcl  # noqa: E402
import evidence as ev  # noqa: E402
import proof_sweep as ps  # noqa: E402

SWEEP = "python tests/tools/proof_sweep.py --det-only --skip-db2 --cases {cases} --work DIR"
UPDATE = "python tests/tools/det_coverage_ledger.py update DIR"


def stale_evidence() -> list[tuple[str, list[str]]]:
    """(KEY, the blocking inputs that changed) for every committed record a PR must re-prove."""
    out = []
    for t in ev.targets():
        rec = ev.load(t)
        if rec is not None and (blocking := ev.status(rec, t)["blocking"]):
            out.append((t.key, list(blocking)))
    return out


def ledger_gaps(cases: list[str] | None = None, ledger: dict | None = None) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """(stale: [(CASE, the blocking inputs that changed)], missing: [CASE]) over the non-Db2 cases the PR det-sweep runs."""
    ledger = dcl.load() if ledger is None else ledger
    cases = [p.parent.name for p in sorted(dcl.CASES.glob("*/case.json"))] if cases is None else cases
    stale, missing = [], []
    for case in cases:
        if ps.is_db2(case):
            continue
        entry = ledger.get(case)
        if entry is None:
            if ("det", case) not in ps.KNOWN_UNPROVEN:
                missing.append(case)
            continue
        if bad := [n for n in dcl.stale(entry, dcl.fingerprints(case)) if n in dcl.BLOCKING]:
            stale.append((case, bad))
    return stale, missing


def report(evidence: list[tuple[str, list[str]]], stale: list[tuple[str, list[str]]], missing: list[str]) -> list[str]:
    """The problem lines, each with its fix; [] when nothing is stale."""
    lines = [f"evidence: {key}: {', '.join(bad)} changed since the proof -- python tests/tools/evidence.py prove {key}"
             for key, bad in evidence]  # fmt: skip
    lines += [f"det ledger: {case}: stale ({', '.join(bad)} changed)" for case, bad in stale]
    lines += [f"det ledger: {case}: no entry (a new case? or list it in det_sweep_baseline.json with its cause)"
              for case in missing]  # fmt: skip
    resweep = [c for c, _ in stale] + missing
    if resweep:
        lines.append(f"  refresh the det ledger: {SWEEP.format(cases=','.join(resweep))} && {UPDATE}")
    return lines


def main() -> int:
    lines = report(stale_evidence(), *ledger_gaps())
    for line in lines:
        print(line)
    if lines:
        print("derived: records this branch stales (CI fails on each); refresh them in this PR (#6731)")
        return 1
    print("derived: evidence records and det-sweep ledger current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
