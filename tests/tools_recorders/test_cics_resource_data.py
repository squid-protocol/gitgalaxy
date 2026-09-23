"""
#3351-#3354: cics_resource_data -- EXEC CICS FILE/MAP/QUEUE/CONTAINER/CHANNEL
operations in the master DB.

These pin the properties the design turns on:
  1. Operations ride on each file's own `cics_resources` payload (a per-file
     fact), and every command becomes one row with all its columns.
  2. The table cascade-deletes with file_data, so re-recording the same snapshot
     does not duplicate rows.
  3. A delta scan restores an unchanged program's rows exactly, and a baseline
     from before the channel still rehydrates.
  4. The audit report carries every row; the LLM brief summarises per resource.
"""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "cc0101", "latest_commit_date": "2026-09-23T00:00:00Z"},
}


def _op(verb, kind, access, operand, name, resolution, line, **cols):
    base = {
        "verb": verb,
        "kind": kind,
        "access": access,
        "operand": operand,
        "name": name,
        "resolution": resolution,
        "candidates": None,
        "qualifier_operand": None,
        "qualifier": None,
        "record_clause": None,
        "record": None,
        "attributes": None,
        "line": line,
    }
    base.update(cols)
    return base


# One of each kind, as the extractor emits them (CBSA / carddemo shapes).
PROGRAM = {
    "path": "cobol_src/CRECUST.cbl",
    "lang_id": "cobol",
    "raw_imports": [],
    "cics_resources": [
        _op(
            "READ",
            "FILE",
            "read",
            "'CUSTOMER'",
            "CUSTOMER",
            "literal",
            265,
            record_clause="INTO",
            record="OUTPUT-DATA",
            attributes="RIDFLD(CUSTOMER-KY) UPDATE",
        ),
        _op(
            "SEND",
            "MAP",
            "write",
            "'BNK1CA'",
            "BNK1CA",
            "literal",
            966,
            qualifier_operand="'BNK1CAM'",
            qualifier="BNK1CAM",
            record_clause="FROM",
            record="BNK1CAO",
            attributes="ERASE CURSOR",
        ),
        _op(
            "WRITEQ",
            "QUEUE",
            "write",
            "'JOBS'",
            "JOBS",
            "literal",
            517,
            qualifier="TD",
            record_clause="FROM",
            record="JCL-RECORD",
        ),
        _op(
            "PUT",
            "CONTAINER",
            "write",
            "WS-PUT-CONT-NAME",
            None,
            "ambiguous",
            557,
            candidates="CIPA,CIPB",
            qualifier_operand="WS-CHANNEL-NAME",
            qualifier="CIPCREDCHANN",
            record_clause="FROM",
            record="DFHCOMMAREA",
        ),
        _op(
            "RUN",
            "CHANNEL",
            "pass",
            "WS-CHANNEL-NAME",
            "CIPCREDCHANN",
            "move",
            582,
            qualifier_operand="WS-RUN-TRANSID",
        ),
    ],
}
UNIVERSE = [PROGRAM, {"path": "COBOL/EMPTY.cbl", "lang_id": "cobol", "raw_imports": []}]


def _record(db, universe=UNIVERSE):
    RecordKeeper().record_mission([dict(f) for f in universe], [], {}, SESSION, str(db))


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_operation_becomes_a_row_with_its_columns(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    rows = _rows(
        db,
        "SELECT verb, resource_kind, access, name_operand, resource_name, name_resolution, name_candidates, "
        "qualifier_operand, qualifier, record_clause, record_name, attributes, line_number "
        "FROM cics_resource_data c JOIN file_data f ON c.file_id = f.id "
        "WHERE f.file_path = 'cobol_src/CRECUST.cbl' ORDER BY c.id",
    )
    assert rows == [
        (
            "READ",
            "FILE",
            "read",
            "'CUSTOMER'",
            "CUSTOMER",
            "literal",
            None,
            None,
            None,
            "INTO",
            "OUTPUT-DATA",
            "RIDFLD(CUSTOMER-KY) UPDATE",
            265,
        ),
        (
            "SEND",
            "MAP",
            "write",
            "'BNK1CA'",
            "BNK1CA",
            "literal",
            None,
            "'BNK1CAM'",
            "BNK1CAM",
            "FROM",
            "BNK1CAO",
            "ERASE CURSOR",
            966,
        ),
        ("WRITEQ", "QUEUE", "write", "'JOBS'", "JOBS", "literal", None, None, "TD", "FROM", "JCL-RECORD", None, 517),
        (
            "PUT",
            "CONTAINER",
            "write",
            "WS-PUT-CONT-NAME",
            None,
            "ambiguous",
            "CIPA,CIPB",
            "WS-CHANNEL-NAME",
            "CIPCREDCHANN",
            "FROM",
            "DFHCOMMAREA",
            None,
            557,
        ),
        (
            "RUN",
            "CHANNEL",
            "pass",
            "WS-CHANNEL-NAME",
            "CIPCREDCHANN",
            "move",
            None,
            "WS-RUN-TRANSID",
            None,
            None,
            None,
            None,
            582,
        ),
    ]


def test_a_file_with_no_operations_records_none(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    (count,) = _rows(
        db,
        "SELECT COUNT(*) FROM cics_resource_data c JOIN file_data f ON c.file_id = f.id "
        "WHERE f.file_path = 'COBOL/EMPTY.cbl'",
    )[0]
    assert count == 0


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "mainframe.db"
    for _ in range(2):
        _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM cics_resource_data")[0][0] == 5


def test_an_unchanged_program_keeps_its_operations_through_a_delta_scan(tmp_path):
    """The rehydrator restores every column under the extractor's own payload keys,
    so a full and an incremental scan write identical rows."""
    db = tmp_path / "mainframe.db"
    _record(db)
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cobol_src/CRECUST.cbl"]["cics_resources"] == PROGRAM["cics_resources"]
    assert cache["COBOL/EMPTY.cbl"]["cics_resources"] == []

    before = _rows(db, "SELECT * FROM cics_resource_data ORDER BY id")
    restored = [dict(PROGRAM, cics_resources=cache["cobol_src/CRECUST.cbl"]["cics_resources"]), UNIVERSE[1]]
    _record(db, restored)
    after = _rows(db, "SELECT * FROM cics_resource_data ORDER BY id")
    # Identical apart from the autoincrement ids (row and file_data) redrawn on reinsert.
    assert [r[1:3] + r[4:] for r in after] == [r[1:3] + r[4:] for r in before]


def test_a_baseline_without_the_table_still_rehydrates(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE cics_resource_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cobol_src/CRECUST.cbl"]["cics_resources"] == []


def test_the_audit_report_carries_every_row():
    block = AuditRecorder()._mainframe_facts_block(PROGRAM)
    rows = block["CICS Resources"]
    assert len(rows) == 5
    assert rows[3] == {
        "Verb": "PUT",
        "Kind": "CONTAINER",
        "Access": "write",
        "Operand": "WS-PUT-CONT-NAME",
        "Name": None,
        "Resolution": "ambiguous",
        "Candidates": "CIPA,CIPB",
        "Qualifier Operand": "WS-CHANNEL-NAME",
        "Qualifier": "CIPCREDCHANN",
        "Record Clause": "FROM",
        "Record": "DFHCOMMAREA",
        "Attributes": None,
        "Line": 557,
    }
    # A file with no CICS operations gets no key at all.
    assert "CICS Resources" not in AuditRecorder()._mainframe_facts_block({"path": "x.cbl"})


def test_the_llm_brief_summarises_each_resource():
    lines = LLMRecorder()._mainframe_facts_lines([PROGRAM])
    text = "\n".join(lines)
    assert "`5` EXEC CICS operations naming a resource" in text
    assert (
        "- **CICS operations:** `FILE CUSTOMER (read)`, `MAP BNK1CA (write)`, `QUEUE JOBS (write)`, "
        "`CONTAINER WS-PUT-CONT-NAME? (write)`, `CHANNEL CIPCREDCHANN (pass)`"
    ) in lines
    assert LLMRecorder()._mainframe_facts_lines([{"path": "x.cbl", "cics_resources": []}]) == []
