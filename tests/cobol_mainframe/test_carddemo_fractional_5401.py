"""#5401: burned CardDemo CICS cases state fractional values that a PIC target truncates. COTRN02C moves NUMVAL-C of the
amount into PIC S9(9)V99 and the port truncates it (RoundingMode.DOWN); a scenario whose cents are all below .50 leaves a
HALF_UP mutant alive, because rounding the integer part up only shows from .50. So the amount is stated below, at and above
half, in both signs. CORPT00C's date parts take the same NUMVAL-C but are not stated fractional: see the last test.
Pure JSON, no Java or Docker."""

import json
from pathlib import Path

import pytest

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

GOOD_AMOUNT = "+00000123.45"
# scenario -> TRNAMTI
AMOUNTS = {
    "amount-fraction-above-half": "+00000123.75",
    "amount-fraction-at-half": "+00000123.50",
    "amount-fraction-nines": "+00000123.99",
    "amount-negative-fraction-above-half": "-00000123.75",
}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    names = [s["name"] for s in case["scenarios"]]
    assert len(set(names)) == len(names), f"{name}: duplicate scenario names"
    return {s["name"]: s for s in case["scenarios"]}


@pytest.mark.parametrize("scenario,amount", sorted(AMOUNTS.items()))
def test_tranadd_amount_has_a_fraction_at_or_above_half(scenario, amount):
    found = _scenarios("carddemo-tranadd")[scenario]
    screen = found["receive"]["COTRN2A"]
    assert screen["TRNAMTI"] == amount
    # a valid format (sign, 8 digits, the point, 2 digits), so only the rounding can tell a mutant apart
    assert len(amount) == len(GOOD_AMOUNT) and amount[0] in "+-" and amount[9] == "."
    assert amount[1:9].isdigit() and amount[10:].isdigit()
    assert int(amount[10:]) >= 50
    assert screen["TORIGDTI"] == screen["TPROCDTI"] == "2022-07-18"
    assert "#5401" in found["why"]


def test_tranadd_states_the_fraction_below_at_and_above_half_and_both_signs():
    cents = {int(a[10:]) for a in AMOUNTS.values()}
    assert any(c > 50 for c in cents) and 50 in cents
    assert {a[0] for a in AMOUNTS.values()} == {"+", "-"}
    assert int(GOOD_AMOUNT[10:]) < 50  # the case's own valid amount is the below-half member


def test_report_states_no_fractional_date_part():
    # NUMVAL-C('.9') into PIC 99: GnuCOBOL truncates (00), IBM rounds a float-mode store (01, register C6), so the oracle and
    # the det port disagree by design and the scenario cannot be proven; CORPT00C d2fca7d77a stays a sibling gap
    case = json.loads((EQUIVALENCE / "carddemo-report" / "case.json").read_text(encoding="utf-8"))
    for scenario in case["scenarios"]:
        screen = scenario.get("receive", {}).get("CORPT0A", {})
        for field, value in screen.items():
            if field[:3] in ("SDT", "EDT"):
                assert "." not in value, (scenario["name"], field)
