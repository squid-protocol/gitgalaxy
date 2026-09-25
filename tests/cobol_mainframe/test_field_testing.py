"""Field-testing record (tests/cobol_mainframe/field_testing.json) and its counters.

The real record must validate against the corpus manifest and the ledger, and the generated
report (docs/language_status/cics_field_testing.md) must be current. The counting rules --
development rounds are not fresh, only fresh rounds after the last engine defect count, and a
field needs CLEAN_ROUNDS such rounds carrying CLEAN_FACTS facts -- are pinned on a synthetic
record so they cannot drift quietly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import field_testing as ft  # noqa: E402


def test_the_record_is_valid_and_the_report_is_current():
    registry, ledger, corpora = ft.load()
    assert ft.validate(registry, ledger, corpora) == []
    assert ft.REPORT.read_text(encoding="utf-8") == ft.render(registry, ledger), (
        "stale: python tests/tools/field_testing.py report --write"
    )


def _ledger(facts: dict[str, int], tier: str = "cross_verified") -> dict:
    return {name: {"scoreboard": {"units": {"truth": tier, "engine": {"truth": n}}}} for name, n in facts.items()}


def _registry(defect_rounds: list[int], dev: int, private: bool = False) -> dict:
    estates = [{"id": f"e{i}", "kind": "public", "round": i} for i in range(1, 6)]
    if private:
        estates.append({"id": "p1", "kind": "private", "round": 6, "label": "private-01", "fields": ["units"]})
    return {
        "estates": estates,
        "fields": {"units": {"introduced": "#1", "development_rounds": dev}},
        "defects": [
            {"id": f"D{r}", "estate": f"e{r}", "side": "engine", "severity": "fact", "fields": ["units"]}
            for r in defect_rounds
        ],
    }


def _units(registry: dict, ledger: dict) -> dict:
    return next(r for r in ft.counters(registry, ledger) if r["field"] == "units")


def test_development_rounds_count_as_tested_but_not_fresh():
    row = _units(_registry([], dev=3), _ledger({f"e{i}": 200 for i in range(1, 6)}))
    assert (row["public"], row["fresh"], row["clean_rounds"], row["clean_facts"]) == (5, 2, 2, 400)
    assert row["status"] == "field-tested"


def test_a_defect_resets_the_clean_rounds_and_thin_facts_keep_a_field_open():
    ledger = _ledger({f"e{i}": 200 for i in range(1, 6)})
    row = _units(_registry([4], dev=3), ledger)  # a defect in fresh round 4: only round 5 is clean
    assert (row["engine_defects"], row["clean_rounds"], row["status"]) == (1, 1, "open")
    thin = _units(_registry([], dev=3), _ledger({f"e{i}": 100 for i in range(1, 6)}))
    assert (thin["clean_rounds"], thin["clean_facts"], thin["status"]) == (2, 200, "open")
    assert "100 more clean fresh facts" in thin["needs"]


def test_a_draft_tier_does_not_test_a_field_and_a_private_estate_counts_by_its_listed_fields():
    row = _units(_registry([], dev=0), _ledger({f"e{i}": 50 for i in range(1, 6)}, tier="draft"))
    assert (row["public"], row["status"]) == (0, "untested")
    row = _units(_registry([], dev=3, private=True), _ledger({f"e{i}": 200 for i in range(1, 6)}))
    assert (row["public"], row["private"], row["fresh"]) == (5, 1, 3)


def test_a_private_estate_may_not_carry_identifying_fields():
    registry, ledger, corpora = ft.load()
    registry["estates"].append(
        {"id": "p9", "kind": "private", "round": 99, "label": "private-09", "fields": ["units"], "url": "x"}
    )
    assert any("anonymised" in e for e in ft.validate(registry, ledger, corpora))
