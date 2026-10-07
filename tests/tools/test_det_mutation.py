"""det_mutation (#4628): the det-port mutation ledger, the reviewed survivors, and the L5 hook. Fingerprints are
stubbed; no proof, translator or corpus needed (the committed ledgers' own check needs git only)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_mutation as dm

CASE = "cbsa-abndproc"  # a case that exists in the tree
FP = {"generator": "g", "case": "a", "corpus": "b", "harness": "c", "oracle": "d"}
S1 = {"id": "aaaa000001", "op": "CON", "file": "service/X.java", "line": 10, "before": "x = 0;", "after": "x = 1;"}
S2 = {"id": "aaaa000002", "op": "DEL", "file": "service/X.java", "line": 12, "before": "f();", "after": "/* f(); */"}


def entry(**over):
    return {"program": "ABNDPROC", "seed": 0, "mutants": 400, "chosen": 6, "mode": "fast",
            "counts": {"killed": 3, "timeout": 0, "survived": 2, "stillborn": 1, "error": 0, "pending": 0},
            "killed": ["k1", "k2", "k3"], "stillborn": ["s1"], "survived": [S1, S2],
            "inputs": {"port": "p", **FP}, **over}  # fmt: skip


def claim(s, verdict="equivalent", **over):
    return {**{k: s[k] for k in ("id", "op", "line", "before", "after")}, "verdict": verdict, "reason": "why", **over}


def test_summary_accounts_survivors():
    s = dm.summary(CASE, entry(), {})
    assert (s["killed"], s["survived"], s["accounted"], s["unaccounted"], s["l5"]) == (3, 2, 0, 2, False)
    assert s["score"] == 0.6
    s = dm.summary(CASE, entry(), {CASE: [claim(S1), claim(S2, "unreachable")]})
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (2, 0, True)
    # a claim on a different Java line (the port moved) does not account for the survivor
    s = dm.summary(CASE, entry(), {CASE: [claim(S1), claim(S2, after="g();")]})
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (1, 1, False)


def test_gap_verdicts_are_triaged_not_accounted():
    survivors = {CASE: [claim(S1), claim(S2, "harness-gap")]}
    s = dm.summary(CASE, entry(), survivors)
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (1, 1, False)
    # a gap entry whose mutant is killed now is a closed gap, not a wrong claim: a warning to drop it
    gap = {**claim(S1, "case-gap"), "id": "k1"}
    assert dm.refuted(CASE, entry(), {CASE: [gap]}) == []
    problems, warnings = dm.check({CASE: entry()}, {CASE: [gap]}, tracked=False)
    assert not problems and "killed now" in warnings[0]


def test_a_killed_stated_mutant_fails():
    killed = {**claim(S1), "id": "k2"}
    survivors = {CASE: [killed, claim(S2)]}
    assert dm.refuted(CASE, entry(), survivors) == ["k2"]
    assert dm.summary(CASE, entry(), survivors)["l5"] is False
    problems, _ = dm.check({CASE: entry()}, survivors, tracked=False)
    assert any("the run killed it" in p for p in problems)


def test_check_form_and_claims():
    assert dm.check({CASE: entry()}, {CASE: [claim(S1), claim(S2)]}, tracked=False) == ([], [])
    problems, _ = dm.check({}, {CASE: [claim(S1, verdict="dunno")]}, tracked=False)
    assert "unknown verdict" in problems[0]
    problems, _ = dm.check({}, {CASE: [claim(S1, reason="")]}, tracked=False)
    assert "lacks reason" in problems[0]
    problems, _ = dm.check({}, {CASE: [claim(S1), claim(S1)]}, tracked=False)
    assert "listed twice" in problems[0]
    problems, _ = dm.check({"no-such-case": entry()}, {}, tracked=False)
    assert "no such case" in problems[0]
    problems, warnings = dm.check({CASE: entry()}, {CASE: [{**claim(S1), "id": "zz"}]}, tracked=False)
    assert not problems and "not judged" in warnings[0]


def test_status_is_none_when_stale(monkeypatch):
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: entry()})
    monkeypatch.setattr(dm, "load_survivors", lambda path=dm.SURVIVORS: {CASE: [claim(S1), claim(S2)]})
    monkeypatch.setattr(dm, "fingerprints", lambda case: dict(FP))
    s = dm.status(CASE, "ABNDPROC")
    assert s is not None and s["l5"] and s["killed"] == 3 and s["accounted"] == 2
    assert dm.status(CASE, "OTHER") is None
    assert dm.status("carddemo-signon") is None  # no entry
    monkeypatch.setattr(dm, "fingerprints", lambda case: {**FP, "generator": "moved"})
    assert dm.status(CASE) is None


def test_member_spans_and_scope():
    text = ("class X {\n"
            "    public int runBatch(List<Dd> dds) {\n        if (x) { y(); }\n        return 0;\n    }\n"
            "    public void runTask(CicsTask t) {\n        z();\n    }\n}\n")  # fmt: skip
    assert dm.member_spans(text, ("runBatch",)) == [(2, 5)]
    assert dm.member_spans(text, ("runTask",)) == [(6, 8)]


def test_the_ledgers_are_tracked():
    """`.gitignore` has `*.json`: both files need their `!path` exception, or a PR ships without its data."""
    assert dm._tracked(dm.LEDGER)
    assert dm._tracked(dm.SURVIVORS)


def test_the_committed_ledgers_agree():
    problems, _ = dm.check(tracked=False)
    assert problems == []
