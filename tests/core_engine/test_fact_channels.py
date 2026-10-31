"""
#3383: the fact-channel registry (gitgalaxy/core/fact_channels.py).

The persist (record_keeper) and restore (state_rehydrator) seams iterate CHANNELS, so
these pin what a registry entry must satisfy for both to work, for every entry:
  1. table and name are unique, and the columns exist in the table the recorder creates;
  2. the restore query selects the file path as `_fp` and binds (repo_name, commit_hash);
  3. the schema (ddl / extra_columns / indexes) names its own table and columns, and an older table
     missing the healed columns gains them without losing rows;
  4. an item given as the extractor emits it survives record -> rehydrate unchanged
     for the channels whose rows the test builds (the rest are covered per channel in
     tests/tools_recorders/).
"""

import dataclasses
import re
import sqlite3
import sys
from pathlib import Path

from gitgalaxy.core.fact_channels import _WEB_SERVICE_FIELDS, CHANNELS, CHANNELS_BY_NAME, create_channel_table
from gitgalaxy.core.state_rehydrator import StateRehydrator, _has_column, _has_table, _restore_child_table
from gitgalaxy.recorders.record_keeper import RecordKeeper, _ensure_columns
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import EngineFile

SESSION = {
    "target": "RegistryRepo",
    "git_audit": {"commit_hash": "reg3383", "latest_commit_date": "2026-10-18T00:00:00Z"},
}


def _record(tmp_path, files):
    db = tmp_path / "m.db"
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db))
    return db


def test_the_registry_has_unique_names_tables_and_payload_keys():
    for attr in ("name", "table", "payload_key"):
        values = [getattr(c, attr) for c in CHANNELS]
        assert len(values) == len(set(values)), attr


def test_every_channel_names_real_columns_and_a_restore_query(tmp_path):
    db = _record(tmp_path, [{"path": "a.cbl", "lang_id": "cobol", "raw_imports": []}])
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        for channel in CHANNELS:
            table_columns = {r["name"] for r in cursor.execute(f"PRAGMA table_info({channel.table})")}
            assert set(channel.columns) <= table_columns, channel.name
            assert len(set(channel.columns)) == len(channel.columns), channel.name
            sql = channel.select_sql(cursor, _has_table, _has_column)
            assert "AS _fp" in sql, channel.name
            # Executes against the current schema and binds exactly (repo_name, commit_hash).
            assert list(cursor.execute(sql, ("RegistryRepo", "reg3383"))) == [], channel.name
    finally:
        conn.close()


def test_a_baseline_without_the_tables_restores_nothing(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_path TEXT)")
    conn.commit()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        for channel in CHANNELS:
            sql = channel.select_sql(cursor, _has_table, _has_column)
            restored = _restore_child_table(cursor, "r", "c", channel.table, sql, channel.to_payload)
            assert restored == {}, channel.name
    finally:
        conn.close()


def test_a_channel_payload_round_trips_through_record_and_rehydrate(tmp_path):
    sql_tables = [
        {
            "table": "ACCOUNT",
            "table_line": 7,
            "colno": 1,
            "name": "ACCOUNT_EYECATCHER",
            "sql_type": "CHAR",
            "length": 4,
            "scale": None,
            "nullable": True,
            "attributes": None,
            "line": 8,
        }
    ]
    csd = [{"resource_type": "FILE", "name": "ACCTFIL", "group": "G1", "dsname": "A.B", "line": 3}]
    files = [{"path": "a.csd", "lang_id": "cobol", "raw_imports": [], "sql_tables": sql_tables, "csd_resources": csd}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["a.csd"]
    assert node["sql_tables"] == sql_tables
    assert [{k: v for k, v in r.items() if v is not None} for r in node["csd_resources"]] == csd
    for channel in CHANNELS:
        assert channel.payload_key in node


def test_a_resolved_channel_inserts_from_the_site_list_and_restores_per_file(tmp_path):
    call_site = CHANNELS_BY_NAME["call_site"]
    assert call_site.resolved and [c.name for c in CHANNELS if c.resolved] == ["call_site", "transaction"]
    files = [{"path": p, "lang_id": "cobol", "raw_imports": []} for p in ("a.cbl", "b.cbl")]
    sites = [
        {
            "src_path": "a.cbl",
            "verb": "CALL",
            "form": "literal",
            "operand": "'B'",
            "target": "B",
            "resolved_path": "b.cbl",
        },
        {
            "src_path": "a.cbl",
            "verb": "LINK",
            "form": "literal",
            "target": "C",
            "line": 9,
            "commarea": "CA",
            "sysid": "S1",
        },
        {"src_path": "gone.cbl", "verb": "CALL", "form": "literal", "target": "Z", "line": 1},
    ]
    db = tmp_path / "m.db"
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), call_sites=sites)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT src_file_id, target, dst_file_id, line_number FROM call_site_data ORDER BY id"
        ).fetchall()
        ids = dict(conn.execute("SELECT file_path, id FROM file_data"))
    finally:
        conn.close()
    assert rows == [(ids["a.cbl"], "B", ids["b.cbl"], 0), (ids["a.cbl"], "C", None, 9)]  # gone.cbl has no file row
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]
    assert [s["target"] for s in node["a.cbl"]["call_sites"]] == ["B", "C"]
    assert node["a.cbl"]["call_sites"][1] == {
        "verb": "LINK",
        "form": "literal",
        "operand": None,
        "target": "C",
        "line": 9,
        "commarea": "CA",
        "sysid": "S1",
    }
    assert node["b.cbl"]["call_sites"] == []


def test_the_transaction_channel_inserts_resolved_and_restores_per_deck(tmp_path):
    files = [{"path": p, "lang_id": "cobol", "raw_imports": []} for p in ("d.csd", "p.cbl")]
    txns = [
        {"src_path": "d.csd", "transid": "ABCD", "program": "P", "group": "G", "resolved_path": "p.cbl", "line": 3},
        {"src_path": "d.csd", "transid": "WXYZ", "program": "EXT", "line": 4},
        {"src_path": "gone.csd", "transid": "NONE", "program": "Q"},
    ]
    db = tmp_path / "m.db"
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), transactions=txns)
    conn = sqlite3.connect(db)
    try:
        ids = dict(conn.execute("SELECT file_path, id FROM file_data"))
        rows = conn.execute("SELECT file_id, transid, group_name, dst_file_id FROM transaction_data ORDER BY id")
        rows = rows.fetchall()
    finally:
        conn.close()
    # gone.csd has no file row; an unresolved program keeps a NULL destination
    assert rows == [(ids["d.csd"], "ABCD", "G", ids["p.cbl"]), (ids["d.csd"], "WXYZ", None, None)]
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]
    assert node["d.csd"]["transaction_defs"] == [
        {"transid": "ABCD", "program": "P", "group": "G", "profile": None, "line": 3},
        {"transid": "WXYZ", "program": "EXT", "group": None, "profile": None, "line": 4},
    ]
    assert node["p.cbl"]["transaction_defs"] == []


def test_a_baseline_without_the_healed_call_site_columns_restores_without_the_keys():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE file_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_path TEXT)"
        )
        cursor.execute(
            "CREATE TABLE call_site_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, src_file_id INTEGER,"
            " verb TEXT, form TEXT, operand TEXT, target TEXT, dst_file_id INTEGER, line_number INTEGER)"
        )
        cursor.execute("INSERT INTO file_data VALUES (1, 'r', 'c', 'a.cbl')")
        cursor.execute("INSERT INTO call_site_data VALUES (1, 'r', 'c', 1, 'CALL', 'literal', NULL, 'B', NULL, 4)")
        call_site = CHANNELS_BY_NAME["call_site"]
        sql = call_site.select_sql(cursor, _has_table, _has_column)
        restored = _restore_child_table(cursor, "r", "c", call_site.table, sql, call_site.to_payload)
        assert restored == {"a.cbl": [{"verb": "CALL", "form": "literal", "operand": None, "target": "B", "line": 4}]}
    finally:
        conn.close()


def test_the_sql_statement_channel_round_trips_a_table_less_and_a_call_statement(tmp_path):
    statements = [
        {
            "ordinal": 1,
            "verb": "SELECT",
            "table": "ACCT",
            "access": "read",
            "host_variables": "A,B",
            "line": 5,
            "statement": "SELECT 1",
        },
        {"ordinal": 2, "verb": "OPEN", "cursor": "C1", "line": 9},
        {"ordinal": 3, "verb": "CALL", "line": 12, "routine": "S.PROC"},
    ]
    files = [{"path": "a.cbl", "lang_id": "cobol", "raw_imports": [], "sql_statements": statements}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["a.cbl"]
    assert [{k: v for k, v in r.items() if v is not None} for r in node["sql_statements"]] == statements
    assert "routine" not in node["sql_statements"][0]  # a non-CALL row restores without the key


def test_a_baseline_without_statement_text_or_routine_restores_them_as_null():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE file_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_path TEXT)"
        )
        cursor.execute(
            "CREATE TABLE sql_statement_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_id INTEGER,"
            " stmt_ordinal INTEGER, verb TEXT, table_name TEXT, access TEXT, cursor_name TEXT, host_variables TEXT,"
            " line_number INTEGER)"
        )
        cursor.execute("INSERT INTO file_data VALUES (1, 'r', 'c', 'a.cbl')")
        cursor.execute(
            "INSERT INTO sql_statement_data VALUES (1, 'r', 'c', 1, 1, 'DELETE', 'T', 'delete', NULL, NULL, 3)"
        )
        channel = CHANNELS_BY_NAME["sql_statement"]
        sql = channel.select_sql(cursor, _has_table, _has_column)
        restored = _restore_child_table(cursor, "r", "c", channel.table, sql, channel.to_payload)
        assert restored["a.cbl"][0]["statement"] is None and "routine" not in restored["a.cbl"][0]
    finally:
        conn.close()


def test_the_cics_task_and_data_move_channels_round_trip_every_payload_key(tmp_path):
    tasks = [
        {
            "verb": "START",
            "target_kind": "transaction",
            "operand": "'TRN1'",
            "name": "TRN1",
            "resolution": "literal",
            "candidates": None,
            "channel_operand": None,
            "channel": None,
            "token": "REQ",
            "record_clause": "FROM",
            "record": "WS-REC",
            "timing": "AFTER 5",
            "attributes": "LENGTH(10)",
            "line": 7,
        }
    ]
    moves = [
        {
            "verb": "MOVE",
            "source": "A",
            "source_kind": "item",
            "target": "B",
            "corresponding": True,
            "source_refmod": True,
            "target_refmod": False,
            "line": 4,
            "source_refmod_text": "1:2",
            "target_refmod_text": None,
        },
        {
            "verb": "INITIALIZE",
            "source": None,
            "source_kind": None,
            "target": "C",
            "corresponding": False,
            "source_refmod": False,
            "target_refmod": False,
            "line": 9,
            "source_refmod_text": None,
            "target_refmod_text": None,
        },
    ]
    files = [{"path": "a.cbl", "lang_id": "cobol", "raw_imports": [], "cics_tasks": tasks, "data_moves": moves}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["a.cbl"]
    assert node["cics_tasks"] == tasks
    assert node["data_moves"] == moves


def test_the_web_service_channel_round_trips_every_payload_key(tmp_path):
    services = [
        {
            "assistant": "DFHLS2WS",
            "direction": "provider",
            "program": "PROG1",
            "uri": "/svc/prog1",
            "request": "REQCPY",
            "response": "RESCPY",
            "interface": "CHANNEL",
            "container": "DFHWS-DATA",
            "binding": "prog1.wsbind",
            "document": "prog1.wsdl",
            "transaction": "TRN1",
            "line": 12,
        },
        {key: None for key in _WEB_SERVICE_FIELDS} | {"line": 0},
    ]
    files = [{"path": "ws.jcl", "lang_id": "jcl", "raw_imports": [], "web_services": services}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["ws.jcl"]
    assert node["web_services"] == services
    conn = sqlite3.connect(db)
    try:
        columns = [r[1] for r in conn.execute("PRAGMA table_info(web_service_data)")]
    finally:
        conn.close()
    assert "transaction_id" in columns and "transaction" not in columns


def test_the_copy_statement_channel_round_trips_every_payload_key(tmp_path):
    copies = [
        {
            "member": "CPYA",
            "library": "LIB1",
            "replacing": '[["==:X:==", "==Y==", "LEADING"]]',
            "section": "WORKING-STORAGE",
            "fd_name": "FD1",
            "after_ordinal": 4,
            "line": 21,
        },
        {
            "member": "CPYB",
            "library": None,
            "replacing": None,
            "section": None,
            "fd_name": None,
            "after_ordinal": None,
            "line": 0,
        },
    ]
    files = [{"path": "p.cbl", "lang_id": "cobol", "raw_imports": [], "section_copies": copies}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["p.cbl"]
    assert node["section_copies"] == copies


def test_the_special_names_and_compiler_options_channels_round_trip_every_payload_key(tmp_path):
    names = [
        {"clause": "CURRENCY", "value": "EUR", "symbol": "E", "line": 7},
        {"clause": "DECIMAL-POINT", "value": "COMMA", "symbol": None, "line": 0},
    ]
    options = [
        {"option": "TRUNC", "value": "BIN", "written": "TRUNC(BIN)", "line": 1},
        {"option": "NUMPROC", "value": None, "written": "NUMPROC", "line": 1},
    ]
    files = [
        {"path": "p.cbl", "lang_id": "cobol", "raw_imports": [], "special_names": names, "compiler_options": options}
    ]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["p.cbl"]
    assert node["special_names"] == names
    assert node["compiler_options"] == options


def test_the_entry_point_dli_call_and_ims_gen_channels_round_trip_every_payload_key(tmp_path):
    entries = [
        {"kind": "PROCEDURE", "entry_name": None, "params": "A,B", "line": 4},
        {"kind": "ENTRY", "entry_name": "ALT", "params": None, "line": 90},
    ]
    dli = [
        {
            "interface": "EXEC",
            "function": "GU",
            "function_operand": None,
            "pcb": "PCB1",
            "io_area": "IO",
            "segments": "S1,S2",
            "ssas": None,
            "where": "K = 1;K = 2",
            "psb": "PSB1",
            "line": 12,
        },
        {
            "interface": "CALL",
            "function": None,
            "function_operand": "FUNC",
            "pcb": "P",
            "io_area": "IO",
            "segments": None,
            "ssas": "SSA1",
            "where": None,
            "psb": None,
            "line": 0,
        },
    ]
    gen = [
        {
            "kind": "FIELD",
            "name": "F",
            "parent": "SEG",
            "owner": "DBD1",
            "dbd_name": None,
            "procopt": None,
            "pcb_type": None,
            "access": "SEQ",
            "bytes": 8,
            "start": 1,
            "psb_name": None,
            "program": None,
            "attributes": None,
            "line": 3,
        },
        {
            "kind": "REGION",
            "name": None,
            "parent": None,
            "owner": None,
            "dbd_name": None,
            "procopt": None,
            "pcb_type": None,
            "access": "BMP",
            "bytes": None,
            "start": None,
            "psb_name": "PSB1",
            "program": "PGM",
            "attributes": "x",
            "line": 0,
        },
    ]
    files = [
        {
            "path": "p.cbl",
            "lang_id": "cobol",
            "raw_imports": [],
            "entry_points": entries,
            "dli_calls": dli,
            "ims_gen": gen,
        }
    ]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["p.cbl"]
    assert node["entry_points"] == entries
    assert node["dli_calls"] == dli
    assert node["ims_gen"] == gen


def test_the_job_submit_mq_call_uow_handler_and_file_control_channels_round_trip_every_payload_key(tmp_path):
    submits = [
        {"kind": "EXEC", "step": "S1", "name": None, "target_kind": "PGM", "target": "PGMA", "line": 7},
        {"kind": "JOB", "step": None, "name": "JOBA", "target_kind": None, "target": None, "line": 0},
    ]
    mq = [
        {
            "verb": "MQOPEN",
            "direction": "put",
            "operand": "Q-NAME",
            "queue": "Q.ONE",
            "resolution": "literal",
            "candidates": None,
            "handle": "H1",
            "open_line": None,
            "options": "MQOO-OUTPUT",
            "line": 10,
        },
        {
            "verb": "MQPUT",
            "direction": None,
            "operand": None,
            "queue": None,
            "resolution": "ambiguous",
            "candidates": "A,B",
            "handle": "H1",
            "open_line": 10,
            "options": None,
            "line": 0,
        },
    ]
    uow = [
        {
            "kind": "HANDLE_CONDITION",
            "source": "CICS",
            "verb": "HANDLE CONDITION",
            "condition": "NOTFND",
            "target": "ERR-PARA",
            "target_kind": "LABEL",
            "resp_var": None,
            "attributes": "x",
            "line": 20,
        },
        {
            "kind": "COMMIT",
            "source": "SQL",
            "verb": None,
            "condition": None,
            "target": None,
            "target_kind": None,
            "resp_var": "WS-RESP",
            "attributes": None,
            "line": 0,
        },
    ]
    selects = [
        {
            "select_name": "F1",
            "assign": "DD1",
            "organization": "INDEXED",
            "access_mode": "DYNAMIC",
            "record_key": "K1",
            "alternate_keys": "A1+DUP",
            "relative_key": None,
            "file_status": "FS",
            "fd_copies": "CPY",
            "line": 5,
        },
        {
            "select_name": "F2",
            "assign": None,
            "organization": None,
            "access_mode": None,
            "record_key": None,
            "alternate_keys": None,
            "relative_key": "RK",
            "file_status": None,
            "fd_copies": None,
            "line": 0,
        },
    ]
    files = [
        {
            "path": "p.cbl",
            "lang_id": "cobol",
            "raw_imports": [],
            "job_submits": submits,
            "mq_calls": mq,
            "uow_handlers": uow,
            "file_control": selects,
        }
    ]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["p.cbl"]
    assert node["job_submits"] == submits
    assert node["mq_calls"] == mq
    assert node["uow_handlers"] == uow
    assert node["file_control"] == selects


def test_the_vsam_define_and_job_flow_channels_round_trip_every_payload_key(tmp_path):
    vsam = [
        {
            "kind": "CLUSTER",
            "name": "A.B.KSDS",
            "organization": "INDEXED",
            "key_length": 8,
            "key_offset": 0,
            "record_avg": 80,
            "record_max": 200,
            "related": None,
            "unique_key": None,
            "upgrade": None,
            "step": "DEF1",
            "line": 4,
        },
        {
            "kind": "AIX",
            "name": "A.B.AIX",
            "organization": None,
            "key_length": None,
            "key_offset": None,
            "record_avg": None,
            "record_max": None,
            "related": "A.B.KSDS",
            "unique_key": "UNIQUEKEY",
            "upgrade": "UPGRADE",
            "step": None,
            "line": 0,
        },
    ]
    base = {
        "kind": "STEP",
        "name": None,
        "step_ordinal": 1,
        "step_name": "S1",
        "program": "PGMA",
        "proc": None,
        "cond": "(4,LT)",
        "if_cond": None,
        "in_proc": None,
        "dd_name": None,
        "dsn": None,
        "disp": None,
        "generation": None,
        "line": 3,
    }
    flow = [
        {
            **base,
            "disp_normal": "CATLG",
            "runs": "PGMB",
            "runs_via": "PARM",
            "systsin_member": "MEM",
            "parm": "X",
            "instream": "BODY",
            "lrecl": 80,
            "recfm": "FB",
        },
        {**base, "kind": "JOB", "name": "JOBA", "step_ordinal": None, "step_name": None, "program": None, "line": 0},
    ]
    files = [{"path": "j.jcl", "lang_id": "jcl", "raw_imports": [], "vsam_defines": vsam, "job_flow": flow}]
    db = _record(tmp_path, files)
    node = StateRehydrator(str(db)).load_state("RegistryRepo")["ram_cache"]["j.jcl"]
    assert node["vsam_defines"] == vsam
    assert node["job_flow"] == flow


def test_a_baseline_without_the_healed_job_flow_columns_restores_them_as_absent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE file_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_path TEXT)"
        )
        old = CHANNELS_BY_NAME["job_flow"].ddl
        old = "\n".join(ln for ln in old.split("\n") if not ln.strip().startswith("disp_normal "))
        cursor.execute(old)
        cursor.execute("INSERT INTO file_data VALUES (1, 'r', 'h', 'j.jcl')")
        cursor.execute(
            "INSERT INTO job_flow_data (repo_name, commit_hash, file_id, kind, step_name, line_number) "
            "VALUES ('r', 'h', 1, 'STEP', 'S1', 2)"
        )
        channel = CHANNELS_BY_NAME["job_flow"]
        row = cursor.execute(channel.select_sql(cursor, _has_table, _has_column), ("r", "h")).fetchone()
        payload = channel.to_payload(row)
        assert payload["step_name"] == "S1" and payload["line"] == 2
        assert not {"disp_normal", "runs", "parm", "instream", "lrecl", "recfm"} & payload.keys()
    finally:
        conn.close()


def test_a_baseline_without_the_refmod_texts_restores_them_as_null():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE file_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_path TEXT)"
        )
        cursor.execute(
            "CREATE TABLE data_move_data (id INTEGER PRIMARY KEY, repo_name TEXT, commit_hash TEXT, file_id INTEGER,"
            " verb TEXT, source TEXT, source_kind TEXT, target TEXT, corresponding INTEGER, source_refmod INTEGER,"
            " target_refmod INTEGER, line_number INTEGER)"
        )
        cursor.execute("INSERT INTO file_data VALUES (1, 'r', 'c', 'a.cbl')")
        cursor.execute("INSERT INTO data_move_data VALUES (1, 'r', 'c', 1, 'MOVE', 'A', 'item', 'B', 0, 1, 0, 3)")
        channel = CHANNELS_BY_NAME["data_move"]
        sql = channel.select_sql(cursor, _has_table, _has_column)
        restored = _restore_child_table(cursor, "r", "c", channel.table, sql, channel.to_payload)
        row = restored["a.cbl"][0]
        assert row["source_refmod"] is True and row["source_refmod_text"] is None
    finally:
        conn.close()


_HEALED_ONLY = {
    "sql_statement": ("routine_name",),
    "job_flow": ("runs", "runs_via", "systsin_member", "parm", "instream", "lrecl", "recfm"),
}


def test_every_channel_declares_a_schema_that_names_its_own_table():
    assert set(CHANNELS_BY_NAME) == {c.name for c in CHANNELS}
    for channel in CHANNELS:
        assert f"CREATE TABLE IF NOT EXISTS {channel.table} (" in channel.ddl, channel.name
        assert "file_id INTEGER" in channel.ddl and "ON DELETE CASCADE" in channel.ddl, channel.name
        assert channel.indexes, channel.name
        for statement in channel.indexes:
            assert statement.startswith("CREATE INDEX IF NOT EXISTS") and f" ON {channel.table}(" in statement
        healed = [col.split()[0] for group in channel.extra_columns for col in group]
        healed_only = _HEALED_ONLY.get(
            channel.name, ()
        )  # added by ALTER on a fresh DB too: the stored text is unchanged
        assert all(f"                {name} " in channel.ddl for name in healed if name not in healed_only), (
            channel.name
        )


def test_a_table_created_before_a_healed_column_gains_it_and_keeps_its_rows():
    for channel in CHANNELS:
        if not channel.extra_columns:
            continue
        conn = sqlite3.connect(":memory:")
        try:
            cursor = conn.cursor()
            healed = {col.split()[0] for group in channel.extra_columns for col in group}
            old_ddl = channel.ddl
            for name in healed:
                old_ddl = "\n".join(line for line in old_ddl.split("\n") if not line.strip().startswith(name + " "))
            cursor.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY)")
            cursor.execute(old_ddl)
            cursor.execute(f"INSERT INTO {channel.table} (repo_name) VALUES ('keep')")  # noqa: S608 -- registry literal
            create_channel_table(cursor, channel.name, _ensure_columns)
            columns = {r[1] for r in cursor.execute(f"PRAGMA table_info({channel.table})")}
            assert healed <= columns, channel.name
            assert cursor.execute(f"SELECT repo_name FROM {channel.table}").fetchall() == [("keep",)]  # noqa: S608
        finally:
            conn.close()


# galaxy_ir (#3383): the SCOPE comment and the loader are checked against the registry.
_GALAXY_IR = Path(__file__).resolve().parents[2] / "gitgalaxy" / "tools" / "cobol_to_cobol" / "galaxy_ir.py"

# Tables galaxy_ir loads that have no registry entry yet (custom insert or restore, #3383 remaining
# slices). A table leaves this set when its channel is migrated; a new channel is never added here.
_UNMIGRATED_IR_TABLES: frozenset = frozenset()


def _galaxy_ir_source():
    text = _GALAXY_IR.read_text(encoding="utf-8")
    scope = text.split("\nimport bisect", 1)[0]
    return text, scope


def test_every_channel_names_its_galaxy_ir_field_and_loader():
    text, scope = _galaxy_ir_source()
    ir_fields = {f.name for f in dataclasses.fields(EngineFile)}
    for channel in CHANNELS:
        assert channel.ir_field in ir_fields, channel.name
        assert channel.table in scope, f"{channel.table} missing from the galaxy_ir SCOPE comment"
        assert f'_has_table(cur, "{channel.table}")' in text, f"galaxy_ir does not load {channel.table}"


def test_every_table_galaxy_ir_loads_is_registered_or_listed_unmigrated():
    text, _ = _galaxy_ir_source()
    loaded = set(re.findall(r'_has_table\(cur, "(\w+)"\)', text))
    registered = {c.table for c in CHANNELS}
    assert loaded - registered == _UNMIGRATED_IR_TABLES, "register the channel, or list the legacy table"


# The recipe's channel table (#3383): checked against the registry the same way.
_RECIPE = Path(__file__).resolve().parents[2] / "gitgalaxy" / "core" / "how_to_add_a_fact_channel.md"

# Tables the recipe table names that are not registry channels yet: the unmigrated galaxy_ir tables
# the recipe has a row for, plus wrapper_data (global/resolved, no galaxy_ir loader) and file_data
# (the host of the wrapper_facts column, not a channel). A table leaves this set when migrated.
_UNMIGRATED_RECIPE_TABLES = _UNMIGRATED_IR_TABLES | {
    "wrapper_data",
    "file_data",
}


def _recipe_tables():
    tables = set()
    for line in _RECIPE.read_text(encoding="utf-8").splitlines():
        cells = line.split("|")
        # a table row: channel | issue | extractor | table | IR accessor, between two outer pipes
        if line.startswith("| ") and len(cells) == 7 and cells[2].strip().startswith("#"):
            tables |= set(re.findall(r"`(\w+_data)\b", cells[4]))
    return tables


def test_every_channel_is_in_the_recipe_table():
    tables = _recipe_tables()
    assert tables, "the recipe channel table was not found"
    for channel in CHANNELS:
        assert channel.table in tables, f"{channel.table} has no row in how_to_add_a_fact_channel.md"


def test_every_other_recipe_table_is_listed_unmigrated():
    unregistered = _recipe_tables() - {c.table for c in CHANNELS}
    assert unregistered == _UNMIGRATED_RECIPE_TABLES, "register the channel, or list the legacy table"


# The READMEs (#3383): the recorders README is the DB schema doc and the core README names the registry.
_RECORDERS_README = Path(__file__).resolve().parents[2] / "gitgalaxy" / "recorders" / "README.md"
_CORE_README = Path(__file__).resolve().parents[2] / "gitgalaxy" / "core" / "README.md"


def test_every_channel_table_is_in_the_recorders_readme():
    text = _RECORDERS_README.read_text(encoding="utf-8")
    for channel in CHANNELS:
        assert f"`{channel.table}`" in text, f"{channel.table} is not documented in recorders/README.md"


def test_the_core_readme_points_at_the_registry():
    text = _CORE_README.read_text(encoding="utf-8")
    assert "core/fact_channels.py" in text and "how_to_add_a_fact_channel.md" in text


# The recorders and the differential (#3383): their section tables are checked against the registry.
# A per-file payload key that is deliberately not reported is listed here with its reason.
_NO_AUDIT_SECTION = {"section_copies"}  # reader-applied COPY ... REPLACING, no standalone report rows yet
_NO_LLM_LINE = {"section_copies", "entry_points"}  # the brief carries no bullet for these two


def _per_file_payload_keys():
    return {c.payload_key for c in CHANNELS if not c.resolved}


def test_every_per_file_channel_has_an_audit_section_or_a_listed_reason():
    from gitgalaxy.recorders.audit_recorder import AUDIT_SECTIONS

    reported = {s.key for s in AUDIT_SECTIONS}
    assert _per_file_payload_keys() - reported == _NO_AUDIT_SECTION, "add an AuditSection (or list the reason)"


def test_every_per_file_channel_has_an_llm_line_or_a_listed_reason():
    from gitgalaxy.recorders.llm_recorder import FACT_LINES, FACT_SUMMARIES

    lined = {s.key for s in FACT_LINES}
    assert _per_file_payload_keys() - lined == _NO_LLM_LINE, "add a FactLine (or list the reason)"
    assert {s.key for s in FACT_SUMMARIES} <= _per_file_payload_keys()


def test_every_recorder_section_names_a_registered_payload_key_or_the_call_graph():
    from gitgalaxy.recorders.audit_recorder import AUDIT_SECTIONS
    from gitgalaxy.recorders.llm_recorder import FACT_LINES

    known = {c.payload_key for c in CHANNELS}
    assert {s.key for s in AUDIT_SECTIONS} - known == set()
    assert {s.key for s in FACT_LINES} - known == set()


def test_the_differential_set_channels_and_the_registry_name_each_other():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import refraction_differential as rd

    compared = [c.differential for c in CHANNELS if c.differential]
    assert len(compared) == len(set(compared)), "two channels claim one SetChannel"
    assert set(compared) == {s.language for s in rd.SET_CHANNELS}, "declare `differential=` on the channel"
