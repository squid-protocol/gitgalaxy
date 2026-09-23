# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_high_risk_execution
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_high_risk_execution

# galaxyscope:ignore sec_db_hooks, sec_high_risk_execution

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.call_resolver import decode_qualifiers


def _json_list(value: Any) -> list:
    """Decode a persisted JSON-list column (e.g. calls_out_to) back to a list.
    Tolerates already-decoded lists, NULLs and malformed text (-> [])."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        out = json.loads(value)
        return out if isinstance(out, list) else []
    except (ValueError, TypeError):
        return []


def _has_table(cursor: sqlite3.Cursor, name: str) -> bool:
    """Whether the baseline DB carries `name` (#3200).

    A baseline written before a table existed is a normal state to rehydrate
    from, not a failure: the scan simply has no prior value for that channel.
    """
    return cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _has_column(cursor, table: str, column: str) -> bool:
    """Whether `table` carries `column` -- a baseline written before a column was
    added (#3250: record_data.attributes) is restored with that column as NULL."""
    return any(row[1] == column for row in cursor.execute(f"PRAGMA table_info({table})"))


def _restore_child_table(cursor, repo_name, baseline_hash, table, select_sql, to_payload) -> dict:
    """Restore one per-file fact channel's payload for unchanged files (#3200/#3201/#3246).

    Returns `{file_path: [payload_dict, ...]}`; a baseline predating `table` yields
    `{}`. `select_sql` aliases the file path AS `_fp`, aliases every other column to
    the extractor's own payload key names, and takes `(repo_name, baseline_hash)`.
    See `gitgalaxy/core/how_to_add_a_fact_channel.md`.
    """
    by_file: dict[str, list] = {}
    if _has_table(cursor, table):
        for r in cursor.execute(select_sql, (repo_name, baseline_hash)):
            by_file.setdefault(r["_fp"], []).append(to_payload(r))
    return by_file


def _json_import_set(value: Any) -> set:
    """Decode a persisted raw_imports column back to a set. Entries can be import
    strings or (module, alias) tuples that JSON stored as lists; restore the tuples
    (a set needs hashable members, and the resolver distinguishes the two)."""
    return {tuple(x) if isinstance(x, list) else x for x in _json_list(value)}


# galaxyscope:ignore sec_high_risk_execution
class StateRehydrator:
    """
    Restores the GitGalaxy engine's memory state from a previous SQLite audit.

    DEFENSIVE DESIGN: During a 'Delta Scan' (incremental update), it is incredibly
    inefficient to re-parse 10,000 unchanged files just to figure out how 2 modified
    files impact them. This class rehydrates the previous architectural state directly
    into RAM, allowing the engine to instantly execute dependency resolution without
    triggering the CPU-bound structural signature extractors.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def load_state(self, repo_name: str, commit_hash: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Rebuild the RAM dictionary from a baseline commit's state in SQLite.

        `commit_hash` selects the baseline explicitly. When it is None the method
        falls back to the most recent commit by `commit_date` (the legacy
        behavior). #2983: a single master DB can hold MANY commits of one repo in
        arbitrary historical order (the exposure-history program keys file/function
        state by `(repo_name, commit_hash)`). "Latest by commit_date" is only the
        right baseline for a DB that holds one lineage scanned forward — and even
        then commit dates are non-monotonic (rebases, clock skew, imported
        history). A longitudinal walk must therefore pass the explicit parent
        commit; if that commit isn't present we refuse rather than silently
        substituting whichever row has the newest date and producing a nonsense
        `git diff`.
        """
        # PERFORMANCE OPTIMIZATION: Fast disk-check before attempting DB connections
        if not self.db_path.exists():
            print(f"⚠️ No master DB found at {self.db_path}. Cold start required.")
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Resolve the baseline commit hash for this specific repository.
            if commit_hash is None:
                # Legacy default: newest by author date (see the non-monotonicity
                # caveat in the docstring — safe only for a single forward lineage).
                cursor.execute(
                    """
                    SELECT commit_hash FROM repo_data
                    WHERE repo_name = ?
                    ORDER BY commit_date DESC LIMIT 1
                """,
                    (repo_name,),
                )
                row = cursor.fetchone()
                if not row:
                    print(f"⚠️ No scan history found for '{repo_name}'. Full baseline required.")
                    conn.close()
                    return None
                baseline_hash = row["commit_hash"]
            else:
                # Explicit baseline: it must actually be recorded for this repo.
                # Never guess a different commit — that is exactly the silent
                # nonsense-delta #2983 exists to prevent.
                cursor.execute(
                    """
                    SELECT commit_hash FROM repo_data
                    WHERE repo_name = ? AND commit_hash = ? LIMIT 1
                """,
                    (repo_name, commit_hash),
                )
                if not cursor.fetchone():
                    print(
                        f"⚠️ Requested baseline commit '{commit_hash}' not found for "
                        f"'{repo_name}' in {self.db_path}. Refusing to substitute a "
                        "different commit — cold start / full baseline required."
                    )
                    conn.close()
                    return None
                baseline_hash = commit_hash

            print(f"🔄 Rehydrating RAM from commit: {baseline_hash}")

            # 2. Extract the structural metrics for the baseline commit
            cursor.execute(
                """
                SELECT * FROM file_data
                WHERE repo_name = ? AND commit_hash = ?
            """,
                (repo_name, baseline_hash),
            )

            file_rows = cursor.fetchall()

            # #3220: Reconstruct the FULL risk_vector / hit_vector from the persisted
            # columns by INVERTING the recorder's own write. RecordKeeper writes
            # risk_vector -> risk_<name> columns (RISK_SCHEMA order) and hit_vector ->
            # SHORT_KEY_MAP-renamed columns (SIGNAL_SCHEMA order); we read those same
            # maps from the recorder so the inversion can never drift from the write.
            # Without this, rehydrated (unchanged) files came back with hit_vector=[]
            # and no risk_vector, so they could not be re-persisted or re-audited like
            # a full scan -- the root of the incremental/full divergence.
            risk_cols: list[str] = []
            hit_cols: list[str] = []
            signal_names: list[str] = []
            try:
                from gitgalaxy.recorders.record_keeper import RecordKeeper

                _rk = RecordKeeper()
                signal_names = list(_rk.SIGNAL_SCHEMA)
                risk_cols = [f"risk_{r.replace('-', '_')}" for r in _rk.RISK_SCHEMA]
                hit_cols = [_rk.SHORT_KEY_MAP.get(h, h) for h in _rk.SIGNAL_SCHEMA]
            except Exception as schema_err:
                # Never let vector reconstruction take down rehydration: fall back to
                # the pre-#3220 lossy behaviour (empty vectors) rather than a cold start.
                print(f"⚠️ Vector schema unavailable, rehydrating without risk/hit vectors: {schema_err}")

            # 3. Rebuild the orchestrator's `ram_cache` dictionary format
            ram_state = {}
            for f in file_rows:
                rel_path = f["file_path"]
                row_keys = f.keys()

                # #3220: full-fidelity vectors (see the schema inversion above).
                risk_vector = [float(f[c]) if c in row_keys and f[c] is not None else 0.0 for c in risk_cols]
                hit_vector = [int(f[c]) if c in row_keys and f[c] is not None else 0 for c in hit_cols]
                # #3220: `equations` is the raw signal-count dict the SignalProcessor
                # consumes (galaxyscope passes meta["equations"] as calculate_risk_vector's
                # raw_signals). It is the exact inverse of hit_vector, so reconstruct it
                # here -- without it, _calculate_risk_exposures recomputes every unchanged
                # file's risk vector from an empty signal dict (all-zero drift).
                equations = dict(zip(signal_names, hit_vector))
                # #3220: the proximity-mitigation tally re-weights cognitive_load /
                # safety_score / state_flux in the score layer (_proximity_tally ->
                # _weighted). Restore it from the persisted JSON so the rehydrated file's
                # recomputed risk vector matches a full scan exactly.
                mitigation_telemetry: dict[str, Any] = {}
                if "mitigation_telemetry" in row_keys and f["mitigation_telemetry"]:
                    try:
                        mitigation_telemetry = json.loads(f["mitigation_telemetry"])
                    except (ValueError, TypeError):
                        mitigation_telemetry = {}

                # DEFENSIVE DESIGN: Schema Drift Protection.
                # If an older database lacks the 'silo_risk' column, safely default to 0.0
                safe_silo_risk = f["silo_risk"] if "silo_risk" in row_keys else 0.0

                # DEFENSIVE DESIGN: We must perfectly reconstruct the dictionary schema
                # expected by `galaxyscope.py` so the Orchestrator can execute its
                # downstream graph recalculation without throwing KeyError exceptions.
                ram_state[rel_path] = {
                    "path": rel_path,
                    "lang_id": f["language"],
                    "total_loc": f["total_loc"],
                    "coding_loc": f["coding_loc"],
                    # #2625: same Schema Drift Protection as silo_risk above. Before
                    # doc_loc was persisted, rehydrated (unchanged) files silently
                    # reported "Documentation LOC: 0" on every incremental scan
                    # because this reconstruction had no column to read it from.
                    "doc_loc": f["doc_loc"] if "doc_loc" in row_keys else 0,
                    "file_impact": float(f["structural_mass"]),
                    "control_flow_ratio": float(f["control_flow_ratio"]),
                    # #3220: restore the file's raw import strings so the delta graph
                    # resolver rebuilds every edge FROM this file (popularity/pagerank/
                    # api_exposure of imported files depend on it). Persisted as JSON.
                    "raw_imports": _json_import_set(f["raw_imports"]) if "raw_imports" in row_keys else set(),
                    # #3313 step 3: the file's raw idiom-wrapper facts, so an unchanged
                    # file's wrappers and call sites still take part in the repo-wide
                    # resolution (wrapper_resolver) on a delta scan. NULL/absent: none.
                    "wrapper_facts": (
                        json.loads(f["wrapper_facts"]) if "wrapper_facts" in row_keys and f["wrapper_facts"] else None
                    ),
                    "risk_vector": risk_vector,
                    "hit_vector": hit_vector,
                    "equations": equations,
                    "mitigation_telemetry": mitigation_telemetry,
                    # #3220: seed metadata with the persisted documentation shield.
                    # _calculate_risk_exposures keeps an existing "metadata" dict (only
                    # adds folder_dominant_lang), so doc_umbrella survives to
                    # _calc_documentation. ghost_meta.get("doc_umbrella", 0.0) otherwise
                    # defaulted to 0.0 on every rehydrated file.
                    "metadata": {
                        "doc_umbrella": (
                            float(f["doc_umbrella"])
                            if "doc_umbrella" in row_keys and f["doc_umbrella"] is not None
                            else 0.0
                        )
                    },
                    # #3220: a rehydrated file's language identity was already
                    # confidently locked in the baseline scan. _calculate_risk_exposures
                    # rebuilds telemetry from meta["lock_tier"]/["source_proof"], and the
                    # statistical auditor drops a file whose tier defaults to 4 UNLESS it
                    # has named structure -- so zero-structure config/data files (.yaml,
                    # .txt, extensionless scripts) were banished. Restore a confident lock
                    # (these are NOT persisted columns, so row parity is unaffected).
                    "lock_tier": 1,
                    "source_proof": "Rehydrated Baseline Lock",
                    "intensity": 1.0,
                    "telemetry": {
                        "popularity": f["popularity"],
                        "ownership": f["author"],
                        "ai_threat_score": f["ai_threat_score"],
                        "author_distribution": safe_silo_risk,
                    },
                    # Schema Drift Protection (same pattern as silo_risk/doc_loc above).
                    # total_upstream/total_downstream are TRANSITIVE reach counts computed
                    # at scan time (security_auditor.reach_counts) and written only to the
                    # JSON audit -- they were never persisted as file_data columns. An
                    # unguarded f["total_downstream"] therefore raises IndexError on every
                    # real DB, which the broad except below swallowed, silently dropping
                    # EVERY delta scan back to a full scan. Recomputed by the ripple.
                    "dependency_network": {
                        "total_downstream": f["total_downstream"] if "total_downstream" in row_keys else 0,
                        "total_upstream": f["total_upstream"] if "total_upstream" in row_keys else 0,
                    },
                }

            # #3220: rehydrate per-file FUNCTIONS and CLASSES from function_data /
            # class_data. named_structure = len(functions)+len(classes) is what the
            # statistical auditor uses to keep an ambiguous file (extensionless helper
            # scripts especially) instead of banishing it to the exclusion queue, and
            # function_count/class_count + the func-derived risk aggregation read these
            # lists directly. Without them, ~254 unchanged files were dropped and every
            # file's function/class counts read 0. function_data uses the same hit-column
            # names as file_data, so per-function hit_vector inverts identically.
            try:
                class_name_by_id: dict[int, str] = {}
                for c in cursor.execute(
                    "SELECT cd.id AS _cid, cd.class_name FROM class_data cd "
                    "JOIN file_data fd ON cd.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ?",
                    (repo_name, baseline_hash),
                ):
                    class_name_by_id[c["_cid"]] = c["class_name"]

                funcs_by_file: dict[str, list] = {}
                for r in cursor.execute(
                    "SELECT fd.file_path AS _fp, fn.* FROM function_data fn "
                    "JOIN file_data fd ON fn.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ?",
                    (repo_name, baseline_hash),
                ):
                    rk = r.keys()
                    fn = {
                        "name": r["func_name"],
                        "archetype": r["func_archetype"] if "func_archetype" in rk else None,
                        "parent_class_name": (
                            class_name_by_id.get(r["parent_class_id"])
                            if "parent_class_id" in rk and r["parent_class_id"] is not None
                            else None
                        ),
                        "is_public": bool(r["is_public"]) if "is_public" in rk else True,
                        "is_documented": bool(r["is_documented"]) if "is_documented" in rk else False,
                        # calls_out_to is persisted as a JSON string but consumed as a
                        # list (network_risk_sensor's test-coverage mapping iterates it);
                        # decode it so risk_verification's coverage graph resolves.
                        "calls_out_to": _json_list(r["calls_out_to"]) if "calls_out_to" in rk else [],
                        # #3328/#3329: the call resolver keys functions by start line
                        # and reads the per-callee receiver chains.
                        "calls_out_qualifiers": decode_qualifiers(
                            _json_list(r["calls_out_to"]) if "calls_out_to" in rk else [],
                            _json_list(r["calls_out_qualifiers"]) if "calls_out_qualifiers" in rk else None,
                        ),
                        "start_line": int(r["start_line"] or 0) if "start_line" in rk else 0,
                        # engine stores the complexity/branch metric under "branch"
                        # (signal_processor reads func["branch"] for z-scores + archetype).
                        "branch": r["complexity"] if "complexity" in rk and r["complexity"] is not None else 0,
                        # PER-FUNCTION hit_vector is a DICT keyed by SIGNAL_SCHEMA NAME
                        # (network_risk_sensor / signal_processor do hv.get("test"),
                        # hv.get("decorators"), hv.get("branch") ...), NOT by the persisted
                        # column name and NOT a list like the file-level hit_vector. The
                        # value comes from the SHORT_KEY_MAP-renamed column function_data
                        # stores. Keying by column name (struct_branch/def_test) made every
                        # hv.get(<signal>) miss -> zeroed density features -> wrong function
                        # archetype -> cognitive_load/safety_score/state_flux drift.
                        "hit_vector": {
                            signal_names[i]: int(r[hit_cols[i]])
                            for i in range(len(signal_names))
                            if hit_cols[i] in rk and r[hit_cols[i]] is not None
                        },
                    }
                    # Carry every persisted per-function column through unchanged too, so
                    # any consumer key we did not alias above still resolves (loc, args,
                    # complexity, usage_status, keyword_density, docstring, calls_out_to,
                    # func_z_score, token_mass, branch/struct_* ...).
                    for k in rk:
                        if k not in ("_fp", "id", "file_id", "parent_class_id") and k not in fn:
                            fn[k] = r[k]
                    funcs_by_file.setdefault(r["_fp"], []).append(fn)

                classes_by_file: dict[str, list] = {}
                for r in cursor.execute(
                    "SELECT fd.file_path AS _fp, cd.* FROM class_data cd "
                    "JOIN file_data fd ON cd.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ?",
                    (repo_name, baseline_hash),
                ):
                    rk = r.keys()
                    cl = {"name": r["class_name"]}
                    for k in rk:
                        if k not in ("_fp", "id", "file_id") and k not in cl:
                            cl[k] = r[k]
                    classes_by_file.setdefault(r["_fp"], []).append(cl)

                # #3200/#3201/#3246: the mainframe boundary channel, restored for
                # the same reason #3220 restores raw_imports. An unchanged file is
                # never re-parsed, so without this an incremental scan drops
                # every call site, dataset binding, record layout and transaction
                # it already knew about -- the DB would end up describing only the
                # files that happened to change in the last commit. Every table is
                # optional: a baseline written before #3200/#3246/#3211-followup
                # simply has fewer of them. `resolved_path`/`dst_file_id` are
                # deliberately NOT restored for calls or transactions: resolution
                # is repo-wide and redone every scan, because a file added or
                # deleted this commit can change what an unchanged file resolves to.
                calls_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "call_site_data",
                    "SELECT fd.file_path AS _fp, cs.verb, cs.form, cs.operand, cs.target, cs.line_number AS line "
                    "FROM call_site_data cs JOIN file_data fd ON cs.src_file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY cs.id",
                    lambda r: {
                        "verb": r["verb"],
                        "form": r["form"],
                        "operand": r["operand"],
                        "target": r["target"],
                        "line": int(r["line"] or 0),
                    },
                )
                # #3345: the resolved-DSN pair is per-file (one JCL file determines
                # it), so it is restored like the raw DSN. A baseline written
                # before #3345 lacks the columns; its rows come back without the
                # keys, exactly the shape the extractor gives a COBOL row.
                resolved_cols = (
                    "ds.dsn_resolved, ds.dsn_resolution"
                    if _has_table(cursor, "dataset_data") and _has_column(cursor, "dataset_data", "dsn_resolution")
                    else "NULL AS dsn_resolved, NULL AS dsn_resolution"
                )
                datasets_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "dataset_data",
                    "SELECT fd.file_path AS _fp, ds.step_name, ds.internal_name, ds.assign_name, "  # noqa: S608 -- resolved_cols is one of two literals; values are bound
                    "ds.dd_name, ds.access_modes AS modes, ds.dsn, ds.line_number AS line, "
                    f"{resolved_cols} "
                    "FROM dataset_data ds JOIN file_data fd ON ds.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ds.id",
                    lambda r: {
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
                    },
                )
                # Aliased to the extractor's own payload key names (level_number ->
                # level, item_name -> name, value_literal -> value). `attributes`
                # (#3250, PL/I) is NULL on a baseline written before it existed.
                attributes_col = (
                    "rd.attributes"
                    if _has_table(cursor, "record_data") and _has_column(cursor, "record_data", "attributes")
                    else "NULL"
                )
                records_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "record_data",
                    "SELECT fd.file_path AS _fp, rd.section, rd.fd_name, rd.ordinal, rd.parent_ordinal, "  # noqa: S608 -- attributes_col is one of two literals; values are bound
                    "rd.level_number AS level, rd.item_name AS name, rd.pic, rd.usage, rd.occurs_min, "
                    "rd.occurs_max, rd.occurs_depending_on, rd.redefines, rd.value_literal AS value, "
                    f"rd.line_number AS line, {attributes_col} AS attributes "
                    "FROM record_data rd JOIN file_data fd ON rd.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY rd.file_id, rd.ordinal",
                    lambda r: {
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
                    },
                )
                # #3211-followup: the CSD transaction definitions, restored per
                # deck so an unchanged .csd/JCL keeps its transactions through a
                # delta scan. `group_name` is aliased to the extractor's `group`
                # payload key.
                transactions_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "transaction_data",
                    "SELECT fd.file_path AS _fp, td.transid, td.program, td.group_name AS _group, "
                    "td.profile, td.line_number AS line "
                    "FROM transaction_data td JOIN file_data fd ON td.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY td.id",
                    lambda r: {
                        "transid": r["transid"],
                        "program": r["program"],
                        "group": r["_group"],
                        "profile": r["profile"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3344: DB2 DECLARE TABLE / DCLGEN columns, aliased back to the
                # extractor's payload keys (table_name -> table, column_name ->
                # name). A pre-#3344 baseline has no table and restores nothing.
                sql_tables_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "sql_table_data",
                    'SELECT fd.file_path AS _fp, st.table_name AS "table", st.table_line, st.colno, st.column_name AS name, '
                    "st.sql_type, st.length, st.scale, st.nullable, st.attributes, st.line_number AS line "
                    "FROM sql_table_data st JOIN file_data fd ON st.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY st.id",
                    lambda r: {
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
                )

                # #3347: BMS screen-field layouts, aliased to the extractor's payload
                # keys (field_name -> name, initial_value -> initial).
                screen_fields_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "screen_field_data",
                    "SELECT fd.file_path AS _fp, sf.kind, sf.ordinal, sf.parent_ordinal, "
                    "sf.field_name AS name, sf.pos_line, sf.pos_column, sf.length, sf.attrb, sf.picin, "
                    "sf.picout, sf.initial_value AS initial, sf.occurs, sf.attributes, sf.line_number AS line "
                    "FROM screen_field_data sf JOIN file_data fd ON sf.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY sf.file_id, sf.ordinal",
                    lambda r: {
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
                )

                for rel_path, node in ram_state.items():
                    node["functions"] = funcs_by_file.get(rel_path, [])
                    node["classes"] = classes_by_file.get(rel_path, [])
                    node["call_sites"] = calls_by_file.get(rel_path, [])
                    node["dataset_bindings"] = datasets_by_file.get(rel_path, [])
                    node["record_layouts"] = records_by_file.get(rel_path, [])
                    node["transaction_defs"] = transactions_by_file.get(rel_path, [])
                    node["sql_tables"] = sql_tables_by_file.get(rel_path, [])
                    node["screen_fields"] = screen_fields_by_file.get(rel_path, [])
            except sqlite3.Error as fc_err:
                print(f"⚠️ Could not rehydrate functions/classes (structure counts may drift): {fc_err}")

            conn.close()

            # Return the standardized payload
            return {"commit_hash": baseline_hash, "ram_cache": ram_state}

        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError) as e:
            # Broadened beyond sqlite3.Error: a structurally valid DB can still
            # carry row-level type confusion -- e.g. a non-numeric string in a
            # REAL column -- which raises ValueError/TypeError from the float()
            # coercions above, not sqlite3.Error. Any of these means the historical
            # state can't be trusted; fall back to a cold start the same way a
            # corrupted DB does, rather than crashing the delta-scan path.
            print(f"⚠️ Database corruption or read error at {self.db_path}: {e}")
            return None

    def load_latest_state(self, repo_name: str) -> Optional[dict[str, Any]]:
        """Back-compat alias for `load_state(repo_name)` — the latest-by-date
        baseline. Prefer `load_state(repo_name, commit_hash=...)` with an explicit
        parent for longitudinal history walks (#2983)."""
        return self.load_state(repo_name)
