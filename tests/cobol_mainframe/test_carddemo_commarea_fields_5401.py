"""#5401: three burned CardDemo CICS cases state the caller COMMAREA fields their mutants read: a non-blank
CDEMO-TO-TRANID (cardview 6d63a520f9, tranlist bdeaa77fbe) and an all LOW-VALUES CDEMO-FROM-PROGRAM on PF3 (tranadd
e31af14845). Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> (scenario, field, predicate on the input COMMAREA value)
STATED = {
    "carddemo-cardview": ("enter-carried-to-tranid", "CDEMO-TO-TRANID", lambda v: bool(v.strip())),
    "carddemo-tranlist": ("select-with-carried-to-tranid", "CDEMO-TO-TRANID", lambda v: bool(v.strip())),
    "carddemo-tranadd": ("pf3-low-values-from-program", "CDEMO-FROM-PROGRAM", lambda v: v == "\u0000" * 8),
}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    return case["scenarios"]


@pytest.mark.parametrize("name", sorted(STATED))
def test_case_states_commarea_field(name):
    scenario, field, ok = STATED[name]
    scenarios = _scenarios(name)
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names), f"{name}: duplicate scenario names"
    (found,) = [s for s in scenarios if s["name"] == scenario]
    assert ok(found["commarea"][field]), f"{name}: {scenario} no longer sets {field}"
    assert "#5401" in found["why"]
