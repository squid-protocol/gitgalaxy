"""
#3355: the COMMAREA contract columns -- call_site_data.commarea /
commarea_length / commarea_datalength and record_data.copy_members -- through the
write path, the schema heal, the delta-scan restore, and the two reports.

Every back-compat edge is pinned: a table created before #3355 heals on the next
record, a baseline without the columns still rehydrates (the keys simply absent,
the shape the extractor gives a site with no COMMAREA), and a restored payload
re-records byte-identical rows.
"""

import copy
import sqlite3

import pytest

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "CicsRepo",
    "git_audit": {"commit_hash": "cb3355", "latest_commit_date": "2026-09-23T00:00:00Z"},
}

CALLER = {
    "path": "src/BNK1DCS.cbl",
    "lang_id": "cobol",
    "raw_imports": [],
    "classes": [{"name": "BNK1DCS"}],
    "call_sites": [
        {
            "verb": "LINK",
            "form": "literal",
            "operand": "INQCUST",
            "target": "INQCUST",
            "line": 834,
            "commarea": "INQCUST-COMMAREA",
        },
        {
            "verb": "RETURN TRANSID",
            "form": "literal",
            "operand": "ODCS",
            "target": "ODCS",
            "line": 300,
            "commarea": "WS-COMM-AREA",
            "commarea_length": "248",
        },
        {"verb": "CALL", "form": "literal", "operand": "CEEGMT", "target": "CEEGMT", "line": 900},
    ],
    "record_layouts": [
        {
            "section": "WORKING-STORAGE",
            "fd_name": None,
            "ordinal": 0,
            "parent_ordinal": None,
            "level": 1,
            "name": "INQCUST-COMMAREA",
            "pic": None,
            "usage": None,
            "occurs_min": None,
            "occurs_max": None,
            "occurs_depending_on": None,
            "redefines": None,
            "value": None,
            "line": 157,
            "attributes": None,
            "copy_members": "INQCUST",
        },
        {
            "section": "WORKING-STORAGE",
            "fd_name": None,
            "ordinal": 1,
            "parent_ordinal": None,
            "level": 1,
            "name": "WS-FLAG",
            "pic": "X",
            "usage": None,
            "occurs_min": None,
            "occurs_max": None,
            "occurs_depending_on": None,
            "redefines": None,
            "value": None,
            "line": 160,
            "attributes": None,
        },
    ],
}
CALLEE = {
    "path": "src/INQCUST.cbl",
    "lang_id": "cobol",
    "raw_imports": [],
    "classes": [{"name": "INQCUST"}],
    "call_sites": [],
}
UNIVERSE = [CALLER, CALLEE]

CALL_ROWS = [
    ("src/BNK1DCS.cbl", "RETURN TRANSID", 300, None, "WS-COMM-AREA", "248", None),
    ("src/BNK1DCS.cbl", "LINK", 834, "src/INQCUST.cbl", "INQCUST-COMMAREA", None, None),
    ("src/BNK1DCS.cbl", "CALL", 900, None, None, None, None),
]
SELECT_CALLS = """
    SELECT f.file_path, c.verb, c.line_number, d.file_path, c.commarea, c.commarea_length, c.commarea_datalength
    FROM call_site_data c JOIN file_data f ON c.src_file_id = f.id LEFT JOIN file_data d ON c.dst_file_id = d.id
    ORDER BY c.line_number
"""
SELECT_RECORDS = "SELECT item_name, copy_members FROM record_data ORDER BY ordinal"


def _record(db, universe=UNIVERSE):
    universe = copy.deepcopy(universe)
    sites, edges = resolve_invocations(universe)
    RecordKeeper().record_mission(universe, [], {}, SESSION, str(db), call_sites=sites, invocation_edges=edges)


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.fixture
def recorded(tmp_path):
    db = tmp_path / "cics.db"
    _record(db)
    return db


def test_the_contract_operands_persist_beside_the_call_graph(recorded):
    assert _rows(recorded, SELECT_CALLS) == CALL_ROWS
    assert _rows(recorded, SELECT_RECORDS) == [("INQCUST-COMMAREA", "INQCUST"), ("WS-FLAG", None)]


def test_re_recording_the_same_snapshot_does_not_duplicate(recorded):
    _record(recorded)
    assert _rows(recorded, SELECT_CALLS) == CALL_ROWS


def test_tables_from_before_3355_heal_on_the_next_record(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE call_site_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, repo_name TEXT, commit_hash TEXT, src_file_id INTEGER,
            verb TEXT, form TEXT, operand TEXT, target TEXT, dst_file_id INTEGER, line_number INTEGER)"""
    )
    conn.execute(
        """CREATE TABLE record_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, repo_name TEXT, commit_hash TEXT, file_id INTEGER,
            section TEXT, fd_name TEXT, ordinal INTEGER, parent_ordinal INTEGER, level_number INTEGER,
            item_name TEXT, pic TEXT, usage TEXT, occurs_min INTEGER, occurs_max INTEGER,
            occurs_depending_on TEXT, redefines TEXT, value_literal TEXT, line_number INTEGER, attributes TEXT)"""
    )
    conn.commit()
    conn.close()
    _record(db)
    assert _rows(db, SELECT_CALLS) == CALL_ROWS
    assert _rows(db, SELECT_RECORDS)[0] == ("INQCUST-COMMAREA", "INQCUST")


def _drop_contract_columns(db):
    conn = sqlite3.connect(db)
    for col in ("commarea", "commarea_length", "commarea_datalength"):
        conn.execute(f"ALTER TABLE call_site_data DROP COLUMN {col}")
    conn.execute("ALTER TABLE record_data DROP COLUMN copy_members")
    conn.commit()
    conn.close()


def test_an_unchanged_file_keeps_its_contract_through_a_delta_scan(recorded, tmp_path):
    """Full then incremental: the restored payload re-records byte-identical rows."""
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    cache = StateRehydrator(str(recorded)).load_state("CicsRepo")["ram_cache"]
    calls = {c["line"]: c for c in cache["src/BNK1DCS.cbl"]["call_sites"]}
    assert calls[834]["commarea"] == "INQCUST-COMMAREA" and "commarea_length" not in calls[834]
    assert (calls[300]["commarea"], calls[300]["commarea_length"]) == ("WS-COMM-AREA", "248")
    # A site with no COMMAREA comes back in the extractor's own shape.
    assert set(calls[900]) == {"verb", "form", "operand", "target", "line"}
    recs = cache["src/BNK1DCS.cbl"]["record_layouts"]
    assert recs[0]["copy_members"] == "INQCUST" and "copy_members" not in recs[1]

    rehydrated = [
        {**{k: f[k] for k in ("path", "lang_id", "raw_imports", "classes")}, **cache[f["path"]]} for f in UNIVERSE
    ]
    again = tmp_path / "again.db"
    _record(again, rehydrated)
    assert _rows(again, SELECT_CALLS) == _rows(recorded, SELECT_CALLS)
    assert _rows(again, SELECT_RECORDS) == _rows(recorded, SELECT_RECORDS)


def test_a_baseline_without_the_columns_still_rehydrates(recorded):
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    _drop_contract_columns(recorded)
    cache = StateRehydrator(str(recorded)).load_state("CicsRepo")["ram_cache"]
    calls = cache["src/BNK1DCS.cbl"]["call_sites"]
    assert len(calls) == 3 and all("commarea" not in c for c in calls)
    assert all("copy_members" not in r for r in cache["src/BNK1DCS.cbl"]["record_layouts"])


def test_the_audit_block_adds_the_operands_only_where_present():
    block = AuditRecorder._mainframe_facts_block(None, CALLER)
    by_line = {c["Line"]: c for c in block["Call Sites"]}
    assert by_line[834]["COMMAREA"] == "INQCUST-COMMAREA" and "COMMAREA Length" not in by_line[834]
    assert by_line[300]["COMMAREA Length"] == "248"
    assert set(by_line[900]) == {"Verb", "Form", "Operand", "Target", "Line"}
    recs = block["Record Layout"]
    assert recs[0]["Copy Members"] == "INQCUST" and "Copy Members" not in recs[1]


def test_the_llm_brief_names_the_record_each_transfer_passes():
    lines = "\n".join(LLMRecorder()._mainframe_facts_lines([copy.deepcopy(CALLER)]))
    assert "**COMMAREA passed:**" in lines
    assert "`LINK INQCUST ← INQCUST-COMMAREA`" in lines
    assert "`RETURN TRANSID ODCS ← WS-COMM-AREA LENGTH(248)`" in lines
    bare = {**CALLER, "call_sites": [CALLER["call_sites"][2]]}
    assert "COMMAREA passed" not in "\n".join(LLMRecorder()._mainframe_facts_lines([bare]))
