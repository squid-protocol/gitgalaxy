"""#5079 (oracle_assumptions.md X59): ADDRESS EIB / COMMAREA, proven end to end -- GnuCOBOL with the stub, and the det port
under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's ADDRESS page ("a pointer reference set
to the address of the EXEC interface block (EIB)" / "of the communication area (COMMAREA) available to the currently
executing program"): the pointers are no copies, so a LINKAGE view set to the EIB shows the EIB's later updates (EIBRESP
after a command) and a write through the COMMAREA view is the DFHCOMMAREA's own. The unit tests of the refusals are
tests/cics_crucible/test_address_5079.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

TOOLS = Path(__file__).resolve().parents[1] / "tools"

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ADRDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PE                  USAGE POINTER.
       01  WS-PC                  USAGE POINTER.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RD                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       01  WS-REC                 PIC X(8) VALUE SPACES.
       01  WS-LEN                 PIC S9(4) COMP VALUE 8.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05  CA-TAG             PIC X(4).
       01  EV.
           05  FILLER             PIC X(8).
           05  EV-TRNID           PIC X(4).
           05  FILLER             PIC X(64).
           05  EV-RESP            PIC S9(8) COMP.
       01  CV.
           05  CV-TAG             PIC X(4).
       PROCEDURE DIVISION.
           EXEC CICS ADDRESS EIB(WS-PE) COMMAREA(WS-PC) RESP(WS-RESP)
                END-EXEC.
           SET ADDRESS OF EV TO WS-PE.
           SET ADDRESS OF CV TO WS-PC.
           MOVE 'A1' TO WS-TAG.
           MOVE EV-RESP TO WS-RD.
           PERFORM SHOW.
           EXEC CICS READQ TD QUEUE('NOPE') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           MOVE 'B1' TO WS-TAG.
           MOVE EV-RESP TO WS-RD.
           PERFORM SHOW.
           MOVE 'WXYZ' TO CV-TAG.
           MOVE 'C1' TO WS-TAG.
           MOVE 0 TO WS-RD.
           PERFORM SHOW.
           EXEC CICS RETURN END-EXEC.
       SHOW.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  EV-TRNID DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  CA-TAG DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
"""
# Hand-traced from IBM: tag, the transaction id the EIB view reads, the EIB view's EIBRESP, the COMMAREA's tag. A1: ADDRESS completed
# (NORMAL, 0) and the views read the EIB (ADR1) and the COMMAREA the task started with (ABCD). B1: the READQ TD of an undefined queue is
# QIDERR (44) and the view, one storage with the EIB, shows it. C1: the write through the COMMAREA view is the DFHCOMMAREA's own.
SENT = [
    "A1 ADR1 0000 ABCD",
    "B1 ADR1 0044 ABCD",
    "C1 ADR1 0000 WXYZ",
]
CSD = """\
DEFINE PROGRAM(ADRDEMO) GROUP(ADR) LANGUAGE(COBOL)
DEFINE TRANSACTION(ADR1) GROUP(ADR) PROGRAM(ADRDEMO)
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_address_program_is_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cpy").mkdir()
    (estate / "cpy" / "ADRCA.cpy").write_text(
        "       01  ADR-CA.\n           05  CA-TAG             PIC X(4).\n", encoding="ascii"
    )
    (estate / "cbl" / "ADRDEMO.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "ADR.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "adr-5079-synthetic", "program": "ADRDEMO", "program_source": "cbl/ADRDEMO.cbl",
            "copy_dirs": [], "transid": "ADR1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/ADR.csd", "commarea": {"segments": [{"copybook": "cpy/ADRCA.cpy", "record": "ADR-CA"}]}, "linked": False,
            "scenarios": [{"name": "queue", "commarea": {"CA-TAG": "ABCD"}}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "AdrdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "ADRDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "adr-5079", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["queue"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
