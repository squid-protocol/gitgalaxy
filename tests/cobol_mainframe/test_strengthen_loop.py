"""#4049: the test-strengthening loop (tests/tools/strengthen.py). The pure parts: the model's answer parsed,
malformed proposals refused with the reason, a proposal turned into a case entry (the model's expected result is
never taken -- there is none), the prompt carrying the gaps and the oracle's limits, and the inputs a port fails."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import strengthen as st  # noqa: E402

CALL = {"name": "c", "kind": "call", "program": "P", "using": [{"name": "A", "size": 4}, {"name": "B", "size": 6}],
        "calls": [{"name": "one", "args": ["AB", "X"]}]}  # fmt: skip
CICS = {"name": "m", "kind": "cics", "program": "M",
        "scenarios": [{"name": "first", "aid": "DFHENTER", "commarea": {"CA-USER-TYPE": "U", "CA-CONTEXT": 0}}]}  # fmt: skip


def test_the_answer_is_one_json_array_of_proposals():
    text = 'Here:\n```json\n[{"name": "a", "args": ["x", "y"]}, "noise"]\n```\nthanks'
    assert st.parse(text) == [{"name": "a", "args": ["x", "y"]}]
    assert st.parse("no json here") == []


def test_malformed_proposals_are_refused_with_the_reason():
    taken = {"one"}
    assert st.validate(CALL, {"name": "two", "args": ["ABCD", "XYZ"]}, taken) is None
    assert "not a new" in st.validate(CALL, {"name": "one", "args": ["A", "B"]}, taken)
    assert "args must be 2" in st.validate(CALL, {"name": "two", "args": ["A"]}, taken)
    assert "at most 4" in st.validate(CALL, {"name": "two", "args": ["ABCDE", "X"]}, taken)
    assert st.validate(CICS, {"name": "admin", "aid": "DFHPF3", "commarea": {"CA-USER-TYPE": "A"}}, set()) is None
    assert "not in the existing" in st.validate(CICS, {"name": "x", "commarea": {"CA-SECRET": "1"}}, set())
    assert "DFH AID" in st.validate(CICS, {"name": "x", "aid": "ENTER"}, set())


def test_an_entry_keeps_the_input_and_never_an_expected_result():
    p = {"name": "two", "args": ["A", "B"], "expected": "Date is valid", "targets": ["A000-MAIN:128:WHEN@131"],
         "why": "reaches the first WHEN"}  # fmt: skip
    e = st.as_entry(CALL, p)
    assert set(e) == {"name", "args", "why"} and "expected" not in e
    assert e["why"].startswith("#4049 (proposed for A000-MAIN:128:WHEN@131)")


def test_the_prompt_carries_the_gaps_the_inputs_and_the_oracles_limits():
    src = [f"LINE {i}" for i in range(1, 200)]
    gaps = [{"unit": "A000-MAIN", "line": 128, "kind": "EVALUATE", "outcome": "WHEN@131"}]
    hints = [{"file": "S.java", "line": 9, "before": "a > 0", "after": "a >= 0"}]
    text = st.prompt(CALL, src, gaps, hints, ["- `x`: refused"], "CEEDAYS refuses month 13")
    assert "A000-MAIN:128:WHEN@131" in text and "  128 LINE 128" in text
    assert '"name": "one"' in text and "`a > 0` -> `a >= 0`" in text
    assert "CEEDAYS refuses month 13" in text and "`x`: refused" in text
    assert "Never an expected result" in text and "unreachable" in text


def test_the_inputs_a_port_fails_are_named():
    report = {"outputs": {"CALLS": {"diffs": [{"record": 1}]}}}
    assert st.failing_entries(CALL, report) == ["one"]
    cics = {"outputs": {"first": {"equal": 1, "records": 2, "diffs": [{}]}, "ok": {"equal": 1, "records": 1}}}
    assert st.failing_entries(CICS, cics) == ["first"]


# ---- batch cases: new records built from an existing one and its layout ----------------------------------------
BATCH = {"name": "b", "kind": "batch", "program": "B", "datasets": {}}
FIELDS = [{"name": "ACCT-ID", "offset": 0, "bytes": 4, "pic": "9(4)", "usage": None},
          {"name": "EXP-DATE", "offset": 4, "bytes": 10, "pic": "X(10)", "usage": None},
          {"name": "BAL", "offset": 14, "bytes": 3, "pic": "S9(5)", "usage": "COMP-3"}]  # fmt: skip
INPUTS = {"ACCT": {"fields": FIELDS, "records": [b"00012024-01-31\x00\x00\x0c", b"00022025-12-31\x00\x00\x0c"],
                   "spec": {"organization": "indexed", "keys": [{"offset": 0, "length": 4}]}}}  # fmt: skip


def test_a_new_record_is_an_existing_one_with_named_display_fields_changed():
    rec, bad = st.build_record(BATCH, INPUTS, {"dataset": "ACCT", "based_on": 2, "set": {"ACCT-ID": 7,
                                                                                         "EXP-DATE": "2025-01-31"}})  # fmt: skip
    assert bad is None and rec == b"00072025-01-31\x00\x00\x0c"  # BAL's bytes copied, untouched


def test_a_malformed_record_proposal_is_refused_with_the_reason():
    def why(p):
        return st.build_record(BATCH, INPUTS, p)[1]

    assert "not an input" in why({"dataset": "NOPE", "based_on": 1})
    assert "record number 1..2" in why({"dataset": "ACCT", "based_on": 3})
    assert "no field" in why({"dataset": "ACCT", "based_on": 1, "set": {"NAME": "X"}, "x": 1})
    assert "COMP-3" in why({"dataset": "ACCT", "based_on": 1, "set": {"BAL": 5}})  # keeps a text file text
    assert "already a record's" in why({"dataset": "ACCT", "based_on": 1, "set": {"EXP-DATE": "2026-01-01"}})


def test_a_value_with_more_decimals_than_its_picture_is_refused_not_rounded():
    fields = [{"name": "AMT", "offset": 0, "bytes": 5, "pic": "S9(3)V99", "usage": None}]
    inputs = {"T": {"fields": fields, "records": [b"0010{"], "spec": {}}}
    assert st.build_record(BATCH, inputs, {"dataset": "T", "based_on": 1, "set": {"AMT": "1.25"}})[1] is None
    assert "more decimals" in st.build_record(BATCH, inputs, {"dataset": "T", "based_on": 1, "set": {"AMT": 1.999}})[1]


# ---- #4049: survivor-driven rounds (--case-gaps) -------------------------------------------------------------
def test_the_case_gaps_are_the_survivors_the_committed_results_triaged_so(tmp_path):
    results = {"ports": [
        {"case": "c", "program": "P", "survivors": [{"id": "a1", "verdict": "case_gap"},
                                                     {"id": "b2", "verdict": "equivalent"}]},
        {"case": "crucible:x", "program": "Q", "survivors": [{"id": "c3", "verdict": "case_gap"}]},
        {"case": "crucible:x", "program": "R", "survivors": [{"id": "d4", "verdict": "case_gap"}]}]}  # fmt: skip
    f = tmp_path / "scores.json"
    f.write_text(st.json.dumps(results), encoding="utf-8")
    assert st.case_gaps(f, "c") == {"a1"}
    assert st.case_gaps(f, "crucible:x", "Q") == {"c3"}
    assert st.case_gaps(f, "nope") == set()


def test_a_cics_proposal_may_set_any_commarea_field_of_the_layout_and_plan_a_fault():
    names = {"CA-USER-TYPE", "CA-CONTEXT", "CA-LAST-MAP"}
    ok = {"name": "x", "aid": "DFHENTER", "commarea": {"CA-LAST-MAP": "M1"},
          "faults": [{"cmd": "XCTL", "program": "PROG1", "resp": "PGMIDERR", "resp2": 3}]}  # fmt: skip
    assert st.validate(CICS, ok, set(), names) is None
    assert "COMMAREA layout" in st.validate(CICS, {"name": "x", "commarea": {"CA-SECRET": "1"}}, set(), names)
    bad = {"name": "x", "faults": [{"cmd": "LINK", "program": "P", "resp": "PGMIDERR"}]}
    assert "fault" in st.validate(CICS, bad, set(), names)


def test_the_prompt_names_the_survivors_to_kill_by_id():
    src = [f"LINE {i}" for i in range(1, 50)]
    hints = [{"id": "abc123", "file": "S.java", "line": 9, "before": "a > 0", "after": "a >= 0"}]
    text = st.prompt(CALL, src, [], hints, [], "")
    assert "`abc123` S.java:9" in text and "targets" in text
