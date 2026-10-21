"""#5401: every burned CardDemo CICS port states EIBCALEN (`commarea_length`) in at least one scenario, so the mutants
that depend on the COMMAREA length stay killable. The eight cases are a literal list: a new burned CICS port needs a
deliberate addition here. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> the commarea_length values its scenarios state today (cardview and cardlist: whole COMMAREA only, X23).
STATED = {
    "carddemo-adminmenu": {146, 159},
    "carddemo-userupd": {185, 186},
    "carddemo-report": {146, 153},
    "carddemo-tranlist": {160},
    "carddemo-billpay": {200, 201},
    "carddemo-tranadd": {200, 201},
    "carddemo-cardview": {172},
    "carddemo-cardlist": {414},
}


def _lengths(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    return [s["commarea_length"] for s in case["scenarios"] if "commarea_length" in s]


@pytest.mark.parametrize("name", sorted(STATED))
def test_case_states_eibcalen(name):
    lengths = _lengths(name)
    assert lengths, f"{name}: no scenario sets commarea_length (EIBCALEN)"
    assert all(isinstance(n, int) and n > 0 for n in lengths)
    assert len(set(lengths)) == len(lengths), f"{name}: duplicate commarea_length scenarios"
    assert set(lengths) >= STATED[name]
