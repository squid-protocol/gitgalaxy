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
from typing import Any

from gitgalaxy.core.call_resolver import decode_qualifiers
from gitgalaxy.core.fact_channels import CHANNELS
from gitgalaxy.core.unicode_paths import nfc


def _json_dict(value: Any) -> dict:
    """Decode a persisted JSON-object column; NULL or malformed text -> {}."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        out = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


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

    def load_state(self, repo_name: str, commit_hash: str | None = None) -> dict[str, Any] | None:
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
                equations = dict(zip(signal_names, hit_vector, strict=True))
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
                    # #3660: the file's declared top-level names, so an unchanged
                    # file's properties still resolve declaration imports on a delta.
                    "declared_names": (
                        json.loads(f["declared_names"]) if "declared_names" in row_keys and f["declared_names"] else []
                    ),
                    # #3813: how the file's bytes were decoded, so an unchanged file keeps
                    # its source_encoding / source_decode across a delta. NULL on a DB that
                    # predates the columns: unknown, not a guess.
                    "source_encoding": f["source_encoding"] if "source_encoding" in row_keys else None,
                    "source_decode": f["source_decode"] if "source_decode" in row_keys else None,
                    # #3788: the file's namespace-import aliases, so an unchanged file's `ns.f()`
                    # calls still resolve on a delta scan. NULL/absent: none.
                    "namespace_imports": (
                        json.loads(f["namespace_imports"])
                        if "namespace_imports" in row_keys and f["namespace_imports"]
                        else {}
                    ),
                    # #4265: library-qualified COPY members, so a delta scan resolves them the same way.
                    "import_libraries": (
                        json.loads(f["import_libraries"])
                        if "import_libraries" in row_keys and f["import_libraries"]
                        else {}
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
                    # #4483: this file SURVIVED the baseline scan's audit (it has a file_data
                    # row). The persisted hit/risk vectors are the post-sanitisation values
                    # (SARIF_IGNORED_PATHS zeroes them after the audit), so re-judging the file
                    # here reads a zero-signal row as a data dump and drops it. The statistical
                    # auditor passes a rehydrated file through instead of re-auditing it.
                    "rehydrated": True,
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
                        # the decorators applied to it (the resolver's kind='decorator' edges)
                        "decorated_by": _json_list(r["decorated_by"]) if "decorated_by" in rk else [],
                        "decorated_by_qualifiers": decode_qualifiers(
                            _json_list(r["decorated_by"]) if "decorated_by" in rk else [],
                            _json_list(r["decorated_by_qualifiers"]) if "decorated_by_qualifiers" in rk else None,
                        ),
                        # function names used as values (the resolver's kind='reference' edges)
                        "references_to": _json_list(r["references_to"]) if "references_to" in rk else [],
                        "references_qualifiers": decode_qualifiers(
                            _json_list(r["references_to"]) if "references_to" in rk else [],
                            _json_list(r["references_qualifiers"]) if "references_qualifiers" in rk else None,
                        ),
                        # the receiver -> class map the resolver's `typed` step reads
                        "calls_out_receiver_types": _json_dict(r["calls_out_receiver_types"])
                        if "calls_out_receiver_types" in rk
                        else {},
                        # #3835: callee -> call-site argument counts (java overload choice)
                        "calls_out_arities": _json_dict(r["calls_out_arities"]) if "calls_out_arities" in rk else {},
                        "start_line": int(r["start_line"] or 0) if "start_line" in rk else 0,
                        # with start_line, the caller's span the resolver uses to prefer
                        # a function nested inside it over a same-named one elsewhere
                        "loc": int(r["loc"] or 0) if "loc" in rk else 0,
                        # #3362: COBOL GO TO targets, re-resolved on a delta scan.
                        "transfers_to": _json_list(r["transfers_to"]) if "transfers_to" in rk else [],
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
                    # #3786: the resolver (and a fresh scan) carry a class's parents as
                    # `inheritance`, a list; the DB column `inheritance_parents` is its JSON.
                    try:
                        parents = json.loads(cl.pop("inheritance_parents", None) or "[]")
                    except (TypeError, ValueError):
                        parents = []
                    cl["inheritance"] = parents if isinstance(parents, list) else []
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
                # #3383: the registered per-file fact channels (dataset, record, sql_table, csd_resource,
                # screen_field, cics_resource) -- declared in gitgalaxy/core/fact_channels.py.
                channel_rows = {
                    channel.name: _restore_child_table(
                        cursor,
                        repo_name,
                        baseline_hash,
                        channel.table,
                        channel.select_sql(cursor, _has_table, _has_column),
                        channel.to_payload,
                    )
                    for channel in CHANNELS
                }

                # #3448: job-submission evidence, aliased back to the payload keys.
                job_submits_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "job_submit_data",
                    "SELECT fd.file_path AS _fp, js.kind, js.step_name AS step, js.submit_name AS name, "
                    "js.target_kind, js.target, js.line_number AS line "
                    "FROM job_submit_data js JOIN file_data fd ON js.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY js.id",
                    lambda r: {
                        "kind": r["kind"],
                        "step": r["step"],
                        "name": r["name"],
                        "target_kind": r["target_kind"],
                        "target": r["target"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3447: IBM MQ calls, aliased back to the payload keys.
                mq_calls_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "mq_call_data",
                    "SELECT fd.file_path AS _fp, mq.verb, mq.direction, mq.queue_operand AS operand, "
                    "mq.queue_name AS queue, mq.queue_resolution AS resolution, mq.queue_candidates AS candidates, "
                    "mq.handle, mq.open_line, mq.options, mq.line_number AS line "
                    "FROM mq_call_data mq JOIN file_data fd ON mq.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY mq.id",
                    lambda r: {
                        "verb": r["verb"],
                        "direction": r["direction"],
                        "operand": r["operand"],
                        "queue": r["queue"],
                        "resolution": r["resolution"],
                        "candidates": r["candidates"],
                        "handle": r["handle"],
                        "open_line": int(r["open_line"]) if r["open_line"] is not None else None,
                        "options": r["options"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3453: units of work and error handling, aliased to the payload keys.
                uow_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "uow_handler_data",
                    "SELECT fd.file_path AS _fp, u.kind, u.source, u.verb, u.condition_name AS condition, "
                    "u.target, u.target_kind, u.resp_var, u.attributes, u.line_number AS line "
                    "FROM uow_handler_data u JOIN file_data fd ON u.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY u.id",
                    lambda r: {
                        "kind": r["kind"],
                        "source": r["source"],
                        "verb": r["verb"],
                        "condition": r["condition"],
                        "target": r["target"],
                        "target_kind": r["target_kind"],
                        "resp_var": r["resp_var"],
                        "attributes": r["attributes"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3455: file definitions, aliased back to the payload keys.
                file_control_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "file_control_data",
                    'SELECT fd.file_path AS _fp, fc.select_name, fc.assign_name AS "assign", fc.organization, fc.access_mode, fc.record_key, fc.alternate_keys, fc.relative_key, fc.file_status, fc.fd_copies, fc.line_number AS "line" '
                    "FROM file_control_data fc JOIN file_data fd ON fc.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY fc.id",
                    lambda r: {
                        "select_name": r["select_name"],
                        "assign": r["assign"],
                        "organization": r["organization"],
                        "access_mode": r["access_mode"],
                        "record_key": r["record_key"],
                        "alternate_keys": r["alternate_keys"],
                        "relative_key": r["relative_key"],
                        "file_status": r["file_status"],
                        "fd_copies": r["fd_copies"],
                        "line": int(r["line"] or 0),
                    },
                )
                vsam_defines_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "vsam_define_data",
                    'SELECT fd.file_path AS _fp, vd.kind, vd.cluster_name AS "name", vd.organization, vd.key_length, vd.key_offset, vd.record_avg, vd.record_max, vd.related, vd.unique_key, vd.upgrade, vd.step_name AS "step", vd.line_number AS "line" '
                    "FROM vsam_define_data vd JOIN file_data fd ON vd.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY vd.id",
                    lambda r: {
                        "kind": r["kind"],
                        "name": r["name"],
                        "organization": r["organization"],
                        "key_length": int(r["key_length"]) if r["key_length"] is not None else None,
                        "key_offset": int(r["key_offset"]) if r["key_offset"] is not None else None,
                        "record_avg": int(r["record_avg"]) if r["record_avg"] is not None else None,
                        "record_max": int(r["record_max"]) if r["record_max"] is not None else None,
                        "related": r["related"],
                        "unique_key": r["unique_key"],
                        "upgrade": r["upgrade"],
                        "step": r["step"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3451: JCL job flow, aliased back to the payload keys.
                # #3622: `disp_normal` is NULL on a baseline written before it existed.
                normal_col = (
                    "jf.disp_normal"
                    if _has_table(cursor, "job_flow_data") and _has_column(cursor, "job_flow_data", "disp_normal")
                    else "NULL"
                )
                # #3710: a runner step's runs / runs_via / systsin_member, NULL before they existed.
                runner_cols = (
                    "jf.runs, jf.runs_via, jf.systsin_member"
                    if _has_table(cursor, "job_flow_data") and _has_column(cursor, "job_flow_data", "runs")
                    else "NULL AS runs, NULL AS runs_via, NULL AS systsin_member"
                )
                parm_col = (  # #3624
                    "jf.parm"
                    if _has_table(cursor, "job_flow_data") and _has_column(cursor, "job_flow_data", "parm")
                    else "NULL"
                )
                instream_col = (  # #4268
                    "jf.instream"
                    if _has_table(cursor, "job_flow_data") and _has_column(cursor, "job_flow_data", "instream")
                    else "NULL"
                )
                job_flow_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "job_flow_data",
                    'SELECT fd.file_path AS _fp, jf.kind, jf.job_name AS "name", jf.step_ordinal, jf.step_name, jf.program, jf.proc_name AS "proc", jf.cond, jf.if_cond, jf.in_proc, jf.dd_name, jf.dsn, jf.disp, jf.generation, jf.line_number AS "line", '  # noqa: S608 -- normal_col is one of two literals
                    f"{normal_col} AS disp_normal, {runner_cols}, {parm_col} AS parm, {instream_col} AS instream "
                    "FROM job_flow_data jf JOIN file_data fd ON jf.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY jf.id",
                    lambda r: {
                        "kind": r["kind"],
                        "name": r["name"],
                        "step_ordinal": int(r["step_ordinal"]) if r["step_ordinal"] is not None else None,
                        "step_name": r["step_name"],
                        "program": r["program"],
                        "proc": r["proc"],
                        "cond": r["cond"],
                        "if_cond": r["if_cond"],
                        "in_proc": r["in_proc"],
                        "dd_name": r["dd_name"],
                        "dsn": r["dsn"],
                        "disp": r["disp"],
                        "generation": r["generation"],
                        "line": int(r["line"] or 0),
                        **({"disp_normal": r["disp_normal"]} if r["disp_normal"] else {}),
                        **{k: r[k] for k in ("runs", "runs_via", "systsin_member", "parm", "instream") if r[k]},
                    },
                )

                # #3454: program entry points.
                entry_points_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "entry_point_data",
                    "SELECT fd.file_path AS _fp, ep.kind, ep.entry_name, ep.params, ep.line_number AS line "
                    "FROM entry_point_data ep JOIN file_data fd ON ep.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ep.id",
                    lambda r: {
                        "kind": r["kind"],
                        "entry_name": r["entry_name"],
                        "params": r["params"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3450: IMS DL/I calls, aliased back to the payload keys.
                dli_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "dli_call_data",
                    'SELECT fd.file_path AS _fp, dc.interface, dc.function, dc.function_operand, dc.pcb, dc.io_area, dc.segments, dc.ssas, dc.where_text AS "where", dc.psb, dc.line_number AS "line" '
                    "FROM dli_call_data dc JOIN file_data fd ON dc.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY dc.id",
                    lambda r: {
                        "interface": r["interface"],
                        "function": r["function"],
                        "function_operand": r["function_operand"],
                        "pcb": r["pcb"],
                        "io_area": r["io_area"],
                        "segments": r["segments"],
                        "ssas": r["ssas"],
                        "where": r["where"],
                        "psb": r["psb"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3477: IMS PSB / DBD macros and region steps.
                ims_gen_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "ims_gen_data",
                    'SELECT fd.file_path AS _fp, ig.kind, ig.name, ig.parent, ig.owner, ig.dbd_name, ig.procopt, ig.pcb_type, ig.access, ig.bytes, ig.start_pos AS "start", ig.psb_name, ig.program, ig.attributes, ig.line_number AS "line" '
                    "FROM ims_gen_data ig JOIN file_data fd ON ig.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY ig.id",
                    lambda r: {
                        "kind": r["kind"],
                        "name": r["name"],
                        "parent": r["parent"],
                        "owner": r["owner"],
                        "dbd_name": r["dbd_name"],
                        "procopt": r["procopt"],
                        "pcb_type": r["pcb_type"],
                        "access": r["access"],
                        "bytes": int(r["bytes"]) if r["bytes"] is not None else None,
                        "start": int(r["start"]) if r["start"] is not None else None,
                        "psb_name": r["psb_name"],
                        "program": r["program"],
                        "attributes": r["attributes"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3820: SPECIAL-NAMES currency strings / decimal point.
                special_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "special_names_data",
                    'SELECT fd.file_path AS _fp, sn.clause, sn.value, sn.symbol, sn.line_number AS "line" '
                    "FROM special_names_data sn JOIN file_data fd ON sn.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY sn.id",
                    lambda r: {
                        "clause": r["clause"],
                        "value": r["value"],
                        "symbol": r["symbol"],
                        "line": int(r["line"] or 0),
                    },
                )

                # #3828: CBL / PROCESS compiler options.
                options_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "compiler_options_data",
                    'SELECT fd.file_path AS _fp, co.option, co.value, co.written, co.line_number AS "line" '
                    "FROM compiler_options_data co JOIN file_data fd ON co.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY co.id",
                    lambda r: {
                        "option": r["option"],
                        "value": r["value"],
                        "written": r["written"],
                        "line": int(r["line"] or 0),
                    },
                )

                # The slicer's synthetic top-level buckets: callers without a
                # function_data row, restored so their calls re-resolve.
                synthetic_by_file = _restore_child_table(
                    cursor,
                    repo_name,
                    baseline_hash,
                    "synthetic_unit_data",
                    "SELECT fd.file_path AS _fp, su.unit_name AS name, su.start_line, su.calls_out_to, "
                    "su.calls_out_qualifiers, su.calls_out_receiver_types, su.calls_out_arities, su.transfers_to, su.calls_only "
                    "FROM synthetic_unit_data su JOIN file_data fd ON su.file_id = fd.id "
                    "WHERE fd.repo_name = ? AND fd.commit_hash = ? ORDER BY su.id",
                    lambda r: {
                        "name": r["name"],
                        "start_line": int(r["start_line"] or 0),
                        "is_synthetic_slice": True,
                        "calls_only": bool(r["calls_only"]),
                        "calls_out_to": _json_list(r["calls_out_to"]),
                        "calls_out_qualifiers": decode_qualifiers(
                            _json_list(r["calls_out_to"]), _json_list(r["calls_out_qualifiers"])
                        ),
                        "calls_out_receiver_types": _json_dict(r["calls_out_receiver_types"]),
                        "calls_out_arities": _json_dict(r["calls_out_arities"]),
                        "transfers_to": _json_list(r["transfers_to"]),
                    },
                )

                for rel_path, node in ram_state.items():
                    node["functions"] = funcs_by_file.get(rel_path, []) + synthetic_by_file.get(rel_path, [])
                    node["classes"] = classes_by_file.get(rel_path, [])
                    for channel in CHANNELS:
                        node[channel.payload_key] = channel_rows[channel.name].get(rel_path, [])
                    node["job_submits"] = job_submits_by_file.get(rel_path, [])
                    node["mq_calls"] = mq_calls_by_file.get(rel_path, [])
                    node["uow_handlers"] = uow_by_file.get(rel_path, [])
                    node["file_control"] = file_control_by_file.get(rel_path, [])
                    node["vsam_defines"] = vsam_defines_by_file.get(rel_path, [])
                    node["job_flow"] = job_flow_by_file.get(rel_path, [])
                    node["entry_points"] = entry_points_by_file.get(rel_path, [])
                    node["dli_calls"] = dli_by_file.get(rel_path, [])
                    node["ims_gen"] = ims_gen_by_file.get(rel_path, [])
                    node["special_names"] = special_by_file.get(rel_path, [])  # #3820
                    node["compiler_options"] = options_by_file.get(rel_path, [])  # #3828
            except sqlite3.Error as fc_err:
                print(f"⚠️ Could not rehydrate functions/classes (structure counts may drift): {fc_err}")

            # #4421: the --copy-libraries reports of the baseline (None: none were declared)
            copy_reports: dict[str, Any] = {}
            for key in ("copy_member_collisions", "copy_member_gaps"):
                raw = None
                if _has_column(cursor, "repo_data", key):
                    raw = cursor.execute(
                        f"SELECT {key} FROM repo_data WHERE repo_name = ? AND commit_hash = ?",  # noqa: S608 -- literal key
                        (repo_name, baseline_hash),
                    ).fetchone()[0]
                copy_reports[key] = _json_list(raw) if raw else None
            conn.close()

            # #3815: a baseline written before stored paths were NFC can hold an NFD path. Key
            # it as today's scan stores it, or the delta scan reads the file as renamed.
            if not all(p.isascii() for p in ram_state):
                ram_state = {nfc(p): {**node, "path": nfc(p)} for p, node in ram_state.items()}

            # Return the standardized payload
            return {"commit_hash": baseline_hash, "ram_cache": ram_state, **copy_reports}

        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError) as e:
            # Broadened beyond sqlite3.Error: a structurally valid DB can still
            # carry row-level type confusion -- e.g. a non-numeric string in a
            # REAL column -- which raises ValueError/TypeError from the float()
            # coercions above, not sqlite3.Error. Any of these means the historical
            # state can't be trusted; fall back to a cold start the same way a
            # corrupted DB does, rather than crashing the delta-scan path.
            print(f"⚠️ Database corruption or read error at {self.db_path}: {e}")
            return None

    def load_latest_state(self, repo_name: str) -> dict[str, Any] | None:
        """Back-compat alias for `load_state(repo_name)` — the latest-by-date
        baseline. Prefer `load_state(repo_name, commit_hash=...)` with an explicit
        parent for longitudinal history walks (#2983)."""
        return self.load_state(repo_name)
