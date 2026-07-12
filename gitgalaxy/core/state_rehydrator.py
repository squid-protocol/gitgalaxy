# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_high_risk_execution

import sqlite3
from pathlib import Path
from typing import Dict, Any

# galaxyscope:ignore sec_high_risk_execution, agentic_rce, logic_bomb
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

    def load_latest_state(self, repo_name: str) -> Dict[str, Any]:
        """
        Pulls the most recent commit state from SQLite and rebuilds the RAM dictionary.
        """
        # PERFORMANCE OPTIMIZATION: Fast disk-check before attempting DB connections
        if not self.db_path.exists():
            print(f"⚠️ No master DB found at {self.db_path}. Cold start required.")
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Retrieve the most recent commit hash for this specific repository
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

            latest_hash = row["commit_hash"]
            print(f"🔄 Rehydrating RAM from commit: {latest_hash}")

            # 2. Extract the structural metrics for the baseline commit
            cursor.execute(
                """
                SELECT * FROM file_data 
                WHERE repo_name = ? AND commit_hash = ?
            """,
                (repo_name, latest_hash),
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
                    "file_impact": f["structural_mass"],
                    "control_flow_ratio": f["control_flow_ratio"],
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
            return {"commit_hash": latest_hash, "ram_cache": ram_state}

        except sqlite3.Error as e:
            print(f"⚠️ Database corruption or read error at {self.db_path}: {e}")
            return None
    
    # ==============================================================================
# TEST 6: DICTIONARY OVERRIDE TYPE SPOOFING
# ==============================================================================
def test_rehydrator_dictionary_type_spoofing(tmp_path):
    """
    DEVIOUS EDGE CASE: An attacker (or corrupted DB) places a String into a column 
    that the RAM cache strictly expects to be a Float. When the Signal Processor 
    attempts to execute metrics math on this dictionary override, it will crash. 
    The Rehydrator MUST enforce strict type casting.
    """
    db_path = tmp_path / "spoofed_master.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE repo_data (repo_name TEXT, commit_hash TEXT, commit_date INTEGER)")
    cursor.execute("""
        CREATE TABLE file_data (
            repo_name TEXT, commit_hash TEXT, file_path TEXT, language TEXT,
            total_loc INTEGER, coding_loc INTEGER, structural_mass REAL,
            control_flow_ratio REAL, popularity INTEGER, author TEXT,
            ai_threat_score REAL, silo_risk REAL, total_downstream INTEGER, total_upstream INTEGER
        )
    """)

    cursor.execute("INSERT INTO repo_data VALUES ('test_repo', 'hash_1', 1600000000)")
    
    # MALICIOUS INJECTION: Injecting a String 'HACKED' into the Float columns
    cursor.execute("""
        INSERT INTO file_data VALUES (
            'test_repo', 'hash_1', 'src/hacked.py', 'python',
            150, 100, 'HACKED_MASS', 'HACKED_CFR', 12, 'Attacker', 'HACKED_THREAT', 12.5, 4, 2
        )
    """)
    conn.commit()
    conn.close()

    rehydrator = StateRehydrator(str(db_path))
    result = rehydrator.load_latest_state("test_repo")
    
    ram = result["ram_cache"]["src/hacked.py"]
    
    # If the rehydrator didn't cast to float(), this will be a string and crash the downstream math!
    assert isinstance(ram["file_impact"], float), "State Rehydrator failed to sanitize dictionary overrides!"
    assert isinstance(ram["control_flow_ratio"], float), "State Rehydrator allowed a string into a float field!"