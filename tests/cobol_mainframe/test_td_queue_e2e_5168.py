"""#5168 (oracle_assumptions.md X61): the transient-data queue forms past X57, proven end to end -- GnuCOBOL with the stub, and the det
port under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's READQ TD and TDQUEUE pages: READQ TD SET
with NOSUSPEND, an INDIRECT queue, an open extrapartition input queue read to its end, a closed one (NOTOPEN), one open for
output (INVREQ), and a RECOVSTATUS(LOGICAL) queue whose read and write a SYNCPOINT ROLLBACK undoes -- queues seeded by the case's
"td". The unit tests of both runtimes are tests/cics_crucible/test_td_queue_5168.py."""

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
       PROGRAM-ID. TDQ2DEM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC                 PIC X(8) VALUE 'ZZZZZZZZ'.
       01  WS-NEW                 PIC X(8) VALUE 'NEWREC02'.
       01  WS-LEN                 PIC S9(4) COMP VALUE 8.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-PTR                 USAGE POINTER.
       01  WS-RD                  PIC 9(4).
       01  WS-LD                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  BLK                    PIC X(8).
       PROCEDURE DIVISION.
           MOVE 'A1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('SEED') SET(WS-PTR)
                LENGTH(WS-LEN) NOSUSPEND RESP(WS-RESP) END-EXEC.
           SET ADDRESS OF BLK TO WS-PTR.
           MOVE BLK TO WS-REC.
           PERFORM SHOW.
           MOVE 'B1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('INDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'C1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('SEED') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'D1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('EXIN') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'E1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('EXIN') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'F1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('EXCL') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'G1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('EXOU') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'H1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('LOGQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           EXEC CICS WRITEQ TD QUEUE('LOGQ') FROM(WS-NEW) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           EXEC CICS SYNCPOINT ROLLBACK END-EXEC.
           MOVE 'K1' TO WS-TAG.
           MOVE 'ZZZZZZZZ' TO WS-REC.
           EXEC CICS READQ TD QUEUE('LOGQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'L1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('LOGQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'M1' TO WS-TAG.
           EXEC CICS WRITEQ TD QUEUE('EXIN') FROM(WS-NEW) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'N1' TO WS-TAG.
           EXEC CICS WRITEQ TD QUEUE('EXCL') FROM(WS-NEW) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'O1' TO WS-TAG.
           EXEC CICS WRITEQ TD QUEUE('EXOU') FROM(WS-NEW) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'P1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('UMLQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           EXEC CICS RETURN END-EXEC.
       SHOW.
           MOVE WS-RESP TO WS-RD.
           MOVE WS-LEN TO WS-LD.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-LD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-REC DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
"""
# Hand-traced from IBM (READQ TD, TDQUEUE definitions), tag RESP LENGTH INTO. A1: SET on the first seeded record. B1: INDQ routes to SEED:
# its second record. C1: SEED is empty (QZERO 23), INTO as it was. D1 / E1: the open extrapartition input queue, then its end (QZERO).
# F1: OPENTIME(DEFERRED), closed: NOTOPEN (19). G1: open for output: INVREQ (16). H1: LOGQ (RECOVSTATUS LOGICAL) read; then a record
# written and SYNCPOINT ROLLBACK: both undone. K1: the record read at H1 is back. L1: the record written before the rollback is gone (QZERO).
SENT = [
    "A1 0000 0008 ALPHA001",
    "B1 0000 0008 BRAVO002",
    "C1 0023 0008 BRAVO002",
    "D1 0000 0008 EXTRA001",
    "E1 0023 0008 EXTRA001",
    "F1 0019 0008 EXTRA001",
    "G1 0016 0008 EXTRA001",
    "H1 0000 0008 OLDREC01",
    "K1 0000 0008 OLDREC01",
    "L1 0023 0008 OLDREC01",
    "M1 0016 0008 OLDREC01",
    "N1 0019 0008 OLDREC01",
    "O1 0000 0008 OLDREC01",
    "P1 0000 0008 \u00dcBER\u00e9001",
]
CSD = """\
DEFINE TDQUEUE(SEED) GROUP(TDQ) TYPE(INTRA)
DEFINE TDQUEUE(INDQ) GROUP(TDQ) TYPE(INDIRECT) INDIRECTNAME(SEED)
DEFINE TDQUEUE(EXIN) GROUP(TDQ) TYPE(EXTRA) DDNAME(EXINDD) TYPEFILE(INPUT) OPENTIME(INITIAL)
DEFINE TDQUEUE(EXCL) GROUP(TDQ) TYPE(EXTRA) DDNAME(EXCLDD) TYPEFILE(INPUT) OPENTIME(DEFERRED)
DEFINE TDQUEUE(EXOU) GROUP(TDQ) TYPE(EXTRA) DDNAME(EXOUDD) TYPEFILE(OUTPUT) OPENTIME(INITIAL)
DEFINE TDQUEUE(LOGQ) GROUP(TDQ) TYPE(INTRA) RECOVSTATUS(LOGICAL)
DEFINE TDQUEUE(UMLQ) GROUP(TDQ) TYPE(INTRA)
DEFINE PROGRAM(TDQ2DEM) GROUP(TDQ) LANGUAGE(COBOL)
DEFINE TRANSACTION(TDQ2) GROUP(TDQ) PROGRAM(TDQ2DEM)
"""
SEEDED = {"SEED": ["ALPHA001", "BRAVO002"], "EXIN": ["EXTRA001"], "LOGQ": ["OLDREC01"], "UMLQ": ["\u00dcBER\u00e9001"]}


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_td_queue_program_is_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "TDQ2DEM.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "TDQ2.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "td-5168-synthetic", "program": "TDQ2DEM", "program_source": "cbl/TDQ2DEM.cbl",
            "copy_dirs": [], "transid": "TDQ2", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/TDQ2.csd", "commarea": None, "linked": False,
            "td": SEEDED,
            "scenarios": [{"name": "queue", "commarea": None}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "Tdq2demService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "TDQ2DEM.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "td-5168", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["queue"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
    assert [e["resp"] for e in events if e.get("event") == "READQ-TD"] == [
        "NORMAL",
        "NORMAL",
        "QZERO",
        "NORMAL",
        "QZERO",
        "NOTOPEN",
        "INVREQ",
        "NORMAL",
        "NORMAL",
        "QZERO",
        "NORMAL",
    ]
    # a refused write (INVREQ at M1, NOTOPEN at N1) records no text; the SEND TEXT lines above show the RESPs
    assert [e["text"] for e in events if e.get("event") == "WRITEQ-TD"] == ["NEWREC02", None, None, "NEWREC02"]
