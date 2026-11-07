"""#7959: a data-area operand of an EXEC CICS command must be a COBOL data name (IBM: a literal, a figurative constant
or LENGTH OF is a data-value). Real `P.translate`, one authored program per operand form."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402

_SRC = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. T7959.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05 WS-A PIC X(10).
           05 WS-B PIC X(2).
       01  WS-TAB.
           05 WS-E PIC X(4) OCCURS 4.
       PROCEDURE DIVISION.
           EXEC CICS WRITEQ TS QUEUE('Q1')
               FROM({frm})
               LENGTH(10)
           END-EXEC
           EXEC CICS RETURN
           END-EXEC
"""


def _refusal(tmp_path, frm):
    src = tmp_path / "T7959.cbl"
    src.write_text(_SRC.format(frm=frm))
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T7959Service {\n    public void runTask(CicsTask task) {}\n}\n"
    r = P.translate(src, [], stub, "com.x", {}, tmp_path / "proj")
    return str(r)


@pytest.mark.parametrize("frm", ["REC", "WS-A", "REC(1:4)", "WS-E(2)"])
def test_a_data_name_form_is_a_data_area(tmp_path, frm):
    assert "not a data area" not in (_refusal(tmp_path, frm) or "")


@pytest.mark.parametrize("frm", ["'X'", "10", "SPACES", "LENGTH OF REC"])
def test_a_data_value_form_is_a_named_source_defect(tmp_path, frm):
    msg = _refusal(tmp_path, frm)
    assert msg is not None and "not a data area" in msg and "source defect, #7959" in msg
