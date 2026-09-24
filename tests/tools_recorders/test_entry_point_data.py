"""#3454: call_site_data.using_args and entry_point_data in the master DB, through
the resolver and recorder, with a byte-identical delta restore; a CALL without
USING keeps its pre-#3454 shape."""

import copy
import sqlite3

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "cu3454", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
CALLS = [
    {
        "verb": "CALL",
        "form": "literal",
        "operand": "CSUTLDTC",
        "target": "CSUTLDTC",
        "line": 392,
        "using_args": "A,B,C",
    },
    {"verb": "CALL", "form": "literal", "operand": "CEE3ABD", "target": "CEE3ABD", "line": 410},
]
ENTRIES = [{"kind": "PROCEDURE", "entry_name": None, "params": "LS-DATE,LS-DATE-FORMAT,LS-RESULT", "line": 88}]
UNIVERSE = [
    {"path": "cbl/CORPT00C.cbl", "lang_id": "cobol", "raw_imports": [], "call_sites": CALLS},
    {
        "path": "cbl/CSUTLDTC.cbl",
        "lang_id": "cobol",
        "raw_imports": [],
        "classes": [{"name": "CSUTLDTC"}],
        "entry_points": ENTRIES,
    },
]


def _record(db):
    files = copy.deepcopy(UNIVERSE)
    sites, edges = resolve_invocations(files)
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), call_sites=sites, invocation_edges=edges)
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_using_args_and_entry_points_are_recorded(tmp_path):
    db = _record(tmp_path / "m.db")
    assert _rows(db, "SELECT operand, using_args FROM call_site_data ORDER BY line_number") == [
        ("CSUTLDTC", "A,B,C"),
        ("CEE3ABD", None),
    ]
    assert _rows(db, "SELECT kind, entry_name, params, line_number FROM entry_point_data") == [
        ("PROCEDURE", None, "LS-DATE,LS-DATE-FORMAT,LS-RESULT", 88)
    ]


def test_a_delta_restore_is_identical(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    restored = {c["operand"]: c for c in cache["cbl/CORPT00C.cbl"]["call_sites"]}
    assert restored["CSUTLDTC"]["using_args"] == "A,B,C"
    assert "using_args" not in restored["CEE3ABD"]  # the pre-#3454 shape
    assert cache["cbl/CSUTLDTC.cbl"]["entry_points"] == ENTRIES
