"""#5401: the burned CardDemo cardlist case (COCRDLIC) states a scenario for each of its three XCTL sites answering
PGMIDERR (the source has no RESP, so CICS abends the task): PF3 to the menu COMEN01C (line 402), 'S' to COCRDSLC (538),
'U' to COCRDUPC (566). Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-cardlist" / "case.json"

# scenario -> (AID, receive map, faulted XCTL target)
STATED = {
    "pf3-xctl-fails": ("DFHPF3", {"CCRDLIA": {}}, "COMEN01C"),
    "select-view-xctl-fails": ("DFHENTER", {"CCRDLIA": {"CRDSEL3I": "S"}}, "COCRDSLC"),
    "select-update-xctl-fails": ("DFHENTER", {"CCRDLIA": {"CRDSEL5I": "U"}}, "COCRDUPC"),
}


def _case():
    return json.loads(CASE.read_text(encoding="utf-8"))


def test_scenario_names_are_unique():
    names = [s["name"] for s in _case()["scenarios"]]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("name", sorted(STATED))
def test_cardlist_states_failed_xctl(name):
    aid, receive, target = STATED[name]
    case = _case()
    (found,) = [s for s in case["scenarios"] if s["name"] == name]
    assert found["aid"] == aid
    assert found["receive"] == receive
    assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]
    assert "#5401" in found["why"]
    assert name not in case["bounds_refused"]
