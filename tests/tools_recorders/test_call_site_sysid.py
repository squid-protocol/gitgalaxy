"""#3494: call_site_data.sysid -- a CICS LINK's SYSID(...) through the resolver and
recorder, with a byte-identical delta restore; a site without SYSID keeps its shape."""

import copy
import sqlite3

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "dpl3494", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
SRC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       PROCEDURE DIVISION.
           EXEC CICS LINK PROGRAM('REMOTEP') SYSID('AOR1')
                COMMAREA(WS-AREA)
           END-EXEC.
           EXEC CICS LINK PROGRAM('LOCALP') COMMAREA(WS-AREA) END-EXEC.
           GOBACK.
"""


def test_sysid_is_extracted_recorded_and_restored(tmp_path):
    calls = extract_boundary("cobol", SRC)["calls"]
    by_target = {c["target"]: c for c in calls}
    assert by_target["REMOTEP"]["sysid"] == "'AOR1'" and "sysid" not in by_target["LOCALP"]
    files = [{"path": "cbl/CALLER.cbl", "lang_id": "cobol", "raw_imports": [], "call_sites": calls}]
    sites, edges = resolve_invocations(copy.deepcopy(files))
    db = tmp_path / "m.db"
    RecordKeeper().record_mission(
        copy.deepcopy(files), [], {}, SESSION, str(db), call_sites=sites, invocation_edges=edges
    )
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT target, sysid FROM call_site_data ORDER BY line_number").fetchall()
    finally:
        conn.close()
    assert rows == [("REMOTEP", "'AOR1'"), ("LOCALP", None)]
    restored = {
        c["target"]: c
        for c in StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cbl/CALLER.cbl"]["call_sites"]
    }
    assert restored["REMOTEP"]["sysid"] == "'AOR1'" and "sysid" not in restored["LOCALP"]
