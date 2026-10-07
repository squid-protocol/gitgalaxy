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
