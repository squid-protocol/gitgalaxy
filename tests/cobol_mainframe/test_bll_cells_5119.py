"""#5119 (oracle_assumptions.md X56): OS/VS COBOL's BLL cells and SERVICE RELOAD, lowered onto the pointer lane (X47).

IBM's CICS/MVS 2.1.2 Application Programmer's Reference (SC33-0512-1) gives the OS/VS COBOL addressing ("Base locator
for linkage (BLL)", pp. 21-23) and its own conversion to VS COBOL II ("Converting to VS COBOL II", p. 29; Figure 3,
p. 26). det/bll.py applies that conversion to the program before either side reads it -- the cell list becomes
POINTERs in WORKING-STORAGE, SERVICE RELOAD record becomes SET ADDRESS OF record TO its cell, the long record's
`ADD 4096` goes, MOVE cell TO cell is SET cell TO cell -- so the det port and the GnuCOBOL oracle run one program on the
pointer lane. The pieces, the whole input class each:
- the lowering of IBM's own examples (Figure 3, the SERVICE RELOAD example, Figure 5, the MOVE example), unchanged for
  a program with no BLL evidence, and each idiom it cannot keep refused whole by name;
- the det translator: a BLL program translates with no hole; READ SET(cell) and ADDRESS TWA(cell) are still holes
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
        (
            "           SERVICE RELOAD FILE-REC.\n",
            "",
            "FRPTR changed (line 23) with no SERVICE RELOAD FILE-REC after it in the paragraph",
        ),
        (
            "           SERVICE RELOAD FILE-REC.\n",
            "       NEXT-PARA.\n           SERVICE RELOAD FILE-REC.\n",
            "with no SERVICE RELOAD FILE-REC after it in the paragraph (addressability through a paragraph name)",
        ),
        (
            "           ADD 4096, FRPTR\n               GIVING FRPTR1.\n           SERVICE RELOAD FILE-REC.\n",
            "           SERVICE RELOAD FILE-REC.\n           ADD 4096, FRPTR\n               GIVING FRPTR1.\n",
            "SERVICE RELOAD FILE-REC (line 25) before its secondary cells FRPTR1 were reset",
        ),
        ("GIVING FRPTR1.", "GIVING TSPTR.", "ADD 4096 FRPTR GIVING TSPTR (line 25): TSPTR is not the secondary cell"),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           MOVE FRPTR TO WS-NUM.\n",
            "MOVE FRPTR TO WS-NUM (line 29): an address moved to or from a data item",
        ),
        (
            "           MOVE 'HEAD' TO FIELD1(1:4).\n",
            "           IF FRPTR = ZERO GOBACK END-IF.\n",
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
            "EXEC CICS GETMAIN SET(FRPTR) FLENGTH(5400)\n                INITIMG(WS-IMG) END-EXEC.",
            "EXEC CICS READ FILE('F') RIDFLD(WS-OUT) SET(FRPTR)\n                END-EXEC.",
            "READ",
        ),
        (
            "MOVE FRPTR TO TSPTR SERVICE RELOAD TS-REC.",
            "EXEC CICS ADDRESS TWA(TSPTR) END-EXEC SERVICE RELOAD TS-REC.",
            "EXEC CICS ADDRESS not modelled",
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


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_bll_program_is_proven_against_gnucobol(tmp_path):
    """The lowered program under GnuCOBOL and the stub, and the det port under CicsTask: the SEND TEXT both make is
    the hand-traced one -- the record's head written through FILE-REC and read through TS-REC (one block), its tail past
    4096 bytes (IBM's secondary cell) -- and the case is proven."""
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    # (DFHCOMMAREA before the list, IBM's order: the engine's evidence that the program is a CICS one, #4270)
    program = PROGRAM.replace("       01  PARMLIST.\n", "       01  DFHCOMMAREA PIC X(4).\n       01  PARMLIST.\n")
    (estate / "cbl" / "BLLDEMO.cbl").write_text(program, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "bll-5119-synthetic", "program": "BLLDEMO", "program_source": "cbl/BLLDEMO.cbl",
            "copy_dirs": [], "transid": "BLL1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "commarea": None, "linked": False, "scenarios": [{"name": "long-record", "commarea": None}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "BlldemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "BLLDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "bll-5119", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["long-record"]["cobol"]
    assert [e["text"] for e in events if e.get("event") == "SEND-TEXT"] == [SENT]
