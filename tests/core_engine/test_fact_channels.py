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
from pathlib import Path

from gitgalaxy.core.fact_channels import CHANNELS, CHANNELS_BY_NAME, create_channel_table
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


def test_every_channel_declares_a_schema_that_names_its_own_table():
    assert set(CHANNELS_BY_NAME) == {c.name for c in CHANNELS}
    for channel in CHANNELS:
        assert f"CREATE TABLE IF NOT EXISTS {channel.table} (" in channel.ddl, channel.name
        assert "file_id INTEGER" in channel.ddl and "ON DELETE CASCADE" in channel.ddl, channel.name
        assert channel.indexes, channel.name
        for statement in channel.indexes:
            assert statement.startswith("CREATE INDEX IF NOT EXISTS") and f" ON {channel.table}(" in statement
        healed = [col.split()[0] for group in channel.extra_columns for col in group]
        assert all(f"                {name} " in channel.ddl for name in healed), channel.name


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
_UNMIGRATED_IR_TABLES = frozenset(
    {
        "call_site_data",
        "transaction_data",
        "sql_statement_data",
        "web_service_data",
        "copy_statement_data",
        "special_names_data",
        "compiler_options_data",
        "data_move_data",
        "ims_gen_data",
        "dli_call_data",
        "entry_point_data",
        "job_flow_data",
        "file_control_data",
        "vsam_define_data",
        "uow_handler_data",
        "mq_call_data",
        "job_submit_data",
        "cics_task_data",
    }
)


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
_UNMIGRATED_RECIPE_TABLES = (_UNMIGRATED_IR_TABLES - {"transaction_data", "copy_statement_data"}) | {
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
