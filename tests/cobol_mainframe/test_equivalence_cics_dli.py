"""#5278 (register I5): EXEC DLI under CICS, the oracle side. equivalence_cics.py rewrites each EXEC DLI to a CALL of
ggdli.c's EXEC entry points (GGDLISCHD, GGDLIX, GGDLITERM), stages the case's ims DBD / PSB / seed in the scenario
directory, and compares both runtimes' final database bytes (a DLI-DBS event) beside the CICS events. The unit tests
need nothing; the end-to-end proof needs EQUIVALENCE_E2E=1, Docker and a JDK 17."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tests" / "tools"
sys.path.insert(0, str(TOOLS))

import equivalence_cics as ec  # noqa: E402

FIXTURE = ROOT / "tests" / "equivalence" / "ims" / "fixture"


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _jdk() is None,
                         reason="needs EQUIVALENCE_E2E=1, Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLICDEM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DEPT                PIC X(20).
       01  WS-EMP                 PIC X(20).
       01  WS-KEY                 PIC X(4) VALUE 'E001'.
       01  WS-D100                PIC X(4) VALUE 'D100'.
       01  WS-D999                PIC X(4) VALUE 'D999'.
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       PROCEDURE DIVISION.
           EXEC DLI SCHD PSB((WS-TAG)) NODHABEND END-EXEC.
           MOVE 'A1' TO WS-TAG.
           PERFORM SHOW.
           MOVE 'B1' TO WS-TAG.
           EXEC DLI GU USING PCB(1) SEGMENT(DEPT) WHERE(DEPTNO=WS-D100)
                SEGMENT(EMP) WHERE(EMPNO = WS-KEY) INTO(WS-EMP)
                END-EXEC.
           PERFORM SHOW.
           MOVE 'BOBBY     ' TO WS-EMP(5:10).
           MOVE 'C1' TO WS-TAG.
           EXEC DLI REPL USING PCB(1) SEGMENT(EMP) FROM(WS-EMP)
                END-EXEC.
           PERFORM SHOW.
           MOVE 'D1' TO WS-TAG.
           EXEC DLI GU USING PCB(2) SEGMENT(DEPT) WHERE(DEPTNO=WS-D999)
                INTO(WS-DEPT) END-EXEC.
           PERFORM SHOW.
           MOVE 'D400FINANCE' TO WS-DEPT.
           MOVE 'E1' TO WS-TAG.
           EXEC DLI ISRT USING PCB(1) SEGMENT(DEPT) FROM(WS-DEPT)
                END-EXEC.
           PERFORM SHOW.
           MOVE 'F1' TO WS-TAG.
           EXEC DLI DLET USING PCB(1) SEGMENT(DEPT) FROM(WS-DEPT)
                END-EXEC.
           PERFORM SHOW.
           MOVE 'G1' TO WS-TAG.
           EXEC DLI TERM END-EXEC.
           PERFORM SHOW.
           EXEC CICS RETURN END-EXEC.
       SHOW.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  DIBSTAT DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-EMP DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
"""
CSD = """\
DEFINE PROGRAM(DLICDEM) GROUP(DLI) LANGUAGE(COBOL)
DEFINE TRANSACTION(DLIC) GROUP(DLI) PROGRAM(DLICDEM)
"""


def _seg(name: str, data: str) -> dict:
    return {"segment": name, "text": data}


def _case() -> dict:
    return {"kind": "cics", "corpus": "dli-5278-synthetic", "program": "DLICDEM",
            "program_source": "cbl/DLICDEM.cbl", "copy_dirs": [], "transid": "DLIC",
            "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {}, "csd": "csd/DLIC.csd",
            "commarea": None, "linked": False,
            "ims": {"dbd": ["ims/LVLDBD.dbd"], "psb": "ims/LVLPSB.psb",
                    "seed": {"LVLDBD": {"segments": [
                        _seg("DEPT", "D100SALES"), _seg("EMP", "E001ALICE     \u0000\u0000\u0000"),
                        _seg("DEPT", "D200OPS")]}}},
            "scenarios": [{"name": "run", "commarea": None}]}  # fmt: skip


def test_exec_dli_becomes_the_calls_of_the_oracles_entry_points():
    """Each command is one CALL of ggdli.c with every argument's mode stated (BY VALUE persists to the next
    argument in GnuCOBOL), DIBSTAT answered, a WHERE value a data name."""
    out, _ = ec.translate(PROGRAM)
    assert "CALL 'GGDLISCHD' USING BY REFERENCE DIBSTAT BY VALUE 1" in out
    assert "CALL 'GGDLITERM' USING BY REFERENCE DIBSTAT" in out
    assert "BY CONTENT 'GU  '" in out and "BY CONTENT 'DEPT    DEPTNO  EQ'" in out
    assert "BY REFERENCE WS-D100" in out and "BY REFERENCE WS-KEY" in out and "BY VALUE LENGTH OF WS-KEY" in out
    assert "BY CONTENT 'REPL'" in out and "BY CONTENT 'DLET'" in out and "BY CONTENT 'ISRT'" in out
    assert "01  DIB." in out
    assert max(len(ln) for ln in out.splitlines()) <= 72


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("EXEC DLI GU USING PCB(1) SEGMENT(A) SEGMENT(B) SEGMENT(C) SEGMENT(D) INTO(X) END-EXEC", "more than 3"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(A) INTO(5) END-EXEC", "a data name expected"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(A) WHERE(F = 'X') INTO(X) END-EXEC", "data name expected"),
        ("EXEC DLI CHKP END-EXEC", "not modelled"),
        ("EXEC DLI TERM PSB END-EXEC", "no option"),
    ],
)  # fmt: skip
def test_a_dli_form_the_oracle_does_not_model_is_refused_by_name(stmt, why):
    with pytest.raises(ec.Unsupported, match=why):
        ec.translate_dli(stmt.removeprefix("EXEC DLI ").removesuffix(" END-EXEC"))


def _prove(tmp_path: Path, name: str, program: str, csd: str, case: dict) -> dict:
    """Translate `program` with the det translator and prove it against GnuCOBOL + ggdli.c (the report, proven or not)."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    import det_port  # noqa: E402

    estate = tmp_path / "estate"
    for sub in ("cbl", "csd", "ims"):
        (estate / sub).mkdir(parents=True)
    (estate / "cbl" / f"{name}.cbl").write_text(program, encoding="ascii")
    (estate / "csd" / "DLIC.csd").write_text(csd, encoding="ascii")
    for dbd in ("LVLDBD.dbd", "LVLPSB.psb"):
        shutil.copy(FIXTURE / dbd, estate / "ims" / dbd)
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{name.title()}Service.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / f"{name}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "dli-5278", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    return report


@E2E
def test_a_cics_dli_program_is_compared_against_gnucobol_database_bytes(tmp_path):
    report = _prove(tmp_path, "DLICDEM", PROGRAM, CSD, _case())
    events = report["outputs"]["run"]["cobol"]
    sent = [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"]
    # IBM: SCHD / REPL on the held segment / ISRT / TERM blank; a miss GE; DLET with no get before it DJ
    assert [ln[:5].rstrip() for ln in sent] == ["A1", "B1", "C1", "D1 GE", "E1", "F1 DJ", "G1"], sent
    assert sent[1].endswith("E001ALICE") and sent[2].endswith("E001BOBBY")
    (dbs,) = [e["dbs"] for e in events if e.get("event") == "DLI-DBS"]
    data = bytes.fromhex(dbs["LVLDBD"])
    assert b"BOBBY" in data and b"ALICE" not in data and b"D400FINANCE" in data


# #5233: a program that answers every DIBSTAT, run unfaulted and with one planned status per scenario
FAULT_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLICFLT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DEPT                PIC X(20).
       01  WS-EMP                 PIC X(20).
       01  WS-KEY                 PIC X(4) VALUE 'E001'.
       01  WS-NONE                PIC X(4) VALUE 'E999'.
       01  WS-D100                PIC X(4) VALUE 'D100'.
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(50) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       PROCEDURE DIVISION.
           MOVE 'A1' TO WS-TAG.
           EXEC DLI SCHD PSB((WS-TAG)) NODHABEND END-EXEC.
           PERFORM SHOW.
           IF DIBSTAT NOT = SPACES GO TO DONE.
           MOVE 'B1' TO WS-TAG.
           EXEC DLI GU USING PCB(1) SEGMENT(DEPT) WHERE(DEPTNO=WS-D100)
                INTO(WS-DEPT) END-EXEC.
           PERFORM SHOW.
           MOVE 'C1' TO WS-TAG.
           EXEC DLI GNP USING PCB(1) SEGMENT(EMP) WHERE(EMPNO = WS-KEY)
                INTO(WS-EMP) END-EXEC.
           PERFORM SHOW.
           MOVE 'D1' TO WS-TAG.
           EXEC DLI GNP USING PCB(1) SEGMENT(EMP) WHERE(EMPNO = WS-NONE)
                INTO(WS-EMP) END-EXEC.
           PERFORM SHOW.
           MOVE 'E1' TO WS-TAG.
           EXEC DLI GU USING PCB(1) SEGMENT(DEPT) WHERE(DEPTNO=WS-D100)
                INTO(WS-DEPT) END-EXEC.
           PERFORM SHOW.
           MOVE 'F1' TO WS-TAG.
           EXEC DLI GNP USING PCB(1) SEGMENT(EMP) INTO(WS-EMP) END-EXEC.
           PERFORM SHOW.
           MOVE 'BOBBY     ' TO WS-EMP(5:10).
           MOVE 'G1' TO WS-TAG.
           EXEC DLI REPL USING PCB(1) SEGMENT(EMP) FROM(WS-EMP)
                END-EXEC.
           PERFORM SHOW.
           MOVE 'H1' TO WS-TAG.
           EXEC DLI TERM END-EXEC.
           PERFORM SHOW.
           GO TO DONE.
       SHOW.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  DIBSTAT DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-EMP DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(50) END-EXEC.
       DONE.
           EXEC CICS RETURN END-EXEC.
"""
FAULT_RUNS = {  # scenario -> its dli_faults
    "base": [],
    "schd-tc": [{"op": "SCHD", "status": "TC"}],
    "gu-ge": [{"op": "GU", "nth": 1, "status": "GE"}],
    "gnp-am": [{"op": "GNP", "nth": 3, "status": "AM"}],
    "repl-ac": [{"op": "REPL", "status": "AC"}],
    "every-gnp-gb": [{"op": "GNP", "nth": "*", "status": "GB"}],
}


def _statuses(report: dict, name: str) -> dict[str, str]:
    sent = [e["text"].rstrip() for e in report["outputs"][name]["cobol"] if e.get("event") == "SEND-TEXT"]
    return {ln[:2]: ln[3:5].strip() for ln in sent}


@E2E
def test_planned_dli_statuses_fire_the_same_on_both_runtimes_and_a_qualified_gnp_that_finds_nothing_is_ge(tmp_path):
    case = {**_case(), "program": "DLICFLT", "program_source": "cbl/DLICFLT.cbl",
            "scenarios": [{"name": n, "commarea": None, **({"dli_faults": f} if f else {})}
                          for n, f in FAULT_RUNS.items()]}  # fmt: skip
    report = _prove(tmp_path, "DLICFLT", FAULT_PROGRAM, CSD.replace("DLICDEM", "DLICFLT"), case)
    base = _statuses(report, "base")
    assert base == {"A1": "", "B1": "", "C1": "", "D1": "GE", "E1": "", "F1": "", "G1": "", "H1": ""}, base
    assert _statuses(report, "schd-tc") == {"A1": "TC"}
    assert _statuses(report, "gu-ge")["B1"] == "GE" and _statuses(report, "gu-ge")["C1"] == "GP"
    assert _statuses(report, "gnp-am")["F1"] == "AM"
    assert _statuses(report, "repl-ac")["G1"] == "AC"
    assert {k: v for k, v in _statuses(report, "every-gnp-gb").items() if k in ("C1", "D1", "F1")} == {
        "C1": "GB", "D1": "GB", "F1": "GB"}  # fmt: skip
    for name, plan in FAULT_RUNS.items():
        fired = report["outputs"][name].get("fired")
        assert (fired is not None) == bool(plan)
        if plan:
            assert fired["cobol"] and fired["cobol"] == fired["java"], (name, fired)
    assert report["outputs"]["gu-ge"]["fired"]["cobol"] == ["DLI GU 1 GE"]


def test_a_scenarios_dli_faults_become_the_plan_both_stubs_read():
    case = _case()
    sc = {"name": "s", "dli_faults": [{"op": "GNP", "nth": 2, "status": "GE"}, {"op": "SCHD", "status": "TC"},
                                      {"op": "REPL", "nth": "*", "status": "AM"}]}  # fmt: skip
    assert ec.dli_fault_lines(case, sc) == ["GNP 2 GE", "SCHD 1 TC", "REPL * AM"]
    assert ec.dli_fault_lines(case, {"name": "s"}) == []


@pytest.mark.parametrize(
    "fault",
    [
        {"op": "CHKP", "status": "GE"},  # a BMP call, no CICS command
        {"op": "TERM", "status": "GE"},
        {"op": "SCHD", "status": "GE"},  # SCHD answers TC only
        {"op": "GU", "status": "XX"},
        {"op": "GU", "nth": 0, "status": "GE"},
        {"op": "GU", "nth": "2", "status": "GE"},
    ],
)  # fmt: skip
def test_a_dli_fault_the_models_do_not_state_is_refused(fault):
    with pytest.raises(ec.Unsupported, match="dli_fault"):
        ec.dli_fault_lines(_case(), {"name": "s", "dli_faults": [fault]})


def test_dli_faults_need_an_ims_section():
    case = {k: v for k, v in _case().items() if k != "ims"}
    with pytest.raises(ec.Unsupported, match='no "ims" section'):
        ec.dli_fault_lines(case, {"name": "s", "dli_faults": [{"op": "GU", "status": "GE"}]})
