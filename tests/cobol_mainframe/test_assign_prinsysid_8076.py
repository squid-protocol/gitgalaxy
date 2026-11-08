"""#8076, IBM CICS TS 6.x EXEC CICS ASSIGN PRINSYSID: the other system of an MRO / LU6.1 / APPC principal facility; any
other principal facility, or none, is INVREQ RESP2 5. The region has no such session (register X19), so the stub's
GGCASGN answers INVREQ RESP2 5 and the command writes no data area, whatever the response form and whatever else the
same command asks for. This pins the harness lowering of the whole input class and the stub's answer; the det port's
side is pinned in test_det_translate.py."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402

FORMS = ("", "RESP(R)", "RESP(R) RESP2(R2)", "NOHANDLE")
CHECK = ["MOVE 'PRINSYSI' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS"]


@pytest.mark.parametrize("form", FORMS)
def test_prinsysid_is_a_stub_check_and_writes_no_data_area(form):
    got = ec.translate_command(f"ASSIGN PRINSYSID(WS-SYS) {form}".strip())
    assert got[:2] == CHECK, got
    assert not any("WS-SYS" in ln for ln in got), got  # never moved to the target
    assert "    MOVE 0 TO GG-RESP GG-RESP2" in got  # the guarded block is inert: the INVREQ stays


@pytest.mark.parametrize("other", ("USERID(WS-USER)", "FACILITY(WS-FAC)", "ABCODE(WS-AB)", "STARTCODE(WS-SC)"))
def test_prinsysid_beside_another_option_stores_neither(other):
    got = ec.translate_command(f"ASSIGN PRINSYSID(WS-SYS) {other} RESP(R)")
    assert got[:2] == CHECK, got
    guard = got.index("IF GG-RESP = 0")
    assert any(ln.strip().startswith("MOVE GG-NAME1(1:") for ln in got[guard:]), got  # the other one only if no INVREQ
    assert not any("WS-SYS" in ln for ln in got), got


def test_a_terminal_option_alone_still_checks_the_terminal():
    assert ec.translate_command("ASSIGN USERID(WS-USER) RESP(R)")[0] != CHECK[0]
    assert ec.translate_command("ASSIGN FACILITY(WS-FAC) RESP(R)")[0] == "MOVE 'TERMCHK' TO GG-NAME2"


def test_prinsysid_is_not_refused_any_more():
    ec.translate_command("ASSIGN PRINSYSID(WS-SYS)")  # was Unsupported until #8076


def test_the_stub_answers_prinsysid_invreq_resp2_5():
    src = read_source(HERE.parents[0] / "equivalence" / "cics" / "ggcics_conditions.c").text
    block = src.split('strcmp(want, "PRINSYSI") == 0', 1)[1].split("}", 1)[0]
    assert "c->resp = INVREQ" in block and "c->resp2 = 5" in block
