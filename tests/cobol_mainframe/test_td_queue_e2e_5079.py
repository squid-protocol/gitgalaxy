"""#5079 (oracle_assumptions.md X57): READQ TD / DELETEQ TD, proven end to end -- GnuCOBOL with the stub, and the det port
under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's READQ TD / DELETEQ TD pages: a
read of an empty queue (QZERO), first in first out and a read that consumes, LENGTH shorter than the record (LENGERR,
the record lost, LENGTH set to its own length), DELETEQ TD, a queue the CSD does not define (QIDERR), an extrapartition
queue's DELETEQ TD (INVREQ). The unit tests of both runtimes are tests/cics_crucible/test_td_queue_5079.py."""

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
       PROGRAM-ID. TDQDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A                   PIC X(8) VALUE 'FIRST   '.
       01  WS-B                   PIC X(8) VALUE 'SECOND  '.
       01  WS-C                   PIC X(8) VALUE 'THIRD   '.
       01  WS-REC                 PIC X(8) VALUE SPACES.
       01  WS-LEN                 PIC S9(4) COMP VALUE 8.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RD                  PIC 9(4).
       01  WS-LD                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       PROCEDURE DIVISION.
           MOVE 'A1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('AUDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           EXEC CICS WRITEQ TD QUEUE('AUDQ') FROM(WS-A) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           EXEC CICS WRITEQ TD QUEUE('AUDQ') FROM(WS-B) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           MOVE 'B1' TO WS-TAG.
           MOVE 8 TO WS-LEN.
           EXEC CICS READQ TD QUEUE('AUDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'C1' TO WS-TAG.
           MOVE 4 TO WS-LEN.
           EXEC CICS READQ TD QUEUE('AUDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'D1' TO WS-TAG.
           MOVE 8 TO WS-LEN.
           EXEC CICS READQ TD QUEUE('AUDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           EXEC CICS WRITEQ TD QUEUE('AUDQ') FROM(WS-C) LENGTH(8)
                RESP(WS-RESP) END-EXEC.
           EXEC CICS DELETEQ TD QUEUE('AUDQ') RESP(WS-RESP) END-EXEC.
           MOVE 'E1' TO WS-TAG.
           PERFORM SHOW.
           MOVE 'F1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('AUDQ') INTO(WS-REC)
                LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'G1' TO WS-TAG.
           EXEC CICS DELETEQ TD QUEUE('EXTR') RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'H1' TO WS-TAG.
           EXEC CICS DELETEQ TD QUEUE('NOPE') RESP(WS-RESP) END-EXEC.
           PERFORM SHOW.
           MOVE 'I1' TO WS-TAG.
           EXEC CICS READQ TD QUEUE('NOPE') INTO(WS-REC)
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
# Hand-traced from IBM: tag, RESP, LENGTH, INTO. A1: QZERO (23), LENGTH and INTO untouched. B1: the first record, LENGTH 8.
# C1: LENGTH 4 under a record of 8: INTO gets its first 4 bytes (the other 4 are what INTO held: 'T   ' of 'FIRST   '), LENGERR (22), LENGTH set to
# the record's own length, 8. D1: the second record was consumed by C1 (and lost): QZERO again, LENGTH (the program reset it to 8) and INTO as they were. E1: DELETEQ TD NORMAL (the LENGTH shown is the last one set). F1: the queue is
# empty again. G1: DELETEQ TD of an extrapartition queue, INVREQ (16). H1 / I1: QIDERR (44).
SENT = [
    "A1 0023 0008",
    "B1 0000 0008 FIRST",
    "C1 0022 0008 SECOT",
    "D1 0023 0008 SECOT",
    "E1 0000 0008 SECOT",
    "F1 0023 0008 SECOT",
    "G1 0016 0008 SECOT",
    "H1 0044 0008 SECOT",
    "I1 0044 0008 SECOT",
]
CSD = """\
DEFINE TDQUEUE(AUDQ) GROUP(TDQ) TYPE(INTRA)
DEFINE TDQUEUE(EXTR) GROUP(TDQ) TYPE(EXTRA) DDNAME(EXTRDD)
DEFINE PROGRAM(TDQDEMO) GROUP(TDQ) LANGUAGE(COBOL)
DEFINE TRANSACTION(TDQ1) GROUP(TDQ) PROGRAM(TDQDEMO)
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_td_queue_program_is_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "TDQDEMO.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "TDQ.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "td-5079-synthetic", "program": "TDQDEMO", "program_source": "cbl/TDQDEMO.cbl",
            "copy_dirs": [], "transid": "TDQ1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/TDQ.csd", "commarea": None, "linked": False,
            "scenarios": [{"name": "queue", "commarea": None}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "TdqdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "TDQDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "td-5079", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["queue"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
    reads = [e for e in events if e.get("event") == "READQ-TD"]
    assert [(e["queue"], e["resp"]) for e in reads] == [
        ("AUDQ", "QZERO"),
        ("AUDQ", "NORMAL"),
        ("AUDQ", "LENGERR"),
        ("AUDQ", "QZERO"),
        ("AUDQ", "QZERO"),
        ("NOPE", "QIDERR"),
    ]
    assert [e.get("text") for e in events if e.get("event") == "WRITEQ-TD"] == ["FIRST   ", "SECOND  ", "THIRD   "]
