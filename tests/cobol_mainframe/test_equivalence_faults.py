"""#4023 follow-up: file / CICS fault injection in the equivalence harness -- both sides get the same fault at the
same statement, and a fault run is proven like the normal one.

Pure parts are pinned here: the plan both sides read, which faults a run selects, how a run is judged (abend,
RETURN-CODE, faults fired), the CICS conditions a scenario may inject, and the generated runtime and porting rules
that give the Java side the same faults. The GnuCOBOL side (tests/equivalence/faults/ggfault.c, ggabend.c) runs
against a small program when EQUIVALENCE_E2E=1 (it needs Docker); the CardDemo proofs with their faults are the
EQUIVALENCE_E2E tests in test_equivalence.py / test_equivalence_cics.py.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import _RUNTIME  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA  # noqa: E402

CASE = {"name": "c", "program": "P", "datasets": {}, "faults": [
    {"name": "open", "plan": [{"dd": "INFILE", "op": "OPEN", "nth": 1, "status": "35"}]},
    {"name": "both", "plan": [{"dd": "X", "op": "READ", "nth": 1, "status": "23"},
                              {"dd": "X", "op": "READ", "nth": "*", "status": "30"}]}]}  # fmt: skip


def test_the_plan_is_one_fault_per_line_as_both_sides_read_it():
    assert eq.fault_plan(CASE["faults"][0]) == "INFILE OPEN 1 35\n"
    assert eq.fault_plan(CASE["faults"][1]) == "X READ 1 23\nX READ * 30\n"
    with pytest.raises(ValueError):
        eq.fault_plan({"name": "bad", "plan": [{"dd": "X", "op": "SEEK", "status": "30"}]})
    with pytest.raises(ValueError):
        eq.fault_plan({"name": "bad", "plan": [{"dd": "X", "op": "READ", "status": "3"}]})


def test_a_run_selects_all_faults_none_or_named_ones():
    assert [f["name"] for f in eq.selected_faults(CASE, None)] == ["open", "both"]
    assert eq.selected_faults(CASE, "none") == []
    assert [f["name"] for f in eq.selected_faults(CASE, "both")] == ["both"]
    with pytest.raises(SystemExit):
        eq.selected_faults(CASE, "nope")


def _run(abend=None, rc="0", fired=None):
    out = {"ABEND": abend.encode()} if abend else {"RETURN-CODE": rc.encode()}
    if fired is not None:
        out["FAULTS"] = fired.encode()
    return out


def test_a_fault_run_is_equal_on_the_same_abend_and_the_same_faults_fired():
    f = CASE["faults"][0]
    run = eq.compare_run(CASE, Path("."), _run("U0999", fired="INFILE OPEN 1 35\n"),
                         _run("U0999", fired="INFILE OPEN 1 35\n"), fault=f)  # fmt: skip
    assert run["ok"] and run["summary"] == "both ABEND U0999"
    # an abend the port did not code, or none at all, is a difference; outputs are not compared after an abend
    assert not eq.compare_run(
        CASE,
        Path("."),
        _run("U0999", fired="INFILE OPEN 1 35\n"),
        _run("UNCODED java.lang.IllegalStateException", fired="INFILE OPEN 1 35\n"),
        fault=f,
    )["ok"]
    assert (
        "Java None"
        in eq.compare_run(
            CASE,
            Path("."),
            _run("U0999", fired="INFILE OPEN 1 35\n"),
            _run(rc="0", fired="INFILE OPEN 1 35\n"),
            fault=f,
        )["summary"]
    )


def test_a_fault_that_never_fires_or_fires_on_one_side_only_proves_nothing():
    f = CASE["faults"][0]
    run = eq.compare_run(CASE, Path("."), _run(rc="0", fired=""), _run(rc="0", fired=""), fault=f)
    assert not run["ok"] and "never fired" in run["summary"]
    run = eq.compare_run(CASE, Path("."), _run("U0999", fired="INFILE OPEN 1 35\n"), _run("U0999", fired=""), fault=f)
    assert not run["ok"] and "faults fired differ" in run["summary"]


def test_a_normal_run_compares_the_return_code():
    assert eq.compare_run(CASE, Path("."), _run(rc="4"), _run(rc="4"))["ok"]
    assert "RETURN-CODE: COBOL 4, Java 0" in eq.compare_run(CASE, Path("."), _run(rc="4"), _run(rc="0"))["summary"]


def test_cics_scenarios_inject_named_conditions_as_dfhresp_numbers():
    sc = {"name": "s", "faults": [{"cmd": "READ", "file": "ACCTDAT", "resp": "IOERR"},
                                  {"file": "CUSTDAT", "nth": "*", "resp": "NOTOPEN", "resp2": 7}]}  # fmt: skip
    assert ec.fault_lines(sc) == ["READ ACCTDAT 1 17 0", "READ CUSTDAT * 19 7"]
    assert ec.CICS_RESP["NOTFND"] == 13 and ec.CICS_RESP["DISABLED"] == 84
    with pytest.raises(ec.Unsupported):
        ec.fault_lines({"name": "s", "faults": [{"file": "X", "resp": "NOSUCHCONDITION"}]})


def test_the_java_side_gets_the_same_faults_and_codes_abends():
    files, abend = _RUNTIME["CobolFiles"], _RUNTIME["CobolAbend"]
    for method in ("public String open(String dd)", "Read<T> read(String dd", "Read<T> readNext(String dd",
                   "public String write(String dd", "public String rewrite(String dd", "public String close(String dd",
                   "gitgalaxy.faults.plan", "gitgalaxy.faults.log"):  # fmt: skip
        assert method in files, method
    assert 'String.format(Locale.ROOT, "U%04d", Math.floorMod(abcode, 4096))' in abend
    assert "public <T> FileRead<T> read(String file" in CICS_TASK_JAVA and "withFaults(" in CICS_TASK_JAVA
    rules = "\n".join(PORTING_RULES)
    assert "CobolFiles" in rules and "CobolAbend.user" in rules and "task.read(file" in rules


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker")
def test_the_gnucobol_injector_and_abend_stub(tmp_path):
    """The planned statement returns its status instead of running: an OPEN 35 takes the program's error branch to
    CEE3ABD (U0999), a READ 10 is AT END, and each fault that fires is logged."""
    prog = "".join(f"       {x}\n" for x in [  # fixed format: every line ends before column 73
        "IDENTIFICATION DIVISION.", "PROGRAM-ID. P.", "ENVIRONMENT DIVISION.", "INPUT-OUTPUT SECTION.",
        "FILE-CONTROL.", "    SELECT IN-F ASSIGN TO INFILE ORGANIZATION IS SEQUENTIAL",
        "           FILE STATUS IS WS-ST.", "DATA DIVISION.", "FILE SECTION.", "FD IN-F.", "01 IN-R PIC X(4).",
        "WORKING-STORAGE SECTION.", "01 WS-ST PIC XX.", "01 ABCODE PIC S9(9) BINARY.",
        "01 TIMING PIC S9(9) BINARY.", "PROCEDURE DIVISION.", "    OPEN INPUT IN-F",
        "    IF WS-ST NOT = '00'", "       MOVE 999 TO ABCODE", "       CALL 'CEE3ABD' USING ABCODE, TIMING",
        "    END-IF", *["    READ IN-F AT END DISPLAY 'END ' WS-ST",
                        "         NOT AT END DISPLAY 'REC ' IN-R END-READ"] * 2,
        "    STOP RUN."])  # fmt: skip
    (tmp_path / "P.cbl").write_text(prog, encoding="ascii")
    (tmp_path / "in.dat").write_bytes(b"ABCDEFGH")
    for stub in ("ggfault.c", "ggabend.c"):
        shutil.copy(eq.FAULTS_DIR / stub, tmp_path / stub)
    (tmp_path / "open.plan").write_text("INFILE OPEN 1 35\n", encoding="ascii")
    (tmp_path / "read.plan").write_text("INFILE READ 2 10\n", encoding="ascii")
    script = ("set -e; gcc -shared -fPIC -O2 -o ggfault.so ggfault.c -ldl; cobc -x -std=ibm -o p P.cbl ggabend.c; "
              "INFILE=in.dat ./p > normal.out; "
              "GG_ABEND=abend GGFAULT_PLAN=open.plan GGFAULT_LOG=open.log LD_PRELOAD=./ggfault.so INFILE=in.dat ./p "
              "> open.out || true; "
              "GGFAULT_PLAN=read.plan GGFAULT_LOG=read.log LD_PRELOAD=./ggfault.so INFILE=in.dat ./p > read.out")  # fmt: skip
    proc = subprocess.run(["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v",  # noqa: S603, S607
                           f"{tmp_path}:/work", "-w", "/work", eq.IMAGE, "bash", "-c", script],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert (tmp_path / "normal.out").read_text().split() == ["REC", "ABCD", "REC", "EFGH"]
    assert (tmp_path / "abend").read_text().strip() == "U0999"
    assert (tmp_path / "open.log").read_text() == "INFILE OPEN 1 35\n"
    assert (tmp_path / "read.out").read_text().split() == ["REC", "ABCD", "END", "10"]
    assert (tmp_path / "read.log").read_text() == "INFILE READ 2 10\n"
