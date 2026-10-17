"""#5168 round 5 (oracle_assumptions.md X66): SET / INQUIRE TDQUEUE ENABLESTATUS and the DISABLED condition proven end to end --
GnuCOBOL with the stub, and the det port under CicsTask, one synthetic program whose SEND TEXT lines are hand-traced from IBM's pages
(CICS TS 6.x). The unit tests of both runtimes are tests/cics_crucible/test_td_queue_5168.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _step(tag: str, body: str) -> str:
    """One MOVE tag, the command wrapped inside column 72, and a PERFORM SHOW."""
    lines, cur = [], ""
    for word in body.split():
        if cur and len(cur) + 1 + len(word) > 56:
            lines.append(cur)
            cur = "     " + word
        else:
            cur = f"{cur} {word}" if cur else word
    lines.append(cur)
    return (
        f"           MOVE '{tag}' TO WS-TAG.\n"
        + "".join(f"           {ln}\n" for ln in lines)
        + "           PERFORM SHOW.\n"
    )


_STEPS = [
    ("A1", "EXEC CICS INQUIRE TDQUEUE('SEED') ENABLESTATUS(WS-ES)\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC."),
    ("B1", "EXEC CICS WRITEQ TD QUEUE('SEED') FROM(WS-NEW) LENGTH(8)\n     RESP(WS-RESP) END-EXEC."),
    (
        "C1",
        "EXEC CICS SET TDQUEUE('SEED') ENABLESTATUS(DFHVALUE(DISABLED))\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.",
    ),
    ("D1", "EXEC CICS INQUIRE TDQUEUE('SEED') ENABLESTATUS(WS-ES)\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC."),
    ("E1", "EXEC CICS WRITEQ TD QUEUE('SEED') FROM(WS-NEW) LENGTH(8)\n     RESP(WS-RESP) END-EXEC."),
    ("F1", "EXEC CICS READQ TD QUEUE('SEED') INTO(WS-REC) LENGTH(WS-LEN)\n     RESP(WS-RESP) END-EXEC."),
    ("G1", "EXEC CICS DELETEQ TD QUEUE('SEED')\n     RESP(WS-RESP) END-EXEC."),
    (
        "H1",
        "EXEC CICS SET TDQUEUE('SEED') ENABLESTATUS(DFHVALUE(ENABLED))\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.",
    ),
    ("I1", "EXEC CICS READQ TD QUEUE('SEED') INTO(WS-REC) LENGTH(WS-LEN)\n     RESP(WS-RESP) END-EXEC."),
    (
        "J1",
        "EXEC CICS SET TDQUEUE('EXOU') ENABLESTATUS(DFHVALUE(DISABLED))\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.",
    ),
    ("K1", "EXEC CICS WRITEQ TD QUEUE('EXOU') FROM(WS-NEW) LENGTH(8)\n     RESP(WS-RESP) END-EXEC."),
    ("L1", "EXEC CICS SET TDQUEUE('EXOU') ENABLESTATUS(WS-BAD)\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC."),
    (
        "M1",
        "EXEC CICS SET TDQUEUE('GONE') ENABLESTATUS(DFHVALUE(DISABLED))\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.",
    ),
    ("N1", "EXEC CICS INQUIRE TDQUEUE('GONE') ENABLESTATUS(WS-ES)\n     RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC."),
]

PROGRAM = (
    """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TDQ5DEM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC                 PIC X(8) VALUE 'ZZZZZZZZ'.
       01  WS-NEW                 PIC X(8) VALUE 'NEWREC03'.
       01  WS-LEN                 PIC S9(4) COMP VALUE 8.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RESP2               PIC S9(8) COMP VALUE 0.
       01  WS-ES                  PIC S9(8) COMP VALUE 0.
       01  WS-BAD                 PIC S9(8) COMP VALUE 7.
       01  WS-RD                  PIC 9(4).
       01  WS-R2                  PIC 9(4).
       01  WS-OD                  PIC 9(4).
       01  WS-TAG                 PIC X(2).
       01  WS-OUT                 PIC X(30) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       PROCEDURE DIVISION.
"""
    + "".join(_step(t, b) for t, b in _STEPS)
    + """\
           EXEC CICS RETURN END-EXEC.
       SHOW.
           MOVE WS-RESP TO WS-RD.
           MOVE WS-RESP2 TO WS-R2.
           MOVE WS-ES TO WS-OD.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-R2 DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-OD DELIMITED BY SIZE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(30) END-EXEC.
           MOVE 0 TO WS-RESP WS-RESP2 WS-ES.
"""
)
# Hand-traced from IBM (SET / INQUIRE TDQUEUE, WRITEQ / READQ / DELETEQ TD, CICS TS 6.x): tag RESP RESP2 ENABLESTATUS (ENABLED 23,
# DISABLED 24; DFHRESP DISABLED 84). A1: SEED is enabled; B1 writes. C1 disables it, D1: DISABLED; E1 / F1 / G1: write, read and delete
# answer DISABLED. H1 enables it again, I1 reads the first record. J1 disables EXOU, K1: the write answers DISABLED (no record).
# L1: an invalid CVDA is INVREQ RESP2 10. M1 / N1: GONE is QIDERR RESP2 1.
SENT = [
    "A1 0000 0000 0023",
    "B1 0000 0000 0000",
    "C1 0000 0000 0000",
    "D1 0000 0000 0024",
    "E1 0084 0000 0000",
    "F1 0084 0000 0000",
    "G1 0084 0000 0000",
    "H1 0000 0000 0000",
    "I1 0000 0000 0000",
    "J1 0000 0000 0000",
    "K1 0084 0000 0000",
    "L1 0016 0010 0000",
    "M1 0044 0001 0000",
    "N1 0044 0001 0000",
]
CSD = """\
DEFINE TDQUEUE(SEED) GROUP(TDQ) TYPE(INTRA)
DEFINE TDQUEUE(EXOU) GROUP(TDQ) TYPE(EXTRA) DDNAME(EXOUDD) TYPEFILE(OUTPUT) OPENTIME(INITIAL)
DEFINE PROGRAM(TDQ5DEM) GROUP(TDQ) LANGUAGE(COBOL)
DEFINE TRANSACTION(TDQ5) GROUP(TDQ) PROGRAM(TDQ5DEM)
"""
SEEDED = {"SEED": ["FIRSTREC"]}


def test_the_program_lines_are_the_ones_traced():
    assert len(SENT) == len(_STEPS) and [s[:2] for s in SENT] == [t for t, _ in _STEPS]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_an_enablestatus_program_is_proven_against_gnucobol(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "TDQ5DEM.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "TDQ5.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"kind": "cics", "corpus": "td-5168-enable-synthetic", "program": "TDQ5DEM", "program_source": "cbl/TDQ5DEM.cbl",
            "copy_dirs": [], "transid": "TDQ5", "clock": "2026/10/14 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/TDQ5.csd", "commarea": None, "linked": False,
            "td": SEEDED,
            "scenarios": [{"name": "queue", "commarea": None}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "Tdq5demService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "TDQ5DEM.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "td-5168e", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["queue"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
    # the disabled queues' writes record no text (DISABLED at E1 and K1); the enabled one's does (B1)
    assert [e["text"] for e in events if e.get("event") == "WRITEQ-TD"] == ["NEWREC03", None, None]
