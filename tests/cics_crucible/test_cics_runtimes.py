"""#3989 phase 3: the two CICS runtimes the crucible drives, run directly -- no GnuCOBOL, no Maven.

* The stub runtime (tests/equivalence/cics/ggcics.c) is compiled with a C compiler and called the way a
  translated program calls it (the GG-CICS block first).
* The generated CicsTask (the transaction forge's CICS_TASK_JAVA) is compiled with javac and driven by a
  small main.

Each pins a CICS semantic the crucible's cases lean on, as IBM documents it (cited per test).
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
STUB = TESTS / "equivalence" / "cics" / "ggcics.c"
sys.path.insert(0, str(TESTS / "tools"))

CC = shutil.which("cc") or shutil.which("gcc")
needs_cc = pytest.mark.skipif(CC is None, reason="needs a C compiler")
needs_javac = pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")

_STUB_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; } gg_cics;
int GGCRECT(gg_cics *c, char *into);
int main(int argc, char **argv) {
    gg_cics c;
    char into[64];
    memset(&c, 0, sizeof c);
    for (int i = 1; i < argc; i++) {
        memset(into, '.', sizeof into);
        c.len = atoi(argv[i]);
        GGCRECT(&c, into);
        printf("resp=%d len=%d into=%.8s\n", c.resp, c.len, into);
    }
    return 0;
}
"""


def _stub(tmp_path: Path, main: str) -> Path:
    src = tmp_path / "main.c"
    src.write_text("#include <stdlib.h>\n" + main, encoding="ascii")
    exe = tmp_path / "stub"
    subprocess.run([CC, "-o", str(exe), str(src), str(STUB)], check=True, capture_output=True)  # noqa: S603
    return exe


def _run_stub(exe: Path, work: Path, *args: str) -> list[str]:
    (work / "out").mkdir(parents=True, exist_ok=True)
    env = {"GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out"), "PATH": "/usr/bin:/bin"}
    proc = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    return proc.stdout.splitlines()


# ---- #4005: terminal RECEIVE -------------------------------------------------------------------------
@needs_cc
def test_the_stub_receive_returns_the_typed_text_once_and_truncates_with_lengerr(tmp_path):
    """IBM, EXEC CICS RECEIVE: data longer than LENGTH "is truncated to that value and the LENGERR
    condition occurs. The data area specified in the LENGTH option is set to the original length of
    data." The terminal's input is read once; a second RECEIVE would wait for the operator."""
    exe = _stub(tmp_path, _STUB_MAIN)
    (tmp_path / "terminal.in").write_bytes(b"CA02 S")
    assert _run_stub(exe, tmp_path, "20", "20") == ["resp=0 len=6 into=CA02 S..", "resp=0 len=0 into=........"]
    assert (tmp_path / "out" / "events.txt").read_text().splitlines() == ["001 RECEIVE resp=0 len=6 copied=6",
                                                                          "002 RECEIVE-WAIT"]  # fmt: skip
    assert (tmp_path / "out" / "001.bin").read_bytes() == b"CA02 S"

    short = tmp_path / "short"
    short.mkdir()
    (short / "terminal.in").write_bytes(b"CA02 S")
    assert _run_stub(exe, short, "4") == ["resp=22 len=6 into=CA02...."]
    assert (short / "out" / "001.bin").read_bytes() == b"CA02"

    nothing = tmp_path / "nothing"  # a step that transmitted no data (ENTER on a SEND TEXT screen)
    nothing.mkdir()
    assert _run_stub(exe, nothing, "20") == ["resp=0 len=0 into=........"]
    read = tmp_path / "read"  # an earlier program of the task (before an XCTL) already read it
    read.mkdir()
    (read / "terminal.in").write_bytes(b"CA02 S")
    (read / "terminal.read").write_bytes(b"")
    assert _run_stub(exe, read, "20") == ["resp=0 len=0 into=........"]
    assert (read / "out" / "events.txt").read_text() == "001 RECEIVE-WAIT\n"


# ---- the generated CicsTask ------------------------------------------------------------------------------
def _cics_task(tmp_path: Path, main_body: str) -> str:
    """Compile the generated CicsTask with a main whose body is `main_body`; its stdout."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA

    pkg = tmp_path / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    (pkg / "CicsTask.java").write_text(CICS_TASK_JAVA.replace("__PACKAGE__", "t"), encoding="utf-8")
    (pkg / "Main.java").write_text("package t.cics;\n\npublic class Main {\n    public static void main(String[] a) {\n"
                                   + main_body + "\n    }\n}\n", encoding="utf-8")  # fmt: skip
    classes = tmp_path / "classes"
    subprocess.run(["javac", "-d", str(classes), *map(str, pkg.glob("*.java"))], check=True,  # noqa: S603, S607
                   capture_output=True)  # fmt: skip
    proc = subprocess.run(["java", "-cp", str(classes), "t.cics.Main"], capture_output=True, text=True,  # noqa: S603, S607
                          check=True)  # fmt: skip
    return proc.stdout


@needs_javac
def test_cics_task_receive_text_records_the_event_and_truncates_with_lengerr(tmp_path):
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("CA02", "ENTER", null, null).withTerminalInput("CA02 S");
        System.out.println(t.receiveText(20));
        CicsTask s = new CicsTask("CA02", "ENTER", null, null).withTerminalInput("CA02 S");
        System.out.println(s.receiveText(4));
        try {
            s.receiveText(20);
        } catch (IllegalStateException e) {
            System.out.println("waits");
        }
        CicsTask n = new CicsTask("CA02", "ENTER", null, null);
        System.out.println(n.receiveText(20));
        System.out.println(t.events());
        System.out.println(s.events());""",
    )
    assert out.splitlines() == [
        "Received[resp=NORMAL, length=6, data=CA02 S]",
        "Received[resp=LENGERR, length=6, data=CA02]",
        "waits",
        "Received[resp=NORMAL, length=0, data=]",
        "[{event=RECEIVE, resp=NORMAL, length=6, data=CA02 S}]",
        "[{event=RECEIVE, resp=LENGERR, length=6, data=CA02}]",
    ]
    assert re.search(
        r"public Received receiveText\(int maxLength\)", (tmp_path / "src/t/cics/CicsTask.java").read_text()
    )
