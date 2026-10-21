"""#5401: burned CardDemo CICS cases state the caller COMMAREA fields their mutants read: a non-blank
CDEMO-TO-TRANID (cardview 6d63a520f9, tranlist bdeaa77fbe) and an all LOW-VALUES CDEMO-FROM-PROGRAM on PF3 (tranadd
e31af14845), and a 12-character CDEMO-CB00-TRN-SELECTED on billpay (d3458d6107), and on cardlist a non-blank WS-RETURN-FLAG (62c41cc4a8) and a stale first-card account id on a menu entry
(6fef123a15). Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> (scenario, field, predicate on the input COMMAREA value)
STATED = {
    "carddemo-cardview": ("enter-carried-to-tranid", "CDEMO-TO-TRANID", lambda v: bool(v.strip())),
    "carddemo-tranlist": ("select-with-carried-to-tranid", "CDEMO-TO-TRANID", lambda v: bool(v.strip())),
    "carddemo-billpay": ("first-entry-with-long-selected-account", "CDEMO-CB00-TRN-SELECTED", lambda v: len(v) >= 12),
    "carddemo-tranadd": ("pf3-low-values-from-program", "CDEMO-FROM-PROGRAM", lambda v: v == "\u0000" * 8),
    "carddemo-cardlist": ("pf8-next-page-carries-return-flag", "WS-RETURN-FLAG", lambda v: bool(v.strip())),
}

# a second scenario on the same case: (scenario, field, predicate)
EXTRA = {
    "carddemo-cardlist": ("pf3-from-menu-stale-first-card-faulting-carddat", "WS-CA-FIRST-CARD-ACCT-ID", lambda v: v != 0),
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


@pytest.mark.parametrize("name", sorted(EXTRA))
def test_case_states_stale_field_on_menu_entry(name):
    scenario, field, ok = EXTRA[name]
    (found,) = [s for s in _scenarios(name) if s["name"] == scenario]
    assert ok(found["commarea"][field]), f"{name}: {scenario} no longer sets {field}"
    assert found["commarea"]["CDEMO-FROM-PROGRAM"] == "COMEN01C"
    assert found["commarea"]["CDEMO-PGM-CONTEXT"] == 0
    assert [f["file"] for f in found["faults"]] == ["CARDDAT"]
    assert "#5401" in found["why"]
