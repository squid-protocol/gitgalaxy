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

import sqlite3
from pathlib import Path
from typing import Any, Optional


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
            except Exception as schema_err:  # noqa: BLE001
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
                    # #3220: raw_imports (import strings) are not yet persisted, so the
                    # graph must still be re-resolved for add/delete exactness -- tracked
                    # as the remaining piece. Vectors below ARE now fully restored.
                    "raw_imports": set(),
                    "risk_vector": risk_vector,
                    "hit_vector": hit_vector,
                    "equations": equations,
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
                        "parent_class_name": class_name_by_id.get(r["parent_class_id"] if "parent_class_id" in rk else None),
                        "is_public": bool(r["is_public"]) if "is_public" in rk else True,
                        "is_documented": bool(r["is_documented"]) if "is_documented" in rk else False,
                        # engine stores the complexity/branch metric under "branch"
                        # (signal_processor reads func["branch"] for z-scores + archetype).
                        "branch": r["complexity"] if "complexity" in rk and r["complexity"] is not None else 0,
                        # PER-FUNCTION hit_vector is a DICT keyed by hit-column name
                        # (signal_processor does hv.get(<col>)), NOT a list like the
                        # file-level hit_vector. function_data persists the same columns.
                        "hit_vector": {c: int(r[c]) for c in hit_cols if c in rk and r[c] is not None},
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

                for rel_path, node in ram_state.items():
                    node["functions"] = funcs_by_file.get(rel_path, [])
                    node["classes"] = classes_by_file.get(rel_path, [])
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
