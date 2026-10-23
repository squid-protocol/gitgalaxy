"""#6072: the burned CardDemo COPAUS0C case reaches four more branches (SEL0004, a GNP that ends the list, an SCHD that
fails once and always), and states three outcomes no input reaches. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIV = Path(__file__).resolve().parents[1] / "equivalence"
CASE = EQUIV / "carddemo-copaus0c" / "case.json"
INFEASIBLE = EQUIV / "infeasible_outcomes" / "carddemo-copaus0c.json"

# scenario -> the dli_faults it injects (None: none)
NEW = {
    "select-row-4": None,
    "enter-account-probe-gnp-ends": [{"op": "GNP", "nth": 6, "status": "GE"}],
    "enter-schd-tc-once": [{"op": "SCHD", "nth": 1, "status": "TC"}],
    "enter-schd-fails": [{"op": "SCHD", "nth": "*", "status": "TC"}],
}


def _case():
    return json.loads(CASE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(NEW))
def test_copaus0c_states_scenario(name):
    case = _case()
    (found,) = [s for s in case["scenarios"] if s["name"] == name]
    assert found["why"]
    assert found.get("dli_faults") == NEW[name]
    assert name not in case.get("bounds_refused", {})


def test_select_row_4_selects_the_fourth_row():
    (found,) = [s for s in _case()["scenarios"] if s["name"] == "select-row-4"]
    assert found["receive"]["COPAU0A"]["SEL0004I"] == "S"


def test_the_three_outcomes_stay_stated_infeasible():
    entries = json.loads(INFEASIBLE.read_text(encoding="utf-8"))["entries"]
    assert {(e["line"], e["outcome"]) for e in entries} == {(542, "OTHER"), (612, "OTHER"), (668, "true")}
