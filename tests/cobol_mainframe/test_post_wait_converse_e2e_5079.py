"""#5079 (oracle_assumptions.md X63): POST / WAIT EVENT and terminal CONVERSE, proven end to end -- GnuCOBOL with the stub, and the
det port under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's pages (EXEC CICS POST, WAIT EVENT,
CANCEL, CONVERSE (default)):
- A1 / B1: a POST's "4-byte control area is initialized to binary zeros", and WAIT EVENT returns once it is posted, "its first byte
  set to X'40' and its third byte to X'80'" (the task takes no time, so the wait runs the clock to the expiry, X4);
- C1: the POST has expired, so CANCEL of its REQID finds "an unexpired interval control command" no more: NOTFND;
- D1 / E1: a second POST is a new area (unposted), and its CANCEL is NORMAL;
- F1: seconds out of range, INVREQ RESP2 6; G1: a TIME already past, EXPIRED; H1: WAIT EVENT on a null pointer, INVREQ RESP2 2;
- I1: CONVERSE writes FROM to the terminal and reads the reply INTO, TOLENGTH set to its length; a reply longer than INTO is
  truncated with LENGERR and TOLENGTH the original length;
- J1 (PSTSET, a second program: the terminal is read once per task): CONVERSE SET(pointer) hands the reply back as a block a
  record is set onto, TOLENGTH its length; MAXLENGTH cuts it with LENGERR and TOLENGTH the original length (X58, X63).
The unit tests of the translators, the options and the refusals are tests/cobol_mainframe/test_post_wait_converse_5079.py."""

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
       PROGRAM-ID. PSTDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PTR                 USAGE POINTER.
       01  WS-NULL                USAGE POINTER.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RESP2               PIC S9(8) COMP VALUE 0.
       01  WS-RD                  PIC 9(4).
       01  WS-R2                  PIC 9(4).
       01  WS-LD                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-FLAG                PIC X(1) VALUE '-'.
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       01  WS-MSG                 PIC X(6) VALUE 'HELLO!'.
       01  WS-IN                  PIC X(6) VALUE SPACES.
       01  WS-LEN                 PIC S9(4) COMP VALUE 6.
       LINKAGE SECTION.
       01  ECB.
           05  ECB-1              PIC X.
           05  ECB-2              PIC X.
           05  ECB-3              PIC X.
           05  ECB-4              PIC X.
       PROCEDURE DIVISION.
           SET WS-NULL TO NULL.
           EXEC CICS POST AFTER SECONDS(30) SET(WS-PTR)
                REQID('TMR1') RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           SET ADDRESS OF ECB TO WS-PTR.
           MOVE 'A1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           EXEC CICS WAIT EVENT ECADDR(WS-PTR)
                RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           MOVE 'B1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           MOVE 0 TO WS-RESP2.
           EXEC CICS CANCEL REQID('TMR1') RESP(WS-RESP)
           END-EXEC.
           MOVE 'C1' TO WS-TAG.
           MOVE '-' TO WS-FLAG.
           PERFORM SHOW.
           EXEC CICS POST AFTER MINUTES(2) SET(WS-PTR)
                REQID('TMR2') RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           SET ADDRESS OF ECB TO WS-PTR.
           MOVE 'D1' TO WS-TAG.
           PERFORM FLAG.
           PERFORM SHOW.
           EXEC CICS CANCEL REQID('TMR2') RESP(WS-RESP)
           END-EXEC.
           MOVE 'E1' TO WS-TAG.
           MOVE '-' TO WS-FLAG.
           PERFORM SHOW.
           EXEC CICS POST INTERVAL(2560) SET(WS-PTR)
                RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           MOVE 'F1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS POST TIME(090000) SET(WS-PTR)
                RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           MOVE 'G1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS WAIT EVENT ECADDR(WS-NULL)
                RESP(WS-RESP) RESP2(WS-RESP2)
           END-EXEC.
           MOVE 'H1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS CONVERSE FROM(WS-MSG) INTO(WS-IN)
                TOLENGTH(WS-LEN) RESP(WS-RESP)
           END-EXEC.
           MOVE 0 TO WS-RESP2.
           MOVE 'I1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS RETURN END-EXEC.
       FLAG.
           MOVE 'X' TO WS-FLAG.
           IF ECB-1 = LOW-VALUE AND ECB-3 = LOW-VALUE
              MOVE 'U' TO WS-FLAG
           END-IF.
           IF ECB-1 = X'40' AND ECB-3 = X'80'
              MOVE 'P' TO WS-FLAG
           END-IF.
       SHOW.
           MOVE WS-RESP TO WS-RD.
           MOVE WS-RESP2 TO WS-R2.
           MOVE WS-LEN TO WS-LD.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-FLAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-R2 DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-IN DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-LD DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
"""


def _line(tag: str, flag: str, resp: int, resp2: int, reply: str = "", length: int = 6) -> str:
    return f"{tag} {flag} {resp:04d} {resp2:04d} {reply:<6} {length:04d}"


# Hand-traced from IBM (see the module docstring); the clock is 10:00:00, RESP numbers are DFHRESP's (NOTFND 13, INVREQ 16, LENGERR 22,
# EXPIRED 31). WS-LEN starts at 6 and only the CONVERSE changes it.
_COMMON = [
    _line("A1", "U", 0, 0),
    _line("B1", "P", 0, 0),
    _line("C1", "-", 13, 0),
    _line("D1", "U", 0, 0),
    _line("E1", "-", 0, 0),
    _line("F1", "-", 16, 6),
    _line("G1", "-", 31, 0),
    _line("H1", "-", 16, 2),
    "HELLO!",
]
SENT = {
    "short": [*_COMMON, _line("I1", "-", 0, 0, "OK", 2)],
    "long": [*_COMMON, _line("I1", "-", 22, 0, "ABCDEF", 10)],
}
SET_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PSTSET.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PTR                 USAGE POINTER.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RD                  PIC 9(4).
       01  WS-R2                  PIC 9(4).
       01  WS-LD                  PIC 9(4).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       01  WS-MSG                 PIC X(6) VALUE 'HELLO!'.
       01  WS-LEN                 PIC S9(4) COMP VALUE 6.
       LINKAGE SECTION.
       01  REPLY.
           05  REPLY-2            PIC X(2).
       PROCEDURE DIVISION.
           EXEC CICS CONVERSE FROM(WS-MSG) SET(WS-PTR)
                TOLENGTH(WS-LEN) MAXLENGTH(4) RESP(WS-RESP)
           END-EXEC.
           SET ADDRESS OF REPLY TO WS-PTR.
           MOVE WS-RESP TO WS-RD.
           MOVE 0 TO WS-R2.
           MOVE WS-LEN TO WS-LD.
           MOVE SPACES TO WS-OUT.
           STRING 'J1 ' DELIMITED BY SIZE WS-RD DELIMITED BY SIZE
                  ' ' DELIMITED BY SIZE WS-R2 DELIMITED BY SIZE
                  ' ' DELIMITED BY SIZE REPLY-2 DELIMITED BY SIZE
                  ' ' DELIMITED BY SIZE WS-LD DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
# J1: a reply of 2 bytes fits MAXLENGTH 4 (NORMAL, length 2); one of 10 is cut to 4 bytes, the view's 2 are "AB", LENGERR 22, length 10.
SET_SENT = {"short": ["HELLO!", "J1 0000 0000 OK 0002"], "long": ["HELLO!", "J1 0022 0000 AB 0010"]}
CSD = """\
DEFINE PROGRAM(PSTDEMO) GROUP(PST) LANGUAGE(COBOL)
DEFINE TRANSACTION(PST1) GROUP(PST) PROGRAM(PSTDEMO)
DEFINE PROGRAM(PSTSET) GROUP(PST) LANGUAGE(COBOL)
DEFINE TRANSACTION(PST2) GROUP(PST) PROGRAM(PSTSET)
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
@pytest.mark.parametrize(
    ("program", "source", "transid", "sent"),
    [("PSTDEMO", PROGRAM, "PST1", SENT), ("PSTSET", SET_PROGRAM, "PST2", SET_SENT)],
    ids=["post-wait-converse", "converse-set"],
)
def test_a_post_wait_converse_program_is_proven_against_gnucobol(tmp_path, program, source, transid, sent):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / f"{program}.cbl").write_text(source, encoding="ascii")
    (estate / "csd" / "PST.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "pst-5079-synthetic", "program": program, "program_source": f"cbl/{program}.cbl",
            "copy_dirs": [], "transid": transid, "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/PST.csd", "commarea": None, "linked": False,
            "scenarios": [{"name": "short", "terminal": "OK"}, {"name": "long", "terminal": "ABCDEFGHIJ"}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{program.title()}Service.java").read_text(
        "utf-8"
    )
    r = P.translate(estate / "cbl" / f"{program}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "pst-5079", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    for scenario, expected in sent.items():
        events = report["outputs"][scenario]["cobol"]
        assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == expected, scenario


def test_the_harness_calls_the_stubs_pointer_entry_for_converse_set():
    """X63 / X58: CONVERSE SET(ptr) -> GGCCONS (the stub's block), TOLENGTH set after; the option rules as the det port's."""
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics as ec

    out = ec.translate_command("CONVERSE FROM(WS-MSG) SET(WS-PTR) TOLENGTH(WS-LEN) MAXLENGTH(4)")
    assert "CALL 'GGCCONS' USING GG-CICS" in out
    assert "    BY REFERENCE WS-PTR" in out and "MOVE 4 TO GG-LEN" in out and "    MOVE GG-LEN TO WS-LEN" in out
    assert "MOVE 32768 TO GG-LEN" in ec.translate_command("CONVERSE FROM(WS-MSG) SET(WS-PTR) TOLENGTH(WS-LEN)")
    for text in ("CONVERSE FROM(WS-MSG) SET(WS-PTR)", "CONVERSE FROM(WS-MSG) SET(WS-PTR) TOLENGTH(4)"):
        with pytest.raises(ec.Unsupported, match="TOLENGTH"):
            ec.translate_command(text)
