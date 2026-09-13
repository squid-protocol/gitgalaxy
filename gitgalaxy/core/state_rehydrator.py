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

    def load_state(
        self, repo_name: str, commit_hash: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
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

            # 3. Rebuild the orchestrator's `ram_cache` dictionary format
            ram_state = {}
            for f in file_rows:
                rel_path = f["file_path"]
                row_keys = f.keys()

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
                    # Initialize empty collections for downstream pipeline requirements
                    "raw_imports": set(),
                    "hit_vector": [],
                    "telemetry": {
                        "popularity": f["popularity"],
                        "ownership": f["author"],
                        "ai_threat_score": f["ai_threat_score"],
                        "author_distribution": safe_silo_risk,
                    },
                    "dependency_network": {
                        "total_downstream": f["total_downstream"],
                        "total_upstream": f["total_upstream"],
                    },
                }

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
