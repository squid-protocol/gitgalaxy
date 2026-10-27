"""#6166: COUSR00C treats an id or a flag as absent when it is SPACES or LOW-VALUES (NOT = SPACES AND LOW-VALUES, or
= SPACES OR LOW-VALUES). The two forms are different bytes: spaces is a field the terminal sent blank, LOW-VALUES is a
field never received (or a COMMAREA id of NULs). The case states each test with both forms: the row selection (flag and
id, rows 1 / 3 / 10, U and D), the typed search id, and the carried first / last page ids (PF7 on page 1 and past it,
PF8). Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-userlist" / "case.json"
NUL8 = "\x00" * 8


def _by_name():
    scenarios = json.loads(CASE.read_text(encoding="utf-8"))["scenarios"]
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names)
    return dict(zip(names, scenarios, strict=True))


def _screen(scenario):
    return scenario["receive"]["COUSR0A"]


# the carried page ids: (scenario, COMMAREA field, value, AID, page number)
CARRIED = [
    ("pf7-with-no-first-id", "CDEMO-CU00-USRID-FIRST", "", "DFHPF7", 1),
    ("pf7-first-id-nul-page-1", "CDEMO-CU00-USRID-FIRST", NUL8, "DFHPF7", 1),
    ("pf7-first-id-blank-page-3", "CDEMO-CU00-USRID-FIRST", "", "DFHPF7", 3),
    ("pf7-first-id-nul-page-3", "CDEMO-CU00-USRID-FIRST", NUL8, "DFHPF7", 3),
    ("pf8-with-no-last-id", "CDEMO-CU00-USRID-LAST", "", "DFHPF8", 1),
    ("pf8-with-low-values-last-id", "CDEMO-CU00-USRID-LAST", NUL8, "DFHPF8", 1),
]


@pytest.mark.parametrize(("name", "field", "value", "aid", "page"), CARRIED)
def test_carried_page_id_states_both_blank_forms(name, field, value, aid, page):
    found = _by_name()[name]
    assert found["aid"] == aid
    assert found["commarea"][field] == value
    assert found["commarea"]["CDEMO-CU00-PAGE-NUM"] == page


def test_search_id_states_the_spaces_form_and_the_unreceived_form():
    scenarios = _by_name()
    assert _screen(scenarios["enter-search-id-spaces"]) == {"USRIDINI": ""}
    assert _screen(scenarios["enter-lists-from-the-start"]) == {}


# scenario -> (screen fields, rows whose id is blank or unreceived); a blank-id row never transfers
SELECTIONS = {
    "select-row-1-blank-id": {"SEL0001I": "U", "USRID01I": ""},
    "select-delete-row-10-blank-id": {"SEL0010I": "D", "USRID10I": ""},
    "select-delete-row-3-nul-id": {"SEL0003I": "D"},
    "select-row-with-no-id-received": {"SEL0001I": "U"},
    "select-in-an-empty-row": {"SEL0008I": "U", "USRID08I": ""},
}


@pytest.mark.parametrize("name", sorted(SELECTIONS))
def test_selection_with_no_id_states_the_form(name):
    scenarios = _by_name()
    assert _screen(scenarios[name]) == SELECTIONS[name]
    assert not scenarios[name].get("faults")


def test_flag_variants_beside_a_real_id():
    scenarios = _by_name()
    assert _screen(scenarios["blank-flag-row-1-then-select-row-2"]) == {
        "SEL0001I": " ",
        "USRID01I": "ADMIN001",
        "SEL0002I": "U",
        "USRID02I": "ADMIN002",
    }
    assert _screen(scenarios["nul-flag-row-1-then-select-row-2"]) == {
        "USRID01I": "ADMIN001",
        "SEL0002I": "D",
        "USRID02I": "ADMIN002",
    }


def test_new_scenarios_carry_the_issue_tag():
    scenarios = _by_name()
    for name in (
        "enter-search-id-spaces",
        "pf7-first-id-nul-page-1",
        "pf7-first-id-blank-page-3",
        "pf7-first-id-nul-page-3",
        "select-row-1-blank-id",
        "select-delete-row-10-blank-id",
        "select-delete-row-3-nul-id",
        "blank-flag-row-1-then-select-row-2",
        "nul-flag-row-1-then-select-row-2",
    ):
        assert "#6166" in scenarios[name]["why"]
