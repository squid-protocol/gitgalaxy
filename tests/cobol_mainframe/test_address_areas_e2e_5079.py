"""#5079 (X59): the equivalence harness states the TWA / CWA / TCTUA sizes (TRANSACTION TWASIZE, SIT WRKAREA, TYPETERM USERAREALEN).

Before this the three areas were proven by the cics-crucible runner only. A case or scenario may now carry `twasize`, `wrkarea`
and `userarealen` (a TCTUA is the terminal's, so it needs a `termid`); each is stated to the stub ($GGCICS_TWASIZE, $GGCICS_WRKAREA,
$GGCICS_USERAREALEN) and to the port (withTwaSize, withCwa, withTctua) alike, and present in the scenario facts only when stated.
The end-to-end proof is one synthetic program whose SEND TEXT lines are hand-traced from IBM's ADDRESS page: each pointer addresses
the area's own bytes, so a write through one SET ADDRESS view shows in a view made from a second ADDRESS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import equivalence_cics as ec  # noqa: E402


def test_no_area_is_stated_unless_the_case_states_one():
    assert not set(ec.AREA_KEYS) & set(ec.terminal_facts({}, {"name": "s"}))


def test_each_area_is_stated_from_the_scenario_else_the_case():
    facts = ec.terminal_facts(
        {"twasize": 4, "wrkarea": 8, "termid": "T001"}, {"name": "s", "wrkarea": 16, "userarealen": 2}
    )
    assert (facts["twasize"], facts["wrkarea"], facts["userarealen"]) == (4, 16, 2)


@pytest.mark.parametrize("key", ec.AREA_KEYS)
@pytest.mark.parametrize("bad", [-1, "8", 1.5, True])
def test_an_area_size_that_is_not_a_byte_count_is_refused_by_name(key, bad):
    with pytest.raises(ec.Unsupported, match=f'"{key}" is a byte count'):
        ec.terminal_facts({"termid": "T001"}, {"name": "s", key: bad})


def test_a_tctua_needs_the_terminal_that_owns_it():
    with pytest.raises(ec.Unsupported, match='"userarealen" is a byte count.*termid'):
        ec.terminal_facts({}, {"name": "s", "userarealen": 8})


PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ARADEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PT                  USAGE POINTER.
       01  WS-PC                  USAGE POINTER.
       01  WS-PU                  USAGE POINTER.
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  TW                     PIC X(4).
       01  CW                     PIC X(4).
       01  TU                     PIC X(4).
       01  TW2                    PIC X(4).
       01  CW2                    PIC X(4).
       01  TU2                    PIC X(4).
       PROCEDURE DIVISION.
           EXEC CICS ADDRESS TWA(WS-PT) CWA(WS-PC) TCTUA(WS-PU)
                END-EXEC.
           SET ADDRESS OF TW TO WS-PT.
           SET ADDRESS OF CW TO WS-PC.
           SET ADDRESS OF TU TO WS-PU.
           MOVE 'TWAX' TO TW.
           MOVE 'CWAY' TO CW.
           MOVE 'TCTZ' TO TU.
           EXEC CICS ADDRESS TWA(WS-PT) CWA(WS-PC) TCTUA(WS-PU)
                END-EXEC.
           SET ADDRESS OF TW2 TO WS-PT.
           SET ADDRESS OF CW2 TO WS-PC.
           SET ADDRESS OF TU2 TO WS-PU.
           MOVE 'W1' TO WS-TAG.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  TW2 DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  CW2 DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  TU2 DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
# Hand-traced from IBM: the second ADDRESS returns the same area as the first, so each view reads what the first view wrote.
SENT = ["W1 TWAX CWAY TCTZ"]
CSD = """\
DEFINE PROGRAM(ARADEMO) GROUP(ARA) LANGUAGE(COBOL)
DEFINE TRANSACTION(ARA1) GROUP(ARA) PROGRAM(ARADEMO)
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_the_sized_areas_are_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cpy").mkdir()
    (estate / "cbl" / "ARADEMO.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "ARA.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "ara-5079-synthetic", "program": "ARADEMO", "program_source": "cbl/ARADEMO.cbl",
            "copy_dirs": [], "transid": "ARA1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/ARA.csd", "commarea": None, "linked": False,
            "scenarios": [{"name": "sized", "termid": "T001", "twasize": 4, "wrkarea": 4, "userarealen": 4}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "ArademoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "ARADEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "ara-5079", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["sized"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
