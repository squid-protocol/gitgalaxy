"""#5079 (oracle_assumptions.md X59): the runtime under EXEC CICS ADDRESS CWA (slice 1; the spec models it since slice 2a).

IBM, EXEC CICS ADDRESS: CWA "returns a pointer reference set to the address of the common work area (CWA)"; its size is the
SIT's WRKAREA, one area for the region. Over the whole input class (CicsTask + DetCics, compiled):
- a CWA of WRKAREA bytes shared by a task, the programs it LINKs to, and every other task of the region;
- a size of 0 or none stated gives X'FF000000';
- the plan the crucible runner hands the Java side carries `wrkarea` only when the case states it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_port_shares_the_cwa_across_link_and_tasks_and_gives_null_for_no_area(tmp_path):
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
    public static void main(String[] a) {
        byte[] area = new byte[64];  // the region's CWA: the caller keeps one array for every task
        CicsTask t = new CicsTask("CA0H", "ENTER", null, null).withCwa(area);
        Field p1 = ptr(), p2 = ptr();
        DetCics.addressCwa(t, p1);
        DetCics.addressCwa(t, p2);
        System.out.println(DetCics.pointerValue(p1) == DetCics.pointerValue(p2) && !DetCics.isNoCommareaAddress(p1));
        Field seen = ptr();
        t.withPrograms(new CicsTask.Programs() {
            public boolean defined(String program) { return true; }
            public void run(String program, CicsTask task) { DetCics.addressCwa(task, seen); }
        });
        t.link("CACWSB");  // a LINKed program sees the same bytes
        System.out.println(DetCics.pointerValue(seen) == DetCics.pointerValue(p1));
        Field other = ptr();  // another task of the region
        DetCics.addressCwa(new CicsTask("CA0I", "ENTER", null, null).withCwa(area), other);
        System.out.println(DetCics.pointerValue(other) == DetCics.pointerValue(p1));
        // size 0, empty and unstated: X'FF000000'
        for (CicsTask n : new CicsTask[] {new CicsTask("CA0J", "ENTER", null, null).withCwa(new byte[0]),
                                          new CicsTask("CA0K", "ENTER", null, null).withCwa(null),
                                          new CicsTask("CA0L", "ENTER", null, null)}) {
            Field p = ptr();
            DetCics.addressCwa(n, p);
            System.out.println(DetCics.isNoCommareaAddress(p));
        }
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
