"""#5401: the cardlist case (COCRDLIC) kills the mutation survivors its ENTER-shaped scenarios cannot state.
Oracle register X8 refuses every ENTER with nothing selected (line 518 subscripts VIEW-REQUESTED-ON with
I-SELECTED = 0), so each survivor is stated under a PF key, which skips that test. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-cardlist" / "case.json"

# scenario -> (AID, survivor id it kills)
STATED = {
    "pf8-with-all-zeros-account-filter": ("DFHPF8", "1761ccd4aa"),
    "pf8-with-all-zeros-card-filter": ("DFHPF8", "d9ff5e4dbc"),
    "pf8-endbr-invreq": ("DFHPF8", "fc564b048f"),
    "pf7-endbr-invreq": ("DFHPF7", "fc564b048f"),
    # killed by scenarios stated earlier (re-judged in #5401)
    "pf8-back-from-card-view-keeps-the-selected-ids": ("DFHPF8", "103529adf5"),
    "pf3-from-menu-stale-first-card-faulting-carddat": ("DFHPF3", "0e7e448057"),
}


def _scenarios():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    return case, {s["name"]: s for s in case["scenarios"]}


@pytest.mark.parametrize("name", sorted(STATED))
def test_survivor_scenario_is_a_pf_key_and_not_refused(name):
    aid, _survivor = STATED[name]
    case, by_name = _scenarios()
    assert by_name[name]["aid"] == aid
    assert by_name[name]["why"]
    assert name not in case["bounds_refused"]


@pytest.mark.parametrize("name", ["pf8-with-all-zeros-account-filter", "pf8-with-all-zeros-card-filter"])
def test_zero_filters_are_all_zeros_of_the_declared_width(name):
    _case, by_name = _scenarios()
    (field, value), = by_name[name]["receive"]["CCRDLIA"].items()
    assert field in ("ACCTSIDI", "CARDSIDI")
    assert len(value) == (11 if field == "ACCTSIDI" else 16)
    assert set(value) == {"0"}


@pytest.mark.parametrize("name", ["pf8-endbr-invreq", "pf7-endbr-invreq"])
def test_endbr_scenarios_fault_the_endbr_with_invreq(name):
    _case, by_name = _scenarios()
    (fault,) = by_name[name]["faults"]
    assert (fault["cmd"], fault["file"], fault["resp"]) == ("ENDBR", "CARDDAT", "INVREQ")


def test_every_refused_scenario_is_still_an_enter():
    """X8 only refuses the ENTER forms: a PF scenario in bounds_refused would mean line 518 is reached another way."""
    case, by_name = _scenarios()
    assert {by_name[n]["aid"] for n in case["bounds_refused"]} <= {"DFHENTER", "DFHPF5"}
