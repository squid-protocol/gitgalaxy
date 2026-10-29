"""#6967: every branch outcome behind a burned ENQ / DEQ / FETCH / container / CEELOCT command is closed.

The burned CBSA programs that code RESP (or a feedback code) on these commands are CRECUST (ENQ, DEQ, FETCH ANY, PUT / GET
CONTAINER, CEELOCT), CREACC (ENQ, DEQ) and CRDTAGY1-5 (GET / PUT CONTAINER, DELAY). For each case, an outcome the det sweep
leaves uncovered must carry a reviewed infeasible entry (nothing is hidden), and a fault a scenario plans must be a command
in the harness vocabulary. DEQ has no fault key: IBM lists only operand conditions for it (register X60).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EQUIV = ROOT / "tests" / "equivalence"
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_cics  # noqa: E402,F401  (loads first: equivalence_cics_faults imports it back)
import equivalence_cics_faults as ecf  # noqa: E402

CASES = ("cbsa-crecust", "cbsa-creacc", *(f"cbsa-crdtagy{n}" for n in range(1, 6)))
DEQ_CASES = (("cbsa-crecust", 478), ("cbsa-creacc", 419))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _uncovered(case: str) -> set[str]:
    return set(_json(EQUIV / "det_sweep_coverage" / f"{case}.json").get("uncovered", {}).get("branches", ()))


def _stated(case: str) -> set[str]:
    entries = _json(EQUIV / "infeasible_outcomes" / f"{case}.json")["entries"]
    return {f"{e['line']}:{e['outcome']}" for e in entries if e.get("line")}


@pytest.mark.parametrize("case", CASES)
def test_every_uncovered_outcome_is_a_reviewed_infeasible_entry(case: str) -> None:
    assert _uncovered(case) - _stated(case) == set()


@pytest.mark.parametrize("case", CASES)
def test_a_planned_fault_is_in_the_harness_vocabulary(case: str) -> None:
    scenarios = _json(EQUIV / case / "case.json")["scenarios"]
    used = {f["cmd"] for sc in scenarios for f in sc.get("faults", ())}
    assert used <= set(ecf.FAULT_COMMANDS)


def test_the_vocabulary_covers_the_burned_command_families() -> None:
    for cmd in ("ENQ", "FETCH-ANY", "FETCH-STATUS", "PUT-CONTAINER", "GET-CONTAINER", "CALL-CEELOCT"):
        assert cmd in ecf.FAULT_COMMANDS
    assert "DEQ" not in ecf.FAULT_COMMANDS  # IBM lists LENGERR 1 / INVREQ 2 only: operand conditions, no region fault


@pytest.mark.parametrize(("case", "line"), DEQ_CASES)
def test_the_deq_arm_states_ibms_condition_list(case: str, line: int) -> None:
    entry = next(e for e in _json(EQUIV / "infeasible_outcomes" / f"{case}.json")["entries"] if e.get("line") == line)
    assert "LENGERR (RESP2 1" in entry["reason"]
    assert "INVREQ (RESP2 2" in entry["reason"]
