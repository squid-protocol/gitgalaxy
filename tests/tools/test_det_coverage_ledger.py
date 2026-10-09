"""det_coverage_ledger: the sweep's coverage line -> ledger numbers, and the ratchet CI applies (missing / disagreeing /
stale entries). Fingerprints are stubbed; no sweep, git or corpus needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_coverage_ledger as dcl

LINE = "proven on 8 scenarios, covering 4/4 paragraphs and 2/2 branches"
FP = {"case": "a", "corpus": "b", "harness": "c", "oracle": "d"}
CASE = "cbsa-abndproc"  # a case that exists in the tree


def entry(**over):
    return {"scenarios": 8, "paragraphs": {"covered": 4, "live": 4}, "branches": {"covered": 2, "total": 2},
            "inputs": dict(FP), **over}  # fmt: skip


def test_parse_line():
    assert dcl.parse_line(LINE) == {"scenarios": 8, "paragraphs": {"covered": 4, "live": 4},
                                    "branches": {"covered": 2, "total": 2}}  # fmt: skip
    assert dcl.parse_line("not proven") is None
    assert dcl.parse_line("") is None


def test_check(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    det = {CASE: {"proved": True, "coverage": LINE}}
    assert dcl.check(det, {CASE: entry()}) == ([], [])
    problems, _ = dcl.check(det, {})
    assert "no entry" in problems[0]
    problems, _ = dcl.check(det, {CASE: entry(branches={"covered": 1, "total": 2})})
    assert "coverage moved" in problems[0]
    problems, _ = dcl.check(det, {CASE: entry(inputs={**FP, "case": "x"})})
    assert "stale (case changed)" in problems[0]
    problems, warnings = dcl.check(det, {CASE: entry(inputs={**FP, "harness": "x"})})
    assert not problems and "harness" in warnings[0]
    problems, _ = dcl.check(det, {CASE: entry(), "no-such-case": entry()})
    assert "no such case" in problems[0]
    assert dcl.check({CASE: {"proved": False, "coverage": ""}}, {}) == ([], [])


def test_build_and_fresh(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    det = {CASE: {"proved": True, "coverage": LINE}, "cbsa-updcust": {"proved": False, "coverage": LINE}}
    built = dcl.build(det, {})
    assert set(built) == {CASE} and built[CASE]["inputs"] == FP
    assert dcl.fresh_coverage(CASE, built) == (4, 4, 2, 2)
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "oracle": "z"})
    assert dcl.fresh_coverage(CASE, built) is None


def test_update_rewrites_stale_fingerprints(monkeypatch):
    """A harness-stale entry whose numbers the sweep reproduces is refreshed (#4270): update never keeps old fingerprints."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "new"})
    old = {CASE: entry(inputs={**FP, "harness": "old"})}
    assert dcl.stale(old[CASE], dcl.fingerprints(CASE)) == ["harness"]
    built = dcl.build({CASE: {"proved": True, "coverage": LINE}}, old)
    assert built[CASE]["inputs"]["harness"] == "new" and dcl.stale(built[CASE], dcl.fingerprints(CASE)) == []
    assert dcl.fresh_coverage(CASE, built) == (4, 4, 2, 2)


def test_update_drops_a_case_the_sweep_did_not_prove_and_keeps_one_it_did_not_run(monkeypatch):
    """#4758: an entry means the last sweep of its case proved it (the evidence report reads a Db2 case's verdict from
    it); a case the sweep skipped (a push refresh skips Db2) keeps its entry."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    old = {CASE: entry(), "cbsa-updcust": entry()}
    built = dcl.build({CASE: {"proved": False, "coverage": ""}}, old)
    assert set(built) == {"cbsa-updcust"}
    assert dcl.build({}, old) == old


def test_ledger_is_committed():
    """The ledger must be in git (a `*.json` ignore rule once kept it out of PR #4606)."""
    assert dcl._tracked(dcl.LEDGER)


def test_missing_ledger_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    monkeypatch.setattr(dcl, "LEDGER", tmp_path / "nope.json")
    problems, _ = dcl.check({}, {})
    assert "not a committed file" in problems[0]


def test_last_coverage_keeps_a_scheduled_stale_entry_and_flags_a_blocking_one(monkeypatch):
    """#4730: harness / oracle staleness leaves the last measurement readable; case / corpus makes it unknown."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    e = entry(measured_at="abc123")
    assert dcl.last_coverage(CASE, {CASE: e}) == {"coverage": (4, 4, 2, 2), "stale_inputs": [], "blocking": False,
                                                  "measured_at": "abc123"}  # fmt: skip
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "z", "oracle": "z"})
    got = dcl.last_coverage(CASE, {CASE: e})
    assert got["stale_inputs"] == ["harness", "oracle"] and not got["blocking"] and got["coverage"] == (4, 4, 2, 2)
    assert dcl.fresh_coverage(CASE, {CASE: e}) is None  # still not "current"
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "z", "case": "z"})
    assert dcl.last_coverage(CASE, {CASE: e})["blocking"] is True
    assert dcl.last_coverage(CASE, {}) is None
    assert dcl.last_coverage(CASE, {CASE: entry()})["measured_at"] is None  # an entry from before measured_at


def test_update_records_the_commit_measured_at(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    monkeypatch.setattr(dcl, "_head", lambda: "feedface")
    built = dcl.build({CASE: {"proved": True, "coverage": LINE}}, {})
    assert built[CASE]["measured_at"] == "feedface"
