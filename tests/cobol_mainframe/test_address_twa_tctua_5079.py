"""#5079 (oracle_assumptions.md X59): the facts and runtime under EXEC CICS ADDRESS TWA / TCTUA (slice 1; the spec models them since slice 2).

IBM, EXEC CICS ADDRESS: TWA "returns a pointer reference set to the address of the transaction work area (TWA)", TCTUA the
terminal control table user area. The sizes are definitions: TRANSACTION TWASIZE(n), TYPETERM USERAREALEN(n). The pieces, each
over the whole input class:
- parse_csd: TWASIZE per transaction, USERAREALEN per terminal (through the TERMINAL's TYPETERM); lowercase, a DEFINE that
  continues on following lines, a size of 0, and a CSD with neither (no key at all: an always-present empty key breaks
  exact-equality tests);
- the runtime (CicsTask + DetCics, compiled): a TWA of TWASIZE bytes shared by the task and every program it LINKs to; a TCTUA
  that outlives the task; an area of size 0 or unstated gives X'FF000000'.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
import cics_crucible_compare as cc  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

CSD = """\
* a comment line TWASIZE(99) must not count
DEFINE TYPETERM(CRU3278) GROUP(G)
       DEVICE(3270) USERAREALEN(16)
DEFINE TYPETERM(NOAREA) GROUP(G) DEVICE(3270)
DEFINE TERMINAL(T001) TYPETERM(CRU3278) GROUP(G)
DEFINE TERMINAL(T002) TYPETERM(NOAREA) GROUP(G)
DEFINE TRANSACTION(CA0H) PROGRAM(CATWAD) GROUP(G)
       TWASIZE(32)
define transaction(ca0i) program(catwad) group(g) twasize( 0 )
DEFINE TRANSACTION(CA0J) PROGRAM(CATWAD) GROUP(G)
"""


def test_parse_csd_reads_twasize_per_transaction_and_userarealen_per_terminal():
    csd = cc.parse_csd(CSD)
    assert csd["twasize"] == {"CA0H": 32, "CA0I": 0}  # CA0J states none: no entry
    assert csd["userarealen"] == {"T001": 16}  # T002's TYPETERM states none


def test_parse_csd_adds_neither_key_when_the_csd_states_no_area():
    csd = cc.parse_csd("DEFINE TRANSACTION(CA0J) PROGRAM(CATWAD)\nDEFINE TERMINAL(T001) TYPETERM(X)\n")
    assert "twasize" not in csd
    assert "userarealen" not in csd


def test_parse_csd_ignores_a_userarealen_on_a_terminal_whose_typeterm_is_not_defined():
    assert "userarealen" not in cc.parse_csd("DEFINE TERMINAL(T001) TYPETERM(GONE)\n")


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_port_shares_the_twa_across_link_and_the_tctua_across_tasks_and_gives_null_for_no_area(tmp_path):
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
    static Field ptr() { return Field.alphanumeric(new Storage(8), 0, 8, false); }
    static byte[] callee = null;
    public static void main(String[] a) {
        // the TWA: the task and the program it LINKs to address the same 32 bytes
        CicsTask t = new CicsTask("CA0H", "ENTER", null, null).withTwaSize(32);
        Field p1 = ptr(), p2 = ptr();
        DetCics.addressTwa(t, p1);
        DetCics.addressTwa(t, p2);
        System.out.println(DetCics.pointerValue(p1) == DetCics.pointerValue(p2) && !DetCics.isNoCommareaAddress(p1));
        Field seen = ptr();
        t.withPrograms(new CicsTask.Programs() {
            public boolean defined(String program) { return true; }
            public void run(String program, CicsTask task) { DetCics.addressTwa(task, seen); }
        });
        t.link("CATWSB");
        System.out.println(DetCics.pointerValue(seen) == DetCics.pointerValue(p1));
        // size 0 and unstated: X'FF000000'
        for (CicsTask n : new CicsTask[] {new CicsTask("CA0I", "ENTER", null, null).withTwaSize(0),
                                          new CicsTask("CA0J", "ENTER", null, null)}) {
            Field p = ptr();
            DetCics.addressTwa(n, p);
            DetCics.addressTctua(n, ptr());
            System.out.println(DetCics.isNoCommareaAddress(p));
        }
        // the TCTUA: the terminal's bytes, written by one task and found by the next
        byte[] area = new byte[16];
        CicsTask first = new CicsTask("CA0K", "ENTER", null, null).withTctua(area);
        Field f1 = ptr();
        DetCics.addressTctua(first, f1);
        CicsTask second = new CicsTask("CA0K", "ENTER", null, null).withTctua(area);
        Field f2 = ptr();
        DetCics.addressTctua(second, f2);
        System.out.println(!DetCics.isNoCommareaAddress(f1) && !DetCics.isNoCommareaAddress(f2));
        Field none = ptr();
        DetCics.addressTctua(new CicsTask("CA0K", "ENTER", null, null).withTctua(new byte[0]), none);
        System.out.println(DetCics.isNoCommareaAddress(none));
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
    assert out == ["true", "true", "true", "true", "true", "true"]
