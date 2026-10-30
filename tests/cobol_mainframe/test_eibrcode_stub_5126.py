"""#5126 (register X64), slice 1 -- the stub half of EIBRCODE: a scenario's planned file control condition may state the
6 bytes of EIBRCODE (`rcode`, 12 hex digits; VSAM / BDAM return codes ride in it for ILLOGIC and IOERR, so they are
environment facts the scenario states, not a table copied from IBM). The planner writes them as faults.cfg's sixth column,
the stub driver calls GGCRCOD right after a file command's RESP fields in a program that reads EIBRCODE, and a command or a
condition that states nothing leaves the field as it was."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_faults as cf  # noqa: E402

FORMS = [
    "READ {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READ {f}(WS-FILE) INTO(REC) RIDFLD(KEY) UPDATE RESP(R)",
    "READNEXT {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READPREV {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "STARTBR {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "ENDBR {f}('KSDS') RESP(R)",
    "WRITE {f}('KSDS') FROM(REC) RIDFLD(KEY) RESP(R)",
    "REWRITE {f}('KSDS') FROM(REC) RESP(R)",
    "DELETE {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "UNLOCK {f}('KSDS') RESP(R)",
]
CALL = "CALL 'GGCRCOD' USING GG-CICS EIBRCODE"


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("spelling", ["FILE", "DATASET"])
def test_a_reader_calls_ggcrcod_right_after_the_eib_resp_fields(form, spelling):
    text = form.format(f=spelling)
    st = ec.translate_command(text, eibrcode=True)
    assert st.count(CALL) == 1
    # right after EIBRESP2 is set: before a condition's GO TO, which would skip it
    assert st[st.index("MOVE GG-RESP2 TO EIBRESP2") + 1] == CALL
    # nothing else changes: the command's own statements are the non-reader's, plus the one call
    assert [x for x in st if x != CALL] == ec.translate_command(text)


@pytest.mark.parametrize("form", FORMS)
def test_a_non_reader_keeps_its_text(form):
    text = form.format(f="FILE")
    assert ec.translate_command(text) == ec.translate_command(text, eibrcode=False)
    assert CALL not in ec.translate_command(text)


@pytest.mark.parametrize("text", ["ASSIGN APPLID(A)", "RETURN", "GETMAIN SET(P) LENGTH(10)", "SYNCPOINT"])
def test_no_other_command_calls_it(text):
    try:
        st = ec.translate_command(text, eibrcode=True)
    except ec.Unsupported:
        return
    assert CALL not in st


@pytest.mark.parametrize(
    ("line", "reads"),
    [
        ("           MOVE EIBRCODE TO FE-RCODE.", True),
        ("           MOVE EIBRCODE(1:1) TO C.", True),
        ("           MOVE 1 TO EIBRCODE-NICE.", False),
        ("           DISPLAY 'EIBRCODE: '.", False),
        ("      *    MOVE EIBRCODE TO X.", False),
    ],
)
def test_the_program_scan_reads_whole_words_outside_literals_and_comments(line, reads):
    assert ec.reads_eibrcode(["       PROCEDURE DIVISION.", line]) is reads


def _sc(*faults):
    return {"name": "s", "faults": list(faults)}


def test_the_planner_writes_a_stated_rcode_as_the_sixth_column():
    f = {"cmd": "READ", "file": "ZC01FILE", "resp": "IOERR", "rcode": "80a0000000ff"}
    (line,) = cf.fault_lines(_sc(f))
    assert line.split() == ["READ", "ZC01FILE", "1", "17", "120", "80A0000000FF"]


def test_a_fault_with_no_rcode_keeps_its_five_columns():
    (line,) = cf.fault_lines(_sc({"cmd": "READ", "file": "ZC01FILE", "resp": "IOERR"}))
    assert len(line.split()) == 5


@pytest.mark.parametrize("bad", ["", "80", "80A0000000F", "80A0000000FFF", "80A000000XFF", 8, None])
def test_a_malformed_rcode_is_refused(bad):
    with pytest.raises(ec.Unsupported, match="12 hex digits"):
        cf.fault_lines(_sc({"cmd": "READ", "file": "F", "resp": "IOERR", "rcode": bad}))


def test_an_rcode_on_a_command_that_is_not_file_control_is_refused():
    with pytest.raises(ec.Unsupported):
        cf.fault_lines(_sc({"cmd": "LINK", "program": "P", "resp": "PGMIDERR", "rcode": "000000000000"}))


def test_the_stub_source_parses_the_column_and_copies_it_only_when_stated():
    src = (HERE.parents[0] / "equivalence" / "cics" / "ggcics_faults.c").read_text(encoding="utf-8")
    assert "int GGCRCOD(gg_cics *c, unsigned char *eibrcode)" in src
    assert "fault_rcode_set = 0;" in src  # cleared by every injected_at: a later command never inherits a stale value
    assert "if (fault_rcode_set && c->resp != NORMAL) memcpy(eibrcode, fault_rcode, 6);" in src
