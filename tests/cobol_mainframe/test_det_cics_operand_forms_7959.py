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


# #8058: the rest of the class. Each (command, option) IBM declares a data-value in its CICS TS 6.x syntax diagram
# (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-<command>) that det read through the data-area path.
_CMD = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. V8058.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOKEN PIC X(8).
       01  WS-DOC   PIC X(16).
       01  WS-HOST  PIC X(20).
       01  WS-URL   PIC X(40).
       01  WS-TEXT  PIC X(20).
       01  WS-USER  PIC X(8).
       01  WS-NAME  PIC X(8).
       01  WS-MEDIA PIC X(56).
       01  WS-ROUTE PIC X(2).
       01  WS-VAL   PIC X(20).
       01  WS-SCHN  PIC X(8).
       01  WS-LEN   PIC S9(8) COMP.
       01  WS-RESP  PIC S9(8) COMP.
       PROCEDURE DIVISION.
           EXEC CICS {cmd}
               RESP(WS-RESP)
           END-EXEC
           EXEC CICS RETURN
           END-EXEC
"""


def _cmd(tmp_path, cmd):
    src = tmp_path / "V8058.cbl"
    text = _CMD.format(cmd=cmd)
    assert all(len(ln) <= 72 for ln in text.splitlines()), "a source line runs past column 72"
    src.write_text(text)
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class V8058Service {\n    public void runTask(CicsTask task) {}\n}\n"
    return P.translate(src, [], stub, "com.x", {}, tmp_path / "proj")


# (the command with `{v}` at the data-value option, the data name that fills it, the Java call it lowers to)
_VALUES = {
    "WEB CLOSE SESSTOKEN": ("WEB CLOSE SESSTOKEN({v})", "WS-TOKEN", "task.webClose("),
    "WEB OPEN HOST": (
        "WEB OPEN HOST({v}) HOSTLENGTH(20)\n               SCHEME(WS-LEN) SESSTOKEN(WS-TOKEN)",
        "WS-HOST",
        "task.webOpenHost(",
    ),
    "WEB SEND DOCTOKEN": ("WEB SEND DOCTOKEN({v})", "WS-DOC", "task.webSendDocument("),
    "WEB SEND MEDIATYPE": (
        "WEB SEND FROM(WS-TEXT) FROMLENGTH(20)\n               MEDIATYPE({v})",
        "WS-MEDIA",
        "task.webSend(",
    ),
    "WEB PARSE URL URL": (
        "WEB PARSE URL({v}) URLLENGTH(40)\n               SCHEMENAME(WS-SCHN)",
        "WS-URL",
        "task.webParse(",
    ),
    "WEB WRITE HTTPHEADER SESSTOKEN": (
        "WEB WRITE HTTPHEADER('X-A') NAMELENGTH(3)\n               VALUE('B') VALUELENGTH(1) SESSTOKEN({v})",
        "WS-TOKEN",
        "task.webWriteHeader(",
    ),
    "WEB READ QUERYPARM": (
        "WEB READ QUERYPARM({v}) NAMELENGTH(8)\n               VALUE(WS-VAL) VALUELENGTH(WS-LEN)",
        "WS-NAME",
        "task.webReadParam(",
    ),
    "WRITE OPERATOR TEXT": ("WRITE OPERATOR TEXT({v})", "WS-TEXT", "task.writeOperator("),
    "WRITE OPERATOR ROUTECODES": (
        "WRITE OPERATOR TEXT(WS-TEXT) ROUTECODES({v})\n               NUMROUTES(1)",
        "WS-ROUTE",
        "task.writeOperator(",
    ),
    "VERIFY PASSWORD USERID": ("VERIFY PASSWORD('SECRET01') USERID({v})", "WS-USER", "task.verifyPassword("),
}
_LITERAL = {"WRITE OPERATOR ROUTECODES": "X'0B'"}


@pytest.mark.parametrize("opt", sorted(_VALUES))
@pytest.mark.parametrize("form", ["name", "literal"])
def test_data_value_options_take_a_constant(tmp_path, opt, form):
    """IBM declares each option a data-value (a sender, which may be a constant): a literal translates, and a data name
    keeps reading the area's text as before (`Cobol.text(<field>, CS)`)."""
    cmd, name, call = _VALUES[opt]
    lit = _LITERAL.get(opt, "'ABCDEFGH'")
    r = _cmd(tmp_path, cmd.format(v=name if form == "name" else lit))
    assert not _holes(r), r.stats["holes"]
    assert call in r.java
    if form == "name":  # the data-area text path, unchanged
        assert "Cobol.text(f" in r.java and "_" + name.replace("-", "_") + "," in r.java
    if form == "literal" and lit.startswith("'"):
        assert '"ABCDEFGH"' in r.java


def test_a_figurative_constant_data_value_is_refused_by_name(tmp_path):
    """A figurative constant has no length of its own: refused by name as a translator gap, not as a source defect."""
    holes = _cmd(tmp_path, "WRITE OPERATOR TEXT(SPACES)").stats["holes"]
    assert not any("not a data area" in h for h in holes)
    assert any("figurative constant as a data-value" in h and "#8058" in h for h in holes)


@pytest.mark.parametrize(
    "cmd",
    [
        # IBM WEB READ FORMFIELD(data-area) (QUERYPARM beside it is a data-value)
        "WEB READ FORMFIELD('FIELD001') NAMELENGTH(8)\n               VALUE(WS-VAL) VALUELENGTH(WS-LEN)",
        # IBM DOCUMENT RETRIEVE DOCTOKEN(data-area)
        "DOCUMENT RETRIEVE\n               DOCTOKEN('ABCDEFGHABCDEFGH') INTO(WS-VAL)\n               MAXLENGTH(20) DATAONLY",
        # IBM WEB SEND STATUSTEXT(data-area)
        "WEB SEND FROM(WS-TEXT) FROMLENGTH(20)\n               STATUSCODE(200) STATUSTEXT('OK')",
        # IBM WEB PARSE URL HOST(data-area): written to
        "WEB PARSE URL(WS-URL) URLLENGTH(40) HOST('H')\n               HOSTLENGTH(WS-LEN)",
    ],
)
def test_data_area_options_still_refuse_a_constant(tmp_path, cmd):
    assert _holes(_cmd(tmp_path, cmd))
