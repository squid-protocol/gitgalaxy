"""#5042 (oracle_assumptions.md X58): SET(pointer) on RECEIVE, RETRIEVE, READQ TS, GET CONTAINER, READ, READNEXT and READPREV.

Each hands the program the address of a copy of the data in a new block of task storage (the pointer lane of X47); a SET
ADDRESS OF a LINKAGE 01 record then reads it. The pieces, each over the whole class:
- the det translator (Cics.command): the shape of every member and form, and every refusal by name;
- the equivalence harness's translator (equivalence_cics.translate_command): the same members onto the stub's entry points;
- a whole program translates with no hole;
- the runtime (DetCics + CicsTask, compiled and run): the record is the block's bytes, and the pointer ends where IBM says.
(The stub and CicsTask answer one step list alike in tests/cics_crucible/test_cics_set_pointer_5042.py.)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
import test_det_translate as T  # noqa: E402  (bare imports: tests/ has no __init__.py, see CLAUDE.md)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

C = T.C

# (the command, what its translation holds): one per member and form
_SHAPES = [
    (
        "RECEIVE SET(PTR) LENGTH(RLEN) MAXLENGTH(80)",
        ['DetCics.setBlock(task, f_PTR, "RECEIVE", received1.data(), CS);'],
    ),
    (
        "RECEIVE SET(PTR) FLENGTH(RLEN) MAXFLENGTH(80) NOTRUNCATE",
        ["task.receive(INT(80), true);", 'setBlock(task, f_PTR, "RECEIVE"'],
    ),
    (
        "RETRIEVE SET(PTR) LENGTH(RLEN)",
        [
            "task.retrieve(Integer.MAX_VALUE, false, false, false);",
            "DetCics.setBlock(task, f_PTR, null, DetCics.fromRegion(",
            "STORE(RLEN",
        ],
    ),  # fmt: skip
    (
        "RETRIEVE SET(PTR) LENGTH(RLEN) RTRANSID(RT)",
        ["task.retrieve(Integer.MAX_VALUE, true, false, false);", "putPadded(f_RT"],
    ),
    (
        "READQ TS QUEUE('Q') SET(PTR) LENGTH(RLEN)",
        ["task.readqTsNext(", 'DetCics.setBlock(task, f_PTR, "READQ", DetCics.fromRegion(', "Cobol.store(f_RLEN"],
    ),  # fmt: skip
    ("READQ TS QUEUE('Q') ITEM(3) SET(PTR) LENGTH(RLEN)", ["task.readqTs(", "INT(3), Integer.MAX_VALUE)"]),
    (
        "GET CONTAINER(CN) SET(PTR) FLENGTH(FL)",
        ["task.getContainerSet(null, CN.strip())", "DetCics.setPointer(f_PTR, cont1s.handle())", "STORE(FL"],
    ),  # fmt: skip
    ("GET CONTAINER(CN) CHANNEL(CH) SET(PTR) FLENGTH(FL)", ["task.getContainerSet(CH.strip(), CN.strip())"]),
    (
        "GET CONTAINER(CN) SET(PTR) FLENGTH(FL) CONVERTST(DFHVALUE(NOCONVERT)) CCSID(CS)",
        ["task.getContainerSet(null, CN.strip(), -1, true)", "task.containerCcsid()"],
    ),  # fmt: skip
    (
        "READ FILE('KSDS') SET(PTR) RIDFLD(KEY)",
        ["setBlock(task, f_PTR, \"READ \" + 'KSDS'.stripTrailing(), read1.record(), false);"],
    ),
    (
        "READ FILE('KSDS') SET(PTR) RIDFLD(KEY) LENGTH(RLEN)",
        ["read1.record(), false);", "STORE(RLEN, BigDecimal.valueOf(read1.record().length))"],
    ),
    (
        "READ FILE('KSDS') SET(PTR) RIDFLD(KEY) UPDATE",
        ["task.readForUpdate(", "read1.record(), true);", "heldKey.put("],
    ),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) UPDATE TOKEN(TK)", ["read1.record(), true);", "task.holdToken("]),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) GTEQ", ["read1.record(), false);"]),
    (
        "READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY)",
        ["task.readnext(", "setBlock(task, f_PTR, \"BROWSE \" + 'KSDS'.stripTrailing(), rec", ", true);"],
    ),
    (
        "READPREV FILE('KSDS') SET(PTR) RIDFLD(KEY)",
        ["task.readprev(", "setBlock(task, f_PTR, \"BROWSE \" + 'KSDS'.stripTrailing(), rec", ", true);"],
    ),
]


@pytest.mark.parametrize(("text", "holds"), _SHAPES)
def test_every_member_translates_to_a_block_the_pointer_addresses(text, holds):
    out = "\n".join(T._PtrCics().command(text, ""))
    for h in holds:
        assert h in out, (text, h, out)
    assert "DetCics.put(f_PTR" not in out  # (the pointer is never a record to move data into)


_REFUSED = [
    ("RECEIVE SET(PTR) LENGTH(RLEN)", "without MAXLENGTH"),
    ("RECEIVE SET(PTR) MAXLENGTH(80)", "without LENGTH"),
    ("RECEIVE SET(TBL-PTR) LENGTH(RLEN) MAXLENGTH(80)", "plain USAGE POINTER"),
    ("RECEIVE SET(OVER-PTR) LENGTH(RLEN) MAXLENGTH(80)", "REDEFINES overlays"),
    ("RECEIVE SET(REC) LENGTH(RLEN) MAXLENGTH(80)", "USAGE POINTER"),
    ("RETRIEVE SET(PTR)", "RETRIEVE SET without LENGTH"),
    ("RETRIEVE SET(PTR) LENGTH(4)", "literal LENGTH"),
    ("RETRIEVE SET(PTR) LENGTH(LENGTH OF REC)", "literal LENGTH"),
    ("RETRIEVE INTO(REC) SET(PTR) LENGTH(RLEN)", "alternatives"),
    ("RETRIEVE SET(PTR) LENGTH(RLEN) WAIT", "WAIT"),
    ("READQ TS QUEUE('Q') SET(PTR)", "READQ TS SET without LENGTH"),
    ("READQ TS QUEUE('Q') SET(PTR) LENGTH(40)", "literal LENGTH"),
    ("READQ TS QUEUE('Q') INTO(REC) SET(PTR) LENGTH(RLEN)", "alternatives"),
    ("READQ TS QUEUE('Q') SET(PTR) LENGTH(RLEN) SYSID('R')", "SYSID"),
    ("GET CONTAINER(CN) SET(PTR)", "SET without FLENGTH"),
    ("GET CONTAINER(CN) SET(PTR) FLENGTH(8)", "SET without FLENGTH"),
    ("GET CONTAINER(CN) SET(PTR) INTO(REC) FLENGTH(FL)", "needs one of INTO"),
    ("GET CONTAINER(CN) SET(PTR) NODATA FLENGTH(FL)", "needs one of INTO"),
    ("GET CONTAINER(CN) SET(PTR) FLENGTH(FL) BYTEOFFSET(2)", "BYTEOFFSET"),
    ("READ FILE('KSDS') SET(PTR) INTO(REC) RIDFLD(KEY)", "needs one of INTO / SET"),
    ("READ FILE('KSDS') RIDFLD(KEY)", "needs one of INTO / SET"),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) LENGTH(80)", "SET with LENGTH"),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) RBA", "SET with RBA"),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) SYSID('R')", "SYSID"),
    ("READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY) LENGTH(RLEN)", "SET with LENGTH"),
    ("READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY) RBA", "SET with RBA"),
    ("READPREV FILE('KSDS') RIDFLD(KEY)", "READPREV needs one of INTO / SET"),
    ("READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY) UPDATE", "browse for update"),
    ("GETMAIN64 SET(PTR) FLENGTH(L)", "GETMAIN64 not modelled"),
    ("FREEMAIN64 DATAPOINTER(PTR)", "FREEMAIN64 not modelled"),
    ("LOAD PROGRAM('P') SET(PTR)", "LOAD not modelled"),
]


@pytest.mark.parametrize(("text", "why"), _REFUSED)
def test_what_the_class_cannot_model_is_refused_by_name(text, why):
    with pytest.raises(C.CicsError, match=why):
        T._PtrCics().command(text, "")


def test_the_other_set_options_of_the_same_words_stay_refused():
    """SEND MAP / RECEIVE MAP / SEND CONTROL SET(ptr-ref) point at BMS storage, a different mechanism: still refused."""
    for text in ("SEND MAP('M') SET(PTR)", "RECEIVE MAP('M') SET(PTR)", "SEND CONTROL SET(PTR)"):
        with pytest.raises(C.CicsError, match="SET"):
            T._PtrCics().command(text, "")


# ---- the equivalence harness's translator ------------------------------------------------------------------------------------
def _ec():
    import equivalence_cics as ec

    return ec


@pytest.mark.parametrize(
    ("text", "call"),
    [
        ("RECEIVE SET(P) LENGTH(L) MAXLENGTH(80)", "GGCRECP"),
        ("RETRIEVE SET(P) LENGTH(L)", "GGCRTRS"),
        ("READQ TS QUEUE(Q) SET(P) LENGTH(L)", "GGCRDQS"),
        ("GET CONTAINER(C) SET(P) FLENGTH(L)", "GGCGETS"),
        ("READ FILE(F) SET(P) RIDFLD(K)", "GGCRDST"),
        ("READ FILE(F) SET(P) RIDFLD(K) UPDATE LENGTH(L)", "GGCRDST"),
        ("READNEXT FILE(F) SET(P) RIDFLD(K)", "GGCRDNS"),
        ("READPREV FILE(F) SET(P) RIDFLD(K)", "GGCRDPS"),
    ],
)
def test_the_harness_calls_the_stubs_entry_point_for_every_member(text, call):
    out = _ec().translate_command(text)
    assert f"CALL '{call}' USING GG-CICS" in out
    assert "    BY REFERENCE P" in out  # (the pointer item, by reference: the stub stores the block's address in it)


@pytest.mark.parametrize(
    "text",
    [
        "RECEIVE SET(P) LENGTH(L)",
        "RECEIVE SET(A(1)) LENGTH(L) MAXLENGTH(80)",
        "RETRIEVE SET(P)",
        "RETRIEVE INTO(A) SET(P) LENGTH(L)",
        "READQ TS QUEUE(Q) SET(P)",
        "READQ TS QUEUE(Q) INTO(A) SET(P) LENGTH(L)",
        "GET CONTAINER(C) SET(P) FLENGTH(8)",
        "GET CONTAINER(C) SET(P) NODATA FLENGTH(L)",
        "READ FILE(F) SET(P) INTO(A) RIDFLD(K)",
        "READ FILE(F) SET(P) RIDFLD(K) LENGTH(8)",
        "READNEXT FILE(F) SET(P) RIDFLD(K) RBA",
        "READNEXT FILE(F) SET(P) RIDFLD(K) LENGTH(L)",
    ],
)
def test_the_harness_refuses_what_the_translator_refuses(text):
    with pytest.raises(_ec().Unsupported):
        _ec().translate_command(text)


def test_the_harness_sets_the_lengths_and_the_token_back():
    out = _ec().translate_command("READ FILE(F) SET(P) RIDFLD(K) UPDATE TOKEN(TK) LENGTH(L)")
    assert "    MOVE GG-LEN TO L" in out and "    MOVE GG-NUM TO TK" in out
    assert "MOVE 'UPDATE TOKEN' TO GG-FLAGS" in out
    out = _ec().translate_command("READQ TS QUEUE(Q) SET(P) LENGTH(L) NUMITEMS(N)")
    assert "    MOVE GG-LEN TO L" in out and "    MOVE GG-NUM TO N" in out
    assert (
        _ec().translate_command("RECEIVE SET(P) LENGTH(L) MAXLENGTH(80) NOTRUNCATE")[0]
        == "MOVE 'NOTRUNCATE' TO GG-FLAGS"
    )


# ---- a whole program --------------------------------------------------------------------------------------------------------
PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRSET.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  RCV-PTR                USAGE POINTER.
       01  RTV-PTR                USAGE POINTER.
       01  QUE-PTR                USAGE POINTER.
       01  CON-PTR                USAGE POINTER.
       01  RCV-LEN                PIC S9(04) COMP VALUE 0.
       01  RTV-LEN                PIC S9(04) COMP VALUE 0.
       01  QUE-LEN                PIC S9(04) COMP VALUE 0.
       01  CON-LEN                PIC S9(08) COMP VALUE 0.
       01  QNAME                  PIC  X(08) VALUE 'QUEUE1'.
       01  CNAME                  PIC  X(16) VALUE 'CONT1'.
       01  CHNAME                 PIC  X(16) VALUE 'CHAN1'.
       01  RESPCODE               PIC S9(08) COMP VALUE 0.
       LINKAGE SECTION.
       01  RCV-REC                PIC  X(32).
       01  RTV-REC                PIC  X(32).
       01  QUE-REC                PIC  X(32).
       01  CON-REC                PIC  X(32).
       PROCEDURE DIVISION.
           EXEC CICS RECEIVE SET(RCV-PTR) LENGTH(RCV-LEN)
                MAXLENGTH(80) RESP(RESPCODE) NOHANDLE
           END-EXEC.
           SET ADDRESS OF RCV-REC TO RCV-PTR.
           EXEC CICS RETRIEVE SET(RTV-PTR) LENGTH(RTV-LEN)
                RESP(RESPCODE) NOHANDLE
           END-EXEC.
           SET ADDRESS OF RTV-REC TO RTV-PTR.
           EXEC CICS READQ TS QUEUE(QNAME) SET(QUE-PTR)
                LENGTH(QUE-LEN) RESP(RESPCODE) NOHANDLE
           END-EXEC.
           SET ADDRESS OF QUE-REC TO QUE-PTR.
           EXEC CICS GET CONTAINER(CNAME) CHANNEL(CHNAME)
                SET(CON-PTR) FLENGTH(CON-LEN)
                RESP(RESPCODE) NOHANDLE
           END-EXEC.
           SET ADDRESS OF CON-REC TO CON-PTR.
           EXEC CICS RETURN END-EXEC.
"""


def _translate(tmp_path: Path, source: str = PROGRAM):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "PTRSET.cbl").write_text(source, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True, exist_ok=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class PtrsetService {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    return P.translate(tmp_path / "PTRSET.cbl", [], stub, "com.x", {}, tmp_path / "proj")


def test_a_program_with_the_four_set_forms_translates_whole(tmp_path):
    r = _translate(tmp_path)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.stats["statements"] == r.stats["translated"]
    java = r.java
    assert "DetCics.setBlock(task, " in java and java.count("DetCics.setAddress(task, ") == 4
    assert "task.receive(" in java and "task.retrieve(" in java and "task.readqTsNext(" in java
    assert "task.getContainerSet(" in java


def test_a_set_into_a_pointer_a_redefines_overlays_is_a_hole(tmp_path):
    source = PROGRAM.replace(
        "       01  RCV-LEN ", "       01  RCV-PTR-X REDEFINES RCV-PTR PIC X(8).\n       01  RCV-LEN ", 1
    )
    r = _translate(tmp_path, source)
    assert any("REDEFINES overlays" in h for h in r.stats["holes"]), r.stats["holes"]


# ---- the runtime, compiled and run --------------------------------------------------------------------------------------------
def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_record_set_onto_a_set_block_reads_it_and_the_pointer_ends_where_ibm_says(tmp_path):
    """DetCics.setBlock over a real CicsTask: the record addressed through the pointer holds a copy of the data; a write
    through it never changes the source; the next RECEIVE ends the first pointer (its record then reads zeros, ASSUMED
    X58); a READ UPDATE SET pointer ends at SYNCPOINT, a READ SET pointer at the next READ of the file."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cics.CicsTask;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetCics;
public class Main {
    static Field rec(int n) { return Field.alphanumeric(new Storage(n), 0, n, false); }
    static String text(Field f) { return new String(f.storage().bytes, java.nio.charset.StandardCharsets.ISO_8859_1).replace('\\0', '.'); }
    public static void main(String[] a) {
        Charset l1 = Charset.forName("ISO-8859-1");
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withTerminalInput("hello world!");
        Field p1 = rec(8), p2 = rec(8), r1 = rec(5), r2 = rec(5), r3 = rec(4), r4 = rec(4);
        CicsTask.Received got = t.receive(5, true);
        DetCics.setBlock(t, p1, "RECEIVE", got.data(), l1);
        DetCics.setAddress(t, r1, p1);
        System.out.println(text(r1));
        r1.storage().bytes[0] = 'J';
        System.out.println(text(r1));
        got = t.receive(80, true);
        DetCics.setBlock(t, p2, "RECEIVE", got.data(), l1);
        DetCics.setAddress(t, r2, p2);
        System.out.println(text(r1) + " " + text(r2));
        DetCics.setBlock(t, p1, "READ F", "ABCD".getBytes(l1), false);
        DetCics.setAddress(t, r3, p1);
        System.out.println(text(r3));
        DetCics.setBlock(t, p1, "READ F", "WXYZ".getBytes(l1), false);
        System.out.println(text(r3));
        DetCics.setBlock(t, p2, "BROWSE F", "1234".getBytes(l1), true);
        DetCics.setAddress(t, r4, p2);
        t.syncpoint();
        System.out.println(text(r4));
        try {
            t.freemain(DetCics.pointerValue(p1));
            System.out.println("freed");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert (
        out
        == [
            "hello",
            "Jello",
            ".....  world!",  # (the first pointer's record reads zeros: the next RECEIVE ended it; the second's is the block's " world!")
            "ABCD",
            "....",
            "....",
            "FREEMAIN of storage already freed or received: not modelled",
        ]
    )
