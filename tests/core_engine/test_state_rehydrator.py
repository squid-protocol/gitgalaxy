import sqlite3

import pytest

# Adjust this import to match your actual directory structure
from gitgalaxy.core.state_rehydrator import StateRehydrator

# ==============================================================================
# MOCK DATABASE CALIBRATION
# ==============================================================================


@pytest.fixture
def mock_db(tmp_path):
    """Creates a temporary SQLite database populated with mock schema and data."""
    db_path = tmp_path / "gitgalaxy_master.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create Mock Schema
    cursor.execute("""
        CREATE TABLE repo_data (
            repo_name TEXT,
            commit_hash TEXT,
            commit_date INTEGER
        )
    """)
    # #3220: columns here must exist in the schema the engine actually writes
    # (recorders/record_keeper.py). This fixture previously invented
    # total_downstream / total_upstream -- columns the real file_data schema has
    # NEVER had -- so every test passed against a fictional DB while production
    # crashed on the missing columns. They are transitive reach counts written
    # only to the JSON audit, never persisted. Do NOT add them back.
    # (doc_loc is intentionally omitted: test_rehydrator_doc_loc_* uses this
    # fixture as a legacy DB to exercise the absent-column default.)
    cursor.execute("""
        CREATE TABLE file_data (
            repo_name TEXT,
            commit_hash TEXT,
            file_path TEXT,
            language TEXT,
            total_loc INTEGER,
            coding_loc INTEGER,
            structural_mass REAL,
            control_flow_ratio REAL,
            popularity INTEGER,
            author TEXT,
            ai_threat_score REAL,
            silo_risk REAL
        )
    """)

    # Insert Mock Data: Repo History
    # Older commit
    cursor.execute("INSERT INTO repo_data VALUES ('test_repo', 'hash_old_123', 1600000000)")
    # Newer commit (This should be the one selected!)
    cursor.execute("INSERT INTO repo_data VALUES ('test_repo', 'hash_new_456', 1700000000)")
    # Different repo entirely
    cursor.execute("INSERT INTO repo_data VALUES ('other_repo', 'hash_other_789', 1800000000)")

    # Insert Mock Data: File Physics for the newer commit
    cursor.execute("""
        INSERT INTO file_data VALUES (
            'test_repo', 'hash_new_456', 'src/main.py', 'python',
            150, 100, 45.5, 0.35, 12, 'Joe Esquibel', 85.0, 12.5
        )
    """)

    conn.commit()
    conn.close()

    return str(db_path)


# ==============================================================================
# TEST 1: COLD START (Missing DB)
# ==============================================================================
def test_rehydrator_cold_start(tmp_path):
    """Proves the rehydrator safely returns None if the master DB is missing."""
    missing_db_path = tmp_path / "does_not_exist.db"
    rehydrator = StateRehydrator(str(missing_db_path))

    result = rehydrator.load_latest_state("test_repo")
    assert result is None, "Failed to handle a cold start gracefully!"


# ==============================================================================
# TEST 2: GHOST REPOSITORY (Missing Repo Data)
# ==============================================================================
def test_rehydrator_missing_repo(mock_db):
    """Proves the rehydrator safely returns None if the repo history is empty."""
    rehydrator = StateRehydrator(mock_db)

    result = rehydrator.load_latest_state("ghost_repo")
    assert result is None, "Failed to handle a missing repository gracefully!"


# ==============================================================================
# TEST 3: TEMPORAL ACCURACY & SCHEMA MAPPING
# ==============================================================================
def test_rehydrator_successful_load(mock_db):
    """
    Proves the rehydrator fetches the most recent commit based on time,
    and accurately maps the flat SQL columns into the nested RAM dictionary.
    """
    rehydrator = StateRehydrator(mock_db)
    result = rehydrator.load_latest_state("test_repo")

    # 1. Assert Temporal Accuracy
    assert result is not None
    assert result["commit_hash"] == "hash_new_456", "Failed to select the most recent commit!"

    # 2. Assert the ram_cache dictionary structure is perfectly mapped
    ram_cache = result["ram_cache"]
    assert "src/main.py" in ram_cache, "Failed to map the file path as the dictionary key!"

    file_node = ram_cache["src/main.py"]
    assert file_node["lang_id"] == "python"
    assert file_node["file_impact"] == 45.5
    assert file_node["control_flow_ratio"] == 0.35

    # 3. Assert nested JSON/Dictionary reconstruction
    assert file_node["telemetry"]["ownership"] == "Joe Esquibel"
    assert file_node["telemetry"]["ai_threat_score"] == 85.0
    # #3220: these columns are never persisted (real file_data has no such
    # columns), so the rehydrator defaults them to 0 instead of raising
    # IndexError. They are recomputed by the ripple during the incremental scan.
    assert file_node["dependency_network"]["total_downstream"] == 0
    assert file_node["dependency_network"]["total_upstream"] == 0

    # 4. Assert Delta Engine defaults were injected
    assert isinstance(file_node["raw_imports"], set)

    # #3220: the rehydrator now reconstructs FULL vectors by inverting the recorder's
    # schema (risk_<name> / SHORT_KEY_MAP hit columns). This mock DB has none of those
    # columns, so both vectors come back as the correctly-sized all-zero lists (not the
    # old lossy []). equations mirror the hit_vector as the signal-count dict.
    assert isinstance(file_node["hit_vector"], list)
    assert set(file_node["hit_vector"]) <= {0}
    assert isinstance(file_node["risk_vector"], list)
    assert set(file_node["risk_vector"]) <= {0.0}
    assert isinstance(file_node["equations"], dict)


# ==============================================================================
# TEST 4: THE POISONED WELL (Corrupted SQLite Database)
# ==============================================================================
def test_rehydrator_poisoned_db(tmp_path):
    """
    DEVIOUS EDGE CASE: The CI/CD runner downloads a corrupted or 0-byte file
    and passes it to --incremental. The rehydrator must catch the sqlite3.Error
    and fail gracefully rather than crashing the GitHub Action.
    """
    poisoned_db_path = tmp_path / "poisoned_master.db"

    # Write garbage string data into what should be a binary SQLite file
    with open(poisoned_db_path, "w") as f:
        f.write("This is not a database file. It's a trap.")

    rehydrator = StateRehydrator(str(poisoned_db_path))

    try:
        result = rehydrator.load_latest_state("test_repo")
        assert result is None, "Failed to reject a poisoned/corrupted database gracefully!"
    except sqlite3.DatabaseError:
        pytest.fail("The StateRehydrator failed to catch the DatabaseError internally!")


# ==============================================================================
# TEST 5: SCHEMA DRIFT ATTACK (Missing Legacy Columns)
# ==============================================================================
def test_rehydrator_legacy_schema_drift(tmp_path):
    """
    DEVIOUS EDGE CASE: The user is rehydrating from an older version of GitGalaxy
    (e.g., before the 'silo_risk' column existed. The dictionary builder
    must not throw an IndexError.
    """
    db_path = tmp_path / "legacy_master.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Intentionally omitted 'silo_risk'
    cursor.execute("""
        CREATE TABLE repo_data (repo_name TEXT, commit_hash TEXT, commit_date INTEGER)
    """)
    cursor.execute("""
        CREATE TABLE file_data (
            repo_name TEXT, commit_hash TEXT, file_path TEXT, language TEXT,
            total_loc INTEGER, coding_loc INTEGER, structural_mass REAL,
            control_flow_ratio REAL, popularity INTEGER, author TEXT,
            ai_threat_score REAL, total_downstream INTEGER, total_upstream INTEGER
        )
    """)

    cursor.execute("INSERT INTO repo_data VALUES ('test_repo', 'legacy_hash', 1600000000)")
    cursor.execute("""
        INSERT INTO file_data VALUES (
            'test_repo', 'legacy_hash', 'src/legacy.py', 'python',
            150, 100, 45.5, 0.35, 12, 'Joe Esquibel', 85.0, 4, 2
        )
    """)
    conn.commit()
    conn.close()

    rehydrator = StateRehydrator(str(db_path))

    try:
        # If this throws an IndexError, the Rehydrator isn't resilient to schema drift!
        rehydrator.load_latest_state("test_repo")

        # Depending on how we implemented the fix in state_rehydrator.py, it should
        # either succeed with a default value, or we need to update state_rehydrator.py
        # to use `f.keys()` to safely check if the column exists.
    except IndexError:
        pytest.fail("The StateRehydrator threw an IndexError on legacy database schemas!")


# ==============================================================================
# TEST 6: DICTIONARY OVERRIDE TYPE SPOOFING
# ==============================================================================
def test_rehydrator_dictionary_type_spoofing(tmp_path):
    """
    DEVIOUS EDGE CASE: An attacker (or corrupted DB) places a String into a column
    that the RAM cache strictly expects to be a Float. When the Signal Processor
    attempts to execute metrics math on this dictionary override, it will crash.
    The Rehydrator must catch the resulting ValueError/TypeError and fall back to
    a cold start (None) rather than propagating the crash -- the same way it
    already handles a corrupted/poisoned SQLite file.
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

    assert result is None, (
        "Failed to reject a type-spoofed database gracefully -- crashed instead of falling back to a cold start!"
    )


def test_rehydrator_doc_loc_defensive_default_on_legacy_db(mock_db):
    """#2625: a pre-doc_loc database must rehydrate with doc_loc 0 (schema
    drift protection, silo_risk precedent) -- not KeyError. The mock_db
    fixture deliberately has no doc_loc column."""
    result = StateRehydrator(mock_db).load_latest_state("test_repo")
    assert result is not None
    assert result["ram_cache"]["src/main.py"]["doc_loc"] == 0


def test_rehydrator_doc_loc_read_back_when_present(tmp_path):
    """#2625: with the modern schema, an unchanged file's doc_loc must
    survive rehydration instead of silently reporting 0 documentation on
    every incremental scan (the pre-#2625 behavior)."""
    db_path = tmp_path / "modern.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE repo_data (repo_name TEXT, commit_hash TEXT, commit_date INTEGER)")
    conn.execute(
        """CREATE TABLE file_data (
            repo_name TEXT, commit_hash TEXT, file_path TEXT, language TEXT,
            total_loc INTEGER, coding_loc INTEGER, doc_loc INTEGER, structural_mass REAL,
            control_flow_ratio REAL, popularity INTEGER, author TEXT,
            ai_threat_score REAL, silo_risk REAL, total_downstream INTEGER, total_upstream INTEGER
        )"""
    )
    conn.execute("INSERT INTO repo_data VALUES ('test_repo', 'hash_1', 1700000000)")
    conn.execute(
        "INSERT INTO file_data VALUES ('test_repo', 'hash_1', 'src/main.py', 'python', "
        "150, 100, 42, 45.5, 0.35, 12, 'Joe Esquibel', 85.0, 12.5, 4, 2)"
    )
    conn.commit()
    conn.close()

    result = StateRehydrator(str(db_path)).load_latest_state("test_repo")
    assert result is not None
    assert result["ram_cache"]["src/main.py"]["doc_loc"] == 42


# ==============================================================================
# #2983: EXPLICIT BASELINE SELECTION
# ==============================================================================
def test_explicit_baseline_selects_that_commit(mock_db):
    """load_state(repo, commit_hash) rehydrates THAT commit, not the newest by
    date — the multi-commit-DB case #2983 fixes. The mock has hash_new_456 as the
    newest by date; we ask for the older hash_old_123 and must get it back."""
    # Give the older commit its own file state (the fixture only seeds the newer one).
    conn = sqlite3.connect(mock_db)
    conn.execute("""
        INSERT INTO file_data VALUES (
            'test_repo', 'hash_old_123', 'src/legacy.py', 'python',
            50, 40, 10.0, 0.2, 3, 'Joe Esquibel', 10.0, 1.0
        )
    """)
    conn.commit()
    conn.close()

    result = StateRehydrator(mock_db).load_state("test_repo", "hash_old_123")
    assert result is not None
    assert result["commit_hash"] == "hash_old_123", "Explicit baseline was ignored!"
    # Proves it rehydrated the OLD commit's files, not the newer-by-date commit's.
    assert "src/legacy.py" in result["ram_cache"]
    assert "src/main.py" not in result["ram_cache"]


def test_explicit_baseline_missing_returns_none(mock_db):
    """An explicit baseline that isn't recorded must refuse (return None), never
    silently fall back to a different commit (the nonsense-delta #2983 prevents)."""
    result = StateRehydrator(mock_db).load_state("test_repo", "deadbeef_not_here")
    assert result is None


def test_load_state_none_matches_legacy_latest(mock_db):
    """load_state(repo) with no commit_hash keeps the latest-by-date behavior,
    identical to the legacy load_latest_state alias — full backward compatibility."""
    r = StateRehydrator(mock_db)
    assert r.load_state("test_repo")["commit_hash"] == "hash_new_456"
    assert r.load_state("test_repo")["commit_hash"] == r.load_latest_state("test_repo")["commit_hash"]
