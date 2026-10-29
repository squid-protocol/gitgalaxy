"""#4771 (oracle_assumptions.md X47): the pointer lane -- GETMAIN / FREEMAIN, WEB RECEIVE SET and SET ADDRESS OF.

A POINTER item holds the handle of a block of task storage (CicsTask); SET ADDRESS OF a LINKAGE 01 record to it makes the
record's bytes the block's, so a write through either is seen by the other (a real alias, not a copy). The pieces:
- the translator: a whole program with the four statements translates with no hole; what it cannot model (a pointer a
  REDEFINES overlays, SET ADDRESS OF ... TO NULL) is refused
  by name;
- the runtime (DetCics + CicsTask, compiled and run): aliasing, the zero padding past a block, and the refusals.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

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
       01  ELEMENT-TABLE.
           02  ELEMENT-ITEM       PIC  X(32) OCCURS 3 TIMES.
       01  WEBRESP                PIC S9(08) COMP VALUE 0.
       LINKAGE SECTION.
       01  CACHE-MESSAGE.
           02  CACHE-SUB          PIC  X(32).
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
    assert "setPointerToItem" not in java and "setAddressOfItem" not in java  # a LINKAGE 01 record: unchanged output


def test_address_of_a_subordinate_or_working_storage_item_is_a_windowed_alias(tmp_path):
    """#4771 (X47): SET ADDRESS OF record TO ADDRESS OF item and SET ptr TO ADDRESS OF item, for an item inside a record
    (ZECS001's ZF-DATA) or a WORKING-STORAGE record, translate whole through the window calls."""
    source = PROGRAM.replace(
        "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.",
        "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF ZF-DATA.",
    ).replace("SET CACHE-ADDRESS TO ADDRESS OF OTHER-MESSAGE.", "SET CACHE-ADDRESS TO ADDRESS OF WEB-MEDIA-TYPE.")
    source = source.replace(
        "       LINKAGE SECTION.",
        "       01  ZF-RECORD.\n           02  ZF-PREFIX      PIC  X(08).\n           02  ZF-DATA        PIC  X(32).\n"
        "       LINKAGE SECTION.",
        1,
    )
    r = _translate(tmp_path, source)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert "DetCics.setAddressOfItem(task, " in r.java and "DetCics.setPointerToItem(task, " in r.java


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        # a REDEFINES over a pointer that is not a pure numeric view (a byte view: the handle's bytes would be read)
        (
            (
                "USAGE POINTER.\n       01  SAVE-ADDRESS",
                "USAGE POINTER.\n       01  CACHE-ADDRESS-X REDEFINES CACHE-ADDRESS PIC X(8).\n       01  SAVE-ADDRESS",
            ),
            "REDEFINES overlays",
        ),
        # ADDRESS OF a table element: an element of an OCCURS is not a single item
        (
            (
                "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.",
                "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF ELEMENT-ITEM.",
            ),
            "a table element",
        ),
        (
            ("SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF CACHE-MESSAGE.", "SET ADDRESS OF OTHER-MESSAGE TO NULL."),
            "SET ADDRESS OF",
        ),
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


_OVERLAY_HEAD = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  LINKAGE-ADDRESSES.
           02  CACHE-ADDRESS      USAGE POINTER.
           02  CACHE-ADDRESS-X    REDEFINES CACHE-ADDRESS
                                  PIC S9(08) COMP.
           02  SAVE-ADDRESS       USAGE POINTER.
           02  SAVE-ADDRESS-X     REDEFINES SAVE-ADDRESS.
               03  SAVE-HIGH      PIC S9(04) COMP.
               03  SAVE-LOW       PIC S9(04) COMP.
       01  ZF-LENGTH              PIC S9(08) COMP VALUE 5.
       01  OUT-NUMBER             PIC S9(08) COMP VALUE 0.
       PROCEDURE DIVISION.
"""


@pytest.mark.parametrize(
    "statement",
    [
        "MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X.",  # (SAVE-ADDRESS-X is a group view, not a pure numeric one)
        "ADD ZF-LENGTH TO CACHE-ADDRESS-X GIVING OUT-NUMBER.",  # the sum is a number, a handle is none
        "ADD ZF-LENGTH 1 TO CACHE-ADDRESS-X.",
        "ADD ZF-LENGTH TO CACHE-ADDRESS-X ROUNDED.",
        "ADD ZF-LENGTH TO CACHE-ADDRESS-X ON SIZE ERROR MOVE 1 TO OUT-NUMBER END-ADD.",
        "ADD CACHE-ADDRESS-X TO OUT-NUMBER.",
        "MULTIPLY 2 BY CACHE-ADDRESS-X.",
        "MOVE CACHE-ADDRESS-X TO OUT-NUMBER.",
        "MOVE ZF-LENGTH TO CACHE-ADDRESS-X.",
        "COMPUTE OUT-NUMBER = CACHE-ADDRESS-X + 1.",
        "IF CACHE-ADDRESS-X EQUAL ZEROES MOVE 1 TO OUT-NUMBER END-IF.",
        "MOVE SAVE-LOW TO OUT-NUMBER.",  # a field under the overlay is the pointer's bytes too
        "MOVE ZERO TO SAVE-HIGH.",
    ],
)
def test_a_numeric_view_of_a_pointer_is_a_hole_not_arithmetic_on_a_handle(tmp_path, statement):
    """A pointer holds a handle of a block, not an address: ADD n TO / MOVE / COMPUTE / IF on an item that REDEFINES a
    POINTER (ZECS001's CACHE-ADDRESS-X) would compute on handle bytes, so the statement is refused by name -- even
    when no pointer-lane statement uses the pointer, where the pointer's own refusal never fires."""
    source = _OVERLAY_HEAD + "           " + statement + "\n           EXEC CICS RETURN END-EXEC.\n"
    r = _translate(tmp_path, source)
    assert any("REDEFINES overlays a POINTER" in h for h in r.stats["holes"]), r.stats["holes"]
    assert r.stats["translated"] < r.stats["statements"]


_PURE_HEAD = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  LINKAGE-ADDRESSES.
           02  CACHE-ADDRESS      USAGE POINTER.
           02  CACHE-ADDRESS-X    REDEFINES CACHE-ADDRESS
                                  PIC S9(08) COMP.
           02  SAVE-ADDRESS       USAGE POINTER.
           02  SAVE-ADDRESS-X     REDEFINES SAVE-ADDRESS
                                  PIC S9(08) COMP.
       01  ZF-LENGTH              PIC S9(08) COMP VALUE 5.
       01  GETMAIN-LENGTH         PIC S9(08) COMP VALUE 64.
       01  BINARY-ZEROES          PIC  X(01) VALUE LOW-VALUES.
       LINKAGE SECTION.
       01  CACHE-MESSAGE          PIC  X(8).
       PROCEDURE DIVISION.
"""


@pytest.mark.parametrize(
    "statement",
    [
        "ADD ZF-LENGTH TO CACHE-ADDRESS-X.",  # ZECS001: advance the address
        "SUBTRACT ZF-LENGTH FROM CACHE-ADDRESS-X.",
        "ADD 32 TO CACHE-ADDRESS-X.",
        "MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X.",  # ZECS001: copy the address through the two views
    ],
)
def test_a_pure_numeric_view_of_a_pointer_moves_the_pointer_not_its_bytes(tmp_path, statement):
    """#4771 (X47): `ADD|SUBTRACT n TO|FROM view` and `MOVE view TO view` over a pure `PIC S9(8) COMP` REDEFINES of a
    POINTER (ZECS001's CACHE-ADDRESS-X) are the two address idioms: they translate whole, to the runtime's pointer calls,
    and the pointer-lane statements that name the pointer are no longer refused for the overlay."""
    source = (
        _PURE_HEAD
        + "           EXEC CICS GETMAIN SET(CACHE-ADDRESS) FLENGTH(GETMAIN-LENGTH)\n"
        + "                INITIMG(BINARY-ZEROES) NOHANDLE\n           END-EXEC.\n"
        + "           "
        + statement
        + "\n           SET ADDRESS OF CACHE-MESSAGE TO CACHE-ADDRESS.\n"
        + "           EXEC CICS FREEMAIN DATAPOINTER(SAVE-ADDRESS) NOHANDLE\n           END-EXEC.\n"
        + "           EXEC CICS RETURN\n           END-EXEC.\n"
    )
    r = _translate(tmp_path, source)
    assert r.stats["holes"] == [], r.stats["holes"]
    call = "copyPointer" if statement.startswith("MOVE") else "advancePointer"
    assert f"DetCics.{call}(" in r.java
    assert "-(" in r.java or not statement.startswith("SUBTRACT")


def test_the_whole_group_holding_a_pointer_still_moves_as_bytes(tmp_path):
    """A MOVE or INITIALIZE of the group that holds the pointer and its overlay copies / clears the handle bytes, which
    is what IBM's group move does: only a statement that names the numeric view is refused."""
    source = _OVERLAY_HEAD + "           INITIALIZE LINKAGE-ADDRESSES.\n           EXEC CICS RETURN END-EXEC.\n"
    r = _translate(tmp_path, source)
    assert not any("REDEFINES overlays a POINTER" in h for h in r.stats["holes"]), r.stats["holes"]


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
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
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


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_windowed_storage_reads_and_writes_every_field_kind_as_the_plain_one_does(tmp_path):
    """#4771: a record set onto an item inside a larger storage views it through Storage.base. Every item kind (display
    incl. leading separate sign, packed, binary, native binary, edited, alphanumeric, a group, a reference modification)
    gives the same bytes there as in a plain storage, a write through the window is the storage's and the other way, and
    pointers to the item are the same one each time and differ from the record's own."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Arrays;
import t.cics.CicsTask;
import t.cobolrt.Cobol;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetCics;
public class Main {
    static final Charset CS = Charset.forName("ISO-8859-1");
    static Field[] kinds(Storage s) {
        return new Field[] {
            Field.zoned(s, 0, 5, 2, true, false, false), Field.zoned(s, 5, 4, 0, true, true, true),
            Field.packed(s, 10, 7, 1, true), Field.binary(s, 14, 8, 0, true, false), Field.binary(s, 18, 4, 0, false, true),
            Field.numericEdited(s, 20, 8, "ZZZ9.99", false), Field.alphanumeric(s, 28, 4, false)};
    }
    static void fill(Field[] f) {
        BigDecimal[] v = {new BigDecimal("-123.45"), new BigDecimal("-77"), new BigDecimal("12345.6"),
            new BigDecimal("-12345678"), new BigDecimal("4321"), new BigDecimal("12.5")};
        for (int i = 0; i < v.length; i++) Cobol.move(v[i], f[i], CS);
        Cobol.move("ab", f[6], CS);
        Cobol.move(f[0], f[3], CS);          // field to field: display -> binary
        Cobol.move(f[2], f[1], CS);          // packed -> separate-sign display
    }
    public static void main(String[] a) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        Storage plain = new Storage(32);
        fill(kinds(plain));
        Storage big = new Storage(100);
        Arrays.fill(big.bytes, (byte) '#');
        Field item = Field.alphanumeric(big, 41, 32, false);
        Field rec = Field.group(new Storage(32), 0, 32);
        DetCics.setAddressOfItem(t, rec, item);
        fill(kinds(rec.storage()));
        System.out.println(Arrays.equals(plain.bytes, Arrays.copyOfRange(big.bytes, 41, 73)));
        System.out.println(big.bytes[40] == '#' && big.bytes[73] == '#');
        System.out.println(Arrays.equals(rec.raw(), plain.bytes) + " " + rec.offset());
        Field ref = rec.ref(29, 4);
        System.out.println(new String(ref.raw(), CS) + " " + ref.offset());
        big.bytes[41 + 28] = 'Z';
        System.out.println(new String(Field.alphanumeric(rec.storage(), 28, 4, false).raw(), CS));
        Field p = Field.alphanumeric(new Storage(8), 0, 8, false), q = Field.alphanumeric(new Storage(8), 0, 8, false);
        DetCics.setPointerToItem(t, p, item);
        DetCics.setPointerToRecord(t, q, rec);
        System.out.println(DetCics.samePointer(t, p, q) + " " + (DetCics.pointerValue(p) == DetCics.pointerValue(q)));
        Field own = Field.alphanumeric(big, 0, 8, false), pOwn = Field.alphanumeric(new Storage(8), 0, 8, false);
        DetCics.setPointerToItem(t, pOwn, own);
        System.out.println(DetCics.samePointer(t, p, pOwn));
        Field viaPtr = Field.alphanumeric(new Storage(4), 0, 4, false);
        DetCics.setAddress(t, viaPtr, p);
        System.out.println(viaPtr.offset() + " " + new String(viaPtr.raw(), CS).length());
        try {
            DetCics.setAddressOfItem(t, Field.alphanumeric(new Storage(40), 0, 40, false), Field.alphanumeric(big, 90, 5, false));
            System.out.println("not refused");
        } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
        Field again = Field.group(new Storage(8), 0, 8);
        DetCics.setAddressOfRecord(t, again, rec);
        System.out.println(again.offset() + " " + (again.storage().bytes == big.bytes));
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
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "true",
        "true",
        "true 41",
        "ab   69",
        "Zb  ",
        "true true",
        "false",
        "41 4",
        "SET ADDRESS OF a record longer than the storage after the item: not modelled",
        "41 true",
    ], out


def test_every_pointer_hole_left_in_zecs001_is_refused_by_name(tmp_path):
    """#4771: the estate's own ZECS001 (not a model of it) holds no pointer hole; its CALL ZUIDSTCK is the stand-in (#5945).

    The stub has a `runTask(CicsTask)`, as the forge's has: without it the CICS lane is off and every pointer statement is
    the generic "SET ADDRESS OF (pointers)" hole, which would hide the reason this test exists to pin."""
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    src = Path(root) / "zecs/Source/ZECS001.cbl" if root else None
    if src is None or not src.is_file():
        pytest.skip("needs the zecs corpus (GITGALAXY_MAINFRAME_CORPORA)")
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class Zecs001Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(src, [], stub, "com.x", {}, tmp_path / "proj")
    # (case-insensitive: "SET-ADDRESS CACHE-ADDRESS: a pointer a REDEFINES overlays" names no upper-case POINTER)
    pointer = [
        h
        for h in r.stats["holes"]
        if any(k in h.upper() for k in ("POINTER", "ADDRESS", "ZUIDSTCK", "GETMAIN", "FREEMAIN"))
    ]
    assert not any("SET ADDRESS OF (pointers)" in h for h in r.stats["holes"]), "the CICS lane must be on"
    # (#4771: the pointer arithmetic is modelled -- CACHE-ADDRESS-X / SAVE-ADDRESS-X are pure numeric views -- and #5945
    # models CALL ZUIDSTCK as a stand-in whose 16 bytes the run states, so no pointer-lane hole is left)
    assert pointer == [], pointer
    # (the whole hole set, not only the pointer-looking holes: 560 of 561 statements translate, and the one left is the
    # COMMAREA DTO the stub does not carry, so a new hole of any kind cannot hide)
    assert (r.stats["statements"], r.stats["translated"]) == (561, 560), r.stats
    assert sorted(int(h.split(":")[0].split()[1]) for h in r.stats["holes"]) == [753], r.stats["holes"]
    assert "cobolrt.le.Zuidstck.call(" in r.java  # the CALL (line 1244) is the stand-in, THE-TOD passed by reference
    for line in (1111, 1115, 1147, 1400, 1519):  # the views' ADD / MOVE statements translate
        assert not any(h.startswith(f"line {line}:") for h in r.stats["holes"])
    assert "DetCics.advancePointer(task, " in r.java and "DetCics.copyPointer(" in r.java


@pytest.mark.parametrize("program", ["ZECS000", "ZECS003"])
def test_zecs_file_name_template_programs_translate_whole_and_name_the_run_time_hole(tmp_path, program):
    """#4771: ZECS000 / ZECS003 name their file by a data item (ZF-FCT, ZC##FILE): no translation-time hole is left, and
    the file the project does not store is a named Hole at run time, never a silent miss."""
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    src = Path(root) / f"zecs/Source/{program}.cbl" if root else None
    if src is None or not src.is_file():
        pytest.skip("needs the zecs corpus (GITGALAXY_MAINFRAME_CORPORA)")
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = f"package com.x.service;\nimport com.x.cics.CicsTask;\npublic class {program.title()}Service {{\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(src, [], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == []
    assert "the program names no file the generated project stores" in r.java


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_an_advanced_pointer_addresses_the_same_block_further_on(tmp_path):
    """#4771 (X47): DetCics.advancePointer / copyPointer over a real CicsTask. A record set to the advanced pointer is a
    window on the block from that offset (a write through either is seen by both), going back to the start gives the
    pointer the block's first handle again, and a result outside the block, a null or a freed pointer is refused by name."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import t.cics.CicsTask;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetCics;
public class Main {
    static Field rec(int n) { return Field.alphanumeric(new Storage(n), 0, n, false); }
    static String text(Field f) { return new String(f.storage().bytes, java.nio.charset.StandardCharsets.ISO_8859_1); }
    static void refused(Runnable r) {
        try { r.run(); System.out.println("not refused"); } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
    }
    public static void main(String[] a) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        Field ptr = rec(8), save = rec(8), init = rec(1), whole = rec(10), tail = rec(6);
        init.storage().bytes[0] = '.';
        DetCics.getmain(t, ptr, 10, false, init);
        DetCics.setAddress(t, whole, ptr);
        System.arraycopy("ABCDEFGHIJ".getBytes(), 0, whole.storage().bytes, 0, 10);
        DetCics.copyPointer(save, ptr);
        System.out.println(DetCics.samePointer(t, save, ptr));
        DetCics.advancePointer(t, ptr, 4);
        System.out.println(DetCics.samePointer(t, save, ptr));
        DetCics.setAddress(t, tail, ptr);
        System.out.println(text(tail).substring(tail.storage().base, tail.storage().base + 6));
        tail.storage().bytes[tail.storage().base] = 'x';
        System.out.println(text(whole));
        DetCics.advancePointer(t, ptr, 6);
        refused(() -> DetCics.advancePointer(t, ptr, 1));
        DetCics.advancePointer(t, ptr, -10);
        System.out.println(DetCics.samePointer(t, save, ptr));
        refused(() -> DetCics.advancePointer(t, ptr, -1));
        refused(() -> DetCics.advancePointer(t, rec(8), 1));
        t.freemain(DetCics.pointerValue(save));
        refused(() -> DetCics.advancePointer(t, save, 1));
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
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "true",
        "false",
        "EFGHIJ",
        "ABCDxFGHIJ",
        "pointer arithmetic leaves the storage the pointer addresses (11 of 10 bytes)",
        "true",
        "pointer arithmetic leaves the storage the pointer addresses (-1 of 10 bytes)",
        "SET ADDRESS OF a null or unknown pointer: not modelled",
        "SET ADDRESS OF storage already freed: not modelled",
    ]


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_zuidstck_fills_the_tod_from_the_run_and_refuses_when_it_is_not_stated(tmp_path):
    """#5945 (X47): CALL ZUIDSTCK's 16 bytes are the run's stated $GGC_ZUIDSTCK_TOD, whatever they are (two different TODs
    give two different THE-TOD(1:6) key prefixes); an unstated, short, non-hex or wrongly sized TOD is refused by name."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    assert "t/cobolrt/le/Zuidstck.java" in files
    files["Main.java"] = """
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.le.Zuidstck;
public class Main {
    public static void main(String[] a) {
        Field tod = Field.alphanumeric(new Storage(16), 0, 16, false);
        try {
            Zuidstck.call(tod);
            StringBuilder sb = new StringBuilder();
            for (byte b : tod.storage().bytes) sb.append(String.format("%02X", b));
            System.out.println(sb);
            Zuidstck.call(Field.alphanumeric(new Storage(8), 0, 8, false));
        } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
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

    def run(tod: str | None) -> list[str]:
        env = {k: v for k, v in os.environ.items() if k != "GGC_ZUIDSTCK_TOD"}
        if tod is not None:
            env["GGC_ZUIDSTCK_TOD"] = tod
        return subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                              capture_output=True, text=True, encoding="utf-8", check=True, env=env).stdout.splitlines()  # fmt: skip

    refusal = "ZUIDSTCK: a TOD the run does not state ($GGC_ZUIDSTCK_TOD, 32 hexadecimal digits) is not modelled"
    wrong_size = "ZUIDSTCK: a 16-byte TOD item expected (got 8)"
    one, two = "00112233445566778899AABBCCDDEEFF", "D5E3F1F2F3F4F5F6000000000000000A"
    assert run(one) == [one, wrong_size]
    assert run(two.lower()) == [two, wrong_size]  # (any 16 bytes: the program never reads them as a time)
    for bad in (None, "", one[:-2], one + "00", "ZZ" + one[2:]):
        assert run(bad) == [refusal], bad


_BYTE_VIEW_HEAD = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PTR                 POINTER.
       01  WS-PTR-X REDEFINES WS-PTR PIC X(4).
       01  WS-OUT                 PIC X(8) VALUE SPACES.
       01  WS-NUM                 PIC S9(8) COMP VALUE 0.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(8).
       01  LS-VIEW                PIC X(8).
       PROCEDURE DIVISION.
           EXEC CICS ADDRESS COMMAREA(WS-PTR)
           END-EXEC.
"""


def test_a_pic_x4_byte_view_tested_against_the_no_commarea_address_translates_whole(tmp_path):
    """#6876 (X59), CAADDR / CAADSB / CAEBCA / CAEBSB: `IF WS-PTR-X = X'FF000000'` after ADDRESS COMMAREA, then SET ADDRESS OF
    a view TO the pointer. The test goes to the runtime (the handle's bytes are never compared); both spellings of the
    relation (literal on either side, NOT =) translate, and the pointer's own statements are no longer refused."""
    body = (
        "           IF WS-PTR-X = X'FF000000'\n               MOVE 'ABSENT' TO WS-OUT\n"
        "           ELSE\n               MOVE 'PRESENT' TO WS-OUT\n"
        "               SET ADDRESS OF LS-VIEW TO WS-PTR\n           END-IF.\n"
        "           IF X'FF000000' NOT = WS-PTR-X\n               MOVE 'P' TO WS-OUT\n           END-IF.\n"
        "           EXEC CICS RETURN END-EXEC.\n"
    )
    r = _translate(tmp_path, _BYTE_VIEW_HEAD + body)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.java.count("DetCics.isNoCommareaAddress(") == 2
    assert "DetCics.setAddress(task, " in r.java


@pytest.mark.parametrize(
    "statement",
    [
        "MOVE WS-PTR-X TO WS-OUT.",  # the handle's bytes
        "MOVE 'ABCD' TO WS-PTR-X.",
        "IF WS-PTR-X = 'ABCD' MOVE 'Y' TO WS-OUT END-IF.",
        "IF WS-PTR-X = LOW-VALUES MOVE 'Y' TO WS-OUT END-IF.",
        "IF WS-PTR-X > X'FF000000' MOVE 'Y' TO WS-OUT END-IF.",
        "IF WS-PTR-X (1:1) = X'FF' MOVE 'Y' TO WS-OUT END-IF.",
    ],
)
def test_any_other_use_of_a_pointer_byte_view_is_a_hole(tmp_path, statement):
    source = _BYTE_VIEW_HEAD + "           " + statement + "\n           EXEC CICS RETURN END-EXEC.\n"
    r = _translate(tmp_path, source)
    assert any("REDEFINES overlays a POINTER" in h or "pointer byte view" in h for h in r.stats["holes"]), r.stats[
        "holes"
    ]
    assert r.stats["translated"] < r.stats["statements"]


def test_a_byte_view_of_the_wrong_width_or_shared_with_another_overlay_stays_refused(tmp_path):
    for old, new in (
        ("PIC X(4).", "PIC X(8)."),  # not the pointer's width
        ("PIC X(4).", "PIC X(4).\n       01  WS-PTR-N REDEFINES WS-PTR PIC S9(8) COMP."),  # a second overlay
    ):
        source = _BYTE_VIEW_HEAD.replace(old, new, 1) + (
            "           IF WS-PTR-X = X'FF000000' MOVE 'A' TO WS-OUT END-IF.\n           EXEC CICS RETURN END-EXEC.\n"
        )
        r = _translate(tmp_path, source)
        assert r.stats["holes"], (new, "must stay a hole")
