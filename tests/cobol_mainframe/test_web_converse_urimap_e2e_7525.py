"""#7525 (register X35): EXEC CICS WEB CONVERSE URIMAP, proven end to end -- GnuCOBOL with the stub, and the det port under
CicsTask, one synthetic program (no census or burned source: no burned program issues CONVERSE URIMAP, they use PATH). The
class: every body method (POST, PUT, PATCH: FROM + MEDIATYPE) and every bodyless one (GET, DELETE), a non-2xx status (a normal
response, RESP 0) and a response over MAXLENGTH (LENGERR RESP2 57, INTO holds the first MAXLENGTH bytes). The expected lines are
hand-traced from IBM's WEB CONVERSE page and the stated exchanges: URIMAP gives this request's path (the client URIMAP of the
session's own stated peer, an ASSUMED reading, register X35), the exchange is chosen by method and path, in the order stated.
The run-time refusals (a URIMAP the run does not state, another peer's) are not compared: the oracle and the port refuse in their
own ways, and the runtime tests (test_web_converse_urimap_post_7525.py, test_cics_runtimes.py) cover them."""

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
       PROGRAM-ID. WCUDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOKEN               PIC X(8).
       01  WS-UM                  PIC X(8) VALUE 'UM1'.
       01  WS-BODY                PIC X(40) VALUE SPACES.
       01  WS-FROM                PIC X(4) VALUE 'data'.
       01  WS-MEDIA               PIC X(56) VALUE 'text/plain'.
       01  WS-MAX                 PIC S9(8) COMP VALUE 40.
       01  WS-TOLEN               PIC S9(8) COMP VALUE 0.
       01  WS-STATUS              PIC S9(4) COMP VALUE 0.
       01  WS-RESP                PIC S9(8) COMP VALUE 0.
       01  WS-RESP2               PIC S9(8) COMP VALUE 0.
       01  WS-TAG                 PIC X(2).
       01  WS-ST                  PIC 9(3).
       01  WS-RD                  PIC 9(4).
       01  WS-R2                  PIC 9(3).
       01  WS-OUT                 PIC X(40) VALUE SPACES.
       PROCEDURE DIVISION.
           EXEC CICS WEB OPEN URIMAP(WS-UM) SESSTOKEN(WS-TOKEN)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'O1' TO WS-TAG.
           MOVE 0 TO WS-STATUS.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(POST))
                FROM(WS-FROM) FROMLENGTH(4) MEDIATYPE(WS-MEDIA)
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'P1' TO WS-TAG.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(PUT))
                FROM(WS-FROM) FROMLENGTH(4) MEDIATYPE(WS-MEDIA)
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'P2' TO WS-TAG.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(PATCH))
                FROM(WS-FROM) FROMLENGTH(4) MEDIATYPE(WS-MEDIA)
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'P3' TO WS-TAG.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(GET))
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'G1' TO WS-TAG.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(DELETE))
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'D1' TO WS-TAG.
           PERFORM SHOW.
           MOVE SPACES TO WS-BODY.
           MOVE 4 TO WS-MAX.
           EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN)
                URIMAP(WS-UM) METHOD(DFHVALUE(POST))
                FROM(WS-FROM) FROMLENGTH(4) MEDIATYPE(WS-MEDIA)
                INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN)
                STATUSCODE(WS-STATUS)
                RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           MOVE 'C1' TO WS-TAG.
           PERFORM SHOW.
           EXEC CICS WEB CLOSE SESSTOKEN(WS-TOKEN)
                RESP(WS-RESP) END-EXEC.
           EXEC CICS RETURN END-EXEC.
       SHOW.
           MOVE WS-STATUS TO WS-ST.
           MOVE WS-RESP TO WS-RD.
           MOVE WS-RESP2 TO WS-R2.
           MOVE SPACES TO WS-OUT.
           STRING WS-TAG DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-ST DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-RD DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-R2 DELIMITED BY SIZE ' ' DELIMITED BY SIZE
                  WS-BODY DELIMITED BY SPACE
                  INTO WS-OUT.
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(40) END-EXEC.
"""
CSD = """\
DEFINE PROGRAM(WCUDEMO) GROUP(WCU) LANGUAGE(COBOL)
DEFINE TRANSACTION(WCU1) GROUP(WCU) PROGRAM(WCUDEMO)
"""
PEER_PATH = "/p/one"
# method, status, text, body: the stated exchanges, answered in this order by method and path (URIMAP UM1's path)
EXCHANGES = [
    ("POST", 201, "Created", "created-body"),
    ("PUT", 200, "OK", "put-body"),
    ("PATCH", 200, "OK", "patch-body"),
    ("GET", 404, "Not Found", "no-such"),
    ("DELETE", 200, "OK", ""),
    ("POST", 200, "OK", "0123456789"),
]
# tag, STATUSCODE, RESP, RESP2, INTO. O1: WEB OPEN URIMAP completed. P1-P3: the body methods; G1: a 404 is a normal response;
# D1: no body (INTO untouched, blank); C1: a response of 10 bytes over MAXLENGTH 4 is LENGERR (22) RESP2 57, INTO the first 4 bytes.
SENT = [
    "O1 000 0000 000",
    "P1 201 0000 000 created-body",
    "P2 200 0000 000 put-body",
    "P3 200 0000 000 patch-body",
    "G1 404 0000 000 no-such",
    "D1 200 0000 000",
    "C1 200 0022 057 0123",
]


def _case() -> dict:
    peer = {"scheme": "HTTP", "host": "wcu.example", "port": 80, "urimap": "UM1", "path": PEER_PATH,
            "exchanges": [{"method": m, "path": PEER_PATH, "query": "", "status": s, "statustext": t,
                           "mediatype": "text/plain", "body": b} for m, s, t, b in EXCHANGES]}  # fmt: skip
    return {"kind": "cics", "corpus": "wcu-7525-synthetic", "program": "WCUDEMO", "program_source": "cbl/WCUDEMO.cbl",
            "copy_dirs": [], "transid": "WCU1", "clock": "2026/11/06 10:00:00.00", "datasets": {}, "screens": {},
            "csd": "csd/WCU.csd", "commarea": None, "linked": False, "http_peers": [peer],
            "scenarios": [{"name": "converse", "commarea": None}]}  # fmt: skip


def test_the_case_states_peers_the_oracle_translator_accepts_and_the_program_translates_whole():
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics_web as web

    case = _case()
    assert web.http_peers(case, case["scenarios"][0]) == case["http_peers"]
    import equivalence_cics as ec

    for method in ("POST", "PUT", "PATCH", "GET", "DELETE"):
        body = " FROM(WS-FROM) FROMLENGTH(4) MEDIATYPE(WS-MEDIA)" if method in ("POST", "PUT", "PATCH") else ""
        lines = ec.translate_command(
            f"WEB CONVERSE SESSTOKEN(WS-TOKEN) URIMAP(WS-UM) METHOD(DFHVALUE({method})){body} INTO(WS-BODY) "
            "MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN) STATUSCODE(WS-STATUS) RESP(WS-RESP) RESP2(WS-RESP2)"
        )
        assert any("GGCWCNV" in line for line in lines), method


def test_the_expected_lines_cover_each_stated_exchange():
    assert len(SENT) == len(EXCHANGES) + 1  # the WEB OPEN line and one per exchange
    assert {m for m, *_ in EXCHANGES} == {"POST", "PUT", "PATCH", "GET", "DELETE"}


@pytest.mark.slow(reason="a Maven build of the generated project and a GnuCOBOL container run")
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_converse_urimap_program_is_proven_against_gnucobol(tmp_path):
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "WCUDEMO.cbl").write_text(PROGRAM, encoding="ascii")
    (estate / "csd" / "WCU.csd").write_text(CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    (tmp_path / "case.json").write_text(json.dumps(_case()), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "WcudemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl" / "WCUDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                    project)  # fmt: skip
    assert r.stats["holes"] == [], r.stats["holes"]
    assert ".webConverse(" in r.java
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "wcu-7525", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["converse"]["cobol"]
    assert [e["text"].rstrip() for e in events if e.get("event") == "SEND-TEXT"] == SENT
