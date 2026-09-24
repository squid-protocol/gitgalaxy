"""tests/tools/ground_truth_diff.py: the reviewer-facing semantic diff of the keys and the ledger."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ground_truth_diff as gd  # noqa: E402


def _key(dead, census=None):
    v = {"status": "validated", "tier": "cross_verified", "by": "m", "at": "d", "notes": []}
    if census:
        v["census"] = census
    return {
        "corpus": "k",
        "programs": {
            "A.cbl": {
                "program_id": "A",
                "units": [{"name": "MAIN"}, {"name": "A999"}],
                "dead": dead,
                "copybooks": [],
                "calls": [],
                "files": [],
                "verification": v,
            }
        },
    }


def test_truth_change_after_census_is_flagged():
    base = _key({}, census={"by": "r", "at": "2026-09-24"})
    head = _key({"A999": {"reason": "r", "trivial": True}}, census={"by": "r", "at": "2026-09-24"})
    lines, warnings = gd.diff_keys(base, head)
    assert any("dead: +['A999']" in line for line in lines)
    assert warnings and "re-census" in warnings[0]


def test_truth_change_with_a_new_census_is_not_flagged():
    base = _key({}, census={"by": "r", "at": "2026-09-24"})
    head = _key({"A999": {"reason": "r", "trivial": True}}, census={"by": "r", "at": "2026-09-25"})
    assert gd.diff_keys(base, head)[1] == []


def test_defect_turned_deliberate_is_flagged():
    base = {
        "causes": {"c": {"kind": "defect", "issue": 1}},
        "corpora": {"k": {"mismatches": {"e": "c"}, "scoreboard": {}}},
    }
    head = copy.deepcopy(base)
    head["causes"]["c"]["kind"] = "deliberate"
    lines, warnings = gd.diff_ledger(base, head)
    assert any("defect → deliberate" in line for line in lines)
    assert warnings and "defect → deliberate" in warnings[0]


def test_scoreboard_movement_is_reported():
    sb = {"dead": {"truth": "x", "engine": {"tp": 1, "got": 2, "truth": 1}, "forge": None}}
    base = {"causes": {}, "corpora": {"k": {"mismatches": {}, "scoreboard": sb}}}
    head = copy.deepcopy(base)
    head["corpora"]["k"]["scoreboard"]["dead"]["engine"]["got"] = 1
    lines, _ = gd.diff_ledger(base, head)
    assert "| k | dead | engine | P 1/2 R 1/1 | P 1/1 R 1/1 |" in lines
