"""#5079 (oracle_assumptions.md X63): WAIT EXTERNAL / WAITCICS, proven end to end -- GnuCOBOL with the stub, and the det port
under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's pages (EXEC CICS WAIT EXTERNAL, WAITCICS):
ECBLIST is "a pointer to a list of addresses of MVS-format ECBs", NUMEVENTS their number, "Null (X'00000000' and X'FF000000') ECB
addresses are ignored", and a task that waits on an ECB "previously posted and not subsequently cleared" is "not suspended" (CICS
clears nothing). Posted is the register's assumption (first byte X'40', the MVS completion bit; IBM names none), so the program
posts an ECB the way IBM's WAITCICS page says ("moving an appropriate value into the ECB").
- A1: one posted ECB and two null entries: NORMAL, and the ECB still posted afterwards (nothing cleared);
- B1 / C1: a null entry, an unposted ECB and a posted one: WAIT EXTERNAL (PURGEABLE) and WAITCICS (NOTPURGEABLE) return NORMAL;
- D1: every address null: INVREQ RESP2 5; E1: NUMEVENTS not positive: INVREQ RESP2 3;
- F1: a null ECBLIST: INVREQ RESP2 2 (WAIT EXTERNAL only; WAITCICS with one is refused, a unit test);
- G1: a POST's timer-event area, posted by WAIT EVENT, in the list: NORMAL.
The list is a GETMAIN block seen through a LINKAGE table of pointers (the stub treats only task storage as a list).
A list with no posted ECB would wait for ever (nothing else runs to post one): refused by name, a unit test
(tests/cobol_mainframe/test_post_wait_converse_5079.py)."""

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
       PROGRAM-ID. WAXDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  LP                     USAGE POINTER.
       01  NULLP                  USAGE POINTER.
       01  WS-PTR                 USAGE POINTER.
       01  WS-N                   PIC S9(8) COMP VALUE 3.
       01  WS-ZN                  PIC S9(8) COMP VALUE 0.
       01  WS-ZERO                PIC X VALUE LOW-VALUE.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RESP2               PIC S9(8) COMP VALUE 0.
       01  WS-RD                  PIC 9(4).
       01  WS-R2                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-FLAG                PIC X(1) VALUE '-'.
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  ECB-LIST.
           02  ECB-ENT            USAGE POINTER OCCURS 3 TIMES.
       01  ECB.
           05  ECB-1              PIC X.
           05  FILLER             PIC X(3).
       PROCEDURE DIVISION.
           EXEC CICS GETMAIN SET(LP) FLENGTH(24)
                INITIMG(WS-ZERO) NOHANDLE END-EXEC.
           SET ADDRESS OF ECB-LIST TO LP.
           SET NULLP TO NULL.
           SET ECB-ENT(1) TO NULL.
           SET ECB-ENT(2) TO NULL.
           SET ECB-ENT(3) TO NULL.
           EXEC CICS GETMAIN SET(WS-PTR) FLENGTH(4)
                INITIMG(WS-ZERO) NOHANDLE END-EXEC.
           SET ECB-ENT(1) TO WS-PTR.
           SET ADDRESS OF ECB TO ECB-ENT(1).
           MOVE X'40' TO ECB-1.
           EXEC CICS WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(WS-N)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'A1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           SET ECB-ENT(1) TO NULL.
           EXEC CICS GETMAIN SET(WS-PTR) FLENGTH(4)
                INITIMG(WS-ZERO) NOHANDLE END-EXEC.
           SET ECB-ENT(2) TO WS-PTR.
           EXEC CICS GETMAIN SET(WS-PTR) FLENGTH(4)
                INITIMG(WS-ZERO) NOHANDLE END-EXEC.
           SET ECB-ENT(3) TO WS-PTR.
           SET ADDRESS OF ECB TO ECB-ENT(3).
           MOVE X'40' TO ECB-1.
           EXEC CICS WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(3) PURGEABLE
                NAME('WAXB') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'B1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           EXEC CICS WAITCICS ECBLIST(LP) NUMEVENTS(3) NOTPURGEABLE
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'C1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           SET ECB-ENT(2) TO NULL.
           SET ECB-ENT(3) TO NULL.
           EXEC CICS WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(3)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'D1' TO WS-TAG.
           MOVE '-' TO WS-FLAG.
           PERFORM SHOW.
           EXEC CICS WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(WS-ZN)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'E1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS WAIT EXTERNAL ECBLIST(NULLP) NUMEVENTS(3)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'F1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS POST AFTER SECONDS(30) SET(WS-PTR)
                REQID('WAXT') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           EXEC CICS WAIT EVENT ECADDR(WS-PTR)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           SET ECB-ENT(2) TO WS-PTR.
           SET ADDRESS OF ECB TO ECB-ENT(2).
           EXEC CICS WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(3)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'G1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           EXEC CICS RETURN END-EXEC.
       FLAG.
           MOVE 'U' TO WS-FLAG.
           IF ECB-1 = X'40'
              MOVE 'P' TO WS-FLAG
           END-IF.
       SHOW.
           MOVE WS-RESP TO WS-RD.
           MOVE WS-RESP2 TO WS-R2.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-FLAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-R2 DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
"""
# Hand-traced from IBM (see the module docstring): tag, the checked ECB's state (P posted, U not, - none), RESP (NORMAL 0, INVREQ 16),
# RESP2. The wait of A1-C1 and G1 returns at once (a posted ECB), and the posted byte survives it.
SENT = [
    "A1 P 0000 0000",
    "B1 P 0000 0000",
    "C1 P 0000 0000",
    "D1 - 0016 0005",
    "E1 - 0016 0003",
    "F1 - 0016 0002",
    "G1 P 0000 0000",
]
CSD = """\
DEFINE PROGRAM(WAXDEMO) GROUP(WAX) LANGUAGE(COBOL)
DEFINE TRANSACTION(WAX1) GROUP(WAX) PROGRAM(WAXDEMO)
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_wait_external_program_is_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "WAXDEMO.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "WAX.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "wax-5079-synthetic", "program": "WAXDEMO", "program_source": "cbl/WAXDEMO.cbl",
            "copy_dirs": [], "transid": "WAX1", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/WAX.csd", "commarea": None, "linked": False,
            "scenarios": [{"name": "one"}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "WaxdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "WAXDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.java.count("task.waitExternal(") == 7
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "wax-5079", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["one"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT


def test_the_harness_translates_every_wait_in_the_program():
    """The statements of PROGRAM reach the stub: the ECB waits, the distinct forms, none refused."""
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics as ec

    for text, flag in (("WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(WS-N) RESP(R) RESP2(R2)", "EXTERNAL"),
                       ("WAIT EXTERNAL ECBLIST(LP) NUMEVENTS(3) PURGEABLE NAME('WAXB')", "EXTERNAL"),
                       ("WAITCICS ECBLIST(LP) NUMEVENTS(3) NOTPURGEABLE", "WAITCICS"),
                       ("WAIT EXTERNAL ECBLIST(NULLP) NUMEVENTS(3)", "EXTERNAL")):  # fmt: skip
        out = ec.translate_command(text)
        assert out[0] == f"MOVE '{flag}' TO GG-FLAGS" and "CALL 'GGCECBW' USING GG-CICS" in out, out
