import sqlite3
import pytest
from unittest.mock import patch
from gitgalaxy.recorders.record_keeper import RecordKeeper


@pytest.fixture
def keeper():
    """Initializes the RecordKeeper with a controlled schema for deterministic testing."""
    mock_schemas = {
        "RISK_SCHEMA": ["tech_debt", "cognitive_load"],
        "SIGNAL_SCHEMA": ["high_risk_execution", "io", "prompt_injection"]
    }
    with patch("gitgalaxy.recorders.record_keeper.RECORDING_SCHEMAS", mock_schemas):
        return RecordKeeper()


@pytest.fixture
def mock_pipeline_state():
    """Provides a comprehensive, standardized pipeline state for the DB recorder."""
    parsed_files = [
        {
            "path": "src/api/router.py",
            "name": "router.py",
            "lang_id": "python",
            "directory_group": "src/api",
            "lock_tier": 0,
            "total_loc": 200,
            "coding_loc": 150,
            "file_impact": 45.5,
            "raw_imports": ["src/db/models.py"],
            "telemetry": {
                "control_flow_ratio": 0.5,
                "author_distribution": 10.0,
                "ownership_entropy": 0.5,
                "raw_churn_freq": 12.0,
                "ownership": "BackendTeam",
                "popularity": 5,
                "archetype": "API Controller",
                "repo_macro_species": "Web Service",
                "repo_z_score": 1.2,
                "domain_context": {
                    "parent_entity": "AuthService",
                    "AI Threat Score": "95.5%",
                    "AI Threat Class": "Botnet / DDoS"
                },
                "network_metrics": {
                    "pagerank_score": 0.05,
                    "normalized_blast_radius": 1.2,
                    "ecosystem_role": "Core Hub"
                },
                "ai_guardrails": {
                    "is_agentic_black_hole": True,  # Maps to agentic_isolation_risk
                    "hallucination_zone": False
                }
            },
            "is_ml_threat": True,
            "equations": {
                "sec_hardcoded_secrets": 1,  # Maps to has_credentials, #367
                "sec_extension_mismatch": 1,  # Maps to binary_anomaly, #368
            },
            "risk_vector": [80.0, 60.0],  # debt, cog_load
            "hit_vector": [2, 5, 1],  # danger, io, prompt_injection
            "classes": [
                {
                    "name": "APIRouter",
                    "inheritance": ["BaseRouter"],
                    "method_count": 5
                }
            ],
            "functions": [
                {
                    "name": "process_request",
                    "type_id": "function",
                    "loc": 50,
                    "impact": 15.0,
                    "big_o_depth": 2,
                    "is_recursive": False,
                    "db_complexity": 3,
                    "docstring": "Handles incoming API requests.",
                    "calls_out_to": ["validate_token"],
                    "hit_vector": {"high_risk_execution": 1, "io": 2}
                }
            ]
        }
    ]

    unparsable_files = [
        {
            "path": "assets/logo.png",
            "reason": "Security Shielding (Format Excluded)",
            "size_bytes": 1024
        }
    ]

    summary = {
        "summary": {
            "typosquat_hits": 2
        },
        "composition": {
            "python": {"files": 1, "loc": 200}
        },
        "repo_macro_species": {
            "name": "Web Service",
            "z_score": 1.2
        },
        "directory_groups": {
            "src/api": {"total_mass": 45.5, "file_count": 1, "avg_exposures": {"cognitive_load": 60.0}}
        },
        "network_macro": {
            "modularity": 0.8,
            "assortativity": 0.5,
            "cyclic_density": 0.0,
            "avg_path_length": 1.0,
            "articulation_points": 1
        },
        "ecosystem_audits": {
            "xray": {"anomalies_found": 1}
        }
    }

    session_meta = {
        "engine": "GitGalaxy Unit Test",
        "target": "TestProject",
        "target_directory": "/mock/path",
        "timestamp": "2026-06-18T12:00:00Z",
        "duration_seconds": 2.5,
        "git_audit": {
            "branch": "main",
            "commit_hash": "a1b2c3d4",
            "latest_commit_date": "2026-06-18T10:00:00Z"
        }
    }

    return parsed_files, unparsable_files, summary, session_meta


# ==============================================================================
# TEST 1: SCHEMA INTEGRITY & TABLE CREATION
# ==============================================================================
def test_record_keeper_schema_creation(keeper, mock_pipeline_state, tmp_path):
    """Proves the SQLite database generates the correct DevSecOps tables and columns."""
    db_path = tmp_path / "test_schema.sqlite"
    parsed, unparsable, summary, session = mock_pipeline_state

    keeper.record_mission(parsed, unparsable, summary, session, str(db_path))

    assert db_path.exists(), "SQLite database file was not created!"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Verify Core Tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "repo_data" in tables
    assert "file_data" in tables
    assert "function_data" in tables
    assert "excluded_artifacts" in tables  # Updated Terminology
    assert "folder_data" in tables    # Updated Terminology

    # 2. Verify File Column Mapping (Terminology Updates)
    cursor.execute("PRAGMA table_info(file_data)")
    columns = {row[1] for row in cursor.fetchall()}
    
    assert "ecosystem_baseline" in columns
    assert "agentic_isolation_risk" in columns
    assert "obfuscation_flag" in columns
    assert "risk_tech_debt" in columns  # Dynamically generated from RISK_SCHEMA
    assert "state_danger" in columns    # Mapped dynamically from SIGNAL_SCHEMA -> SHORT_KEY_MAP

    conn.close()


# ==============================================================================
# TEST 2: DATA INSERTION & FOREIGN KEY LINKING
# ==============================================================================
def test_record_keeper_data_insertion(keeper, mock_pipeline_state, tmp_path):
    """Proves data flows cleanly from the complex RAM dictionary into relational tables."""
    db_path = tmp_path / "test_data.sqlite"
    parsed, unparsable, summary, session = mock_pipeline_state

    keeper.record_mission(parsed, unparsable, summary, session, str(db_path))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Returns dict-like rows for easy assertion
    cursor = conn.cursor()

    # 1. Verify Repo Data
    cursor.execute("SELECT * FROM repo_data WHERE repo_name='TestProject'")
    repo = cursor.fetchone()
    assert repo["commit_hash"] == "a1b2c3d4"
    assert repo["audit_binary_anomalies"] == 1
    assert repo["typosquat_hits"] == 2
    assert repo["ecosystem_baseline"] == "Web Service"

    # 2. Verify File Data & Security Extraction
    cursor.execute("SELECT * FROM file_data WHERE file_name='router.py'")
    file_row = cursor.fetchone()
    assert file_row["ai_threat_class"] == "Botnet / DDoS"
    assert file_row["ai_threat_score"] == 95.5
    assert file_row["agentic_isolation_risk"] == 1
    # #366: is_malware reads file_data["is_ml_threat"] (security_auditor.py's
    # real output key), not the never-produced "is_malware".
    assert file_row["is_malware"] == 1
    # #367: has_credentials reads equations["sec_hardcoded_secrets"], not the
    # never-produced "has_credentials".
    assert file_row["has_credentials"] == 1
    # #368: binary_anomaly reads equations["sec_extension_mismatch"], not the
    # never-produced "binary_anomaly".
    assert file_row["binary_anomaly"] == 1
    # #369: no GlassWorm-style detector exists anywhere in the codebase --
    # obfuscation_flag is now honestly hardcoded to 0 rather than reading a
    # key nothing ever produced.
    assert file_row["obfuscation_flag"] == 0
    assert file_row["ecosystem_role"] == "Core Hub"
    assert file_row["state_danger"] == 2  # The hit_vector value for danger

    file_id = file_row["id"]

    # 3. Verify Class & Function Relationships (Foreign Keys)
    cursor.execute("SELECT * FROM class_data WHERE file_id=?", (file_id,))
    class_row = cursor.fetchone()
    assert class_row["class_name"] == "APIRouter"

    cursor.execute("SELECT * FROM function_data WHERE file_id=?", (file_id,))
    func_row = cursor.fetchone()
    assert func_row["func_name"] == "process_request"
    assert func_row["big_o_depth"] == 2
    assert "validate_token" in func_row["calls_out_to"]
    
    # Verify the specific signal mapped properly in the function table
    assert func_row["arch_io"] == 2  # The hit_vector value for io inside the function dict

    # 4. Verify Excluded Artifacts
    cursor.execute("SELECT * FROM excluded_artifacts")
    excluded = cursor.fetchone()
    assert excluded["file_path"] == "assets/logo.png"

    conn.close()


# ==============================================================================
# TEST 3: IDEMPOTENCY (THE CASCADE DELETE)
# ==============================================================================
def test_record_keeper_idempotency(keeper, mock_pipeline_state, tmp_path):
    """Proves that running the recorder twice for the same commit does not duplicate data."""
    db_path = tmp_path / "test_idempotency.sqlite"
    parsed, unparsable, summary, session = mock_pipeline_state

    # 1. Run the first time
    keeper.record_mission(parsed, unparsable, summary, session, str(db_path))
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM file_data")
    assert cursor.fetchone()[0] == 1

    # 2. Run the second time (simulating a re-run or failure recovery)
    keeper.record_mission(parsed, unparsable, summary, session, str(db_path))

    # 3. Verify there are still exactly 1 file (not 2)
    cursor.execute("SELECT COUNT(*) FROM file_data")
    assert cursor.fetchone()[0] == 1

    # 4. Verify children were cascade-deleted and cleanly re-inserted
    cursor.execute("SELECT COUNT(*) FROM function_data")
    assert cursor.fetchone()[0] == 1

    conn.close()


# ==============================================================================
# TEST 4: EMPTY STATE SURVIVABILITY
# ==============================================================================
def test_record_keeper_empty_state(keeper, tmp_path):
    """Proves the SQLite generator survives a completely empty repository without math faults."""
    db_path = tmp_path / "test_empty.sqlite"
    session = {"target": "EmptyProject", "git_audit": {}}

    keeper.record_mission([], [], {}, session, str(db_path))

    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM file_data")
    assert cursor.fetchone()[0] == 0
    
    cursor.execute("SELECT COUNT(*) FROM repo_data")
    assert cursor.fetchone()[0] == 1  # The repo row should exist, just filled with 0s

    conn.close()