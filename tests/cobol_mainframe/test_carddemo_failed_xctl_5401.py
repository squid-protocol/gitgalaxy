"""#5401: burned CardDemo CICS cases with an XCTL site state a scenario where that XCTL answers PGMIDERR (the source
has no RESP, so CICS abends the task): tranlist select to COTRN01C (9e54fb034b) and PF3 to COMEN01C, report PF3 to
COMEN01C, userupd PF3 after the save to COADM01C. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> [(scenario, faulted XCTL target)]
STATED = {
    "carddemo-tranlist": [("select-xctl-fails", "COTRN01C"), ("pf3-xctl-fails", "COMEN01C")],
    "carddemo-report": [("pf3-xctl-fails", "COMEN01C")],
    "carddemo-userupd": [("pf3-saves-then-xctl-fails", "COADM01C")],
}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    return case["scenarios"]


@pytest.mark.parametrize("name", sorted(STATED))
def test_case_states_failed_xctl(name):
    scenarios = _scenarios(name)
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names), f"{name}: duplicate scenario names"
    for scenario, target in STATED[name]:
        (found,) = [s for s in scenarios if s["name"] == scenario]
        assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]
        assert "#5401" in found["why"]
