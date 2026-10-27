"""Port-side blocker ledger (tests/cobol_mainframe/port_blockers.json, #5051) and its generated report.

The real ledger must validate and its report be current. The validator rules are pinned on synthetic ledgers:
every side and class, an estate or none, burned-only estates, the derived new_class, and a deterministic render.
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import port_blockers as pb  # noqa: E402

BURNED = {"zecs", "cics-genapp", "census-only"}
REGISTRY = {
    "estates": [
        {"id": "zecs", "kind": "public", "round": 1},
        {"id": "cics-genapp", "kind": "public", "round": 2},
        {"id": "census-only", "kind": "public", "round": 3},
        {"id": "unburned", "kind": "public", "round": 4},
    ]
}


def _blocker(i: int, **kw) -> dict:
    b = {
        "id": f"P{i:03d}",
        "estate": "zecs",
        "after_round": 1,
        "side": "det",
        "class": "cics-command",
        "programs": ["a"],
        "issue": 1,
        "fixed_by": None,
        "refused_by_name": False,
        "new_class": True,
        "summary": "x",
    }
    b.update(kw)
    return b


def _ledger(*blockers: dict) -> dict:
    real, _ = pb.load()
    return {**{k: real[k] for k in ("sides", "classes", "found_by")}, "blockers": list(blockers)}


def _errors(*blockers: dict) -> list[str]:
    return pb.validate(_ledger(*blockers), REGISTRY, BURNED)


def test_the_real_ledger_is_valid_and_the_report_is_current():
    ledger, registry = pb.load()
    burned = pb.burned_names()
    assert pb.validate(ledger, registry, burned) == []
    assert pb.REPORT.read_text(encoding="utf-8") == pb.render(ledger, registry, burned), (
        "stale: python tests/tools/port_blockers.py report --write"
    )


def test_every_side_and_class_is_accepted_and_others_are_not():
    real, _ = pb.load()
    for side in real["sides"]:
        assert _errors(_blocker(1, side=side)) == []
    for cls in real["classes"]:
        assert _errors(_blocker(1, **{"class": cls})) == []
    assert any("side must be" in e for e in _errors(_blocker(1, side="oracle")))
    assert any("class must be" in e for e in _errors(_blocker(1, **{"class": "weather"})))


def test_new_class_is_derived_from_the_first_blocker_of_a_class():
    assert _errors(_blocker(1), _blocker(2, new_class=False)) == []
    assert any("new_class must be false" in e for e in _errors(_blocker(1), _blocker(2)))
    assert any("new_class must be true" in e for e in _errors(_blocker(1, new_class=False)))


def test_an_estate_must_be_known_burned_and_match_its_round():
    assert any("unknown estate" in e for e in _errors(_blocker(1, estate="nowhere")))
    assert any("not a burned estate" in e for e in _errors(_blocker(1, estate="unburned", after_round=4)))
    assert any("estate's round 2" in e for e in _errors(_blocker(1, estate="cics-genapp", after_round=1)))
    assert any("only for a blocker with no estate" in e for e in _errors(_blocker(1, found_by="review")))


def test_a_blocker_with_no_estate_names_its_source_and_a_round():
    assert _errors(_blocker(1, estate=None, found_by="crucible", after_round=3)) == []
    assert any("found_by" in e for e in _errors(_blocker(1, estate=None, after_round=3)))
    assert any("after_round" in e for e in _errors(_blocker(1, estate=None, found_by="review", after_round=9)))


def test_required_fields_and_references():
    assert any("duplicate" in e for e in _errors(_blocker(1), _blocker(1, new_class=False)))
    assert any("cite an issue" in e for e in _errors(_blocker(1, issue=None)))
    assert _errors(_blocker(1, issue=None, fixed_by="#12")) == []
    assert any("fixed_by is a PR" in e for e in _errors(_blocker(1, fixed_by="12")))
    assert any("refused_by_name" in e for e in _errors(_blocker(1, refused_by_name="yes")))
    assert any("summary" in e for e in _errors(_blocker(1, summary="")))
    assert any("programs is a list" in e for e in _errors(_blocker(1, programs="a")))


def test_the_report_counts_per_estate_and_is_deterministic():
    ledger = _ledger(
        _blocker(1),
        _blocker(2, new_class=False, programs=["a", "b"]),
        _blocker(3, estate="cics-genapp", after_round=2, **{"class": "vsam"}),
    )
    text = pb.render(ledger, REGISTRY, BURNED)
    assert text == pb.render(copy.deepcopy(ledger), REGISTRY, BURNED)
    assert "| 1 | zecs | 2 | 2 | 1 | 1 | 2 | 1.00 | 0 |" in text
    assert "| 2 | cics-genapp | 1 | 3 | 1 | 0 | 1 | 1.00 | 0 |" in text
    assert "unburned" not in text


def test_new_class_follows_discovery_order_not_file_order():
    late = _blocker(1, estate="cics-genapp", after_round=2, new_class=False)
    early = _blocker(2, estate="zecs", after_round=1)
    assert _errors(late, early) == []
    assert any("new_class must be" in e for e in _errors(_blocker(1, estate="cics-genapp", after_round=2), early))


def test_the_real_ledger_cites_each_issue_once():
    real, _ = pb.load()
    issues = [b["issue"] for b in real["blockers"] if b.get("issue")]
    assert len(issues) == len(set(issues))


def test_the_curve_and_estimate_use_program_counts_and_say_what_they_are():
    ledger = _ledger(
        _blocker(1),
        _blocker(2, new_class=False),
        _blocker(3, estate="cics-genapp", after_round=2, new_class=False),
    )
    text = pb.render(ledger, REGISTRY, BURNED, {"zecs": 4, "cics-genapp": 6})
    assert "| 1 | zecs | 4 | 2 | 0.50 | 2 | 1 | 1 | 0 |" in text
    assert "| 2 | cics-genapp | 6 | 1 | 0.17 | 3 | 0 | 1 | 1 |" in text
    assert "0.30 pooled (range 0.17 to 0.50)" in text
    assert "no variance model" in text


def test_an_estimate_needs_two_estates_with_a_program_count():
    text = pb.render(_ledger(_blocker(1)), REGISTRY, BURNED, {"zecs": 4})
    assert "no estimate" in text


def test_the_real_estates_have_program_counts():
    ledger, registry = pb.load()
    burned = pb.burned_names()
    sizes = pb.estate_sizes([e["id"] for e in registry["estates"] if e["id"] in burned])
    assert set(sizes) == {e["id"] for e in registry["estates"] if e["id"] in burned}
    assert all(n > 0 for n in sizes.values())
