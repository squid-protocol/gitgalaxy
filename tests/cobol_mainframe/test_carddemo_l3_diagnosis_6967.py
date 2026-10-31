"""#6967: the diagnosis of the four CardDemo L3 programs (docs/language_status/carddemo_l3_diagnosis.md) is pinned to
the committed ledgers, so an arm that opens (or closes) fails here instead of the doc going stale. Pure Python."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "tests" / "equivalence"

# Net uncovered branches per evidence-backed case: (line, outcome) left after the stated infeasible entries.
OPEN_ARMS = {"carddemo-cbpaup0c": set(), "carddemo-dateutil": set()}
# The det sweep's ledger: fully covered, nothing to diagnose.
FULL = {"carddemo-coacct01": (13, 33), "carddemo-codate01": (13, 28)}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_net_uncovered_arms_are_exactly_the_diagnosed_ones():
    for case, expected in OPEN_ARMS.items():
        uncovered = {
            (b["line"], b["outcome"]) for b in _load(EQ / case / "evidence.json")["coverage"]["uncovered_branches"]
        }
        stated_path = EQ / "infeasible_outcomes" / f"{case}.json"
        stated = {(e.get("line"), e["outcome"]) for e in _load(stated_path)["entries"] if e["kind"] != "PARAGRAPH"}
        assert uncovered - stated == expected, case


def test_coacct01_and_codate01_are_fully_covered_in_the_sweep_ledger():
    for case, (paragraphs, branches) in FULL.items():
        entry = _load(EQ / "det_sweep_coverage" / f"{case}.json")
        assert entry["paragraphs"] == {"covered": paragraphs, "live": paragraphs}, case
        assert entry["branches"] == {"covered": branches, "total": branches}, case


def test_the_harness_mechanisms_the_diagnosis_names_are_in_the_cases():
    for case in ("carddemo-coacct01", "carddemo-codate01"):
        assert _load(EQ / case / "case.json").get("perform_stack_check") is True, case  # register C20
    faults = _load(EQ / "carddemo-cbpaup0c" / "case.json").get("faults", [])
    assert any(f.get("ims_seed") for f in faults)  # #6995
