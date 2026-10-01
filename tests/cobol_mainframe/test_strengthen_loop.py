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
