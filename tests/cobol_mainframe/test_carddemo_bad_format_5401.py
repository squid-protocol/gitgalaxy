"""#5401: burned CardDemo CICS cases state bad-format amount and date inputs one validation clause at a time. COTRN02C
checks the amount with four clauses (sign byte, digits 2-9, the point at 10, cents 11-12) and each date with five (year,
'-', month, '-', day); a scenario with the whole field bad fails the first clause and leaves a mutant of any later one
alive. Each scenario below breaks exactly ONE byte of an otherwise valid field, and the test recomputes that from the
COBOL byte positions. CORPT00C rebuilds each date part with NUMVAL-C, so a one-digit EDTMMI is stated too.
Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

GOOD_AMOUNT = "+00000123.45"
GOOD_DATE = "2022-07-18"

# scenario -> (field, 1-based byte that is bad)
AMOUNT = {
    "amount-bad-sign-good-digits": 1,
    "amount-first-digit-not-numeric": 2,
    "amount-last-digit-not-numeric": 9,
    "amount-point-not-a-point": 10,
    "amount-cents-tens-not-numeric": 11,
    "amount-cents-units-not-numeric": 12,
}
DATE = {
    "date-year-first-digit-not-numeric": 1,
    "date-first-separator-wrong": 5,
    "date-month-units-not-numeric": 7,
    "date-second-separator-wrong": 8,
    "date-day-tens-not-numeric": 9,
}
FIELDS = {"orig": "TORIGDTI", "proc": "TPROCDTI"}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    scenarios = case["scenarios"]
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names), f"{name}: duplicate scenario names"
    return {s["name"]: s for s in scenarios}


def _differing_bytes(value, good):
    assert len(value) == len(good), (value, good)
    return [i + 1 for i, (a, b) in enumerate(zip(value, good)) if a != b]


@pytest.mark.parametrize("scenario,byte", sorted(AMOUNT.items()))
def test_tranadd_amount_breaks_one_clause(scenario, byte):
    found = _scenarios("carddemo-tranadd")[scenario]
    screen = found["receive"]["COTRN2A"]
    assert _differing_bytes(screen["TRNAMTI"], GOOD_AMOUNT) == [byte]
    # every other field is the valid add-by-account input, so only the amount can fail
    assert screen["TORIGDTI"] == screen["TPROCDTI"] == GOOD_DATE
    assert "#5401" in found["why"]


@pytest.mark.parametrize("tag", sorted(FIELDS))
@pytest.mark.parametrize("suffix,byte", sorted(DATE.items()))
def test_tranadd_date_breaks_one_clause(tag, suffix, byte):
    found = _scenarios("carddemo-tranadd")[f"{tag}-{suffix}"]
    screen = found["receive"]["COTRN2A"]
    assert _differing_bytes(screen[FIELDS[tag]], GOOD_DATE) == [byte]
    other = FIELDS["proc" if tag == "orig" else "orig"]
    assert screen[other] == GOOD_DATE
    assert screen["TRNAMTI"] == GOOD_AMOUNT
    assert "#5401" in found["why"]


def test_every_clause_of_every_field_is_stated():
    # the amount's four clauses and each date's five: no byte-range of a clause is left without a scenario
    assert {1, 2, 9, 10, 11, 12} <= set(AMOUNT.values())
    assert {1, 5, 7, 8, 9} <= set(DATE.values())


def test_report_states_a_one_digit_end_month():
    found = _scenarios("carddemo-report")["custom-end-month-single-digit"]
    screen = found["receive"]["CORPT0A"]
    assert screen["EDTMMI"] == "6"
    assert screen["SDTMMI"] == "01" and screen["EDTDDI"] == "30" and screen["EDTYYYYI"] == "2022"
    assert "#5401" in found["why"]
