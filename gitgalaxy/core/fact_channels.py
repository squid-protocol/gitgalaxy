# ==============================================================================
# GitGalaxy Core: fact-channel registry (#3383)
#
# PURPOSE:
# A per-file fact channel (a child table that rides on each file's own payload
# list) is declared ONCE here: its table, payload key, insert columns and row
# builder, and its delta-scan restore query and payload mapper. The two shared
# seams -- record_keeper (insert) and state_rehydrator (restore) -- iterate
# CHANNELS, so a new channel PR adds one entry here instead of editing both.
# See gitgalaxy/core/how_to_add_a_fact_channel.md.
#
# SCOPE AND NON-SCOPE:
#   - Persist, restore and schema (DDL, _ensure_columns heals, indexes), plus the
#     galaxy_ir `ir_field` that test_fact_channels.py checks against galaxy_ir's SCOPE
#     comment and loader (checked, not generated). The recipe channel table and
#     custom-insert channels are not registry-driven yet (#3383 remaining slices).
#   - A resolved channel (call_site_data, `resolved=True`) is inserted from the engine's repo-wide
#     list by record_keeper's _insert_resolved_channel; its schema and restore live here too
#     (transaction_data is the other one).
#   - Channels with a custom insert or restore (the later per-file channels) are not migrated yet.
#   - Order of CHANNELS is the insert order; each table is independent, so it
#     does not change any row.
#   - Data only: no import of the recorder or the rehydrator (they import this).
# ==============================================================================
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FactChannel:
    """One per-file fact channel.

    `columns` names the table columns AFTER the three standard ones (repo_name,
    commit_hash, file_id); `to_row(item)` builds them from one payload item.
    `restore_select` is the baseline query (aliasing the file path AS `_fp` and
    every other column to the extractor's payload key), or a callable
    `(cursor, has_table, has_column) -> str` when it depends on which columns
    the baseline DB has. `to_payload(row)` maps a restored row back to the item.
    """

    name: str
    table: str
    payload_key: str
    columns: tuple
    to_row: Callable[..., tuple]
    restore_select: "str | Callable[[sqlite3.Cursor, Callable, Callable], str]"
    to_payload: Callable[[Any], dict]
    # Schema: the CREATE TABLE text, the `_ensure_columns` groups that heal an older
    # table (one ALTER group per tuple, in order), and the CREATE INDEX statements.
    ddl: str = ""
    extra_columns: tuple = ()
    indexes: tuple = ()
    # galaxy_ir reader (#3383): the `EngineFile` field its loader fills from this table. Checked
    # against the real dataclass and the loader's `_has_table` guard by test_fact_channels.py.
    ir_field: str = ""
    # A resolved channel (#3383) is inserted from the engine's repo-wide list, not a per-file
    # payload: `to_row(site, path_to_file_id)` also fills the resolved destination, and the
    # source column is `src_column`. Restore reads it per file like the others (destinations
    # are re-resolved every scan).
    resolved: bool = False
    # The column holding the owning file's id: `file_id` for a per-file channel, but a resolved
    # channel names its own (`src_file_id` on call_site_data, `file_id` on transaction_data).
    src_column: str = "file_id"

    def select_sql(self, cursor: sqlite3.Cursor, has_table: Callable, has_column: Callable) -> str:
        if callable(self.restore_select):
            return self.restore_select(cursor, has_table, has_column)
        return self.restore_select


def create_channel_table(cursor: sqlite3.Cursor, name: str, ensure_columns: Callable) -> None:
    """Create the named channel's table, heal an older one, and add its indexes.

    Statement order matches the hand-written blocks it replaced (table, column
    heals, indexes), so sqlite_master is identical. `ensure_columns` is injected
    (record_keeper's `_ensure_columns`) because this module cannot import it.
    """
    channel = CHANNELS_BY_NAME[name]
    cursor.execute(channel.ddl)
    for group in channel.extra_columns:
        ensure_columns(cursor, channel.table, list(group))
    for statement in channel.indexes:
        cursor.execute(statement)


# DDL per channel. Whitespace inside each string is part of the schema text SQLite stores
# (sqlite_master.sql), so it is kept exactly as the recorder wrote it.

# #3345: a JCL DSN with its symbolic parameters (SET / PROC defaults /
# EXEC overrides) resolved where the file alone determines it. `dsn` stays
# the DSN as written; `dsn_resolved` is NULL unless every symbol resolved,
# and `dsn_resolution` says how (literal / resolved / proc_default /
# ambiguous / unresolved -- see mainframe_boundary._jcl_resolve_datasets).
# Both NULL on a COBOL row. Healed onto a table created before #3345.
# #3348: a COBOL row's OPEN sites, a JSON list of [mode, line] in line order, so
# the refractor can drop the OPENs in dead paragraphs. NULL on a JCL row.

_DATASET_DDL = """
            CREATE TABLE IF NOT EXISTS dataset_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                step_name TEXT,
                internal_name TEXT,
                assign_name TEXT,
                dd_name TEXT,
                access_modes TEXT,
                dsn TEXT,
                line_number INTEGER,
                dsn_resolved TEXT,
                dsn_resolution TEXT,
                open_sites TEXT,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """

# #3250: heal a record_data table created before `attributes` existed.
# #3355: `copy_members` -- the COPY member(s) that expand right after this
# entry (`01 DFHCOMMAREA.` + `COPY INQCUST.` -> 'INQCUST'), comma-separated
# in source order; NULL for an entry no COPY follows. Only the position is
# recorded: expanding the member is the reader's job (galaxy_ir), so a
# COMMAREA record and a callee's DFHCOMMAREA can be compared field by field.
# #3694: `sign_separate` -- 1 when a COBOL item codes SIGN [TRAILING] SEPARATE (its sign
# takes a byte of its own, after the digits), 2 for SIGN LEADING SEPARATE (before them),
# NULL otherwise; widths are the reader's job (galaxy_ir).
# #4265: `copy_libraries` -- the library-name each `copy_members` COPY names (`COPY X IN LIB`),
# comma-separated in the same order, "" for an unqualified COPY; NULL when none names one.
# #4265: `copy_replacing` -- each `copy_members` COPY's REPLACING operands, a JSON list in the same
# order: null for a COPY that replaces nothing, else [[from, to(, LEADING|TRAILING)], ...] with
# pseudo-text as written minus its `==` delimiters. NULL when no COPY on the entry replaces
# anything. The copybook keeps its own (tagged) names; the reader applies the REPLACING.
# #4266: `sync` -- 'SYNC' / 'SYNC LEFT' / 'SYNC RIGHT' when a COBOL item codes SYNCHRONIZED (slack
# bytes before it are the reader's job, galaxy_ir); `justified` / `blank_when_zero` -- 1 when it codes
# JUSTIFIED / BLANK WHEN ZERO; `renames` -- a 66 entry's `A [THRU B]` (qualifiers as `X OF Y`).
# All NULL otherwise.

_RECORD_DDL = """
            CREATE TABLE IF NOT EXISTS record_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                section TEXT,
                fd_name TEXT,
                ordinal INTEGER,
                parent_ordinal INTEGER,
                level_number INTEGER,
                item_name TEXT,
                pic TEXT,
                usage TEXT,
                occurs_min INTEGER,
                occurs_max INTEGER,
                occurs_depending_on TEXT,
                redefines TEXT,
                value_literal TEXT,
                line_number INTEGER,
                attributes TEXT,
                copy_members TEXT,
                sign_separate INTEGER,
                copy_libraries TEXT,
                copy_replacing TEXT,
                sync TEXT,
                justified INTEGER,
                blank_when_zero INTEGER,
                renames TEXT,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


_SCREEN_FIELD_DDL = """
            CREATE TABLE IF NOT EXISTS screen_field_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                kind TEXT,
                ordinal INTEGER,
                parent_ordinal INTEGER,
                field_name TEXT,
                pos_line INTEGER,
                pos_column INTEGER,
                length INTEGER,
                attrb TEXT,
                picin TEXT,
                picout TEXT,
                initial_value TEXT,
                occurs INTEGER,
                attributes TEXT,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


_CICS_RESOURCE_DDL = """
            CREATE TABLE IF NOT EXISTS cics_resource_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                verb TEXT,
                resource_kind TEXT,
                access TEXT,
                name_operand TEXT,
                resource_name TEXT,
                name_resolution TEXT,
                name_candidates TEXT,
                qualifier_operand TEXT,
                qualifier TEXT,
                record_clause TEXT,
                record_name TEXT,
                attributes TEXT,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """

# #5120: provenance -- CSD or an assembled macro table (DFHFCT ...). A
# pre-#5120 database gets the columns healed in; its rows read as CSD.

_CSD_RESOURCE_DDL = """
            CREATE TABLE IF NOT EXISTS csd_resource_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                resource_type TEXT,
                resource_name TEXT,
                group_name TEXT,
                dsname TEXT,
                ddname TEXT,
                record_format TEXT,
                key_length INTEGER,
                record_size INTEGER,
                queue_type TEXT,
                plan TEXT,
                db2_entry TEXT,
                transid TEXT,
                program TEXT,
                attributes TEXT,
                line_number INTEGER,
                source TEXT,
                macro_table TEXT,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


_SQL_TABLE_DDL = """
            CREATE TABLE IF NOT EXISTS sql_table_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                table_name TEXT,
                table_line INTEGER,
                colno INTEGER,
                column_name TEXT,
                sql_type TEXT,
                length INTEGER,
                scale INTEGER,
                nullable INTEGER,
                attributes TEXT,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


_SQL_STATEMENT_DDL = """
            CREATE TABLE IF NOT EXISTS sql_statement_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                stmt_ordinal INTEGER,
                verb TEXT,
                table_name TEXT,
                access TEXT,
                cursor_name TEXT,
                host_variables TEXT,
                line_number INTEGER,
                statement_text TEXT,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


# #3449: CICS task control (RUN/START/FETCH/RETRIEVE/DELAY/ENQ ...), per-file.
_CICS_TASK_DDL = """
            CREATE TABLE IF NOT EXISTS cics_task_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                verb TEXT,
                target_kind TEXT,
                target_operand TEXT,
                target_name TEXT,
                target_resolution TEXT,
                target_candidates TEXT,
                channel_operand TEXT,
                channel_name TEXT,
                token TEXT,
                record_clause TEXT,
                record_name TEXT,
                timing TEXT,
                attributes TEXT,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


# #3496: web_service_data's payload keys, in column order (`transaction` is stored as transaction_id).
_WEB_SERVICE_FIELDS = (
    "assistant",
    "direction",
    "program",
    "uri",
    "request",
    "response",
    "interface",
    "container",
    "binding",
    "document",
    "transaction",
)


# #3496: CICS web / API services from the web-services assistant JCL, per-file.
_WEB_SERVICE_DDL = """
            CREATE TABLE IF NOT EXISTS web_service_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                assistant TEXT,
                direction TEXT,
                program TEXT,
                uri TEXT,
                request TEXT,
                response TEXT,
                interface TEXT,
                container TEXT,
                binding TEXT,
                document TEXT,
                transaction_id TEXT,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


# #4457: the COPY ... REPLACING statements no record_data entry carries (a COPY after a section header / FD,
# or before a section's first entry): one row per statement, `replacing` the JSON [[from, to(, LEADING|TRAILING)], ...]
# as in record_data.copy_replacing, `after_ordinal` the record_data ordinal of the entry above it (NULL when none).
_COPY_STATEMENT_DDL = """
            CREATE TABLE IF NOT EXISTS copy_statement_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                member TEXT,
                library TEXT,
                replacing TEXT,
                section TEXT,
                fd_name TEXT,
                after_ordinal INTEGER,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


# #3452: field-level data movement, per-file.
_DATA_MOVE_DDL = """
            CREATE TABLE IF NOT EXISTS data_move_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                verb TEXT,
                source TEXT,
                source_kind TEXT,
                target TEXT,
                corresponding INTEGER,
                source_refmod INTEGER,
                target_refmod INTEGER,
                line_number INTEGER,
                source_refmod_text TEXT,
                target_refmod_text TEXT,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


# #3200: one row per mainframe INVOCATION SITE -- COBOL `CALL`, CICS
# `LINK`/`XCTL PROGRAM(...)`, JCL `EXEC PGM=`. edge_data carries the
# resolved program-to-program edges aggregated from these, but it
# structurally cannot carry the rest: its src/dst are file_data FKs, and
# the majority of real call sites do not resolve to a file in the
# repository at all. `CALL 'CEEGMT'` is a Language Environment service,
# `EXEC PGM=IEFBR14` is a system utility, and a `CALL WS-PGM` whose
# VALUE clause lives in a copybook has no readable target name. Those
# were #3200's "unresolved targets are recorded nowhere"; they are rows
# here, with the level of failure distinguishable:
#   target IS NULL             -- the name itself could not be read
#   target NOT NULL, dst NULL  -- named, but not a program in this repo
#   dst_file_id NOT NULL       -- resolved; also an edge_data row
# `form` ('literal' | 'identifier' | 'unknown') keeps the architectural
# distinction the old pipeline's `unresolved_calls` was really about: a
# literal CALL is a static, link-edited dependency, an identifier CALL
# is dynamic dispatch that a compile-time DAG cannot see.
# No FK to repo_data, for the same cascade-delete reason as edge_data.
# #3355: the COMMAREA contract of a CICS LINK/XCTL/RETURN TRANSID site --
# the record it passes (`COMMAREA(x)`) and its `LENGTH(...)` /
# `DATALENGTH(...)` operands, each as written (whitespace-collapsed,
# upper-cased). NULL when the site carries no such operand (every CALL and
# EXEC PGM row). Per-file, so restored on delta scans like `operand`.
# Joining x to the callee's LINKAGE DFHCOMMAREA is galaxy_ir's job
# (GalaxyIR.commarea_contracts). Healed onto a table created before #3355.
# #3454: a batch CALL's USING list (call_using.py), comma-joined by position,
# NULL for a CALL without USING and every non-CALL row. Paired with the
# callee's entry_point_data params by GalaxyIR.call_contracts.
# #3494: a CICS LINK / START's SYSID(...) as written (the remote region it
# ships to), NULL otherwise. Joined with the CSD's REMOTESYSTEM definitions
# by GalaxyIR.remote_calls.

_CALL_SITE_DDL = """
            CREATE TABLE IF NOT EXISTS call_site_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                src_file_id INTEGER,
                verb TEXT,
                form TEXT,
                operand TEXT,
                target TEXT,
                dst_file_id INTEGER,
                line_number INTEGER,
                commarea TEXT,
                commarea_length TEXT,
                commarea_datalength TEXT,
                using_args TEXT,
                sysid TEXT,
                FOREIGN KEY(src_file_id) REFERENCES file_data(id) ON DELETE CASCADE,
                FOREIGN KEY(dst_file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
"""

# #3211-followup: the CICS transaction map -- which 4-char transaction id a
# user submits and which program CICS routes it to. Extracted from the CSD
# `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` records (a PROGRAM's
# `TRANSID(...)` is the remote-DPL mirror, not a route, #4503), then resolved to the program's file
# by invocation_resolver.resolve_transactions.
#   file_id     -- the .csd/JCL deck the definition lives in
#   transid     -- the transaction id (like dataset_data.dd_name, a name,
#                  not a file)
#   program     -- the PROGRAM-ID it routes to, as written
#   dst_file_id -- the file declaring that PROGRAM-ID, or NULL for a
#                  program not in this repository
# Like dataset_data this is deliberately NOT an edge_data kind: a
# transaction id is not a file, so it cannot be a file_data FK. The COBOL
# in-source routing (EXEC CICS RETURN/START/RUN TRANSID) rides in
# call_site_data; galaxy_ir.transaction_map joins the two.

_TRANSACTION_DDL = """
            CREATE TABLE IF NOT EXISTS transaction_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_id INTEGER,
                transid TEXT,
                program TEXT,
                group_name TEXT,
                profile TEXT,
                dst_file_id INTEGER,
                line_number INTEGER,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE,
                FOREIGN KEY(dst_file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """


def _dataset_select(cursor, has_table, has_column):
    # #3345: the resolved-DSN pair is per-file (one JCL file determines
    # it), so it is restored like the raw DSN. A baseline written
    # before #3345 lacks the columns; its rows come back without the
    # keys, exactly the shape the extractor gives a COBOL row.
    resolved_cols = (
        "ds.dsn_resolved, ds.dsn_resolution"
        if has_table(cursor, "dataset_data") and has_column(cursor, "dataset_data", "dsn_resolution")
        else "NULL AS dsn_resolved, NULL AS dsn_resolution"
    )
    # #3348: a COBOL row's OPEN sites; absent on a baseline written before them.
    if has_table(cursor, "dataset_data") and has_column(cursor, "dataset_data", "open_sites"):
        resolved_cols += ", ds.open_sites"
    else:
        resolved_cols += ", NULL AS open_sites"
    return (
        "SELECT fd.file_path AS _fp, ds.step_name, ds.internal_name, ds.assign_name, "  # noqa: S608 -- resolved_cols is one of two literals; values are bound
        "ds.dd_name, ds.access_modes AS modes, ds.dsn, ds.line_number AS line, "
        f"{resolved_cols} "
        "FROM dataset_data ds JOIN file_data fd ON ds.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ds.id"
    )


def _record_select(cursor, has_table, has_column):
    # Aliased to the extractor's own payload key names (level_number ->
    # level, item_name -> name, value_literal -> value). `attributes`
    # (#3250, PL/I) is NULL on a baseline written before it existed.
    attributes_col = (
        "rd.attributes"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", "attributes")
        else "NULL"
    )
    # #3355: `copy_members` is per-file (the entry's own window); NULL on
    # a baseline written before it existed, and then left off the payload
    # exactly as the extractor leaves it off an entry no COPY follows.
    copy_col = (
        "rd.copy_members"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", "copy_members")
        else "NULL"
    )
    # #3694: `sign_separate` likewise -- NULL before the column existed, and
    # left off the payload exactly as the extractor leaves it off.
    sign_col = (
        "rd.sign_separate"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", "sign_separate")
        else "NULL"
    )
    # #4265: `copy_libraries` likewise.
    lib_col = (
        "rd.copy_libraries"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", "copy_libraries")
        else "NULL"
    )
    repl_col = (
        "rd.copy_replacing"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", "copy_replacing")
        else "NULL"
    )
    # #4266: SYNC / JUSTIFIED / BLANK WHEN ZERO / RENAMES likewise.
    layout_cols = ", ".join(
        f"rd.{c} AS {c}"
        if has_table(cursor, "record_data") and has_column(cursor, "record_data", c)
        else f"NULL AS {c}"
        for c in ("sync", "justified", "blank_when_zero", "renames")
    )
    return (
        "SELECT fd.file_path AS _fp, rd.section, rd.fd_name, rd.ordinal, rd.parent_ordinal, "  # noqa: S608 -- attributes_col is one of two literals; values are bound
        "rd.level_number AS level, rd.item_name AS name, rd.pic, rd.usage, rd.occurs_min, "
        "rd.occurs_max, rd.occurs_depending_on, rd.redefines, rd.value_literal AS value, "
        f"rd.line_number AS line, {attributes_col} AS attributes, {copy_col} AS copy_members, "
        f"{sign_col} AS sign_separate, {lib_col} AS copy_libraries, {repl_col} AS copy_replacing, "
        f"{layout_cols} "
        "FROM record_data rd JOIN file_data fd ON rd.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY rd.file_id, rd.ordinal"
    )


def _csd_resource_select(cursor, _has_table, has_column):
    return (
        "SELECT fd.file_path AS _fp, cr.resource_type, cr.resource_name AS name, "
        'cr.group_name AS "group", cr.dsname, cr.ddname, cr.record_format, cr.key_length, '
        "cr.record_size, cr.queue_type, cr.plan, cr.db2_entry, cr.transid, cr.program, "
        "cr.attributes, cr.line_number AS line, "
        # #5120: a pre-#5120 baseline has no provenance columns; its rows are CSD.
        + (
            "cr.source, cr.macro_table "
            if has_column(cursor, "csd_resource_data", "source")
            else "NULL AS source, NULL AS macro_table "
        )
        + "FROM csd_resource_data cr JOIN file_data fd ON cr.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY cr.id"
    )


def _call_site_select(cursor, has_table, has_column):
    # #3355: the COMMAREA contract operands are per-file (the site's own EXEC block), so they are
    # restored like `operand`. A baseline written before #3355 lacks the columns; its rows come
    # back without the keys, the shape the extractor gives a site with no COMMAREA -- so a
    # restored row is identical to a re-extracted one. `resolved_path` / `dst_file_id` are NOT
    # restored: resolution is repo-wide and redone every scan.
    def col(column, nulls):
        if has_table(cursor, "call_site_data") and has_column(cursor, "call_site_data", column):
            return ", ".join(f"cs.{c}" for c in nulls)
        return ", ".join(f"NULL AS {c}" for c in nulls)

    commarea_cols = col("commarea", ("commarea", "commarea_length", "commarea_datalength"))
    # #3454 / #3494: the USING list and SYSID, restored the same way.
    using_col = col("using_args", ("using_args",))
    sysid_col = col("sysid", ("sysid",))
    return (
        "SELECT fd.file_path AS _fp, cs.verb, cs.form, cs.operand, cs.target, cs.line_number AS line, "  # noqa: S608 -- the column lists are literals; values are bound
        f"{commarea_cols}, {using_col}, {sysid_col} "
        "FROM call_site_data cs JOIN file_data fd ON cs.src_file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY cs.id"
    )


def _sql_statement_select(cursor, has_table, has_column):
    # #3618 / #5736: a pre-#3618 baseline has no `statement_text`, a pre-#5736 one no `routine_name`;
    # their rows come back with NULL, the shape a re-extracted row has without them.
    def col(column, alias):
        if has_table(cursor, "sql_statement_data") and has_column(cursor, "sql_statement_data", column):
            return f"ss.{column} AS {alias}"
        return f"NULL AS {alias}"

    return (
        'SELECT fd.file_path AS _fp, ss.stmt_ordinal AS ordinal, ss.verb, ss.table_name AS "table", '  # noqa: S608 -- the column aliases are literals; values are bound
        f'ss.access, ss.cursor_name AS "cursor", ss.host_variables, ss.line_number AS line, '
        f"{col('statement_text', 'statement')}, {col('routine_name', 'routine')} "
        "FROM sql_statement_data ss JOIN file_data fd ON ss.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ss.id"
    )


def _data_move_select(cursor, has_table, has_column):
    # #3655: a pre-#3655 baseline has no refmod texts; its rows come back with NULL.
    if has_table(cursor, "data_move_data") and has_column(cursor, "data_move_data", "source_refmod_text"):
        refmod_cols = "dm.source_refmod_text, dm.target_refmod_text"
    else:
        refmod_cols = "NULL AS source_refmod_text, NULL AS target_refmod_text"
    return (
        "SELECT fd.file_path AS _fp, dm.verb, dm.source, dm.source_kind, dm.target, dm.corresponding, "  # noqa: S608 -- refmod_cols is one of two literals
        f'dm.source_refmod, dm.target_refmod, dm.line_number AS "line", {refmod_cols} '
        "FROM data_move_data dm JOIN file_data fd ON dm.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY dm.id"
    )


def _transaction_select(_cursor, _has_table, _has_column):
    # #3211-followup: restored per deck so an unchanged .csd/JCL keeps its transactions through a
    # delta scan. `group_name` is aliased to the extractor's `group` payload key; `resolved_path` /
    # `dst_file_id` are NOT restored (resolution is repo-wide and redone every scan).
    return (
        "SELECT fd.file_path AS _fp, td.transid, td.program, td.group_name AS _group, "
        "td.profile, td.line_number AS line "
        "FROM transaction_data td JOIN file_data fd ON td.file_id = fd.id "
        "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY td.id"
    )


CHANNELS = (
    # #3201: the dataset bindings -- a per-file fact channel (no cross-file
    # resolution, unlike call_site_data above).
    FactChannel(
        name="dataset",
        ir_field="datasets",
        table="dataset_data",
        ddl=_DATASET_DDL,
        extra_columns=(("dsn_resolved TEXT", "dsn_resolution TEXT"), ("open_sites TEXT",)),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_dataset_file_id ON dataset_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_dataset_dd_name ON dataset_data(dd_name);",
            "CREATE INDEX IF NOT EXISTS idx_dataset_snapshot ON dataset_data(repo_name, commit_hash);",
        ),
        payload_key="dataset_bindings",
        columns=(
            "step_name",
            "internal_name",
            "assign_name",
            "dd_name",
            "access_modes",
            "dsn",
            "line_number",
            "dsn_resolved",
            "dsn_resolution",
            "open_sites",
        ),
        to_row=lambda b: (
            b.get("step_name"),
            b.get("internal_name"),
            b.get("assign_name"),
            b.get("dd_name"),
            ",".join(b.get("modes") or []) or None,
            b.get("dsn"),
            int(b.get("line", 0) or 0),
            b.get("dsn_resolved"),  # #3345
            b.get("dsn_resolution"),
            json.dumps(b["open_sites"]) if b.get("open_sites") is not None else None,  # #3348
        ),
        restore_select=_dataset_select,
        to_payload=lambda r: {
            "step_name": r["step_name"],
            "internal_name": r["internal_name"],
            "assign_name": r["assign_name"],
            "dd_name": r["dd_name"],
            "modes": (r["modes"] or "").split(",") if r["modes"] else [],
            "dsn": r["dsn"],
            "line": int(r["line"] or 0),
            **(
                {"dsn_resolved": r["dsn_resolved"], "dsn_resolution": r["dsn_resolution"]}
                if r["dsn_resolution"]
                else {}
            ),
            **({"open_sites": json.loads(r["open_sites"])} if r["open_sites"] is not None else {}),
        },
    ),
    # #3246: the DATA DIVISION item tree + FD record layouts -- the same
    # per-file fact-channel shape as the dataset bindings above.
    FactChannel(
        name="record",
        ir_field="records",
        table="record_data",
        ddl=_RECORD_DDL,
        extra_columns=(
            ("attributes TEXT",),
            ("copy_members TEXT",),
            ("sign_separate INTEGER",),
            ("copy_libraries TEXT",),
            ("copy_replacing TEXT",),
            ("sync TEXT", "justified INTEGER", "blank_when_zero INTEGER", "renames TEXT"),
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_record_file_id ON record_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_record_snapshot ON record_data(repo_name, commit_hash);",
        ),
        payload_key="record_layouts",
        columns=(
            "section",
            "fd_name",
            "ordinal",
            "parent_ordinal",
            "level_number",
            "item_name",
            "pic",
            "usage",
            "occurs_min",
            "occurs_max",
            "occurs_depending_on",
            "redefines",
            "value_literal",
            "line_number",
            "attributes",
            "copy_members",
            "sign_separate",
            "copy_libraries",
            "copy_replacing",
            "sync",
            "justified",
            "blank_when_zero",
            "renames",
        ),
        to_row=lambda it: (
            it.get("section"),
            it.get("fd_name"),
            int(it.get("ordinal", 0) or 0),
            it.get("parent_ordinal"),
            int(it.get("level", 0) or 0),
            it.get("name"),
            it.get("pic"),
            it.get("usage"),
            it.get("occurs_min"),
            it.get("occurs_max"),
            it.get("occurs_depending_on"),
            it.get("redefines"),
            it.get("value"),
            int(it.get("line", 0) or 0),
            it.get("attributes"),
            it.get("copy_members"),  # #3355
            int(it["sign_separate"]) if it.get("sign_separate") else None,  # #3694: 1 trailing, 2 leading
            it.get("copy_libraries"),  # #4265
            it.get("copy_replacing"),  # #4265
            it.get("sync"),  # #4266
            1 if it.get("justified") else None,  # #4266
            1 if it.get("blank_when_zero") else None,  # #4266
            it.get("renames"),  # #4266
        ),
        restore_select=_record_select,
        to_payload=lambda r: {
            "section": r["section"],
            "fd_name": r["fd_name"],
            "ordinal": int(r["ordinal"] or 0),
            "parent_ordinal": r["parent_ordinal"],
            "level": int(r["level"] or 0),
            "name": r["name"],
            "pic": r["pic"],
            "usage": r["usage"],
            "occurs_min": r["occurs_min"],
            "occurs_max": r["occurs_max"],
            "occurs_depending_on": r["occurs_depending_on"],
            "redefines": r["redefines"],
            "value": r["value"],
            "line": int(r["line"] or 0),
            "attributes": r["attributes"],
            **({"copy_members": r["copy_members"]} if r["copy_members"] else {}),
            **({"sign_separate": int(r["sign_separate"])} if r["sign_separate"] else {}),
            **({"copy_libraries": r["copy_libraries"]} if r["copy_libraries"] else {}),
            **({"copy_replacing": r["copy_replacing"]} if r["copy_replacing"] else {}),
            **({"sync": r["sync"]} if r["sync"] else {}),
            **({"justified": True} if r["justified"] else {}),
            **({"blank_when_zero": True} if r["blank_when_zero"] else {}),
            **({"renames": r["renames"]} if r["renames"] else {}),
        },
    ),
    # #3344: DB2 DECLARE TABLE / DCLGEN columns -- per-file, like record_data.
    # #3344: DB2 DECLARE TABLE / DCLGEN columns, aliased back to the
    # extractor's payload keys (table_name -> table, column_name ->
    # name). A pre-#3344 baseline has no table and restores nothing.
    FactChannel(
        name="sql_table",
        ir_field="sql_tables",
        table="sql_table_data",
        ddl=_SQL_TABLE_DDL,
        extra_columns=(),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_sql_table_file_id ON sql_table_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_sql_table_name ON sql_table_data(table_name);",
            "CREATE INDEX IF NOT EXISTS idx_sql_table_snapshot ON sql_table_data(repo_name, commit_hash);",
        ),
        payload_key="sql_tables",
        columns=(
            "table_name",
            "table_line",
            "colno",
            "column_name",
            "sql_type",
            "length",
            "scale",
            "nullable",
            "attributes",
            "line_number",
        ),
        to_row=lambda c: (
            c.get("table"),
            int(c.get("table_line", 0) or 0),
            int(c.get("colno", 0) or 0),
            c.get("name"),
            c.get("sql_type"),
            c.get("length"),
            c.get("scale"),
            1 if c.get("nullable", True) else 0,
            c.get("attributes"),
            int(c.get("line", 0) or 0),
        ),
        restore_select=(
            'SELECT fd.file_path AS _fp, st.table_name AS "table", st.table_line, st.colno, st.column_name AS name, '
            "st.sql_type, st.length, st.scale, st.nullable, st.attributes, st.line_number AS line "
            "FROM sql_table_data st JOIN file_data fd ON st.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY st.id"
        ),
        to_payload=lambda r: {
            "table": r["table"],
            "table_line": int(r["table_line"] or 0),
            "colno": int(r["colno"] or 0),
            "name": r["name"],
            "sql_type": r["sql_type"],
            "length": r["length"],
            "scale": r["scale"],
            "nullable": bool(r["nullable"]),
            "attributes": r["attributes"],
            "line": int(r["line"] or 0),
        },
    ),
    # #3446: embedded SQL statements -- per-file, like sql_table. One row per (statement, table); a
    # statement naming no table (OPEN/FETCH/CLOSE a cursor, COMMIT, CALL) has one row with NULL table_name.
    FactChannel(
        name="sql_statement",
        ir_field="sql_statements",
        table="sql_statement_data",
        ddl=_SQL_STATEMENT_DDL,
        # #3618: the statement text; #5736: the routine a `CALL` names (schema.proc), NULL otherwise.
        extra_columns=(("statement_text TEXT",), ("routine_name TEXT",)),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_sql_statement_file_id ON sql_statement_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_sql_statement_table ON sql_statement_data(table_name);",
            "CREATE INDEX IF NOT EXISTS idx_sql_statement_snapshot ON sql_statement_data(repo_name, commit_hash);",
        ),
        payload_key="sql_statements",
        columns=(
            "stmt_ordinal",
            "verb",
            "table_name",
            "access",
            "cursor_name",
            "host_variables",
            "line_number",
            "statement_text",
            "routine_name",
        ),
        to_row=lambda s: (
            int(s.get("ordinal", 0) or 0),
            s.get("verb"),
            s.get("table"),
            s.get("access"),
            s.get("cursor"),
            s.get("host_variables"),
            int(s.get("line", 0) or 0),
            s.get("statement"),
            s.get("routine"),
        ),
        restore_select=_sql_statement_select,
        to_payload=lambda r: {
            "ordinal": int(r["ordinal"] or 0),
            "verb": r["verb"],
            "table": r["table"],
            "access": r["access"],
            "cursor": r["cursor"],
            "host_variables": r["host_variables"],
            "line": int(r["line"] or 0),
            "statement": r["statement"],
            **({"routine": r["routine"]} if r["routine"] else {}),
        },
    ),
    # #3449: CICS task control -- per-file. A pre-#3449 baseline has no table and restores nothing.
    FactChannel(
        name="cics_task",
        ir_field="cics_tasks",
        table="cics_task_data",
        ddl=_CICS_TASK_DDL,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_cics_task_file_id ON cics_task_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_cics_task_target ON cics_task_data(verb, target_name);",
            "CREATE INDEX IF NOT EXISTS idx_cics_task_snapshot ON cics_task_data(repo_name, commit_hash);",
        ),
        payload_key="cics_tasks",
        columns=(
            "verb",
            "target_kind",
            "target_operand",
            "target_name",
            "target_resolution",
            "target_candidates",
            "channel_operand",
            "channel_name",
            "token",
            "record_clause",
            "record_name",
            "timing",
            "attributes",
            "line_number",
        ),
        to_row=lambda t: (
            t.get("verb"),
            t.get("target_kind"),
            t.get("operand"),
            t.get("name"),
            t.get("resolution"),
            t.get("candidates"),
            t.get("channel_operand"),
            t.get("channel"),
            t.get("token"),
            t.get("record_clause"),
            t.get("record"),
            t.get("timing"),
            t.get("attributes"),
            int(t.get("line", 0) or 0),
        ),
        restore_select=(
            "SELECT fd.file_path AS _fp, ct.verb, ct.target_kind, ct.target_operand AS operand, "
            "ct.target_name AS name, ct.target_resolution AS resolution, ct.target_candidates AS candidates, "
            "ct.channel_operand, ct.channel_name AS channel, ct.token, ct.record_clause, "
            "ct.record_name AS record, ct.timing, ct.attributes, ct.line_number AS line "
            "FROM cics_task_data ct JOIN file_data fd ON ct.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ct.id"
        ),
        to_payload=lambda r: {
            "verb": r["verb"],
            "target_kind": r["target_kind"],
            "operand": r["operand"],
            "name": r["name"],
            "resolution": r["resolution"],
            "candidates": r["candidates"],
            "channel_operand": r["channel_operand"],
            "channel": r["channel"],
            "token": r["token"],
            "record_clause": r["record_clause"],
            "record": r["record"],
            "timing": r["timing"],
            "attributes": r["attributes"],
            "line": int(r["line"] or 0),
        },
    ),
    # #3452: field-level data movement -- per-file. #3655: the refmod texts (healed onto an older table).
    FactChannel(
        name="data_move",
        ir_field="data_moves",
        table="data_move_data",
        ddl=_DATA_MOVE_DDL,
        extra_columns=(("source_refmod_text TEXT", "target_refmod_text TEXT"),),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_data_move_file_id ON data_move_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_data_move_snapshot ON data_move_data(repo_name, commit_hash);",
        ),
        payload_key="data_moves",
        columns=(
            "verb",
            "source",
            "source_kind",
            "target",
            "corresponding",
            "source_refmod",
            "target_refmod",
            "line_number",
            "source_refmod_text",
            "target_refmod_text",
        ),
        to_row=lambda m: (
            m.get("verb"),
            m.get("source"),
            m.get("source_kind"),
            m.get("target"),
            int(bool(m.get("corresponding"))),
            int(bool(m.get("source_refmod"))),
            int(bool(m.get("target_refmod"))),
            int(m.get("line", 0) or 0),
            m.get("source_refmod_text"),
            m.get("target_refmod_text"),
        ),
        restore_select=_data_move_select,
        to_payload=lambda r: {
            "verb": r["verb"],
            "source": r["source"],
            "source_kind": r["source_kind"],
            "target": r["target"],
            "corresponding": bool(r["corresponding"]),
            "source_refmod": bool(r["source_refmod"]),
            "target_refmod": bool(r["target_refmod"]),
            "line": int(r["line"] or 0),
            "source_refmod_text": r["source_refmod_text"],
            "target_refmod_text": r["target_refmod_text"],
        },
    ),
    # #3496: web-services assistant steps -- per-file. `transaction` is stored as transaction_id
    # (TRANSACTION is an SQL keyword). A pre-#3496 baseline has no table and restores nothing.
    FactChannel(
        name="web_service",
        ir_field="web_services",
        table="web_service_data",
        ddl=_WEB_SERVICE_DDL,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_web_service_file_id ON web_service_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_web_service_snapshot ON web_service_data(repo_name, commit_hash);",
        ),
        payload_key="web_services",
        columns=(*_WEB_SERVICE_FIELDS[:-1], "transaction_id", "line_number"),
        to_row=lambda w: (*(w.get(c) for c in _WEB_SERVICE_FIELDS), int(w.get("line", 0) or 0)),
        restore_select=(
            "SELECT fd.file_path AS _fp, ws.assistant, ws.direction, ws.program, ws.uri, ws.request, ws.response, "
            'ws.interface, ws.container, ws.binding, ws.document, ws.transaction_id AS "transaction", '
            'ws.line_number AS "line" '
            "FROM web_service_data ws JOIN file_data fd ON ws.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ws.id"
        ),
        to_payload=lambda r: {
            **{k: r[k] for k in _WEB_SERVICE_FIELDS},
            "line": int(r["line"] or 0),
        },
    ),
    # #4457: section-level COPY ... REPLACING statements -- per-file. A pre-#4457 baseline has no table and
    # restores nothing.
    FactChannel(
        name="copy_statement",
        ir_field="copy_statements",
        table="copy_statement_data",
        ddl=_COPY_STATEMENT_DDL,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_copy_statement_file_id ON copy_statement_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_copy_statement_snapshot ON copy_statement_data(repo_name, commit_hash);",
        ),
        payload_key="section_copies",
        columns=("member", "library", "replacing", "section", "fd_name", "after_ordinal", "line_number"),
        to_row=lambda c: (
            c.get("member"),
            c.get("library"),
            c.get("replacing"),
            c.get("section"),
            c.get("fd_name"),
            c.get("after_ordinal"),
            int(c.get("line", 0) or 0),
        ),
        restore_select=(
            "SELECT fd.file_path AS _fp, cs.member, cs.library, cs.replacing, cs.section, cs.fd_name, "
            'cs.after_ordinal, cs.line_number AS "line" '
            "FROM copy_statement_data cs JOIN file_data fd ON cs.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY cs.id"
        ),
        to_payload=lambda r: {
            "member": r["member"],
            "library": r["library"],
            "replacing": r["replacing"],
            "section": r["section"],
            "fd_name": r["fd_name"],
            "after_ordinal": r["after_ordinal"],
            "line": int(r["line"] or 0),
        },
    ),
    # #3356: CSD resource definitions -- per-file, like sql_table_data.
    # #3356: CSD resource definitions, aliased back to the extractor's
    # payload keys (resource_name -> name, group_name -> group). A
    # pre-#3356 baseline has no table and restores nothing.
    FactChannel(
        name="csd_resource",
        ir_field="csd_resources",
        table="csd_resource_data",
        ddl=_CSD_RESOURCE_DDL,
        extra_columns=(("source TEXT", "macro_table TEXT"),),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_csd_resource_file_id ON csd_resource_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_csd_resource_name ON csd_resource_data(resource_type, resource_name);",
            "CREATE INDEX IF NOT EXISTS idx_csd_resource_snapshot ON csd_resource_data(repo_name, commit_hash);",
        ),
        payload_key="csd_resources",
        columns=(
            "resource_type",
            "resource_name",
            "group_name",
            "dsname",
            "ddname",
            "record_format",
            "key_length",
            "record_size",
            "queue_type",
            "plan",
            "db2_entry",
            "transid",
            "program",
            "attributes",
            "line_number",
            "source",
            "macro_table",
        ),
        to_row=lambda r: (
            r.get("resource_type"),
            r.get("name"),
            r.get("group"),
            r.get("dsname"),
            r.get("ddname"),
            r.get("record_format"),
            r.get("key_length"),
            r.get("record_size"),
            r.get("queue_type"),
            r.get("plan"),
            r.get("db2_entry"),
            r.get("transid"),
            r.get("program"),
            r.get("attributes"),
            int(r.get("line", 0) or 0),
            r.get("source") or "CSD",
            r.get("macro_table"),
        ),
        restore_select=_csd_resource_select,
        to_payload=lambda r: {
            "resource_type": r["resource_type"],
            "name": r["name"],
            "group": r["group"],
            "dsname": r["dsname"],
            "ddname": r["ddname"],
            "record_format": r["record_format"],
            "key_length": r["key_length"],
            "record_size": r["record_size"],
            "queue_type": r["queue_type"],
            "plan": r["plan"],
            "db2_entry": r["db2_entry"],
            "transid": r["transid"],
            "program": r["program"],
            "attributes": r["attributes"],
            "line": int(r["line"] or 0),
            **({"source": r["source"], "macro_table": r["macro_table"]} if r["source"] == "MACRO" else {}),
        },
    ),
    # #3347: BMS screen-field layouts -- the same per-file shape.
    # #3347: BMS screen-field layouts, aliased to the extractor's payload
    # keys (field_name -> name, initial_value -> initial).
    FactChannel(
        name="screen_field",
        ir_field="screen_fields",
        table="screen_field_data",
        ddl=_SCREEN_FIELD_DDL,
        extra_columns=(),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_screen_field_file_id ON screen_field_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_screen_field_snapshot ON screen_field_data(repo_name, commit_hash);",
        ),
        payload_key="screen_fields",
        columns=(
            "kind",
            "ordinal",
            "parent_ordinal",
            "field_name",
            "pos_line",
            "pos_column",
            "length",
            "attrb",
            "picin",
            "picout",
            "initial_value",
            "occurs",
            "attributes",
            "line_number",
        ),
        to_row=lambda sf: (
            sf.get("kind"),
            int(sf.get("ordinal", 0) or 0),
            sf.get("parent_ordinal"),
            sf.get("name"),
            sf.get("pos_line"),
            sf.get("pos_column"),
            sf.get("length"),
            sf.get("attrb"),
            sf.get("picin"),
            sf.get("picout"),
            sf.get("initial"),
            sf.get("occurs"),
            sf.get("attributes"),
            int(sf.get("line", 0) or 0),
        ),
        restore_select=(
            "SELECT fd.file_path AS _fp, sf.kind, sf.ordinal, sf.parent_ordinal, "
            "sf.field_name AS name, sf.pos_line, sf.pos_column, sf.length, sf.attrb, sf.picin, "
            "sf.picout, sf.initial_value AS initial, sf.occurs, sf.attributes, sf.line_number AS line "
            "FROM screen_field_data sf JOIN file_data fd ON sf.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY sf.file_id, sf.ordinal"
        ),
        to_payload=lambda r: {
            "kind": r["kind"],
            "ordinal": int(r["ordinal"] or 0),
            "parent_ordinal": r["parent_ordinal"],
            "name": r["name"],
            "pos_line": r["pos_line"],
            "pos_column": r["pos_column"],
            "length": r["length"],
            "attrb": r["attrb"],
            "picin": r["picin"],
            "picout": r["picout"],
            "initial": r["initial"],
            "occurs": r["occurs"],
            "attributes": r["attributes"],
            "line": int(r["line"] or 0),
        },
    ),
    # #3351-#3354: CICS resource operations -- the same per-file shape.
    # #3351-#3354: CICS resource operations, aliased back to the
    # extractor's payload keys. A pre-channel baseline restores nothing.
    FactChannel(
        name="cics_resource",
        ir_field="cics_resources",
        table="cics_resource_data",
        ddl=_CICS_RESOURCE_DDL,
        extra_columns=(),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_cics_resource_file_id ON cics_resource_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_cics_resource_name ON cics_resource_data(resource_kind, resource_name);",
            "CREATE INDEX IF NOT EXISTS idx_cics_resource_snapshot ON cics_resource_data(repo_name, commit_hash);",
        ),
        payload_key="cics_resources",
        columns=(
            "verb",
            "resource_kind",
            "access",
            "name_operand",
            "resource_name",
            "name_resolution",
            "name_candidates",
            "qualifier_operand",
            "qualifier",
            "record_clause",
            "record_name",
            "attributes",
            "line_number",
        ),
        to_row=lambda op: (
            op.get("verb"),
            op.get("kind"),
            op.get("access"),
            op.get("operand"),
            op.get("name"),
            op.get("resolution"),
            op.get("candidates"),
            op.get("qualifier_operand"),
            op.get("qualifier"),
            op.get("record_clause"),
            op.get("record"),
            op.get("attributes"),
            int(op.get("line", 0) or 0),
        ),
        restore_select=(
            "SELECT fd.file_path AS _fp, cr.verb, cr.resource_kind AS kind, cr.access, "
            "cr.name_operand AS operand, cr.resource_name AS name, cr.name_resolution AS resolution, "
            "cr.name_candidates AS candidates, cr.qualifier_operand, cr.qualifier, cr.record_clause, "
            "cr.record_name AS record, cr.attributes, cr.line_number AS line "
            "FROM cics_resource_data cr JOIN file_data fd ON cr.file_id = fd.id "
            "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY cr.id"
        ),
        to_payload=lambda r: {
            "verb": r["verb"],
            "kind": r["kind"],
            "access": r["access"],
            "operand": r["operand"],
            "name": r["name"],
            "resolution": r["resolution"],
            "candidates": r["candidates"],
            "qualifier_operand": r["qualifier_operand"],
            "qualifier": r["qualifier"],
            "record_clause": r["record_clause"],
            "record": r["record"],
            "attributes": r["attributes"],
            "line": int(r["line"] or 0),
        },
    ),
    # #3200: every mainframe call site, resolved or not -- inserted from the engine's resolved list.
    FactChannel(
        name="call_site",
        ir_field="calls",
        table="call_site_data",
        resolved=True,
        src_column="src_file_id",
        ddl=_CALL_SITE_DDL,
        extra_columns=(
            ("commarea TEXT", "commarea_length TEXT", "commarea_datalength TEXT"),
            ("using_args TEXT",),
            ("sysid TEXT",),
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_call_src_file_id ON call_site_data(src_file_id);",
            "CREATE INDEX IF NOT EXISTS idx_call_dst_file_id ON call_site_data(dst_file_id);",
            "CREATE INDEX IF NOT EXISTS idx_call_target ON call_site_data(target);",
            "CREATE INDEX IF NOT EXISTS idx_call_snapshot ON call_site_data(repo_name, commit_hash);",
        ),
        payload_key="call_sites",
        columns=(
            "verb",
            "form",
            "operand",
            "target",
            "dst_file_id",
            "line_number",
            "commarea",
            "commarea_length",
            "commarea_datalength",
            "using_args",
            "sysid",
        ),
        to_row=lambda site, path_to_file_id: (
            site.get("verb"),
            site.get("form"),
            site.get("operand"),
            site.get("target"),
            path_to_file_id.get(site.get("resolved_path") or ""),
            int(site.get("line", 0) or 0),
            site.get("commarea"),  # #3355
            site.get("commarea_length"),
            site.get("commarea_datalength"),
            site.get("using_args"),  # #3454
            site.get("sysid"),  # #3494
        ),
        restore_select=_call_site_select,
        to_payload=lambda r: {
            "verb": r["verb"],
            "form": r["form"],
            "operand": r["operand"],
            "target": r["target"],
            "line": int(r["line"] or 0),
            **{k: r[k] for k in ("commarea", "commarea_length", "commarea_datalength", "using_args", "sysid") if r[k]},
        },
    ),
    # #3211-followup: the CICS transaction map, resolved cross-file (transid -> program -> the program's
    # file) so it is inserted from the engine's resolved list. A definition whose deck has no file_data
    # row is skipped; a program the repository does not contain keeps dst_file_id NULL.
    FactChannel(
        name="transaction",
        ir_field="transactions",
        table="transaction_data",
        resolved=True,
        ddl=_TRANSACTION_DDL,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_transaction_file_id ON transaction_data(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_transaction_transid ON transaction_data(transid);",
            "CREATE INDEX IF NOT EXISTS idx_transaction_snapshot ON transaction_data(repo_name, commit_hash);",
        ),
        payload_key="transaction_defs",
        columns=("transid", "program", "group_name", "profile", "dst_file_id", "line_number"),
        to_row=lambda txn, path_to_file_id: (
            txn.get("transid"),
            txn.get("program"),
            txn.get("group"),
            txn.get("profile"),
            path_to_file_id.get(txn.get("resolved_path") or ""),
            int(txn.get("line", 0) or 0),
        ),
        restore_select=_transaction_select,
        to_payload=lambda r: {
            "transid": r["transid"],
            "program": r["program"],
            "group": r["_group"],
            "profile": r["profile"],
            "line": int(r["line"] or 0),
        },
    ),
)

CHANNELS_BY_NAME = {channel.name: channel for channel in CHANNELS}

CALL_SITE_CHANNEL = next(c for c in CHANNELS if c.name == "call_site")
TRANSACTION_CHANNEL = next(c for c in CHANNELS if c.name == "transaction")
