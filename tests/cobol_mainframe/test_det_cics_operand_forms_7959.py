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


_WEB = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. W7959.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOKEN PIC X(8).
       01  WS-MAP   PIC X(8).
       01  WS-BODY  PIC X(40).
       01  WS-LEN   PIC S9(8) COMP.
       01  WS-RESP  PIC S9(8) COMP.
       PROCEDURE DIVISION.
           EXEC CICS WEB CONVERSE SESSTOKEN({tok}) URIMAP({map})
               GET INTO(WS-BODY) TOLENGTH(WS-LEN)
               {extra}
               RESP(WS-RESP)
           END-EXEC
           EXEC CICS RETURN
           END-EXEC
"""


def _web(tmp_path, tok="WS-TOKEN", map_="WS-MAP", extra=""):
    src = tmp_path / "W7959.cbl"
    src.write_text(_WEB.format(tok=tok, map=map_, extra=extra))
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class W7959Service {\n    public void runTask(CicsTask task) {}\n}\n"
    return P.translate(src, [], stub, "com.x", {}, tmp_path / "proj")


def _holes(r):
    return [h for h in r.stats["holes"] if "not a data area" in h]


@pytest.mark.parametrize(("tok", "map_"), [("WS-TOKEN", "WS-MAP"), ("WS-TOKEN", "'ZMAP01'"), ("'TOKEN001'", "WS-MAP")])
def test_web_converse_data_values_take_a_constant(tmp_path, tok, map_):
    """IBM (CICS TS 6.x and 5.6, EXEC CICS WEB CONVERSE): SESSTOKEN(data-value), URIMAP(data-value). A data-value is a
    sender and may be a constant ("COBOL argument values"), so a literal there is valid source, not a source defect."""
    r = _web(tmp_path, tok, map_)
    assert not _holes(r) and "webConverse(" in r.java
    for lit in (tok, map_):
        if lit.startswith("'"):
            assert f'"{lit.strip(chr(39))}"' in r.java


def test_web_converse_data_areas_still_need_a_data_name(tmp_path):
    """MEDIATYPE is a data-area in IBM's WEB CONVERSE syntax: a literal there is still refused by name."""
    r = _web(tmp_path, extra="MEDIATYPE('text/plain')")
    assert _holes(r)
