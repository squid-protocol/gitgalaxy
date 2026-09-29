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
def test_cics_task_ts_queues_follow_readq_and_writeq(tmp_path):
    out = _cics_task(
        tmp_path,
        """
        CicsTask.TempStorage ts = new CicsTask.TempStorage().seed("Q1", java.util.List.of(new byte[] {1, 2, 3}));
        CicsTask t = new CicsTask("HC01", "ENTER", null, null).withTempStorage(ts);
        CicsTask.TsResult r = t.readqTs("Q1", 1, 2);
        System.out.println(r.resp() + " " + r.length() + " " + r.data().length + " " + r.numItems());
        System.out.println(t.readqTs("NONE", 1, 8).resp() + " " + t.readqTsNext("Q1", 8).resp());
        System.out.println(t.writeqTs("Q2", new byte[] {9}).item() + " " + t.rewriteqTs("Q2", 3, new byte[] {9}).resp());
        CicsTask u = new CicsTask("HC01", "ENTER", null, null).withTempStorage(ts);
        System.out.println(u.readqTs("Q2", 1, 8).resp() + " " + ts.queues().keySet());
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println(e.get("event") + " " + e.get("queue") + " " + e.get("item") + " " + e.get("resp") + " "
                    + e.get("length"));
        }""",
    )
    assert out.splitlines() == [
        "LENGERR 3 2 1",
        "QIDERR ITEMERR",
        "1 ITEMERR",
        "NORMAL [Q1, Q2]",
        "READQ-TS Q1 1 LENGERR 3",
        "READQ-TS NONE 1 QIDERR null",
        "READQ-TS Q1 NEXT ITEMERR null",
        "WRITEQ-TS Q2 1 NORMAL null",
        "WRITEQ-TS Q2 null ITEMERR null",
    ]


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


# ---- #4002: temporary storage -----------------------------------------------------------------------
_TS_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; } gg_cics;
int GGCREADQ(gg_cics *c, char *into);
int GGCWRTQ(gg_cics *c, char *from);
/* argv: ops like R:Q:item:len (item 0 = NEXT), W:Q:data, X:Q:item:data (REWRITE) */
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        gg_cics c;
        char into[64], q[17], data[64];
        int item = 0, len = 0;
        memset(&c, 0, sizeof c);
        memset(into, '.', sizeof into);
        char op = argv[i][0];
        if (op == 'R') { sscanf(argv[i] + 2, "%16[^:]:%d:%d", q, &item, &len); }
        else if (op == 'W') { sscanf(argv[i] + 2, "%16[^:]:%63s", q, data); len = (int)strlen(data); }
        else { sscanf(argv[i] + 2, "%16[^:]:%d:%63s", q, &item, data); len = (int)strlen(data); }
        memset(c.qname, ' ', 16);
        memcpy(c.qname, q, strlen(q));
        memset(c.flags, ' ', 40);
        c.item = item;
        c.len = len;
        if (op == 'R') {
            GGCREADQ(&c, into);
            printf("resp=%d len=%d num=%d into=%.6s\n", c.resp, c.len, c.num, into);
        } else {
            if (op == 'X') memcpy(c.flags, "REWRITE", 7);
            GGCWRTQ(&c, data);
            printf("resp=%d item=%d num=%d\n", c.resp, c.item, c.num);
        }
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_ts_queues_follow_readq_and_writeq(tmp_path):
    """IBM, EXEC CICS READQ TS / WRITEQ TS: QIDERR for a missing queue, ITEMERR outside it (and NEXT past
    its end), LENGERR truncating to LENGTH with LENGTH set to the item's length; WRITEQ creates the queue
    and returns the item number; REWRITE replaces an item."""
    exe = _stub(tmp_path, _TS_MAIN)
    got = _run_stub(exe, tmp_path, "R:Q1:1:8", "W:Q1:HELLO", "W:Q1:AB", "R:Q1:1:8", "R:Q1:1:3", "R:Q1:3:8",
                    "R:Q1:0:8", "R:Q1:0:8", "X:Q1:2:XY", "X:Q1:5:XY", "X:NOPE:1:XY", "R:Q1:2:8")  # fmt: skip
    assert got == [
        "resp=44 len=8 num=0 into=......",  # QIDERR, LENGTH untouched
        "resp=0 item=1 num=1",
        "resp=0 item=2 num=2",
        "resp=0 len=5 num=2 into=HELLO.",
        "resp=22 len=5 num=2 into=HEL...",  # LENGERR: truncated, LENGTH = the item's length (the translator
        # moves NUMITEMS back on NORMAL only)
        "resp=26 len=8 num=0 into=......",  # ITEMERR
        "resp=0 len=2 num=2 into=AB....",  # NEXT after the read of item 1
        "resp=26 len=8 num=0 into=......",  # NEXT past the end
        "resp=0 item=2 num=2",
        "resp=26 item=5 num=0",
        "resp=44 item=1 num=0",
        "resp=0 len=2 num=2 into=XY....",
    ]
    events = (tmp_path / "out" / "events.txt").read_text().splitlines()
    assert events[0] == "001 READQ-TS queue=5131 item=1 resp=44 len=-1 copied=0"
    assert events[4] == "005 READQ-TS queue=5131 item=1 resp=22 len=5 copied=3"
    assert events[6] == "007 READQ-TS queue=5131 item=NEXT resp=0 len=2 copied=2"
    assert events[1] == "002 WRITEQ-TS queue=5131 item=1 resp=0 len=5"
    assert (tmp_path / "ts" / "5131" / "000002.bin").read_bytes() == b"XY"
