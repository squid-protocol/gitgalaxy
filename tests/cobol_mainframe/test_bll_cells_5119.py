"""#5119 (oracle_assumptions.md X56): OS/VS COBOL's BLL cells and SERVICE RELOAD, lowered onto the pointer lane (X47).

IBM's CICS/MVS 2.1.2 Application Programmer's Reference (SC33-0512-1) gives the OS/VS COBOL addressing ("Base locator
for linkage (BLL)", pp. 21-23) and its own conversion to VS COBOL II ("Converting to VS COBOL II", p. 29; Figure 3,
p. 26). det/bll.py applies that conversion to the program before either side reads it -- the cell list becomes
POINTERs in WORKING-STORAGE, SERVICE RELOAD record becomes SET ADDRESS OF record TO its cell, the long record's
`ADD 4096` goes, MOVE cell TO cell is SET cell TO cell -- so the det port and the GnuCOBOL oracle run one program on the
pointer lane. The pieces, the whole input class each:
- the lowering of IBM's own examples (Figure 3, the SERVICE RELOAD example, Figure 5, the MOVE example), unchanged for
  a program with no BLL evidence, and each idiom it cannot keep refused whole by name;
- the det translator: a BLL program translates with no hole; READ SET(cell) and ADDRESS TWA(cell) (X59: only EIB and COMMAREA are modelled) are still holes
  under their own commands' refusals;
- the oracle's translate(): the same lowered program, a refusal raised as Unsupported;
- end to end (EQUIVALENCE_E2E): GnuCOBOL and the det port, one proven case on a synthetic estate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import bll as B  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as S  # noqa: E402

TOOLS = Path(__file__).resolve().parents[1] / "tools"

# IBM's SERVICE RELOAD example (p. 24) with Figure 3's long record: FILE-REC is 5400 bytes, two cells (FRPTR, FRPTR1);
# TS-REC is the third cell. GETMAIN stands for the locate-mode READ (READ SET is #5042's), INITIMG '*'; the program
# writes the head and the tail (past 4096 bytes) of the record, aliases TS-REC to it and SENDs what both show.
PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(20) VALUE SPACES.
       01  WS-NUM                 PIC S9(8) COMP VALUE 0.
       LINKAGE SECTION.
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  FRPTR              PIC S9(8) COMP.
           02  FRPTR1             PIC S9(8) COMP.
           02  TSPTR              PIC S9(8) COMP.
       01  FILE-REC.
           02  FIELD1             PIC X(4000).
           02  FIELD2             PIC X(1000).
           02  FIELD3             PIC X(400).
       01  TS-REC.
           02  TFIELD             PIC X(10).
           02  FILLER             PIC X(390).
       PROCEDURE DIVISION.
           SERVICE RELOAD PARMLIST.
           EXEC CICS GETMAIN SET(FRPTR) FLENGTH(5400)
                INITIMG(WS-IMG) END-EXEC.
           ADD 4096, FRPTR
               GIVING FRPTR1.
           SERVICE RELOAD FILE-REC.
           MOVE 'TAIL-BYTES' TO FIELD3(1:10).
           MOVE 'HEAD' TO FIELD1(1:4).
           MOVE FRPTR TO TSPTR SERVICE RELOAD TS-REC.
           MOVE TFIELD TO WS-OUT(1:10).
           MOVE FIELD3(1:10) TO WS-OUT(11:10).
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(20) ERASE
                END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
SENT = "HEAD******TAIL-BYTES"  # hand-traced: TS-REC is FILE-REC's first bytes; FIELD3 starts at byte 5001


def _lines(tmp_path: Path, source: str) -> list:
    p = tmp_path / "BLLDEMO.cbl"
    p.write_text(source, encoding="ascii")
    return S.program_unit(S.program_lines(p, []))


def _lowered(tmp_path: Path, source: str = PROGRAM) -> list[str]:
    lines = _lines(tmp_path, source)
    return [ln.text.strip() for ln in B.lower(lines, lines[0].file) if ln.text.strip()]


def test_the_cells_become_pointers_and_service_reload_a_set_address_of(tmp_path):
    """IBM's conversion, statement by statement: the list leaves LINKAGE (its FILLER and FRPTR1, the long record's
    secondary cell, dropped), its cells are POINTERs in WORKING-STORAGE; SERVICE RELOAD of the list itself is nothing
    (CICS addresses it), of a record SET ADDRESS OF it TO its base cell; ADD 4096 goes; MOVE cell TO cell is SET."""
    got = _lowered(tmp_path)
    ws = got.index("WORKING-STORAGE SECTION.")
    assert got[ws + 1 : ws + 4] == ["01  PARMLIST.", "05  FRPTR USAGE POINTER.", "05  TSPTR USAGE POINTER."]
    link = got.index("LINKAGE SECTION.")
    assert got[link + 1] == "01  FILE-REC."  # (the list is gone from LINKAGE)
    assert not any("FRPTR1" in t for t in got)
    proc = got[got.index("PROCEDURE DIVISION.") + 1 :]
    assert proc[0] == "CONTINUE."
    assert proc[1] == "EXEC CICS GETMAIN SET(FRPTR) FLENGTH(5400)"  # (SET(cell) is SET(pointer) now)
    assert proc[3:6] == ["CONTINUE", ".", "SET ADDRESS OF FILE-REC TO FRPTR."]
    assert "SET TSPTR TO FRPTR SET ADDRESS OF TS-REC TO TSPTR." in proc


@pytest.mark.parametrize(
    "linkage, procedure, lowered",
    [
        # Figure 5 (p. 30): a BMS map in LINKAGE, GETMAIN into the cell (LENGTH, the halfword form)
        (
            "01  BLLCELLS.\n           02  FILLER PIC S9(8) COMP.\n           02  BLL-DATAA PIC S9(8) COMP.\n"
            "       01  DATA1 PIC X(1050).",
            "EXEC CICS GETMAIN LENGTH(1050)\n                SET(BLL-DATAA) INITIMG(FLDS) END-EXEC.\n"
            "           SERVICE RELOAD DATA1.",
            ["SET(BLL-DATAA) INITIMG(FLDS) END-EXEC.", "SET ADDRESS OF DATA1 TO BLL-DATAA."],
        ),
        # p. 24: "MOVE B-POINTER TO A-POINTER SERVICE RELOAD A-DATA." -- one cell per record, three records
        (
            "01  PARMLIST.\n           02  FILLER PIC S9(8) COMP.\n           02  A-POINTER PIC S9(8) COMP.\n"
            "           02  B-POINTER PIC S9(8) COMP.\n           02  C-POINTER PIC S9(8) COMP.\n"
            "       01  A-DATA PIC X(108).\n       01  B-DATA PIC X.\n       01  C-DATA PIC X.",
            "EXEC CICS GETMAIN SET(B-POINTER) FLENGTH(108)\n                INITIMG(FLDS) END-EXEC.\n"
            "           SERVICE RELOAD B-DATA.\n"
            "           MOVE B-POINTER TO A-POINTER SERVICE RELOAD A-DATA.",
            ["SET ADDRESS OF B-DATA TO B-POINTER.", "SET A-POINTER TO B-POINTER SET ADDRESS OF A-DATA TO A-POINTER."],
        ),
        # DFHCOMMAREA precedes the list (p. 21) and is no cell's; its SERVICE RELOAD is nothing
        (
            "01  DFHCOMMAREA PIC X(8).\n       01  PARMLIST.\n           02  FILLER PIC S9(8) COMP.\n"
            "           02  A-PTR PIC S9(8) COMP.\n       01  A-DATA PIC X(8).",
            "SERVICE RELOAD DFHCOMMAREA.\n           EXEC CICS GETMAIN SET(A-PTR) FLENGTH(8)\n"
            "                INITIMG(FLDS) END-EXEC SERVICE RELOAD A-DATA.",
            ["CONTINUE.", "INITIMG(FLDS) END-EXEC SET ADDRESS OF A-DATA TO A-PTR."],
        ),
    ],
)
def test_ibms_own_examples_lower_onto_the_pointer_lane(tmp_path, linkage, procedure, lowered):
    source = ("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. BLLDEMO.\n       DATA DIVISION.\n"
              "       WORKING-STORAGE SECTION.\n       01  FLDS PIC X VALUE LOW-VALUE.\n       LINKAGE SECTION.\n"
              f"       {linkage}\n       PROCEDURE DIVISION.\n           {procedure}\n"
              "           EXEC CICS RETURN END-EXEC.\n")  # fmt: skip
    got = _lowered(tmp_path, source)
    for t in lowered:
        assert t in got, (t, got)
    assert not any(t.startswith(("02  FILLER", "SERVICE")) for t in got)


def test_a_program_with_no_bll_evidence_is_left_as_it_is(tmp_path):
    """A LINKAGE list of fullwords no SET option names, and no SERVICE RELOAD: ordinary data (VS COBOL II), unchanged.
    SERVICE RELOAD in a program with no cell list is nothing (VS COBOL II ignores it, p. 24)."""
    plain = PROGRAM.replace("           SERVICE RELOAD PARMLIST.\n", "").replace(
        "SET(FRPTR) FLENGTH(5400)", "SET(ADDRESS OF FILE-REC) FLENGTH(5400)"
    )
    plain = plain[: plain.index("           ADD 4096")] + "           EXEC CICS RETURN END-EXEC.\n"
    lines = _lines(tmp_path, plain)
    assert B.lower(lines, lines[0].file) is lines
    vs2 = tmp_path / "v.cbl"
    vs2.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. V.\n       DATA DIVISION.\n"
                   "       LINKAGE SECTION.\n       01  DFHCOMMAREA PIC X(4).\n       PROCEDURE DIVISION.\n"
                   "           SERVICE RELOAD DFHCOMMAREA.\n           EXEC CICS RETURN END-EXEC.\n")  # fmt: skip
    vl = S.program_unit(S.program_lines(vs2, []))
    assert [ln.text.strip() for ln in B.lower(vl, vl[0].file)][-2] == "CONTINUE."


@pytest.mark.parametrize(
    "old, new, why",
    [
        (  # a long record re-addressed at a paragraph name before its secondary cell was reset
            "           ADD 4096, FRPTR\n               GIVING FRPTR1.\n           SERVICE RELOAD FILE-REC.\n",
            "       NEXT-PARA.\n           ADD 4096, FRPTR\n               GIVING FRPTR1.\n",
            "FRPTR changed (line 23) and a paragraph name reached before its secondary cells FRPTR1 were reset",
        ),
        (
            "           ADD 4096, FRPTR\n               GIVING FRPTR1.\n           SERVICE RELOAD FILE-REC.\n",
            "           SERVICE RELOAD FILE-REC.\n           ADD 4096, FRPTR\n               GIVING FRPTR1.\n",
            "SERVICE RELOAD FILE-REC (line 25) before its secondary cells FRPTR1 were reset",
        ),
        ("GIVING FRPTR1.", "GIVING TSPTR.", "ADD 4096 FRPTR GIVING TSPTR (line 25): TSPTR is not the secondary cell"),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           MOVE FRPTR TO WS-OUT.\n",
            "MOVE FRPTR TO WS-OUT (line 29): an address moved to or from WS-OUT, no plain fullword",
        ),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           MOVE FRPTR TO WS-NUM WS-NUM.\n",
            "MOVE FRPTR TO WS-NUM WS-NUM (line 29): an address moved to several items",
        ),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           MOVE WS-NUM TO FRPTR1.\n",
            "MOVE WS-NUM TO FRPTR1 (line 29): a secondary cell of a long record",
        ),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           IF FRPTR > ZERO GOBACK END-IF.\n",
            "FRPTR (line 29): a BLL cell used as a number",
        ),
        ("MOVE FRPTR TO TSPTR", "MOVE FRPTR TO FRPTR1", "a secondary cell of a long record"),
        (
            "SET(FRPTR) FLENGTH(5400)",
            "SET(FRPTR1) FLENGTH(5400)",
            "FRPTR1 (line 23): a secondary cell of a long record set by a command",
        ),
        ("FROM(WS-OUT) LENGTH(20)", "FROM(TSPTR) LENGTH(4)", "FROM(TSPTR) (line 33): a BLL cell as a command's data"),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           SERVICE LABEL.\n",
            "SERVICE LABEL (line 29: the CICS translator's output)",
        ),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           SERVICE RELOAD WS-OUT.\n",
            "SERVICE RELOAD WS-OUT (line 29): not a LINKAGE SECTION 01 record",
        ),
        (
            "       01  TS-REC.\n",
            "       01  DFHCOMMAREA PIC X.\n       01  TS-REC.\n",
            "DFHCOMMAREA after the BLL cell list",
        ),
    ],
)
def test_what_the_lowering_cannot_keep_is_refused_whole_by_name(tmp_path, old, new, why):
    assert old in PROGRAM
    with pytest.raises(B.Refused) as e:
        _lowered(tmp_path, PROGRAM.replace(old, new, 1))
    msg = str(e.value)
    assert msg.startswith(B.REFUSED_PREFIX + ": ") and msg.endswith(": not modelled"), msg
    assert why in msg, (why, msg)
    assert isinstance(e.value, L.LayoutError)  # (the translator reads such a program no further, as any refused whole)


# ---- #5119 remainder: a cell cleared, and where a record needs another cell ---------------------------------------
def _sized(size: int, occurs: int = 1) -> str:
    """A program with a first record of `size` bytes (x `occurs`) and a second, R2, whose cell is reloaded; the list
    has cells for the worst case (one per 4096 bytes of R1, plus R2's)."""
    n = -(-size * occurs // 4096)
    cells = "".join(f"           02  C{i}                 PIC S9(8) COMP.\n" for i in range(1, n + 2))
    first = f"       01  R1.\n           02  R1-F  PIC X({size})" + (f" OCCURS {occurs}.\n" if occurs > 1 else ".\n")
    return ("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. BLLDEMO.\n       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n       01  WS-IMG PIC X VALUE '*'.\n       LINKAGE SECTION.\n"
            "       01  PARMLIST.\n           02  FILLER             PIC S9(8) COMP.\n" + cells + first +
            "       01  R2 PIC X(8).\n       PROCEDURE DIVISION.\n           SERVICE RELOAD PARMLIST.\n"
            f"           EXEC CICS GETMAIN SET(C{n + 1}) FLENGTH(8) INITIMG(WS-IMG) END-EXEC.\n"
            "           SERVICE RELOAD R2.\n           EXEC CICS RETURN END-EXEC.\n")  # fmt: skip


@pytest.mark.parametrize(
    "size, occurs, cells",
    [(1, 1, 1), (4095, 1, 1), (4096, 1, 1), (4097, 1, 2), (8192, 1, 2), (8193, 1, 3), (4000, 2, 2), (4096, 2, 2),
     (2049, 2, 2), (4097, 3, 4)],
)  # fmt: skip
def test_a_record_takes_one_cell_per_4096_bytes_and_the_next_record_the_cell_after(tmp_path, size, occurs, cells):
    """IBM, "BLL and large storage areas": one cell per 4096 bytes; the record after it is addressed by the cell
    after those, whatever the size, so a miscount would reload R2 through a cell of R1."""
    got = _lowered(tmp_path, _sized(size, occurs))
    assert f"SET ADDRESS OF R2 TO C{cells + 1}." in got, got
    assert not any("C%d" % (cells + 2) in t for t in got)


CLEAR_OLD = "           SERVICE RELOAD FILE-REC.\n"


@pytest.mark.parametrize("fig", ["ZERO", "ZEROS", "ZEROES", "LOW-VALUE", "LOW-VALUES", "zero"])
def test_a_cell_cleared_is_set_to_null(tmp_path, fig):
    """No address in a cell: IBM's conversion makes the cell a POINTER, so MOVE ZERO / LOW-VALUES is SET cell TO NULL (the
    handle zero, X47); the cell is changed, so its record is reloaded as for any change."""
    source = PROGRAM.replace("           MOVE FRPTR TO TSPTR SERVICE RELOAD TS-REC.\n",
                             f"           MOVE {fig} TO TSPTR.\n           SERVICE RELOAD TS-REC.\n")  # fmt: skip
    assert "SET TSPTR TO NULL." in _lowered(tmp_path, source)
    assert "       SET TSPTR TO NULL.\n" in B.lower_text(source, []).replace("           ", "       ")
    r = _translate(tmp_path, source)
    assert r.stats["holes"] == [], r.stats["holes"]


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("MOVE ZERO TO FRPTR1.", "a secondary cell of a long record"),
        ("MOVE ZERO TO FRPTR TSPTR.", "an address moved to several items"),
        ("MOVE SPACES TO TSPTR.", "only ZERO or LOW-VALUES clears a cell"),
        ("MOVE HIGH-VALUES TO TSPTR.", "only ZERO or LOW-VALUES clears a cell"),
        ("MOVE 1 TO TSPTR.", "an address moved to or from 1, no plain fullword"),
    ],
)
def test_what_else_is_moved_into_a_cell_is_refused_by_name(tmp_path, stmt, why):
    source = PROGRAM.replace("           MOVE FRPTR TO TSPTR SERVICE RELOAD TS-REC.\n",
                             f"           {stmt}\n           SERVICE RELOAD TS-REC.\n")  # fmt: skip
    with pytest.raises(B.Refused, match=why):
        _lowered(tmp_path, source)


def _translate(tmp_path: Path, source: str = PROGRAM):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "BLLDEMO.cbl").write_text(source, encoding="ascii")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True, exist_ok=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class BlldemoService {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    return P.translate(tmp_path / "BLLDEMO.cbl", [], stub, "com.x", {}, tmp_path / "proj")


def test_a_bll_program_translates_whole_on_the_pointer_lane(tmp_path):
    r = _translate(tmp_path)
    assert r.stats["holes"] == []
    for call in ("DetCics.getmain(task, f2_FRPTR, 5400, false, ", "DetCics.setAddress(task, f7_FILE_REC, f2_FRPTR);",
                 "Cobol.move(f2_FRPTR, f3_TSPTR, CS);", "DetCics.setAddress(task, f11_TS_REC, f3_TSPTR);"):  # fmt: skip
        assert call in r.java, call


@pytest.mark.parametrize(
    "old, new, hole",
    [  # the cell form of a command that is refused for a pointer too stays refused, under that command's reason
        (
            "MOVE FRPTR TO TSPTR SERVICE RELOAD TS-REC.",
            "EXEC CICS ADDRESS ACEE(TSPTR) END-EXEC SERVICE RELOAD TS-REC.",
            "ADDRESS ACEE: option not modelled",
        ),
        # a list that is not the first LINKAGE record (IBM: only DFHCOMMAREA may precede it) is no BLL list: its
        # fullwords are data, and SET(FRPTR) names no pointer
        (
            "       01  PARMLIST.\n",
            "       01  DFHCOMMAREA PIC X.\n       01  OTHER PIC X.\n       01  PARMLIST.\n",
            "FRPTR: not a plain USAGE POINTER item",
        ),
    ],
)
def test_a_cell_in_a_command_the_lane_refuses_stays_a_hole(tmp_path, old, new, hole):
    assert old in PROGRAM
    r = _translate(tmp_path, PROGRAM.replace(old, new))
    assert any(hole in h for h in r.stats["holes"]), r.stats["holes"]


# ---- the SET(cell) class (#5042's commands, X58): each lowers onto its pointer form ---------------------------------
_GETMAIN = "EXEC CICS GETMAIN SET(FRPTR) FLENGTH(5400)\n                INITIMG(WS-IMG) END-EXEC."
_WS_LEN = ("       01  WS-NUM ", "       01  WS-LEN                 PIC S9(4) COMP VALUE 0.\n       01  WS-NUM ")


@pytest.mark.parametrize(
    "command, java, stub",
    [
        ("READ FILE('F') RIDFLD(WS-OUT) SET(FRPTR)", '"READ " + "F".stripTrailing()', "GGCRDST"),
        # IBM's own order (p. 22): `READ UPDATE DATASET(...)`, UPDATE an option after the verb, never a second verb word
        (
            "READ UPDATE DATASET('FILEA') RIDFLD(WS-OUT)\n                SET(FRPTR) LENGTH(WS-LEN)",
            '"READ " + "FILEA"',
            "GGCRDST",
        ),
        ("READNEXT FILE('F') RIDFLD(WS-OUT) SET(FRPTR)", '"BROWSE " + "F".stripTrailing()', "GGCRDNS"),
        ("READPREV FILE('F') RIDFLD(WS-OUT) SET(FRPTR)", '"BROWSE " + "F".stripTrailing()', "GGCRDPS"),
        ("RECEIVE SET(FRPTR) LENGTH(WS-LEN)\n                MAXLENGTH(80)", '"RECEIVE"', "GGCRECP"),
        ("RETRIEVE SET(FRPTR) LENGTH(WS-LEN)", "null", "GGCRTRS"),
        ("READQ TS QUEUE('Q') SET(FRPTR)\n                LENGTH(WS-LEN) ITEM(1)", '"READQ"', "GGCRDQS"),
    ],
)
def test_each_set_command_into_a_cell_is_its_pointer_form(tmp_path, command, java, stub):
    """Every locate-mode command of the class, SET(cell): the det port sets the cell as its SET(pointer) form does
    (DetCics.setBlock, the key that ends it) and the oracle calls the same stub entry with the cell -- the runtimes
    then answer the X58 step lists alike (tests/cics_crucible/test_cics_set_pointer_5042.py)."""
    source = PROGRAM.replace(_GETMAIN, f"EXEC CICS {command}\n                END-EXEC.").replace(*_WS_LEN)
    r = _translate(tmp_path, source)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert f"DetCics.setBlock(task, f2_FRPTR, {java}" in r.java
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics as ec

    text, _ = ec.translate(source)
    assert f"CALL '{stub}'" in text and "BY REFERENCE FRPTR" in text


@pytest.mark.parametrize(
    "command, hole",
    [  # the cell form keeps each command's own refusal (X58)
        ("RECEIVE SET(FRPTR) LENGTH(WS-LEN)", "RECEIVE SET without MAXLENGTH"),
        ("RETRIEVE SET(FRPTR)", "RETRIEVE SET without LENGTH"),
        ("READQ TS QUEUE('Q') SET(FRPTR) LENGTH(80)", "READQ TS SET with a literal LENGTH"),
        ("READ FILE('F') RIDFLD(WS-OUT) SET(FRPTR) RBA", "READ SET with RBA / RRN / XRBA"),
        ("READNEXT FILE('F') RIDFLD(WS-OUT) SET(FRPTR)\n                LENGTH(WS-LEN)", "READNEXT SET with LENGTH"),
    ],
)
def test_each_set_command_into_a_cell_keeps_its_own_refusal(tmp_path, command, hole):
    source = PROGRAM.replace(_GETMAIN, f"EXEC CICS {command}\n                END-EXEC.").replace(*_WS_LEN)
    r = _translate(tmp_path, source)
    assert any(hole in h for h in r.stats["holes"]), r.stats["holes"]


# ---- IBM's chained storage areas (p. 22): a paragraph name re-addresses; an address held in data -------------------
CHAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IMG                 PIC X VALUE SPACE.
       01  WS-OUT                 PIC X(20) VALUE SPACES.
       01  WS-NAMES               PIC X(12) VALUE 'ONE TWO THRE'.
       01  WS-K                   PIC 9 VALUE 0.
       01  WS-POS                 PIC 99 VALUE 1.
       01  WS-HEAD                PIC S9(8) COMP VALUE 0.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  NEWPTR             PIC S9(8) COMP.
           02  USERPTR            PIC S9(8) COMP.
       01  NEWAREA.
           02  NFIELD             PIC X(4).
           02  NNEXT              PIC S9(8) COMP.
       01  USERAREA.
           02  FIELD              PIC X(4).
           02  NEXTAREA           PIC S9(8) COMP.
       PROCEDURE DIVISION.
       MAIN-PARA.
           SERVICE RELOAD PARMLIST.
           PERFORM BUILD-AREA 3 TIMES.
           MOVE WS-HEAD TO USERPTR.
       WALK.
           MOVE FIELD TO WS-OUT(WS-POS:4).
           ADD 5 TO WS-POS.
           IF NEXTAREA = ZERO GO TO DONE.
           MOVE NEXTAREA TO USERPTR.
           GO TO WALK.
       DONE.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(20) ERASE
                END-EXEC.
           EXEC CICS RETURN END-EXEC.
       BUILD-AREA.
           EXEC CICS GETMAIN SET(NEWPTR) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           SERVICE RELOAD NEWAREA.
           ADD 1 TO WS-K.
           MOVE WS-NAMES(WS-K * 4 - 3:4) TO NFIELD.
           MOVE WS-HEAD TO NNEXT.
           MOVE NEWPTR TO WS-HEAD.
       BUILD-EXIT.
           EXIT.
"""
# hand-traced: three areas pushed on a list (ONE, TWO, THRE; each NNEXT the head before it), walked from the head
# through NEXTAREA, each next area addressed by the paragraph name WALK, as IBM's `MOVE NEXTAREA TO USERPTR. ANYNAME.`
CHAIN_SENT = "THRE TWO  ONE"  # (trailing spaces: the harness trims a SEND TEXT event)


def test_ibms_chained_storage_example_lowers(tmp_path):
    """IBM's example (p. 22) with the SERVICE RELOAD PARMLIST it asks for at the start: `MOVE NEXTAREA TO USERPTR`
    takes the address the fullword holds (a token, X56) and `ANYNAME.` re-addresses USERAREA through USERPTR."""
    source = ("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. BLLDEMO.\n       DATA DIVISION.\n"
              "       WORKING-STORAGE SECTION.\n       01  TESTVAL PIC X(4).\n       LINKAGE SECTION.\n"
              "       01  PARMLIST.\n           02  FILLER PIC S9(8) COMP.\n           02  USERPTR PIC S9(8) COMP.\n"
              "       01  USERAREA.\n           02  FIELD PIC X(4).\n           02  NEXTAREA PIC S9(8) COMP.\n"
              "       PROCEDURE DIVISION.\n           SERVICE RELOAD PARMLIST.\n           MOVE NEXTAREA TO USERPTR.\n"
              "       ANYNAME.\n           MOVE FIELD TO TESTVAL.\n           EXEC CICS RETURN END-EXEC.\n")  # fmt: skip
    got = _lowered(tmp_path, source)
    at = got.index("ANYNAME.")
    assert got[at - 1 : at + 3] == ["CALL 'GGCBLLG' USING NEXTAREA USERPTR.", "ANYNAME.",
                                    "CALL 'GGCBLLR' USING USERAREA USERPTR.", "MOVE FIELD TO TESTVAL."]  # fmt: skip
    oracle = B.lower_text(source, [])
    assert "       ANYNAME.\n           SET ADDRESS OF USERAREA TO USERPTR.\n" in oracle


def test_a_record_changed_with_no_reload_is_readdressed_at_every_paragraph_name(tmp_path):
    """Only the records whose cell changes with no SERVICE RELOAD later in its paragraph are reloaded, at the head of
    every paragraph but one that is only EXIT; det leaves a record as it is for a null cell (CALL 'GGCBLLR'), the
    oracle sets it (GnuCOBOL: a later use fails the proof); an address goes into data as a token (CALL 'GGCBLLP')."""
    got = _lowered(tmp_path, CHAIN)
    reload = "CALL 'GGCBLLR' USING USERAREA USERPTR."
    for para in ("MAIN-PARA.", "WALK.", "DONE.", "BUILD-AREA."):
        assert got[got.index(para) + 1] == reload, para
    assert got[got.index("BUILD-EXIT.") + 1] == "EXIT."
    assert "SET ADDRESS OF NEWAREA TO NEWPTR." in got and not any("NEWAREA NEWPTR" in t for t in got)
    assert "CALL 'GGCBLLP' USING NEWPTR WS-HEAD." in got
    oracle = B.lower_text(CHAIN, [])
    assert oracle.count("SET ADDRESS OF USERAREA TO USERPTR.") == 4 and "GGCBLLR" not in oracle
    r = _translate(tmp_path, CHAIN)
    assert r.stats["holes"] == [], r.stats["holes"]
    for call in ("DetCics.bllReload(task, f14_USERAREA, f3_USERPTR);", "DetCics.bllFromData(task, f16_NEXTAREA, f3_USERPTR);",
                 "DetCics.bllToData(task, f2_NEWPTR, f9_WS_HEAD);"):  # fmt: skip
        assert call in r.java, call


def test_a_long_record_readdressed_at_a_paragraph_name(tmp_path):
    """PROGRAM with its SERVICE RELOAD FILE-REC replaced by a paragraph name after the ADD 4096: FILE-REC is reloaded
    there, whole from its base cell (its secondary cell reset first, as IBM asks)."""
    source = PROGRAM.replace("           SERVICE RELOAD FILE-REC.\n", "       NEXT-PARA.\n")
    got = _lowered(tmp_path, source)
    assert got[got.index("NEXT-PARA.") + 1] == "CALL 'GGCBLLR' USING FILE-REC FRPTR."
    assert "           SET ADDRESS OF FILE-REC TO FRPTR.\n" in B.lower_text(source, [])


def test_declaratives_are_refused_where_records_are_readdressed(tmp_path):
    source = CHAIN.replace("       PROCEDURE DIVISION.\n", "       PROCEDURE DIVISION.\n       DECLARATIVES.\n"
                           "       D1 SECTION.\n           USE FOR DEBUGGING ON ALL PROCEDURES.\n"
                           "       END DECLARATIVES.\n")  # fmt: skip
    with pytest.raises(B.Refused, match="DECLARATIVES in a program whose records are addressed again"):
        _lowered(tmp_path, source)


NULLCELL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(20) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  P1                 PIC S9(8) COMP.
           02  P2                 PIC S9(8) COMP.
           02  P3                 PIC S9(8) COMP.
           02  P4                 PIC S9(8) COMP.
       01  BIG-REC.
           02  FIELD-A            PIC X(8192).
           02  FIELD-T            PIC X(8).
       01  TS-REC                 PIC X(8).
       PROCEDURE DIVISION.
           SERVICE RELOAD PARMLIST.
           EXEC CICS GETMAIN SET(P1) FLENGTH(8200)
                INITIMG(WS-IMG) END-EXEC.
           ADD 4096, P1 GIVING P2.
           ADD 4096, P2 GIVING P3.
           SERVICE RELOAD BIG-REC.
           MOVE 'END!' TO FIELD-T(1:4).
           MOVE 'HD' TO FIELD-A(1:2).
           MOVE P1 TO P4 SERVICE RELOAD TS-REC.
           MOVE TS-REC TO WS-OUT(1:8).
           MOVE FIELD-T(1:4) TO WS-OUT(9:4).
           IF P1 NOT = ZERO MOVE 'Y' TO WS-OUT(13:1).
           MOVE ZERO TO P4.
           IF P4 = ZERO MOVE 'Y' TO WS-OUT(14:1).
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(20) ERASE
                END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
# hand-traced: GETMAIN fills 8200 bytes with '*'; HD at byte 1, END! at byte 8193 (the third cell's span); TS-REC is
# the record's first 8 bytes; P1 holds an address, P4 was cleared
NULLCELL_SENT = "HD******END!YY"


def test_a_cleared_cell_and_a_three_cell_record_translate_whole(tmp_path):
    r = _translate(tmp_path, NULLCELL)
    assert r.stats["holes"] == [], r.stats["holes"]
    lowered = _lowered(tmp_path, NULLCELL)
    assert "SET P4 TO NULL." in lowered and "SET ADDRESS OF BIG-REC TO P1." in lowered


def test_the_oracle_runs_the_same_lowered_program():
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics as ec

    text, has_commarea = ec.translate(PROGRAM)
    assert not has_commarea
    assert "           05  FRPTR USAGE POINTER." in text and "           SET ADDRESS OF FILE-REC TO FRPTR." in text
    assert "BY REFERENCE FRPTR" in text  # (GETMAIN's stub call sets the POINTER, as for any pointer)
    assert all(len(ln) <= 72 for ln in text.splitlines())
    with pytest.raises(ec.Unsupported, match="OS/VS COBOL BLL addressing: SERVICE LABEL"):
        ec.translate(PROGRAM.replace("           MOVE 'HEAD' TO FIELD1(1:4).\n", "           SERVICE LABEL.\n"))


def test_a_long_lowered_statement_is_wrapped_in_fixed_form():
    long_name = "A-VERY-LONG-RECORD-NAME-FOR-WRAPPING"
    rows = B._fixed(f"    MOVE FRPTR TO TSPTR SET ADDRESS OF {long_name} TO TSPTR.")
    assert len(rows) == 2 and all(len(r) <= 65 for r in rows) and rows[1].startswith("    ")


def _prove(tmp_path: Path, name: str, program: str, sent: str) -> None:
    """The lowered program under GnuCOBOL and the stub, and the det port under CicsTask, as one cics case on a synthetic
    estate: proven, and the SEND TEXT both make is the hand-traced `sent`."""
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    program = program.replace("PROGRAM-ID. BLLDEMO.", f"PROGRAM-ID. {name}.")
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "cbl" / f"{name}.cbl").write_text(program, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "bll-5119-synthetic", "program": name, "program_source": f"cbl/{name}.cbl",
            "copy_dirs": [], "transid": "BLL1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "commarea": None, "linked": False, "scenarios": [{"name": "run", "commarea": None}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    svc = name.capitalize() + "Service"
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{svc}.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / f"{name}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", f"bll-5119-{name.lower()}",  # noqa: S603
                           "--case-file", str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port),
                           "--keep", str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["run"]["cobol"]
    assert [e["text"] for e in events if e.get("event") == "SEND-TEXT"] == [sent]


_E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")


@_E2E
def test_a_bll_program_is_proven_against_gnucobol(tmp_path):
    """The record's head written through FILE-REC and read through TS-REC (one block), its tail past 4096 bytes (IBM's
    secondary cell). DFHCOMMAREA before the list, IBM's order: the engine's evidence that the program is a CICS one
    (#4270)."""
    program = PROGRAM.replace("       01  PARMLIST.\n", "       01  DFHCOMMAREA PIC X(4).\n       01  PARMLIST.\n")
    _prove(tmp_path, "BLLDEMO", program, SENT)


@_E2E
def test_a_chained_storage_program_is_proven_against_gnucobol(tmp_path):
    """IBM's chained storage areas: addresses held in data (tokens, alike in both runtimes) and each area addressed
    again at a paragraph name."""
    _prove(tmp_path, "BLLCHAIN", CHAIN, CHAIN_SENT)


READQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLREAD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ITEM                PIC X(12) VALUE 'QUEUED-ITEM1'.
       01  WS-LEN                 PIC S9(4) COMP VALUE 0.
       01  WS-LEND                PIC 99.
       01  WS-OUT                 PIC X(20) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  QPTR               PIC S9(8) COMP.
       01  Q-REC                  PIC X(12).
       PROCEDURE DIVISION.
           SERVICE RELOAD PARMLIST.
           EXEC CICS WRITEQ TS QUEUE('BLLQ') FROM(WS-ITEM)
                LENGTH(12) END-EXEC.
           EXEC CICS READQ TS QUEUE('BLLQ') SET(QPTR)
                LENGTH(WS-LEN) ITEM(1) END-EXEC.
           SERVICE RELOAD Q-REC.
           MOVE Q-REC TO WS-OUT(1:12).
           MOVE WS-LEN TO WS-LEND.
           MOVE WS-LEND TO WS-OUT(14:2).
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(20) ERASE
                END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


@_E2E
def test_a_cleared_cell_and_a_three_cell_record_are_proven_against_gnucobol(tmp_path):
    """A record of 8200 bytes over three cells (its tail past 8192), a cell moved to another, tested against ZERO both
    ways, and cleared by MOVE ZERO."""
    _prove(tmp_path, "BLLNULL", NULLCELL, NULLCELL_SENT)


@_E2E
def test_a_read_set_into_a_cell_is_proven_against_gnucobol(tmp_path):
    """READQ TS SET(cell) and SERVICE RELOAD: the item CICS hands over, read through the record its cell addresses."""
    _prove(tmp_path, "BLLREAD", READQ, "QUEUED-ITEM1 12")


def test_only_a_program_with_bll_evidence_is_read_by_the_lowering():
    """The lowering reads a program only for a SERVICE statement or a SET / DATAPOINTER naming a declared fullword: a
    pointer-lane program (#4771's, SET(pointer) on USAGE POINTER items) or a fragment never reaches its parser."""
    sys.path.insert(0, str(Path(__file__).parent))
    from test_pointer_lane_4771 import PROGRAM as POINTER_PROGRAM

    assert not B.needed(POINTER_PROGRAM.splitlines())
    assert not B.needed(["           EXEC CICS GETMAIN64 SET(P) FLENGTH(10) END-EXEC."])
    assert B.needed(PROGRAM.splitlines())
    assert B.needed(["    SERVICE RELOAD X."])
    assert B.lower_text(POINTER_PROGRAM, []) == POINTER_PROGRAM
