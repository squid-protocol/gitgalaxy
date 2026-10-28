"""#6882 (register X26): the burned CBSA programs that SET TERMINAL (BNK1CCS, BNK1DCS) each carry a scenario that plans
IBM's two SET TERMINAL failures, INVREQ (RESP2 43) and TERMIDERR (RESP2 23), so the failure arm after the SET runs in
both runtimes. The plan lines are the ones the stub's injected() and the port's task.planned() read."""

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402

EQUIVALENCE = TESTS / "equivalence"
PROGRAMS = ["bnk1ccs", "bnk1dcs"]
EXPECTED = {"INVREQ": "SET-TERMINAL - 1 16 43", "TERMIDERR": "SET-TERMINAL - 1 11 23"}


def _planned(program):
    case = json.loads((EQUIVALENCE / f"cbsa-{program}" / "case.json").read_text(encoding="utf-8"))
    found = {}
    for scenario in case["scenarios"]:
        for fault in scenario.get("faults", []):
            if fault.get("cmd") == "SET-TERMINAL":
                found.setdefault(fault["resp"], []).append(ec.fault_lines(scenario))
    return found


@pytest.mark.parametrize("program", PROGRAMS)
@pytest.mark.parametrize("resp", sorted(EXPECTED))
def test_each_set_terminal_program_plans_both_failures(program, resp):
    plans = _planned(program).get(resp)
    assert plans, f"cbsa-{program} has no scenario planning SET TERMINAL {resp}"
    assert all(EXPECTED[resp] in lines for lines in plans)
