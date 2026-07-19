import pytest
import sqlite3

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
            silo_risk REAL,
            total_downstream INTEGER,
            total_upstream INTEGER
        )
    """)

    # Insert Mock Data: Repo History
    # Older commit
    cursor.execute(
        "INSERT INTO repo_data VALUES ('test_repo', 'hash_old_123', 1600000000)"
    )
    # Newer commit (This should be the one selected!)
    cursor.execute(
        "INSERT INTO repo_data VALUES ('test_repo', 'hash_new_456', 1700000000)"
    )
    # Different repo entirely
    cursor.execute(
        "INSERT INTO repo_data VALUES ('other_repo', 'hash_other_789', 1800000000)"
    )

    # Insert Mock Data: File Physics for the newer commit
    cursor.execute("""
        INSERT INTO file_data VALUES (
            'test_repo', 'hash_new_456', 'src/main.py', 'python',
            150, 100, 45.5, 0.35, 12, 'Joe Esquibel', 85.0, 12.5, 4, 2
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
    assert result["commit_hash"] == "hash_new_456", (
        "Failed to select the most recent commit!"
    )

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
    assert file_node["dependency_network"]["total_downstream"] == 4
    assert file_node["dependency_network"]["total_upstream"] == 2

    # 4. Assert Delta Engine defaults were injected
    assert isinstance(file_node["raw_imports"], set)
    assert file_node["hit_vector"] == []

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
    with open(poisoned_db_path, 'w') as f:
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
