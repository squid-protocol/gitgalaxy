"""#5126 (register X64): EIBCPOSN, EIBREQID, EIBRSRCE, EIBERR and EIBERRCD are refused by name, not modelled: no burned
program reads them, so a value copied from IBM would be a claim no proof runs. This pins the current state: each is a
named `fact:` gap in proof_blockers, no burned estate's COBOL reads it, and the stub assigns none of them -- except
EIBREQID, which POST writes when the program gave no REQID (IBM: CICS generates one; X63). Burned estates only."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
sys.path.insert(0, str(HERE))
import equivalence_cics as ec  # noqa: E402
import proof_blockers as pb  # noqa: E402
import test_eib_fn_rcode_5126 as guard  # noqa: E402

FIELDS = ("EIBCPOSN", "EIBREQID", "EIBRSRCE", "EIBERR", "EIBERRCD")

# one command of each family that could plausibly touch a terminal / request-id field
COMMANDS = [
    "RECEIVE INTO(REC) LENGTH(LEN) RESP(R)",
    "SEND MAP('M') MAPSET('S') FROM(REC) RESP(R)",
    "SEND TEXT FROM(REC) LENGTH(LEN) RESP(R)",
    "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "ASSIGN USERID(WS-U) RESP(R)",
    "START TRANSID('T001') INTERVAL(10) REQID('RQ') RESP(R)",
    "POST INTERVAL(10) REQID('RQ') RESP(R)",
    "POST INTERVAL(10) RESP(R)",
    "RETURN TRANSID('T001')",
]


def test_each_field_is_a_named_fact_gap_neither_runtime_states():
    assert set(FIELDS) <= pb.EIB_FIELDS
    assert not set(FIELDS) & pb.STATED_EIB
    assert not set(FIELDS) & pb.CASE_STATED_EIB


@pytest.mark.parametrize("field", FIELDS)
def test_a_program_reading_the_field_lists_it_as_a_fact_gap(field):
    src = f"       MOVE {field} TO WS-X.\n       MOVE 'X{field}: ' TO WS-Y.\n       MOVE {field}-NICE TO WS-Z.\n"
    assert set(pb.facts_needed(src)["eib"]) == {field}


def test_no_burned_program_reads_these_fields():
    assert not {p: n & set(FIELDS) for p, n in guard._readers().items() if n & set(FIELDS)}, (
        "a burned program reads an EIB field X64 refuses: model it per IBM, state it in the harness, update X64"
    )


@pytest.mark.parametrize("text", COMMANDS)
def test_the_stub_assigns_only_the_reqid_post_generates(text):
    try:
        out = " ".join(ec.translate_command(text))
    except ec.Unsupported:
        pytest.skip("refused whole by the stub")
    for field in FIELDS:
        wanted = field == "EIBREQID" and text.startswith("POST") and "REQID" not in text
        assert (f"TO {field}" in out) == wanted, (text, field)
