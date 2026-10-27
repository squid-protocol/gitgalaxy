"""#3989 phase 3: the two CICS runtimes the crucible drives, run directly -- no GnuCOBOL, no Maven.

* The stub runtime (tests/equivalence/cics/ggcics.c) is compiled with a C compiler and called the way a
  translated program calls it (the GG-CICS block first).
* The generated CicsTask (the transaction forge's CICS_TASK_JAVA) is compiled with javac and driven by a
  small main.

Each pins a CICS semantic the crucible's cases lean on, as IBM documents it (cited per test).
"""

import atexit
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
STUB = TESTS / "equivalence" / "cics" / "ggcics.c"
sys.path.insert(0, str(TESTS / "tools"))

CC = shutil.which("cc") or shutil.which("gcc")
needs_cc = pytest.mark.skipif(CC is None, reason="needs a C compiler")
needs_javac = pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
javac = (
    shutil.which("javac") or "javac"
)  # PATH's javac by its path: tests/tools/javac_server.py serves only an absolute one
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

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


@functools.cache
def _stub_obj() -> Path:
    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-ggcics-obj-"))
    atexit.register(shutil.rmtree, base, True)
    obj = base / "ggcics.o"
    built = subprocess.run([CC, "-c", str(STUB), "-o", str(obj)], check=False, capture_output=True, text=True)  # noqa: S603
    assert built.returncode == 0, built.stderr
    return obj


_GG_CICS_TYPEDEF = re.compile(r"typedef struct \{[^}]*\} gg_cics;")


@functools.cache
def _stub_struct() -> str:
    """The stub's own `gg_cics` typedef, read from ggcics.c."""
    found = _GG_CICS_TYPEDEF.search(STUB.read_text(encoding="utf-8"))
    assert found, "ggcics.c no longer declares `typedef struct {...} gg_cics;`"
    return found.group(0)


def _with_stub_struct(main: str) -> str:
    """#6430: a main's own shorter `gg_cics` typedef is replaced by the stub's. A stub function that writes a field past
    the main's copy (GGCLINK's `go_to`, #6400) overran the main's stack struct, which crashed on macOS only."""
    return _GG_CICS_TYPEDEF.sub(lambda _m: _stub_struct(), main)


@functools.cache
def _compiled_stub(main: str) -> Path:
    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-ggcics-exe-"))
    atexit.register(shutil.rmtree, base, True)
    src = base / "main.c"
    src.write_text("#include <stdlib.h>\n" + _with_stub_struct(main), encoding="ascii")
    exe = base / ("stub.exe" if os.name == "nt" else "stub")
    built = subprocess.run(
        [CC, "-o", str(exe), str(src), str(_stub_obj())], check=False, capture_output=True, text=True
    )  # noqa: S603
    assert built.returncode == 0, built.stderr  # the compiler's own words, on every OS
    return exe


def test_every_stub_main_is_compiled_against_the_stubs_own_gg_cics_struct():
    """#6430: the mains in this file declare shorter `gg_cics` structs; compiling swaps in ggcics.c's, so no stub
    function can write past a main's copy."""
    mains = re.findall(
        r"^_[A-Z0-9_]*MAIN\w* = r\"\"\"(.*?)\"\"\"", Path(__file__).read_text(encoding="utf-8"), re.S | re.M
    )
    assert mains and any(_GG_CICS_TYPEDEF.search(m) for m in mains)
    for main in mains:
        swapped = _with_stub_struct(main)
        assert swapped.count("} gg_cics;") == main.count("} gg_cics;")
        assert all(m == _stub_struct() for m in _GG_CICS_TYPEDEF.findall(swapped))
    assert "int go_to;" in _stub_struct() and "tochan" in _stub_struct()


def _stub(tmp_path: Path, main: str) -> Path:
    return _compiled_stub(main)


def _stub_base_env() -> dict[str, str]:
    """What a stub needs to start: Windows wants its own PATH (the MinGW runtime) and SYSTEMROOT (#5055)."""
    if os.name == "nt":
        return {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    return {"PATH": "/usr/bin:/bin"}


def _run_stub(exe: Path, work: Path, *args: str) -> list[str]:
    (work / "out").mkdir(parents=True, exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
    proc = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    return proc.stdout.splitlines()


# ---- #4005: terminal RECEIVE -------------------------------------------------------------------------
@needs_cc
def test_the_stub_receive_returns_the_typed_text_once_and_truncates_with_lengerr(tmp_path):
    """IBM, EXEC CICS RECEIVE: data longer than LENGTH "is truncated to that value and the LENGERR
    condition occurs. The data area specified in the LENGTH option is set to the original length of
    data." The terminal's input is read once per task (one process, #4004); a second RECEIVE would wait for the
    operator."""
    exe = _stub(tmp_path, _STUB_MAIN)
    (tmp_path / "terminal.in").write_bytes(b"CA02 S")
    assert _run_stub(exe, tmp_path, "20", "20") == ["resp=0 len=6 into=CA02 S..", "resp=0 len=0 into=........"]
    assert (tmp_path / "out" / "events.txt").read_text().splitlines() == ["001 RECEIVE pgm= resp=0 len=6 copied=6",
                                                                          "002 RECEIVE-WAIT pgm="]  # fmt: skip
    assert (tmp_path / "out" / "001.bin").read_bytes() == b"CA02 S"

    short = tmp_path / "short"
    short.mkdir()
    (short / "terminal.in").write_bytes(b"CA02 S")
    assert _run_stub(exe, short, "4") == ["resp=22 len=6 into=CA02...."]
    assert (short / "out" / "001.bin").read_bytes() == b"CA02"

    nothing = tmp_path / "nothing"  # a step that transmitted no data (ENTER on a SEND TEXT screen)
    nothing.mkdir()
    assert _run_stub(exe, nothing, "20") == ["resp=0 len=0 into=........"]


# ---- the generated CicsTask ------------------------------------------------------------------------------
@functools.cache
def _cics_task_classes() -> tuple[Path, str]:
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-cicstask-rt-"))
    atexit.register(shutil.rmtree, base, True)
    pkg = base / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    runtime = CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC")
    (pkg / "CicsTask.java").write_text(runtime, encoding="utf-8")
    (pkg / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "t"), encoding="utf-8")
    classes = base / "classes"
    built = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(classes), *map(str, pkg.glob("*.java"))], check=False,  # noqa: S603, S607
                           capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    assert built.returncode == 0, built.stderr
    return classes, runtime


def _cics_task(tmp_path: Path, main_body: str) -> str:
    """Compile the generated CicsTask with a main whose body is `main_body`; its stdout."""
    rt_classes, runtime = _cics_task_classes()
    pkg = tmp_path / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    (pkg / "CicsTask.java").write_text(runtime, encoding="utf-8")
    main_java = pkg / "Main.java"
    main_java.write_text("package t.cics;\n\npublic class Main {\n    public static void main(String[] a) {\n"
                         + main_body + "\n    }\n}\n", encoding="utf-8")  # fmt: skip
    classes = tmp_path / "classes"
    built = javac_run([javac, "-encoding", "UTF-8", "-cp", str(rt_classes), "-d", str(classes), str(main_java)], check=False,  # noqa: S603, S607
                           capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    assert built.returncode == 0, built.stderr
    cp = os.pathsep.join([str(classes), str(rt_classes)])
    # (bytes, decoded here: text=True reads the Windows locale charset, and a not sign in the output left stdout None)
    proc = subprocess.run(["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", cp, "t.cics.Main"],  # noqa: S603, S607
                          capture_output=True, check=True)  # fmt: skip
    return proc.stdout.decode("utf-8")


@needs_javac
@pytest.mark.slow(
    reason="1 s warm; on a loaded CI runner it was the first test in its worker and paid the cold javac of the shared CicsTask build (18 s, #4174 run 38903503168)"
)
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
@pytest.mark.slow(
    reason="1.4 s warm; first in its CI split part it paid the cold javac of the shared CicsTask build (26 s, #6018 full-suite part 3/3)"
)
def test_cics_task_abend_carries_its_cause_outcome_and_exit(tmp_path):
    """#4003: an exit that takes the abend leaves the task running; the default action terminates it."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("HC02", "ENTER", null, null);
        System.out.println("[" + t.abcode() + "]");
        t.abendToExit("AEYH", "condition", "QIDERR", "HCMAIN", "MAIN-ABEND");
        System.out.println(t.abcode() + " " + t.ended());
        t.abendOnCondition("QIDERR");
        System.out.println(t.ended() + " " + CicsTask.abcodeFor("PGMIDERR"));
        CicsTask u = new CicsTask("HC02", "ENTER", null, null);
        u.abend("HCX1");
        for (CicsTask x : java.util.List.of(t, u)) {
            for (java.util.Map<String, Object> e : x.events()) {
                java.util.Map<String, Object> sorted = new java.util.TreeMap<>(e);
                if (e.get("exit") instanceof java.util.Map<?, ?> m) {
                    sorted.put("exit", new java.util.TreeMap<>(m));
                }
                System.out.println(sorted);
            }
        }""",
    )
    assert out.splitlines() == [
        "[    ]",
        "AEYH false",
        "true AEI0",
        "{abcode=AEYH, cause=condition, condition=QIDERR, event=ABEND, exit={label=MAIN-ABEND, program=HCMAIN}, "
        "outcome=exit}",
        "{abcode=AEYH, cause=condition, condition=QIDERR, event=ABEND, outcome=terminated}",
        "{abcode=HCX1, cause=command, event=ABEND, outcome=terminated}",
    ]


@needs_javac
def test_cics_task_searches_the_abend_exits_upward_and_unwinds_the_levels_below(tmp_path):
    """#3989, IBM HANDLE ABEND: "CICS searches for an active abend exit, starting at the logical level of the
    application program in which the abend occurred, and proceeding to successively higher levels"; the exit
    is deactivated when it gets control, the levels below it are gone, PUSH HANDLE suspends it and CANCEL on
    ABEND takes none. EIBTRMID is the task's terminal at every level."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask task) {
                if (p.equals("MAIN")) {
                    task.handleAbend("MAIN-ABEND");
                    task.link("SUB", new StringBuilder("CA"), 2);
                    System.out.println("MAIN back: exit=" + task.abendExit() + " ended=" + task.ended()
                            + " abcode=" + task.abcode());
                    System.out.println("again: " + task.abendOnCondition("NOTFND") + " " + task.ended());
                } else if (p.equals("SUB")) {
                    System.out.println("SUB " + task.termid() + " level=" + task.level());
                    task.pushHandle();
                    task.handleAbend("SUB-ABEND");
                    System.out.println("SUB own: " + task.abend("HCX1") + " " + task.ended());
                    System.out.println("pop " + task.popHandle() + " " + task.popHandle());
                    task.link("SUB2");
                    System.out.println("SUB not here: " + task.ended());
                } else if (p.equals("SUB2")) {
                    System.out.println("SUB2 unwinds: " + task.abendOnCondition("QIDERR") + " " + task.ended());
                }
            }
        };
        CicsTask t = new CicsTask("HC02", "ENTER", null, null).withPrograms(programs).withTermid("T001");
        t.run("MAIN");
        CicsTask c = new CicsTask("HC03", "ENTER", null, null);
        c.handleAbend("X");
        System.out.println("cancel: " + c.abendCancel("HCX2") + " " + c.ended());
        for (CicsTask x : java.util.List.of(t, c)) {
            for (java.util.Map<String, Object> e : x.events()) {
                if ("ABEND".equals(e.get("event"))) {
                    Object exit = e.get("exit") instanceof java.util.Map<?, ?> m ? new java.util.TreeMap<>(m) : null;
                    System.out.println(e.get("issuer") + " " + e.get("abcode") + " " + e.get("outcome") + " " + exit);
                }
            }
        }""",
    )
    assert out.splitlines() == [
        "SUB T001 level=2",
        "SUB own: SUB-ABEND false",  # its own exit takes it: go on at the label
        "pop NORMAL INVREQ",
        "SUB2 unwinds: null true",  # the exit is MAIN's, two levels up: stop now
        "SUB not here: true",  # SUB's LINK came back with SUB unwound too: it stops
        "MAIN back: exit=MAIN-ABEND ended=false abcode=AEYH",  # SUB was unwound, not returned to
        "again: null true",  # MAIN's exit was deactivated when it got control: terminated
        "cancel: null true",
        "SUB HCX1 exit {label=SUB-ABEND, program=SUB}",
        "SUB2 AEYH exit {label=MAIN-ABEND, program=MAIN}",
        "MAIN AEIM terminated null",
        "null HCX2 terminated null",
    ]


@needs_javac
def test_cics_task_link_runs_the_callee_on_the_callers_commarea(tmp_path):
    """#4004, IBM EXEC CICS LINK: the COMMAREA is passed by reference (the callee's writes are the caller's),
    EIBCALEN is the LENGTH given, PGMIDERR RESP2 1 for an undefined program, LENGERR RESP2 11 outside
    0-32763; a GOBACK is a RETURN; an XCTL below level 1 runs its target at the same level."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("GONE");
            }

            public void run(String p, CicsTask task) {
                StringBuilder ca = task.hasCommarea() ? task.commarea(StringBuilder.class) : null;
                System.out.println(p + " level=" + task.level() + " calen=" + task.eibcalen());
                if (p.equals("MAIN")) {
                    StringBuilder mine = new StringBuilder("PING");
                    System.out.println(task.link("SUB", mine, 100) + " " + mine);
                    System.out.println(task.link("GONE", mine, 100) + " " + task.link("SUB", mine, 40000));
                    task.link("NOCA");
                    task.returnTransid(null, null);
                } else if (p.equals("SUB")) {
                    ca.append("-SUB");
                    task.xctl("SUB2", new StringBuilder(ca), 50);  // a copy: its own DTO is X39's refusal (#4956)
                } else if (p.equals("SUB2")) {
                    ca.append("-SUB2");
                    task.receiveText(10);
                    task.returnTransid(null, null);
                }
            }
        };
        CicsTask t = new CicsTask("T1", "ENTER", null, null).withPrograms(programs).withTerminalInput("T1 X")
                .withSnapshot(o -> o == null ? null : o.toString());
        t.run("MAIN");
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println(new java.util.TreeMap<>(e));
        }
        try {
            t.receiveText(10);
        } catch (IllegalStateException e) {
            System.out.println("read once per task");
        }""",
    )
    assert out.splitlines() == [
        "MAIN level=1 calen=0",
        "SUB level=2 calen=100",
        "SUB2 level=2 calen=50",
        "NORMAL PING-SUB",
        "PGMIDERR LENGERR",
        "NOCA level=2 calen=0",
        "{commarea=PING, event=LINK, issuer=MAIN, length=100, resp=NORMAL, resp2=null, target=SUB}",
        "{commarea=PING-SUB, event=XCTL, issuer=SUB, length=50, program=SUB2, resp=NORMAL, resp2=null}",
        "{data=T1 X, event=RECEIVE, issuer=SUB2, length=4, resp=NORMAL}",
        "{caller_commarea=PING-SUB, event=RETURN, issuer=SUB2, length=100, level=2}",  # #3989: the LINK's LENGTH
        "{commarea=PING-SUB, event=LINK, issuer=MAIN, length=100, resp=PGMIDERR, resp2=1, target=GONE}",
        "{commarea=PING-SUB, event=LINK, issuer=MAIN, length=40000, resp=LENGERR, resp2=11, target=SUB}",
        "{commarea=null, event=LINK, issuer=MAIN, length=0, resp=NORMAL, resp2=null, target=NOCA}",
        "{caller_commarea=null, event=RETURN, issuer=NOCA, length=0, level=2}",
        "{commarea=null, event=RETURN, issuer=MAIN, length=null, transid=null}",
        "read once per task",
    ]


@needs_javac
def test_cics_task_interval_control_follows_start_retrieve_and_cancel(tmp_path):
    out = _cics_task(
        tmp_path,
        """
        java.time.LocalDateTime ten = java.time.LocalDateTime.of(2026, 3, 2, 10, 0, 0);
        CicsTask t = new CicsTask("GT01", "ENTER", null, null).withClock(ten)
                .withRetrieveData(java.util.List.of("ALPHA".getBytes(), "BRA".getBytes()))
                .withRequests(java.util.Map.of("R2", ten.plusSeconds(5), "R3", ten));
        System.out.println(t.start("GT02", null, 130, "ABC".getBytes(), "R1", true).expires());
        System.out.println(t.startAt("GT02", null, 93000, null, null, false).expires() + " "
                + t.startAt("GT02", null, 30000, null, null, false).expires() + " "
                + t.start("GT02", null, 170, null, null, false).resp());
        System.out.println(t.cancel("R1") + " " + t.cancel("R1") + " " + t.cancel("R2") + " " + t.cancel("R3"));
        CicsTask.RetrieveResult r1 = t.retrieve(4);
        CicsTask.RetrieveResult r2 = t.retrieve(4);
        System.out.println(r1.resp() + " " + r1.length() + " " + new String(r1.data()) + " " + r2.resp() + " "
                + t.retrieve(4).resp());
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("START")) {
                System.out.println(new java.util.TreeMap<>(e).keySet() + " " + e.get("interval") + e.get("time"));
            }
        }""",
    )
    assert out.splitlines() == [
        "2026-03-02T10:01:30",
        "2026-03-02T10:00 2026-03-03T03:00 INVREQ",
        "NORMAL NOTFND NORMAL NOTFND",
        "LENGERR 5 ALPH NORMAL ENDDATA",
        "[event, expires, from, interval, protect, reqid, resp, termid, transid] 000130null",
        "[event, expires, from, protect, resp, termid, time, transid] null093000",
        "[event, expires, from, protect, resp, termid, time, transid] null030000",
        "[event, expires, from, interval, protect, resp, resp2, termid, transid] 000170null",  # #4270: RESP2 6
    ]


@needs_javac
def test_cics_task_xctl_fails_in_place_with_lengerr_or_pgmiderr(tmp_path):
    """#4008, IBM EXEC CICS XCTL: LENGERR RESP2 11 for a LENGTH outside 0-32763, PGMIDERR RESP2 1 for an
    undefined program; either way nothing is transferred and the program goes on."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("GONE");
            }

            public void run(String p, CicsTask task) {
                if (p.equals("CAXA")) {
                    System.out.println(task.xctl("CAXB", "BIG", 32767) + " " + task.ended());
                    System.out.println(task.xctl("GONE", "V1", 10) + " " + task.ended());
                    System.out.println(task.xctl("CAXB", "V1", 80) + " " + task.ended());
                } else {
                    System.out.println(p + " calen=" + task.eibcalen() + " ca=" + task.commarea(String.class));
                }
            }
        };
        CicsTask t = new CicsTask("CA02", "ENTER", null, null).withPrograms(programs);
        t.run("CAXA");
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println(new java.util.TreeMap<>(e));
        }""",
    )
    assert out.splitlines() == [
        "LENGERR false",
        "PGMIDERR false",
        "NORMAL true",
        "CAXB calen=80 ca=V1",
        "{commarea=BIG, event=XCTL, issuer=CAXA, length=32767, program=CAXB, resp=LENGERR, resp2=11}",
        "{commarea=V1, event=XCTL, issuer=CAXA, length=10, program=GONE, resp=PGMIDERR, resp2=1}",
        "{commarea=V1, event=XCTL, issuer=CAXA, length=80, program=CAXB, resp=NORMAL, resp2=null}",
    ]


@needs_javac
def test_cics_task_failed_xctl_and_link_end_with_the_condition_abend_code(tmp_path):
    """#4648, IBM EXEC CICS XCTL / LINK conditions (INVREQ, LENGERR, NOTAUTH, PGMIDERR): a planned failure of either
    command is its RESP, and with no HANDLE CONDITION / RESP the program's default action abends the task with the
    condition's code (AEIP, AEIV, AEY7, AEI0) -- NOTAUTH had none, so the runtime threw instead. An XCTL that failed
    transfers nothing; a LINK that failed runs nothing."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask task) {
                if (p.equals("CAXA")) {
                    for (String cmd : new String[] {"XCTL", "LINK"}) {
                        for (String want : new String[] {"INVREQ", "LENGERR", "NOTAUTH", "PGMIDERR"}) {
                            String r = cmd.equals("XCTL") ? task.xctl("CAXB", "V1", 80) : task.link("CAXB", "V1", 80);
                            System.out.println(cmd + " " + r + " " + task.ended() + " " + task.transferResp2());  // #4986
                            if (!r.equals("NORMAL")) {
                                task.abendOnCondition(r);
                                System.out.println(task.abcode());
                            }
                        }
                    }
                } else {
                    System.out.println("ran " + p);
                }
            }
        };
        CicsTask t = new CicsTask("CA02", "ENTER", null, null).withPrograms(programs).withFaults(java.util.List.of(
                "XCTL CAXB 1 " + CicsSpec.resp("INVREQ") + " 1", "XCTL CAXB 2 " + CicsSpec.resp("LENGERR") + " 11",
                "XCTL CAXB 3 " + CicsSpec.resp("NOTAUTH") + " 100", "XCTL CAXB 4 " + CicsSpec.resp("PGMIDERR") + " 3",
                "LINK CAXB 1 " + CicsSpec.resp("INVREQ") + " 1", "LINK CAXB 2 " + CicsSpec.resp("LENGERR") + " 11",
                "LINK CAXB 3 " + CicsSpec.resp("NOTAUTH") + " 100", "LINK CAXB 4 " + CicsSpec.resp("PGMIDERR") + " 3"),
                null);
        t.run("CAXA");
        for (java.util.Map<String, Object> e : t.events()) {
            if (!"ABEND".equals(e.get("event"))) {
                System.out.println(e.get("event") + " " + e.get("resp") + " " + e.get("resp2"));
            }
        }""",
    )
    lines = out.splitlines()
    assert lines[:2] == ["XCTL INVREQ false 1", "AEIP"]
    # #4986: EIBRESP2 (task.transferResp2) is the plan's, not the condition name's: PGMIDERR 3 was 1, NOTAUTH 100 was 0
    shown = [ln.split() for ln in lines if ln.startswith(("XCTL ", "LINK ")) and ln.count(" ") == 3]
    assert [(c, r, x) for c, r, _, x in shown] == [(c, r, str(x)) for c in ("XCTL", "LINK")
                     for r, x in (("INVREQ", 1), ("LENGERR", 11), ("NOTAUTH", 100), ("PGMIDERR", 3))]  # fmt: skip
    assert [ln for ln in lines if ln.startswith(("AE", "ran"))] == ["AEIP", "AEIV", "AEY7", "AEI0"] * 2
    assert "ran CAXB" not in lines  # nothing transferred, nothing linked
    assert lines[-8:] == [f"{c} {r} {x}" for c in ("XCTL", "LINK")
                          for r, x in (("INVREQ", 1), ("LENGERR", 11), ("NOTAUTH", 100), ("PGMIDERR", 3))]  # fmt: skip


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


@needs_javac
def test_cics_task_receive_notruncate_eoc_and_send_control(tmp_path):
    """#4413, IBM EXEC CICS RECEIVE (3270 logical / LUTYPE2): MAXLENGTH with NOTRUNCATE returns the first bytes NORMAL
    with the length returned and keeps the rest for the next RECEIVE of the task; a negative limit is zero; an
    LUTYPE2 terminal's RECEIVE returning the input's last byte raises EOC, and one leaving data retained there is
    refused (undocumented). SEND CONTROL records its options sorted and its CURSOR offset."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("HC05", "ENTER", null, null).withTerminalInput("HC05 ABCDEFG");
        System.out.println(t.receive(5, true));
        System.out.println(t.receive(4, true));
        System.out.println(t.receive(4, true));
        try {
            t.receive(4, true);
        } catch (IllegalStateException e) {
            System.out.println("waits");
        }
        CicsTask z = new CicsTask("HC05", "ENTER", null, null).withTerminalInput("HC05");
        System.out.println(z.receive(-3, false));
        CicsTask l = new CicsTask("HC05", "ENTER", null, null).withTerminalInput("HC05 X").withEndOfChain(true);
        System.out.println(l.receive(80, false));
        CicsTask m = new CicsTask("HC05", "ENTER", null, null).withTerminalInput("HC05 X").withEndOfChain(true);
        System.out.println(m.receive(2, false));
        CicsTask n = new CicsTask("HC05", "ENTER", null, null).withTerminalInput("HC05 X").withEndOfChain(true);
        try {
            n.receive(2, true);
        } catch (IllegalStateException e) {
            System.out.println("refused");
        }
        t.sendControl(null, "FREEKB", "ERASE");
        t.sendControl(85, "CURSOR", "ALARM");
        System.out.println(t.events());""",
    )
    assert out.splitlines() == [
        "Received[resp=NORMAL, length=5, data=HC05 ]",
        "Received[resp=NORMAL, length=4, data=ABCD]",
        "Received[resp=NORMAL, length=3, data=EFG]",
        "waits",
        "Received[resp=LENGERR, length=4, data=]",
        "Received[resp=EOC, length=6, data=HC05 X]",
        "Received[resp=LENGERR, length=6, data=HC]",
        "refused",
        (
            "[{event=RECEIVE, resp=NORMAL, length=5, data=HC05 }, {event=RECEIVE, resp=NORMAL, length=4, data=ABCD}, "
            "{event=RECEIVE, resp=NORMAL, length=3, data=EFG}, {event=SEND-CONTROL, options=[ERASE, FREEKB], "
            "cursor=null}, {event=SEND-CONTROL, options=[ALARM, CURSOR], cursor=85}]"
        ),
    ]


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
    assert events[0] == "001 READQ-TS pgm= queue=5131 item=1 resp=44 len=-1 copied=0"
    assert events[4] == "005 READQ-TS pgm= queue=5131 item=1 resp=22 len=5 copied=3"
    assert events[6] == "007 READQ-TS pgm= queue=5131 item=NEXT resp=0 len=2 copied=2"
    assert events[1] == "002 WRITEQ-TS pgm= queue=5131 item=1 resp=0 len=5"
    assert (tmp_path / "ts" / "5131" / "000002.bin").read_bytes() == b"XY"


# ---- #4003: conditions and abends ------------------------------------------------------------------------
_COND_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCPENT(gg_cics *c); int GGCHCND(gg_cics *c); int GGCHABN(gg_cics *c); int GGCPUSH(gg_cics *c);
int GGCPOP(gg_cics *c); int GGCABND(gg_cics *c); int GGCCOND(gg_cics *c); int GGCASGN(gg_cics *c);
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static void handle(int cond, int label) { c.num = cond; c.item = label; GGCHCND(&c); }
static void raise(int resp) { c.resp = resp; GGCCOND(&c); printf("%d ", c.go_to); }
int main(void) {
    memset(&c, 0, sizeof c);
    blank(c.name1, 8, "HCQREAD"); GGCPENT(&c);
    raise(44);                            /* default: abend AEYH, no exit: terminated (-1) */
    handle(44, 1); handle(26, 2); handle(1, 3);
    raise(44); raise(26); raise(22);      /* labels 1, 2, then ERROR's 3 */
    handle(26, -1); raise(26);            /* IGNORE: 0 */
    handle(26, 4); raise(26);             /* a later HANDLE overrides the IGNORE: 4 */
    handle(26, 0); raise(26);             /* HANDLE without a label: back to the default, here ERROR's 3 */
    blank(c.name2, 8, "LABEL"); blank(c.flags, 40, "MAIN-ABEND"); c.item = 5; GGCHABN(&c);
    GGCPUSH(&c); raise(44);               /* pushed: no handler, no exit: -1 */
    GGCPOP(&c); printf("pop=%d ", c.resp);
    GGCPOP(&c); printf("pop=%d ", c.resp); /* nothing pushed: INVREQ */
    raise(44);                            /* the handler is back: 1 */
    handle(1, 0); raise(13);              /* NOTFND, no ERROR: abend AEIM to the exit, label 5 */
    GGCASGN(&c); printf("%.4s ", c.name1);
    raise(13);                            /* the exit was deactivated when it got control: -1 */
    blank(c.name2, 8, "RESET"); GGCHABN(&c);
    blank(c.name1, 8, "HCX1"); blank(c.flags, 40, ""); GGCABND(&c); printf("%d ", c.go_to);
    blank(c.name2, 8, "RESET"); GGCHABN(&c);
    blank(c.name1, 8, "HCX2"); blank(c.flags, 40, "CANCEL"); GGCABND(&c); printf("%d\n", c.go_to);
    return 0;
}
"""


@needs_cc
def test_the_stub_handles_conditions_and_abends_as_cics_does(tmp_path):
    """IBM, HANDLE CONDITION / IGNORE CONDITION / HANDLE ABEND / PUSH and POP HANDLE and the abend-exit
    search: the last HANDLE or IGNORE for a condition wins, ERROR catches what has no handler of its own,
    PUSH suspends every handler and the abend exit, an exit is deactivated as it takes an abend, RESET
    reactivates it and ABEND CANCEL skips it."""
    exe = _stub(tmp_path, _COND_MAIN)
    assert _run_stub(exe, tmp_path) == ["-1 1 2 3 0 4 3 -1 pop=0 pop=16 1 5 AEIM -1 5 -1"]
    assert (tmp_path / "out" / "events.txt").read_text().splitlines() == [
        "001 ABEND pgm=HCQREAD abcode=AEYH cause=condition condition=44 outcome=terminated",
        "002 ABEND pgm=HCQREAD abcode=AEYH cause=condition condition=44 outcome=terminated",
        "003 ABEND pgm=HCQREAD abcode=AEIM cause=condition condition=13 outcome=exit exit=HCQREAD.MAIN-ABEND",
        "004 ABEND pgm=HCQREAD abcode=AEIM cause=condition condition=13 outcome=terminated",
        "005 ABEND pgm=HCQREAD abcode=HCX1 cause=command outcome=exit exit=HCQREAD.MAIN-ABEND",
        "006 ABEND pgm=HCQREAD abcode=HCX2 cause=command outcome=terminated",
    ]


def test_the_stub_and_the_runner_agree_on_condition_abend_codes():
    src = STUB.with_name("ggcics_spec.h").read_text(encoding="utf-8")  # #4270 spec PR 4: the stub's condition_abcode
    import cics_crucible as runner
    import equivalence_cics as ec

    table = dict(re.findall(r'case DFHRESP_(\w+): return "(\w{4})";', src))
    assert {c: table[c] for c in runner.CONDITION_ABCODE} == runner.CONDITION_ABCODE
    assert all(c in ec.DFHRESP for c in table)


# ---- #4006: interval control ----------------------------------------------------------------------------
_IC_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCSTRT(gg_cics *c, char *from); int GGCRTRV(gg_cics *c, char *into); int GGCCNCL(gg_cics *c);
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static void start(const char *transid, const char *termid, const char *reqid, int hhmmss, const char *how) {
    blank(c.name1, 8, transid); blank(c.name2, 8, termid); blank(c.qname, 16, reqid); blank(c.flags, 40, how);
    c.num = hhmmss; c.item = 1; c.len = 3;
    GGCSTRT(&c, "ABC");
    printf("%d ", c.resp);
}
int main(void) {
    char into[8];
    start("GT02", "", "", 0, "INTERVAL");
    start("GT02", "T001", "R1", 130, "INTERVAL PROTECT");
    start("GT02", "", "", 103000, "TIME");
    start("GT02", "", "", 93000, "TIME");       /* within the preceding six hours: now */
    start("GT02", "", "", 30000, "TIME");       /* seven hours before: tomorrow */
    start("GT02", "", "", 170, "INTERVAL");     /* 70 seconds: INVREQ */
    start("NOPE", "", "", 0, "INTERVAL");       /* TRANSIDERR */
    start("GT02", "T999", "", 0, "INTERVAL");   /* TERMIDERR */
    blank(c.qname, 16, "R1"); GGCCNCL(&c); printf("%d ", c.resp);  /* this task's own, unexpired */
    blank(c.qname, 16, "R1"); GGCCNCL(&c); printf("%d ", c.resp);  /* already cancelled */
    blank(c.qname, 16, "R2"); GGCCNCL(&c); printf("%d ", c.resp);  /* requests.cfg: unexpired */
    blank(c.qname, 16, "R3"); GGCCNCL(&c); printf("%d ", c.resp);  /* requests.cfg: expired */
    for (int i = 0; i < 3; i++) {
        memset(into, '.', sizeof into);
        c.len = 4;
        blank(c.flags, 40, "INTO");
        GGCRTRV(&c, into);
        printf("%d/%d/%.6s ", c.resp, c.len, into);
    }
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_interval_control_follows_start_retrieve_and_cancel(tmp_path):
    """IBM EXEC CICS START: expiry at now + INTERVAL or at TIME (the six-hour rule), INVREQ / TRANSIDERR /
    TERMIDERR; RETRIEVE: the started task's data in order, LENGERR truncating (LENGTH = the record's length),
    then ENDDATA; CANCEL: NORMAL only for an unexpired request."""
    exe = _stub(tmp_path, _IC_MAIN)
    (tmp_path / "transactions.cfg").write_text("GT01\nGT02\n")
    (tmp_path / "terminals.cfg").write_text("T001\n")
    now = 1772445600  # 2026-03-02T10:00:00 as the stub's clock counts it
    (tmp_path / "requests.cfg").write_text(f"R2 {now + 5}\nR3 {now}\n")
    (tmp_path / "retrieve_001.bin").write_bytes(b"ALPHA")
    (tmp_path / "retrieve_002.bin").write_bytes(b"BRA")
    out = subprocess.run([str(exe)], env={"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path),
                                          "GGCICS_NOW": "2026-03-02T10:00:00"},
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    assert out.split() == ["0", "0", "0", "0", "0", "16", "28", "11", "0", "13", "0", "13",
                           "22/5/ALPH..", "0/3/BRA...", "29/4/......"]  # fmt: skip
    events = (tmp_path / "events.txt").read_text().splitlines()
    expires = [re.search(r"expires=(\S*)", e).group(1) for e in events if " START " in e]
    assert expires == ["2026-03-02T10:00:00", "2026-03-02T10:01:30", "2026-03-02T10:30:00", "2026-03-02T10:00:00",
                       "2026-03-03T03:00:00", "", "", ""]  # fmt: skip
    assert "interval=000130 reqid=R1 protect=1 resp=0" in events[1] and "termid=T001" in events[1]
    assert "time=093000" in events[3]
    assert events[-3] == "013 RETRIEVE pgm= resp=22 len=5 copied=4 into=1"
    assert events[-1] == "015 RETRIEVE pgm= resp=29 len=-1 copied=0 into=1"


# ---- #4008: XCTL RESP / LENGTH ---------------------------------------------------------------------------
_XCTL_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCXCTL(gg_cics *c, char *commarea, int len);
int main(void) {
    static char block[100] = "1C00420007GOLD";
    gg_cics c;
    const char *to[] = {"CAXB", "GONE", "CAXB"};
    int lens[] = {32767, 10, 80};
    for (int i = 0; i < 3; i++) {
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        memcpy(c.name1, to[i], 4);
        c.item = 1;
        GGCXCTL(&c, block, lens[i]);
        printf("%d/%d ", c.resp, c.resp2);
    }
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_xctl_fails_in_place_and_copies_length_bytes(tmp_path):
    """#4008, IBM EXEC CICS XCTL: LENGERR RESP2 11 outside 0-32763, PGMIDERR RESP2 1 for an undefined program;
    a successful one carries LENGTH bytes from the named area, past the end of the item if need be."""
    exe = _stub(tmp_path, _XCTL_MAIN)
    (tmp_path / "programs.cfg").write_text("CAXA\nCAXB\n")
    assert [ln.strip() for ln in _run_stub(exe, tmp_path)] == ["22/11 27/1 0/0"]
    events = (tmp_path / "out" / "events.txt").read_text().splitlines()
    assert events == ["001 XCTL pgm= program=CAXB len=32767 area=1 resp=22 resp2=11",
                      "002 XCTL pgm= program=GONE len=10 area=1 resp=27 resp2=1",
                      "003 XCTL pgm= program=CAXB len=80 area=1 resp=0 resp2=0"]  # fmt: skip
    assert (tmp_path / "out" / "003.bin").read_bytes()[:14] == b"1C00420007GOLD"
    assert len((tmp_path / "out" / "003.bin").read_bytes()) == 80


# ---- #4007: HANDLE AID ------------------------------------------------------------------------------------
_AID_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCHAID(gg_cics *c); int GGCAID(gg_cics *c); int GGCPUSH(gg_cics *c); int GGCPOP(gg_cics *c);
static gg_cics c;
static void handle(const char *key, int label) {
    memset(c.name1, ' ', 8); memcpy(c.name1, key, strlen(key)); c.item = label; GGCHAID(&c);
}
static void press(char aid) { memset(c.name1, ' ', 8); c.name1[0] = aid; GGCAID(&c); printf("%d ", c.go_to); }
int main(void) {
    memset(&c, 0, sizeof c);
    press('5');                                   /* no HANDLE AID: 0 */
    handle("PF5", 1); handle("PF3", 2);
    press('5'); press('3'); press('9'); press('\'');  /* PF5, PF3, PF9 (no label), ENTER */
    handle("ANYKEY", 3);
    press('9'); press('_'); press('\''); press('%');  /* ANYKEY: PF9, CLEAR, not ENTER, PA1 */
    handle("PF5", 0); press('5');                 /* no label: deactivated, ANYKEY takes it */
    GGCPUSH(&c); press('3'); GGCPOP(&c); press('3');  /* PUSH suspends HANDLE AID; POP restores it */
    handle("PF9", -1); press('9');                /* #4414: deactivated under ANYKEY: refused, 0 */
    c.resp = 36; press('3');                      /* #4414: a label and a condition: refused, 0 */
    c.resp = 36; press('\'');                     /* a condition, no label for ENTER: 0 */
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_handle_aid_gives_each_key_its_label(tmp_path):
    """IBM, HANDLE AID: control goes to the key's label after the input command; a key without a label is
    left to the program; ANYKEY is any PA or PF key or CLEAR, not ENTER; an option never given a label is
    ANYKEY's; PUSH HANDLE suspends it."""
    exe = _stub(tmp_path, _AID_MAIN)
    assert [ln.strip() for ln in _run_stub(exe, tmp_path)] == ["0 1 2 0 0 3 3 0 3 3 0 2 0 0 0"]
    # #4414: what IBM does not say is refused, for the driver: a key deactivated (-1) while ANYKEY has a label, and a
    # label that applies to the key of an input command that raised a condition
    events = [ln.split(" ", 1)[1] for ln in (tmp_path / "out" / "events.txt").read_text().splitlines()]
    assert events == ["AID-REFUSED pgm= deactivated=1", "AID-REFUSED pgm= resp=36"]


def test_the_stubs_aid_bytes_are_the_harness_dfhaid():
    """GGCAID reads EIBAID as the harness's DFHAID.cpy spells each key (the driver sets EIBAID from it)."""
    cpy = (STUB.parent / "DFHAID.cpy").read_text()
    names = {"ENTER": "DFHENTER", "CLEAR": "DFHCLEAR", "CLRPARTN": "DFHCLRP", "LIGHTPEN": "DFHPEN", "OPERID": "DFHOPID",
             "TRIGGER": "DFHTRIG"} | {k: f"DFH{k}" for k in [f"PA{n}" for n in (1, 2, 3)] + [f"PF{n}" for n in range(1, 25)]}  # fmt: skip
    values = {}
    for m in re.finditer(r"02 (DFH\w+)\s+PIC X VALUE (X'([0-9A-F]{2})'|'(''|[^'])')\.", cpy):
        values[m.group(1)] = chr(int(m.group(3), 16)) if m.group(3) else ("'" if m.group(4) == "''" else m.group(4))
    src = STUB.read_text() + (STUB.parent / "ggcics_conditions.c").read_text()  # #5274: GGCAID moved to its family file
    for key, dfh in names.items():
        m = re.search(r'\{"' + key + r'", (\'\\\'\'|\'.\'|0x[0-9A-F]+)\}', src)
        assert m, key
        raw = m.group(1)
        got = "'" if raw == "'\\''" else (chr(int(raw, 16)) if raw.startswith("0x") else raw[1])
        assert got == values[dfh], (key, got, values[dfh])


# ---- browse and DELETE (IBM CICS TS, STARTBR / READNEXT / READPREV / ENDBR / DELETE) -----------------------------
_BROWSE_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCSTBR(gg_cics *c, char *rid, int kl); int GGCRDNX(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCRDPV(gg_cics *c, char *rid, int kl, char *into, int il); int GGCENBR(gg_cics *c);
int GGCDELT(gg_cics *c, char *rid, int kl);
int main(int argc, char **argv) {
    gg_cics c;
    char rid[3], into[5];
    memset(&c, 0, sizeof c);
    memset(c.name1, ' ', 8);
    memcpy(c.name1, "F", 1);
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0];
        memset(c.flags, ' ', 40);
        if (argv[i][1] == ':') memcpy(rid, argv[i] + 2, 2);   /* the program sets RIDFLD */
        if (argv[i][1] == '*') memset(rid, 0xFF, 2);           /* HIGH-VALUES */
        memset(into, '.', 4);
        into[4] = 0;
        if (op == 'S') GGCSTBR(&c, rid, 2);
        if (op == 'E') { memcpy(c.flags, "EQUAL", 5); GGCSTBR(&c, rid, 2); }
        if (op == 'N') GGCRDNX(&c, rid, 2, into, 4);
        if (op == 'P') GGCRDPV(&c, rid, 2, into, 4);
        if (op == 'B') GGCENBR(&c);
        if (op == 'D') GGCDELT(&c, rid, 2);
        printf("%c resp=%d rid=%.2s into=%s\n", op, c.resp, (unsigned char)rid[0] == 0xFF ? "FF" : rid, into);
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_browses_as_cics_does(tmp_path):
    """STARTBR GTEQ / EQUAL, READNEXT from the start key then on, READPREV after READNEXT reading the same record
    again, a HIGH-VALUES start for a backwards browse, ENDFILE at both ends, NOTFND for a READPREV whose start key
    is not there, INVREQ for a second STARTBR and an ENDBR without a browse; DELETE by key."""
    (tmp_path / "f.dat").write_bytes(b"10aa20bb30cc")
    (tmp_path / "files.cfg").write_text(f"F {tmp_path / 'f.dat'} 4 0 2\n", encoding="ascii")
    exe = _stub(tmp_path, _BROWSE_MAIN)
    got = _run_stub(exe, tmp_path, "S:15", "N", "N", "P", "P", "P", "S:10", "B", "B",
                    "E:15", "S:15", "P", "B", "S*", "P", "P", "B", "S*", "N", "B", "S:20", "N", "N", "N", "B",
                    "D:20", "D:20")  # fmt: skip
    assert got == [
        "S resp=0 rid=15 into=....",  # GTEQ: positioned on 20
        "N resp=0 rid=20 into=20bb",
        "N resp=0 rid=30 into=30cc",
        "P resp=0 rid=30 into=30cc",  # after a READNEXT: repositions to RIDFLD, the same record again
        "P resp=0 rid=20 into=20bb",
        "P resp=0 rid=10 into=10aa",
        "S resp=16 rid=10 into=....",  # a browse is active: INVREQ
        "B resp=0 rid=10 into=....",
        "B resp=16 rid=10 into=....",  # no browse: INVREQ
        "E resp=13 rid=15 into=....",  # EQUAL: no record 15
        "S resp=0 rid=15 into=....",
        "P resp=13 rid=15 into=....",  # READPREV right after STARTBR: the key must exist
        "B resp=0 rid=15 into=....",
        "S resp=0 rid=FF into=....",  # X'FF': the end, for READPREV
        "P resp=0 rid=30 into=30cc",
        "P resp=0 rid=20 into=20bb",
        "B resp=0 rid=20 into=....",
        "S resp=0 rid=FF into=....",
        "N resp=20 rid=FF into=....",  # READNEXT from the end: ENDFILE
        "B resp=0 rid=FF into=....",
        "S resp=0 rid=20 into=....",
        "N resp=0 rid=20 into=20bb",
        "N resp=0 rid=30 into=30cc",
        "N resp=20 rid=30 into=....",  # past the last: ENDFILE
        "B resp=0 rid=30 into=....",
        "D resp=0 rid=20 into=....",
        "D resp=13 rid=20 into=....",  # gone: NOTFND
    ]
    assert (tmp_path / "f.dat").read_bytes() == b"10aa30cc"


@needs_javac
def test_cics_task_browses_as_the_stub_does(tmp_path):
    """The same browse as test_the_stub_browses_as_cics_does, through CicsTask: the same RESPs and keys."""
    out = _cics_task(
        tmp_path,
        """
        java.util.TreeSet<String> keys = new java.util.TreeSet<>(java.util.List.of("10", "20", "30"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        String rid = "";
        String ff = "\\u00FF\\u00FF";
        String[] ops = {"S:15", "N", "N", "P", "P", "P", "S:10", "B", "B", "E:15", "S:15", "P", "B", "S*", "P", "P",
                        "B", "S*", "N", "B", "S:20", "N", "N", "N", "B"};
        for (String op : ops) {
            if (op.length() > 1) {
                rid = op.charAt(1) == '*' ? ff : op.substring(2);
            }
            int resp;
            switch (op.charAt(0)) {
                case 'S': resp = t.startbr("F", rid, false, () -> keys); break;
                case 'E': resp = t.startbr("F", rid, true, () -> keys); break;
                case 'N': { CicsTask.Browsed b = t.readnext("F", rid); resp = b.resp(); if (b.normal()) rid = b.key(); break; }
                case 'P': { CicsTask.Browsed b = t.readprev("F", rid); resp = b.resp(); if (b.normal()) rid = b.key(); break; }
                default: resp = t.endbr("F");
            }
            System.out.println(op.charAt(0) + " resp=" + resp + " rid=" + (rid.equals(ff) ? "FF" : rid));
        }
        System.out.println(t.delete("F", keys.contains("20"), () -> keys.remove("20")) + " "
                + t.delete("F", keys.contains("20"), () -> keys.remove("20")) + " " + keys);""",
    )
    stub = ["S resp=0 rid=15", "N resp=0 rid=20", "N resp=0 rid=30", "P resp=0 rid=30", "P resp=0 rid=20",
            "P resp=0 rid=10", "S resp=16 rid=10", "B resp=0 rid=10", "B resp=16 rid=10", "E resp=13 rid=15",
            "S resp=0 rid=15", "P resp=13 rid=15", "B resp=0 rid=15", "S resp=0 rid=FF", "P resp=0 rid=30",
            "P resp=0 rid=20", "B resp=0 rid=20", "S resp=0 rid=FF", "N resp=20 rid=FF", "B resp=0 rid=FF",
            "S resp=0 rid=20", "N resp=0 rid=20", "N resp=0 rid=30", "N resp=20 rid=30", "B resp=0 rid=30"]  # fmt: skip
    assert out.splitlines() == [*stub, "0 13 [10, 30]"]


# ---- #4657: the browse commands' RESP2 (IBM CICS TS: STARTBR INVREQ 33 / NOTFND 80, READNEXT / READPREV INVREQ 34 /
# ENDFILE 90 / NOTFND 80, ENDBR INVREQ 35, DELETE NOTFND 80) -- the stub and CicsTask agree, and say IBM's value ----
_BROWSE_RESP2_OPS = ("S:15", "N", "N", "N", "P", "S:10", "B", "B", "N", "P", "E:15", "S*", "P", "P", "P", "B",
                     "S:20", "D:20", "D:20")  # fmt: skip
_BROWSE_RESP2_WANT = [
    "S 0 0", "N 0 0", "N 0 0", "N 20 90",  # past the last record: ENDFILE, RESP2 90
    "P 0 0", "S 16 33",  # a browse is active: INVREQ, RESP2 33
    "B 0 0", "B 16 35",  # ENDBR without a browse: INVREQ, RESP2 35
    "N 16 34", "P 16 34",  # READNEXT / READPREV without a browse: INVREQ, RESP2 34
    "E 13 80",  # EQUAL, no such key: NOTFND, RESP2 80
    "S 0 0", "P 0 0", "P 0 0", "P 0 0", "B 0 0",  # HIGH-VALUES, backwards over all three records
    "S 0 0", "D 0 0", "D 13 80",  # DELETE of a key that is gone: NOTFND, RESP2 80
]  # fmt: skip


@needs_cc
def test_the_stub_sets_browse_resp2_as_ibm_documents(tmp_path):
    (tmp_path / "f.dat").write_bytes(b"10aa20bb30cc")
    (tmp_path / "files.cfg").write_text(f"F {tmp_path / 'f.dat'} 4 0 2\n", encoding="ascii")
    main = _BROWSE_MAIN.replace('"%c resp=%d rid', '"%c %d %d rid').replace(
        "op, c.resp, (unsigned", "op, c.resp, c.resp2, (unsigned"
    )
    got = _run_stub(_stub(tmp_path, main), tmp_path, *_BROWSE_RESP2_OPS)
    assert [" ".join(line.split()[:3]) for line in got] == _BROWSE_RESP2_WANT


@needs_javac
def test_cics_task_sets_browse_resp2_as_the_stub_does(tmp_path):
    """#4657: the det runtime left EIBRESP2 0 on these (COBIL00C DISPLAYs it after a failed STARTBR / READPREV)."""
    out = _cics_task(
        tmp_path,
        """
        java.util.TreeSet<String> keys = new java.util.TreeSet<>(java.util.List.of("10", "20", "30"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        String rid = "";
        String ff = "\\u00FF\\u00FF";
        String[] ops = {"S:15", "N", "N", "N", "P", "S:10", "B", "B", "N", "P", "E:15", "S*", "P", "P", "P", "B",
                        "S:20", "D:20", "D:20"};
        for (String op : ops) {
            if (op.length() > 1) {
                rid = op.charAt(1) == '*' ? ff : op.substring(2);
            }
            int resp, resp2;
            switch (op.charAt(0)) {
                case 'S': resp = t.startbr("F", rid, false, () -> keys); resp2 = t.resp2(); break;
                case 'E': resp = t.startbr("F", rid, true, () -> keys); resp2 = t.resp2(); break;
                case 'N': { CicsTask.Browsed b = t.readnext("F", rid); resp = b.resp(); resp2 = b.resp2(); if (b.normal()) rid = b.key(); break; }
                case 'P': { CicsTask.Browsed b = t.readprev("F", rid); resp = b.resp(); resp2 = b.resp2(); if (b.normal()) rid = b.key(); break; }
                case 'D': { String k = rid; resp = t.delete("F", keys.contains(k), () -> keys.remove(k)); resp2 = t.resp2(); break; }
                default: resp = t.endbr("F"); resp2 = t.resp2();
            }
            System.out.println(op.charAt(0) + " " + resp + " " + resp2);
        }""",
    )
    assert out.splitlines() == _BROWSE_RESP2_WANT


# ---- #4270: READ GTEQ / GENERIC (IBM CICS TS, EXEC CICS READ; oracle_assumptions.md X22) --------------------------
_READ_SEARCH_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int main(int argc, char **argv) {
    gg_cics c;
    char into[5];
    for (int i = 1; i < argc; i++) {
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        memcpy(c.name1, "F", 1);
        memset(c.flags, ' ', 40);
        char op = argv[i][0], *rid = argv[i] + 1;
        if (op == 'G' || op == 'Q') memcpy(c.flags, "GTEQ", 4);
        if (op == 'R' || op == 'Q') memcpy(c.flags + 5, "GENERIC", 7);
        memset(into, '.', 4);
        into[4] = 0;
        c.len = 4;
        GGCREAD(&c, rid, op == 'R' || op == 'Q' ? (int)strlen(rid) : 3, into, 4);
        printf("%s resp=%d resp2=%d into=%s\n", argv[i], c.resp, c.resp2, into);
    }
    return 0;
}
"""
# op: E a plain READ (full key), G GTEQ, R GENERIC (KEYLENGTH = the key given), Q GENERIC GTEQ
_READ_SEARCH_OPS = ("E150", "G150", "G200", "G301", "R2", "R21", "Q25", "R4", "Q4", "Q0")
_READ_SEARCH_WANT = [
    "E150 resp=13 resp2=80 into=....",  # the full-key READ: NOTFND RESP2 80 (#5092, X52)
    "G150 resp=0 resp2=0 into=200b",  # no 150: the first greater key
    "G200 resp=0 resp2=0 into=200b",  # the key itself
    "G301 resp=13 resp2=80 into=....",  # none greater: NOTFND, RESP2 80
    "R2 resp=0 resp2=0 into=200b",  # generic key "2": the first of 200 / 210 in key order
    "R21 resp=0 resp2=0 into=210c",
    "Q25 resp=0 resp2=0 into=300d",  # no key starting 25: the first greater
    "R4 resp=13 resp2=80 into=....",
    "Q4 resp=13 resp2=80 into=....",
    "Q0 resp=0 resp2=0 into=100a",
]


@needs_cc
def test_the_stub_read_gteq_and_generic_search_as_ibm_documents(tmp_path):
    """GTEQ: "the first record that has a greater key is retrieved"; GENERIC: the first KEYLENGTH bytes; NOTFND
    RESP2 80 when the search finds nothing. The file is out of key order on disk: the search is in key order."""
    (tmp_path / "f.dat").write_bytes(b"300d210c100a200b")
    (tmp_path / "files.cfg").write_text(f"F {tmp_path / 'f.dat'} 4 0 3\n", encoding="ascii")
    exe = _stub(tmp_path, _READ_SEARCH_MAIN)
    assert _run_stub(exe, tmp_path, *_READ_SEARCH_OPS) == _READ_SEARCH_WANT


@needs_javac
def test_cics_task_read_search_answers_as_the_stub_does(tmp_path):
    """CicsTask.readSearch over the same file and searches (the lookup as DetCics.Store.search does it)."""
    out = _cics_task(
        tmp_path,
        """
        java.util.TreeMap<String, String> f = new java.util.TreeMap<>(java.util.Map.of(
                "300", "300d", "210", "210c", "100", "100a", "200", "200b"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String op : new String[] {"E150", "G150", "G200", "G301", "R2", "R21", "Q25", "R4", "Q4", "Q0"}) {
            char o = op.charAt(0);
            String k = op.substring(1);
            boolean gteq = o == 'G' || o == 'Q';
            int n = o == 'R' || o == 'Q' ? k.length() : 3;
            CicsTask.FileRead<String> r = o == 'E' ? t.read("F", () -> java.util.Optional.ofNullable(f.get(k)))
                    : t.readSearch("F", false, () -> f.values().stream().filter(v -> {
                        int c = v.substring(0, n).compareTo(k.substring(0, n));
                        return c == 0 || gteq && c > 0;
                    }).findFirst());
            System.out.println(op + " resp=" + r.resp() + " resp2=" + r.resp2() + " into="
                    + (r.record() == null ? "...." : r.record()));
        }""",
    )
    assert out.splitlines() == _READ_SEARCH_WANT


_DELETE_GENERIC_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCDELT(gg_cics *c, char *rid, int kl);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char rid[4] = "???";
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        memcpy(c.name1, "F", 1);
        memset(c.flags, ' ', 40);
        memcpy(c.flags, "GENERIC", 7);
        memcpy(rid, argv[i], strlen(argv[i]) < 3 ? strlen(argv[i]) : 3);
        GGCDELT(&c, rid, (int)strlen(argv[i]));
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_delete_generic_deletes_every_record_with_the_generic_key(tmp_path):
    """#4771 zECS (ZECS003; IBM, EXEC CICS DELETE; X22): GENERIC deletes every record whose key starts with the KEYLENGTH
    bytes of RIDFLD; NOTFND RESP2 80 when none does; a KEYLENGTH not shorter than the key is INVREQ 25 (#5092,
    test_delete_invreq_5092.py), zero is refused by name."""
    (tmp_path / "f.dat").write_bytes(b"300d210c100a200b")
    (tmp_path / "files.cfg").write_text(f"F {tmp_path / 'f.dat'} 4 0 3\n", encoding="ascii")
    exe = _stub(tmp_path, _DELETE_GENERIC_MAIN)
    assert _run_stub(exe, tmp_path, "2", "2", "10", "4", "300") == [
        "2 resp=0 resp2=0", "2 resp=13 resp2=80", "10 resp=0 resp2=0", "4 resp=13 resp2=80",
        "300 resp=16 resp2=25"]  # fmt: skip
    assert (tmp_path / "f.dat").read_bytes() == b"300d"


@needs_javac
def test_cics_task_delete_generic_answers_as_the_stub_does(tmp_path):
    """#4771: CicsTask.delete with the det port's generic loop (search the generic key, remove what it finds, until
    none is left) over the same file and keys: the same RESP / RESP2 and the same records left."""
    out = _cics_task(
        tmp_path,
        """
        java.util.TreeMap<String, String> f = new java.util.TreeMap<>(java.util.Map.of(
                "300", "300d", "210", "210c", "100", "100a", "200", "200b"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String k : new String[] {"2", "2", "10", "4"}) {
            java.util.function.Supplier<java.util.Optional<String>> search =
                    () -> f.keySet().stream().filter(x -> x.startsWith(k)).findFirst();
            int resp = t.delete("F", search.get().isPresent(), () -> {
                java.util.Optional<String> found;
                while ((found = search.get()).isPresent()) f.remove(found.get());
            });
            System.out.println(k + " resp=" + resp + " resp2=" + t.resp2());
        }
        System.out.println(String.join("", f.values()));""",
    )
    assert out.splitlines() == ["2 resp=0 resp2=0", "2 resp=13 resp2=80", "10 resp=0 resp2=0", "4 resp=13 resp2=80",
                                "300d"]  # fmt: skip


@needs_javac
def test_cics_task_asktime_and_formattime_follow_the_clock(tmp_path):
    """ABSTIME is milliseconds since 00:00 on 1 January 1900 (IBM, EXEC CICS ASKTIME): 3867129015000 at
    2022-07-18 10:30:15, the value the translated COBOL computes under GnuCOBOL at the same clock."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("T", "ENTER", null, null)
                .withClock(java.time.LocalDateTime.parse("2022-07-18T10:30:15"));
        long abs = t.asktime();
        System.out.println(abs + " " + CicsTask.formatDate(abs, "YYYYMMDD", "-") + " " + CicsTask.formatTime(abs, ":")
                + " " + CicsTask.formatDate(abs, "MMDDYY", "/") + " " + CicsTask.formatDate(abs, "DDMMYYYY", ""));""",
    )
    assert out.split() == ["3867129015000", "2022-07-18", "10:30:15", "07/18/22", "18072022"]


@needs_javac
def test_cics_task_formattime_day_of_year_forms_and_binary_numbers(tmp_path):
    """#4415 slice 3 (X46): YYDDD / YYYYDDD / YYDDMM / YYYYDDMM and DAYCOUNT / DAYOFMONTH / DAYOFWEEK (Sunday=0) /
    MONTHOFYEAR / YEAR / MILLISECONDS, over the whole input class: the first instant (1900-01-01, day 1), a leap day, a
    non-leap and a leap year end (day 365 / 366), a century leap year; expected values from Python's datetime."""
    out = _cics_task(
        tmp_path,
        """
        long[] abs = {0L, 3867129015123L, 3918239999999L, 3912969600000L, 3944635200007L, 3160857600000L};
        for (long ab : abs) {
            System.out.println(CicsTask.formatDate(ab, "YYDDD", "/") + " " + CicsTask.formatDate(ab, "YYYYDDD", "/") + " "
                + CicsTask.formatDate(ab, "YYDDMM", "/") + " " + CicsTask.formatDate(ab, "YYYYDDMM", "") + " "
                + CicsTask.formatNumber(ab, "DAYCOUNT") + " " + CicsTask.formatNumber(ab, "DAYOFMONTH") + " "
                + CicsTask.formatNumber(ab, "DAYOFWEEK") + " " + CicsTask.formatNumber(ab, "MONTHOFYEAR") + " "
                + CicsTask.formatNumber(ab, "YEAR") + " " + CicsTask.formatNumber(ab, "MILLISECONDS"));
        }
        try { CicsTask.formatNumber(-1, "YEAR"); } catch (UnsupportedOperationException e) { System.out.println("refused"); }""",
    )
    assert out.splitlines() == [
        "00/001 1900/001 00/01/01 19000101 1 1 1 1 1900 0",
        "22/199 2022/199 22/18/07 20221807 44759 18 1 7 2022 123",
        "24/060 2024/060 24/29/02 20242902 45350 29 4 2 2024 999",
        "23/365 2023/365 23/31/12 20233112 45290 31 0 12 2023 0",
        "24/366 2024/366 24/31/12 20243112 45656 31 2 12 2024 7",
        "00/061 2000/061 00/01/03 20000103 36585 1 3 3 2000 0",
        "refused",
    ]


# ---- #4213: an ESDS browsed by relative byte address (STARTBR / READNEXT / READPREV ... RBA) ----------------------
_RBA_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCSTBR(gg_cics *c, char *rid, int kl); int GGCRDNX(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCRDPV(gg_cics *c, char *rid, int kl, char *into, int il); int GGCENBR(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    unsigned char rid[4] = {0, 0, 0, 0};
    char into[5];
    memset(&c, 0, sizeof c);
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0];
        memset(c.name1, ' ', 8);
        memcpy(c.name1, op == 'K' || op == 'k' ? "K" : "F", 1);
        memset(c.flags, ' ', 40);
        if (argv[i][1] == ':') {                                   /* the program sets RIDFLD: a fullword RBA */
            unsigned long v = strtoul(argv[i] + 2, NULL, 10);
            rid[0] = (unsigned char)(v >> 24); rid[1] = (unsigned char)(v >> 16);
            rid[2] = (unsigned char)(v >> 8); rid[3] = (unsigned char)v;
        }
        if (argv[i][1] == '*') memset(rid, 0xFF, 4);              /* X'FFFFFFFF' */
        memset(into, '.', 4);
        into[4] = 0;
        if (op == 'S' || op == 'K') { memcpy(c.flags, "EQUAL RBA", 9); GGCSTBR(&c, (char *)rid, 4); }
        if (op == 's') { memcpy(c.flags, "EQUAL", 5); GGCSTBR(&c, (char *)rid, 4); }   /* by key */
        if (op == 'N') { memcpy(c.flags, "RBA", 3); GGCRDNX(&c, (char *)rid, 4, into, 4); }
        if (op == 'P') { memcpy(c.flags, "RBA", 3); GGCRDPV(&c, (char *)rid, 4, into, 4); }
        if (op == 'n') GGCRDNX(&c, (char *)rid, 4, into, 4);                            /* by key */
        if (op == 'B') GGCENBR(&c);
        unsigned long v = ((unsigned long)rid[0] << 24) | ((unsigned long)rid[1] << 16) | ((unsigned long)rid[2] << 8) | rid[3];
        if (v == 0xFFFFFFFFUL) printf("%c resp=%d rid=FF into=%s\n", op, c.resp, into);
        else printf("%c resp=%d rid=%lu into=%s\n", op, c.resp, v, into);
        fflush(stdout);
    }
    return 0;
}
"""

# IBM CICS TS, EXEC CICS STARTBR / READNEXT / READPREV with RBA ("the record identification field specified in the
# RIDFLD option contains a relative byte address"; READNEXT "causes CICS to return the relative byte address of each
# retrieved record"); STARTBR EQUAL, the default of a direct ESDS browse; a RIDFLD of X'FF's at the end, for READPREV;
# READPREV right after STARTBR on the STARTBR's record; changing RIDFLD repositions (in the same form, an RBA).
_RBA_OPS = ["S:0", "N", "N", "N", "N", "P", "P", "P", "P", "S:4", "B", "S:4", "P", "B", "S*", "P", "P", "B",
            "S*", "N", "B", "S:0", "N", "N:8", "N", "B", "B"]  # fmt: skip
_RBA_EXPECTED = [
    "S resp=0 rid=0",  # RBA 0: the first record
    "N resp=0 rid=0 into=10aa",  # the STARTBR's record; RIDFLD is its RBA
    "N resp=0 rid=4 into=20bb",
    "N resp=0 rid=8 into=30cc",
    "N resp=20 rid=8",  # past the last: ENDFILE
    "P resp=0 rid=8 into=30cc",  # after a READNEXT: back to RIDFLD, the same record again
    "P resp=0 rid=4 into=20bb",
    "P resp=0 rid=0 into=10aa",
    "P resp=20 rid=0",  # before the first: ENDFILE
    "S resp=16 rid=4",  # a browse is active: INVREQ
    "B resp=0 rid=4",
    "S resp=0 rid=4",
    "P resp=0 rid=4 into=20bb",  # READPREV right after STARTBR: the record at the STARTBR's RBA
    "B resp=0 rid=4",
    "S resp=0 rid=FF",  # X'FFFFFFFF': the end, for READPREV
    "P resp=0 rid=8 into=30cc",
    "P resp=0 rid=4 into=20bb",
    "B resp=0 rid=4",
    "S resp=0 rid=FF",
    "N resp=20 rid=FF",  # READNEXT from the end: ENDFILE
    "B resp=0 rid=FF",
    "S resp=0 rid=0",
    "N resp=0 rid=0 into=10aa",
    "N resp=0 rid=8 into=30cc",  # RIDFLD changed to RBA 8: repositions there
    "N resp=20 rid=8",
    "B resp=0 rid=8",
    "B resp=16 rid=8",  # no browse: INVREQ
]


def _rba_files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"10aa20bb30cc")
    (work / "k.dat").write_bytes(b"10aa20bb30cc")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 0 ESDS\nK {work / 'k.dat'} 4 0 2\n", encoding="ascii")


@needs_cc
def test_the_stub_browses_an_esds_by_rba_as_cics_does(tmp_path):
    """An ESDS of three 4-byte records at RBAs 0, 4 and 8 (each record's byte offset: oracle_assumptions.md X13)."""
    _rba_files(tmp_path)
    exe = _stub(tmp_path, _RBA_MAIN)
    got = [ln.replace(" into=....", "") for ln in _run_stub(exe, tmp_path, *_RBA_OPS)]
    assert got == _RBA_EXPECTED


@needs_cc
@pytest.mark.parametrize(
    "ops, why",
    [
        (["S:2"], "STARTBR RBA 2 on F: no record starts there"),  # mid-record: IBM does not say what happens
        (["S:12"], "STARTBR RBA 12 on F: no record starts there"),  # past the end of the data
        (
            ["S:3000000000"],
            "STARTBR RBA 3000000000 on F: no record starts there",
        ),  # #5055: RBA above 2^31 (32-bit signed wrap)
        (["S:0", "N", "N:6"], "READNEXT RBA 6 on F: no record starts there"),
        (["s:0"], "STARTBR by key on F, an ESDS"),  # an ESDS browse is by RBA (or through a path)
        (["K:0"], "STARTBR RBA on K, not an ESDS"),  # a KSDS by RBA: not modelled
        (["S:0", "n"], "READNEXT by key in an RBA browse of F"),
    ],
)
def test_the_stub_refuses_an_rba_it_cannot_vouch_for(tmp_path, ops, why):
    """#4213: what IBM does not document stops the run (98, "... not modelled"), refused by name, never guessed."""
    _rba_files(tmp_path)
    exe = _stub(tmp_path, _RBA_MAIN)
    (tmp_path / "out").mkdir()
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    proc = subprocess.run([str(exe), *ops], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert proc.returncode == 98
    assert proc.stdout.splitlines()[-1] == f"{why}: not modelled"


@needs_javac
def test_cics_task_browses_an_esds_by_rba_as_the_stub_does(tmp_path):
    """The same RBA browse through CicsTask (withEsds, startbrRba / readnextRba / readprevRba): the same RESPs, RBAs
    and records; and the same refusals."""
    out = _cics_task(
        tmp_path,
        """
        java.util.List<byte[]> recs = new java.util.ArrayList<>();
        for (String r : new String[] {"10aa", "20bb", "30cc"}) recs.add(r.getBytes());
        CicsTask t = new CicsTask("T", "ENTER", null, null).withEsds("F", 4, recs);
        long rid = 0;
        String[] ops = {%s};
        for (String op : ops) {
            if (op.length() > 1) {
                rid = op.charAt(1) == '*' ? 0xFFFFFFFFL : Long.parseLong(op.substring(2));
            }
            int resp;
            String into = "";
            switch (op.charAt(0)) {
                case 'S': resp = t.startbrRba("F", rid); break;
                case 'N': case 'P': {
                    CicsTask.BrowsedRba b = op.charAt(0) == 'N' ? t.readnextRba("F", rid, 4) : t.readprevRba("F", rid, 4);
                    resp = b.resp();
                    if (b.record() != null) { rid = b.rba(); into = " into=" + new String(b.record()); }
                    break;
                }
                default: resp = t.endbr("F");
            }
            System.out.println(op.charAt(0) + " resp=" + resp + " rid=" + (rid == 0xFFFFFFFFL ? "FF" : rid) + into);
        }
        byte[] word = CicsTask.rbaBytes(168);
        System.out.println(CicsTask.rba(word) + " " + word.length + " " + CicsTask.rba(new byte[] {-1, -1, -1, -1}));
        for (Runnable r : new Runnable[] {() -> t.startbrRba("F", 2), () -> t.startbrRba("F", 12),
                                           () -> t.startbrRba("G", 0)}) {
            try { r.run(); System.out.println("no refusal"); }
            catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }
        }"""
        % ", ".join(f'"{o}"' for o in _RBA_OPS),
    )
    assert out.splitlines() == [
        *_RBA_EXPECTED,
        "168 4 4294967295",
        "STARTBR RBA 2 on F: no record starts there: not modelled",
        "STARTBR RBA 12 on F: no record starts there: not modelled",
        "STARTBR RBA on G, not an ESDS: not modelled",
    ]


@needs_javac
def test_cics_task_facades_run_their_task_in_the_region_joined_or_deployed(tmp_path):
    """#4343: a facade (handleTransaction, handleLink) gets its task from CicsTask.region() and runs it there. With
    nothing deployed, a region of the program alone: started from a cleared screen, the task's input is the transid
    typed; with a COMMAREA it is the whole record; a LINK elsewhere is PGMIDERR; returned() is the RETURN's COMMAREA.
    A deployed region shares one temporary storage across tasks and reaches its programs; a joined one (a harness's)
    wins on its thread until closed."""
    out = _cics_task(
        tmp_path,
        """
        java.util.function.Consumer<CicsTask> prog = task -> {
            String in = task.hasCommarea() ? task.commarea(StringBuilder.class).append("+").toString()
                    : task.receiveText(8).data();
            System.out.println(task.transid() + " calen=" + task.eibcalen() + " in=" + in + " link="
                    + task.link("OTHER") + " ts=" + task.writeqTs("Q", new byte[] {1}).item());
            task.returnTransid("TX01", new StringBuilder(in));
        };
        CicsTask.Region local = CicsTask.region();
        CicsTask first = local.transaction("TX01", null);
        local.run(first, "PROG", prog);
        System.out.println(first.returned(StringBuilder.class));
        CicsTask b = local.transaction("TX01", new StringBuilder("CA"));
        local.run(b, "PROG", prog);
        try {
            b.returned(String.class);
        } catch (IllegalStateException e) {
            System.out.println("refused: " + e.getMessage());
        }
        CicsTask.Programs both = new CicsTask.Programs() {
            public boolean defined(String p) {
                return p.equals("PROG") || p.equals("OTHER");
            }

            public void run(String p, CicsTask task) {
                if (p.equals("PROG")) {
                    prog.accept(task);
                } else {
                    task.returnTransid(null, null);
                }
            }
        };
        CicsTask.deploy(new CicsTask.LocalRegion(both, "T001", null));
        for (int i = 0; i < 2; i++) {
            CicsTask.Region r = CicsTask.region();
            CicsTask t = r.transaction("TX01", null);
            r.run(t, "PROG", prog);
        }
        CicsTask.Region mine = new CicsTask.LocalRegion(null, null,
                () -> java.time.LocalDateTime.of(2022, 7, 18, 10, 30));
        try (CicsTask.Joined j = CicsTask.join(mine)) {
            System.out.println(CicsTask.region() == mine);
            System.out.println(CicsTask.region().transaction("TX01", null).now());
        }
        System.out.println(CicsTask.region() != mine);
        CicsTask l = CicsTask.region().linked("PROG", new StringBuilder("L"));
        CicsTask.region().run(l, "PROG", prog);
        System.out.println(l.level() + " " + l.aid());""",
    )
    assert out.splitlines() == [
        "TX01 calen=0 in=TX01 link=PGMIDERR ts=1",  # a cleared screen: the transid typed; no other program
        "TX01",
        "TX01 calen=null in=CA+ link=PGMIDERR ts=2",  # the whole record; the region's one TS
        "refused: the task RETURNed a java.lang.StringBuilder, not a java.lang.String (no layout converts one into "
        "the other)",  # #4449: neither is laid out as bytes
        "TX01 calen=0 in=TX01 link=NORMAL ts=1",  # deployed: OTHER is reached, and one TS across tasks
        "TX01 calen=0 in=TX01 link=NORMAL ts=2",
        "true",
        "2022-07-18T10:30",  # the region's clock, not the JVM's
        "true",
        "CSMI calen=null in=L+ link=NORMAL ts=3",  # a LINK from outside: the mirror's task, the deployed region's TS
        "1 null",
    ]


@needs_javac
def test_a_syncpoint_in_a_program_linked_from_outside_the_region_is_refused(tmp_path):
    """#4437: IBM's SYNCPOINT / SYNCPOINT ROLLBACK raise INVREQ (RESP2 200) in a program LINKed from a remote system
    that did not give SYNCONRETURN. The region does not know how its client LINKed, so a program LINKed from outside
    (LocalRegion.linked: the mirror's task) refuses both, by name; a task the region starts itself commits and rolls
    back as before (NORMAL, the only outcome there)."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Region r = new CicsTask.LocalRegion(null, null, null);
        for (String cmd : new String[] {"SYNCPOINT", "ROLLBACK"}) {
            CicsTask l = r.linked("PROG", null);
            try {
                if (cmd.equals("SYNCPOINT")) l.syncpoint(); else l.rollback();
                System.out.println("ran");
            } catch (UnsupportedOperationException e) {
                System.out.println(e.getMessage());
            }
        }
        CicsTask t = r.transaction("TX01", null);
        t.rollback();
        CicsTask u = r.transaction("TX01", null);
        u.syncpoint();
        System.out.println("local ok");""",
    )
    assert out.splitlines() == [
        "SYNCPOINT in a program LINKed from outside the region: INVREQ (RESP2 200) unless the client LINKed with "
        "SYNCONRETURN, which the region does not know",
        "SYNCPOINT ROLLBACK in a program LINKed from outside the region: INVREQ (RESP2 200) unless the client LINKed "
        "with SYNCONRETURN, which the region does not know",
        "local ok",
    ]


# ---- #4270: channels and containers ---------------------------------------------------------------------
_CONT_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; } gg_cics;
int GGCPUTC(gg_cics *c, char *from); int GGCGETC(gg_cics *c, char *into); int GGCDELC(gg_cics *c);
int GGCASCH(gg_cics *c); int GGCTASK(gg_cics *c); int GGCLINK(gg_cics *c, char *area);
int GGCNEXT(gg_cics *c, char **area); int GGCLRET(gg_cics *c);
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static void op(const char *cont, const char *chan, const char *flags, int len) {
    blank(c.qname, 16, cont); blank(c.chan, 16, chan); blank(c.flags, 40, flags); c.len = len;
}
int main(void) {
    char into[16], *area = NULL;
    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); GGCNEXT(&c, &area);
    op("REQ", "", "", 4); GGCGETC(&c, into); printf("%d/%d ", c.resp, c.resp2);         /* no current channel */
    GGCASCH(&c); printf("[%.16s] ", c.chan);
    op("REQ", "CH1", "CHANNEL CHAR", 6); GGCPUTC(&c, "ABCDEF"); printf("%d ", c.resp);
    op("REQ", "CH1", "CHANNEL APPEND", 2); GGCPUTC(&c, "GH"); printf("%d ", c.resp);
    op("REQ", "CH1", "CHANNEL", -1); GGCPUTC(&c, "X"); printf("%d/%d ", c.resp, c.resp2);  /* LENGERR 1 */
    op("REQ", "", "", 1); GGCPUTC(&c, "X"); printf("%d/%d ", c.resp, c.resp2);             /* INVREQ 4 */
    op("REQ", "", "BIT", 1); GGCPUTC(&c, "X"); printf("%d/%d ", c.resp, c.resp2);          /* INVREQ 1 */
    blank(c.name1, 8, "SUB"); c.item = 0; c.len = 0; blank(c.flags, 40, "CHANNEL"); blank(c.chan, 16, "CH1");
    GGCLINK(&c, NULL); GGCNEXT(&c, &area);
    GGCASCH(&c); printf("[%.3s] ", c.chan);
    memset(into, '.', sizeof into);
    op("REQ", "", "", 16); GGCGETC(&c, into); printf("%d/%d/%.10s ", c.resp, c.len, into); /* the current channel */
    memset(into, '.', sizeof into);
    op("REQ", "", "", 3); GGCGETC(&c, into); printf("%d/%d/%d/%.5s ", c.resp, c.resp2, c.len, into);
    op("REQ", "", "NODATA", 0); GGCGETC(&c, into); printf("%d/%d ", c.resp, c.len);
    op("NONE", "", "", 4); GGCGETC(&c, into); printf("%d/%d ", c.resp, c.resp2);           /* CONTAINERERR 10 */
    op("REQ", "OTHER", "CHANNEL", 4); GGCGETC(&c, into); printf("%d/%d ", c.resp, c.resp2); /* CHANNELERR 2 */
    op("OUT", "", "", 2); GGCPUTC(&c, "OK"); printf("%d ", c.resp);
    op("REQ", "", "", 0); GGCDELC(&c); printf("%d ", c.resp);
    GGCLRET(&c);
    op("OUT", "CH1", "CHANNEL", 8); GGCGETC(&c, into); printf("%d/%d/%.2s ", c.resp, c.len, into);
    op("REQ", "CH1", "CHANNEL", 0); GGCDELC(&c); printf("%d/%d\n", c.resp, c.resp2);
    return 0;
}
"""


@needs_cc
def test_the_stub_channels_and_containers_follow_ibm(tmp_path):
    """#4270, IBM PUT / GET / DELETE CONTAINER (CHANNEL), LINK CHANNEL, ASSIGN CHANNEL: no current channel is INVREQ
    RESP2 4 (1 with a data type) and blanks; PUT creates the channel; APPEND appends; FLENGTH below zero is LENGERR
    RESP2 1; the LINKed program's current channel is the one passed, and what it puts and deletes its caller sees;
    GET truncates with LENGERR RESP2 11 and returns the container's length; NODATA; CONTAINERERR 10; CHANNELERR 2."""
    exe = _stub(tmp_path, _CONT_MAIN)
    out = _run_stub(exe, tmp_path)
    assert out == ["16/4 [                ] 0 0 22/1 16/4 16/1 [CH1] 0/8/ABCDEFGH.. 22/11/8/ABC.. 0/8 110/10 122/2 0 0 "
                   "0/2/OK 110/10"]  # fmt: skip


@needs_javac
def test_cics_task_channels_and_containers(tmp_path):
    """#4270: CicsTask's channels, as the stub's (above): the current channel through LINK / XCTL CHANNEL, the
    containers byte for byte, the conditions with their RESP2; a data type other than an existing container's is
    refused (IBM leaves it unsettled)."""
    out = _cics_task(
        tmp_path,
        """
        java.util.List<String> seen = new java.util.ArrayList<>();
        CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask s) {
                if (p.equals("XB")) {
                    seen.add("XB:" + s.assignChannel().strip() + ":" + s.getContainer(null, "OUT", 8).resp());
                    return;
                }
                CicsTask.ContainerResult g = s.getContainer(null, "REQ", 16);
                seen.add(s.assignChannel().strip() + ":" + g.resp() + "/" + g.length() + "/" + new String(g.data()));
                CicsTask.ContainerResult h = s.getContainer(null, "REQ", 3);
                seen.add(h.resp() + "/" + h.resp2() + "/" + h.length() + "/" + new String(h.data()));
                seen.add(s.getContainer(null, "REQ", -1).length() + " " + s.getContainer("OTHER", "REQ", 4).resp()
                        + " " + s.getContainer(null, "NONE", 4).resp2());
                s.putContainer(null, "OUT", "OK".getBytes(), 2, null, false);
                seen.add(s.deleteContainer(null, "REQ").resp());
                seen.add(s.xctlChannel("XB", "CH1"));
            }
        });
        System.out.println(t.getContainer(null, "REQ", 4).resp2() + " [" + t.assignChannel() + "]");
        System.out.println(t.putContainer("CH1", "REQ", "ABCDEF".getBytes(), 6, "CHAR", false).resp() + " "
                + t.putContainer("CH1", "REQ", "GH".getBytes(), 2, null, true).resp() + " "
                + t.putContainer("CH1", "REQ", new byte[0], -1, null, false).resp2() + " "
                + t.putContainer(null, "REQ", new byte[0], 0, "BIT", false).resp2());
        System.out.println(t.linkChannel("SUB", "CH1") + " " + seen);
        System.out.println(t.getContainer("CH1", "OUT", 8).resp() + " " + t.deleteContainer("CH1", "REQ").resp());
        try {
            t.putContainer("CH1", "OUT", new byte[0], 0, "CHAR", false);
        } catch (UnsupportedOperationException e) {
            System.out.println("refused");
        }
        System.out.println(t.events().get(0));""",
    )
    assert out.splitlines() == [
        "4 [                ]",
        "NORMAL NORMAL 1 1",
        "NORMAL [CH1:NORMAL/8/ABCDEFGH, LENGERR/11/8/ABC, 8 CHANNELERR 10, NORMAL, NORMAL, XB:CH1:NORMAL]",
        "NORMAL CONTAINERERR",
        "refused",
        "{event=LINK, target=SUB, length=0, commarea=null, resp=NORMAL, resp2=null, issuer=MAIN}",
    ]


@needs_javac
def test_cics_task_return_channel(tmp_path):
    """#5005 (X17), IBM EXEC CICS RETURN CHANNEL: the channel (created empty when absent) is made available to the next
    program and the task ends; below the highest logical level the command fails, INVREQ RESP2 2, and returns."""
    out = _cics_task(
        tmp_path,
        """
        java.util.List<String> seen = new java.util.ArrayList<>();
        CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask s) {
                int[] r = s.returnChannel("NEXT", "CH1");
                seen.add(r[0] + "/" + r[1] + " ended=" + s.ended());
            }
        });
        t.putContainer("CH1", "REQ", "AB".getBytes(), 2, null, false);
        System.out.println(t.linkChannel("SUB", "CH1") + " " + seen + " " + t.returnedChannel());
        int[] r = t.returnChannel("NEXT", "CH1");
        System.out.println(r[0] + "/" + r[1] + " " + t.ended() + " " + (t.returnedChannel() != null));
        System.out.println(t.events().get(t.events().size() - 1));""",
    )
    lines = out.splitlines()
    assert lines[0] == "NORMAL [16/2 ended=false] null"
    assert lines[1] == "0/0 true true"
    assert "transid=NEXT" in lines[2] and "channel=CH1" in lines[2] and "containers=[REQ]" in lines[2]


# ---- #4951: MOVE CONTAINER and the container browse ------------------------------------------------------
# One scenario, run on the stub and on CicsTask, which must print the same lines (IBM, EXEC CICS MOVE CONTAINER (CHANNEL),
# STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (CHANNEL)); what IBM leaves open is refused (register X42).
_MOVE_FULL_STRUCT = r"""
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
"""
_MOVE_STUB_MAIN = (
    r"""
#include <stdio.h>
#include <string.h>
"""
    + _MOVE_FULL_STRUCT
    + r"""
int GGCPUTC(gg_cics *c, char *from); int GGCGETC(gg_cics *c, char *into); int GGCMOVC(gg_cics *c);
int GGCSBRC(gg_cics *c); int GGCGNXC(gg_cics *c); int GGCEBRC(gg_cics *c); int GGCSYNC(gg_cics *c);
int GGCTASK(gg_cics *c); int GGCLINK(gg_cics *c, char *area); int GGCNEXT(gg_cics *c, char **area); int GGCLRET(gg_cics *c);
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static const char *nm(int r) {
    switch (r) { case 0: return "NORMAL"; case 16: return "INVREQ"; case 22: return "LENGERR"; case 83: return "END";
                 case 110: return "CONTAINERERR"; case 112: return "TOKENERR"; case 122: return "CHANNELERR"; }
    return "?";
}
static void say(const char *what) { printf("%s=%s/%d\n", what, nm(c.resp), c.resp2); }
static void put(const char *chan, const char *cont, const char *data, const char *flags) {
    blank(c.qname, 16, cont); blank(c.chan, 16, chan); blank(c.flags, 40, flags); c.len = (int)strlen(data);
    GGCPUTC(&c, (char *)data);
}
static void get(const char *what, const char *chan, const char *cont) {
    char into[16]; memset(into, '.', sizeof into);
    blank(c.qname, 16, cont); blank(c.chan, 16, chan); blank(c.flags, 40, chan[0] ? "CHANNEL" : ""); c.len = 16;
    GGCGETC(&c, into);
    printf("%s=%s/%d", what, nm(c.resp), c.resp2);
    if (c.resp == 0) printf("/%d/%.*s", c.len, c.len, into);
    printf("\n");
}
static void move(const char *what, const char *cont, const char *as, const char *chan, const char *tochan) {
    char fl[40] = "";
    blank(c.qname, 16, cont); blank(c.as, 16, as); blank(c.chan, 16, chan); blank(c.tochan, 16, tochan);
    if (chan[0]) strcat(fl, "CHANNEL ");
    if (tochan[0]) strcat(fl, "TOCHAN");
    blank(c.flags, 40, fl);
    GGCMOVC(&c); say(what);
}
static int start(const char *what, const char *chan) {
    blank(c.chan, 16, chan); blank(c.flags, 40, chan[0] ? "CHANNEL" : "");
    GGCSBRC(&c); printf("%s=%s/%d", what, nm(c.resp), c.resp2);
    if (c.resp == 0) printf("/token %d", c.num);
    printf("\n"); return c.num;
}
static void next(const char *what, int token) {
    c.num = token; GGCGNXC(&c); printf("%s=%s/%d", what, nm(c.resp), c.resp2);
    if (c.resp == 0) printf("/[%.*s]", (int)strcspn(c.qname, " "), c.qname);
    printf("\n");
}
static void end(const char *what, int token) { c.num = token; GGCEBRC(&c); say(what); }
int main(void) {
    char *area = NULL;
    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); GGCNEXT(&c, &area);
    move("move-no-channel", "A", "Q", "", "CH2");
    put("CH1", "A", "aa", "CHANNEL CHAR"); put("CH1", "B", "bb", "CHANNEL");
    move("rename", "A", "A2", "CH1", "CH1");
    get("get-old", "CH1", "A"); get("get-new", "CH1", "A2");
    move("to-new-channel", "B", "B", "CH1", "CH2");
    get("source-gone", "CH1", "B"); get("target", "CH2", "B");
    move("no-container", "X", "Y", "CH1", "CH3"); get("not-created", "CH3", "Y");
    move("no-channel", "B", "B", "NOPE", "CH2");
    put("CH2", "T", "tttt", "CHANNEL CHAR");
    move("overwrite", "A2", "T", "CH1", "CH2"); get("overwritten", "CH2", "T");
    int t1 = start("start", "CH2");
    next("n1", t1); next("n2", t1); next("n3", t1); next("n4", t1);
    end("end", t1); next("after-end", t1); end("end-again", t1); next("never-started", 99);
    start("start-no-channel", "NOPE");
    int t2 = start("start2", "CH2");
    put("CH2", "B", "xx", "CHANNEL");  /* the data changes, not the names */
    next("n1", t2);
    int t3 = start("start3", "CH2"); GGCSYNC(&c); next("after-syncpoint", t3);
    int t4 = start("start4", "CH2");
    blank(c.name1, 8, "SUB"); c.item = 0; c.len = 0; blank(c.flags, 40, "CHANNEL"); blank(c.chan, 16, "CH2");
    GGCLINK(&c, NULL); GGCNEXT(&c, &area);
    next("other-program", t4); int t5 = start("sub-start", "");
    end("sub-end", t5);
    GGCLRET(&c);
    next("owner", t4);
    return 0;
}
"""
)

_MOVE_EXPECTED = [
    "move-no-channel=INVREQ/4",
    "rename=NORMAL/0",
    "get-old=CONTAINERERR/10",
    "get-new=NORMAL/0/2/aa",
    "to-new-channel=NORMAL/0",
    "source-gone=CONTAINERERR/10",
    "target=NORMAL/0/2/bb",
    "no-container=CONTAINERERR/10",
    "not-created=CHANNELERR/2",
    "no-channel=CHANNELERR/2",
    "overwrite=NORMAL/0",
    "overwritten=NORMAL/0/2/aa",
    "start=NORMAL/0/token 1",
    "n1=NORMAL/0/[B]",
    "n2=NORMAL/0/[T]",
    "n3=END/2",
    "n4=END/2",
    "end=NORMAL/0",
    "after-end=TOKENERR/3",
    "end-again=TOKENERR/3",
    "never-started=TOKENERR/3",
    "start-no-channel=CHANNELERR/2",
    "start2=NORMAL/0/token 2",
    "n1=NORMAL/0/[B]",
    "start3=NORMAL/0/token 3",
    "after-syncpoint=TOKENERR/3",
    "start4=NORMAL/0/token 4",
    "other-program=TOKENERR/3",
    "sub-start=NORMAL/0/token 5",
    "sub-end=NORMAL/0",
    "owner=NORMAL/0/[B]",
]


@needs_cc
def test_the_stub_moves_containers_and_browses_a_channel(tmp_path):
    """#4951, IBM MOVE CONTAINER: the container leaves its channel and is AS in TOCHANNEL (made when absent, and not made
    by a move that raises a condition), overwriting an existing AS; INVREQ RESP2 4, CHANNELERR 2, CONTAINERERR 10.
    STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER: END RESP2 2 past the last, TOKENERR RESP2 3 for a token after ENDBROWSE,
    after a sync point, never given, or another program's; the order is creation order (ASSUMED, X42)."""
    out = _run_stub(_stub(tmp_path, _MOVE_STUB_MAIN), tmp_path)
    assert out == _MOVE_EXPECTED


@needs_javac
def test_cics_task_moves_containers_and_browses_a_channel_as_the_stub_does(tmp_path):
    """#4951: CicsTask answers the scenario above line for line."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask[] sub = new CicsTask[1];
        int[] tokens = new int[8];
        java.util.function.BiConsumer<String, CicsTask.ContainerResult> say = (what, r) -> System.out.println(what + "=" + r.resp() + "/" + r.resp2());
        CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask s) {
                CicsTask.ContainerResult g = s.getNextContainer(tokens[4]);
                System.out.println("other-program=" + g.resp() + "/" + g.resp2());
                CicsTask.ContainerResult b = s.startBrowseContainer(null);
                System.out.println("sub-start=" + b.resp() + "/" + b.resp2() + "/token " + b.length());
                say.accept("sub-end", s.endBrowseContainer(b.length()));
            }
        });
        java.util.function.BiConsumer<String, CicsTask.ContainerResult> got = (what, r) -> System.out.println(what + "=" + r.resp() + "/" + r.resp2()
                + (r.normal() ? "/" + r.length() + "/" + new String(r.data()) : ""));
        say.accept("move-no-channel", t.moveContainer(null, "A", "Q", "CH2"));
        t.putContainer("CH1", "A", "aa".getBytes(), 2, "CHAR", false);
        t.putContainer("CH1", "B", "bb".getBytes(), 2, null, false);
        say.accept("rename", t.moveContainer("CH1", "A", "A2", "CH1"));
        got.accept("get-old", t.getContainer("CH1", "A", 16));
        got.accept("get-new", t.getContainer("CH1", "A2", 16));
        say.accept("to-new-channel", t.moveContainer("CH1", "B", "B", "CH2"));
        got.accept("source-gone", t.getContainer("CH1", "B", 16));
        got.accept("target", t.getContainer("CH2", "B", 16));
        say.accept("no-container", t.moveContainer("CH1", "X", "Y", "CH3"));
        got.accept("not-created", t.getContainer("CH3", "Y", 16));
        say.accept("no-channel", t.moveContainer("NOPE", "B", "B", "CH2"));
        t.putContainer("CH2", "T", "tttt".getBytes(), 4, "CHAR", false);
        say.accept("overwrite", t.moveContainer("CH1", "A2", "T", "CH2"));
        got.accept("overwritten", t.getContainer("CH2", "T", 16));
        java.util.function.BiConsumer<String, Integer> next = (what, tok) -> {
            CicsTask.ContainerResult r = t.getNextContainer(tok);
            System.out.println(what + "=" + r.resp() + "/" + r.resp2() + (r.normal() ? "/[" + r.name().strip() + "]" : ""));
        };
        java.util.function.BiFunction<String, String, Integer> start = (what, ch) -> {
            CicsTask.ContainerResult r = t.startBrowseContainer(ch);
            System.out.println(what + "=" + r.resp() + "/" + r.resp2() + (r.normal() ? "/token " + r.length() : ""));
            return r.length();
        };
        int t1 = start.apply("start", "CH2");
        next.accept("n1", t1); next.accept("n2", t1); next.accept("n3", t1); next.accept("n4", t1);
        say.accept("end", t.endBrowseContainer(t1)); next.accept("after-end", t1);
        say.accept("end-again", t.endBrowseContainer(t1)); next.accept("never-started", 99);
        start.apply("start-no-channel", "NOPE");
        int t2 = start.apply("start2", "CH2");
        t.putContainer("CH2", "B", "xx".getBytes(), 2, null, false);
        next.accept("n1", t2);
        int t3 = start.apply("start3", "CH2");
        t.syncpoint();
        next.accept("after-syncpoint", t3);
        tokens[4] = start.apply("start4", "CH2");
        t.linkChannel("SUB", "CH2");
        next.accept("owner", tokens[4]);""",
    )
    assert out.splitlines() == _MOVE_EXPECTED


@needs_cc
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        ('put("CH1", "A", "a", "CHANNEL"); move("m", "A", "A", "CH1", "CH1");', "MOVE CONTAINER onto itself"),
        (
            'put("CH1", "A", "a", "CHANNEL CHAR"); put("CH1", "B", "b", "CHANNEL"); move("m", "A", "B", "CH1", "CH1");',
            "onto a container of the other data type",
        ),
        (
            'put("CH1", "A", "a", "CHANNEL"); int t = start("s", "CH1"); put("CH1", "B", "b", "CHANNEL"); next("n", t);',
            "browsed channel changed during the browse",
        ),
        (
            'put("CH1", "A", "a", "CHANNEL"); int t = start("s", "CH1"); blank(c.qname, 16, "A"); blank(c.chan, 16, "CH1"); '
            'blank(c.flags, 40, "CHANNEL"); GGCDELC(&c); next("n", t);',
            "browsed channel changed during the browse",
        ),
        ('start("s", "");', "STARTBROWSE CONTAINER with no channel"),
        ('put("CH1", " A", "a", "CHANNEL");', "illegal CONTAINER name and a channel not in scope"),
    ],
)
def test_the_stub_refuses_what_ibm_leaves_open_on_move_and_browse(tmp_path, steps, why):
    """#4951 (X42): a move onto itself or onto the other data type, a browse of a channel that changed, a browse with no
    channel (IBM: the BTS form) and a name with an embedded blank are refused, never guessed."""
    main = (
        _MOVE_STUB_MAIN.replace("int GGCSYNC(gg_cics *c);", "int GGCSYNC(gg_cics *c); int GGCDELC(gg_cics *c);").split(
            "int main(void) {"
        )[0]
        + "int main(void) {\n    char *area = NULL;\n"
        + '    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); GGCNEXT(&c, &area);\n'
        + steps
        + "\n    return 0;\n}\n"
    )
    exe = _stub(tmp_path, main)
    (tmp_path / "out").mkdir(exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    proc = subprocess.run([str(exe)], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert proc.returncode != 0 and why in proc.stderr + proc.stdout


@needs_javac
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        (
            't.putContainer("CH1", "A", "a".getBytes(), 1, null, false); t.moveContainer("CH1", "A", "A", "CH1");',
            "MOVE CONTAINER onto itself",
        ),
        (
            't.putContainer("CH1", "A", "a".getBytes(), 1, "CHAR", false); t.putContainer("CH1", "B", "b".getBytes(), 1, null, false);'
            ' t.moveContainer("CH1", "A", "B", "CH1");',
            "onto a container of the other data type",
        ),
        (
            't.putContainer("CH1", "A", "a".getBytes(), 1, null, false); int k = t.startBrowseContainer("CH1").length();'
            ' t.putContainer("CH1", "B", "b".getBytes(), 1, null, false); t.getNextContainer(k);',
            "browsed channel changed during the browse",
        ),
        (
            't.putContainer("CH1", "A", "a".getBytes(), 1, null, false); int k = t.startBrowseContainer("CH1").length();'
            ' t.deleteContainer("CH1", "A"); t.getNextContainer(k);',
            "browsed channel changed during the browse",
        ),
        ("t.startBrowseContainer(null);", "STARTBROWSE CONTAINER with no channel"),
        (
            't.putContainer("CH1", " A", "a".getBytes(), 1, null, false);',
            "illegal CONTAINER name and a channel not in scope",
        ),
    ],
)
def test_cics_task_refuses_what_ibm_leaves_open_on_move_and_browse(tmp_path, steps, why):
    """#4951 (X42): the same refusals as the stub's."""
    out = _cics_task(
        tmp_path,
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN");\n'
        "try {\n" + steps + '\nSystem.out.println("no refusal");\n} catch (UnsupportedOperationException e) {\n'
        'System.out.println("refused: " + e.getMessage());\n}',
    )
    assert out.startswith("refused: ") and why in out, out


# ---- #5005: DELETE CHANNEL and QUERY CHANNEL -------------------------------------------------------------
# One scenario, run on the stub and on CicsTask, which must print the same lines (IBM, EXEC CICS DELETE CHANNEL, QUERY
# CHANNEL: CHANNELERR RESP2 2 for a channel not in scope); what IBM leaves open is refused (register X44).
_CHAN_EXTERNS = "int GGCDELH(gg_cics *c); int GGCQCHN(gg_cics *c); int GGCDELC(gg_cics *c);\nint GGCSYNC(gg_cics *c);"
_CHAN_HELPERS = r"""
static void delch(const char *what, const char *chan) { blank(c.chan, 16, chan); GGCDELH(&c); say(what); }
static void query(const char *what, const char *chan) {
    blank(c.chan, 16, chan); c.num = -7; GGCQCHN(&c);
    printf("%s=%s/%d", what, nm(c.resp), c.resp2);
    if (c.resp == 0) printf("/count %d", c.num); else if (c.num != -7) printf("/count written");
    printf("\n");
}
static void delc(const char *what, const char *chan, const char *cont) {
    blank(c.qname, 16, cont); blank(c.chan, 16, chan); blank(c.flags, 40, "CHANNEL"); GGCDELC(&c); say(what);
}
static void link_sub(const char *chan) {
    char *area = NULL;
    blank(c.name1, 8, "SUB"); c.item = 0; c.len = 0; blank(c.flags, 40, "CHANNEL"); blank(c.chan, 16, chan);
    GGCLINK(&c, NULL); GGCNEXT(&c, &area);
}
"""


def _chan_stub_main(body: str) -> str:
    head = _MOVE_STUB_MAIN.replace("int GGCSYNC(gg_cics *c);", _CHAN_EXTERNS).split("int main(void) {")[0]
    return (
        head + _CHAN_HELPERS + "int main(void) {\n    char *area = NULL;\n"
        '    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); GGCNEXT(&c, &area);\n' + body + "\n    return 0;\n}\n"
    )


_CHAN_STUB_SCENARIO = r"""
    query("q-none", "CH1"); delch("d-none", "CH1");
    put("CH1", "A", "aa", "CHANNEL CHAR"); put("CH1", "B", "bb", "CHANNEL"); put("CH2", "X", "xx", "CHANNEL");
    query("q-ch1", "CH1"); query("q-ch2", "CH2");
    delc("delc", "CH1", "A"); query("q-after-delc", "CH1");
    delch("d-ch1", "CH1");
    get("get-gone", "CH1", "B"); query("q-gone", "CH1"); delch("d-again", "CH1");
    put("CH1", "N", "n", "CHANNEL"); query("q-recreated", "CH1"); get("old-b", "CH1", "B");
    put("CH3", "Z", "z", "CHANNEL"); delc("delc-z", "CH3", "Z"); query("q-empty", "CH3"); delch("d-empty", "CH3");
    query("q-empty-gone", "CH3");
    link_sub("CH2");
    query("sub-query", "CH2"); query("sub-other", "CH1"); delch("sub-del-other", "CH1");
    put("CH2", "S", "s", "CHANNEL"); query("sub-query2", "CH2");
    GGCLRET(&c);
    query("q-after", "CH2"); delch("d-ch2", "CH2"); query("q-ch2-gone", "CH2"); get("x-gone", "CH2", "X");
"""

_CHAN_EXPECTED = [
    "q-none=CHANNELERR/2",
    "d-none=CHANNELERR/2",
    "q-ch1=NORMAL/0/count 2",
    "q-ch2=NORMAL/0/count 1",
    "delc=NORMAL/0",
    "q-after-delc=NORMAL/0/count 1",
    "d-ch1=NORMAL/0",
    "get-gone=CHANNELERR/2",
    "q-gone=CHANNELERR/2",
    "d-again=CHANNELERR/2",
    "q-recreated=NORMAL/0/count 1",
    "old-b=CONTAINERERR/10",
    "delc-z=NORMAL/0",
    "q-empty=NORMAL/0/count 0",
    "d-empty=NORMAL/0",
    "q-empty-gone=CHANNELERR/2",
    "sub-query=NORMAL/0/count 1",
    "sub-other=CHANNELERR/2",
    "sub-del-other=CHANNELERR/2",
    "sub-query2=NORMAL/0/count 2",
    "q-after=NORMAL/0/count 2",
    "d-ch2=NORMAL/0",
    "q-ch2-gone=CHANNELERR/2",
    "x-gone=CHANNELERR/2",
]


@needs_cc
def test_the_stub_deletes_and_queries_channels_as_ibm_documents(tmp_path):
    """#5005, IBM DELETE CHANNEL / QUERY CHANNEL: the count of containers (0 for an emptied channel, then the channel still
    exists), a deleted channel and its containers gone (CHANNELERR RESP2 2 for it afterwards; a PUT makes a new, empty one),
    a channel outside the program's scope CHANNELERR RESP2 2 (a LINKed program sees only the channel it was passed)."""
    out = _run_stub(_stub(tmp_path, _chan_stub_main(_CHAN_STUB_SCENARIO)), tmp_path)
    assert out == _CHAN_EXPECTED


@needs_javac
def test_cics_task_deletes_and_queries_channels_as_the_stub_does(tmp_path):
    """#5005: CicsTask answers the scenario above line for line."""
    out = _cics_task(
        tmp_path,
        """
        java.util.function.BiConsumer<String, CicsTask.ContainerResult> say = (what, r) -> System.out.println(what + "=" + r.resp() + "/" + r.resp2());
        java.util.function.BiConsumer<String, CicsTask.ContainerResult> count = (what, r) -> System.out.println(what + "=" + r.resp() + "/" + r.resp2()
                + (r.normal() ? "/count " + r.length() : (r.length() != -1 ? "/count written" : "")));
        CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask s) {
                count.accept("sub-query", s.queryChannel("CH2"));
                count.accept("sub-other", s.queryChannel("CH1"));
                say.accept("sub-del-other", s.deleteChannel("CH1"));
                s.putContainer("CH2", "S", "s".getBytes(), 1, null, false);
                count.accept("sub-query2", s.queryChannel("CH2"));
            }
        });
        java.util.function.BiConsumer<String, CicsTask.ContainerResult> got = (what, r) -> System.out.println(what + "=" + r.resp() + "/" + r.resp2()
                + (r.normal() ? "/" + r.length() + "/" + new String(r.data()) : ""));
        count.accept("q-none", t.queryChannel("CH1")); say.accept("d-none", t.deleteChannel("CH1"));
        t.putContainer("CH1", "A", "aa".getBytes(), 2, "CHAR", false); t.putContainer("CH1", "B", "bb".getBytes(), 2, null, false);
        t.putContainer("CH2", "X", "xx".getBytes(), 2, null, false);
        count.accept("q-ch1", t.queryChannel("CH1")); count.accept("q-ch2", t.queryChannel("CH2"));
        say.accept("delc", t.deleteContainer("CH1", "A")); count.accept("q-after-delc", t.queryChannel("CH1"));
        say.accept("d-ch1", t.deleteChannel("CH1"));
        got.accept("get-gone", t.getContainer("CH1", "B", 16)); count.accept("q-gone", t.queryChannel("CH1"));
        say.accept("d-again", t.deleteChannel("CH1"));
        t.putContainer("CH1", "N", "n".getBytes(), 1, null, false); count.accept("q-recreated", t.queryChannel("CH1"));
        got.accept("old-b", t.getContainer("CH1", "B", 16));
        t.putContainer("CH3", "Z", "z".getBytes(), 1, null, false); say.accept("delc-z", t.deleteContainer("CH3", "Z"));
        count.accept("q-empty", t.queryChannel("CH3")); say.accept("d-empty", t.deleteChannel("CH3"));
        count.accept("q-empty-gone", t.queryChannel("CH3"));
        t.linkChannel("SUB", "CH2");
        count.accept("q-after", t.queryChannel("CH2")); say.accept("d-ch2", t.deleteChannel("CH2"));
        count.accept("q-ch2-gone", t.queryChannel("CH2")); got.accept("x-gone", t.getContainer("CH2", "X", 16));""",
    )
    assert out.splitlines() == _CHAN_EXPECTED


@needs_cc
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        (
            'put("CH1", "A", "a", "CHANNEL"); int t = start("s", "CH1"); delch("d", "CH1"); next("n", t);',
            "browsed channel changed during the browse",
        ),
        (
            'put("CH2", "A", "a", "CHANNEL"); link_sub("CH2"); delch("d", "CH2");',
            "DELETE CHANNEL of the current channel",
        ),
        ('delch("d", " A");', "channel name"),
        ('query("q", " A");', "channel name"),
        ('delch("d", "");', "channel name"),
    ],
)
def test_the_stub_refuses_what_ibm_leaves_open_on_delete_and_query_channel(tmp_path, steps, why):
    """#5005 (X44): the current channel (IBM's RESP2 4 / 5 / 6 all fit it, unranked), a browse of a channel that was deleted
    and a blank or embedded-blank name are refused, never guessed."""
    exe = _stub(tmp_path, _chan_stub_main(steps))
    (tmp_path / "out").mkdir(exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    proc = subprocess.run([str(exe)], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert proc.returncode != 0 and why in proc.stderr + proc.stdout


@needs_javac
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        (
            't.putContainer("CH1", "A", "a".getBytes(), 1, null, false); int k = t.startBrowseContainer("CH1").length();'
            ' t.deleteChannel("CH1"); t.getNextContainer(k);',
            "browsed channel changed during the browse",
        ),
        (
            't.putContainer("CH2", "A", "a".getBytes(), 1, null, false); t.linkChannel("SUB", "CH2");',
            "DELETE CHANNEL of the current channel",
        ),
        ('t.deleteChannel(" A");', "channel name"),
        ('t.queryChannel(" A");', "channel name"),
        ('t.deleteChannel("");', "channel name"),
    ],
)
def test_cics_task_refuses_what_ibm_leaves_open_on_delete_and_query_channel(tmp_path, steps, why):
    """#5005 (X44): the same refusals as the stub's."""
    out = _cics_task(
        tmp_path,
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {\n'
        "    public boolean defined(String p) { return true; }\n"
        '    public void run(String p, CicsTask s) { s.deleteChannel("CH2"); }\n});\n'
        "try {\n" + steps + '\nSystem.out.println("no refusal");\n} catch (UnsupportedOperationException e) {\n'
        'System.out.println("refused: " + e.getMessage());\n}',
    )
    assert out.startswith("refused: ") and why in out, out


# ---- #4270 slice 2: START AFTER / AT, the data options, ENVDEFERR, IOERR ---------------------------------------
_IC2_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCSTRT(gg_cics *c, char *from); int GGCRTRV(gg_cics *c, char *into);
#define NG (-999999999)
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static void start(const char *how, int h, int m, int s, int num, const char *reqid, int from) {
    blank(c.name1, 8, "GT02"); blank(c.name2, 8, ""); blank(c.qname, 16, reqid); blank(c.flags, 40, how);
    c.hours = h; c.mins = m; c.secs = s; c.num = num; c.item = from; c.len = 3;
    blank(c.rtran, 4, "GT03"); blank(c.rterm, 4, "T001"); blank(c.rqueue, 8, "QNAME");
    GGCSTRT(&c, "ABC");
    printf("%d/%d ", c.resp, c.resp2);
}
int main(void) {
    char into[8];
    start("AFTER", NG, 1, NG, 0, "", 0);           /* MINUTES(1): 000100 */
    start("AFTER", NG, 90, NG, 0, "", 0);          /* MINUTES alone up to 5999: 013000 */
    start("AFTER", 1, 90, NG, 0, "", 0);           /* with HOURS, MINUTES 0-59: INVREQ 5 */
    start("AFTER", 100, NG, NG, 0, "", 0);         /* INVREQ 4 */
    start("AFTER", NG, 1, 60, 0, "", 0);           /* INVREQ 6 */
    start("AT", 25, NG, NG, 0, "", 0);             /* a later day: tomorrow 01:00 */
    start("TIME", 0, 0, 0, 250000, "", 0);         /* the same as TIME */
    start("INTERVAL RTRANSID QUEUE", 0, 0, 0, 0, "R1", 1);
    start("INTERVAL", 0, 0, 0, 0, "R1", 1);        /* the REQID of this task's own START with FROM, again: IOERR */
    memset(into, '.', sizeof into); blank(c.rtran, 4, ""); blank(c.rqueue, 8, "");
    blank(c.flags, 40, "INTO RTRANSID QUEUE"); c.len = 8; GGCRTRV(&c, into);
    printf("%d/%d/%.4s/%.4s/%.8s ", c.resp, c.len, into, c.rtran, c.rqueue);
    blank(c.flags, 40, "RTERMID"); GGCRTRV(&c, into); printf("%d ", c.resp);  /* not given on its START */
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_start_after_at_and_the_data_options_follow_ibm(tmp_path):
    """#4270 slice 2, IBM EXEC CICS START / RETRIEVE, "Expiration times": AFTER / AT ranges (one option alone or a
    combination) with INVREQ RESP2 4 / 5 / 6; an hours component over 23 is a later day; a REQID this task used with
    FROM, used again with FROM, is IOERR; RETRIEVE returns RTRANSID / QUEUE and is ENVDEFERR for an option its START
    did not give."""
    exe = _stub(tmp_path, _IC2_MAIN)
    (tmp_path / "transactions.cfg").write_text("GT02\n")
    (tmp_path / "retrieve_001.bin").write_bytes(b"ALPHA")
    (tmp_path / "retrieve_001.opt").write_text(f"from=1 rtransid={b'GT03'.hex()} queue={b'QNAME'.hex()}\n")
    (tmp_path / "retrieve_002.opt").write_text(f"from=0 rtransid={b'GT04'.hex()}\n")
    out = subprocess.run([str(exe)], env={"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path),
                                          "GGCICS_NOW": "2026-03-02T10:00:00"},
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    assert out.split() == ["0/0", "0/0", "16/5", "16/4", "16/6", "0/0", "0/0", "0/0", "17/0",
                           "0/5/ALPH/GT03/QNAME", "56"]  # fmt: skip
    events = (tmp_path / "events.txt").read_text().splitlines()
    assert "interval=000100" in events[0] and "expires=2026-03-02T10:01:00" in events[0]
    assert "interval=013000" in events[1] and "interval= " in events[2] and "resp2=5" in events[2]
    assert "time=250000" in events[5] and "expires=2026-03-03T01:00:00" in events[5]
    assert "expires=2026-03-03T01:00:00" in events[6]
    assert events[7].endswith(f"rtransid={b'GT03'.hex().upper()} queue={b'QNAME'.hex().upper()}")
    assert events[9].endswith(f"into=1 rtransid={b'GT03'.hex().upper()} queue={b'QNAME'.hex().upper()}")
    assert " resp=56 len=-1 copied=0 into=0" in events[10]


@needs_javac
def test_cics_task_start_after_at_and_the_data_options(tmp_path):
    """#4270 slice 2: CicsTask's START / RETRIEVE as the stub's (above), and what IBM leaves open refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GT01", "ENTER", null, null).withClock(java.time.LocalDateTime.of(2026, 3, 2, 10, 0))
                .withStartData(java.util.List.of(new CicsTask.StartData("ALPHA".getBytes(), "GT03", null, "QNAME"),
                        new CicsTask.StartData(null, "GT04", null, null)));
        StringBuilder b = new StringBuilder();
        for (CicsTask.StartResult r : java.util.List.of(t.startRequest("GT02").after(null, 1, null).issue(),
                t.startRequest("GT02").after(null, 90, null).issue(), t.startRequest("GT02").after(1, 90, null).issue(),
                t.startRequest("GT02").after(100, null, null).issue(), t.startRequest("GT02").after(null, 1, 60).issue(),
                t.startRequest("GT02").at(25, null, null).issue(), t.startRequest("GT02").time(250000).issue(),
                t.startRequest("GT02").reqid("R1").from("ABC".getBytes()).rtransid("GT03").queue("QNAME").issue(),
                t.startRequest("GT02").reqid("R1").from("ABC".getBytes()).issue())) {
            b.append(r.resp()).append('/').append(r.resp2()).append('/').append(r.expires()).append(' ');
        }
        System.out.println(b.toString().trim());
        CicsTask.RetrieveResult r = t.retrieve(8, true, false, true);
        System.out.println(r.resp() + " " + r.length() + " " + new String(r.data()) + " " + r.rtransid() + " "
                + r.queue() + " " + t.retrieve(null, false, true, false).resp());
        try {
            t.retrieve(8);
        } catch (UnsupportedOperationException e) {
            System.out.println("refused after ENVDEFERR");
        }
        try {
            t.startRequest("GT02").reqid("R1").issue();
        } catch (UnsupportedOperationException e) {
            System.out.println("refused REQID reuse");
        }
        for (java.util.Map<String, Object> e : t.events().subList(0, 3)) {
            System.out.println(e.get("interval") + " " + e.get("resp2"));
        }""",
    )
    assert out.splitlines() == [
        "NORMAL/0/2026-03-02T10:01 NORMAL/0/2026-03-02T11:30 INVREQ/5/null INVREQ/4/null INVREQ/6/null "
        "NORMAL/0/2026-03-03T01:00 NORMAL/0/2026-03-03T01:00 NORMAL/0/2026-03-02T10:00 IOERR/0/null",
        "NORMAL 5 ALPHA GT03 QNAME ENVDEFERR",
        "refused after ENVDEFERR",
        "refused REQID reuse",
        "000100 null",
        "013000 null",
        "null 5",
    ]


def test_scheduler_passes_each_starts_data_options_as_its_record():
    """#4270 slice 2: a START's RTRANSID / RTERMID / QUEUE travel with its FROM data as one record; a START with none
    of them (nor FROM) stores none (the started task's RETRIEVE: ENDDATA)."""
    import cics_crucible as runner

    assert runner._record({"data": None, "rtransid": None, "rtermid": None, "queue": None}) is None
    assert runner._record({"data": b"X", "rtransid": "GT03"}) == {"data": b"X", "rtransid": "GT03", "rtermid": None,
                                                                  "queue": None}  # fmt: skip
    assert runner._named("resp=0 rtransid=47543033 queue=", ("rtransid", "rtermid", "queue")) == {
        "rtransid": "GT03",
        "queue": "",
    }


_RUN_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCRUNT(gg_cics *c, char *child);
static gg_cics c;
int main(void) {
    char child[17] = "................";
    memset(c.name1, ' ', 8); memcpy(c.name1, "GT24", 4); GGCRUNT(&c, child); printf("%d/%d/%.16s ", c.resp, c.resp2, child);
    memset(c.name1, ' ', 8); memcpy(c.name1, "NONE", 4); GGCRUNT(&c, child); printf("%d/%d\n", c.resp, c.resp2);
    return 0;
}
"""


@needs_cc
def test_the_stub_run_transid_attaches_a_child_or_is_transiderr(tmp_path):
    """#4270 slice 2, IBM RUN TRANSID: a defined transaction gets a child token in CHILD's 16 bytes; an undefined one
    is TRANSIDERR RESP2 1. The child is the runner's to schedule (the event)."""
    exe = _stub(tmp_path, _RUN_MAIN)
    (tmp_path / "transactions.cfg").write_text("GT24\n")
    out = subprocess.run([str(exe)], env={"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path)},
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    assert out.split() == ["0/0/GGCHILD000000001", "28/1"]
    assert (tmp_path / "events.txt").read_text().splitlines() == [
        "001 RUN pgm= transid=GT24 resp=0 resp2=0",
        "002 RUN pgm= transid=NONE resp=28 resp2=1",
    ]


@needs_javac
def test_cics_task_run_transid_as_the_stubs_and_a_childs_retrieve_is_refused(tmp_path):
    """#4270 slice 2: CicsTask.runTransid as the stub's GGCRUNT; a RETRIEVE in a RUN child is refused (undocumented)."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GT21", "ENTER", null, null).withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public boolean transaction(String tr) {
                return tr.equals("GT24");
            }

            public void run(String p, CicsTask s) {
            }
        });
        CicsTask.RunResult r1 = t.runTransid("GT24");
        CicsTask.RunResult r2 = t.runTransid("NONE");
        System.out.println(r1.resp() + "/" + r1.resp2() + "/" + r1.child() + " " + r2.resp() + "/" + r2.resp2() + "/"
                + r2.child());
        System.out.println(new java.util.TreeMap<>(t.events().get(1)));
        try {
            new CicsTask("GT24", null, null, null).withRunChild(true).retrieve(4);
        } catch (UnsupportedOperationException e) {
            System.out.println("refused");
        }""",
    )
    assert out.splitlines() == ["NORMAL/0/GGCHILD000000001 TRANSIDERR/1/null",
                                "{event=RUN, resp=TRANSIDERR, resp2=1, transid=NONE}", "refused"]  # fmt: skip


# ---- #4270 slice 3: ASSIGN STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD ------------------------------------------
_ASGN_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCASGN(gg_cics *c);
static gg_cics c;
static void ask(const char *what) {
    memset(c.name2, ' ', 8); memcpy(c.name2, what, strlen(what)); c.num = -1;
    GGCASGN(&c);
    for (int i = 0; i < 8; i++) if (c.name1[i] == ' ') c.name1[i] = '_';
    printf("%d/%d/%.8s/%d ", c.resp, c.resp2, c.name1, c.num);
}
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) ask(argv[i]);
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_assign_startcode_userid_and_the_terminal_facts(tmp_path):
    """#4270 slice 3, IBM EXEC CICS ASSIGN: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD from what the runner states;
    TERMCHK is INVREQ RESP2 5 for a task with no terminal; an unstated fact, or a RUN child's STARTCODE, is refused."""
    exe = _stub(tmp_path, _ASGN_MAIN)
    base = {"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path), "GGCICS_USERID": "CICSUSER",
            "GGCICS_SCREEN": "24 80"}  # fmt: skip

    def run(env, *asks):
        return subprocess.run([str(exe), *asks], env={**base, **env}, capture_output=True, text=True)

    out = run({"GGCICS_STARTCODE": "TD", "GGCICS_FACILITY": "T001"}, "STARTCOD", "USERID", "TERMCHK", "FACILITY",
              "SCRNHT", "SCRNWD").stdout  # fmt: skip
    assert out.split() == ["0/0/TD______/-1", "0/0/CICSUSER/-1", "0/0/________/-1", "0/0/T001____/-1",
                           "0/0/________/24", "0/0/________/80"]  # fmt: skip
    assert run({"GGCICS_STARTCODE": "SD", "GGCICS_FACILITY": ""}, "STARTCOD", "TERMCHK").stdout.split() == [
        "0/0/SD______/-1",
        "16/5/________/-1",
    ]
    # #5126: a terminal nobody states is refused (the port refuses too), not taken as "none"
    unterminal = run({"GGCICS_STARTCODE": "SD"}, "TERMCHK")
    assert unterminal.returncode == 98 and "ASSIGN TERMCHK: not stated" in unterminal.stdout
    unstated = run({}, "STARTCOD")
    assert unstated.returncode == 98 and "ASSIGN STARTCOD: not stated" in unstated.stdout
    child = run({"GGCICS_STARTCODE": "S", "GGCICS_RUNCHILD": "1"}, "STARTCOD")
    assert child.returncode == 98 and "RUN TRANSID child" in child.stdout


@needs_javac
def test_cics_task_assign_startcode_userid_and_the_terminal_facts(tmp_path):
    """#4270 slice 3: CicsTask's ASSIGN as the stub's (above)."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GT31", "ENTER", null, null).withTermid("T001").withStartcode("TD")
                .withUserid("CICSUSER").withScreen(24, 80);
        System.out.println("[" + t.assignStartcode() + "][" + t.assignUserid() + "][" + t.assignFacility() + "] "
                + t.assignTerminalResp() + " " + t.assignScreen(false) + "x" + t.assignScreen(true));
        CicsTask s = new CicsTask("GT32", null, null, null).withTermid(null).withStartcode("S");
        System.out.println("[" + s.assignStartcode() + "] " + s.assignTerminalResp());
        for (CicsTask u : new CicsTask[] {new CicsTask("GT33", null, null, null),
                new CicsTask("GT34", null, null, null).withTermidIfStated("")}) {
            try {
                u.assignTerminalResp();
            } catch (IllegalStateException e) {
                System.out.println("unstated terminal");
            }
        }
        try {
            s.assignFacility();
        } catch (IllegalStateException e) {
            System.out.println("no facility");
        }
        try {
            s.assignUserid();
        } catch (IllegalStateException e) {
            System.out.println("unstated");
        }
        try {
            new CicsTask("GT24", null, null, null).withRunChild(true).withStartcode("S").assignStartcode();
        } catch (UnsupportedOperationException e) {
            System.out.println("refused");
        }""",
    )
    assert out.splitlines() == [
        "[TD][CICSUSER][T001] 0 24x80",
        "[S ] 16",
        "unstated terminal",
        "unstated terminal",
        "no facility",
        "unstated",
        "refused",
    ]


_DEED_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCDEED(gg_cics *c, char *field, int flen);
int GGCINQT(gg_cics *c);
int GGCSETT(gg_cics *c);
static gg_cics c;
int main(int argc, char **argv) {
    char f[64];
    if (strcmp(argv[1], "deedit") == 0) {
        memset(f, ' ', sizeof f);
        memcpy(f, argv[2], strlen(argv[2]));
        c.num = argc > 4 ? atoi(argv[4]) : atoi(argv[3]);
        GGCDEED(&c, f, atoi(argv[3]));
        printf("%d/%d/[%.*s]\n", c.resp, c.resp2, atoi(argv[3]), f);
        return 0;
    }
    memset(c.name1, ' ', 8);
    memcpy(c.name1, argv[2], strlen(argv[2]));
    if (strcmp(argv[1], "set") == 0) { c.num = atoi(argv[3]); GGCSETT(&c); }
    else { c.num = -1; GGCINQT(&c); }
    printf("%d/%d/%d\n", c.resp, c.resp2, c.num);
    return 0;
}
"""


@needs_cc
def test_the_stub_bif_deedit_and_the_terminal_uctranst(tmp_path):
    """#4415 slice 1 (register X26), IBM EXEC CICS BIF DEEDIT / INQUIRE TERMINAL / SET TERMINAL: DEEDIT in the region's
    EBCDIC page (IBM's two examples, the negative zone, a zoned rightmost byte, LENGTH below 1 is LENGERR); a field with
    no digit left or beyond 7-bit ASCII is refused. UCTRANST: the CVDA the runner states; TERMIDERR RESP2 1 / 23, INVREQ
    RESP2 43; unstated, or another terminal's, refused."""
    exe = _stub(tmp_path, "#include <stdlib.h>\n" + _DEED_MAIN)
    base = {"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path)}

    def run(env, *args):
        return subprocess.run([str(exe), *args], env={**base, **env}, capture_output=True, text=True)  # noqa: S603

    for field, n, want in (("14-6704/B", "9", "00146704B"), ("$25.68", "9", "000002568"), ("123-", "4", "012L"),
                           ("1.5CR", "5", "0001N"), ("A", "1", "A"), ("ab12cd3C", "8", "0000123C")):  # fmt: skip
        assert run({}, "deedit", field, n).stdout.strip() == f"0/0/[{want}]", field
    assert run({}, "deedit", "x7", "2", "0").stdout.strip() == "22/0/[x7]"
    for bad, why in (("abc", "no digit left"), ("\xe91", "7-bit ASCII")):
        got = run({}, "deedit", bad, "3" if bad == "abc" else "2")
        assert got.returncode == 98 and why in got.stdout, bad
    terminal = {"GGCICS_FACILITY": "T001", "GGCICS_UCTRANST": "UCTRAN"}
    assert run(terminal, "inq", "T001").stdout.strip() == "0/0/450"
    assert run(terminal, "set", "T001", "451").stdout.strip() == "0/0/451"
    assert run(terminal, "set", "T001", "999").stdout.strip() == "16/43/999"
    (tmp_path / "terminals.cfg").write_text("T001\n", encoding="ascii")
    assert run(terminal, "inq", "ZZZZ").stdout.strip() == "11/1/-1"
    assert run(terminal, "set", "ZZZZ", "450").stdout.strip() == "11/23/450"
    unstated = run({"GGCICS_FACILITY": "T001"}, "inq", "T001")
    assert unstated.returncode == 98 and "UCTRANST: not stated" in unstated.stdout


@needs_javac
def test_cics_task_uctranst_and_deedit_as_the_stub_does(tmp_path):
    """#4415: CicsTask's INQUIRE / SET TERMINAL UCTRANST as the stub's (above): the stated CVDA, SET changes it, INVREQ
    RESP2 43 for a bad CVDA, TERMIDERR for a terminal the region lacks, a terminal RECEIVE after a SET refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("HC41", "ENTER", null, null).withTermid("T001").withUctranst("UCTRAN")
                .withPrograms(new CicsTask.Programs() {
                    public boolean defined(String p) { return true; }
                    public void run(String p, CicsTask k) { }
                    public boolean terminal(String x) { return x.equals("T001"); }
                });
        System.out.println(java.util.Arrays.toString(t.inquireUctranst("T001")));
        System.out.println(java.util.Arrays.toString(t.setUctranst("T001", 451)));
        System.out.println(java.util.Arrays.toString(t.inquireUctranst("T001")));
        System.out.println(java.util.Arrays.toString(t.setUctranst("T001", 999)));
        System.out.println(java.util.Arrays.toString(t.inquireUctranst("ZZZZ")) + java.util.Arrays.toString(t.setUctranst("ZZZZ", 450)));
        try {
            t.receiveText(8);
        } catch (UnsupportedOperationException e) {
            System.out.println("refused");
        }
        try {
            new CicsTask("HC41", "ENTER", null, null).withTermid("T001").inquireUctranst("T001");
        } catch (IllegalStateException e) {
            System.out.println("unstated");
        }
        System.out.println(CicsTask.deeditResp(0) + " " + CicsTask.deeditResp(1));
        System.out.println(java.util.Arrays.toString(CicsTask.formattimeCheck(-1)) + java.util.Arrays.toString(CicsTask.formattimeCheck(0)));""",
    )
    assert out.splitlines() == ["[0, 0, 450]", "[0, 0]", "[0, 0, 451]", "[16, 43]", "[11, 1, 0][11, 23]", "refused",
                                "unstated", "22 0", "[16, 1][0, 0]"]  # fmt: skip


_X29_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCDELQ(gg_cics *c);
int GGCINQA(gg_cics *c);
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCXCNT(gg_cics *c);
static gg_cics c;
int main(int argc, char **argv) {
    memset(c.qname, ' ', 16);
    memset(c.name1, ' ', 8);
    memset(c.flags, ' ', 40);
    if (strcmp(argv[1], "delq") == 0) {
        memcpy(c.qname, argv[2], strlen(argv[2]));
        GGCDELQ(&c);
        printf("%d/%d\n", c.resp, c.resp2);
    } else if (strcmp(argv[1], "zeros") == 0) {
        memset(c.qname, 0, 8);
        GGCDELQ(&c);
        printf("%d/%d\n", c.resp, c.resp2);
    } else if (strcmp(argv[1], "inqa") == 0) {
        memcpy(c.flags, argv[2], strlen(argv[2]));
        GGCINQA(&c);
        if (strcmp(argv[2], "ODFACILTYPE") == 0) printf("%d/%d/%d\n", c.resp, c.resp2, c.num);
        else printf("%d/%d/[%.8s]\n", c.resp, c.resp2, c.name1);
    } else {
        memcpy(c.qname, argv[2], strlen(argv[2]));
        if (argc > 3) memcpy(c.name1, argv[3], strlen(argv[3]));
        if (argc > 4) c.num = atoi(argv[4]);
        unsigned char vb[4] = {0}, incb[4] = {0, 0, 0, 1};
        if (strcmp(argv[1], "gcnt") == 0) {
            GGCGCNT(&c, vb, 4, incb, 4, 0);
            c.num = ((int)vb[0] << 24) | ((int)vb[1] << 16) | ((int)vb[2] << 8) | vb[3];
        } else if (strcmp(argv[1], "dcnt") == 0) {
            if (argc > 4) {
                unsigned int n = (unsigned int)atoi(argv[4]);
                vb[0] = (n >> 24) & 255; vb[1] = (n >> 16) & 255; vb[2] = (n >> 8) & 255; vb[3] = n & 255;
                GGCDCNT(&c, vb, 4, NULL, 0, NULL, 0);
            } else {
                GGCDCNT(&c, NULL, 0, NULL, 0, NULL, 0);
            }
        } else if (strcmp(argv[1], "xcnt") == 0) {
            GGCXCNT(&c);
        } else {
            GGCQCNT(&c, vb, 4, NULL, 0, NULL, 0);
            c.num = ((int)vb[0] << 24) | ((int)vb[1] << 16) | ((int)vb[2] << 8) | vb[3];
        }
        printf("%d/%d/%d\n", c.resp, c.resp2, c.num);
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_deleteq_ts_inquire_association_and_query_counter(tmp_path):
    """#4415 slice 2 (register X29), IBM EXEC CICS DELETEQ TS / INQUIRE ASSOCIATION / QUERY COUNTER: DELETEQ TS removes
    the whole queue (QIDERR RESP 44 when it is not there, INVREQ for a name of binary zeros, RESP2 0); INQUIRE
    ASSOCIATION answers the five origin values the runner states (the facility type as its CVDA), refused unstated;
    QUERY COUNTER answers a counter's value and leaves it, INVREQ RESP2 201 for one that is not there, a value beyond a
    fullword refused."""
    exe = _stub(tmp_path, _X29_MAIN)
    ts = tmp_path / "tsroot"
    hexname = "5131"  # "Q1"
    (ts / hexname).mkdir(parents=True)
    (ts / hexname / "000001.bin").write_bytes(b"\xc1")
    (ts / hexname / "000002.bin").write_bytes(b"\xc2")
    (ts / hexname / "next").write_text("1\n", encoding="ascii")

    def run(env, *args, check=True):
        base = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path), **env}
        return subprocess.run([str(exe), *args], env=base, capture_output=True, text=True, check=check)  # noqa: S603

    with_ts = {"GGCICS_TS": str(ts)}
    assert run(with_ts, "delq", "Q1").stdout.strip() == "0/0"
    assert not (ts / hexname).exists()  # (the items and the NEXT position went with it)
    assert run(with_ts, "delq", "Q1").stdout.strip() == "44/0"  # QIDERR
    assert run(with_ts, "zeros").stdout.strip() == "16/0"  # INVREQ: "the queue name is all binary zeroes"
    origin = {"GGCICS_ORIGIN": "GTCICS01,CICSUSER,T001,GTNET,TERMINAL"}
    for want, out in (("ODAPPLID", "0/0/[GTCICS01]"), ("ODUSERID", "0/0/[CICSUSER]"), ("ODFACILNAME", "0/0/[T001    ]"),
                      ("ODNETWORKID", "0/0/[GTNET   ]"), ("ODFACILTYPE", "0/0/213")):  # fmt: skip
        assert run(origin, "inqa", want).stdout.strip() == out, want
    unstated = run({}, "inqa", "ODAPPLID", check=False)
    assert unstated.returncode == 98 and "origin data is not stated" in unstated.stdout
    bad = run({"GGCICS_ORIGIN": "A,B,C,D,NOSUCH"}, "inqa", "ODFACILTYPE", check=False)
    assert bad.returncode == 98 and "facility type" in bad.stdout
    (tmp_path / "counters.cfg").write_text("GENAPOOL GENACNT 41\n- PLAIN 7\nBIG BIGCNT 4294967296\n", encoding="ascii")
    assert run({}, "qcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/41"
    assert run({}, "qcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/41"  # (unchanged: not a GET)
    assert run({}, "qcnt", "PLAIN").stdout.strip() == "0/0/7"
    assert run({}, "qcnt", "NOPE", "GENAPOOL").stdout.strip() == "16/201/0"
    big = run({}, "qcnt", "BIGCNT", "BIG", check=False)
    assert (
        big.returncode == 0 and big.stdout.strip() == "22/2/0"
    )  # #4770 (X30): LENGERR RESP2 2 (2**32), the low 32 bits


@needs_cc
def test_the_stub_defines_gets_and_deletes_named_counters(tmp_path):
    """#4270 (register X30), IBM EXEC CICS DEFINE / GET / DELETE COUNTER: DEFINE creates a counter (VALUE, else zero),
    INVREQ RESP2 202 for one that exists; GET answers the value then adds one, and INVREQ RESP2 201 -- not NOTFND --
    for one that is not there; DELETE removes it (INVREQ 201 when it is not there); a pool outside IBM's characters is
    INVREQ 403, a counter name 404 (not for DELETE); a VALUE below zero and a blank name are refused."""
    exe = _stub(tmp_path, _X29_MAIN)

    def run(*args, check=True):
        base = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path)}
        return subprocess.run([str(exe), *args], env=base, capture_output=True, text=True, check=check)  # noqa: S603

    assert run("gcnt", "GENACNT", "GENAPOOL").stdout.strip() == "16/201/0"  # (IBM lists no NOTFND)
    assert run("xcnt", "GENACNT", "GENAPOOL").stdout.strip() == "16/201/0"
    assert run("dcnt", "GENACNT", "GENAPOOL", "11").stdout.strip() == "0/0/11"
    assert run("dcnt", "GENACNT", "GENAPOOL", "5").stdout.strip() == "16/202/5"  # duplicate: the first value stays
    assert run("dcnt", "GENACNT", "", "0").stdout.strip() == "0/0/0"  # the same name in another pool (8 blanks)
    assert run("qcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/11"
    assert run("gcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/11"
    assert run("gcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/12"
    assert run("xcnt", "GENACNT", "GENAPOOL").stdout.strip() == "0/0/0"
    assert run("qcnt", "GENACNT", "GENAPOOL").stdout.strip() == "16/201/0"
    assert run("qcnt", "GENACNT").stdout.strip() == "0/0/0"  # (the other pool's, untouched)
    assert run("dcnt", "genacnt", "GENAPOOL", "1").stdout.strip() == "16/404/1"
    assert run("dcnt", "1CNT", "GENAPOOL", "1").stdout.strip() == "16/404/1"
    assert run("dcnt", "A-B", "GENAPOOL", "1").stdout.strip() == "16/404/1"
    assert run("dcnt", "A_1$#@", "BAD POOL", "1").stdout.strip() == "16/403/1"
    assert run("xcnt", "genacnt", "GENAPOOL").stdout.strip() == "16/201/0"  # (IBM's DELETE page lists no 404)
    assert run("xcnt", "GENACNT", "gena").stdout.strip() == "16/403/0"
    neg = run("dcnt", "NEGCNT", "GENAPOOL", "-1", check=False)
    assert neg.returncode == 98 and "VALUE below zero" in neg.stdout
    blank = run("dcnt", "", "GENAPOOL", "1", check=False)  # (an empty argv word is a name of blanks)
    assert blank.returncode == 98 and "blank name" in blank.stdout


@needs_javac
def test_cics_task_deleteq_ts_inquire_association_and_query_counter_as_the_stub_does(tmp_path):
    """#4415 slice 2: CicsTask answers as the stub does (above): DELETEQ TS the whole queue and its NEXT position, QIDERR /
    INVREQ; INQUIRE ASSOCIATION the stated origin (8 characters, the facility type's CVDA), refused unstated; QUERY COUNTER
    the value unchanged, INVREQ RESP2 201, a value beyond a fullword LENGERR (#4770, X30)."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.TempStorage ts = new CicsTask.TempStorage().seed("Q1", java.util.List.of(new byte[] {1}, new byte[] {2}));
        CicsTask t = new CicsTask("HC41", "ENTER", null, null).withTempStorage(ts)
                .withCounters(new java.util.HashMap<>(java.util.Map.of("GENAPOOL/GENACNT", 41L, "/PLAIN", 7L,
                        "BIG/BIGCNT", 4294967296L)));
        t.readqTsNext("Q1", 8);
        System.out.println(t.deleteqTs("Q1") + " " + t.readqTs("Q1", 1, 8).resp() + " " + t.deleteqTs("Q1"));
        System.out.println(t.deleteqTs(new String(new char[] {0, 0, 0})));
        t.withOrigin("GTCICS01", "CICSUSER", "T001", "GTNET", "TERMINAL");
        CicsTask.Origin o = t.inquireAssociation();
        System.out.println("[" + o.applid() + "][" + o.userid() + "][" + o.facilname() + "][" + o.networkid() + "] "
                + o.faciltype());
        try {
            new CicsTask("HC41", "ENTER", null, null).inquireAssociation();
        } catch (IllegalStateException e) {
            System.out.println("unstated");
        }
        try {
            t.withOrigin("A", "B", "C", "D", "NOSUCH");
        } catch (IllegalArgumentException e) {
            System.out.println("bad type");
        }
        System.out.println(java.util.Arrays.toString(t.queryCounter("GENAPOOL", "GENACNT"))
                + java.util.Arrays.toString(t.queryCounter("GENAPOOL", "GENACNT"))
                + java.util.Arrays.toString(t.queryCounter("", "PLAIN"))
                + java.util.Arrays.toString(t.queryCounter("GENAPOOL", "NOPE")));
        System.out.println(java.util.Arrays.toString(t.getCounter("GENAPOOL", "NOPE"))
                + java.util.Arrays.toString(t.getCounter("GENAPOOL", "GENACNT"))
                + java.util.Arrays.toString(t.getCounter("GENAPOOL", "GENACNT")));
        System.out.println(java.util.Arrays.toString(t.defineCounter("GENAPOOL", "GENACNT", 5))
                + java.util.Arrays.toString(t.defineCounter("GENAPOOL", "NEWCNT", 0))
                + java.util.Arrays.toString(t.defineCounter("", "GENACNT", 3))
                + java.util.Arrays.toString(t.defineCounter("BAD POOL", "X", 1))
                + java.util.Arrays.toString(t.defineCounter("GENAPOOL", "x", 1))
                + java.util.Arrays.toString(t.defineCounter("GENAPOOL", "1X", 1)));
        System.out.println(java.util.Arrays.toString(t.deleteCounter("GENAPOOL", "NEWCNT"))
                + java.util.Arrays.toString(t.deleteCounter("GENAPOOL", "NEWCNT"))
                + java.util.Arrays.toString(t.deleteCounter("gena", "NEWCNT"))
                + java.util.Arrays.toString(t.queryCounter("", "GENACNT")));
        for (Runnable bad : new Runnable[] {() -> t.defineCounter("GENAPOOL", "NEG", -1), () -> t.getCounter("", "  ")}) {
            try {
                bad.run();
            } catch (UnsupportedOperationException e) {
                System.out.println("refused " + e.getMessage().contains("below zero") + " " + e.getMessage().contains("blank"));
            }
        }
        System.out.println(java.util.Arrays.toString(t.queryCounter("BIG", "BIGCNT")));""",
    )
    assert out.splitlines() == ["0 QIDERR 44", "16", "[GTCICS01][CICSUSER][T001    ][GTNET   ] 213", "unstated",
                                "bad type", "[0, 0, 41][0, 0, 41][0, 0, 7][16, 201, 0]",
                                "[16, 201, 0][0, 0, 41][0, 0, 42]", "[16, 202][0, 0][0, 0][16, 403][16, 404][16, 404]",
                                "[0, 0][16, 201][16, 403][0, 0, 3]", "refused true false", "refused false true",
                                "[22, 2, 0]"]  # fmt: skip


_X32_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCURIB(gg_cics *c);
int GGCURIP(gg_cics *c, char *area, int len);
int GGCWTO(gg_cics *c, char *from);
static gg_cics c;
static void step(const char *what) {
    memset(c.flags, ' ', 40);
    memcpy(c.flags, what, strlen(what));
}
int main(int argc, char **argv) {
    char name[8], path[258], tran[4];
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "wto") == 0) {
            c.len = (int)strlen(argv[i + 1]);
            GGCWTO(&c, argv[++i]);
            printf("wto %d/%d\n", c.resp, c.resp2);
            continue;
        }
        step(argv[i]);
        GGCURIB(&c);
        printf("%s %d/%d", argv[i], c.resp, c.resp2);
        if (strcmp(argv[i], "NEXT") == 0 && c.resp == 0) {
            memset(path, '#', sizeof path);
            step("URIMAP"); GGCURIP(&c, name, 8);
            step("PATH"); GGCURIP(&c, path, 257);
            step("TRANSACTION"); GGCURIP(&c, tran, 4);
            printf(" [%.8s] [%.255s] [%.4s]", name, path, tran);
            printf(" tail=%c%c", path[255], path[256]);
        }
        printf("\n");
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_inquire_urimap_browse_and_write_operator(tmp_path):
    """#4270 zECS (register X32), IBM INQUIRE URIMAP (browse) / WRITE OPERATOR: START opens the browse (ILLOGIC RESP2 1 when one
    is open), NEXT returns the stated definitions in order (name 8, PATH 255, TRANSACTION 4, blank-padded, an area longer
    than IBM's length keeps its tail) then END RESP2 2, END closes it; the definitions unstated, and a NEXT / END with no
    browse, are refused; WRITE OPERATOR records its text, refusing one IBM reformats."""
    exe = _stub(tmp_path, _X32_MAIN)
    cfg = tmp_path / "urimaps.cfg"
    cfg.write_text("ZCEXAMPL ZC01 /zecs/*\nZCPLAIN - /plain\n", encoding="ascii")

    def run(*args, env=None, check=True):
        base = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out"),
                "GGCICS_URIMAPS": str(cfg), **(env or {})}  # fmt: skip
        (tmp_path / "out").mkdir(exist_ok=True)
        return subprocess.run([str(exe), *args], env=base, capture_output=True, text=True, check=check)  # noqa: S603

    out = run("START", "START", "NEXT", "NEXT", "NEXT", "END").stdout.splitlines()
    assert out[0] == "START 0/0" and out[1] == "START 21/1"  # ILLOGIC RESP2 1: a browse is already in progress
    assert out[2].startswith("NEXT 0/0 [ZCEXAMPL] [/zecs/*") and out[2].endswith(
        "[ZC01] tail=##"
    )  # (the 256th-257th bytes: the program's own, untouched)
    assert out[3].startswith("NEXT 0/0 [ZCPLAIN ] [/plain") and out[3].endswith(
        "[    ] tail=##"
    )  # no transaction: blanks
    assert out[4] == "NEXT 83/2" and out[5] == "END 0/0"  # END RESP2 2: no more resource definitions of this type
    for args in (("NEXT",), ("END",)):
        bad = run(*args, check=False)
        assert bad.returncode == 98 and "no browse started" in bad.stdout
    cfg.write_text("", encoding="ascii")
    assert run("START", "NEXT", "END").stdout.splitlines() == ["START 0/0", "NEXT 83/2", "END 0/0"]
    unstated = subprocess.run(
        [str(exe), "START"],
        env={**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )  # noqa: S603
    assert unstated.returncode == 98 and "URIMAP definitions are not stated" in unstated.stdout
    assert run("wto", "zECS start ZXAA for ZCAA").stdout.strip() == "wto 0/0"
    events = (tmp_path / "out" / "events.txt").read_text(encoding="ascii")
    assert "WRITE-OPERATOR" in events and "len=24" in events
    for text in ("DFH1234 something", "DFHAA1234 more", "x" * 114):
        refused = run("wto", text, check=False)
        assert refused.returncode == 98 and "IBM reformats" in refused.stdout, text
    assert run("wto", "DFHx plain").stdout.strip() == "wto 0/0"  # (not DFHnnnn / DFHaannnn)


@needs_javac
def test_cics_task_inquire_urimap_browse_and_write_operator_as_the_stub_does(tmp_path):
    """#4270 zECS (X32): CicsTask answers as the stub does (above): the stated definitions in order, blank-padded; ILLOGIC
    RESP2 1 for a second START; END RESP2 2 past the last; NEXT / END with no browse and unstated definitions refused;
    WRITE OPERATOR recorded as an event, a text IBM reformats refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("HC41", "ENTER", null, null).withUrimaps(java.util.List.of(
                new String[] {"ZCEXAMPL", "ZC01", "/zecs/*"}, new String[] {"ZCPLAIN", "", "/plain"}));
        System.out.println(java.util.Arrays.toString(t.inquireUrimapStart()) + java.util.Arrays.toString(t.inquireUrimapStart()));
        for (int i = 0; i < 3; i++) {
            int[] r = t.inquireUrimapNext();
            System.out.println(java.util.Arrays.toString(r) + (r[0] == 0 ? "[" + t.urimapName() + "][" + t.urimapPath().strip()
                    + "|" + t.urimapPath().length() + "][" + t.urimapTransaction() + "]" : ""));
        }
        System.out.println(java.util.Arrays.toString(t.inquireUrimapEnd()));
        for (Runnable bad : new Runnable[] {t::inquireUrimapEnd, () -> t.inquireUrimapNext(),
                () -> new CicsTask("HC41", "ENTER", null, null).inquireUrimapStart(),
                () -> t.writeOperator("DFH1234 something"), () -> t.writeOperator("x".repeat(114))}) {
            try {
                bad.run();
            } catch (UnsupportedOperationException e) {
                System.out.println(e.getMessage());
            }
        }
        System.out.println(t.writeOperator("DFHx plain") + " " + t.writeOperator("zECS start ZXAA"));
        System.out.println(t.events().stream().filter(e -> "WRITE-OPERATOR".equals(e.get("event"))).map(e -> e.get("text"))
                .collect(java.util.stream.Collectors.toList()));
        // #5859: TEXTLENGTH (0-690, else INVREQ RESP2 1), ROUTECODES / NUMROUTES (codes 1-28, else INVREQ RESP2 3)
        String rc = "\u0001\u0011\u001d";
        for (Object[] w : new Object[][] {{"hello world", 5, rc, 2}, {"hi", 691, null, null}, {"hi", -1, null, null},
                {"hi", 2, rc, 3}, {"hi", 2, "\u0000", 1}, {"hi", 0, rc, 1}, {"hi", null, "\u001c", 1}}) {
            System.out.println(java.util.Arrays.toString(t.writeOperator((String) w[0], (Integer) w[1], (String) w[2], (Integer) w[3])));
        }
        for (Runnable bad : new Runnable[] {() -> t.writeOperator("abc", 4, null, null),
                () -> t.writeOperator("abc", null, rc, 0), () -> t.writeOperator("abc", null, rc, 4),
                () -> t.writeOperator("DFH1234 x", 3, null, null)}) {
            try {
                bad.run();
                System.out.println("accepted");
            } catch (UnsupportedOperationException e) {
                System.out.println(e.getMessage());
            }
        }
        System.out.println(t.events().stream().filter(e -> "WRITE-OPERATOR".equals(e.get("event"))).map(e -> e.get("text"))
                .collect(java.util.stream.Collectors.toList()));""",
    )
    assert out.splitlines() == [
        "[0, 0][21, 1]", "[0, 0][ZCEXAMPL][/zecs/*|255][ZC01]", "[0, 0][ZCPLAIN ][/plain|255][    ]", "[83, 2]", "[0, 0]",
        "INQUIRE URIMAP NEXT or END with no browse started: not modelled",
        "INQUIRE URIMAP NEXT or END with no browse started: not modelled",
        "the installed URIMAP definitions are not stated (withUrimaps): not modelled",
        "WRITE OPERATOR text IBM reformats: not modelled", "WRITE OPERATOR text IBM reformats: not modelled",
        "0 0", "[DFHx plain, zECS start ZXAA]",
        "[0, 0]", "[16, 1]", "[16, 1]", "[16, 3]", "[16, 3]", "[0, 0]", "[0, 0]",
        "WRITE OPERATOR TEXTLENGTH past the text area: not modelled",
        "WRITE OPERATOR NUMROUTES IBM leaves open: not modelled",
        "WRITE OPERATOR NUMROUTES IBM leaves open: not modelled",
        "accepted",  # (TEXTLENGTH 3 cuts "DFH1234 x" to "DFH": not a CICS message)
        "[DFHx plain, zECS start ZXAA, hello, , hi, DFH]"]  # fmt: skip


_X34_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCURIB(gg_cics *c);
int GGCURIP(gg_cics *c, char *area, int len);
int GGCINQP(gg_cics *c);
static gg_cics c;
static void put(char *dst, int n, const char *what) {
    memset(dst, ' ', n);
    memcpy(dst, what, strlen(what));
}
int main(int argc, char **argv) {
    char path[255], tran[4];
    for (int i = 1; i + 1 < argc; i += 2) {
        put(c.name1, 8, argv[i + 1]);
        c.num = -1;
        if (strcmp(argv[i], "prog") == 0) {
            GGCINQP(&c);
            printf("prog %s %d/%d num=%d\n", argv[i + 1], c.resp, c.resp2, c.num);
            continue;
        }
        put(c.flags, 40, "DIRECT");
        GGCURIB(&c);
        printf("uri %s %d/%d", argv[i + 1], c.resp, c.resp2);
        if (c.resp == 0) {
            put(c.flags, 40, "PATH"); GGCURIP(&c, path, 255);
            put(c.flags, 40, "TRANSACTION"); GGCURIP(&c, tran, 4);
            printf(" [%.10s] [%.4s]", path, tran);
        }
        printf("\n");
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_inquire_urimap_direct_and_program_status(tmp_path):
    """#4768 zECS (register X34), IBM INQUIRE URIMAP (the direct form): URIMAP(name) reads that stated definition (PATH,
    TRANSACTION as a browse NEXT's), NOTFND RESP2 3 "The URIMAP cannot be found" otherwise, and it does not disturb an
    open browse; INQUIRE PROGRAM STATUS: ENABLED (CVDA 23) for a defined program, nothing for PGMIDERR."""
    exe = _stub(tmp_path, _X34_MAIN)
    (tmp_path / "urimaps.cfg").write_text("ZCEXAMPL ZC01 /zecs/*\nZCPLAIN - /plain\n", encoding="ascii")
    (tmp_path / "programs.cfg").write_text("ZECS001\n", encoding="ascii")
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out"),
           "GGCICS_URIMAPS": str(tmp_path / "urimaps.cfg")}  # fmt: skip
    (tmp_path / "out").mkdir()
    out = subprocess.run([str(exe), "uri", "ZCPLAIN", "uri", "ZCEXAMPL", "uri", "ZCNONE", "uri", "zcplain",
                          "prog", "ZECS001", "prog", "ZCETTL"], env=env, capture_output=True, text=True,
                         check=True).stdout.splitlines()  # noqa: S603  # fmt: skip
    assert out == ["uri ZCPLAIN 0/0 [/plain    ] [    ]", "uri ZCEXAMPL 0/0 [/zecs/*   ] [ZC01]", "uri ZCNONE 13/3",
                   "uri zcplain 13/3", "prog ZECS001 0/0 num=23", "prog ZCETTL 27/0 num=-1"]  # fmt: skip
    unstated = subprocess.run([str(exe), "uri", "ZCPLAIN"], env={k: v for k, v in env.items() if k != "GGCICS_URIMAPS"},
                              capture_output=True, text=True, check=False)  # noqa: S603  # fmt: skip
    assert unstated.returncode == 98 and "URIMAP definitions are not stated" in unstated.stdout


@needs_javac
def test_cics_task_inquire_urimap_direct_and_program_status_as_the_stub_does(tmp_path):
    """#4768 zECS (X34): CicsTask answers as the stub does (above): the named definition or NOTFND RESP2 3 (names compared
    as given, blank-trimmed), a browse left where it was; STATUS ENABLED (23); unstated definitions refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("HC41", "ENTER", null, null).withUrimaps(java.util.List.of(
                new String[] {"ZCEXAMPL", "ZC01", "/zecs/*"}, new String[] {"ZCPLAIN", "", "/plain"}));
        for (String n : new String[] {"ZCPLAIN ", "ZCEXAMPL", "ZCNONE", "zcplain"}) {
            int[] r = t.inquireUrimap(n);
            System.out.println(java.util.Arrays.toString(r) + (r[0] == 0 ? "[" + t.urimapPath().strip() + "|"
                    + t.urimapPath().length() + "][" + t.urimapTransaction() + "]" : ""));
        }
        t.inquireUrimapStart();
        t.inquireUrimap("ZCPLAIN");
        t.inquireUrimapNext();
        System.out.println(t.urimapName() + " " + t.programStatus("ZECS001"));
        try {
            new CicsTask("HC41", "ENTER", null, null).inquireUrimap("ZCPLAIN");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }""",
    )
    assert out.splitlines() == [
        "[0, 0][/plain|255][    ]", "[0, 0][/zecs/*|255][ZC01]", "[13, 3]", "[13, 3]", "ZCEXAMPL 23",
        "the installed URIMAP definitions are not stated (withUrimaps): not modelled"]  # fmt: skip


_X33_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCDOCC(gg_cics *c, char *src, int srclen, char *tok, int toklen);
int GGCDOCR(gg_cics *c, char *tok, int toklen, char *into, int intolen);
static gg_cics c;
static void flags(const char *what) {
    memset(c.flags, ' ', 40);
    memcpy(c.flags, what, strlen(what));
}
/* argv: `data TEXT LEN`, `tpl NAME`, `empty`, `get MAXLEN INTOSIZE TOKEN` (- : the last token); every create keeps its token */
int main(int argc, char **argv) {
    char tok[17] = "                ", last[17] = "                ", into[64], name[48];
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "data") == 0) {
            flags("DATA");
            c.len = atoi(argv[i + 2]);
            GGCDOCC(&c, argv[i + 1], (int)strlen(argv[i + 1]), tok, 16);
            i += 2;
            printf("data %d/%d [%.16s]\n", c.resp, c.resp2, tok);
        } else if (strcmp(argv[i], "tpl") == 0) {
            flags("TEMPLATE");
            memset(name, ' ', sizeof name);
            memcpy(name, argv[i + 1], strlen(argv[i + 1]));
            GGCDOCC(&c, name, 48, tok, 16);
            i += 1;
            printf("tpl %d/%d [%.16s]\n", c.resp, c.resp2, tok);
        } else if (strcmp(argv[i], "empty") == 0) {
            flags("EMPTY");
            GGCDOCC(&c, tok, 0, tok, 16);
            printf("empty %d/%d [%.16s]\n", c.resp, c.resp2, tok);
        } else if (strcmp(argv[i], "get") == 0) {
            int max = atoi(argv[i + 1]), size = atoi(argv[i + 2]);
            const char *use = i + 3 < argc && strcmp(argv[i + 3], "-") != 0 ? argv[i + 3] : tok;
            char t[16];
            memset(t, ' ', 16);
            memcpy(t, use, strlen(use) < 16 ? strlen(use) : 16);
            memset(into, '#', sizeof into);
            c.len = max;
            GGCDOCR(&c, t, 16, into, size);
            printf("get %d/%d len=%d [", c.resp, c.resp2, c.len);
            for (int k = 0; k < size; k++) putchar(into[k] < 32 ? '|' : into[k]); /* (a CR or LF shows as |) */
            printf("]\n");
            i += 3;
        }
    }
    (void)last;
    return 0;
}
"""


@needs_cc
def test_the_stub_document_create_and_retrieve(tmp_path):
    """#4769 (register X33), IBM DOCUMENT CREATE / RETRIEVE: TEXT / BINARY keep LENGTH bytes unchanged; a TEMPLATE yields the
    installed definition's text (NOTFND RESP2 3 when absent, refused when unstated or when it holds symbols / template
    commands); a negative LENGTH is LENGERR RESP2 1; RETRIEVE copies at most MAXLENGTH bytes (rest of INTO untouched),
    LENGTH the document's length, a short buffer LENGERR RESP2 2 with the length it needs, a negative MAXLENGTH LENGERR
    RESP2 1 (LENGTH untouched), an unknown token NOTFND RESP2 1, MAXLENGTH beyond INTO refused."""
    exe = _stub(tmp_path, _X33_MAIN)
    cfg = tmp_path / "doctemplates.cfg"
    text = "type: AS\r\nhttp://h:1\r\n"
    cfg.write_text(
        f"ZC01DC {text.encode().hex().upper()}\nBLANK -\nSYMB {b'Hello &name; there'.hex().upper()}\n"
        f"CMD {b'a #set x=1 b'.hex().upper()}\nINC {b'#INCLUDE t'.hex().upper()}\n",
        encoding="ascii",
    )

    def run(*args, templates=True, check=True):
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
        if templates:
            env["GGCICS_DOCTEMPLATES"] = str(cfg)
        (tmp_path / "out").mkdir(exist_ok=True)
        return subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=check)  # noqa: S603

    out = run(
        "data", "HELLO WORLD", "5", "get", "20", "20", "-", "tpl", "ZC01DC", "get", "100", "30", "-"
    ).stdout.splitlines()
    assert out[0] == "data 0/0 [GGDOC00000000001]"
    assert out[1] == "get 0/0 len=5 [HELLO###############]"  # the rest of INTO is untouched, LENGTH is the document's
    assert out[2] == "tpl 0/0 [GGDOC00000000002]"
    assert out[3] == "get 0/0 len=22 [type: AS||http://h:1||########]"  # (CR, LF each shown as |)
    o = run(
        "data",
        "ABCDEFGH",
        "8",
        "get",
        "3",
        "8",
        "-",
        "get",
        "0",
        "8",
        "-",
        "get",
        "-1",
        "8",
        "-",
        "get",
        "8",
        "8",
        "-",
        "get",
        "8",
        "8",
        "GGDOC9",
        "data",
        "X",
        "-2",
        "tpl",
        "NOPE",
        "empty",
        "get",
        "4",
        "4",
        "-",
    ).stdout.splitlines()
    assert o[1] == "get 22/2 len=8 [ABC#####]"  # truncated to MAXLENGTH; LENGTH is the length the whole document needs
    assert o[2] == "get 22/2 len=8 [########]"  # a zero-length buffer: the dummy-buffer sizing call IBM describes
    assert o[3] == "get 22/1 len=-1 [########]"  # MAXLENGTH below zero: LENGTH is not returned (left as the program's)
    assert o[4] == "get 0/0 len=8 [ABCDEFGH]" and o[5] == "get 1/1 len=8 [########]".replace("1/1", "13/1")
    assert o[6] == "data 22/1 [GGDOC00000000001]"  # LENGTH negative: LENGERR RESP2 1, the token left alone
    assert o[7].startswith("tpl 13/3") and o[8] == "empty 0/0 [GGDOC00000000002]"
    assert o[9] == "get 0/0 len=0 [####]"  # an empty document
    assert run("tpl", "BLANK", "get", "5", "5", "-").stdout.splitlines()[1] == "get 0/0 len=0 [#####]"
    for args, why in ((("tpl", "SYMB"), "symbols or template commands"), (("tpl", "CMD"), "symbols or template commands"),
                      (("tpl", "INC"), "symbols or template commands"), (("data", "ABCDEFGH", "8", "get", "8", "4", "-"), "MAXLENGTH beyond INTO"),
                      (("data", "AB", "3"), "DOCUMENT CREATE LENGTH")):  # fmt: skip
        bad = run(*args, check=False)
        assert bad.returncode == 98 and why in bad.stdout, (args, bad.stdout)
    unstated = run("tpl", "ZC01DC", templates=False, check=False)
    assert unstated.returncode == 98 and "document templates are not stated" in unstated.stdout


def test_the_stub_creates_more_than_64_documents_in_one_task(tmp_path):
    """#6072: IBM sets no count of documents a task may create (ZECS000 holds 501), so the stub's tables grow past 64:
    every token is the next number and the first and the last documents still retrieve their own bytes."""
    exe = _stub(tmp_path, _X33_MAIN)
    n = 600
    args = [a for i in range(n) for a in ("data", f"D{i:03d}", "4")]
    args += ["get", "4", "4", "GGDOC00000000001", "get", "4", "4", "-", "get", "4", "4", "GGDOC00000000065"]
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    (tmp_path / "out").mkdir(exist_ok=True)
    out = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=True).stdout.splitlines()  # noqa: S603
    assert out[64] == "data 0/0 [GGDOC00000000065]" and out[n - 1] == f"data 0/0 [GGDOC{n:011d}]"
    assert out[n] == "get 0/0 len=4 [D000]"
    assert out[n + 1] == "get 0/0 len=4 [D599]"
    assert out[n + 2] == "get 0/0 len=4 [D064]"


@needs_javac
def test_cics_task_document_create_and_retrieve_as_the_stub_does(tmp_path):
    """#4769 (X33): CicsTask answers as the stub does (above): the same tokens, LENGERR RESP2 1 / 2, NOTFND RESP2 1 / 3,
    the truncation length, the template text, an unstated or symbol-bearing template refused."""
    out = _cics_task(
        tmp_path,
        """
        java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1;
        CicsTask t = new CicsTask("HC41", "ENTER", null, null).withDoctemplates(java.util.Map.of(
                "ZC01DC", "type: AS\\r\\nhttp://h:1\\r\\n", "BLANK", "", "SYMB", "Hello &name; there",
                "CMD", "a #set x=1 b", "INC", "#INCLUDE t"));
        CicsTask.DocumentCreated d = t.documentCreateData("ABCDEFGH".getBytes(cs), 8);
        System.out.println(d.resp() + "/" + d.resp2() + " " + d.doctoken());
        for (int max : new int[] {3, 0, -1, 8, 20}) {
            CicsTask.DocumentData r = t.documentRetrieve(d.doctoken() + "   ", max);
            System.out.println(r.resp() + "/" + r.resp2() + " " + r.length() + " " + (r.data() == null ? "-" : new String(r.data(), cs)));
        }
        CicsTask.DocumentData bad = t.documentRetrieve("GGDOC9", 8);
        System.out.println(bad.resp() + "/" + bad.resp2() + " " + bad.length() + " " + bad.data());
        CicsTask.DocumentCreated neg = t.documentCreateData(null, -2);
        System.out.println(neg.resp() + "/" + neg.resp2() + " " + neg.doctoken());
        CicsTask.DocumentCreated tp = t.documentCreateTemplate("ZC01DC".concat(" ".repeat(42)), cs);
        System.out.println(tp.resp() + "/" + tp.resp2() + " " + tp.doctoken());
        CicsTask.DocumentData tr = t.documentRetrieve(tp.doctoken(), 100);
        System.out.println(tr.resp() + "/" + tr.length() + " " + new String(tr.data(), cs).replace("\\r\\n", "|"));
        CicsTask.DocumentCreated none = t.documentCreateTemplate("NOPE", cs);
        System.out.println(none.resp() + "/" + none.resp2() + " " + none.doctoken());
        CicsTask.DocumentCreated e = t.documentCreateEmpty();
        CicsTask.DocumentData er = t.documentRetrieve(e.doctoken(), 4);
        System.out.println(e.doctoken() + " " + er.resp() + "/" + er.length() + "/" + er.data().length);
        System.out.println(t.documentRetrieve(t.documentCreateTemplate("BLANK", cs).doctoken(), 5).length());
        for (String name : new String[] {"SYMB", "CMD", "INC"}) {
            try {
                t.documentCreateTemplate(name, cs);
            } catch (UnsupportedOperationException ex) {
                System.out.println(ex.getMessage());
            }
        }
        try {
            new CicsTask("HC41", "ENTER", null, null).documentCreateTemplate("ZC01DC", cs);
        } catch (UnsupportedOperationException ex) {
            System.out.println(ex.getMessage());
        }""",
    )
    sym = "DOCUMENT CREATE TEMPLATE text with symbols or template commands: not modelled"
    assert out.splitlines() == [
        "0/0 GGDOC00000000001", "22/2 8 ABC", "22/2 8 ", "22/1 -1 -", "0/0 8 ABCDEFGH", "0/0 8 ABCDEFGH",
        "13/1 -1 null", "22/1 null", "0/0 GGDOC00000000002", "0/22 type: AS|http://h:1|", "13/3 null",
        "GGDOC00000000003 0/0/0", "0", sym, sym, sym,
        "the installed document templates are not stated (withDoctemplates): not modelled"]  # fmt: skip


def test_scheduler_states_each_tasks_startcode():
    """#4270 slice 3: a terminal step's task is STARTCODE TD; a START-triggered one S / SD by its requests' FROM, a
    group that mixes them none (refused)."""
    import cics_crucible as runner

    case = type("C", (), {"data": {"clock": "2026-03-02T10:00:00", "terminal": "T001"}})()
    assert runner.task_frame(case, 0, {"at": 0, "aid": "ENTER"})["startcode"] == "TD"
    assert runner.REGION_USERID == "CICSUSER" and runner.REGION_SCREEN == (24, 80)


# ---- #4270: EIBTASKN, a stated fact of the run -------------------------------------------------------------------
_TASKN_MAIN = r"""
#include <stdio.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; char qname[16];
                 int item; int num; } gg_cics;
int GGCTASKN(gg_cics *c);
int main(void) {
    gg_cics c = {0};
    c.num = -1;
    GGCTASKN(&c);
    printf("%d/%d/%d\n", c.resp, c.resp2, c.num);
    return 0;
}
"""


@needs_cc
def test_the_stub_states_eibtaskn_from_the_run(tmp_path):
    """#4270, IBM EIB fields: EIBTASKN "contains the task number assigned to the task by CICS", PIC S9(7) COMP-3. The
    stub never derives it: GGCTASKN gives $GGCICS_TASKN (the drivers MOVE it to EIBTASKN), unstated 0; a value that
    is not a task number is refused (98)."""
    exe = _stub(tmp_path, _TASKN_MAIN)

    def run(env):
        return subprocess.run([str(exe)], env={"GGCICS_DIR": str(tmp_path), **env}, capture_output=True, text=True)  # noqa: S603

    assert run({"GGCICS_TASKN": "34"}).stdout.split() == ["0/0/34"]
    assert run({"GGCICS_TASKN": "9999999"}).stdout.split() == ["0/0/9999999"]
    assert run({}).stdout.split() == ["0/0/0"]
    for bad in ("10000000", "-1", "", "7x"):
        got = run({"GGCICS_TASKN": bad})
        assert got.returncode == 98 and "EIBTASKN: $GGCICS_TASKN is not a task number" in got.stdout, bad


@needs_javac
def test_cics_task_states_eibtaskn_as_the_stub_does(tmp_path):
    """#4270: CicsTask.withTaskNumber as the stub's $GGCICS_TASKN (above): the same at every LINK level, unstated 0,
    a value outside 0 to 9999999 refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask task) {
                System.out.println(p + " " + task.taskNumber());
                if (p.equals("MAIN")) {
                    task.link("SUB");
                    task.returnTransid(null, null);
                }
            }
        };
        new CicsTask("T1", "ENTER", null, null).withPrograms(programs).withTaskNumber(34).run("MAIN");
        System.out.println("unstated " + new CicsTask("T1", "ENTER", null, null).taskNumber());
        try {
            new CicsTask("T1", "ENTER", null, null).withTaskNumber(10_000_000L);
        } catch (IllegalArgumentException e) {
            System.out.println("refused");
        }""",
    )
    assert out.splitlines() == ["MAIN 34", "SUB 34", "unstated 0", "refused"]


# ---- #4270 (X27): RETURN ... IMMEDIATE -------------------------------------------------------------------------------
_RETI_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; char qname[16];
                 int item; int num; } gg_cics;
int GGCRETI(gg_cics *c, char *commarea, int len);
int GGCLINK(gg_cics *c, char *area);
int main(int argc, char **argv) {
    gg_cics c = {0};
    char area[16] = "12345678";
    memset(c.name1, ' ', 8);
    memcpy(c.name1, "PC52", 4);
    if (argc > 2) { c.item = 1; c.len = atoi(argv[2]); }
    if (argc > 3) { memcpy(c.name2, "PCIMML  ", 8); memcpy(c.name1, "PCIMML  ", 8); c.item = 0; GGCLINK(&c, area);
                    memset(c.name1, ' ', 8); memcpy(c.name1, "PC52", 4); c.item = argc > 2; }
    GGCRETI(&c, area, c.len);
    printf("%d/%d\n", c.resp, c.resp2);
    return 0;
}
"""


@needs_cc
def test_the_stub_return_immediate_is_ibms(tmp_path):
    """#4270 (X27), IBM EXEC CICS RETURN: IMMEDIATE attaches TRANSID's task at once; INVREQ RESP2 1 for a task with no
    terminal, INVREQ RESP2 2 below the highest logical level, LENGERR RESP2 11 for a COMMAREA length below 0 or past
    32763 (the program then goes on). The task's terminal is a stated fact ($GGCICS_FACILITY): unstated, refused; a task
    with no terminal below level 1, where IBM lists both INVREQs without a precedence, refused."""
    exe = _stub(tmp_path, _RETI_MAIN)
    (tmp_path / "out").mkdir()

    def run(env, *args):
        return subprocess.run(
            [str(exe), *args],
            env={"GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out"), **env},
            capture_output=True,
            text=True,
        )  # noqa: S603

    term = {"GGCICS_FACILITY": "T001"}
    ok = run(term, "x", "8")
    assert ok.stdout.strip() == "0/0"
    events = (tmp_path / "out" / "events.txt").read_text(encoding="latin-1")
    assert "level=1 transid=PC52 len=8 immediate=1" in events
    assert run(term, "x", "32764").stdout.strip() == "22/11"
    assert run(term, "x", "-1").stdout.strip() == "22/11"
    assert run({"GGCICS_FACILITY": ""}, "x", "8").stdout.strip() == "16/1"
    assert run(term, "x", "8", "link").stdout.strip() == "16/2"
    unstated = run({}, "x", "8")
    assert unstated.returncode == 98 and "terminal is not stated" in unstated.stdout
    both = run({"GGCICS_FACILITY": ""}, "x", "8", "link")
    assert both.returncode == 98 and "does not say which" in both.stdout


@needs_javac
def test_cics_task_return_immediate_as_the_stub_does(tmp_path):
    """#4270 (X27): CicsTask.returnImmediate as the stub's GGCRETI (above): {0, 0} and the task ends with an event that
    says `immediate`; INVREQ 1 with no terminal, INVREQ 2 below level 1 (the event names the level), LENGERR 11; both
    INVREQs at once refused."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("PC51", "ENTER", null, null).withTermid("T001");
        System.out.println(java.util.Arrays.toString(t.returnImmediate("PC52", null, null)) + t.ended());
        System.out.println(t.events().get(0));
        CicsTask u = new CicsTask("PC51", "ENTER", null, null).withTermid("T001");
        System.out.println(java.util.Arrays.toString(u.returnImmediate("PC52", new byte[8], 32764)) + u.ended());
        CicsTask n = new CicsTask("PC54", null, null, null);
        System.out.println(java.util.Arrays.toString(n.returnImmediate("PC52", null, null)) + n.ended());
        final int[][] low = new int[1][];
        CicsTask r = new CicsTask("PC51", "ENTER", null, null).withTermid("T001").withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) { return true; }
            public void run(String p, CicsTask k) { low[0] = k.returnImmediate("PC52", null, null); }
        });
        r.link("PCIMML");
        System.out.println(java.util.Arrays.toString(low[0]) + r.ended());
        System.out.println(r.events().get(1));
        try {
            CicsTask b = new CicsTask("PC54", null, null, null).withPrograms(new CicsTask.Programs() {
                public boolean defined(String p) { return true; }
                public void run(String p, CicsTask k) { k.returnImmediate("PC52", null, null); }
            });
            b.link("PCIMML");
        } catch (IllegalStateException e) {
            System.out.println("refused");
        }""",
    )
    lines = out.splitlines()
    assert lines[0] == "[0, 0]true" and "immediate=true" in lines[1] and "transid=PC52" in lines[1]
    assert lines[2:5] == ["[22, 11]false", "[16, 1]false", "[16, 2]false"]
    assert "level=2" in lines[5] and "resp=INVREQ" in lines[5] and "resp2=2" in lines[5]
    assert lines[6] == "refused"


# ---- #4767 zECS (register X35): WEB OPEN / CONVERSE / CLOSE, the HTTP client ----------------------------------------
_X35_PEERS = [
    (
        "HTTP",
        "zecs.example",
        80,
        "ZCCLIENT",
        "/resources/zc01",
        [
            ("GET", "/resources/zc01/k1", "", 200, "OK", "text/plain", "value-one"),
            ("PUT", "/resources/zc01/k1", "", 201, "Created", "text/plain", "stored"),
            ("GET", "/resources/zc01/k1", "", 404, "Not Found", "text/plain", ""),
            ("DELETE", "/deplicate/k2", "clear=*", 200, "OK", "application/json", "0123456789ABCDEF"),
            ("GET", "/long/status", "", 200, "A reason phrase longer than fifteen", "text/plain", "x"),
        ],
    ),
]
# one step a line: open-u NAME | open-h HOST HOSTLENGTH PORT|- SCHEME | conv SESSION METHOD PATH|- QUERY|- FROM|- MEDIA|-
# MAXLENGTH STATUSLEN | close SESSION ("-": the option not given; SESSION: the n-th open's token, 9: a token never given)
_X35_STEPS = [
    "open-u ZCCLIENT",
    "open-h ZECS.EXAMPLE 12 - 1096",
    "open-h zecs.example 0 80 1096",
    "open-h zecs.example 12 70000 1096",
    "open-h zecs.example 12 80 7",
    "conv 0 748 /resources/zc01/k1 - - _ 40 15",
    "conv 1 749 /resources/zc01/k1 - stored-data text/plain 40 15",
    "conv 0 748 /resources/zc01/k1 - - text/plain 40 15",
    "conv 1 292 /deplicate/k2 ?clear=* - text/plain 10 15",
    "conv 0 749 /x - - text/plain 40 15",
    "conv 0 748 /x - body text/plain 40 15",
    "conv 0 748 /x - - - -4 15",
    "conv 0 748 /x - - - 40 0",
    "conv 0 999 /x - - - 40 15",
    "conv 9 748 /x - - - 40 15",
    "close 0",
    "close 0",
    "conv 0 748 /x - - - 40 15",
]
_X35_EXPECTED = [
    "open 0/0 GGWS0001",
    "open 0/0 GGWS0002",
    "open 22/21",
    "open 16/138",
    "open 16/40",
    "conv 0/0 len=9 [value-one] status=200 [OK] [text/plain]",
    "conv 0/0 len=6 [stored] status=201 [Created] [text/plain]",
    "conv 0/0 len=0 [] status=404 [Not Found] [text/plain]",
    "conv 22/57 len=10 [0123456789] status=200 [OK] [application/json]",
    "conv 16/34",
    "conv 16/33",
    "conv 22/16",
    "conv 22/59",
    "conv 16/54",
    "conv 19/27",
    "close 0/0",
    "close 19/27",
    "conv 19/27",
]
_X35_REFUSED = [  # (steps, what both runtimes stop with)
    (["open-h other.examp 11 - 1096"], "WEB OPEN of a peer the run does not state"),
    (["open-u NOPE"], "WEB OPEN of a peer the run does not state"),
    (["open-h zecs.example 0 - 7"], "more than one condition at once"),
    (["open-h zecs.example 12 0 1096"], "PORTNUMBER below 1"),
    (["open-h zecs.example 40 - 1096"], "WEB OPEN HOSTLENGTH"),
    (["open-u ZCCLIENT", "conv 0 748 /nothing - - - 40 15"], "request the peer states no response to"),
    (["open-h zecs.example 12 - 1096", "conv 0 748 - - - - 40 15"], "no PATH on a session opened by HOST"),
    (["open-u ZCCLIENT", "conv 0 749 /x - - - 40 0"], "more than one condition at once"),
    (["open-u ZCCLIENT", "conv 0 760 /x - - - 40 15"], "TRACE / OPTIONS"),
    (["open-u ZCCLIENT", "conv 0 748 /x - - - 0 15"], "MAXLENGTH 0"),
    (["open-u ZCCLIENT", "conv 0 748 /x - body - 40 15"], "more than one condition at once"),  # (INVREQ 33 and 76)
    (["open-u ZCCLIENT", "conv 0 749 /resources/zc01/k1 - body _ 40 15"], "blank MEDIATYPE"),
    (["open-u ZCCLIENT", "conv 0 748 /long/status - - - 40 15"], "status text longer than STATUSLEN"),
]

_X35_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWOPN(gg_cics *c, char *token, char *host, int hostcap);
int GGCWCNV(gg_cics *c, char *token, char *path, int pathcap, char *query, int querycap, char *from, int fromcap,
            char *media, int mediacap, char *into, int intocap, char *stext, int stextcap);
int GGCWCLS(gg_cics *c, char *token);
static gg_cics c;
static void put(char *dst, int n, const char *what) { memset(dst, ' ', n); memcpy(dst, what, strlen(what)); }
static int given(const char *a) { return strcmp(a, "-") != 0; }
int main(int argc, char **argv) {
    char tokens[10][8], flags[40];
    int nt = 0;
    memset(tokens, 'Z', sizeof tokens);
    for (int i = 1; i < argc; i++) {
        char *w[10];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 10; t = strtok(NULL, " ")) w[k++] = t;
        if (strcmp(w[0], "open-u") == 0 || strcmp(w[0], "open-h") == 0) {
            char host[12] = {0}, tok[8];
            memset(tok, 'Z', 8);
            if (w[0][5] == 'u') { put(c.name1, 8, w[1]); put(c.flags, 40, "URIMAP"); GGCWOPN(&c, tok, host, 0); }
            else {
                memcpy(host, w[1], strlen(w[1]) < 12 ? strlen(w[1]) : 12);
                c.len = atoi(w[2]); c.item = atoi(w[4]);
                if (given(w[3])) { c.num = atoi(w[3]); put(c.flags, 40, "HOST PORT"); } else put(c.flags, 40, "HOST");
                GGCWOPN(&c, tok, host, 12);
            }
            printf("open %d/%d", c.resp, c.resp2);
            if (c.resp == 0) { memcpy(tokens[nt++], tok, 8); printf(" %.8s", tok); }
            printf("\n");
        } else if (strcmp(w[0], "conv") == 0) {
            char path[64], query[64], from[64], media[56], into[40], stext[15];
            int s = atoi(w[1]);
            memset(into, '#', sizeof into); memset(stext, ' ', sizeof stext); memset(media, ' ', sizeof media);
            flags[0] = 0;
            c.num = atoi(w[2]); c.len = atoi(w[7]); c.item = atoi(w[8]);
            c.hours = given(w[3]) ? (int)strlen(w[3]) : 0; if (given(w[3])) { strcat(flags, "PATH "); memcpy(path, w[3], strlen(w[3])); }
            c.mins = given(w[4]) ? (int)strlen(w[4]) : 0; if (given(w[4])) { strcat(flags, "QUERY "); memcpy(query, w[4], strlen(w[4])); }
            c.secs = given(w[5]) ? (int)strlen(w[5]) : 0; if (given(w[5])) { strcat(flags, "FROM "); memcpy(from, w[5], strlen(w[5])); }
            if (given(w[6])) { strcat(flags, "MEDIA"); if (strcmp(w[6], "_") != 0) memcpy(media, w[6], strlen(w[6])); }
            put(c.flags, 40, flags);
            GGCWCNV(&c, tokens[s], path, 64, query, 64, from, 64, media, 56, into, 40, stext, 15);
            printf("conv %d/%d", c.resp, c.resp2);
            if (c.resp == 0 || c.resp2 == 57) {
                int ml = 56, tl = 15;
                while (ml > 0 && media[ml - 1] == ' ') ml--;
                while (tl > 0 && stext[tl - 1] == ' ') tl--;
                printf(" len=%d [%.*s] status=%d [%.*s] [%.*s]", c.len, c.len, into, c.num, tl, stext, ml, media);
            }
            printf("\n");
        } else {
            GGCWCLS(&c, tokens[atoi(w[1])]);
            printf("close %d/%d\n", c.resp, c.resp2);
        }
    }
    return 0;
}
"""


def _x35_cfg(path: Path) -> None:
    def hx(v: str | None) -> str:
        return v.encode("latin-1").hex().upper() if v else "-"

    lines = []
    for scheme, host, port, uri, upath, xs in _X35_PEERS:
        lines.append(f"P {scheme} {hx(host)} {port} {uri or '-'} {hx(upath)}")
        lines += [f"X {m} {hx(p)} {hx(q)} {st} {hx(t)} {hx(mt)} {hx(b)}" for m, p, q, st, t, mt, b in xs]
    path.write_text("".join(f"{ln}\n" for ln in lines), encoding="ascii")


@needs_cc
def test_the_stub_web_open_converse_close(tmp_path):
    """#4767 zECS (register X35), IBM WEB OPEN / WEB CONVERSE / WEB CLOSE: a session to a stated peer by CLIENT URIMAP or by
    HOST / HOSTLENGTH / PORTNUMBER (80 for HTTP when omitted) / SCHEME; each request answered by the next stated response it
    matches (method, path, query without its '?'); INTO at most MAXLENGTH (LENGERR 57 when longer), STATUSCODE, the reason
    phrase, MEDIATYPE blank-padded; the conditions IBM lists for what the program gives (LENGERR 21 / 5 / 8 / 16 / 50 / 59,
    INVREQ 40 / 138 / 33 / 34 / 54 / 76, NOTOPEN 27); WEB CLOSE ends the session. What IBM leaves open is refused."""
    exe = _stub(tmp_path, _X35_MAIN)
    cfg = tmp_path / "http.cfg"
    _x35_cfg(cfg)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out"),
           "GGCICS_HTTP": str(cfg)}  # fmt: skip
    (tmp_path / "out").mkdir()
    out = subprocess.run([str(exe), *_X35_STEPS], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.splitlines() == _X35_EXPECTED
    events = (tmp_path / "out" / "events.txt").read_text(encoding="latin-1").splitlines()
    assert [e.split()[1] for e in events] == ["WEB-OPEN"] * 5 + ["WEB-CONVERSE"] * 4 + ["WEB-CLOSE"] * 2
    hx = lambda t: t.encode("latin-1").hex().upper()  # noqa: E731  # #4767: the connection as the program named it
    assert events[0].endswith(f"host={hx('zecs.example')} scheme=HTTP resp=0 resp2=0")  # URIMAP: the peer's host
    assert events[1].endswith(f"host={hx('ZECS.EXAMPLE')} scheme=HTTP resp=0 resp2=0")  # HOST: as the program wrote it
    assert events[2].endswith("host=- scheme=HTTP resp=22 resp2=21")  # HOSTLENGTH 0: no host
    assert events[3].endswith(f"host={hx('zecs.example')} scheme=HTTP resp=16 resp2=138")
    assert events[4].endswith(f"host={hx('zecs.example')} scheme=- resp=16 resp2=40")  # a scheme that is neither
    assert events[9].endswith("WEB-CLOSE pgm= resp=0 resp2=0")
    assert events[10].endswith("WEB-CLOSE pgm= resp=19 resp2=27")
    conv = events[5:9]
    assert "method=PUT" in conv[1] and "body=1" in conv[1] and "media=746578742F706C61696E" in conv[1]
    assert "query=636C6561723D2A" in conv[3] and "resp=22 resp2=57" in conv[3]
    for steps, why in _X35_REFUSED:
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)
    unstated = subprocess.run([str(exe), "open-u ZCCLIENT"], env={k: v for k, v in env.items() if k != "GGCICS_HTTP"},
                              capture_output=True, text=True, check=False)  # noqa: S603  # fmt: skip
    assert unstated.returncode == 98 and "HTTP peers are not stated" in unstated.stdout


def _x35_java_steps(steps: list[str]) -> str:
    """The Java statements for the steps above, printing as the stub's main does."""
    lines = ["java.util.List<String> tokens = new java.util.ArrayList<>();"]
    for st in steps:
        w = st.split(" ")
        if w[0] == "open-u":
            lines.append(f'show(t.webOpenUrimap("{w[1]}"), tokens);')
        elif w[0] == "open-h":
            host = (w[1] + " " * 12)[:12]
            port = "0, false" if w[3] == "-" else f"{w[3]}, true"
            lines.append(f'show(t.webOpenHost("{host}", {w[2]}, {port}, {w[4]}), tokens);')
        elif w[0] == "conv":

            def area(v: str, width: int) -> str:
                return "null" if v == "-" else '"' + (v + " " * width)[:width] + '"'

            def length(v: str) -> str:
                return "0" if v == "-" else str(len(v))

            media = "null" if w[6] == "-" else '"' + ("" if w[6] == "_" else w[6]).ljust(56) + '"'
            tok = f'tokens.size() > {w[1]} ? tokens.get({w[1]}) : "ZZZZZZZZ"'
            lines.append(
                f"conv(t.webConverse({tok}, {w[2]}, {area(w[3], 64)}, {length(w[3])}, {area(w[4], 64)}, "
                f"{length(w[4])}, {area(w[5], 64)}, {length(w[5])}, {media}, {w[7]}, {w[8]}, CS));"
            )
        else:
            lines.append(
                f'int[] k = t.webClose(tokens.size() > {w[1]} ? tokens.get({w[1]}) : "ZZZZZZZZ"); '
                'System.out.println("close " + k[0] + "/" + k[1]);'
            )
    return "\n".join("{ " + ln + " }" if ln.startswith("int[] k") else ln for ln in lines)


@needs_javac
def test_cics_task_web_open_converse_close_as_the_stub_does(tmp_path):
    """#4767 zECS (X35): CicsTask answers the same steps as the stub (above), line for line, records each request sent as a
    WEB-CONVERSE event, and refuses what the stub refuses."""
    peers = ", ".join(
        f'new CicsTask.HttpPeer("{s}", "{h}", {p}, "{u}", "{up}", java.util.List.of('
        + ", ".join(f'new CicsTask.HttpExchange("{m}", "{pa}", "{q}", {st}, "{tx}", "{mt}", "{b}")'
                    for m, pa, q, st, tx, mt, b in xs) + "))"
        for s, h, p, u, up, xs in _X35_PEERS)  # fmt: skip
    helpers = """
    static final java.nio.charset.Charset CS = java.nio.charset.StandardCharsets.ISO_8859_1;
    static void show(CicsTask.WebOpened o, java.util.List<String> tokens) {
        if (o.resp() == 0) tokens.add(o.sesstoken());
        System.out.println("open " + o.resp() + "/" + o.resp2() + (o.resp() == 0 ? " " + o.sesstoken() : ""));
    }
    static void conv(CicsTask.WebResponse r) {
        System.out.println("conv " + r.resp() + "/" + r.resp2() + (r.body() == null ? "" : " len=" + r.toLength() + " ["
                + new String(r.body(), CS) + "] status=" + r.status() + " [" + r.statusText() + "] ["
                + r.mediaType().stripTrailing() + "]"));
    }
"""
    body = f"""
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of({peers}));
        {_x35_java_steps(_X35_STEPS)}
        for (java.util.Map<String, Object> e : t.events()) {{
            System.out.println(e.get("event") + " " + e.get("host") + " " + e.get("method") + " " + e.get("path") + " ["
                    + e.get("query") + "] " + e.get("mediatype") + " " + e.get("body") + " " + e.get("resp") + "/"
                    + e.get("resp2") + " " + e.get("scheme"));
        }}
        String[][] refused = {{{", ".join("{" + ", ".join('"' + x + '"' for x in steps) + "}" for steps, _ in _X35_REFUSED)}}};
        for (String[] steps : refused) {{
            CicsTask u = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of({peers}));
            try {{
                Main.run(u, steps);
                System.out.println("not refused");
            }} catch (UnsupportedOperationException e) {{
                System.out.println(e.getMessage());
            }}
        }}
        try {{
            new CicsTask("ZC01", "ENTER", null, null).webOpenUrimap("ZCCLIENT");
        }} catch (UnsupportedOperationException e) {{
            System.out.println(e.getMessage());
        }}
    }}
    static void run(CicsTask t, String[] steps) {{
        java.util.List<String> tokens = new java.util.ArrayList<>();
        for (String st : steps) {{
            String[] w = st.split(" ");
            if (w[0].equals("open-u")) {{
                show(t.webOpenUrimap(w[1]), tokens);
            }} else if (w[0].equals("open-h")) {{
                show(t.webOpenHost(String.format("%-12.12s", w[1]), Integer.parseInt(w[2]),
                        w[3].equals("-") ? 0 : Integer.parseInt(w[3]), !w[3].equals("-"), Integer.parseInt(w[4])), tokens);
            }} else {{
                java.util.function.Function<String, String> area = v -> v.equals("-") ? null : String.format("%-64.64s", v);
                java.util.function.Function<String, Integer> len = v -> v.equals("-") ? 0 : v.length();
                String media = w[6].equals("-") ? null : String.format("%-56s", w[6].equals("_") ? "" : w[6]);
                conv(t.webConverse(tokens.get(Integer.parseInt(w[1])), Integer.parseInt(w[2]), area.apply(w[3]),
                        len.apply(w[3]), area.apply(w[4]), len.apply(w[4]), area.apply(w[5]), len.apply(w[5]), media,
                        Integer.parseInt(w[7]), Integer.parseInt(w[8]), CS));
            }}
        }}
    """
    out = _cics_task(tmp_path, body + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    n = len(_X35_EXPECTED)
    assert lines[:n] == _X35_EXPECTED
    # #4767: each connection opened and closed is recorded too (WEB-OPEN host and scheme as the connection names them)
    assert lines[n:n + 11] == [
        "WEB-OPEN zecs.example null null [null] null null 0/0 HTTP",
        "WEB-OPEN ZECS.EXAMPLE null null [null] null null 0/0 HTTP",
        "WEB-OPEN  null null [null] null null 22/21 HTTP",
        "WEB-OPEN zecs.example null null [null] null null 16/138 HTTP",
        "WEB-OPEN zecs.example null null [null] null null 16/40 null",
        "WEB-CONVERSE zecs.example GET /resources/zc01/k1 [] null null 0/0 null",
        "WEB-CONVERSE zecs.example PUT /resources/zc01/k1 [] text/plain stored-data 0/0 null",
        "WEB-CONVERSE zecs.example GET /resources/zc01/k1 [] null null 0/0 null",
        "WEB-CONVERSE zecs.example DELETE /deplicate/k2 [clear=*] null null 22/57 null",
        "WEB-CLOSE null null null [null] null null 0/0 null",
        "WEB-CLOSE null null null [null] null null 19/27 null"]  # fmt: skip
    refusals = [ln for ln in lines[n + 11 :] if not ln.startswith(("open ", "conv "))]
    assert len(refusals) == len(_X35_REFUSED) + 1
    for got, (_steps, why) in zip(refusals, _X35_REFUSED):
        assert why in got and got.endswith(": not modelled"), (got, why)
    assert refusals[-1] == "the HTTP peers are not stated (withHttpPeers): not modelled"


_X35_MANY_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWOPN(gg_cics *c, char *token, char *host, int hostcap);
int GGCWCNV(gg_cics *c, char *token, char *path, int pathcap, char *query, int querycap, char *from, int fromcap,
            char *media, int mediacap, char *into, int intocap, char *stext, int stextcap);
int GGCWCLS(gg_cics *c, char *token);
static gg_cics c;
static void put(char *dst, int n, const char *what) { memset(dst, ' ', n); memcpy(dst, what, strlen(what)); }
/* args: N sessions opened by URIMAP and never closed, then M conversations GET /k<i> on session i % N */
int main(int argc, char **argv) {
    int n = atoi(argv[1]), m = argc > 2 ? atoi(argv[2]) : 0, ok = 0;
    char (*tok)[8] = malloc((size_t)n * 8), host[12] = {0};
    for (int i = 0; i < n; i++) {
        put(c.name1, 8, "ZCCLIENT");
        put(c.flags, 40, "URIMAP");
        GGCWOPN(&c, tok[i], host, 0);
    }
    printf("opened %d first %.8s last %.8s\n", n, tok[0], tok[n - 1]);
    for (int i = 0; i < m; i++) {
        char path[64] = {0}, query[64], from[64], media[56], into[40], stext[15], want[16];
        snprintf(path, sizeof path, "/k%d", i);
        snprintf(want, sizeof want, "b%d", i);
        put(c.flags, 40, "PATH");
        c.num = 748; c.len = 40; c.item = 15; c.hours = (int)strlen(path); c.mins = 0; c.secs = 0;
        GGCWCNV(&c, tok[i % n], path, 64, query, 64, from, 64, media, 56, into, 40, stext, 15);
        if (c.resp == 0 && c.num == 200 && c.len == (int)strlen(want) && memcmp(into, want, strlen(want)) == 0) ok++;
    }
    printf("answered %d of %d\n", ok, m);
    if (n > 64) {
        GGCWCLS(&c, tok[64]);
        printf("close %d/%d\n", c.resp, c.resp2);
        GGCWCLS(&c, tok[64]);
        printf("close again %d/%d\n", c.resp, c.resp2);
    }
    return 0;
}
"""


def _x35_many_cfg(path: Path, exchanges: int, peers: int = 1) -> None:
    hx = lambda t: t.encode("latin-1").hex().upper()  # noqa: E731
    lines = [f"P HTTP {hx('zecs.example')} 80 ZCCLIENT {hx('/')}"]
    lines += [f"X GET {hx(f'/k{i}')} - 200 {hx('OK')} {hx('text/plain')} {hx(f'b{i}')}" for i in range(exchanges)]
    lines += [f"P HTTP {hx(f'h{p}.example')} 80 U{p:07d} {hx('/')}" for p in range(1, peers)]
    path.write_text("".join(f"{ln}\n" for ln in lines), encoding="ascii")


@needs_cc
def test_the_stub_web_sessions_and_responses_are_not_capped_at_64_and_256(tmp_path):
    """#6072: IBM sets no count of sessions a task may open (ZECS000 never closes and opens 501) nor of responses a peer
    gives, so the stub's tables grow: tokens run on, every stated response is answered (255 / 256 / 257 / 501 of them),
    and a session past the 64th still closes. The token's four digits are the one bound (9999)."""
    exe = _stub(tmp_path, _X35_MANY_MAIN)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    (tmp_path / "out").mkdir()

    def run(n: int, m: int, cfg: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(exe), str(n), str(m)], env={**env, "GGCICS_HTTP": str(cfg)},  # noqa: S603
                              capture_output=True, text=True, check=False)  # fmt: skip

    for n, m in ((65, 65), (300, 255), (300, 256), (300, 257), (600, 501)):
        cfg = tmp_path / f"many-{m}.cfg"
        _x35_many_cfg(cfg, m)
        out = run(n, m, cfg)
        assert out.returncode == 0, out.stdout
        assert out.stdout.splitlines() == [f"opened {n} first GGWS0001 last GGWS{n:04d}", f"answered {m} of {m}",
                                           "close 0/0", "close again 19/27"], (n, m, out.stdout)  # fmt: skip
    cfg = tmp_path / "one.cfg"
    _x35_many_cfg(cfg, 1)
    assert run(9999, 0, cfg).stdout.splitlines()[0] == "opened 9999 first GGWS0001 last GGWS9999"
    over = run(10000, 0, cfg)
    assert over.returncode == 98 and "WEB OPEN: more than 9999 sessions in one task" in over.stdout
    many_peers = tmp_path / "peers.cfg"
    _x35_many_cfg(many_peers, 1, peers=33)
    stated = run(1, 0, many_peers)
    assert stated.returncode == 98 and "more than 32 HTTP peers stated" in stated.stdout


@needs_javac
def test_cics_task_web_sessions_and_responses_are_not_capped_either(tmp_path):
    """#6072: CicsTask answers 501 stated responses over 501 unclosed sessions as the stub does, and refuses the 10000th
    open with the stub's words."""
    out = _cics_task(
        tmp_path,
        """
        java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1;
        java.util.List<CicsTask.HttpExchange> xs = new java.util.ArrayList<>();
        for (int i = 0; i < 501; i++) xs.add(new CicsTask.HttpExchange("GET", "/k" + i, "", 200, "OK", "text/plain", "b" + i));
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(
                java.util.List.of(new CicsTask.HttpPeer("HTTP", "zecs.example", 80, "ZCCLIENT", "/", xs)));
        java.util.List<String> tokens = new java.util.ArrayList<>();
        int ok = 0;
        for (int i = 0; i < 501; i++) tokens.add(t.webOpenUrimap("ZCCLIENT").sesstoken());
        for (int i = 0; i < 501; i++) {
            String p = "/k" + i;
            CicsTask.WebResponse r = t.webConverse(tokens.get(i), 748, String.format("%-64.64s", p), p.length(), null, 0,
                    null, 0, null, 40, 15, cs);
            if (r.resp() == 0 && r.status() == 200 && new String(r.body(), cs).equals("b" + i)) ok++;
        }
        System.out.println("answered " + ok + " of 501 first " + tokens.get(0) + " last " + tokens.get(500));
        CicsTask u = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(
                java.util.List.of(new CicsTask.HttpPeer("HTTP", "zecs.example", 80, "ZCCLIENT", "/", xs)));
        String last = "";
        for (int i = 0; i < 9999; i++) last = u.webOpenUrimap("ZCCLIENT").sesstoken();
        System.out.println("opened 9999 last " + last);
        try {
            u.webOpenUrimap("ZCCLIENT");
            System.out.println("not refused");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }
        """,
    )
    assert out.splitlines() == ["answered 501 of 501 first GGWS0001 last GGWS0501", "opened 9999 last GGWS9999",
                                "WEB OPEN: more than 9999 sessions in one task: not modelled"]  # fmt: skip


# ---- #4767 zECS (register X36): WEB PARSE URL ------------------------------------------------------------------------
# one step a line: parse URL URLLENGTH|= HOSTLENGTH|- PATHLENGTH|- QUERYSTRLEN|- ("=": the URL's own length; "-": the option
# not given). Areas: URL 64, SCHEMENAME 16, HOST / PATH / QUERYSTRING 40 bytes.
_X36_STEPS = [
    "parse http://zecs.example:8080/resources/a?k=v = 40 40 40",
    "parse HTTPS://Host.Example/p = 40 40 -",
    "parse http://hostname:8080 = 40 - -",
    "parse https://h = 9 - -",
    "parse http://h/%41%2F = 40 40 -",
    "parse http://h/%4 = 40 40 -",
    "parse http://h/p?a=%4G = 40 40 40",
    "parse no-scheme = 40 - -",
    "parse http://:80 = 40 - -",
    "parse http://h:99999 = 40 - -",
    "parse http://h:80x = 40 - -",
    "parse ://h = 40 - -",
    "parse http://h:65535/x = 40 40 -",
    "parse http://[2001:db8::1]:81/a?b=c = 40 40 40",
    "parse https://[::1]/p = 40 40 -",
    "parse http://192.0.2.7:8080/a?b=c = 40 40 40",
    "parse http://zecs.example/p = 5 40 -",
    "parse http://zecs.example/long/path = 40 5 -",
    "parse http://h/p?abcdef = 40 40 3",
    "parse http://h/p?abcdef = 40 40 6",
]
_X36_EXPECTED = [
    "parse 0/0 [HTTP] [zecs.example] 8080 [/resources/a] [k=v] 12 12 3",
    "parse 0/0 [HTTPS] [Host.Example] 443 [/p] [] 12 2 -",
    "parse 0/0 [HTTP] [hostname] 8080 [] [] 8 - -",
    "parse 0/0 [HTTPS] [h] 443 [] [] 1 - -",
    "parse 0/0 [HTTP] [h] 80 [/%41%2F] [] 1 7 -",
    "parse 16/65",
    "parse 16/65",
    "parse 16/28",
    "parse 16/28",
    "parse 16/28",
    "parse 16/28",
    "parse 16/28",
    "parse 0/0 [HTTP] [h] 65535 [/x] [] 1 2 -",
    "parse 0/0 [HTTP] [2001:db8::1] 81 [/a] [b=c] 11 2 3",
    "parse 0/0 [HTTPS] [::1] 443 [/p] [] 3 2 -",
    "parse 0/0 [HTTP] [192.0.2.7] 8080 [/a] [b=c] 9 2 3",
    "parse 22/29",
    "parse 22/30",
    "parse 22/8",
    "parse 0/0 [HTTP] [h] 80 [/p] [abcdef] 1 2 6",
]
_X36_REFUSED = [  # (steps, what both runtimes stop with)
    (["parse ftp://h/p = 40 40 -"], "scheme other than HTTP / HTTPS"),
    (["parse http://u@h/p = 40 40 -"], "user-info"),
    (["parse http://[::1/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://[]/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://[::1]x/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://[g::1]/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://[::1]]/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://h]/p = 40 40 -"], "IPv6 host that is not"),
    (["parse http://[::1]:/p = 40 40 -"], "empty port"),
    (["parse http://[::1]:0/p = 40 40 -"], "port 0"),
    (["parse http://h/p#f = 40 40 -"], "fragment"),
    (["parse http://h:/p = 40 40 -"], "empty port"),
    (["parse http://h:0/p = 40 40 -"], "port 0"),
    (["parse http://h/%4a = 40 40 -"], "lowercase hex digit"),
    (["parse http://h/p 0 40 - -"], "URLLENGTH not above zero"),
    (["parse http://h/p 70 40 - -"], "length beyond its area"),
    (["parse http://h/p = 50 40 -"], "length beyond its area"),
    (["parse http://zecs.example/long/path = 5 5 -"], "more than one condition at once"),
    (["parse http://zecs.example/p?abc = 5 40 2"], "more than one condition at once"),
    (["parse http://zecs.example/%4 = 5 40 -"], "more than one condition at once"),
    (["parse http://zecs.example:99999/p = 5 40 -"], "more than one condition at once"),
    (["parse http://zecs.example = 5 40 5"], "PATH or QUERYSTRING the URL has none of"),
    (["parse http://h = 40 40 -"], "PATH or QUERYSTRING the URL has none of"),
    (["parse http://h/p = 40 40 40"], "PATH or QUERYSTRING the URL has none of"),
    (["parse x%4 = 40 - -"], "more than one condition at once"),
]

_X36_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWPRS(gg_cics *c, char *url, int urlcap, char *scheme, int schemecap, char *host, int hostcap, char *path,
            int pathcap, char *query, int querycap);
static gg_cics c;
static int given(const char *a) { return strcmp(a, "-") != 0; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[6], url[64], scheme[16], host[40], path[40], query[40], flags[40] = "SCHEME";
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 6; t = strtok(NULL, " ")) w[k++] = t;
        memset(url, ' ', sizeof url); memcpy(url, w[1], strlen(w[1]));
        memset(scheme, '#', sizeof scheme); memset(host, '#', sizeof host);
        memset(path, '#', sizeof path); memset(query, '#', sizeof query);
        c.len = w[2][0] == '=' ? (int)strlen(w[1]) : atoi(w[2]);
        c.hours = given(w[3]) ? atoi(w[3]) : 0; if (given(w[3])) strcat(flags, " HOST");
        c.mins = given(w[4]) ? atoi(w[4]) : 0; if (given(w[4])) strcat(flags, " PATH");
        c.secs = given(w[5]) ? atoi(w[5]) : 0; if (given(w[5])) strcat(flags, " QUERY");
        memset(c.flags, ' ', 40); memcpy(c.flags, flags, strlen(flags));
        GGCWPRS(&c, url, 64, scheme, 16, host, 40, path, 40, query, 40);
        printf("parse %d/%d", c.resp, c.resp2);
        if (c.resp == 0) {
            int sl = 16;
            while (sl > 0 && scheme[sl - 1] == ' ') sl--;
            printf(" [%.*s] [%.*s] %d [%.*s] [%.*s] ", sl, scheme, given(w[3]) ? c.hours : 0, host, c.num,
                   given(w[4]) ? c.mins : 0, path, given(w[5]) ? c.secs : 0, query);
            if (given(w[3])) printf("%d ", c.hours); else printf("- ");
            if (given(w[4])) printf("%d ", c.mins); else printf("- ");
            if (given(w[5])) printf("%d", c.secs); else printf("-");
        }
        printf("\n");
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_web_parse_url(tmp_path):
    """#4767 zECS (register X36), IBM WEB PARSE URL: scheme (upper case, blank-padded), host, port (explicit, else 80 / 443),
    path and query string (still escaped) with their lengths, an IPv6 host without its brackets; INVREQ 28 for a URL that is
    none, INVREQ 65 for a bad escape, LENGERR 29 / 30 / 8 for a host / path / query string longer than its length; what IBM
    leaves open (two conditions at once, a malformed IPv6 host) is refused."""
    exe = _stub(tmp_path, _X36_MAIN)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    (tmp_path / "out").mkdir()
    out = subprocess.run([str(exe), *_X36_STEPS], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.splitlines() == _X36_EXPECTED
    for steps, why in _X36_REFUSED:
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)


def _x36_java(steps: list[str]) -> str:
    lines = []
    for st in steps:
        w = st.split(" ")
        n = str(len(w[1])) if w[2] == "=" else w[2]

        def opt(v: str) -> str:
            return "null" if v == "-" else f"Integer.valueOf({v})"

        lines.append(f'parse(t, "{w[1]}", {n}, {opt(w[3])}, {opt(w[4])}, {opt(w[5])});')
    return "\n".join(lines)


@needs_javac
def test_cics_task_web_parse_url_as_the_stub_does(tmp_path):
    """#4767 zECS (X36): CicsTask.webParse answers the steps above as the stub does, line for line, and refuses what the stub
    refuses."""
    helpers = """
    static void parse(CicsTask t, String url, int n, Integer hl, Integer pl, Integer ql) {
        String area = String.format("%-64s", url);
        CicsTask.WebParsed r = t.webParse(area, n, 16, hl, hl == null ? 0 : 40, pl, pl == null ? 0 : 40, ql,
                ql == null ? 0 : 40);
        String s = "parse " + r.resp() + "/" + r.resp2();
        if (r.resp() == 0) {
            s += " [" + r.scheme().stripTrailing() + "] [" + (hl == null ? "" : r.host()) + "] " + r.port() + " ["
                    + (pl == null ? "" : r.path()) + "] [" + (ql == null ? "" : r.query()) + "] "
                    + (hl == null ? "-" : r.host().length()) + " " + (pl == null ? "-" : r.path().length()) + " "
                    + (ql == null ? "-" : r.query().length());
        }
        System.out.println(s);
    }
"""
    refused = ", ".join("{" + ", ".join('"' + x + '"' for x in steps) + "}" for steps, _ in _X36_REFUSED)
    body = (
        f"""
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        {_x36_java(_X36_STEPS)}
        String[][] refused = {{{refused}}};
        for (String[] steps : refused) {{
            try {{
                for (String st : steps) {{
                    String[] w = st.split(" ");
                    Integer hl = w[3].equals("-") ? null : Integer.valueOf(w[3]);
                    Integer pl = w[4].equals("-") ? null : Integer.valueOf(w[4]);
                    Integer ql = w[5].equals("-") ? null : Integer.valueOf(w[5]);
                    parse(new CicsTask("ZC01", "ENTER", null, null), w[1], w[2].equals("=") ? w[1].length() : Integer.parseInt(w[2]), hl, pl, ql);
                }}
                System.out.println("not refused");
            }} catch (UnsupportedOperationException e) {{
                System.out.println(e.getMessage());
            }}
        }}
    }}
"""
        + helpers
        + "    static void unused() {"
    )
    out = _cics_task(tmp_path, body)
    lines = out.splitlines()
    n = len(_X36_EXPECTED)
    assert lines[:n] == _X36_EXPECTED
    assert len(lines[n:]) == len(_X36_REFUSED)
    for got, (_steps, why) in zip(lines[n:], _X36_REFUSED):
        assert why in got and got.endswith(": not modelled"), (got, why)


# ---- #4767 zECS (register X37): WEB SEND, the server side ------------------------------------------------------------
# one step a line: FROM FROMLENGTH|= MEDIATYPE|-|_ ACTION STATUSCODE|- STATUSTEXT|- STATUSLEN|- CONV (0 neither, 1 SRVCONVERT,
# 2 NOSRVCONVERT); "-": the option not given, "_": a blank MEDIATYPE. Areas: FROM 64, MEDIATYPE 56, STATUSTEXT 20 bytes.
_X37_CASES = [  # (steps, what both runtimes answer, the events they record: status, statustext, mediatype, body)
    (["OK-body = text/plain 2 200 OK 2 1"], ["send 0/0"], [(200, "OK", "text/plain", "OK-body", "IMMEDIATE")]),
    (["x 1 - 2 - - - 0"], ["send 0/0"], [(200, None, None, "x", "IMMEDIATE")]),
    (
        ["abc 3 application/json 2 404 Not_Found 9 2"],
        ["send 0/0"],
        [(404, "Not_Found", "application/json", "abc", "IMMEDIATE")],
    ),
    (["abc 3 text/xml 2 201 Created 3 0"], ["send 0/0"], [(201, "Cre", "text/xml", "abc", "IMMEDIATE")]),
    (["abc 3 TEXT/Plain 2 200 OK - 1"], ["send 0/0"], [(200, "OK" + " " * 18, "TEXT/Plain", "abc", "IMMEDIATE")]),
    (["x 1 - 7 - - - 0"], ["send 16/11"], []),
    (["x 1 - 2 204 - - 0"], ["send 16/72"], []),
    (["x 1 - 0 304 - - 0"], ["send 16/72"], []),
    # #4941 (X37): ACTION(EVENTUAL), and an omitted ACTION (EVENTUAL for a send that is not chunked), is held for the end of
    # the task; a second send replaces it; a send that ended in a condition leaves it as it was
    (["x 1 - 3 - - - 0"], ["send 0/0"], [(200, None, None, "x", "EVENTUAL")]),
    (["x 1 - 0 - - - 0"], ["send 0/0"], [(200, None, None, "x", "EVENTUAL")]),
    (["a 1 - 3 - - - 0", "b 1 - 0 201 - - 0"], ["send 0/0", "send 0/0"], [(201, None, None, "b", "EVENTUAL")]),
    (["a 1 - 3 - - - 0", "x 1 - 7 - - - 0"], ["send 0/0", "send 16/11"], [(200, None, None, "a", "EVENTUAL")]),
    (["a 1 - 3 - - - 0", "b 1 - 3 204 - - 0"], ["send 0/0", "send 16/72"], [(200, None, None, "a", "EVENTUAL")]),
]
_X37_REFUSED = [  # (steps, what both runtimes stop with)
    (["x 1 - 9 204 - - 0"], "more than one condition at once"),
    (["x 0 - 2 - - - 0"], "FROMLENGTH or STATUSLEN not above zero"),
    (["x 1 - 2 - OK 0 0"], "FROMLENGTH or STATUSLEN not above zero"),
    (["x 1 - 2 99 - - 0"], "STATUSCODE outside 100-599"),
    (["x 1 - 2 600 - - 0"], "STATUSCODE outside 100-599"),
    (["x 1 _ 2 - - - 0"], "MEDIATYPE blank or not type/subtype"),
    (["x 1 plain 2 - - - 0"], "MEDIATYPE blank or not type/subtype"),
    (["x 1 application/json 2 - - - 1"], "SRVCONVERT on a media type that is not text/*"),
    (["x 1 - 2 - - - 1"], "SRVCONVERT on a media type that is not text/*"),
    (["x 99 - 2 - - - 0"], "length beyond its area"),
    (["x 1 - 2 - OK 21 0"], "length beyond its area"),
    (["x 1 - 2 - - - 0", "y 1 - 2 - - - 0"], "WEB SEND after a response was sent"),
    (["x 1 - 2 - - - 0", "y 1 - 3 - - - 0"], "WEB SEND after a response was sent"),
    (["x 1 - 3 - - - 0", "y 1 - 2 - - - 0"], "WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send"),
]

_X37_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWSND(gg_cics *c, char *from, int fromcap, char *media, int mediacap, char *stext, int stextcap);
int GGCEND(gg_cics *c);
static gg_cics c;
static int given(const char *a) { return strcmp(a, "-") != 0; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[9], from[64], media[56], stext[20], flags[40] = "";
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 9; t = strtok(NULL, " ")) w[k++] = t;
        memset(from, ' ', sizeof from); memcpy(from, w[0], strlen(w[0]));
        memset(media, ' ', sizeof media); memset(stext, ' ', sizeof stext);
        c.len = w[1][0] == '=' ? (int)strlen(w[0]) : atoi(w[1]);
        if (given(w[2])) { strcat(flags, "MEDIA "); if (strcmp(w[2], "_") != 0) memcpy(media, w[2], strlen(w[2])); }
        c.item = atoi(w[3]);
        c.num = given(w[4]) ? atoi(w[4]) : -1;
        if (given(w[5])) { strcat(flags, "STEXT"); memcpy(stext, w[5], strlen(w[5])); }
        c.hours = given(w[6]) ? atoi(w[6]) : -1;
        c.mins = atoi(w[7]);
        memset(c.flags, ' ', 40); memcpy(c.flags, flags, strlen(flags));
        GGCWSND(&c, from, 64, media, 56, stext, 20);
        printf("send %d/%d\n", c.resp, c.resp2);
    }
    GGCEND(&c); /* the task ends: an ACTION(EVENTUAL) response is sent (#4941) */
    return 0;
}
"""


def _x37_stub_events(out: Path) -> list[tuple]:
    got = []
    for line in (
        (out / "events.txt").read_text(encoding="latin-1").splitlines() if (out / "events.txt").exists() else []
    ):
        seq, verb, *rest = line.split()
        if verb == "RETURN":  # (GGCEND's: the task's end, which sends an ACTION(EVENTUAL) response after it)
            continue
        assert verb == "WEB-SEND"
        kv = dict(a.split("=", 1) for a in rest[1:])

        def text(h: str) -> str | None:
            return None if h == "-" else bytes.fromhex(h).decode("latin-1")

        got.append(
            (
                int(kv["status"]),
                text(kv["stext"]),
                text(kv["media"]),
                (out / f"{seq}.bin").read_bytes().decode("latin-1") if (out / f"{seq}.bin").exists() else "",
                kv["action"],
            )
        )
    return got


@needs_cc
def test_the_stub_web_send(tmp_path):
    """#4767 zECS (register X37), IBM WEB SEND (server): the response to the stated request, recorded as WEB-SEND (status 200
    when not given, the reason phrase and media type when given, the body); INVREQ 11 for an invalid action, INVREQ 72 for
    204 / 205 / 304 with a body; what IBM leaves open (a send not IMMEDIATE, a second send, a malformed MEDIATYPE ...) is
    refused; without a stated request every send is refused."""
    exe = _stub(tmp_path, _X37_MAIN)
    req = tmp_path / "webreq.cfg"
    req.write_text("R HTTP 7A656373 80 PUT 2F6B -\n", encoding="ascii")
    for n, (steps, answers, events) in enumerate(_X37_CASES):
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        assert run.stdout.splitlines() == answers, steps
        assert _x37_stub_events(out) == events, steps
    for n, (steps, why) in enumerate(_X37_REFUSED):
        out = tmp_path / f"refused{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out0")}
    unstated = subprocess.run([str(exe), "x 1 - 2 - - - 0"], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert unstated.returncode == 98 and "HTTP request is not stated" in unstated.stdout


def _x37_java(steps: list[str]) -> str:
    lines = []
    for st in steps:
        w = st.split(" ")

        def area(v: str, width: int) -> str:
            return "null" if v == "-" else '"' + ("" if v == "_" else v).ljust(width) + '"'

        n = str(len(w[0])) if w[1] == "=" else w[1]
        lines.append(
            f'send(t, "{w[0].ljust(64)}", {n}, {area(w[2], 56)}, {w[3]}, {-1 if w[4] == "-" else w[4]}, '
            f"{area(w[5], 20)}, {-1 if w[6] == '-' else w[6]}, {w[7]});"
        )
    return "\n".join(lines)


@needs_javac
def test_cics_task_web_send_as_the_stub_does(tmp_path):
    """#4767 zECS (X37): CicsTask.webSend answers the steps above as the stub does, records the same WEB-SEND events, and
    refuses what the stub refuses."""
    helpers = """
    static void send(CicsTask t, String from, int n, String media, int action, int status, String stext, int sl, int conv) {
        int[] r = t.webSend(from, n, media, action, status, stext, sl, conv);
        System.out.println("send " + r[0] + "/" + r[1]);
    }
    static CicsTask task() {
        return new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "zecs", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), null, null));
    }
    static void events(CicsTask t) {
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println("ev " + e.get("status") + "|" + e.get("statustext") + "|" + e.get("mediatype") + "|"
                    + e.get("body") + "|" + e.get("action") + "|" + e.get("resp") + "/" + e.get("resp2"));
        }
    }
"""
    parts = []
    for steps, _answers, _events in _X37_CASES:
        parts.append("{ CicsTask t = task();\n" + _x37_java(steps) + '\nevents(t); System.out.println("--"); }')
    for steps, _why in _X37_REFUSED:
        parts.append(
            "{ CicsTask t = task(); try {\n" + _x37_java(steps) + '\nSystem.out.println("not refused"); }'
            " catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); } }"
        )
    parts.append(
        'try { send(new CicsTask("ZC01", "ENTER", null, null), "x".repeat(64), 1, null, 2, -1, null, -1, 0); }'
        " catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }"
    )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers, events in _X37_CASES:
        end = lines.index("--", pos)
        got = lines[pos:end]
        want = list(answers)
        for status, stext, media, body, action in events:
            want.append(
                f"ev {status}|{'null' if stext is None else stext}|{'null' if media is None else media}|{body}|{action}|0/0"
            )
        assert got == want, (steps, got, want)
        pos = end + 1
    refusals = [ln for ln in lines[pos:] if not ln.startswith("send ")]
    assert len(refusals) == len(_X37_REFUSED) + 1
    for got, (_steps, why) in zip(refusals, _X37_REFUSED):
        assert why in got and got.endswith(": not modelled"), (got, why)
    assert refusals[-1] == "the HTTP request is not stated (withHttpRequest): not modelled"


# ---- #4767 zECS (register X38): the server reading the request it serves --------------------------------------------------
# Four fixtures, one per request shape; a step a word-line, run alike by the stub (C) and CicsTask (Java) over areas of
# dots ('.'), so "the rest of the area is left alone" shows. Areas: EXTRACT host 20, method 10, version 15, path 30, query 20;
# RECEIVE into 16, media 56; READ name 32, value 24; WRITE name 32, value 40.
_X38_REQ = {
    "full": ("HTTPS", "zecs.example", 8443, "PUT", "HTTP/1.1", "/resources/ecs/a", "x=1&y=2",
             [("Authorization", "Basic QUJD"), ("Content-Type", "text/plain")], "text/plain", "hello world!"),
    "bare": ("HTTP", "h", 80, "GET", "HTTP/1.0", "/", "", [], None, None),
    "lower": ("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "", [("authorization", "x")], None, None),
    "twice": ("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "", [("A", "1"), ("A", "2")], None, None),
}  # fmt: skip
_D = ".".__mul__
_X38_CASES = [  # (fixture, steps, what both runtimes answer, the WEB-HEADER events (name, value))
    ("full", ["ext 20 10 15 30 20"], ["ext 0/0 zecs.example........|PUT.......|HTTP/1.1.......|/resources/ecs/a..............|"
                                      "x=1&y=2.............|8443|HTTPS|12,3,8,16,7"], []),
    ("full", ["ext 20 - - - -"], [f"ext 0/0 zecs.example........|{_D(10)}|{_D(15)}|{_D(30)}|{_D(20)}|8443|HTTPS|12,0,0,0,0"], []),
    ("full", ["ext 12 3 8 16 7"], ["ext 0/0 zecs.example........|PUT.......|HTTP/1.1.......|/resources/ecs/a..............|"
                                   "x=1&y=2.............|8443|HTTPS|12,3,8,16,7"], []),
    ("bare", ["ext 20 10 15 30 20"], [f"ext 0/0 h{_D(19)}|GET{_D(7)}|HTTP/1.0{_D(7)}|/{_D(29)}|{_D(20)}|80|HTTP|1,3,8,1,0"], []),
    ("full", ["ext 0 - - - -"], ["ext 22/21"], []),
    ("full", ["ext - - - 0 -"], ["ext 22/5"], []),
    ("full", ["ext - - 0 - -"], ["ext 22/7"], []),
    ("full", ["ext - 0 - - -"], ["WEB EXTRACT METHODLENGTH or QUERYSTRLEN not above zero"], []),
    ("full", ["ext - - - - 0"], ["WEB EXTRACT METHODLENGTH or QUERYSTRLEN not above zero"], []),
    ("full", ["ext 0 - - 0 -"], ["WEB EXTRACT with more than one condition at once"], []),
    ("full", ["ext 5 - - - -"], ["WEB EXTRACT piece longer than its length"], []),
    ("full", ["ext - 2 - - -"], ["WEB EXTRACT piece longer than its length"], []),
    ("full", ["ext - - 7 - -"], ["WEB EXTRACT piece longer than its length"], []),
    ("full", ["ext - - - 15 -"], ["WEB EXTRACT piece longer than its length"], []),
    ("full", ["ext - - - - 6"], ["WEB EXTRACT piece longer than its length"], []),
    ("full", ["ext 21 - - - -"], ["WEB EXTRACT length beyond its area"], []),
    ("full", ["ext - 11 - - -"], ["WEB EXTRACT length beyond its area"], []),
    ("full", ["ext - - 16 - -"], ["WEB EXTRACT length beyond its area"], []),
    ("full", ["ext - - - 31 -"], ["WEB EXTRACT length beyond its area"], []),
    ("full", ["ext - - - - 21"], ["WEB EXTRACT length beyond its area"], []),
    ("full", ["rcv 16 1"], ["rcv 0/0 hello world!....|12|text/plain"], []),
    ("full", ["rcv 12 0"], ["rcv 0/0 hello world!....|12|-"], []),
    ("full", ["rcv 5 1"], ["rcv 22/57 hello...........|5|text/plain"], []),
    ("full", ["rcv 0 0"], ["rcv 22/16"], []),
    ("full", ["rcv -3 1"], ["rcv 22/16"], []),
    ("full", ["rcv 17 0"], ["WEB RECEIVE length beyond its area"], []),
    ("full", ["rcv 5 0", "rcv 5 0"], ["rcv 22/57 hello...........|5|-", "a second WEB RECEIVE"], []),
    ("bare", ["rcv 5 0"], ["WEB RECEIVE of a request with no body"], []),
    ("full", ["rdh Authorization 13 24"], [f"rdh 0/0 Basic QUJD{_D(14)}|10"], []),
    ("full", ["rdh Content-Type 12 24"], [f"rdh 0/0 text/plain{_D(14)}|10"], []),
    ("full", ["rdh Authorization 13 10"], [f"rdh 0/0 Basic QUJD{_D(14)}|10"], []),
    ("full", ["rdh Authorization 13 9"], ["WEB READ HTTPHEADER value longer than VALUELENGTH"], []),
    ("full", ["rdh X-Missing 9 24"], ["rdh 13/1"], []),
    ("full", ["rdh Autho 5 24"], ["rdh 13/1"], []),
    ("full", ["rdh Authorization 13 0"], ["rdh 22/1"], []),
    ("full", ["rdh X-Missing 9 0"], ["WEB READ HTTPHEADER with more than one condition at once"], []),
    ("full", ["rdh authorization 13 24"], ["WEB READ HTTPHEADER header name found only without case"], []),
    ("full", ["rdh Authorization 0 24"], ["WEB READ HTTPHEADER NAMELENGTH not above zero or past its area"], []),
    ("full", ["rdh Authorization 33 24"], ["WEB READ HTTPHEADER NAMELENGTH not above zero or past its area"], []),
    ("full", ["rdh Authorization 13 25"], ["WEB READ HTTPHEADER length beyond its area"], []),
    ("bare", ["rdh Authorization 13 24"], ["rdh 16/43"], []),
    ("bare", ["rdh Authorization 13 0"], ["WEB READ HTTPHEADER with more than one condition at once"], []),
    ("lower", ["rdh authorization 13 24"], [f"rdh 0/0 x{_D(23)}|1"], []),
    ("lower", ["rdh Authorization 13 24"], ["WEB READ HTTPHEADER header name found only without case"], []),
    ("twice", ["rdh A 1 24"], ["WEB READ HTTPHEADER two headers of the name"], []),
    ("full", ["wrh X-Zecs 6 abc 3"], ["wrh 0/0"], [("X-Zecs", "abc")]),
    ("full", ["wrh X-Zecs 6 abc 3", "wrh X-Zecs 6 abd 3"], ["wrh 0/0", "wrh 0/0"], [("X-Zecs", "abc"), ("X-Zecs", "abd")]),
    ("full", ["wrh Access-Control-Allow-Origin 27 * 1"], ["wrh 0/0"], [("Access-Control-Allow-Origin", "*")]),
    ("full", ["wrh X-Zecs 3 abc 3"], ["wrh 0/0"], [("X-Z", "abc")]),
    ("full", ["wrh X-A 0 v 1"], ["wrh 22/35"], []),
    ("full", ["wrh X-A 3 v 0"], ["wrh 22/55"], []),
    ("full", ["wrh X-A 3 v 32001"], ["wrh 22/55"], []),
    ("full", ["wrh X-A 0 v 0"], ["WEB WRITE HTTPHEADER with more than one condition at once"], []),
    ("full", ["wrh X-A 4 v 1"], ["WEB WRITE HTTPHEADER name blank or holding a blank or a colon"], []),
    ("full", ["wrh X:A 3 v 1"], ["WEB WRITE HTTPHEADER name blank or holding a blank or a colon"], []),
    ("full", ["wrh X-A 33 v 1"], ["WEB WRITE HTTPHEADER length beyond its area"], []),
    ("full", ["wrh X-A 3 v 41"], ["WEB WRITE HTTPHEADER length beyond its area"], []),
    ("full", ["snd", "wrh X-A 3 v 1"], ["snd 0/0", "WEB WRITE HTTPHEADER after the response was sent"], []),
    ("full", ["snde", "wrh X-A 3 v 1"], ["snd 0/0", "WEB WRITE HTTPHEADER after the response was sent"], []),  # (#4941: held)
    ("full", ["wrh X-A 3 v 1", "snde"], ["wrh 0/0", "snd 0/0"], [("X-A", "v")]),
    # #4941 WEB RETRIEVE (X41): INVREQ 2 before any WEB SEND, NOTFND 1 once one was issued (every accepted send is IMMEDIATE)
    ("full", ["rtv"], ["rtv 16/2"], []),
    ("bare", ["rtv"], ["rtv 16/2"], []),
    ("full", ["snd", "rtv"], ["snd 0/0", "rtv 13/1"], []),
    ("bare", ["snd", "rtv", "rtv"], ["snd 0/0", "rtv 13/1", "rtv 13/1"], []),
    ("full", ["sndbad", "snd", "rtv"], ["snd 16/11", "snd 0/0", "rtv 13/1"], []),
    ("full", ["sndbad", "rtv"], ["snd 16/11", "WEB RETRIEVE after a WEB SEND that ended in a condition"], []),
    ("full", ["wrh X-A 3 v 1", "rtv"], ["wrh 0/0", "rtv 16/2"], [("X-A", "v")]),
    ("full", ["snde", "rtv"], ["snd 0/0", "rtv 13/1"], []),  # (#4941: an EVENTUAL send of a FROM body is not a document)
    ("full", ["sndbad", "snde", "rtv"], ["snd 16/11", "snd 0/0", "rtv 13/1"], []),
    ("full", ["snd", "sndbad", "rtv"], ["snd 0/0", "WEB SEND after a response was sent"], []),
]  # fmt: skip

_X38_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWEXT(gg_cics *c, char *host, int hostcap, char *method, int methodcap, char *version, int versioncap, char *path,
            int pathcap, char *query, int querycap);
int GGCWRCV(gg_cics *c, char *into, int intocap, char *media, int mediacap);
int GGCWRDH(gg_cics *c, char *name, int namecap, char *value, int valuecap);
int GGCWWRH(gg_cics *c, char *name, int namecap, char *value, int valuecap);
int GGCWSND(gg_cics *c, char *from, int fromcap, char *media, int mediacap, char *stext, int stextcap);
int GGCWRTV(gg_cics *c, char *tok, int toklen);
static gg_cics c;
static void flags(const char *s) { memset(c.flags, ' ', 40); memcpy(c.flags, s, strlen(s)); }
static void trimprint(const char *s, int n) { while (n > 0 && s[n - 1] == ' ') n--; printf("%.*s", n, s); }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[6], host[20], method[10], version[15], path[30], query[20], into[16], media[56], name[32], value[40];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 6; t = strtok(NULL, " ")) w[k++] = t;
        memset(host, '.', 20); memset(method, '.', 10); memset(version, '.', 15); memset(path, '.', 30);
        memset(query, '.', 20); memset(into, '.', 16); memset(media, ' ', 56);
        if (strcmp(w[0], "ext") == 0) {
            char fl[80] = "";
            const char *names[5] = {"HOST ", "METHOD ", "VERSION ", "PATH ", "QUERY "};
            int *len[5] = {&c.len, &c.hours, &c.mins, &c.secs, &c.item};
            for (int j = 0; j < 5; j++) {
                *len[j] = strcmp(w[1 + j], "-") == 0 ? 0 : atoi(w[1 + j]);
                if (strcmp(w[1 + j], "-") != 0) strcat(fl, names[j]);
            }
            flags(fl);
            GGCWEXT(&c, host, 20, method, 10, version, 15, path, 30, query, 20);
            printf("ext %d/%d", c.resp, c.resp2);
            if (c.resp == 0) {
                printf(" %.20s|%.10s|%.15s|%.30s|%.20s|%d|", host, method, version, path, query, c.num);
                trimprint(c.name1, 8);
                printf("|%d,%d,%d,%d,%d", c.len, c.hours, c.mins, c.secs, c.item);
            }
            printf("\n");
        } else if (strcmp(w[0], "rcv") == 0) {
            c.num = atoi(w[1]);
            flags(strcmp(w[2], "1") == 0 ? "MEDIA" : "");
            GGCWRCV(&c, into, 16, media, 56);
            printf("rcv %d/%d", c.resp, c.resp2);
            if (c.resp == 0 || c.resp2 == 57) {
                printf(" %.16s|%d|", into, c.len);
                if (strcmp(w[2], "1") == 0) trimprint(media, 56); else printf("-");
            }
            printf("\n");
        } else if (strcmp(w[0], "rdh") == 0) {
            memset(name, ' ', 32); memcpy(name, w[1], strlen(w[1])); memset(value, '.', 24);
            c.len = atoi(w[2]); c.num = atoi(w[3]);
            GGCWRDH(&c, name, 32, value, 24);
            printf("rdh %d/%d", c.resp, c.resp2);
            if (c.resp == 0) printf(" %.24s|%d", value, c.num);
            printf("\n");
        } else if (strcmp(w[0], "wrh") == 0) {
            memset(name, ' ', 32); memcpy(name, w[1], strlen(w[1])); memset(value, ' ', 40); memcpy(value, w[3], strlen(w[3]));
            c.len = atoi(w[2]); c.num = atoi(w[4]);
            GGCWWRH(&c, name, 32, value, 40);
            printf("wrh %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "rtv") == 0) {
            char tok[16];
            memset(tok, ' ', 16);
            GGCWRTV(&c, tok, 16);
            printf("rtv %d/%d\n", c.resp, c.resp2);
        } else {
            char from[64], stext[20];
            memset(from, ' ', 64); memset(stext, ' ', 20);
            c.len = 1; c.item = strcmp(w[0], "sndbad") == 0 ? 99 : strcmp(w[0], "snde") == 0 ? 3 : 2; c.num = -1; c.hours = -1; c.mins = 0; flags("");
            GGCWSND(&c, from, 64, media, 56, stext, 20);
            printf("snd %d/%d\n", c.resp, c.resp2);
        }
    }
    return 0;
}
"""


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK")
def test_cics_task_web_percent_decoding_is_ascii_hex_only(tmp_path):
    """#4940: a non-ASCII digit after '%' (fullwidth, Arabic-Indic, ...) is refused, never decoded as hex."""
    body = (
        "        try {\n"
        '        var m = CicsTask.class.getDeclaredMethod("webPlain", String.class, String.class);\n'
        "        m.setAccessible(true);\n"
        '        for (String s : new String[] {"%41", "%4a", "%4A", "%\\uff14\\uff11", "%\\u0664\\u0661",\n'
        '                "%4\\uff11", "%\\u0664A", "%g1"}) {\n'
        '            try { System.out.println(m.invoke(null, "FORMFIELD", s)); }\n'
        '            catch (java.lang.reflect.InvocationTargetException e) { System.out.println("refused"); }\n'
        "        }\n"
        "        } catch (Exception e) { throw new RuntimeException(e); }"
    )
    out = _cics_task(tmp_path, body).split()
    assert out == ["A", "J", "J", "refused", "refused", "refused", "refused", "refused"]


def _x38_cfg(name: str) -> str:
    scheme, host, port, method, version, path, query, headers, media, body = _X38_REQ[name]
    hx = lambda v: v.encode("latin-1").hex().upper() if v else "-"  # noqa: E731
    lines = [f"R {scheme} {hx(host)} {port} {method} {hx(path)} {hx(query)}", f"V {hx(version)}"]
    if body is not None:
        lines.append(f"B {hx(media)} {hx(body)}")
    lines += [f"H {hx(n)} {hx(v)}" for n, v in headers]
    return "".join(f"{ln}\n" for ln in lines)


def _x38_stub_events(out: Path) -> list[tuple]:
    got = []
    for line in (
        (out / "events.txt").read_text(encoding="latin-1").splitlines() if (out / "events.txt").exists() else []
    ):
        _seq, verb, *rest = line.split()
        if verb != "WEB-HEADER":  # (the "snd" step's WEB-SEND is X37's)
            continue
        kv = dict(a.split("=", 1) for a in rest[1:])
        got.append((bytes.fromhex(kv["name"]).decode("latin-1"), bytes.fromhex(kv["value"]).decode("latin-1")))
    return got


@needs_cc
def test_the_stub_serves_the_stated_request(tmp_path):
    """#4767 zECS (register X38), IBM WEB EXTRACT / WEB RECEIVE / WEB READ HTTPHEADER / WEB WRITE HTTPHEADER (server): the
    pieces, body and headers of the stated request, the documented conditions with their RESP2, the response header recorded
    as WEB-HEADER; what IBM leaves open is refused by name; without a stated request every command is refused."""
    exe = _stub(tmp_path, _X38_MAIN)
    for n, (fixture, steps, answers, events) in enumerate(_X38_CASES):
        req = tmp_path / f"webreq{n}.cfg"
        req.write_text(_x38_cfg(fixture), encoding="ascii")
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if (
            len(answers) == 1
            and not answers[0].split()[0] in ("ext", "rcv", "rdh", "wrh", "snd", "rtv")
            or (len(answers) > 1 and not answers[-1].split()[0] in ("ext", "rcv", "rdh", "wrh", "snd", "rtv"))
        ):
            refused = answers[-1]
            assert run.returncode == 98 and refused + ": not modelled" in run.stdout, (steps, run.stdout)
            assert run.stdout.splitlines()[:-1] == answers[:-1], steps
        else:
            assert run.returncode == 0 and run.stdout.splitlines() == answers, (steps, run.stdout)
        assert _x38_stub_events(out) == events, steps
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out0")}
    for step in ("ext 20 - - - -", "rcv 5 0", "rdh A 1 24", "wrh A 1 v 1", "rtv"):
        unstated = subprocess.run([str(exe), step], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert unstated.returncode == 98 and "HTTP request is not stated" in unstated.stdout, step


def _x38_java(steps: list[str]) -> str:
    return "\n".join(f'step(t, "{st}");' for st in steps)


@needs_javac
def test_cics_task_serves_the_stated_request_as_the_stub_does(tmp_path):
    """#4767 zECS (X38): CicsTask.webExtract / webReceive / webReadHeader / webWriteHeader answer the steps above as the stub
    does, record the same WEB-HEADER events and refuse what the stub refuses."""
    helpers = r"""
    static String area(String piece, int cap) {
        StringBuilder b = new StringBuilder(piece);
        while (b.length() < cap) b.append('.');
        return b.toString();
    }
    static String pad(String s, int n) { return String.format("%-" + n + "s", s); }
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        switch (w[0]) {
            case "ext" -> {
                Integer[] l = new Integer[5];
                for (int j = 0; j < 5; j++) l[j] = w[1 + j].equals("-") ? null : Integer.valueOf(w[1 + j]);
                CicsTask.WebExtracted r = t.webExtract(l[0], 20, l[1], 10, l[2], 15, l[3], 30, l[4], 20);
                if (r.resp() != 0) { System.out.println("ext " + r.resp() + "/" + r.resp2()); return; }
                String[] p = {r.host(), r.method(), r.version(), r.path(), r.query()};
                int[] cap = {20, 10, 15, 30, 20};
                StringBuilder o = new StringBuilder("ext 0/0 ");
                StringBuilder lens = new StringBuilder();
                for (int j = 0; j < 5; j++) {
                    o.append(l[j] == null ? area("", cap[j]) : area(p[j], cap[j])).append('|');
                    lens.append(j > 0 ? "," : "").append(l[j] == null ? 0 : p[j].length());
                }
                System.out.println(o + "" + r.port() + "|" + (r.scheme() == 1029 ? "HTTPS" : "HTTP") + "|" + lens);
            }
            case "rcv" -> {
                CicsTask.WebReceived r = t.webReceive(Integer.parseInt(w[1]), 16);
                String o = "rcv " + r.resp() + "/" + r.resp2();
                if (r.body() != null) o += " " + area(r.body(), 16) + "|" + r.body().length() + "|"
                        + (w[2].equals("1") ? r.mediaType() : "-");
                System.out.println(o);
            }
            case "rdh" -> {
                CicsTask.WebHeader r = t.webReadHeader(pad(w[1], 32), Integer.parseInt(w[2]), Integer.parseInt(w[3]), 24);
                String o = "rdh " + r.resp() + "/" + r.resp2();
                if (r.value() != null) o += " " + area(r.value(), 24) + "|" + r.value().length();
                System.out.println(o);
            }
            case "wrh" -> {
                int[] r = t.webWriteHeader(pad(w[1], 32), Integer.parseInt(w[2]), pad(w[3], 40), Integer.parseInt(w[4]));
                System.out.println("wrh " + r[0] + "/" + r[1]);
            }
            case "rtv" -> {
                var r = t.webRetrieve();
                System.out.println("rtv " + r.resp() + "/" + r.resp2());
            }
            default -> {
                int[] r = t.webSend(pad("", 64), 1, null, w[0].equals("sndbad") ? 99 : w[0].equals("snde") ? 3 : 2, -1, null, -1, 0);
                System.out.println("snd " + r[0] + "/" + r[1]);
            }
        }
    }
    static CicsTask task(String scheme, String host, int port, String method, String version, String path, String query,
                         java.util.List<String[]> headers, String media, String body) {
        return new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest(scheme, host, port, method,
                version, path, query, headers, media, body));
    }
    static CicsTask fixture(String name) {
        return switch (name) {
            case "full" -> task("HTTPS", "zecs.example", 8443, "PUT", "HTTP/1.1", "/resources/ecs/a", "x=1&y=2",
                    java.util.List.of(new String[] {"Authorization", "Basic QUJD"}, new String[] {"Content-Type", "text/plain"}),
                    "text/plain", "hello world!");
            case "bare" -> task("HTTP", "h", 80, "GET", "HTTP/1.0", "/", "", java.util.List.of(), null, null);
            case "lower" -> task("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "", java.util.List.<String[]>of(new String[] {"authorization", "x"}), null, null);
            default -> task("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "",
                    java.util.List.of(new String[] {"A", "1"}, new String[] {"A", "2"}), null, null);
        };
    }
    static void events(CicsTask t) {
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("WEB-HEADER")) System.out.println("ev " + e.get("name") + "|" + e.get("value"));
        }
    }
"""
    parts = []
    for fixture, steps, answers, _events in _X38_CASES:
        parts.append(
            f'{{ CicsTask t = fixture("{fixture}");\n try {{\n{_x38_java(steps)}\n}} catch (UnsupportedOperationException e) {{'
            ' System.out.println("refused " + e.getMessage()); }\nevents(t); System.out.println("--"); }'
        )
    parts.append(
        'for (String s : new String[] {"ext 20 - - - -", "rcv 5 0", "rdh A 1 24", "wrh A 1 v 1", "rtv"}) { try { step(new CicsTask("ZC01", '
        '"ENTER", null, null), s); } catch (UnsupportedOperationException e) { System.out.println("refused " + e.getMessage()); } }'
    )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for fixture, steps, answers, events in _X38_CASES:
        end = lines.index("--", pos)
        got = lines[pos:end]
        want = []
        for a in answers:
            head = a.split()[0]
            want.append(a if head in ("ext", "rcv", "rdh", "wrh", "snd", "rtv") else f"refused {a}: not modelled")
        want += [f"ev {n}|{v}" for n, v in events]
        assert got == want, (fixture, steps, got, want)
        pos = end + 1
    unstated = lines[pos:]
    assert unstated == ["refused the HTTP request is not stated (withHttpRequest): not modelled"] * 5


# #4767 (X38): WEB RECEIVE is recorded as WEB-RECEIVE (the request's media type, the bytes returned, RESP, RESP2) by both runtimes.
_X38_RECEIVES = [  # (steps, the events: (media type, body, resp, resp2))
    (["rcv 16 1"], [("text/plain", "hello world!", 0, 0)]),
    (["rcv 12 0"], [("text/plain", "hello world!", 0, 0)]),
    (["rcv 5 1"], [("text/plain", "hello", 22, 57)]),
    (["rcv 0 0"], [(None, None, 22, 16)]),
    (["rcv -3 1"], [(None, None, 22, 16)]),
    (["rcv 5 0", "rcv 5 0"], [("text/plain", "hello", 22, 57)]),  # (the second receive is refused: no second event)
]


_X38_BIG_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWRCV(gg_cics *c, char *into, int intocap, char *media, int mediacap);
static gg_cics c;
int main(int argc, char **argv) {
    static char into[200000];
    char media[56];
    long sum = 0;
    int maxl = argc > 1 ? atoi(argv[1]) : 150000;
    memset(into, 0, sizeof into);
    memset(c.flags, ' ', 40);
    c.num = maxl;
    GGCWRCV(&c, into, (int)sizeof into, media, 56);
    for (int i = 0; i < c.len; i++) sum += (unsigned char)into[i];
    printf("rcv %d/%d len=%d sum=%ld\n", c.resp, c.resp2, c.len, sum);
    return 0;
}
"""


def _big_receive(tmp_path: Path, exe: Path, cfg: str, *args: str) -> subprocess.CompletedProcess[str]:
    req = tmp_path / "bigreq.cfg"
    req.write_text(cfg, encoding="ascii")
    out = tmp_path / "bigout"
    out.mkdir(exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
    return subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=False)  # noqa: S603


@needs_cc
@pytest.mark.parametrize("size", [1, 15999, 16499, 16500, 31999, 32000, 32001, 40000, 100000])
def test_the_stub_web_receive_loads_a_request_body_of_any_size(tmp_path, size):
    """#6072: a stated body of 32000 bytes or more (64000 hex characters) was split by the 33000-byte token buffer, so the B
    line was dropped and WEB RECEIVE saw no body. Every size now loads whole; MAXLENGTH still cuts it (LENGERR 57)."""
    exe = _stub(tmp_path, _X38_BIG_MAIN)
    body = bytes((i * 7 + 3) % 251 for i in range(size))
    cfg = f"R HTTP 7A656373 80 PUT 2F6B -\nB 746578742F706C61696E {body.hex().upper()}\n"
    run = _big_receive(tmp_path, exe, cfg)
    assert run.returncode == 0, run.stdout
    assert run.stdout.splitlines() == [f"rcv 0/0 len={size} sum={sum(body)}"]
    if size > 10:
        cut = _big_receive(tmp_path, exe, cfg, "10")
        assert cut.stdout.splitlines() == [f"rcv 22/57 len=10 sum={sum(body[:10])}"]


@needs_cc
def test_the_stub_refuses_a_stated_line_longer_than_it_reads(tmp_path):
    """#6072: a line past the stub's buffer is refused by name, never split into extra tokens (which dropped the body)."""
    exe = _stub(tmp_path, _X38_BIG_MAIN)
    cfg = f"R HTTP 7A656373 80 PUT 2F6B -\nB 74 {'41' * 140000}\n"
    run = _big_receive(tmp_path, exe, cfg)
    assert run.returncode == 98 and "line longer than the stub reads" in run.stdout, run.stdout


@needs_cc
def test_the_stub_records_web_receive(tmp_path):
    """#4767 (X38): the stub logs a WEB-RECEIVE event for each WEB RECEIVE that ended NORMAL or in a LENGERR."""
    exe = _stub(tmp_path, _X38_MAIN)
    for n, (steps, want) in enumerate(_X38_RECEIVES):
        req = tmp_path / f"rcvreq{n}.cfg"
        req.write_text(_x38_cfg("full"), encoding="ascii")
        out = tmp_path / f"rcvout{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        got = []
        for line in (out / "events.txt").read_text(encoding="latin-1").splitlines():
            seq, verb, *rest = line.split()
            if verb != "WEB-RECEIVE":
                continue
            kv = dict(a.split("=", 1) for a in rest[1:])
            body = out / f"{seq}.bin"
            got.append((None if kv["media"] == "-" else bytes.fromhex(kv["media"]).decode("latin-1"),
                        None if kv["resp2"] == "16" else (body.read_bytes().decode("latin-1") if body.exists() else ""),
                        int(kv["resp"]), int(kv["resp2"])))  # fmt: skip
        assert got == want, steps


@needs_javac
def test_cics_task_records_web_receive(tmp_path):
    """#4767 (X38): CicsTask.webReceive records the same WEB-RECEIVE events as the stub."""
    helpers = r"""
    static void run(int[] maxes) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTPS", "zecs.example",
                8443, "PUT", "HTTP/1.1", "/resources/ecs/a", "x=1&y=2", java.util.List.of(), "text/plain", "hello world!"));
        try {
            for (int m : maxes) t.webReceive(m, 16);
        } catch (UnsupportedOperationException e) {
            // (a second receive is refused)
        }
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("WEB-RECEIVE"))
                System.out.println("ev " + e.get("mediatype") + "|" + e.get("body") + "|" + e.get("resp") + "|" + e.get("resp2"));
        }
        System.out.println("--");
    }
"""
    parts = [f"run(new int[] {{{', '.join(st.split()[1] for st in steps)}}});" for steps, _want in _X38_RECEIVES]
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, want in _X38_RECEIVES:
        end = lines.index("--", pos)
        assert lines[pos:end] == [f"ev {m}|{b}|{r}|{r2}".replace("None", "null") for m, b, r, r2 in want], steps
        pos = end + 1


# ---- #4771 zECS (register X47): the pointer lane -- GETMAIN, FREEMAIN, WEB RECEIVE SET ----------------------------------------
# A step a word-line, run alike by the stub (C) and CicsTask (Java): pointer slots 0 and 1; `gm SLOT LENGTH SHORT INIT` GETMAIN
# (SHORT 1: the LENGTH form; INIT the INITIMG byte), `fm SLOT` FREEMAIN, `rs SLOT MAX` WEB RECEIVE SET (MAX -: no MAXLENGTH),
# `adr SLOT` the pointer set to a record's address, `nul SLOT` to NULL, `rd SLOT N` the first N bytes of the storage (hex). The
# request is the "full" fixture of X38 (body "hello world!", text/plain) unless the case says "bare" (no body).
_X47_CASES = [  # (fixture, steps, what both runtimes answer; a last answer that is no step line is a refusal)
    ("full", ["gm 0 8 0 255", "rd 0 4"], ["gm 0/0", "rd FFFFFFFF"]),
    ("full", ["gm 0 8 0 0", "rd 0 8"], ["gm 0/0", "rd 0000000000000000"]),
    ("full", ["gm 0 100 1 65", "rd 0 3"], ["gm 0/0", "rd 414141"]),
    ("full", ["gm 0 0 0 0"], ["gm 22/1"]),
    ("full", ["gm 0 -5 0 0"], ["gm 22/1"]),
    ("full", ["gm 0 0 1 0"], ["gm 22/1"]),
    ("full", ["gm 0 65520 1 7", "rd 0 2"], ["gm 0/0", "rd 0707"]),
    ("full", ["gm 0 65521 1 7"], ["GETMAIN length beyond the limit"]),
    ("full", ["gm 0 268435457 0 7"], ["GETMAIN length beyond the limit"]),
    ("full", ["gm 0 4 0 1", "fm 0"], ["gm 0/0", "fm 0/0"]),
    ("full", ["gm 0 4 0 1", "gm 1 4 0 2", "fm 0", "fm 1"], ["gm 0/0", "gm 0/0", "fm 0/0", "fm 0/0"]),
    ("full", ["gm 0 4 0 1", "fm 0", "fm 0"], ["gm 0/0", "fm 0/0", "FREEMAIN of storage already freed or received"]),
    ("full", ["nul 1", "fm 1"], ["fm 16/1"]),
    ("full", ["adr 1", "fm 1"], ["fm 16/1"]),
    ("full", ["gm 0 0 0 0", "fm 0"], ["gm 22/1", "fm 16/1"]),  # (LENGERR sets the pointer to zero)
    ("full", ["rs 0 16", "rd 0 12"], ["rs 0/0 12|text/plain", "rd 68656C6C6F20776F726C6421"]),
    ("full", ["rs 0 -", "rd 0 12"], ["rs 0/0 12|text/plain", "rd 68656C6C6F20776F726C6421"]),
    ("full", ["rs 0 5", "rd 0 5"], ["rs 22/57 5|text/plain", "rd 68656C6C6F"]),
    ("full", ["rs 0 0"], ["rs 22/16"]),
    ("full", ["rs 0 -3"], ["rs 22/16"]),
    ("full", ["nul 0", "rs 0 0", "fm 0"], ["rs 22/16", "fm 16/1"]),  # (LENGERR 16 leaves the pointer as it was)
    ("full", ["rs 0 16", "fm 0"], ["rs 0/0 12|text/plain", "FREEMAIN of storage already freed or received"]),
    ("full", ["rs 0 16", "rs 1 16"], ["rs 0/0 12|text/plain", "a second WEB RECEIVE"]),
    ("bare", ["rs 0 16"], ["WEB RECEIVE of a request with no body"]),
]
_X47_STEPS = ("gm", "fm", "rs", "adr", "nul", "rd")

_X47_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen);
int GGCFREM(gg_cics *c, void **slot);
int GGCWRCS(gg_cics *c, void **slot, char *media, int mediacap);
static gg_cics c;
static void flags(const char *s) { memset(c.flags, ' ', 40); memcpy(c.flags, s, strlen(s)); }
int main(int argc, char **argv) {
    static void *p[2];
    static char record[8];
    for (int i = 1; i < argc; i++) {
        char *w[5];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 5; t = strtok(NULL, " ")) w[k++] = t;
        int s = atoi(w[1]);
        if (strcmp(w[0], "gm") == 0) {
            char img = (char)atoi(w[4]);
            c.num = atoi(w[2]);
            flags(strcmp(w[3], "1") == 0 ? "SHORT" : "");
            GGCGETM(&c, &p[s], &img, 1);
            printf("gm %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "fm") == 0) {
            GGCFREM(&c, &p[s]);
            printf("fm %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "rs") == 0) {
            char media[56];
            memset(media, ' ', 56);
            c.num = strcmp(w[2], "-") == 0 ? 2147483647 : atoi(w[2]);
            flags("MEDIA");
            GGCWRCS(&c, &p[s], media, 56);
            printf("rs %d/%d", c.resp, c.resp2);
            if (c.resp == 0 || c.resp2 == 57) {
                int m = 56;
                while (m > 0 && media[m - 1] == ' ') m--;
                printf(" %d|%.*s", c.len, m, media);
            }
            printf("\n");
        } else if (strcmp(w[0], "adr") == 0) {
            p[s] = record;
        } else if (strcmp(w[0], "nul") == 0) {
            p[s] = NULL;
        } else {
            printf("rd ");
            for (int j = 0; j < atoi(w[2]); j++) printf("%02X", ((unsigned char *)p[s])[j]);
            printf("\n");
        }
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_hands_out_task_storage_through_pointers(tmp_path):
    """#4771 (register X47), IBM GETMAIN / FREEMAIN / WEB RECEIVE SET: the documented conditions with their RESP2; what IBM
    leaves open is refused by name."""
    exe = _stub(tmp_path, _X47_MAIN)
    for n, (fixture, steps, answers) in enumerate(_X47_CASES):
        req = tmp_path / f"webreq{n}.cfg"
        req.write_text(_x38_cfg(fixture), encoding="ascii")
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if answers[-1].split()[0] in _X47_STEPS + ("gm", "fm", "rs", "rd"):
            assert run.returncode == 0 and run.stdout.splitlines() == answers, (steps, run.stdout)
        else:
            assert run.returncode == 98 and answers[-1] + ": not modelled" in run.stdout, (steps, run.stdout)
            assert run.stdout.splitlines()[:-1] == answers[:-1], steps


@needs_javac
def test_cics_task_hands_out_task_storage_as_the_stub_does(tmp_path):
    """#4771 (X47): CicsTask.getmain / freemain / acquireReceived / storageAt answer the steps above as the stub does."""
    helpers = r"""
    static long[] slot = new long[2];
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        int s = Integer.parseInt(w[1]);
        switch (w[0]) {
            case "gm" -> {
                long[] r = t.getmain(Long.parseLong(w[2]), w[3].equals("1"), Integer.parseInt(w[4]));
                slot[s] = r[2];
                System.out.println("gm " + r[0] + "/" + r[1]);
            }
            case "fm" -> {
                int[] r = t.freemain(slot[s]);
                System.out.println("fm " + r[0] + "/" + r[1]);
            }
            case "rs" -> {
                CicsTask.WebReceived r = t.webReceive(w[2].equals("-") ? Integer.MAX_VALUE : Integer.parseInt(w[2]), Integer.MAX_VALUE);
                String o = "rs " + r.resp() + "/" + r.resp2();
                if (r.body() != null) {
                    slot[s] = t.acquireReceived(r.body().getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
                    o += " " + r.body().length() + "|" + r.mediaType();
                }
                System.out.println(o);
            }
            case "adr" -> slot[s] = t.addressOf(new byte[8]);
            case "nul" -> slot[s] = 0;
            default -> {
                byte[] b = t.storageAt(slot[s], 0);
                StringBuilder o = new StringBuilder("rd ");
                for (int j = 0; j < Integer.parseInt(w[2]); j++) o.append(String.format("%02X", b[j] & 0xFF));
                System.out.println(o);
            }
        }
    }
    static CicsTask fixture(String name) {
        return new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(name.equals("full")
                ? new CicsTask.HttpRequest("HTTPS", "zecs.example", 8443, "PUT", "HTTP/1.1", "/resources/ecs/a", "x=1&y=2",
                        java.util.List.of(), "text/plain", "hello world!")
                : new CicsTask.HttpRequest("HTTP", "h", 80, "GET", "HTTP/1.0", "/", "", java.util.List.of(), null, null));
    }
"""
    parts = []
    for fixture, steps, _answers in _X47_CASES:
        run = "\n".join(f'step(t, "{st}");' for st in steps)
        parts.append(
            f'{{ CicsTask t = fixture("{fixture}"); slot = new long[2];\n try {{\n{run}\n}} catch (UnsupportedOperationException e) {{'
            ' System.out.println("refused " + e.getMessage()); }\nSystem.out.println("--"); }'
        )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for fixture, steps, answers in _X47_CASES:
        end = lines.index("--", pos)
        want = [a if a.split()[0] in _X47_STEPS else f"refused {a}: not modelled" for a in answers]
        assert lines[pos:end] == want, (fixture, steps, lines[pos:end], want)
        pos = end + 1


# ---- #4767 zECS (register X30): GET DCOUNTER INCREMENT [WRAP] ---------------------------------------------------------------
# a step a line: NAME POOL INCREMENT -- "-" for the blank pool; what both runtimes answer: "resp/resp2 value|the counter after",
# or the refusal. Counters: ZC01_ZECS 41, BIGCNT 4294967294, TOP 4294967295.
_X30_CASES = [
    (["ZC01_ZECS - 1"], ["0/0 41|42"]),
    (["ZC01_ZECS - 5"], ["0/0 41|46"]),
    (["ZC01_ZECS - 5", "ZC01_ZECS - 1"], ["0/0 41|46", "0/0 46|47"]),
    (["BIGCNT - 1"], ["0/0 4294967294|4294967295"]),
    (["NOPE - 1"], ["16/201"]),
    (["lower - 1"], ["16/404"]),
    (["1ST - 1"], ["16/404"]),
    (["ZC01_ZECS lowerpl 1"], ["16/403"]),
]
_X30_REFUSED = [
    (["ZC01_ZECS - 0"], "GET COUNTER with an INCREMENT not above zero"),
    (["BIGCNT - 2"], "GET COUNTER past 4294967295: the counter's maximum is not stated"),
    (["TOP - 1"], "GET COUNTER past 4294967295: the counter's maximum is not stated"),
    (["ZC01_ZECS - 4294967296"], "GET COUNTER past 4294967295: the counter's maximum is not stated"),
]

_X30_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGDCN(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
static gg_cics c;
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[3];
        unsigned char value[8], inc[8];
        unsigned long long n = strtoull(argv[i] + strlen(argv[i]) - 1, NULL, 10), v = 0;
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 3; t = strtok(NULL, " ")) w[k++] = t;
        n = strtoull(w[2], NULL, 10);
        for (int j = 7; j >= 0; j--) { inc[j] = (unsigned char)(n & 255); n >>= 8; }
        memset(c.qname, ' ', 16); memcpy(c.qname, w[0], strlen(w[0]));
        memset(c.name1, ' ', 8); if (strcmp(w[1], "-") != 0) memcpy(c.name1, w[1], strlen(w[1]) > 8 ? 8 : strlen(w[1]));
        GGCGDCN(&c, value, 8, inc, 8, 0);
        for (int j = 0; j < 8; j++) v = v * 256 + value[j];
        if (c.resp == 0) printf("0/0 %llu\n", v); else printf("%d/%d\n", c.resp, c.resp2);
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_gets_a_doubleword_counter_with_an_increment(tmp_path):
    """#4767 zECS (register X30), IBM EXEC CICS GET DCOUNTER: the value before the increment (an unsigned doubleword, big-endian),
    then the counter is INCREMENT more; INVREQ RESP2 201 for a counter that is not there, 403 / 404 for a name outside IBM's
    characters; an INCREMENT not above zero and a counter that would pass 4294967295 (the maximum the run does not state) are
    refused."""
    exe = _stub(tmp_path, _X30_MAIN)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    cfg = tmp_path / "counters.cfg"
    for steps, answers in _X30_CASES:
        cfg.write_text("- ZC01_ZECS 41\n- BIGCNT 4294967294\n- TOP 4294967295\n", encoding="ascii")
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        assert run.stdout.splitlines() == [a.split("|")[0] for a in answers], steps
        if "|" in answers[-1]:
            name = steps[-1].split()[0]
            assert f"- {name} {answers[-1].split('|')[1]}" in cfg.read_text(encoding="ascii"), steps
    for steps, why in _X30_REFUSED:
        cfg.write_text("- ZC01_ZECS 41\n- BIGCNT 4294967294\n- TOP 4294967295\n", encoding="ascii")
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)


@needs_javac
def test_cics_task_gets_a_doubleword_counter_as_the_stub_does(tmp_path):
    """#4767 zECS (X30): CicsTask.getCounter(pool, name, increment) answers the steps above as the stub does and refuses what the
    stub refuses."""
    parts = []
    for steps, _answers in _X30_CASES:
        body = "".join(
            f'{{ long[] r = t.getCounter("{"" if st.split()[1] == "-" else st.split()[1]}", "{st.split()[0]}", {st.split()[2]}L); '
            f'System.out.println(r[0] == 0 ? "0/0 " + r[2] : r[0] + "/" + r[1]); }}\n'
            for st in steps
        )
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withCounters(new java.util.HashMap<>('
            'java.util.Map.of("/ZC01_ZECS", 41L, "/BIGCNT", 4294967294L, "/TOP", 4294967295L)));\n' + body + "}"
        )
    for steps, _why in _X30_REFUSED:
        st = steps[0].split()
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withCounters(new java.util.HashMap<>('
            'java.util.Map.of("/ZC01_ZECS", 41L, "/BIGCNT", 4294967294L, "/TOP", 4294967295L)));\n'
            f'try {{ t.getCounter("", "{st[0]}", {st[2]}L); System.out.println("not refused"); }} '
            "catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); } }"
        )
    out = _cics_task(tmp_path, "\n".join(parts)).splitlines()
    want = [a.split("|")[0] for _s, answers in _X30_CASES for a in answers]
    assert out[: len(want)] == want
    for got, (_steps, why) in zip(out[len(want) :], _X30_REFUSED):
        assert got == why + ": not modelled", (got, why)


# ---- #4770 zECS (register X45): DEFINE / QUERY / DELETE DCOUNTER, GET DCOUNTER WRAP at the limits ---------------------------------
# a scenario: (the counters stated before, the steps, what both runtimes answer, the refusal the last step ends in). A step:
# "def NAME POOL VALUE MIN MAX" ("-": omitted), "get NAME POOL INC WRAP", "qry NAME POOL LIMITS", "gc NAME POOL" (the
# fullword GET COUNTER), "del NAME POOL". Answer: "resp/resp2", then on NORMAL a get's / gc's / qry's values.
_U64 = "18446744073709551615"
_X45_CASES = [
    # IBM's defaults: MINIMUM zero, MAXIMUM a doubleword of X'FF', VALUE zero; the GET adds INCREMENT after handing out the value
    (
        "",
        ["def A - - - -", "qry A - 1", "get A - 1 0", "get A - 5 0", "qry A - 0"],
        ["0/0", f"0/0 0 0 {_U64}", "0/0 0", "0/0 1", "0/0 6"],
        None,
    ),
    # 202 duplicate; 403 / 404 names; 407 MAXIMUM below MINIMUM; 406 VALUE below MINIMUM or above MAXIMUM + 1 (MAXIMUM + 1 is allowed)
    (
        "",
        [
            "def B - 5 - -",
            "def B - 5 - -",
            "def x - 5 - -",
            "def B p 5 - -",
            "def C - 5 10 3",
            "def C - 2 3 10",
            "def C - 12 3 10",
            "def C - 11 3 10",
            "def C - 3 3 10",
            "qry C - 1",
        ],
        ["0/0", "16/202", "16/404", "16/403", "16/407", "16/406", "16/406", "0/0", "16/202", "0/0 11 3 10"],
        None,
    ),
    # a counter at MAXIMUM + 1: SUPPRESSED RESP2 101 and unchanged without WRAP, the minimum with WRAP (then the increment on)
    (
        "",
        [
            "def D - 8 5 10",
            "get D - 1 0",
            "get D - 1 0",
            "get D - 1 0",
            "get D - 1 0",
            "qry D - 1",
            "get D - 1 1",
            "get D - 1 0",
        ],
        ["0/0", "0/0 8", "0/0 9", "0/0 10", "72/101", "0/0 11 5 10", "0/0 5", "0/0 6"],
        None,
    ),
    (
        "",
        [
            "def E - 10 5 10",
            "get E - 1 0",
            "get E - 3 1",
            "qry E - 1",
            "def J - 10 0 10",
            "gc J -",
            "gc J -",
            "get J - 1 1",
        ],
        ["0/0", "0/0 10", "0/0 5", "0/0 8 5 10", "0/0", "0/0 10", "72/101", "0/0 0"],
        None,
    ),
    # a doubleword is unsigned: a value at X'FF..FF' reads back as one, and nothing is past it
    (
        "",
        ["def G - 18446744073709551614 - -", "get G - 1 0", "qry G - 0", "get G - 1 1"],
        ["0/0", "0/0 18446744073709551614", "0/0 18446744073709551615"],
        "GET COUNTER past a doubleword",
    ),
    (
        "",
        ["def H - 18446744073709551615 - -", "qry H - 0", "get H - 1 0"],
        ["0/0", f"0/0 {_U64}"],
        "GET COUNTER past a doubleword",
    ),
    # DELETE DCOUNTER is DELETE COUNTER's: 201 when none; a redefined counter has its own limits
    (
        "",
        ["def K - 3 2 9", "del K -", "del K -", "qry K - 0", "get K - 1 0", "def K - - - -", "qry K - 1"],
        ["0/0", "0/0", "16/201", "16/201", "16/201", "0/0", f"0/0 0 0 {_U64}"],
        None,
    ),
    # refused by name: an INCREMENT of zero, beyond MAXIMUM - MINIMUM, or carrying the counter past MAXIMUM + 1
    ("", ["def I - 0 0 10", "get I - 0 0"], ["0/0"], "GET COUNTER with an INCREMENT not above zero"),
    ("", ["def I - 0 0 10", "get I - 11 0"], ["0/0"], "GET COUNTER with an INCREMENT beyond the counter's range"),
    ("", ["def I - 5 0 10", "get I - 10 1"], ["0/0"], "GET COUNTER with an INCREMENT past MAXIMUM + 1"),
    # a counter with no limits (DEFINE COUNTER's, or a scenario's) is as before: WRAP changes nothing, its limits are not stated
    (
        "LEG 5",
        ["get LEG - 2 1", "qry LEG - 0", "qry LEG - 1"],
        ["0/0 5", "0/0 7"],
        "QUERY DCOUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state",
    ),
]

_X45_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGDCN(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCDDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCQDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCXCNT(gg_cics *c);
static gg_cics c;
static void be(unsigned char *p, const char *w, int *len) {
    unsigned long long n = strtoull(w, NULL, 10);
    for (int j = 7; j >= 0; j--) { p[j] = (unsigned char)(n & 255); n >>= 8; }
    *len = strcmp(w, "-") == 0 ? 0 : 8;
}
static unsigned long long un(const unsigned char *p) { unsigned long long v = 0; for (int j = 0; j < 8; j++) v = v * 256 + p[j]; return v; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[6] = {0};
        int k = 0, vl, ll, hl;
        unsigned char v[8], lo[8], hi[8];
        for (char *t = strtok(argv[i], " "); t && k < 6; t = strtok(NULL, " ")) w[k++] = t;
        memset(c.qname, ' ', 16); memcpy(c.qname, w[1], strlen(w[1]));
        memset(c.name1, ' ', 8); if (strcmp(w[2], "-") != 0) memcpy(c.name1, w[2], strlen(w[2]) > 8 ? 8 : strlen(w[2]));
        if (strcmp(w[0], "def") == 0) {
            be(v, w[3], &vl); be(lo, w[4], &ll); be(hi, w[5], &hl);
            GGCDDCN(&c, v, vl, lo, ll, hi, hl);
            printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "get") == 0) {
            be(lo, w[3], &ll);
            GGCGDCN(&c, v, 8, lo, 8, atoi(w[4]));
            if (c.resp == 0) printf("0/0 %llu\n", un(v)); else printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "gc") == 0) {
            unsigned char gb[4] = {0}, incb[4] = {0, 0, 0, 1};
            GGCGCNT(&c, gb, 4, incb, 4, 0);
            c.num = ((int)gb[0] << 24) | ((int)gb[1] << 16) | ((int)gb[2] << 8) | gb[3];
            if (c.resp == 0) printf("0/0 %d\n", c.num); else printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "qry") == 0) {
            int lim = atoi(w[3]);
            GGCQDCN(&c, v, 8, lo, lim ? 8 : 0, hi, lim ? 8 : 0);
            if (c.resp != 0) printf("%d/%d\n", c.resp, c.resp2);
            else if (lim) printf("0/0 %llu %llu %llu\n", un(v), un(lo), un(hi));
            else printf("0/0 %llu\n", un(v));
        } else {
            GGCXCNT(&c);
            printf("%d/%d\n", c.resp, c.resp2);
        }
    }
    return 0;
}
"""


def _x45_seed(seed: str) -> str:
    return f"- {seed}\n" if seed else ""


@needs_cc
def test_the_stub_defines_queries_and_wraps_a_doubleword_counter(tmp_path):
    """#4770 zECS (register X45), IBM EXEC CICS DEFINE / QUERY / GET DCOUNTER: the stub's GGCDDCN / GGCQDCN / GGCGDCN."""
    exe = _stub(tmp_path, _X45_MAIN)
    for n, (seed, steps, answers, refusal) in enumerate(_X45_CASES):
        work = tmp_path / f"c{n}"
        work.mkdir()
        (work / "out").mkdir()
        (work / "counters.cfg").write_text(_x45_seed(seed), encoding="ascii")
        env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        got = run.stdout.splitlines()
        if refusal is None:
            assert run.returncode == 0 and got == answers, (steps, got)
        else:
            assert run.returncode == 98 and got[: len(answers)] == answers and refusal in run.stdout, (
                steps,
                run.stdout,
            )


@needs_javac
def test_cics_task_defines_queries_and_wraps_a_doubleword_counter_as_the_stub_does(tmp_path):
    """#4770 zECS (X45): CicsTask.defineDcounter / queryDcounter / getCounter(.., wrap) answer the scenarios above as the stub does
    and refuse what it refuses."""

    def u(x: str, dflt: str) -> str:
        return dflt if x == "-" else f'Long.parseUnsignedLong("{x}")'

    parts = []
    for seed, steps, _answers, _refusal in _X45_CASES:
        counters = 'java.util.Map.of("/LEG", 5L)' if seed else "java.util.Map.of()"
        body = ""
        for st in steps:
            w = st.split()
            pool = '""' if w[2] == "-" else f'"{w[2]}"'
            nm = f'"{w[1]}"'
            if w[0] == "def":
                body += (f"r = t.defineDcounter({pool}, {nm}, {u(w[3], '0L')}, {u(w[4], '0L')}, {u(w[5], '-1L')}); "
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            elif w[0] in ("get", "gc"):
                call = (
                    f"t.getCounter({pool}, {nm}, {u(w[3], '1L')}, {'true' if w[4] == '1' else 'false'})"
                    if w[0] == "get"
                    else f"t.getCounter({pool}, {nm})"
                )
                body += f'g = {call}; System.out.println(g[0] == 0 ? "0/0 " + Long.toUnsignedString(g[2]) : g[0] + "/" + g[1]);\n'
            elif w[0] == "qry":
                lim = "true" if w[3] == "1" else "false"
                tail = (
                    ' + " " + Long.toUnsignedString(g[3]) + " " + Long.toUnsignedString(g[4])' if lim == "true" else ""
                )
                body += (f"g = t.queryDcounter({pool}, {nm}, {lim}); "
                         f'System.out.println(g[0] == 0 ? "0/0 " + Long.toUnsignedString(g[2]){tail} : g[0] + "/" + g[1]);\n')  # fmt: skip
            else:
                body += f't_ = t.deleteCounter({pool}, {nm}); System.out.println(t_[0] + "/" + t_[1]);\n'
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withCounters(new java.util.HashMap<>('
            + counters
            + "));\n"
            "int[] r, t_; long[] g;\n"
            f'try {{\n{body}}} catch (UnsupportedOperationException e) {{ System.out.println("refused " + e.getMessage()); }} }}\n'
        )
    out = _cics_task(tmp_path, "\n".join(parts)).splitlines()
    pos = 0
    for _seed, _steps, answers, refusal in _X45_CASES:
        assert out[pos : pos + len(answers)] == answers, (_steps, out[pos : pos + len(answers)])
        pos += len(answers)
        if refusal is not None:
            assert out[pos] == f"refused {refusal}: not modelled", (refusal, out[pos])
            pos += 1


# ---- #4767 zECS (register X37): WEB SEND DOCTOKEN ------------------------------------------------------------------------------
# a step a line: DOC MEDIATYPE|- ACTION STATUSCODE|- STATUSTEXT|- STATUSLEN|- CONV; DOC "empty" (DOCUMENT CREATE), "text" (a
# document of "ab"), "none" (a token that names no document). What both runtimes answer and the WEB-SEND body they record.
_X37_DOC_CASES = [  # (steps, answers, bodies of the events)
    (["empty text/plain 2 204 No_Content 10 1"], ["send 0/0"], [""]),
    (["empty - 2 - - - 0"], ["send 0/0"], [""]),
    (["text text/plain 2 200 OK 2 1"], ["send 0/0"], ["ab"]),
    (["text - 2 204 - - 0"], ["send 16/72"], []),
    (["text - 7 - - - 0"], ["send 16/11"], []),
    # #4941 (X37): a token that names no document (not created, or deleted) is NOTFND RESP2 1; EVENTUAL sends at the task's end
    (["none - 2 - - - 0"], ["send 13/1"], []),
    (["empty - 3 - - - 0"], ["send 0/0"], [""]),
    (["text - 0 - - - 0"], ["send 0/0"], ["ab"]),
]
_X37_DOC_REFUSED = [
    (["none - 7 - - - 0"], "WEB SEND with more than one condition at once"),
    (["empty - 2 - OK 0 0"], "FROMLENGTH or STATUSLEN not above zero"),
    (["empty - 2 99 - - 0"], "STATUSCODE outside 100-599"),
    (["empty application/json 2 - - - 1"], "SRVCONVERT on a media type that is not text/*"),
    (["empty - 2 - OK 21 0"], "length beyond its area"),
    (["empty - 2 - - - 0", "empty - 2 - - - 0"], "WEB SEND after a response was sent"),
]

_X37_DOC_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCDOCC(gg_cics *c, char *src, int srclen, char *tok, int toklen);
int GGCWSDC(gg_cics *c, char *tok, int toklen, char *media, int mediacap, char *stext, int stextcap);
int GGCEND(gg_cics *c);
static gg_cics c;
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[7], tok[16], media[56], stext[20], flags[40] = "";
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 7; t = strtok(NULL, " ")) w[k++] = t;
        memset(tok, ' ', 16); memset(media, ' ', 56); memset(stext, ' ', 20);
        if (strcmp(w[0], "none") != 0) {
            memset(c.flags, ' ', 40); memcpy(c.flags, strcmp(w[0], "empty") == 0 ? "EMPTY" : "DATA", strcmp(w[0], "empty") == 0 ? 5 : 4);
            c.len = 2;
            GGCDOCC(&c, "ab", 2, tok, 16);
        } else memcpy(tok, "GGDOC99999999999", 16);
        if (strcmp(w[1], "-") != 0) { strcat(flags, "MEDIA "); memcpy(media, w[1], strlen(w[1])); }
        c.item = atoi(w[2]);
        c.num = strcmp(w[3], "-") == 0 ? -1 : atoi(w[3]);
        if (strcmp(w[4], "-") != 0) { strcat(flags, "STEXT"); memcpy(stext, w[4], strlen(w[4])); }
        c.hours = strcmp(w[5], "-") == 0 ? -1 : atoi(w[5]);
        c.mins = atoi(w[6]);
        memset(c.flags, ' ', 40); memcpy(c.flags, flags, strlen(flags));
        GGCWSDC(&c, tok, 16, media, 56, stext, 20);
        printf("send %d/%d\n", c.resp, c.resp2);
    }
    GGCEND(&c);
    return 0;
}
"""


@needs_cc
def test_the_stub_sends_a_document(tmp_path):
    """#4767 zECS (register X37), IBM WEB SEND DOCTOKEN (server): the document the task created is the response body, recorded as
    WEB-SEND; an empty document is no body (a 204 may send it: ASSUMED); the rest as FROM; a token naming no document is refused."""
    exe = _stub(tmp_path, _X37_DOC_MAIN)
    req = tmp_path / "webreq.cfg"
    req.write_text("R HTTP 7A656373 80 PUT 2F6B -\n", encoding="ascii")
    for n, (steps, answers, bodies) in enumerate(_X37_DOC_CASES):
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        assert run.stdout.splitlines() == answers, steps
        got = _x37_stub_events(out)
        assert [g[3] for g in got if g[0] in (200, 204)] == bodies, steps
    for n, (steps, why) in enumerate(_X37_DOC_REFUSED):
        out = tmp_path / f"refused{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)


@needs_javac
def test_cics_task_sends_a_document_as_the_stub_does(tmp_path):
    """#4767 zECS (X37): CicsTask.webSendDocument answers the steps above as the stub does and refuses what it refuses."""

    def java(steps: list[str]) -> str:
        lines = []
        for st in steps:
            w = st.split(" ")

            def area(v: str, width: int) -> str:
                return "null" if v == "-" else '"' + v.ljust(width) + '"'

            doc = {"empty": "t.documentCreateEmpty().doctoken()", "text": 't.documentCreateData("ab".getBytes(), 2).doctoken()',
                   "none": '"GGDOC99999999999"'}[w[0]]  # fmt: skip
            lines.append(
                f"send(t, {doc}, {area(w[1], 56)}, {w[2]}, {-1 if w[3] == '-' else w[3]}, {area(w[4], 20)}, "
                f"{-1 if w[5] == '-' else w[5]}, {w[6]});"
            )
        return "\n".join(lines)

    helpers = """
    static void send(CicsTask t, String tok, String media, int action, int status, String stext, int sl, int conv) {
        int[] r = t.webSendDocument(tok, media, action, status, stext, sl, conv, 0, java.nio.charset.StandardCharsets.ISO_8859_1);
        System.out.println("send " + r[0] + "/" + r[1]);
    }
    static CicsTask task() {
        return new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "zecs", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), null, null));
    }
    static void events(CicsTask t) {
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("WEB-SEND")) System.out.println("ev " + e.get("body"));
        }
    }
"""
    parts = [
        "{ CicsTask t = task();\n" + java(steps) + '\nevents(t); System.out.println("--"); }'
        for steps, _a, _b in _X37_DOC_CASES
    ]
    for steps, _why in _X37_DOC_REFUSED:
        parts.append(
            "{ CicsTask t = task(); try {\n" + java(steps) + '\nSystem.out.println("not refused"); }'
            " catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); } }"
        )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers, bodies in _X37_DOC_CASES:
        end = lines.index("--", pos)
        assert lines[pos:end] == answers + [f"ev {b}" for b in bodies], (steps, lines[pos:end])
        pos = end + 1
    refusals = [ln for ln in lines[pos:] if not ln.startswith("send ")]
    assert len(refusals) == len(_X37_DOC_REFUSED)
    for got, (_steps, why) in zip(refusals, _X37_DOC_REFUSED):
        assert why in got and got.endswith(": not modelled"), (got, why)


# ---- #4941 (registers X37, X41): WEB SEND ACTION(EVENTUAL) / DOCSTATUS and the WEB RETRIEVE that follows -------------------
# a step a line: mk (DOCUMENT CREATE of "ab", token slot n in order), sd SLOT ACTION DOCSTATUS (WEB SEND DOCTOKEN; ACTION 0 not
# given, 2 IMMEDIATE, 3 EVENTUAL; DOCSTATUS 0 not given, 295 DOCDELETE, 296 NODOCDELETE), sf ACTION (WEB SEND FROM "x"), rtv
# (WEB RETRIEVE, then DOCUMENT RETRIEVE of the token it gave), rd SLOT (DOCUMENT RETRIEVE), abend. Then the task ends.
_X41_CASES = [  # (steps, what both runtimes answer, the events they record: RETURN, then the WEB-SEND sent at the task's end)
    (["mk", "sd 0 3 0", "rtv"], ["sd 0/0", "rtv 0/0 GGDOC00000000002 ab"], ["RETURN", "WEB-SEND EVENTUAL 200 ab"]),
    (["mk", "sd 0 0 0", "rtv"], ["sd 0/0", "rtv 0/0 GGDOC00000000002 ab"], ["RETURN", "WEB-SEND EVENTUAL 200 ab"]),
    (
        ["mk", "sd 0 3 296", "rtv", "rd 0"],
        ["sd 0/0", "rtv 0/0 GGDOC00000000002 ab", "rd 0/0 ab"],
        ["RETURN", "WEB-SEND EVENTUAL 200 ab"],
    ),
    (["mk", "sd 0 3 295", "rtv", "rd 0"], ["sd 0/0", "rtv 13/1", "rd 13/1"], ["RETURN", "WEB-SEND EVENTUAL 200 ab"]),
    (["mk", "sd 0 2 295", "rd 0"], ["sd 0/0", "rd 13/1"], ["WEB-SEND IMMEDIATE 200 ab", "RETURN"]),
    (["mk", "sd 0 2 0", "rtv"], ["sd 0/0", "rtv 13/1"], ["WEB-SEND IMMEDIATE 200 ab", "RETURN"]),
    (
        ["mk", "sd 0 3 0", "rtv", "rtv"],
        ["sd 0/0", "rtv 0/0 GGDOC00000000002 ab", "rtv 0/0 GGDOC00000000002 ab"],
        ["RETURN", "WEB-SEND EVENTUAL 200 ab"],
    ),
    (["rtv"], ["rtv 16/2"], ["RETURN"]),
    (["sf 3", "rtv"], ["sf 0/0", "rtv 13/1"], ["RETURN", "WEB-SEND EVENTUAL 200 x"]),
    (["mk", "sd 0 3 0", "sf 3", "rtv"], ["sd 0/0", "sf 0/0", "rtv 13/1"], ["RETURN", "WEB-SEND EVENTUAL 200 x"]),
    (
        ["mk", "mk", "sd 0 3 0", "sd 1 3 0", "rtv"],
        ["sd 0/0", "sd 0/0", "rtv 0/0 GGDOC00000000003 ab"],
        ["RETURN", "WEB-SEND EVENTUAL 200 ab"],
    ),
    (["mk", "sd 0 3 0", "sd 0 3 295", "rtv"], ["sd 0/0", "sd 0/0", "rtv 13/1"], ["RETURN", "WEB-SEND EVENTUAL 200 ab"]),
    (["mk", "sd 0 3 295", "sd 0 3 0"], ["sd 0/0", "sd 13/1"], ["RETURN", "WEB-SEND EVENTUAL 200 ab"]),
    (["mk", "sd 0 3 7"], ["sd 16/143"], ["RETURN"]),
    (["mk", "sd 0 3 7", "rtv"], ["sd 16/143", "WEB RETRIEVE after a WEB SEND that ended in a condition"], []),
    (
        ["mk", "sd 0 3 0", "abend"],
        ["sd 0/0", "WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend"],
        [],
    ),
    (["mk", "sd 0 3 0", "sd 0 2 0"], ["sd 0/0", "WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send"], []),
]

_X41_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCDOCC(gg_cics *c, char *src, int srclen, char *tok, int toklen);
int GGCDOCR(gg_cics *c, char *tok, int toklen, char *into, int intolen);
int GGCWSDC(gg_cics *c, char *tok, int toklen, char *media, int mediacap, char *stext, int stextcap);
int GGCWSND(gg_cics *c, char *from, int fromcap, char *media, int mediacap, char *stext, int stextcap);
int GGCWRTV(gg_cics *c, char *tok, int toklen);
int GGCABND(gg_cics *c);
int GGCEND(gg_cics *c);
static gg_cics c;
int main(int argc, char **argv) {
    char toks[8][16];
    int nt = 0;
    for (int i = 1; i < argc; i++) {
        char *w[4] = {"", "", "", ""}, media[56], stext[20], from[64], tok[16], into[16];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 4; t = strtok(NULL, " ")) w[k++] = t;
        memset(media, ' ', 56); memset(stext, ' ', 20); memset(from, ' ', 64); memset(tok, ' ', 16); memset(into, ' ', 16);
        memset(c.flags, ' ', 40);
        c.num = -1; c.hours = -1; c.mins = 0; c.secs = 0;
        if (strcmp(w[0], "mk") == 0) {
            memcpy(c.flags, "DATA", 4);
            c.len = 2;
            GGCDOCC(&c, "ab", 2, toks[nt++], 16);
        } else if (strcmp(w[0], "sd") == 0) {
            c.item = atoi(w[2]);
            c.secs = atoi(w[3]);
            GGCWSDC(&c, toks[atoi(w[1])], 16, media, 56, stext, 20);
            printf("sd %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "sf") == 0) {
            c.item = atoi(w[1]);
            c.len = 1;
            from[0] = 'x';
            GGCWSND(&c, from, 64, media, 56, stext, 20);
            printf("sf %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "rtv") == 0) {
            GGCWRTV(&c, tok, 16);
            printf("rtv %d/%d", c.resp, c.resp2);
            if (c.resp == 0) {
                c.len = 16;
                GGCDOCR(&c, tok, 16, into, 16);
                printf(" %.16s %.*s", tok, c.len, into);
            }
            printf("\n");
        } else if (strcmp(w[0], "rd") == 0) {
            c.len = 16;
            GGCDOCR(&c, toks[atoi(w[1])], 16, into, 16);
            printf("rd %d/%d", c.resp, c.resp2);
            if (c.resp == 0) printf(" %.*s", c.len, into);
            printf("\n");
        } else {
            memcpy(c.name1, "ABCD    ", 8);
            GGCABND(&c);
        }
    }
    GGCEND(&c);
    return 0;
}
"""


def _x41_stub_events(out: Path) -> list[str]:
    got = []
    path = out / "events.txt"
    for line in path.read_text(encoding="latin-1").splitlines() if path.exists() else []:
        seq, verb, *rest = line.split()
        if verb == "WEB-SEND":
            kv = dict(a.split("=", 1) for a in rest[1:])
            body = (out / f"{seq}.bin").read_bytes().decode("latin-1") if (out / f"{seq}.bin").exists() else ""
            got.append(f"WEB-SEND {kv['action']} {kv['status']} {body}")
        else:
            got.append(verb)
    return got


@needs_cc
def test_the_stub_defers_a_web_send_and_retrieves_its_document(tmp_path):
    """#4941 (registers X37, X41), IBM WEB SEND ACTION(EVENTUAL) / DOCSTATUS and WEB RETRIEVE: an EVENTUAL (or omitted) action holds
    the response until the task ends and a second send replaces it; a WEB RETRIEVE after an EVENTUAL document send that did not
    DOCDELETE writes the DOCTOKEN of a copy of the document, else NOTFND 1 (INVREQ 2 before any send); DOCDELETE deletes the
    document (a later request for it is NOTFND 1); what IBM leaves open is refused."""
    exe = _stub(tmp_path, _X41_MAIN)
    req = tmp_path / "webreq.cfg"
    req.write_text("R HTTP 7A656373 80 PUT 2F6B -\n", encoding="ascii")
    for n, (steps, answers, events) in enumerate(_X41_CASES):
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if events:
            assert run.returncode == 0 and run.stdout.splitlines() == answers, (steps, run.stdout)
            assert _x41_stub_events(out) == events, (steps, _x41_stub_events(out))
        else:
            assert run.returncode == 98 and answers[-1] in run.stdout, (steps, run.stdout)
            assert run.stdout.splitlines()[:-1] == answers[:-1] or answers[-1] in run.stdout, (steps, run.stdout)


@needs_javac
def test_cics_task_defers_a_web_send_as_the_stub_does(tmp_path):
    """#4941 (X37, X41): CicsTask answers the steps above as the stub does, records the same events in the same order (the
    deferred WEB-SEND after the task's RETURN), and refuses what the stub refuses."""
    helpers = """
    static String pad(String s, int n) { return (s + " ".repeat(n)).substring(0, n); }
    static void run(String... steps) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "zecs", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), null, null));
        String[] toks = new String[8];
        int nt = 0;
        boolean abended = false;
        for (String s : steps) {
            String[] w = s.split(" ");
            switch (w[0]) {
                case "mk" -> toks[nt++] = t.documentCreateData("ab".getBytes(), 2).doctoken();
                case "sd" -> {
                    int[] r = t.webSendDocument(toks[Integer.parseInt(w[1])], null, Integer.parseInt(w[2]), -1, null, -1, 0,
                            Integer.parseInt(w[3]), java.nio.charset.StandardCharsets.ISO_8859_1);
                    System.out.println("sd " + r[0] + "/" + r[1]);
                }
                case "sf" -> {
                    int[] r = t.webSend(pad("x", 64), 1, null, Integer.parseInt(w[1]), -1, null, -1, 0);
                    System.out.println("sf " + r[0] + "/" + r[1]);
                }
                case "rtv" -> {
                    var r = t.webRetrieve();
                    String more = "";
                    if (r.resp() == 0) {
                        more = " " + r.doctoken() + " " + new String(t.documentRetrieve(r.doctoken(), 16).data());
                    }
                    System.out.println("rtv " + r.resp() + "/" + r.resp2() + more);
                }
                case "rd" -> {
                    var r = t.documentRetrieve(toks[Integer.parseInt(w[1])], 16);
                    System.out.println("rd " + r.resp() + "/" + r.resp2() + (r.resp() == 0 ? " " + new String(r.data()) : ""));
                }
                default -> {
                    t.abend("ABCD");
                    abended = true;
                }
            }
        }
        if (!abended) {
            t.returnTransid(null, null);
        }
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("WEB-SEND")) {
                System.out.println("ev WEB-SEND " + e.get("action") + " " + e.get("status") + " " + e.get("body"));
            } else if (e.get("event").equals("RETURN")) {
                System.out.println("ev RETURN");
            }
        }
        System.out.println("--");
    }
"""
    parts = []
    for steps, _answers, _events in _X41_CASES:
        args = ", ".join('"' + st + '"' for st in steps)
        parts.append(
            "try { run(" + args + "); } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); "
            'System.out.println("--"); }'
        )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers, events in _X41_CASES:
        end = lines.index("--", pos)
        got = lines[pos:end]
        if events:
            assert got == answers + [f"ev {e}" for e in events], (steps, got)
        else:
            assert got[:-1] == answers[:-1] and answers[-1] in got[-1], (steps, got)
        pos = end + 1


# ---- #4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms ----------------------------------------
# One step table, run alike by the stub (C) and CicsTask (Java): rdf / rdq NAME NAMELENGTH VALUELENGTH (areas: name 32, value
# 24), sbr KIND [NAME NAMELENGTH], rnx KIND NAMELENGTH VALUELENGTH (areas: name 16, value 30), ebr KIND; KIND h / f / q
# (HTTPHEADER / FORMFIELD / QUERYPARM). Areas start as dots, so "the rest of the area is left alone" shows.
_URL = "application/x-www-form-urlencoded"
_FORM_Q = "a=1&B=two%20words&c=&e=x%3Dy"
_FORM_B = "user=joe&Pass=p%40ss%21&empty=&long=abcdefghijklmnopqrstuvwxy"
_H2 = [("Host", "h"), ("X-Long", "abcdefghijklmnopqrstuvwxyz0123456789")]
_LONGV = "0123456789" * 3 + "0123"
_X4940_REQ = {
    "form": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", _FORM_Q, _H2, _URL, _FORM_B),
    "hdrs": ("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "", [("A", "1"), ("B", "2")], None, None),
    "dup": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", "a=1&A=2", [], _URL, "k=1&k=2"),
    "emptybody": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", "", [], _URL, ""),
    "multipart": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", "", [], "multipart/form-data", "a=1"),
    "textplain": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", "", [], "text/plain", "a=1"),
    "eqval": ("HTTP", "h", 80, "GET", "HTTP/1.1", "/", "k=a=b", [], None, None),
    "longname": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", "averyverylongfieldname=v&z=1", [], _URL,
                 "averyverylongfieldname=v&z=1"),
    "bothlong": ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", f"averyverylongfieldname={_LONGV}", [], _URL,
                 f"averyverylongfieldname={_LONGV}"),
}  # fmt: skip
_X4940_BAD = {  # data IBM leaves open: the same string as a query string and as a form body
    "plus": "a=b+c", "semi": "a=1;b=2", "noeq": "abc", "badesc": "a=%zz", "shortesc": "a=%4", "ctl": "a=%00",
    "hi": "a=%FF", "escname": "%41=1", "emptypair": "a=1&&b=2", "emptyname": "=v", "trailamp": "a=1&",
}  # fmt: skip
for _n, _d in _X4940_BAD.items():
    _X4940_REQ[_n] = ("HTTP", "h", 80, "POST", "HTTP/1.1", "/", _d, [], _URL, _d)
_X38_REQ.update(_X4940_REQ)


def _d(s: str, n: int) -> str:
    return s + "." * (n - len(s))


def _rd(step: str, resp: str, value: str | None = None, n: int | None = None) -> str:
    return f"{step} {resp}" + ("" if value is None else f" {_d(value, 24)}|{n}")


def _rn(resp: str, name: str | None = None, value: str = "", nl: int = 0, vl: int = 0) -> str:
    return f"rnx {resp}" + ("" if name is None else f" {_d(name, 16)}|{_d(value, 30)}|{nl}|{vl}")


_LONGFIELD = "abcdefghijklmnopqrstuvwxy"
_FORM_ROWS = [("user", "joe"), ("Pass", "p@ss!"), ("empty", ""), ("long", _LONGFIELD)]
_QUERY_ROWS = [("a", "1"), ("B", "two words"), ("c", ""), ("e", "x=y")]
_MORE = "with more than one condition at once"
_X4940_CASES: list[tuple[str, list[str], list[str]]] = [
    # -- WEB READ FORMFIELD / QUERYPARM: the name without case, the value unescaped, cut with the real length
    ("form", ["rdf user 4 24"], [_rd("rdf", "0/0", "joe", 3)]),
    ("form", ["rdf USER 4 24"], [_rd("rdf", "0/0", "joe", 3)]),
    ("form", ["rdf Pass 4 24"], [_rd("rdf", "0/0", "p@ss!", 5)]),
    ("form", ["rdf empty 5 24"], [_rd("rdf", "0/0", "", 0)]),
    ("form", ["rdf long 4 24"], [f"rdf 22/5 {_LONGFIELD[:24]}|25"]),
    ("form", ["rdf long 4 10"], [_rd("rdf", "22/5", _LONGFIELD[:10], 25)]),
    ("form", ["rdf long 4 25"], ["WEB READ FORMFIELD length beyond its area"]),
    ("form", ["rdf nobody 6 24"], ["rdf 13/1"]),
    ("form", ["rdf user 0 24"], ["rdf 22/1"]),
    ("form", ["rdf user 4 0"], ["rdf 22/1"]),
    ("form", ["rdf user 4 -1"], ["rdf 22/1"]),
    ("form", ["rdf user -2 24"], ["rdf 22/1"]),
    ("form", ["rdf user 33 24"], ["WEB READ FORMFIELD length beyond its area"]),
    ("form", ["rdf nobody 6 0"], [f"WEB READ FORMFIELD {_MORE}"]),
    ("form", ["rdq a 1 24"], [_rd("rdq", "0/0", "1", 1)]),
    ("form", ["rdq b 1 24"], [_rd("rdq", "0/0", "two words", 9)]),
    ("form", ["rdq B 1 24", "rdq e 1 24", "rdq c 1 24"],
     [_rd("rdq", "0/0", "two words", 9), _rd("rdq", "0/0", "x=y", 3), _rd("rdq", "0/0", "", 0)]),
    ("form", ["rdq e 1 2"], [_rd("rdq", "22/5", "x=", 3)]),
    ("form", ["rdq user 4 24"], ["rdq 13/1"]),
    ("form", ["rdq a 1 25"], ["WEB READ QUERYPARM length beyond its area"]),
    ("form", ["rdq a 33 24"], ["WEB READ QUERYPARM length beyond its area"]),
    ("form", ["rdq a 0 24"], ["rdq 22/1"]),
    ("form", ["rdq zz 2 0"], [f"WEB READ QUERYPARM {_MORE}"]),
    ("eqval", ["rdq k 1 24"], [_rd("rdq", "0/0", "a=b", 3)]),
    ("bare", ["rdf a 1 24"], ["rdf 16/13"]),
    ("bare", ["rdq a 1 24"], ["rdq 16/13"]),
    ("bare", ["rdf a 0 24"], [f"WEB READ FORMFIELD {_MORE}"]),
    ("bare", ["rdq a 1 0"], [f"WEB READ QUERYPARM {_MORE}"]),
    ("emptybody", ["rdf a 1 24"], ["rdf 16/13"]),
    ("dup", ["rdq a 1 24"], ["WEB READ QUERYPARM two pairs of the name"]),
    ("dup", ["rdq A 1 24"], ["WEB READ QUERYPARM two pairs of the name"]),
    ("dup", ["rdf k 1 24"], ["WEB READ FORMFIELD two pairs of the name"]),
    ("dup", ["rdq zz 2 24"], ["rdq 13/1"]),
    ("multipart", ["rdf a 1 24"], ["WEB FORMFIELD body not application/x-www-form-urlencoded"]),
    ("textplain", ["rdf a 1 24"], ["WEB FORMFIELD body not application/x-www-form-urlencoded"]),
    ("multipart", ["sbr f"], ["WEB FORMFIELD body not application/x-www-form-urlencoded"]),
    ("multipart", ["rdq a 1 24"], ["rdq 16/13"]),
    # -- the data IBM leaves open, refused on every form
    *[
        (n, [step], [f"WEB {kind} data outside the modelled name=value form"])
        for n in _X4940_BAD
        for step, kind in (("rdq a 1 24", "QUERYPARM"), ("rdf a 1 24", "FORMFIELD"), ("sbr q", "QUERYPARM"),
                           ("sbr f", "FORMFIELD"))  # fmt: skip
    ],
    # -- WEB STARTBROWSE / READNEXT / ENDBROWSE FORMFIELD
    ("form", ["sbr f", "rnx f 16 30", "rnx f 16 30", "rnx f 16 30", "rnx f 16 12", "rnx f 16 12", "rnx f 16 30",
              "rnx f 16 30", "rnx f 16 30"],
     ["sbr 0/0", _rn("0/0", "user", "joe", 4, 3), _rn("0/0", "Pass", "p@ss!", 4, 5), _rn("0/0", "empty", "", 5, 0),
      _rn("22/5", "long", _LONGFIELD[:12], 4, 25), _rn("22/5", "long", _LONGFIELD[:12], 4, 25),
      _rn("0/0", "long", _LONGFIELD, 4, 25), "rnx 20/0", "WEB READNEXT FORMFIELD after ENDFILE"]),
    ("form", ["sbr f", "sbr f"], ["sbr 0/0", "sbr 21/5"]),
    ("form", ["rnx f 16 30", "ebr f"], ["rnx 16/4", "ebr 16/4"]),
    ("form", ["sbr f", "ebr f", "ebr f"], ["sbr 0/0", "ebr 0/0", "ebr 16/4"]),
    ("form", ["sbr f", "rnx f 16 30", "ebr f", "sbr f", "rnx f 16 30"],
     ["sbr 0/0", _rn("0/0", "user", "joe", 4, 3), "ebr 0/0", "sbr 0/0", _rn("0/0", "user", "joe", 4, 3)]),
    ("form", ["sbr f Pass 4", "rnx f 16 30", "rnx f 16 30"],
     ["sbr 0/0", _rn("0/0", "Pass", "p@ss!", 4, 5), _rn("0/0", "empty", "", 5, 0)]),
    ("form", ["sbr f nobody 6", "ebr f", "rnx f 16 30"], ["sbr 13/1", "ebr 16/4", "rnx 16/4"]),
    ("form", ["sbr f user 0"], ["sbr 22/1"]),
    ("form", ["sbr f user -1"], ["sbr 22/1"]),
    ("form", ["sbr f user 33"], ["WEB STARTBROWSE FORMFIELD length beyond its area"]),
    ("form", ["sbr f PASS 4"], ["WEB STARTBROWSE FORMFIELD name found only without case"]),
    ("form", ["sbr f", "sbr f nobody 6"], ["sbr 0/0", f"WEB STARTBROWSE FORMFIELD {_MORE}"]),
    ("form", ["sbr f", "rnx f 0 30", "rnx f 16 0", "rnx f -1 30", "rnx f 16 30"],
     ["sbr 0/0", "rnx 22/1", "rnx 22/1", "rnx 22/1", _rn("0/0", "user", "joe", 4, 3)]),
    ("form", ["sbr f", "rnx f 17 30"], ["sbr 0/0", "WEB READNEXT FORMFIELD length beyond its area"]),
    ("form", ["sbr f", "rnx f 16 31"], ["sbr 0/0", "WEB READNEXT FORMFIELD length beyond its area"]),
    ("longname", ["sbr f", "rnx f 16 30", "rnx f 16 30"],
     ["sbr 0/0", _rn("22/4", "averyverylongfie", "v", 22, 1), _rn("22/4", "averyverylongfie", "v", 22, 1)]),
    ("bothlong", ["sbr f", "rnx f 16 30"], ["sbr 0/0", "WEB READNEXT FORMFIELD name and value both truncated"]),
    ("bare", ["sbr f"], ["sbr 16/13"]),
    ("emptybody", ["sbr f"], ["sbr 16/13"]),
    ("bare", ["sbr f x 0"], [f"WEB STARTBROWSE FORMFIELD {_MORE}"]),
    ("dup", ["sbr f", "rnx f 16 30", "rnx f 16 30", "rnx f 16 30"],
     ["sbr 0/0", _rn("0/0", "k", "1", 1, 1), _rn("0/0", "k", "2", 1, 1), "rnx 20/0"]),
    ("dup", ["sbr f k 1"], ["WEB STARTBROWSE FORMFIELD two pairs of the name"]),
    # -- QUERYPARM
    ("form", ["sbr q", *["rnx q 16 30"] * 5],
     ["sbr 0/0", *[_rn("0/0", n, v, len(n), len(v)) for n, v in _QUERY_ROWS], "rnx 20/0"]),
    ("form", ["sbr q e 1", "rnx q 16 30", "rnx q 16 30"], ["sbr 0/0", _rn("0/0", "e", "x=y", 1, 3), "rnx 20/0"]),
    ("form", ["sbr q E 1"], ["WEB STARTBROWSE QUERYPARM name found only without case"]),
    ("form", ["sbr q", "sbr q"], ["sbr 0/0", "sbr 21/5"]),
    ("form", ["rnx q 16 30", "ebr q"], ["rnx 16/4", "ebr 16/4"]),
    ("form", ["sbr q", "ebr q", "ebr q"], ["sbr 0/0", "ebr 0/0", "ebr 16/4"]),
    ("form", ["sbr q user 4"], ["sbr 13/1"]),
    ("bare", ["sbr q"], ["sbr 16/13"]),
    ("longname", ["sbr q", "rnx q 16 30"], ["sbr 0/0", _rn("22/4", "averyverylongfie", "v", 22, 1)]),
    ("bothlong", ["sbr q", "rnx q 16 30"], ["sbr 0/0", "WEB READNEXT QUERYPARM name and value both truncated"]),
    ("dup", ["sbr q", "rnx q 16 30", "rnx q 16 30", "rnx q 16 30"],
     ["sbr 0/0", _rn("0/0", "a", "1", 1, 1), _rn("0/0", "A", "2", 1, 1), "rnx 20/0"]),
    ("dup", ["sbr q a 1"], ["WEB STARTBROWSE QUERYPARM two pairs of the name"]),
    # -- HTTPHEADER
    ("hdrs", ["sbr h", "rnx h 16 30", "rnx h 16 30", "rnx h 16 30", "ebr h"],
     ["sbr 0/0", _rn("0/0", "A", "1", 1, 1), _rn("0/0", "B", "2", 1, 1), "rnx 20/0", "ebr 0/0"]),
    ("hdrs", ["sbr h", "sbr h"], ["sbr 0/0", "sbr 21/10"]),
    ("hdrs", ["rnx h 16 30", "ebr h"], ["rnx 16/4", "ebr 16/4"]),
    ("hdrs", ["sbr h", "rnx h 16 0"], ["sbr 0/0", "rnx 22/1"]),
    ("hdrs", ["sbr h", "rnx h 16 30", "rnx h 16 30", "rnx h 0 30"],
     ["sbr 0/0", _rn("0/0", "A", "1", 1, 1), _rn("0/0", "B", "2", 1, 1), f"WEB READNEXT HTTPHEADER {_MORE}"]),
    ("form", ["sbr h", "rnx h 16 30", "rnx h 16 30"],
     ["sbr 0/0", _rn("0/0", "Host", "h", 4, 1), "WEB READNEXT HTTPHEADER truncated"]),
    ("bare", ["sbr h"], ["sbr 16/43"]),
    # -- the three browses are independent of each other and of a read
    ("form", ["sbr f", "sbr q", "sbr h", "rnx q 16 30", "rnx f 16 30", "rnx h 16 30", "ebr q", "rnx q 16 30",
              "rnx f 16 30", "rdq a 1 24"],
     ["sbr 0/0", "sbr 0/0", "sbr 0/0", _rn("0/0", "a", "1", 1, 1), _rn("0/0", "user", "joe", 4, 3),
      _rn("0/0", "Host", "h", 4, 1), "ebr 0/0", "rnx 16/4", _rn("0/0", "Pass", "p@ss!", 4, 5),
      _rd("rdq", "0/0", "1", 1)]),
]  # fmt: skip
_X4940_HEADS = ("rdf", "rdq", "sbr", "rnx", "ebr")

_X4940_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWRDP(gg_cics *c, char *name, int namecap, char *value, int valuecap);
int GGCWSBR(gg_cics *c, char *name, int namecap);
int GGCWRNX(gg_cics *c, char *name, int namecap, char *value, int valuecap);
int GGCWEBR(gg_cics *c);
static gg_cics c;
static int kind(const char *s) { return s[0] == 'h' ? 0 : s[0] == 'f' ? 1 : 2; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[6], name[40], value[40];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 6; t = strtok(NULL, " ")) w[k++] = t;
        memset(name, '.', 40); memset(value, '.', 40);
        if (strcmp(w[0], "rdf") == 0 || strcmp(w[0], "rdq") == 0) {
            memset(name, ' ', 32); memcpy(name, w[1], strlen(w[1]));
            c.item = w[0][2] == 'f' ? 1 : 2; c.len = atoi(w[2]); c.num = atoi(w[3]);
            GGCWRDP(&c, name, 32, value, 24);
            printf("%s %d/%d", w[0], c.resp, c.resp2);
            if (c.resp == 0 || c.resp2 == 5) printf(" %.24s|%d", value, c.num);
            printf("\n");
        } else if (strcmp(w[0], "sbr") == 0) {
            memset(name, ' ', 32);
            c.item = kind(w[1]);
            if (k > 2) { memcpy(name, w[2], strlen(w[2])); c.len = atoi(w[3]); memset(c.flags, ' ', 40); memcpy(c.flags, "NAME", 4); }
            else { c.len = 0; memset(c.flags, ' ', 40); }
            GGCWSBR(&c, name, 32);
            printf("sbr %d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "rnx") == 0) {
            c.item = kind(w[1]); c.len = atoi(w[2]); c.num = atoi(w[3]);
            GGCWRNX(&c, name, 16, value, 30);
            printf("rnx %d/%d", c.resp, c.resp2);
            if (c.resp == 0 || (c.resp == 22 && c.resp2 != 1)) printf(" %.16s|%.30s|%d|%d", name, value, c.len, c.num);
            printf("\n");
        } else {
            c.item = kind(w[1]);
            GGCWEBR(&c);
            printf("ebr %d/%d\n", c.resp, c.resp2);
        }
    }
    return 0;
}
"""


def _x4940_refused(answers: list[str]) -> bool:
    return not answers[-1].split()[0] in _X4940_HEADS


@needs_cc
def test_the_stub_reads_form_fields_query_parameters_and_browses(tmp_path):
    """#4940 (register X38), IBM WEB READ FORMFIELD / QUERYPARM and WEB STARTBROWSE / READNEXT / ENDBROWSE of HTTPHEADER,
    FORMFIELD, QUERYPARM (server): the stated request's pairs unescaped, names without case on a read, the documented
    conditions with their RESP2 (INVREQ 13 / 43 / 4, NOTFND 1, LENGERR 1 / 4 / 5, ILLOGIC 5 / 10, ENDFILE), a cut value or
    name returned again by the next READNEXT; what IBM leaves open is refused by name; no stated request refuses all."""
    exe = _stub(tmp_path, _X4940_MAIN)
    for n, (fixture, steps, answers) in enumerate(_X4940_CASES):
        req = tmp_path / f"webreq{n}.cfg"
        req.write_text(_x38_cfg(fixture), encoding="ascii")
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if _x4940_refused(answers):
            assert run.returncode == 98 and answers[-1] + ": not modelled" in run.stdout, (fixture, steps, run.stdout)
            assert run.stdout.splitlines()[:-1] == answers[:-1], (fixture, steps, run.stdout)
        else:
            assert run.returncode == 0 and run.stdout.splitlines() == answers, (fixture, steps, run.stdout)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out0")}
    for step in ("rdf a 1 24", "rdq a 1 24", "sbr f", "sbr h", "rnx f 16 30", "ebr q"):
        unstated = subprocess.run([str(exe), step], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert unstated.returncode == 98 and "HTTP request is not stated" in unstated.stdout, step


def _jstr(v: str | None) -> str:
    return "null" if v is None else f'"{v}"'


def _x4940_jtask(fixture: str) -> str:
    scheme, host, port, method, version, path, query, headers, media, body = _X38_REQ[fixture]
    hs = ", ".join(f'new String[] {{"{n}", "{v}"}}' for n, v in headers)
    return (
        'new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest('
        f'"{scheme}", "{host}", {port}, "{method}", "{version}", "{path}", "{query}", '
        f"java.util.List.<String[]>of({hs}), {_jstr(media)}, {_jstr(body)}))"
    )


@needs_javac
def test_cics_task_reads_form_fields_query_parameters_and_browses_as_the_stub_does(tmp_path):
    """#4940 (X38): CicsTask.webReadParam / webStartBrowse / webReadNext / webEndBrowse answer the steps above as the stub does
    and refuse what the stub refuses; without a stated request every one is refused."""
    helpers = r"""
    static String area(String s, int cap) { return s + ".".repeat(cap - s.length()); }
    static String pad(String s, int n) { return String.format("%-" + n + "s", s); }
    static String kind(String k) { return k.equals("h") ? "HTTPHEADER" : k.equals("f") ? "FORMFIELD" : "QUERYPARM"; }
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        switch (w[0]) {
            case "rdf", "rdq" -> {
                CicsTask.WebParam r = t.webReadParam(w[0].equals("rdf") ? "FORMFIELD" : "QUERYPARM", pad(w[1], 32),
                        Integer.parseInt(w[2]), Integer.parseInt(w[3]), 24);
                String o = w[0] + " " + r.resp() + "/" + r.resp2();
                if (r.value() != null) o += " " + area(r.value(), 24) + "|" + r.length();
                System.out.println(o);
            }
            case "sbr" -> {
                int[] r = w.length > 2 ? t.webStartBrowse(kind(w[1]), pad(w[2], 32), Integer.valueOf(w[3]))
                        : t.webStartBrowse(kind(w[1]), null, null);
                System.out.println("sbr " + r[0] + "/" + r[1]);
            }
            case "rnx" -> {
                CicsTask.WebNext r = t.webReadNext(kind(w[1]), Integer.parseInt(w[2]), 16, Integer.parseInt(w[3]), 30);
                String o = "rnx " + r.resp() + "/" + r.resp2();
                if (r.name() != null) o += " " + area(r.name(), 16) + "|" + area(r.value(), 30) + "|" + r.nameLength() + "|"
                        + r.valueLength();
                System.out.println(o);
            }
            default -> {
                int[] r = t.webEndBrowse(kind(w[1]));
                System.out.println("ebr " + r[0] + "/" + r[1]);
            }
        }
    }
"""
    parts = []
    for fixture, steps, _answers in _X4940_CASES:
        body = "\n".join(f'step(t, "{st}");' for st in steps)
        parts.append(
            f"{{ CicsTask t = {_x4940_jtask(fixture)};\n try {{\n{body}\n}} catch (UnsupportedOperationException e) {{"
            ' System.out.println("refused " + e.getMessage()); }\nSystem.out.println("--"); }'
        )
    parts.append(
        'for (String s : new String[] {"rdf a 1 24", "rdq a 1 24", "sbr f", "sbr h", "rnx f 16 30", "ebr q"}) { try { step(new '
        'CicsTask("ZC01", "ENTER", null, null), s); } catch (UnsupportedOperationException e) { System.out.println("refused " '
        "+ e.getMessage()); } }"
    )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for fixture, steps, answers in _X4940_CASES:
        end = lines.index("--", pos)
        want = [a if not (i == len(answers) - 1 and _x4940_refused(answers)) else f"refused {a}: not modelled"
                for i, a in enumerate(answers)]  # fmt: skip
        assert lines[pos:end] == want, (fixture, steps, lines[pos:end], want)
        pos = end + 1
    assert lines[pos:] == ["refused the HTTP request is not stated (withHttpRequest): not modelled"] * 6


# ---- #4950: the async child scheduler (X18): RUN / DELAY / FETCH / FREE CHILD, both runtimes on one script --------
# A step script both runtimes run: P:chan:cont:data (PUT CONTAINER), R:tran[:chan] (RUN TRANSID CHILD [CHANNEL]),
# D:ms (DELAY FOR MILLISECS), F:ANY|n:NOSUSPEND|WAIT|TIMEOUT:ms[:C] (FETCH ANY / CHILD n, C: CHANNEL), X:n (FREE CHILD
# n), G:chan:cont (GET CONTAINER). A child's program is K<ms>[P][A][F]: DELAY ms, PUT CONTAINER R (its EIBTASKN) on its
# channel, ABEND KIDA, a FETCH ANY (a command a child may not issue, R1). Each step prints one line.
# #5089: a child's program is K<ms> then, in order: P F A as above and the ops of a child that RUNs children of its
# own -- a b c d z RUN KA KB KC KD KZ, e RUN KA CHANNEL(CH.1), i / j / x RUN KY2 / KY3 / KZ, u RUN of an undefined
# transaction, w / n / t FETCH ANY WAIT / NOSUSPEND / TIMEOUT(500), r FETCH ANY WAIT CHANNEL then GET its CONTAINER R
# and PUT it as G on the channel the child was handed, q FETCH CHILD of a token it did not start, f FREE CHILD of its
# first child, M DELAY 1000.
_KIDS = {
    "KA": "K2000P", "KB": "K1000P", "KC": "K1000A", "KD": "K500", "KF": "K0F", "KZ": "K1000",
    "KG": "K300a", "KH": "K100aw", "KI": "K0abww", "KJ": "K0er", "KU": "K0uw", "KV": "K0cw",
    "KK": "K0abn", "KL": "K0at", "KM": "K0zMn", "KQ": "K0aq", "KR": "K0afn",
    "KY1": "K0iw", "KY2": "K0jw", "KY3": "K0xw",
}  # fmt: skip

_SCHED_MAIN = r"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCRUNT(gg_cics *c, char *child); int GGCFETCH(gg_cics *c); int GGCDLAY(gg_cics *c); int GGCFREE(gg_cics *c);
int GGCCHIN(gg_cics *c); int GGCCHLD(gg_cics *c); int GGCEND(gg_cics *c); int GGCPUTC(gg_cics *c, char *from);
int GGCGETC(gg_cics *c, char *into); int GGCABND(gg_cics *c);
static gg_cics c;
static void pad(char *dst, int n, const char *src) { memset(dst, ' ', n); memcpy(dst, src, strlen(src)); }
static void delay_ms(int ms) {
    pad(c.flags, 40, "FOR"); c.hours = c.mins = c.secs = -999999999; c.len = ms; GGCDLAY(&c);
}
static void token(int n, char *out) { snprintf(out, 17, "GGCHILD%09d", n); }
int main(int argc, char **argv) {
    char buf[64], tok[17], prog[9];
    memset(&c, 0, sizeof c);
    GGCCHIN(&c);
    GGCCHLD(&c);
    if (c.item == 1) { /* a child */
        memcpy(prog, c.name1, 8); prog[8] = 0;
        int ms = atoi(prog + 1);
        if (ms) delay_ms(ms);
        const char *q = prog + 1;
        while (*q >= '0' && *q <= '9') q++;
        for (; *q && *q != ' '; q++) {
            char child[17] = "-               ";
            const char *runs = "abcdzeixju";
            const char *trs[] = {"KA", "KB", "KC", "KD", "KZ", "KA", "KY2", "KZ", "KY3", "NONE"};
            const char *at = strchr(runs, *q);
            if (at && *q) {
                pad(c.name1, 8, trs[at - runs]); pad(c.flags, 40, *q == 'e' ? "CHANNEL" : "");
                if (*q == 'e') pad(c.chan, 16, "CH.1");
                GGCRUNT(&c, child);
            } else if (*q == 'P') {
                const char *n = getenv("GGCICS_TASKN");
                pad(c.flags, 40, ""); pad(c.qname, 16, "R"); c.len = (int)strlen(n); GGCPUTC(&c, (char *)n);
            } else if (*q == 'F' || *q == 'w') { pad(c.flags, 40, ""); c.num = 0; GGCFETCH(&c); }
            else if (*q == 'n') { pad(c.flags, 40, "NOSUSPEND"); c.num = 0; GGCFETCH(&c); }
            else if (*q == 't') { pad(c.flags, 40, "TIMEOUT"); c.num = 500; GGCFETCH(&c); }
            else if (*q == 'q') { pad(c.flags, 40, "CHILD "); token(7, tok); memcpy(c.qname, tok, 16); GGCFETCH(&c); }
            else if (*q == 'f') { token(1, tok); memcpy(c.qname, tok, 16); GGCFREE(&c); }
            else if (*q == 'M') delay_ms(1000);
            else if (*q == 'r') {
                pad(c.flags, 40, " CHANNEL"); c.num = 0; GGCFETCH(&c);
                if (c.resp == 0) {
                    char reply[17]; memcpy(reply, c.chan, 16); reply[16] = 0;
                    pad(c.flags, 40, "CHANNEL"); pad(c.chan, 16, reply); pad(c.qname, 16, "R"); c.len = 60; memset(buf, 0, sizeof buf);
                    GGCGETC(&c, buf);
                    pad(c.flags, 40, ""); pad(c.qname, 16, "G"); c.len = (int)strlen(buf); GGCPUTC(&c, buf);
                }
            } else if (*q == 'A') { pad(c.name1, 8, "KIDA"); pad(c.flags, 40, ""); GGCABND(&c); }
        }
        GGCEND(&c);
        return 0;
    }
    for (int i = 1; i < argc; i++) {
        char *s = argv[i], *f[5] = {0};
        int nf = 0;
        for (char *p = strtok(s, ":"); p && nf < 5; p = strtok(NULL, ":")) f[nf++] = p;
        if (f[0][0] == 'P') {
            pad(c.flags, 40, "CHANNEL"); pad(c.chan, 16, f[1]); pad(c.qname, 16, f[2]); c.len = (int)strlen(f[3]);
            GGCPUTC(&c, f[3]); printf("P %d\n", c.resp);
        } else if (f[0][0] == 'R') {
            char child[17] = "-               ";
            pad(c.name1, 8, f[1]); pad(c.flags, 40, nf > 2 ? "CHANNEL" : ""); if (nf > 2) pad(c.chan, 16, f[2]);
            GGCRUNT(&c, child); printf("R %d/%d/%.16s\n", c.resp, c.resp2, child);
        } else if (f[0][0] == 'D') {
            delay_ms(atoi(f[1])); printf("D %d\n", c.resp);
        } else if (f[0][0] == 'F') {
            char fl[40] = "";
            if (strcmp(f[1], "ANY")) { strcat(fl, "CHILD "); token(atoi(f[1]), tok); memcpy(c.qname, tok, 16); }
            if (strcmp(f[2], "WAIT")) strcat(fl, f[2]);
            if (nf > 4 || (nf > 3 && !strcmp(f[3], "C"))) strcat(fl, " CHANNEL");
            c.num = nf > 3 && strcmp(f[3], "C") ? atoi(f[3]) : 0;
            pad(c.flags, 40, fl);
            GGCFETCH(&c);
            if (c.resp == 0)
                printf("F %d/%d/%.16s/%.16s/%.4s/%d\n", c.resp, c.resp2, c.qname, strstr(fl, "CHANNEL") ? c.chan : "-               ",
                       c.item ? c.name1 : "-   ", c.num);
            else
                printf("F %d/%d\n", c.resp, c.resp2);
        } else if (f[0][0] == 'X') {
            token(atoi(f[1]), tok); memcpy(c.qname, tok, 16); GGCFREE(&c); printf("X %d/%d\n", c.resp, c.resp2);
        } else if (f[0][0] == 'G') {
            pad(c.flags, 40, "CHANNEL"); pad(c.chan, 16, f[1]); pad(c.qname, 16, f[2]); c.len = 60; memset(buf, 0, sizeof buf);
            GGCGETC(&c, buf); printf("G %d/%s\n", c.resp, buf);
        }
        fflush(stdout);
    }
    GGCEND(&c);
    return 0;
}
"""

_SCHED_JAVA = """
        java.util.Map<String, String> kids = new java.util.HashMap<>();
        for (String k : "%KIDS%".split(",")) {
            kids.put(k.split("=")[0], k.split("=")[1]);
        }
        CicsTask t = new CicsTask("GTPA", "ENTER", null, null).withTaskNumber(100).withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public String program(String tr) {
                return kids.get(tr);
            }

            public boolean transaction(String tr) {
                return kids.containsKey(tr) || tr.equals("KN");
            }

            public void run(String p, CicsTask s) {
                int at = 1;
                while (at < p.length() && Character.isDigit(p.charAt(at))) {
                    at++;
                }
                int ms = Integer.parseInt(p.substring(1, at));
                if (ms > 0) {
                    s.delay(CicsTask.delayMillis(null, null, null, null, Long.valueOf(ms)), "x");
                }
                String runs = "abcdzeixju";
                String[] trs = {"KA", "KB", "KC", "KD", "KZ", "KA", "KY2", "KZ", "KY3", "NONE"};
                for (char op : p.substring(at).toCharArray()) {
                    int r = runs.indexOf(op);
                    if (r >= 0) {
                        if (op == 'e') {
                            s.runTransid(trs[r], "CH.1");
                        } else {
                            s.runTransid(trs[r]);
                        }
                    } else if (op == 'P') {
                        byte[] n = Long.toString(s.taskNumber()).getBytes();
                        s.putContainer(null, "R", n, n.length, null, false);
                    } else if (op == 'F' || op == 'w') {
                        s.fetch(null, "WAIT", 0, false);
                    } else if (op == 'n') {
                        s.fetch(null, "NOSUSPEND", 0, false);
                    } else if (op == 't') {
                        s.fetch(null, "TIMEOUT", 500, false);
                    } else if (op == 'q') {
                        s.fetch("GGCHILD000000007", "WAIT", 0, false);
                    } else if (op == 'f') {
                        s.freeChild("GGCHILD000000001");
                    } else if (op == 'M') {
                        s.delay(1000, "x");
                    } else if (op == 'r') {
                        CicsTask.FetchResult f = s.fetch(null, "WAIT", 0, true);
                        if ("NORMAL".equals(f.resp())) {
                            CicsTask.ContainerResult g = s.getContainer(f.channel(), "R", 60);
                            s.putContainer(null, "G", g.data(), g.data().length, null, false);
                        }
                    } else if (op == 'A') {
                        s.abend("KIDA");
                        return;
                    }
                }
                s.returnTransid(null, null);
            }
        });
        try {
            for (String step : "%STEPS%".split("~")) {
                String[] f = step.split(":");
                switch (f[0]) {
                    case "P" -> System.out.println("P " + t.putContainer(f[1], f[2], f[3].getBytes(), f[3].length(), null, false).resp());
                    case "R" -> {
                        CicsTask.RunResult r = f.length > 2 ? t.runTransid(f[1], f[2]) : t.runTransid(f[1]);
                        System.out.println("R " + r.resp() + "/" + r.resp2() + "/" + (r.child() == null ? "-" : r.child()));
                    }
                    case "D" -> {
                        t.delay(CicsTask.delayMillis(null, null, null, null, Long.valueOf(f[1])), "x");
                        System.out.println("D NORMAL");
                    }
                    case "F" -> {
                        String child = f[1].equals("ANY") ? null : String.format("GGCHILD%09d", Integer.parseInt(f[1]));
                        boolean chan = f.length > 4 || (f.length > 3 && f[3].equals("C"));
                        long ms = f.length > 3 && !f[3].equals("C") ? Long.parseLong(f[3]) : 0;
                        CicsTask.FetchResult r = t.fetch(child, f[2], ms, chan);
                        System.out.println("F " + r.resp() + "/" + r.resp2() + (r.child() == null ? "" : "/" + r.child() + "/"
                                + (r.channel() == null ? "-" : r.channel()) + "/" + (r.abcode() == null ? "-" : r.abcode()) + "/"
                                + r.compstatus()));
                    }
                    case "X" -> {
                        CicsTask.FetchResult r = t.freeChild(String.format("GGCHILD%09d", Integer.parseInt(f[1])));
                        System.out.println("X " + r.resp() + "/" + r.resp2());
                    }
                    case "G" -> {
                        CicsTask.ContainerResult r = t.getContainer(f[1], f[2], 60);
                        System.out.println("G " + r.resp() + "/" + (r.data() == null ? "" : new String(r.data())));
                    }
                    default -> throw new IllegalStateException(step);
                }
            }
        } catch (UnsupportedOperationException e) {
            System.out.println("REFUSED " + e.getMessage());
        }
        java.util.function.BiConsumer<String, java.util.List<java.util.Map<String, Object>>>[] show = new java.util.function.BiConsumer[1];
        show[0] = (ind, evs) -> {
            for (java.util.Map<String, Object> e : evs) {
                String k = (String) e.get("event");
                if ("CHILD".equals(k)) {
                    System.out.println(ind + "CHILD " + e.get("child") + " " + e.get("transid"));
                    show[0].accept(ind + "  ", (java.util.List<java.util.Map<String, Object>>) e.get("events"));
                } else if ("RUN".equals(k)) {
                    System.out.println(ind + "RUN " + e.get("transid") + " " + e.get("resp"));
                } else if ("FETCH".equals(k)) {
                    System.out.println(ind + "FETCH " + e.get("resp") + "/" + e.get("resp2")
                            + (e.get("child") == null ? "" : "/" + e.get("child") + "/" + e.get("compstatus") + "/"
                            + (e.get("abcode") == null ? "-" : e.get("abcode"))));
                } else if ("FREE-CHILD".equals(k)) {
                    System.out.println(ind + "FREE-CHILD " + e.get("resp") + "/" + e.get("resp2"));
                }
            }
        };
        for (java.util.Map<String, Object> e : t.events()) {
            if ("CHILD".equals(e.get("event"))) {
                System.out.println("CHILD " + e.get("child") + " " + e.get("transid"));
                show[0].accept("  ", (java.util.List<java.util.Map<String, Object>>) e.get("events"));
            }
        }"""


def _sched_stub(tmp_path: Path, steps: list[str]) -> list[str]:
    """The stub runs `steps` (the parent EIBTASKN 100); its lines with RESP by name, a refusal as REFUSED <why>, and
    the CHILD events it logged."""
    from equivalence_cics import RESP_NAMES

    exe = _stub(tmp_path, _SCHED_MAIN)
    work = tmp_path / "work"
    (work / "out").mkdir(parents=True)
    (work / "childprogs.cfg").write_text("".join(f"{t} {p}\n" for t, p in _KIDS.items()))
    (work / "transactions.cfg").write_text("".join(f"{t}\n" for t in [*_KIDS, "KN"]))
    (work / "eib.in").write_text("GTPA DFHENTER 0126285 0103015     \n")
    env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out"),
           "EIBIN": str(work / "eib.in"), "GGCICS_TASKN": "100"}  # fmt: skip
    proc = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert proc.returncode in (0, 98), proc.stdout + proc.stderr
    out = []
    for ln in proc.stdout.splitlines():
        if ln.endswith(": not modelled"):
            out.append("REFUSED " + ln.removesuffix(": not modelled"))
            break
        verb, _, rest = ln.partition(" ")
        parts = [p.strip() or "-" for p in rest.split("/")]
        parts[0] = RESP_NAMES[int(parts[0])]
        out.append(f"{verb} {'/'.join(parts)}")

    def show(outdir: Path, ind: str, top: bool) -> None:
        """The CHILD events of a task's out directory (and, nested, what each child did: RUN, FETCH, FREE CHILD)."""
        path = outdir / "events.txt"
        for ln in path.read_text().splitlines() if path.exists() else []:
            parts = ln.split()
            kv = dict(a.split("=", 1) for a in parts[2:] if "=" in a)
            if parts[1] == "CHILD":
                out.append(f"{ind}CHILD {kv['child']} {kv['transid']}")
                show(outdir / kv["dir"] / "out", ind + "  ", False)
            elif top:
                continue
            elif parts[1] == "RUN":
                out.append(f"{ind}RUN {kv['transid']} {RESP_NAMES[int(kv['resp'])]}")
            elif parts[1] == "FETCH":
                tail = f"/{kv['child']}/{kv['compstatus']}/{kv['abcode']}" if "child" in kv else ""
                out.append(f"{ind}FETCH {RESP_NAMES[int(kv['resp'])]}/{kv['resp2']}{tail}")
            elif parts[1] == "FREE-CHILD":
                out.append(f"{ind}FREE-CHILD {RESP_NAMES[int(kv['resp'])]}/{kv['resp2']}")

    show(work / "out", "", True)
    return out


def _sched_java(tmp_path: Path, steps: list[str]) -> list[str]:
    body = _SCHED_JAVA.replace("%KIDS%", ",".join(f"{t}={p}" for t, p in _KIDS.items())).replace(
        "%STEPS%", "~".join(steps)
    )
    return _cics_task(tmp_path, body).splitlines()


_SCHEDULES = {
    # completion order, then RUN order; NOSUSPEND before the first wait; the reply channel and the child's EIBTASKN
    "order": (
        [
            "P:CH.1:IN:x",
            "R:KA:CH.1",
            "R:KB:CH.1",
            "F:ANY:NOSUSPEND",
            "D:3000",
            "F:ANY:NOSUSPEND:C",
            "G:GGREPLY000000001:R",
            "G:GGREPLY000000001:IN",
            "F:ANY:NOSUSPEND",
            "F:ANY:NOSUSPEND",
        ],
        [
            "P NORMAL",
            "R NORMAL/0/GGCHILD000000001",
            "R NORMAL/0/GGCHILD000000002",
            "F NOTFINISHED/52",
            "D NORMAL",
            "F NORMAL/0/GGCHILD000000002/GGREPLY000000001/-/1016",
            "G NORMAL/102",
            "G NORMAL/x",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "F NOTFND/1",
            "CHILD GGCHILD000000001 KA",
            "CHILD GGCHILD000000002 KB",
        ],
    ),
    # a FETCH that waits dispatches; TIMEOUT runs out (53) and moves the clock; FREE CHILD; an abended child
    "waits": (
        [
            "R:KA",
            "R:KC",
            "R:KD",
            "X:3",
            "X:3",
            "F:1:TIMEOUT:1000",
            "F:1:WAIT",
            "F:ANY:NOSUSPEND",
            "F:3:NOSUSPEND",
            "F:ANY:WAIT",
        ],
        [
            "R NORMAL/0/GGCHILD000000001",
            "R NORMAL/0/GGCHILD000000002",
            "R NORMAL/0/GGCHILD000000003",
            "X NORMAL/0",
            "X INVREQ/50",
            "F NOTFINISHED/53",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "F NORMAL/0/GGCHILD000000002/-/KIDA/900",
            "F INVREQ/50",
            "F NOTFND/1",
            "CHILD GGCHILD000000001 KA",
            "CHILD GGCHILD000000002 KC",
        ],
    ),
    # no children: FETCH ANY is INVREQ 52; a token that is not a child's is INVREQ 50, as FREE CHILD of it
    "none": (
        ["F:ANY:NOSUSPEND", "F:7:WAIT", "X:7", "D:100"],
        ["F INVREQ/52", "F INVREQ/50", "X INVREQ/50", "D NORMAL"],
    ),
    # a child that never gets a wait is not run; IBM's channel characters, and one it does not list
    "names": (
        ["R:KA:$@#./-_%&?!|=,;<", "R:KB:CH*1", "R:KB:CH X", "R:NONE"],
        ["R NORMAL/0/GGCHILD000000001", "R CHANNELERR/1/-", "R CHANNELERR/1/-", "R TRANSIDERR/1/-"],
    ),
    # a tie: the child completes at the very instant its parent resumed
    "tie": (
        ["R:KZ", "D:1000", "F:ANY:NOSUSPEND"],
        ["R NORMAL/0/GGCHILD000000001", "D NORMAL", "REFUSED", "CHILD GGCHILD000000001 KZ"],
    ),
    "timeout-tie": (
        ["R:KZ", "F:ANY:TIMEOUT:1000"],
        ["R NORMAL/0/GGCHILD000000001", "REFUSED", "CHILD GGCHILD000000001 KZ"],
    ),
    # #5089: a child's own FETCH concerns only the children it started (here none: INVREQ 52, recorded in its events)
    "child-fetch": (
        ["R:KF", "D:10"],
        ["R NORMAL/0/GGCHILD000000001", "D NORMAL", "CHILD GGCHILD000000001 KF", "  FETCH INVREQ/52"],
    ),
    # a second FETCH CHILD of a fetched child, FREE CHILD of one: refused (IBM does not say)
    "refetch": (
        ["R:KD", "F:1:WAIT", "F:1:WAIT"],
        ["R NORMAL/0/GGCHILD000000001", "F NORMAL/0/GGCHILD000000001/-/-/1016", "REFUSED", "CHILD GGCHILD000000001 KD"],
    ),
    "free-fetched": (
        ["R:KD", "F:1:WAIT", "X:1"],
        ["R NORMAL/0/GGCHILD000000001", "F NORMAL/0/GGCHILD000000001/-/-/1016", "REFUSED", "CHILD GGCHILD000000001 KD"],
    ),
    "dfh": (["R:KA:DFHTRANSACTION"], ["REFUSED"]),
    "timeout-range": (["R:KA", "F:ANY:TIMEOUT:4080001"], ["R NORMAL/0/GGCHILD000000001", "REFUSED"]),
    "no-program": (["R:KN", "D:1"], ["R NORMAL/0/GGCHILD000000001", "REFUSED"]),
    # ---- #5089 (X18): a RUN child that RUNs children of its own -------------------------------------------------
    # a child that never waits ends with its children not run (a parent's rule, at every level)
    "nested-unfetched": (
        ["R:KG", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KG",
            "  RUN KA NORMAL",
        ],
    ),
    # its FETCH waits and dispatches the grandchild; the FETCH answers with the grandchild's token and status
    "nested-fetch": (
        ["R:KH", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KH",
            "  RUN KA NORMAL",
            "  CHILD GGCHILD000000001 KA",
            "  FETCH NORMAL/0/GGCHILD000000001/NORMAL/-",
        ],
    ),
    # two grandchildren: the first to complete (KB, 1000) is fetched first; the child completes at 2000 (KA), so
    # FETCH ANY at the parent sees KB (1000) before KI (2000)
    "nested-two": (
        ["R:KI", "R:KB", "F:ANY:WAIT", "F:ANY:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "R NORMAL/0/GGCHILD000000002",
            "F NORMAL/0/GGCHILD000000002/-/-/1016",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KI",
            "  RUN KA NORMAL",
            "  RUN KB NORMAL",
            "  CHILD GGCHILD000000001 KA",
            "  CHILD GGCHILD000000002 KB",
            "  FETCH NORMAL/0/GGCHILD000000002/NORMAL/-",
            "  FETCH NORMAL/0/GGCHILD000000001/NORMAL/-",
            "CHILD GGCHILD000000002 KB",
        ],
    ),
    # FETCH CHANNEL of a grandchild: the child reads its EIBTASKN (101 + 1) and leaves it for its parent
    "nested-channel": (
        ["P:CH.1:IN:x", "R:KJ:CH.1", "F:1:WAIT:C", "G:GGREPLY000000001:G", "G:GGREPLY000000001:IN"],
        [
            "P NORMAL",
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/GGREPLY000000001/-/1016",
            "G NORMAL/102",
            "G NORMAL/x",
            "CHILD GGCHILD000000001 KJ",
            "  RUN KA NORMAL",
            "  CHILD GGCHILD000000001 KA",
            "  FETCH NORMAL/0/GGCHILD000000001/NORMAL/-",
        ],
    ),
    # failure paths of the grandchild level
    "nested-transiderr": (
        ["R:KU", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KU",
            "  RUN NONE TRANSIDERR",
            "  FETCH INVREQ/52",
        ],
    ),
    "nested-abend": (
        ["R:KV", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KV",
            "  RUN KC NORMAL",
            "  CHILD GGCHILD000000001 KC",
            "  FETCH NORMAL/0/GGCHILD000000001/ABEND/KIDA",
        ],
    ),
    "nested-nosuspend": (
        ["R:KK", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KK",
            "  RUN KA NORMAL",
            "  RUN KB NORMAL",
            "  FETCH NOTFINISHED/52",
        ],
    ),
    "nested-timeout": (
        ["R:KL", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KL",
            "  RUN KA NORMAL",
            "  CHILD GGCHILD000000001 KA",
            "  FETCH NOTFINISHED/53",
        ],
    ),
    "nested-tie": (["R:KM", "F:1:WAIT"], ["R NORMAL/0/GGCHILD000000001", "REFUSED"]),
    # a token that is not one of this task's children (the parent's first token has the same text: tokens are per task)
    "nested-foreign-token": (
        ["R:KQ", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KQ",
            "  RUN KA NORMAL",
            "  FETCH INVREQ/50",
        ],
    ),
    "nested-free": (
        ["R:KR", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KR",
            "  RUN KA NORMAL",
            "  FREE-CHILD NORMAL/0",
            "  FETCH NOTFND/1",
        ],
    ),
    # depth: a child (1), a grandchild (2) and a great-grandchild (3) run; a RUN from level 3 is refused
    "nested-depth": (
        ["R:KY2", "F:1:WAIT"],
        [
            "R NORMAL/0/GGCHILD000000001",
            "F NORMAL/0/GGCHILD000000001/-/-/1016",
            "CHILD GGCHILD000000001 KY2",
            "  RUN KY3 NORMAL",
            "  CHILD GGCHILD000000001 KY3",
            "    RUN KZ NORMAL",
            "    CHILD GGCHILD000000001 KZ",
            "    FETCH NORMAL/0/GGCHILD000000001/NORMAL/-",
            "  FETCH NORMAL/0/GGCHILD000000001/NORMAL/-",
        ],
    ),
    "nested-depth-cap": (["R:KY1", "F:1:WAIT"], ["R NORMAL/0/GGCHILD000000001", "REFUSED"]),
}


def _no_why(lines: list[str]) -> list[str]:
    return [ln.split(" ", 1)[0] if ln.startswith("REFUSED") else ln for ln in lines]


@needs_cc
@pytest.mark.skipif(not Path("/proc/self/exe").exists(), reason="the stub runs a RUN child by re-running itself")
@pytest.mark.parametrize("name", sorted(_SCHEDULES))
def test_the_stub_schedules_run_children_at_the_parents_waits(tmp_path, name):
    """#4950 (X18, ASSUMED): a RUN child is dispatched at its parent's next wait (DELAY, a FETCH that waits) and runs
    to its end first; it completes at its dispatch plus its own DELAYs. FETCH NOSUSPEND finds a child that completed
    before the parent's time (FETCH ANY: the first to complete, RUN order on a tie), TIMEOUT runs out with NOTFINISHED
    53; a tie at the parent's instant, a grandchild's command on a region resource and a second FETCH are refused."""
    steps, want = _SCHEDULES[name]
    assert _no_why(_sched_stub(tmp_path, steps)) == want


@needs_javac
@pytest.mark.parametrize("name", sorted(_SCHEDULES))
def test_cics_task_schedules_run_children_as_the_stub(tmp_path, name):
    """#4950: CicsTask.runTransid / delay / fetch / freeChild on the same scripts give the stub's answers."""
    steps, want = _SCHEDULES[name]
    assert _no_why(_sched_java(tmp_path, steps)) == want


_START_CHANNEL_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCSTRT(gg_cics *c, char *from); int GGCPUTC(gg_cics *c, char *from);
static gg_cics c;
static void pad(char *dst, int n, const char *src) { memset(dst, ' ', n); memcpy(dst, src, strlen(src)); }
int main(int argc, char **argv) {
    pad(c.flags, 40, "CHANNEL"); pad(c.chan, 16, "CH.1"); pad(c.qname, 16, "IN"); c.len = 2; GGCPUTC(&c, "ab");
    for (int i = 1; i < argc; i++) {
        pad(c.name1, 8, "GT24"); pad(c.name2, 8, ""); pad(c.qname, 16, ""); pad(c.flags, 40, "INTERVAL CHANNEL");
        pad(c.chan, 16, argv[i]); c.num = 0; c.item = 0; c.len = 0;
        GGCSTRT(&c, c.flags);
        printf("%d/%d ", c.resp, c.resp2);
        pad(c.flags, 40, "CHANNEL"); pad(c.chan, 16, "CH.1"); pad(c.qname, 16, "IN"); c.len = 2; GGCPUTC(&c, "zz");
    }
    printf("\n");
    return 0;
}
"""


@needs_cc
def test_the_stub_start_channel_hands_on_a_copy_and_checks_the_name(tmp_path):
    """#4950, IBM EXEC CICS START CHANNEL: the started task gets a copy of the channel's containers as they are at the
    START (a PUT after it does not reach it: NNN.channel); a name with a character IBM does not list is CHANNELERR
    RESP2 1; a channel not in the program's scope is refused (IBM does not say it is created)."""
    exe = _stub(tmp_path, _START_CHANNEL_MAIN)
    (tmp_path / "transactions.cfg").write_text("GT24\n")
    assert _run_stub(exe, tmp_path, "CH.1", "CH*1") == ["0/0 122/1 "]
    events = (tmp_path / "out" / "events.txt").read_text().splitlines()
    assert events[0].endswith(" channel=CH.1") and " resp=0 " in events[0] and " resp=122 resp2=1 " in events[1]
    assert (tmp_path / "out" / "001.channel").read_text().splitlines() == ["CH.1", "IN BIT 6162"]  # (no data type: BIT)
    (tmp_path / "out" / "events.txt").unlink()
    with pytest.raises(subprocess.CalledProcessError) as gone:
        _run_stub(exe, tmp_path, "OTHER")
    assert "START CHANNEL of a channel not in the program's scope: not modelled" in gone.value.stdout


@needs_javac
def test_cics_task_start_channel_as_the_stubs(tmp_path):
    """#4950: CicsTask.startRequest(...).channel(name) as the stub's GGCSTRT: the event carries the copy."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GT21", "ENTER", null, null).withClock(java.time.LocalDateTime.parse("2026-10-01T10:30:15"));
        t.putContainer("CH.1", "IN", "ab".getBytes(), 2, "CHAR", false);
        System.out.print(t.startRequest("GT24").channel("CH.1").issue().resp() + " ");
        t.putContainer("CH.1", "IN", "zz".getBytes(), 2, null, false);
        System.out.println(t.startRequest("GT24").channel("CH*1").issue().resp());
        System.out.println(t.events().get(0).get("channel") + " " + t.events().get(1).get("resp2"));
        try {
            t.startRequest("GT24").channel("OTHER").issue();
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }""",
    )
    assert out.splitlines() == ["NORMAL CHANNELERR", "{name=CH.1, containers={IN=6162}} 1",
                                "START CHANNEL(OTHER) of a channel not in the program's scope: not modelled"]  # fmt: skip


def test_cics_task_transfer_resp2_for_natural_faults_and_success(tmp_path):
    """#4986, IBM EXEC CICS XCTL / LINK conditions: with no planned fault EIBRESP2 is the natural one (LENGERR 11 for a
    COMMAREA length outside 0-32763, PGMIDERR 1 for a program with no definition) and 0 after a success; a later
    transfer replaces an earlier one's RESP2 (the plan's included), on both commands and the CHANNEL forms."""
    out = _cics_task(
        tmp_path,
        """
        CicsTask.Programs programs = new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("GONE");
            }

            public void run(String p, CicsTask task) {
                if (p.equals("CAXA")) {
                    System.out.println(task.link("CAXB", "V1", 40000) + " " + task.transferResp2());
                    System.out.println(task.link("GONE", "V1", 80) + " " + task.transferResp2());
                    System.out.println(task.link("CAXB", "V1", 80) + " " + task.transferResp2());
                    System.out.println(task.xctl("CAXB", "V1", 40000) + " " + task.transferResp2());
                    System.out.println(task.xctl("GONE", "V1", 80) + " " + task.transferResp2());
                    System.out.println(task.xctl("CAXB", "V1", 80) + " " + task.transferResp2());
                }
            }
        };
        new CicsTask("CA02", "ENTER", null, null).withPrograms(programs).run("CAXA");""",
    )
    assert out.splitlines() == ["LENGERR 11", "PGMIDERR 1", "NORMAL 0", "LENGERR 11", "PGMIDERR 1", "NORMAL 0"]


def test_the_stub_holds_file_offsets_records_and_timestamps_in_64_bits():
    """`long` is 32 bits on Windows (LLP64): record counts, file offsets (RBA), and interval control
    timestamps can exceed 2^31. The stub runtime must hold them in 64-bit types (long long / unsigned long long)
    so 32-bit truncation or sign wrapping does not occur on Windows (#5012, #5055)."""
    text = "".join(p.read_text(encoding="utf-8") for p in sorted(STUB.parent.glob("ggcics*.c")))  # #5274: its families
    # RBA browse and offset handling
    assert re.search(r"unsigned long long\s+rstart,\s*rlast;", text)
    assert re.search(r"static unsigned long long\s+rba_get\(", text)
    assert re.search(r"static void\s+rba_put\(char \*rid,\s*unsigned long long\s+v\)", text)
    assert re.search(r"static long long\s+rba_record\(", text)
    assert re.search(r"#define\s+RBA_END\s+0xFFFFFFFFULL", text)
    assert re.search(r'snprintf\(why,\s*sizeof why,\s*"%s RBA %llu on %s: no record starts there"', text)
    assert re.search(r'snprintf\(ev,\s*sizeof ev,\s*"%s file=%s rba=%llu resp=%d"', text)
    # Record counts and sizes
    assert re.search(r"static char \*load_records\(const char \*path,\s*int reclen,\s*long long \*n\)", text)
    assert re.search(r"static long long\s+pick\(const char \*all,\s*long long n,", text)
    assert re.search(r"static long long\s+pick_last\(const char \*all,\s*long long n,", text)
    assert re.search(r"static long long\s+read_search\(", text)
    assert re.search(r"long long\s+size\s*=\s*ftell\(data\);", text)
    # Container ordering and sequence
    assert re.search(r"long long\s+order;\s*}\s*gg_container;", text)
    assert re.search(r"static long long\s+container_seq\s*=\s*0;", text)
    # Timestamps in requests.cfg (GGCSTRT, GGCCNCL)
    assert re.search(r"long long\s+ex;", text)
    assert re.search(r'sscanf\(line,\s*"%63s %lld",\s*word,\s*&ex\)', text)
    assert re.search(r"long long\s+expires;", text)
    assert re.search(r'sscanf\(line,\s*"%63s %lld",\s*word,\s*&expires\)', text)


def test_no_stub_runs_with_a_posix_only_env():
    """A stub started with a literal POSIX PATH and no SYSTEMROOT cannot start on Windows (#5055): every env
    comes from `_stub_base_env()`, so the one literal lives in that helper."""
    assert len(re.findall(r'"PATH":\s*"/usr/bin:/bin"', Path(__file__).read_text(encoding="utf-8"))) == 1


# ---- #5039 (register X50): DEFINE / QUERY COUNTER with MINIMUM and MAXIMUM, GET COUNTER INCREMENT [WRAP] at the limits --
# a scenario: (the counters stated before, the steps, what both runtimes answer, the refusal the last step ends in). A step:
# "def NAME POOL VALUE MIN MAX" ("-": omitted), "get NAME POOL INC WRAP", "qry NAME POOL LIMITS", "del NAME POOL". Answer:
# "resp/resp2", then on NORMAL a get's / qry's values.
_I32 = "2147483647"
_X50_CASES = [
    # IBM's defaults: MINIMUM zero, MAXIMUM X'7FFFFFFF' (2147483647), VALUE zero; the GET adds INCREMENT after handing out the value
    (
        "",
        ["def A - - - -", "qry A - 1", "get A - 1 0", "get A - 5 0", "qry A - 0"],
        ["0/0", f"0/0 0 0 {_I32}", "0/0 0", "0/0 1", "0/0 6"],
        None,
    ),
    # 202 duplicate; 403 / 404 names; 407 MAXIMUM below MINIMUM or beyond X'7FFFFFFF'; 406 VALUE below MINIMUM or above MAXIMUM + 1
    (
        "",
        [
            "def B - 5 - -",
            "def B - 5 - -",
            "def x - 5 - -",
            "def B p 5 - -",
            "def C - 5 10 3",
            "def C - 5 0 2147483648",
            "def C - 2 3 10",
            "def C - 12 3 10",
            "def C - 11 3 10",
            "def C - 3 3 10",
            "qry C - 1",
        ],
        ["0/0", "16/202", "16/404", "16/403", "16/407", "16/407", "16/406", "16/406", "0/0", "16/202", "0/0 11 3 10"],
        None,
    ),
    # a counter at MAXIMUM + 1: SUPPRESSED RESP2 101 and unchanged without WRAP, the minimum with WRAP (then the increment on)
    (
        "",
        [
            "def D - 8 5 10",
            "get D - 1 0",
            "get D - 1 0",
            "get D - 1 0",
            "get D - 1 0",
            "qry D - 1",
            "get D - 1 1",
            "get D - 1 0",
        ],
        ["0/0", "0/0 8", "0/0 9", "0/0 10", "72/101", "0/0 11 5 10", "0/0 5", "0/0 6"],
        None,
    ),
    (
        "",
        [
            "def E - 10 5 10",
            "get E - 1 0",
            "get E - 3 1",
            "qry E - 1",
        ],
        ["0/0", "0/0 10", "0/0 5", "0/0 8 5 10"],
        None,
    ),
    # fullword limit: 2147483647 is the maximum fullword counter value
    (
        "",
        [
            "def G - 2147483646 - -",
            "get G - 1 0",
            "qry G - 0",
            "get G - 1 0",
            "get G - 1 0",
            "get G - 1 1",
            "qry G - 0",
        ],
        ["0/0", "0/0 2147483646", "0/0 2147483647", "0/0 2147483647", "72/101", "0/0 0", "0/0 1"],
        None,
    ),
    # DELETE COUNTER: 201 when none; a redefined counter has its own limits
    (
        "",
        ["def K - 3 2 9", "del K -", "del K -", "qry K - 0", "get K - 1 0", "def K - - - -", "qry K - 1"],
        ["0/0", "0/0", "16/201", "16/201", "16/201", "0/0", f"0/0 0 0 {_I32}"],
        None,
    ),
    # refused by name: an INCREMENT of zero, beyond MAXIMUM - MINIMUM, or carrying the counter past MAXIMUM + 1
    ("", ["def I - 0 0 10", "get I - 0 0"], ["0/0"], "GET COUNTER with an INCREMENT not above zero"),
    ("", ["def I - 0 0 10", "get I - 11 0"], ["0/0"], "GET COUNTER with an INCREMENT beyond the counter's range"),
    ("", ["def I - 5 0 10", "get I - 10 1"], ["0/0"], "GET COUNTER with an INCREMENT past MAXIMUM + 1"),
    # a counter with no limits (a scenario's) is as before: WRAP changes nothing, its limits are not stated
    (
        "LEG 5",
        ["get LEG - 2 1", "qry LEG - 0", "qry LEG - 1"],
        ["0/0 5", "0/0 7"],
        "QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state",
    ),
    # VALUE or MINIMUM below zero is refused
    ("", ["def N1 - -1 0 10"], [], "DEFINE COUNTER with a VALUE below zero"),
    ("", ["def N2 - 0 -1 10"], [], "DEFINE COUNTER with a MINIMUM below zero"),
]

_X50_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCXCNT(gg_cics *c);
static gg_cics c;
static void be(unsigned char *p, const char *w, int *len) {
    long long n = strtoll(w, NULL, 10);
    for (int j = 3; j >= 0; j--) { p[j] = (unsigned char)(n & 255); n >>= 8; }
    *len = strcmp(w, "-") == 0 ? 0 : 4;
}
static unsigned long long un(const unsigned char *p) { unsigned long long v = 0; for (int j = 0; j < 4; j++) v = v * 256 + p[j]; return v; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[6] = {0};
        int k = 0, vl, ll, hl;
        unsigned char v[4], lo[4], hi[4];
        for (char *t = strtok(argv[i], " "); t && k < 6; t = strtok(NULL, " ")) w[k++] = t;
        memset(c.qname, ' ', 16); memcpy(c.qname, w[1], strlen(w[1]));
        memset(c.name1, ' ', 8); if (strcmp(w[2], "-") != 0) memcpy(c.name1, w[2], strlen(w[2]) > 8 ? 8 : strlen(w[2]));
        if (strcmp(w[0], "def") == 0) {
            be(v, w[3], &vl); be(lo, w[4], &ll); be(hi, w[5], &hl);
            GGCDCNT(&c, v, vl, lo, ll, hi, hl);
            printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "get") == 0) {
            be(lo, w[3], &ll);
            GGCGCNT(&c, v, 4, lo, 4, atoi(w[4]));
            if (c.resp == 0) printf("0/0 %llu\n", un(v)); else printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "qry") == 0) {
            int lim = atoi(w[3]);
            GGCQCNT(&c, v, 4, lo, lim ? 4 : 0, hi, lim ? 4 : 0);
            if (c.resp != 0) printf("%d/%d\n", c.resp, c.resp2);
            else if (lim) printf("0/0 %llu %llu %llu\n", un(v), un(lo), un(hi));
            else printf("0/0 %llu\n", un(v));
        } else {
            GGCXCNT(&c);
            printf("%d/%d\n", c.resp, c.resp2);
        }
    }
    return 0;
}
"""


def _x50_seed(seed: str) -> str:
    return f"- {seed}\n" if seed else ""


@needs_cc
def test_the_stub_defines_queries_and_wraps_a_fullword_counter(tmp_path):
    """#5039 (register X50), IBM EXEC CICS DEFINE / QUERY / GET COUNTER: the stub's GGCDCNT / GGCQCNT / GGCGCNT."""
    exe = _stub(tmp_path, _X50_MAIN)
    for n, (seed, steps, answers, refusal) in enumerate(_X50_CASES):
        work = tmp_path / f"c{n}"
        work.mkdir()
        (work / "out").mkdir()
        (work / "counters.cfg").write_text(_x50_seed(seed), encoding="ascii")
        env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        got = run.stdout.splitlines()
        if refusal is None:
            assert run.returncode == 0 and got == answers, (steps, got)
        else:
            assert run.returncode == 98 and got[: len(answers)] == answers and refusal in run.stdout, (
                steps,
                run.stdout,
            )


@needs_javac
def test_cics_task_defines_queries_and_wraps_a_fullword_counter_as_the_stub_does(tmp_path):
    """#5039 (X50): CicsTask.defineCounter / queryCounter / getCounter(.., wrap) answer the scenarios above as the stub does
    and refuse what it refuses."""

    def u(x: str, dflt: str) -> str:
        return dflt if x == "-" else f'Long.parseLong("{x}")'

    parts = []
    for seed, steps, _answers, _refusal in _X50_CASES:
        counters = 'java.util.Map.of("/LEG", 5L)' if seed else "java.util.Map.of()"
        body = ""
        for st in steps:
            w = st.split()
            pool = '""' if w[2] == "-" else f'"{w[2]}"'
            nm = f'"{w[1]}"'
            if w[0] == "def":
                body += (f"r = t.defineCounter({pool}, {nm}, {u(w[3], '0L')}, {u(w[4], '0L')}, {u(w[5], '2147483647L')}); "
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            elif w[0] == "get":
                body += (f"g = t.getCounter({pool}, {nm}, {u(w[3], '1L')}, {'true' if w[4] == '1' else 'false'}); "
                         'System.out.println(g[0] == 0 ? "0/0 " + g[2] : g[0] + "/" + g[1]);\n')  # fmt: skip
            elif w[0] == "qry":
                lim = "true" if w[3] == "1" else "false"
                tail = ' + " " + q[3] + " " + q[4]' if lim == "true" else ""
                body += (f"q = t.queryCounter({pool}, {nm}, {lim}); "
                         f'System.out.println(q[0] == 0 ? "0/0 " + q[2]{tail} : q[0] + "/" + q[1]);\n')  # fmt: skip
            else:
                body += f't_ = t.deleteCounter({pool}, {nm}); System.out.println(t_[0] + "/" + t_[1]);\n'
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withCounters(new java.util.HashMap<>('
            + counters
            + "));\n"
            "int[] r, t_, q; long[] g;\n"
            f'try {{\n{body}}} catch (UnsupportedOperationException e) {{ System.out.println("refused " + e.getMessage()); }} }}\n'
        )
    out = _cics_task(tmp_path, "\n".join(parts)).splitlines()
    pos = 0
    for _seed, _steps, answers, refusal in _X50_CASES:
        assert out[pos : pos + len(answers)] == answers, (_steps, out[pos : pos + len(answers)])
        pos += len(answers)
        if refusal is not None:
            assert out[pos] == f"refused {refusal}: not modelled", (refusal, out[pos])
            pos += 1


# ---- #4950: channel and container names (IBM, PUT CONTAINER (CHANNEL): CHANNEL / CONTAINER) -------------------------
# IBM's PUT CONTAINER page: "The acceptable characters are A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - and _. Leading
# and embedded blank characters are not permitted"; CHANNELERR RESP2 1 / CONTAINERERR RESP2 18 for an illegal name.
# The other container commands' pages say nothing of one (refused); RUN TRANSID's page lists & < and the not sign too,
# PUT CONTAINER's does not (refused by name). Both runtimes must agree on all of it.
_IBM_NAME_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$@#/%?!:|"=,;>.-_'
_LEGAL_NAMES = [_IBM_NAME_CHARS[i : i + 16] for i in range(0, len(_IBM_NAME_CHARS), 16)] + ["A", "Z9", "a.b-c_d"]
_ILLEGAL_NAMES = ["A^B", "A B", " AB", "A~", "A[", "A{", "A\\", "A'", "A`", "A*", "A(", "A+", "A\xe9"]  # (a leading
# blank is "not permitted" too; an accented byte is no IBM character)
_DISPUTED_NAMES = ["A&B", "A<B", "A\xacB"]


def _c_lit(s: str) -> str:
    return '"' + "".join(c if c.isalnum() and c.isascii() else "\\%03o" % ord(c) for c in s) + '"'


def _j_lit(s: str) -> str:  # (octal: a \u escape is read before the string is, so \u0022 would end it)
    return _c_lit(s)


_NAME_MAIN_HEAD = _CONT_MAIN.split("int main(void) {")[0]


def _name_stub(body: str) -> str:
    return (
        _NAME_MAIN_HEAD
        + 'int main(void) {\n    char into[16], *area = NULL;\n    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); '
        + "GGCNEXT(&c, &area);\n"
        + body
        + "\n    return 0;\n}\n"
    )


@needs_cc
def test_the_stub_put_container_takes_ibms_name_characters_and_raises_ibms_conditions(tmp_path):
    """#4950: every IBM character is accepted in a CONTAINER and a CHANNEL name; any other (a leading or embedded blank
    included) is CONTAINERERR 18 / CHANNELERR 1 and creates nothing."""
    body = "".join(
        f'op({_c_lit(n)}, "CH1", "CHANNEL", 1); GGCPUTC(&c, "x"); printf("{i} %d/%d\\n", c.resp, c.resp2);\n'
        f'op("K", {_c_lit(n)}, "CHANNEL", 1); GGCPUTC(&c, "x"); printf("{i}c %d/%d\\n", c.resp, c.resp2);\n'
        for i, n in enumerate(_LEGAL_NAMES)
    )
    base = len(_LEGAL_NAMES)
    body += "".join(
        f'op({_c_lit(n)}, "CH1", "CHANNEL", 1); GGCPUTC(&c, "x"); printf("{base + i} %d/%d\\n", c.resp, c.resp2);\n'
        f'op("K", {_c_lit(n)}, "CHANNEL", 1); GGCPUTC(&c, "x"); printf("{base + i}c %d/%d\\n", c.resp, c.resp2);\n'
        for i, n in enumerate(_ILLEGAL_NAMES)
    )
    # with no CHANNEL option the current channel (here the one LINK passes) takes the PUT
    body += (
        'blank(c.name1, 8, "SUB"); c.item = 0; c.len = 0; blank(c.flags, 40, "CHANNEL"); blank(c.chan, 16, "CH1");'
        " GGCLINK(&c, NULL); GGCNEXT(&c, &area);\n"
        f'op({_c_lit("A^B")}, "", "", 1); GGCPUTC(&c, "x"); printf("cur %d/%d\\n", c.resp, c.resp2);\n'
    )
    out = _run_stub(_stub(tmp_path, _name_stub(body)), tmp_path)
    legal = [f"{i}{s} 0/0" for i in range(len(_LEGAL_NAMES)) for s in ("", "c")]
    bad = [f"{base + i}{s} {'110/18' if not s else '122/1'}" for i in range(len(_ILLEGAL_NAMES)) for s in ("", "c")]
    assert out == legal + bad + ["cur 110/18"]


@needs_cc
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        *[
            (f'op({_c_lit(n)}, "CH1", "CHANNEL", 1); GGCPUTC(&c, "x");', "holds & < or a not sign")
            for n in _DISPUTED_NAMES
        ],
        *[
            (f'op("K", {_c_lit(n)}, "CHANNEL", 1); GGCPUTC(&c, "x");', "holds & < or a not sign")
            for n in _DISPUTED_NAMES
        ],
        *[
            (f'op({_c_lit(n)}, "CH1", "CHANNEL", 4); GGCGETC(&c, into);', "holds & < or a not sign")
            for n in _DISPUTED_NAMES
        ],
        ('op("A^", "CH1", "CHANNEL", 4); GGCGETC(&c, into);', "container name 'A^'"),
        ('op("A^", "CH1", "CHANNEL", 0); GGCDELC(&c);', "container name 'A^'"),
        ('op("K", "A^", "CHANNEL", 4); GGCGETC(&c, into);', "channel name 'A^'"),
        ('op("K", "A B", "CHANNEL", 0); GGCDELC(&c);', "channel name 'A B'"),
        ('op("A^", "B^", "CHANNEL", 1); GGCPUTC(&c, "x");', "which condition IBM raises first is not documented"),
        ('op("A^", "CH1", "CHANNEL", -1); GGCPUTC(&c, "x");', "negative FLENGTH"),
        ('op("A^", "", "", 1); GGCPUTC(&c, "x");', "and no channel"),
        ('op("A^", "NOPE", "CHANNEL", 1); GGCPUTC(&c, "x");', "channel not in scope"),
    ],
)
def test_the_stub_refuses_what_ibm_leaves_open_on_container_names(tmp_path, steps, why):
    """#4950: a name holding & < or the not sign (IBM's two pages disagree), an illegal name on a command whose page
    says nothing of one (GET / DELETE CONTAINER), a name over 16, and the PUT CONTAINER combinations IBM does not
    rank are refused, never guessed."""
    exe = _stub(tmp_path, _name_stub('op("OK", "CH1", "CHANNEL", 1); GGCPUTC(&c, "x");\n' + steps))
    (tmp_path / "out").mkdir(exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    proc = subprocess.run([str(exe)], env=env, capture_output=True, encoding="latin-1", check=False)  # noqa: S603
    assert proc.returncode == 98 and why in proc.stderr + proc.stdout, proc.stdout


@needs_javac
def test_cics_task_put_container_names_as_the_stub(tmp_path):
    """#4950: CicsTask.putContainer on the stub's name cases (above), the same lines."""
    lines = []
    for i, n in enumerate(_LEGAL_NAMES):
        lines.append(f'p.accept("{i}", t.putContainer("CH1", {_j_lit(n)}, x, 1, null, false));')
        lines.append(f'p.accept("{i}c", t.putContainer({_j_lit(n)}, "K", x, 1, null, false));')
    base = len(_LEGAL_NAMES)
    for i, n in enumerate(_ILLEGAL_NAMES):
        lines.append(f'p.accept("{base + i}", t.putContainer("CH1", {_j_lit(n)}, x, 1, null, false));')
        lines.append(f'p.accept("{base + i}c", t.putContainer({_j_lit(n)}, "K", x, 1, null, false));')
    out = _cics_task(
        tmp_path,
        "byte[] x = {'x'};\n"
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN").withPrograms(new CicsTask.Programs() {\n'
        "    public boolean defined(String p) { return true; }\n"
        "    public void run(String p, CicsTask s) {\n"
        f"        CicsTask.ContainerResult r = s.putContainer(null, {_j_lit('A^B')}, x, 1, null, false);\n"
        '        System.out.println("cur " + r.resp() + "/" + r.resp2());\n'
        "    }\n});\n"
        "java.util.function.BiConsumer<String, CicsTask.ContainerResult> p = "
        '(k, r) -> System.out.println(k + " " + r.resp() + "/" + r.resp2());\n'
        + "\n".join(lines)
        + '\nt.linkChannel("SUB", "CH1");',
    )
    legal = [f"{i}{s} NORMAL/0" for i in range(len(_LEGAL_NAMES)) for s in ("", "c")]
    bad = [
        f"{base + i}{s} {'CONTAINERERR/18' if not s else 'CHANNELERR/1'}"
        for i in range(len(_ILLEGAL_NAMES))
        for s in ("", "c")
    ]
    assert out.splitlines() == legal + bad + ["cur CONTAINERERR/18"]


@needs_javac
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        *[
            (f't.putContainer("CH1", {_j_lit(n)}, x, 1, null, false);', "holds & < or a not sign")
            for n in _DISPUTED_NAMES
        ],
        *[
            (f't.putContainer({_j_lit(n)}, "K", x, 1, null, false);', "holds & < or a not sign")
            for n in _DISPUTED_NAMES
        ],
        *[(f't.getContainer("CH1", {_j_lit(n)}, 4);', "holds & < or a not sign") for n in _DISPUTED_NAMES],
        ('t.getContainer("CH1", "A^", 4);', "container name 'A^'"),
        ('t.deleteContainer("CH1", "A^");', "container name 'A^'"),
        ('t.getContainer("A^", "K", 4);', "channel name 'A^'"),
        ('t.deleteContainer("A B", "K");', "channel name 'A B'"),
        ('t.putContainer("CH1", "ABCDEFGHIJKLMNOPQ", x, 1, null, false);', "container name 'ABCDEFGHIJKLMNOPQ'"),
        ('t.putContainer("B^", "A^", x, 1, null, false);', "which condition IBM raises first is not documented"),
        ('t.putContainer("CH1", "A^", x, -1, null, false);', "negative FLENGTH"),
        ('t.putContainer(null, "A^", x, 1, null, false);', "and no channel"),
        ('t.putContainer("NOPE", "A^", x, 1, null, false);', "channel not in scope"),
    ],
)
def test_cics_task_refuses_what_ibm_leaves_open_on_container_names(tmp_path, steps, why):
    """#4950: the same refusals as the stub's."""
    out = _cics_task(
        tmp_path,
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN");\nbyte[] x = {\'x\'};\n'
        't.putContainer("CH1", "OK", x, 1, null, false);\n'
        "try {\n" + steps + '\nSystem.out.println("no refusal");\n} catch (UnsupportedOperationException e) {\n'
        'System.out.println("refused: " + e.getMessage());\n}',
    )
    assert out.startswith("refused: ") and why in out, out


# ---- #5037 (register X37): WEB SEND CONTAINER / CHANNEL ------------------------------------------------------------------------
# a step a line: KIND MEDIATYPE|- ACTION STATUSCODE|- CONV. KIND: chtext / chbit / chempty (CH's container CN holding "ab" CHAR, "ab"
# BIT, nothing; sent with CHANNEL(CH)), chmiss (CH holds only CX), nochan (CHANNEL(ZZ), a channel nobody made), nocur (no
# CHANNEL, no current channel). What both runtimes answer and the WEB-SEND body they record.
_X37_CT_CASES = [  # (steps, answers, bodies of the events)
    (["chtext - 2 - 0"], ["send 0/0"], ["ab"]),
    (["chtext text/plain 2 200 1"], ["send 0/0"], ["ab"]),
    (["chtext - 3 - 0"], ["send 0/0"], ["ab"]),
    (["chtext - 0 - 0"], ["send 0/0"], ["ab"]),
    (["chtext - 2 204 0"], ["send 16/72"], []),
    (["chtext - 7 - 0"], ["send 16/11"], []),
    (["chbit text/plain 2 - 1"], ["send 16/150"], []),
    (["chmiss - 2 - 0"], ["send 110/2"], []),
    (["nochan - 2 - 0"], ["send 122/2"], []),
    (["nocur - 2 - 0"], ["send 16/145"], []),
]
_X37_CT_REFUSED = [
    (["chbit - 2 - 0"], "WEB SEND of a DATATYPE BIT container"),
    (["chempty - 2 - 0"], "WEB SEND of an empty container"),
    (["chmiss - 7 - 0"], "WEB SEND with more than one condition at once"),
    (["chtext - 2 99 0"], "STATUSCODE outside 100-599"),
    (["chtext application/json 2 - 1"], "SRVCONVERT on a media type that is not text/*"),
    (["chtext - 2 - 0", "chtext - 2 - 0"], "WEB SEND after a response was sent"),
]

_X37_CT_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCPUTC(gg_cics *c, char *from);
int GGCWSCT(gg_cics *c, char *media, int mediacap, char *stext, int stextcap);
int GGCEND(gg_cics *c);
static gg_cics c;
static void set(char *dst, int n, const char *v) { memset(dst, ' ', (size_t)n); memcpy(dst, v, strlen(v)); }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[5], media[56], flags[40] = "";
        int k = 0, chan = 1;
        for (char *t = strtok(argv[i], " "); t && k < 5; t = strtok(NULL, " ")) w[k++] = t;
        memset(media, ' ', 56);
        if (strcmp(w[0], "nochan") == 0 || strcmp(w[0], "nocur") == 0) {
            chan = strcmp(w[0], "nochan") == 0;
        } else {
            set(c.qname, 16, strcmp(w[0], "chmiss") == 0 ? "CX" : "CN");
            set(c.chan, 16, "CH");
            set(c.flags, 40, strcmp(w[0], "chbit") == 0 ? "CHANNEL BIT" : "CHANNEL CHAR");
            c.len = strcmp(w[0], "chempty") == 0 ? 0 : 2;
            GGCPUTC(&c, "ab");
        }
        set(c.qname, 16, "CN");
        set(c.chan, 16, strcmp(w[0], "nochan") == 0 ? "ZZ" : "CH");
        if (strcmp(w[1], "-") != 0) { strcat(flags, "MEDIA "); memcpy(media, w[1], strlen(w[1])); }
        if (chan) strcat(flags, "CHANNEL");
        c.item = atoi(w[2]);
        c.num = strcmp(w[3], "-") == 0 ? -1 : atoi(w[3]);
        c.hours = -1;
        c.mins = atoi(w[4]);
        set(c.flags, 40, flags);
        GGCWSCT(&c, media, 56, "", 0);
        printf("send %d/%d\n", c.resp, c.resp2);
    }
    GGCEND(&c);
    return 0;
}
"""


@needs_cc
def test_the_stub_sends_a_container(tmp_path):
    """#5037 (register X37), IBM WEB SEND CONTAINER [CHANNEL] (server): the container's data is the response body, recorded as
    WEB-SEND; CONTAINERERR 2, CHANNELERR 2, INVREQ 145 and 150 as IBM lists them; an empty or BIT container is refused."""
    exe = _stub(tmp_path, _X37_CT_MAIN)
    req = tmp_path / "webreq.cfg"
    req.write_text("R HTTP 7A656373 80 PUT 2F6B -\n", encoding="ascii")
    for n, (steps, answers, bodies) in enumerate(_X37_CT_CASES):
        out = tmp_path / f"out{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        assert run.stdout.splitlines() == answers, steps
        got = _x37_stub_events(out)
        assert [g[3] for g in got if g[0] in (200, 204)] == bodies, steps
    for n, (steps, why) in enumerate(_X37_CT_REFUSED):
        out = tmp_path / f"refused{n}"
        out.mkdir()
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(out), "GGCICS_WEBREQ": str(req)}
        bad = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert bad.returncode == 98 and why in bad.stdout, (steps, bad.stdout)


@needs_javac
def test_cics_task_sends_a_container_as_the_stub_does(tmp_path):
    """#5037 (X37): CicsTask.webSendContainer answers the steps above as the stub does and refuses what it refuses."""

    def java(steps: list[str]) -> str:
        lines = []
        for st in steps:
            w = st.split(" ")
            put = ""
            if w[0] not in ("nochan", "nocur"):
                data = '"ab".getBytes()' if w[0] != "chempty" else "new byte[0]"
                typ = '"BIT"' if w[0] == "chbit" else '"CHAR"'
                put = f't.putContainer("CH", "{"CX" if w[0] == "chmiss" else "CN"}", {data}, {2 if w[0] != "chempty" else 0}, {typ}, false); '
            chan = "null" if w[0] == "nocur" else '"ZZ"' if w[0] == "nochan" else '"CH"'
            media = "null" if w[1] == "-" else '"' + w[1].ljust(56) + '"'
            lines.append(f"{put}send(t, {chan}, {media}, {w[2]}, {-1 if w[3] == '-' else w[3]}, {w[4]});")
        return "\n".join(lines)

    helpers = """
    static void send(CicsTask t, String chan, String media, int action, int status, int conv) {
        int[] r = t.webSendContainer(chan, "CN", media, action, status, null, -1, conv, java.nio.charset.StandardCharsets.ISO_8859_1);
        System.out.println("send " + r[0] + "/" + r[1]);
    }
    static CicsTask task() {
        return new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "zecs", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), null, null));
    }
    static void events(CicsTask t) {
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("event").equals("WEB-SEND")) System.out.println("ev " + e.get("body"));
        }
    }
"""
    parts = [
        "{ CicsTask t = task();\n" + java(steps) + '\nevents(t); System.out.println("--"); }'
        for steps, _a, _b in _X37_CT_CASES
    ]
    for steps, _why in _X37_CT_REFUSED:
        parts.append(
            "{ CicsTask t = task(); try {\n" + java(steps) + '\nSystem.out.println("not refused"); }'
            " catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); } }"
        )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + helpers + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers, bodies in _X37_CT_CASES:
        end = lines.index("--", pos)
        assert lines[pos:end] == answers + [f"ev {b}" for b in bodies], (steps, lines[pos:end])
        pos = end + 1
    refusals = [ln for ln in lines[pos:] if not ln.startswith("send ")]
    assert len(refusals) == len(_X37_CT_REFUSED)
    for got, (_steps, why) in zip(refusals, _X37_CT_REFUSED):
        assert why in got and got.endswith(": not modelled"), (got, why)
