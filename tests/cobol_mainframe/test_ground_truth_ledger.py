"""
The mainframe ground-truth ledger (tests/tools/ground_truth_ledger.py).

The gate's rules run on synthetic measurements, so they never need the corpora.
The committed ledger is checked for shape here too; the real measurement against
the pinned corpora runs in .github/workflows/mainframe-ground-truth.yml (and
locally, after `mainframe_corpus.py fetch`).
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ground_truth_ledger as gl  # noqa: E402

BOARD = {"dead": {"truth": "llm_verified", "engine": {"tp": 1, "got": 2, "truth": 1}, "forge": None}}
FP = "engine | dead | P.cbl | X-PARA | fp"
FN = "engine | dead | P.cbl | Y-PARA | fn"


def _ledger(entries: dict, causes=None) -> dict:
    return {
        "causes": {"c": {"kind": "defect", "issue": 1, "summary": "s"}} if causes is None else causes,
        "corpora": {"k": {"scoreboard": copy.deepcopy(BOARD), "mismatches": entries}},
    }


def _problems(ledger, entries, board=BOARD, pending=()):
    problems, _md = gl.check(ledger, {"k": (board, set(entries))}, list(pending))
    return problems


def test_clean_ledger_passes():
    assert _problems(_ledger({FP: "c"}), {FP}) == []


def test_new_mismatch_fails():
    (p,) = _problems(_ledger({FP: "c"}), {FP, FN})
    assert "NEW mismatch" in p and FN in p


def test_fixed_mismatch_fails_until_ratcheted():
    (p,) = _problems(_ledger({FP: "c", FN: "c"}), {FP})
    assert "no longer reproduces" in p and FN in p


def test_untriaged_and_unknown_causes_fail():
    problems = _problems(_ledger({FP: gl.UNTRIAGED, FN: "nope"}), {FP, FN})
    assert any("UNTRIAGED" in p for p in problems)
    assert any("unknown cause 'nope'" in p for p in problems)


def test_cause_needs_issue_kind_and_a_user():
    causes = {
        "c": {"kind": "defect", "issue": 1},
        "no_issue": {"kind": "defect"},
        "bad_kind": {"kind": "meh", "issue": 2},
    }
    problems = _problems(_ledger({FP: "c", FN: "no_issue"}, causes), {FP, FN})
    assert any("'no_issue' has no owning issue" in p for p in problems)
    assert any("'bad_kind' has kind 'meh'" in p for p in problems)
    assert any("'bad_kind' is used by no mismatch" in p for p in problems)


def test_stale_scoreboard_fails():
    board = copy.deepcopy(BOARD)
    board["dead"]["engine"]["got"] = 3
    (p,) = _problems(_ledger({FP: "c"}), {FP}, board=board)
    assert "scoreboard differs" in p


def test_pending_corpora_are_reported_not_gated():
    problems, md = gl.check(_ledger({FP: "c"}), {"k": (BOARD, {FP})}, ["carddemo"])
    assert problems == []
    assert "Pending (no answer key yet, not gated): carddemo" in md


def test_report_counts_defects_apart_from_deliberate():
    causes = {"c": {"kind": "defect", "issue": 1}, "d": {"kind": "deliberate", "issue": 2}}
    _problems_, md = gl.check(_ledger({FP: "c", FN: "d"}, causes), {"k": (BOARD, {FP, FN})}, [])
    assert "1 of 2 mismatches are open defects." in md


def test_update_keeps_causes_adds_untriaged_and_drops_fixed():
    ledger = _ledger({FP: "c"}, {"c": {"kind": "defect", "issue": 1}, "gone": {"kind": "defect", "issue": 2}})
    ledger["corpora"]["k"]["mismatches"]["old | x | P | V | fp"] = "gone"
    counts = gl.update(ledger, {"k": (BOARD, {FP, FN})})
    assert counts == {"added": 1, "removed": 1}
    assert ledger["corpora"]["k"]["mismatches"] == {FN: gl.UNTRIAGED, FP: "c"}
    assert set(ledger["causes"]) == {"c"}  # 'gone' lost its last entry


def test_assign_globs_over_corpus_and_entry():
    ledger = _ledger({FP: gl.UNTRIAGED, FN: gl.UNTRIAGED}, {})
    n = gl.assign(ledger, "new", ["k :: engine | dead | * | fp"], issue=9, summary="s", kind="defect")
    assert n == 1
    assert ledger["corpora"]["k"]["mismatches"] == {FP: "new", FN: gl.UNTRIAGED}
    assert ledger["causes"]["new"] == {"issue": 9, "summary": "s", "kind": "defect"}


def test_assign_refuses_an_unknown_cause_without_metadata():
    with pytest.raises(SystemExit):
        gl.assign(_ledger({FP: gl.UNTRIAGED}, {}), "undeclared", ["*"])


def test_truth_tier_is_the_weakest_verification_behind_a_field():
    key = {
        "programs": {
            "P.cbl": {"verification": {"status": "validated", "tier": "cross_verified"}, "records_validated": False},
            "Q.cbl": {"verification": {"status": "validated", "tier": "human_signed"}},
        },
        "bms_maps": {"M.bms": {"fields_validated": True}},
    }
    assert gl.truth_tier(key, "dead") == "cross_verified"
    assert gl.truth_tier(key, "record fields") == "draft"
    assert gl.truth_tier(key, "BMS screen fields") == "llm_verified"  # a bare flag is the one-model floor
    assert gl.truth_tier(key, "CSD resources") == "draft"  # no entries is not a sign-off
    key["programs"]["Q.cbl"]["verification"]["status"] = "draft"
    assert gl.truth_tier(key, "dead") == "draft"


def test_a_flag_may_carry_its_own_tier_below_the_entry():
    """#3575: program records signed by a SAMPLED census report sample_verified, while
    the program block (which backs units, calls, ...) stays cross_verified."""
    ok = {"status": "validated", "tier": "cross_verified"}
    key = {"programs": {p: {"verification": dict(ok), "records_validated": True} for p in ("P.cbl", "Q.cbl")}}
    assert gl.truth_tier(key, "record fields") == "cross_verified"
    for entry in key["programs"].values():
        entry["records_validated_tier"] = "sample_verified"
    assert gl.truth_tier(key, "record fields") == "sample_verified"
    assert gl.truth_tier(key, "units") == "cross_verified"


def test_ledger_tiers_mirror_the_key_tool():
    import cobol_answer_key as ak

    assert gl.TIERS == ak.TIERS


def test_history_appends_only_when_a_number_moves(tmp_path):
    path = tmp_path / "h.jsonl"
    rows = gl.history_rows({"k": (BOARD, set())})
    assert rows == [
        {"corpus": "k", "field": "dead", "side": "engine", "truth_tier": "llm_verified", "tp": 1, "got": 2, "truth": 1}
    ]
    assert gl.append_history(rows, path) is True
    assert gl.append_history(rows, path) is False
    moved = [{**rows[0], "tp": 2}]
    assert gl.append_history(moved, path) is True
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_committed_ledger_is_canonical_and_triaged():
    raw = gl.LEDGER.read_text(encoding="utf-8")
    ledger = json.loads(raw)
    assert raw == json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    for name, rec in ledger["corpora"].items():
        for e, cause in rec["mismatches"].items():
            assert cause != gl.UNTRIAGED, f"{name} :: {e}"
            assert cause in ledger["causes"], f"{name} :: {e} -> {cause}"
            assert e.rsplit(" | ", 1)[1] in ("fp", "fn")
    for cause, meta in ledger["causes"].items():
        assert meta.get("kind") in gl.KINDS and meta.get("issue"), cause


def test_committed_ledger_covers_every_keyed_corpus():
    import mainframe_corpus as mc

    ledger = json.loads(gl.LEDGER.read_text(encoding="utf-8"))
    assert set(ledger["corpora"]) == {c["name"] for c in gl.keyed(mc.load_manifest())}
