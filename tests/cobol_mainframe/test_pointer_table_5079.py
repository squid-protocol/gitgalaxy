"""#5079 (oracle_assumptions.md X47): the pointer table -- a USAGE POINTER under OCCURS, a list of handles in a block.

WAIT EXTERNAL / WAITCICS take an ECBLIST, a list of addresses held as bytes (IBM: "a pointer to a list of addresses of
MVS-format ECBs"), which the pointer lane could not hold while a POINTER under an OCCURS was refused. Each element is a
pointer of its own (an 8-byte handle, as any other); the whole class, over the translator and the runtime:
- SET element TO ADDRESS OF record / item, SET ADDRESS OF record TO element, SET element TO NULL, GETMAIN SET(element),
  FREEMAIN DATAPOINTER(element), for a table, a table inside a group and a table of groups, with a literal and a data-name
  subscript;
- refused by name: a table named without its subscripts (it would silently be its first element), the wrong number of
  subscripts, ADDRESS OF a table element, a table a REDEFINES overlays;
- the runtime: elements are independent slots, a NULL element leaves the record where it was, a freed element is refused.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import test_pointer_lane_4771 as PL  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

TABLE = """\
       01  ECB-LIST.
           02  ECB-ENT            USAGE POINTER OCCURS 3 TIMES.
       01  ECB-I                  PIC S9(04) COMP VALUE 2.
"""
GROUPED = """\
       01  ECB-LIST.
           02  ECB-ROW OCCURS 2 TIMES.
               03  ECB-ENT        USAGE POINTER OCCURS 3 TIMES.
       01  ECB-I                  PIC S9(04) COMP VALUE 2.
"""


def _program(statements: str, data: str = TABLE) -> str:
    source = PL.PROGRAM.replace("       01  ELEMENT-TABLE.", data + "       01  ELEMENT-TABLE.", 1)
    wrapped = textwrap.wrap(
        statements, 54, break_on_hyphens=False, break_long_words=False
    )  # fixed form reads columns 8-72 only: wrap at word boundaries
    body = "".join(f"           {w}\n" if i == 0 else f"               {w}\n" for i, w in enumerate(wrapped))
    return source.replace("           EXEC CICS RETURN END-EXEC.", body + "           EXEC CICS RETURN END-EXEC.")


@pytest.mark.parametrize(
    ("data", "statement", "call"),
    [
        (TABLE, "SET ECB-ENT(1) TO ADDRESS OF OTHER-MESSAGE.", "DetCics.setPointerToRecord(task, f"),
        (TABLE, "SET ECB-ENT(ECB-I) TO ADDRESS OF OTHER-MESSAGE.", "DetCics.setPointerToRecord(task, f"),
        (TABLE, "SET ECB-ENT(ECB-I) TO ADDRESS OF WEB-MEDIA-TYPE.", "DetCics.setPointerToItem(task, f"),
        (TABLE, "SET ADDRESS OF OTHER-MESSAGE TO ECB-ENT(3).", "DetCics.setAddress(task, f"),
        (TABLE, "SET ADDRESS OF OTHER-MESSAGE TO ECB-ENT(ECB-I).", "DetCics.setAddress(task, f"),
        (TABLE, "SET ECB-ENT(2) TO NULL.", "Cobol.moveFigurative(Figurative.LOW_VALUES, f"),
        (TABLE, "SET ECB-ENT(1) ECB-ENT(2) TO NULL.", "Cobol.moveFigurative(Figurative.LOW_VALUES, f"),
        (
            TABLE,
            "EXEC CICS GETMAIN SET(ECB-ENT(2)) FLENGTH(GETMAIN-LENGTH) INITIMG(BINARY-ZEROES) NOHANDLE END-EXEC.",
            "DetCics.getmain(task, f",
        ),
        (
            TABLE,
            "EXEC CICS FREEMAIN DATAPOINTER(ECB-ENT(ECB-I)) NOHANDLE END-EXEC.",
            "task.freemain(DetCics.pointerValue(",
        ),
        (GROUPED, "SET ECB-ENT(2, 3) TO ADDRESS OF OTHER-MESSAGE.", "DetCics.setPointerToRecord(task, f"),
        (GROUPED, "SET ADDRESS OF OTHER-MESSAGE TO ECB-ENT(ECB-I, 1).", "DetCics.setAddress(task, f"),
        (GROUPED, "SET ECB-ENT(1, 1) TO NULL.", "Cobol.moveFigurative(Figurative.LOW_VALUES, f"),
    ],
)
def test_a_pointer_table_element_is_a_pointer_of_its_own(tmp_path, data, statement, call):
    r = PL._translate(tmp_path, _program(statement, data))
    assert r.stats["holes"] == [], r.stats["holes"]
    assert call in r.java
    assert ".at(" in r.java  # the element, never the table's first occurrence


@pytest.mark.parametrize(
    ("data", "statement", "why"),
    [
        (TABLE, "SET ECB-ENT TO ADDRESS OF OTHER-MESSAGE.", "pointer table named without its subscripts"),
        (TABLE, "SET ADDRESS OF OTHER-MESSAGE TO ECB-ENT.", "pointer table named without its subscripts"),
        (TABLE, "SET ECB-ENT TO NULL.", "pointer table named without its subscripts"),
        (
            TABLE,
            "EXEC CICS FREEMAIN DATAPOINTER(ECB-ENT) NOHANDLE END-EXEC.",
            "pointer table named without its subscripts",
        ),
        (GROUPED, "SET ECB-ENT(2) TO ADDRESS OF OTHER-MESSAGE.", "not a plain USAGE POINTER item"),
        (TABLE, "SET ECB-ENT(1, 2) TO ADDRESS OF OTHER-MESSAGE.", "not a plain USAGE POINTER item"),
        (TABLE, "SET ADDRESS OF OTHER-MESSAGE TO ADDRESS OF ECB-ENT(2).", "a table element"),
        (TABLE, "SET ECB-ENT(1) TO ADDRESS OF ECB-ENT(2).", "SET ADDRESS OF (pointers)"),
    ],
)
def test_what_a_pointer_table_cannot_model_is_refused_by_name(tmp_path, data, statement, why):
    r = PL._translate(tmp_path, _program(statement, data))
    assert r.stats["holes"], "a statement the lane cannot model must be a hole, never silently translated"
    assert any(why in h for h in r.stats["holes"]), (why, r.stats["holes"])


def test_a_pointer_table_a_redefines_overlays_is_refused(tmp_path):
    data = TABLE + "       01  ECB-BYTES REDEFINES ECB-LIST PIC X(24).\n"
    r = PL._translate(tmp_path, _program("SET ECB-ENT(1) TO ADDRESS OF OTHER-MESSAGE.", data))
    assert any("REDEFINES overlays" in h for h in r.stats["holes"]), r.stats["holes"]


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_elements_of_a_pointer_table_are_independent_handles(tmp_path):
    """DetCics over a table Field of three 8-byte elements, as the translator addresses them (`.at(i, 8)`): each element
    holds its own block, a record set to one sees that block only, a NULL element leaves the record as it was, a
    freed element is refused, and a group MOVE of the table copies the handles (two tables then name the same blocks)."""
    pytest.importorskip("tree_sitter_language_pack")
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
    static String text(Field f) { return new String(f.storage().bytes, java.nio.charset.StandardCharsets.ISO_8859_1).replace('\\0', '.'); }
    static void refused(Runnable r) {
        try { r.run(); System.out.println("not refused"); } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
    }
    public static void main(String[] a) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        Storage tab = new Storage(24);
        Field table = Field.group(tab, 0, 8);
        Field init1 = rec(1), init2 = rec(1);
        init1.storage().bytes[0] = 'A';
        init2.storage().bytes[0] = 'B';
        DetCics.getmain(t, table.at(1, 8), 3, false, init1);
        DetCics.getmain(t, table.at(2, 8), 2, false, init2);
        Field r1 = rec(3), r2 = rec(2);
        DetCics.setAddress(t, r1, table.at(1, 8));
        DetCics.setAddress(t, r2, table.at(2, 8));
        System.out.println(text(r1) + " " + text(r2));
        System.out.println(DetCics.pointerValue(table.at(3, 8)) + " " + (DetCics.pointerValue(table.at(1, 8)) != DetCics.pointerValue(table.at(2, 8))));
        DetCics.setPointerToRecord(t, table.at(3, 8), r1);
        Field r3 = rec(3);
        DetCics.setAddress(t, r3, table.at(3, 8));
        r3.storage().bytes[0] = 'z';
        System.out.println(text(r1) + " " + (r1.storage().bytes == r3.storage().bytes));
        Storage copy = new Storage(24);
        System.arraycopy(tab.bytes, 0, copy.bytes, 0, 24);
        Field table2 = Field.group(copy, 0, 8);
        Field r4 = rec(2);
        DetCics.setAddress(t, r4, table2.at(2, 8));
        System.out.println(text(r4) + " " + (r4.storage().bytes == r2.storage().bytes));
        DetCics.setPointer(table.at(1, 8), 0);
        Field r5 = rec(3);
        byte[] before = r5.storage().bytes;
        DetCics.setAddress(t, r5, table.at(1, 8));
        System.out.println(r5.storage().bytes == before ? "null element: record unchanged" : "record moved");
        int[] f = t.freemain(DetCics.pointerValue(table.at(2, 8)));
        System.out.println("free: " + f[0] + "/" + f[1]);
        refused(() -> DetCics.setAddress(t, rec(2), table.at(2, 8)));
        refused(() -> table.at(4, 8));
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    assert jdk is not None
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "AAA BB",
        "0 true",
        "zAA true",
        "BB true",
        "null element: record unchanged",
        "free: 0/0",
        "SET ADDRESS OF storage already freed: not modelled",
        "not refused",
    ], out
