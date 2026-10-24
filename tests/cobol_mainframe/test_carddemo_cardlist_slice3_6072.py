"""#6072 slice 3: the burned CardDemo cardlist case (COCRDLIC) reaches its remaining branches with PF7/PF8 scenarios.
The ENTER forms of these inputs are refused by oracle register X8 (line 518 subscripts VIEW-REQUESTED-ON with
I-SELECTED = 0), so each is stated under a PF key, which skips that test. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-cardlist" / "case.json"
INFEASIBLE = Path(__file__).resolve().parents[1] / "equivalence" / "infeasible_outcomes" / "carddemo-cardlist.json"

# scenario -> (AID, the source line it exists to reach)
STATED = {
    "pf8-with-card-filter-skips-to-the-matching-card": ("DFHPF8", 1397),
    "pf8-page-ends-exactly-on-the-last-card": ("DFHPF8", 1218),
    "pf8-page-number-zero-no-next-page": ("DFHPF8", 1177),
    "pf7-at-the-first-page-account-filter-matches-nothing": ("DFHPF7", 1241),
    "no-commarea-pf7": ("DFHPF7", 315),
    "pf8-back-from-card-view-keeps-the-selected-ids": ("DFHPF8", 844),
}


def _case():
    return json.loads(CASE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(STATED))
def test_cardlist_states_pf_scenario(name):
    aid, _line = STATED[name]
    case = _case()
    (found,) = [s for s in case["scenarios"] if s["name"] == name]
    assert found["aid"] == aid
    assert found["why"]
    assert name not in case["bounds_refused"]


def test_no_commarea_pf7_has_no_commarea():
    (found,) = [s for s in _case()["scenarios"] if s["name"] == "no-commarea-pf7"]
    assert found["commarea"] is None


def test_page_number_zero_scenario_has_no_next_page():
    (found,) = [s for s in _case()["scenarios"] if s["name"] == "pf8-page-number-zero-no-next-page"]
    assert found["commarea"]["WS-CA-SCREEN-NUM"] == 0
    assert found["commarea"]["WS-CA-NEXT-PAGE-IND"] == "\x00"


def test_card_filter_scenario_names_a_card_that_follows_the_last_card():
    (found,) = [s for s in _case()["scenarios"] if s["name"] == "pf8-with-card-filter-skips-to-the-matching-card"]
    card = found["receive"]["CCRDLIA"]["CARDSIDI"]
    assert len(card) == 16 and card.isdigit()
    assert card > found["commarea"]["WS-CA-LAST-CARD-NUM"]


def test_the_two_outcomes_left_stay_stated_infeasible():
    text = INFEASIBLE.read_text(encoding="utf-8")
    entries = json.loads(text)["entries"]
    assert {(e["line"], e["outcome"]) for e in entries} == {(757, "true"), (897, "OTHER")}
