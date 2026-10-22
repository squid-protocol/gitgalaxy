"""#5561: CardDemo CBSTM03B's equivalence case drives every request type of every file it owns: OPEN, READ (sequential
or keyed, as the file is accessed) and CLOSE for TRNXFILE, XREFFILE, CUSTFILE and ACCTFILE, plus the end of file, a
missing record and the file-state errors. Pins the case shape, so a dropped request type fails here, not silently."""

import json
from pathlib import Path

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"
CASE = EQUIVALENCE / "carddemo-cbstm03b"

# LK-M03B-AREA: DD X(8), OPER X(1), RC X(2), KEY X(25), KEY-LN S9(4); FLDT X(1000) is the output.
SEQUENTIAL = ("TRNXFILE", "XREFFILE")
KEYED = ("CUSTFILE", "ACCTFILE")


def _case():
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def _requests(case):
    """(name, DD, operation) for every call, read off the request block's fixed columns."""
    return [(c["name"], c["args"][0][:8], c["args"][0][8]) for c in case["calls"]]


def test_every_file_is_opened_read_and_closed():
    case = _case()
    assert set(case["datasets"]) == set(SEQUENTIAL + KEYED)
    ops = {(dd, op) for _, dd, op in _requests(case)}
    for dd in SEQUENTIAL:
        assert {(dd, "O"), (dd, "R"), (dd, "C")} <= ops, dd
    for dd in KEYED:
        assert {(dd, "O"), (dd, "K"), (dd, "C")} <= ops, dd


def test_request_blocks_are_one_fixed_width():
    case = _case()
    assert {len(c["args"]) for c in case["calls"]} == {1}
    assert len({len(c["args"][0]) for c in case["calls"]}) == 1
    assert case["using"][0]["size"] == 1040


def test_end_of_file_missing_record_and_file_state_errors_are_calls_of_their_own():
    names = {c["name"] for c in _case()["calls"]}
    assert {"trnx-read-eof", "trnx-read-after-eof"} <= names  # status 10, then 46
    assert {"cust-read-missing", "acct-read-missing"} <= names  # status 23
    assert {"trnx-read-unopened", "cust-read-unopened"} <= names  # status 47
    assert "trnx-open-again" in names  # status 41
    assert "trnx-close-again" in names  # status 42
    assert "unknown-dd" in names  # WHEN OTHER


def test_sequential_files_read_until_the_end_of_file():
    case = _case()
    reads = [n for n, dd, op in _requests(case) if dd == "TRNXFILE" and op == "R" and n.startswith("trnx-read-")]
    assert len([n for n in reads if n[len("trnx-read-") :].isdigit()]) == 3
    lines = (CASE / "trnx.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # the end of file is exactly three READs away


def test_every_call_says_what_it_expects():
    assert all(c.get("why") for c in _case()["calls"])


def test_det_sweep_entry_covers_every_call_paragraph_and_branch():
    entry = json.loads((EQUIVALENCE / "det_sweep_coverage" / "carddemo-cbstm03b.json").read_text(encoding="utf-8"))
    assert entry["scenarios"] >= len(_case()["calls"])
    assert entry["paragraphs"]["covered"] == entry["paragraphs"]["live"] > 0
    assert entry["branches"]["covered"] == entry["branches"]["total"] > 0
