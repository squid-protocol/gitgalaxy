"""#4771 (oracle_assumptions.md X47): the pointer lane -- GETMAIN / FREEMAIN, WEB RECEIVE SET and SET ADDRESS OF.

A POINTER item holds the handle of a block of task storage (CicsTask); SET ADDRESS OF a LINKAGE 01 record to it makes the
record's bytes the block's, so a write through either is seen by the other (a real alias, not a copy). The pieces:
- the translator: a whole program with the four statements translates with no hole; what it cannot model (a pointer a
  REDEFINES overlays, ADDRESS OF a subordinate item or a WORKING-STORAGE record, SET ADDRESS OF ... TO NULL) is refused
  by name;
- the runtime (DetCics + CicsTask, compiled and run): aliasing, the zero padding past a block, and the refusals.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  CACHE-ADDRESS          USAGE POINTER.
       01  SAVE-ADDRESS           USAGE POINTER.
       01  GETMAIN-LENGTH         PIC S9(08) COMP VALUE 64.
       01  RECEIVE-LENGTH         PIC S9(08) COMP VALUE 0.
       01  MAXIMUM-LENGTH         PIC S9(08) COMP VALUE 3200000.
       01  WEB-MEDIA-TYPE         PIC  X(56) VALUE SPACES.
       01  BINARY-ZEROES          PIC  X(01) VALUE LOW-VALUES.
       01  WEBRESP                PIC S9(08) COMP VALUE 0.
       LINKAGE SECTION.
       01  CACHE-MESSAGE          PIC  X(32).
       01  OTHER-MESSAGE          PIC  X(32).
       PROCEDURE DIVISION.
           EXEC CICS WEB RECEIVE SET(CACHE-ADDRESS)
                LENGTH(RECEIVE-LENGTH)
                MAXLENGTH(MAXIMUM-LENGTH) NOSRVCONVERT
                MEDIATYPE(WEB-MEDIA-TYPE) RESP(WEBRESP) NOHANDLE
           END-EXEC.
           SET ADDRESS OF CACHE-MESSAGE TO CACHE-ADDRESS.
           SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.
           EXEC CICS GETMAIN SET(SAVE-ADDRESS)
                FLENGTH(GETMAIN-LENGTH)
                INITIMG(BINARY-ZEROES) NOHANDLE
           END-EXEC.
           SET ADDRESS OF CACHE-MESSAGE TO SAVE-ADDRESS.
           MOVE 'ABC' TO CACHE-MESSAGE.
           SET CACHE-ADDRESS TO ADDRESS OF OTHER-MESSAGE.
           EXEC CICS FREEMAIN DATAPOINTER(SAVE-ADDRESS) NOHANDLE
           END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


def _translate(tmp_path: Path, source: str = PROGRAM):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "PTRLN.cbl").write_text(source, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True, exist_ok=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class PtrlnService {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    return P.translate(tmp_path / "PTRLN.cbl", [], stub, "com.x", {}, tmp_path / "proj")


def test_a_program_with_the_four_pointer_statements_translates_whole(tmp_path):
    r = _translate(tmp_path)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.stats["statements"] == r.stats["translated"]
    java = r.java
    assert ".webReceive(" in java
    assert "DetCics.receivedBlock(task, " in java
    assert java.count("DetCics.setAddress(task, ") == 2 and "DetCics.setAddressOfRecord(task, " in java
    assert "DetCics.getmain(task, " in java and "task.freemain(DetCics.pointerValue(" in java
    assert "DetCics.setPointerToRecord(task, " in java


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        # a REDEFINES over a pointer: ZECS001's CACHE-ADDRESS-X, which `ADD n TO` moves along the block
        (("USAGE POINTER.\n       01  SAVE-ADDRESS", "USAGE POINTER.\n       01  CACHE-ADDRESS-X REDEFINES CACHE-ADDRESS "
                                                      "PIC S9(8) COMP.\n       01  SAVE-ADDRESS"), "REDEFINES overlays"),
        # ADDRESS OF a WORKING-STORAGE record: its storage is shared with the rest of the section
        (("SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.", "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF GETMAIN-LENGTH."),
         "not a LINKAGE 01"),
        (("SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.", "SET ADDRESS OF OTHER-MESSAGE TO NULL."),
         "SET ADDRESS OF"),
    ],
)
def test_what_the_lane_cannot_model_is_refused_by_name(tmp_path, edit, why):
    old, new = edit
    assert old in PROGRAM
    if "REDEFINES" in new:  # (the pointer is overlaid: the first statement that uses it is the refusal)
        source = PROGRAM.replace(old, new, 1)
    else:
        source = PROGRAM.replace(old, new)
    r = _translate(tmp_path, source)
    assert r.stats["holes"], "a statement the lane cannot model must be a hole, never silently translated"
    assert any(why in h for h in r.stats["holes"]), (why, r.stats["holes"])


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_record_set_onto_a_block_is_an_alias_of_it(tmp_path):
    """DetCics.setAddress / setAddressOfRecord / setPointerToRecord over a real CicsTask: a write through the record is the
    block's, a second record set to the first's address shares the bytes, a record longer than the block reads zeros past
    it (ASSUMED, X47), and a null or freed pointer is refused by name."""
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
    static void refused(Runnable r) {
        try { r.run(); System.out.println("not refused"); } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
    }
    public static void main(String[] a) {
        Charset l1 = Charset.forName("ISO-8859-1");
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        Field ptr = rec(8), ptr2 = rec(8), init = rec(1), a1 = rec(4), a2 = rec(4), big = rec(10);
        init.storage().bytes[0] = 'Q';
        int[] r = DetCics.getmain(t, ptr, 6, false, init);
        System.out.println(r[0] + "/" + r[1] + " " + (DetCics.pointerValue(ptr) != 0));
        DetCics.setAddress(t, a1, ptr);
        System.out.println(text(a1));
        a1.storage().bytes[1] = 'x';
        DetCics.setAddressOfRecord(t, a2, a1);
        System.out.println(text(a2) + " " + (a1.storage().bytes == a2.storage().bytes));
        DetCics.setPointer(ptr2, 0);
        DetCics.setPointerToRecord(t, ptr2, a1);
        System.out.println(DetCics.pointerValue(ptr2) != 0);
        int[] f = t.freemain(DetCics.pointerValue(ptr2));
        System.out.println("free of a record: " + f[0] + "/" + f[1]);
        refused(() -> DetCics.setAddress(t, rec(4), rec(8)));
        Field p3 = rec(8);
        DetCics.getmain(t, p3, 3, false, init);
        DetCics.setAddress(t, big, p3);
        System.out.println(text(big));
        refused(() -> DetCics.setAddress(t, rec(20), p3));
        f = t.freemain(DetCics.pointerValue(ptr));
        System.out.println("free: " + f[0] + "/" + f[1]);
        refused(() -> DetCics.setAddress(t, rec(4), ptr));
        refused(() -> t.freemain(DetCics.pointerValue(ptr)));
        int[] z = DetCics.getmain(t, p3, 0, false, init);
        System.out.println(z[0] + "/" + z[1] + " " + DetCics.pointerValue(p3));
        refused(() -> DetCics.setAddress(t, rec(4), p3));
        Field slice = Field.alphanumeric(a1.storage(), 2, 2, false);
        refused(() -> DetCics.setAddress(t, slice, ptr2));
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    built = subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "0/0 true",
        "QQQQQQ",  # (the record is 4 bytes of the 6 the block holds)
        "QxQQQQ true",
        "true",
        "free of a record: 16/1",
        "SET ADDRESS OF a null or unknown pointer: not modelled",
        "QQQ.......",  # (a record longer than its storage reads zeros past it)
        "SET ADDRESS OF a record longer than its storage: not modelled",
        "free: 0/0",
        "SET ADDRESS OF storage already freed: not modelled",
        "FREEMAIN of storage already freed or received: not modelled",
        "22/1 0",
        "SET ADDRESS OF a null or unknown pointer: not modelled",
        "SET ADDRESS OF an item that is not a whole 01 record: not modelled",
    ]
