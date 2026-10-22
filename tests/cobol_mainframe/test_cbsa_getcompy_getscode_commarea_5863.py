"""#5863: the CBSA GETCOMPY / GETSCODE cases state a call with no COMMAREA, EIBCALEN shorter than the record
(`commarea_length`, X23) and a caller value longer than its field, so the generated COMMAREA scaffolding's mutants stay killable. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> the commarea_length values its scenarios state: 0 (record present, EIBCALEN 0) and a part of the record
LENGTHS = {"cbsa-getcompy": {0, 20, 40}, "cbsa-getscode": {0, 3, 6}}
# case -> (the field, its width): one scenario states a value wider than the field
LONGER = {
    "cbsa-getcompy": ("longer-caller-name", "COMPANY-NAME", 40),
    "cbsa-getscode": ("longer-sortcode", "SORTCODE", 6),
}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    return {s["name"]: s for s in case["scenarios"]}


@pytest.mark.parametrize("name", sorted(LENGTHS))
def test_case_states_no_commarea_and_short_eibcalen(name):
    scenarios = _scenarios(name)
    assert "no-commarea" in scenarios
    assert scenarios["no-commarea"]["commarea"] is None
    assert "commarea_length" not in scenarios["no-commarea"]
    stated = {s["commarea_length"] for s in scenarios.values() if "commarea_length" in s}
    assert stated == LENGTHS[name]


@pytest.mark.parametrize("name", sorted(LONGER))
def test_case_states_a_value_longer_than_its_field(name):
    scenario, field, width = LONGER[name]
    assert len(_scenarios(name)[scenario]["commarea"][field]) > width
