import json
import sqlite3
import pytest
from unittest.mock import patch
from gitgalaxy.recorders.llm_recorder import LLMRecorder


@pytest.fixture
def recorder():
    """Initializes the LLMRecorder with a controlled schema for deterministic testing."""
    mock_schemas = {
        "RISK_SCHEMA": ["tech_debt", "cognitive_load", "state_flux"],
        "SIGNAL_SCHEMA": ["high_risk_execution", "io", "prompt_injection"],
        "EXPOSURE_LABELS": {"tech_debt": "Tech Debt Exposure", "cognitive_load": "Cognitive Load Exposure"},
    }
    with patch("gitgalaxy.recorders.llm_recorder.config.RECORDING_SCHEMAS", mock_schemas):
        yield LLMRecorder()


@pytest.fixture
def mock_pipeline_state():
    """Provides a comprehensive, standardized pipeline state for the recorder to consume."""
    parsed_files = [
        {
            "path": "src/api/handler.py",
            "name": "handler.py",
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
                "domain_context": {"purpose": "Routes external traffic", "AI Threat Score": "95.5%"},
            },
            "is_ml_threat": True,
            "risk_vector": [80.0, 60.0, 10.0],  # debt, cog_load, flux
            "hit_vector": [2, 5, 1],  # danger, io, prompt_injection
            "functions": [
                {
                    "name": "process_request",
                    "type_id": "function",
                    "loc": 50,
                    "impact": 15.0,
                    "big_o_depth": 2,
                    "is_recursive": False,
                    "docstring": "Handles incoming API requests.",
                    "calls_out_to": ["validate_token"],
                }
            ],
        },
        {
            "path": "src/db/models.py",
            "name": "models.py",
            "lang_id": "python",
            "directory_group": "src/db",
            "lock_tier": 1,
            "total_loc": 50,
            "coding_loc": 40,
            "file_impact": 10.0,
            "raw_imports": [],
            "telemetry": {"popularity": 1},
            "is_ml_threat": False,
            "risk_vector": [10.0, 10.0, 5.0],
            "hit_vector": [0, 0, 0],
            "functions": [],
        },
    ]

    unparsable_files = [
        {"path": "assets/logo.png", "reason": "Security Shielding (Format Excluded)", "size_bytes": 1024}
    ]

    summary = {
        "summary": {
            "total_files": 3,
            "verified_files": 2,
            "total_loc": 250,
            "volatility_index": 1.5,
            "Percent_Visible": 66.6,
            "dominant_language": "python",
        },
        "composition": {"python": {"files": 2, "loc": 250}},
        "repo_macro_species": {"name": "Web Service", "z_score": 1.2},
        "directory_groups": {
            "src/api": {"total_mass": 45.5, "file_count": 1, "avg_exposures": {"cognitive_load": 60.0}},
            "src/db": {"total_mass": 10.0, "file_count": 1, "avg_exposures": {"cognitive_load": 10.0}},
        },
        "ecosystem_fingerprint": {
            "ml_clusters": {"Controller": {"count": 1, "pct": 50.0}},
            "static_mass": {"Data Model": {"count": 1, "pct": 50.0}},
        },
        "network_macro": {
            "modularity": 0.8,
            "assortativity": 0.5,
            "cyclic_density": 0.0,
            "avg_path_length": 1.0,
            "articulation_points": 1,
        },
    }

    session_meta = {
        "engine": "GitGalaxy Unit Test",
        "target": "TestProject",
        "target_directory": "/mock/path",
        "timestamp": "2026-06-18T12:00:00Z",
        "duration_seconds": 2.5,
        "zero_dependency_mode": True,
        "git_audit": {"branch": "main", "commit_hash": "a1b2c3d4", "remote_url": "git@github.com:test/repo.git"},
    }

    return parsed_files, unparsable_files, summary, session_meta


# ==============================================================================
# TEST 1: THREAT SCORE PARSING
# ==============================================================================
def test_parse_threat_score(recorder):
    """Proves the string-to-float conversion for ML Threat Scores is fault-tolerant."""
    valid_artifact = {"telemetry": {"domain_context": {"AI Threat Score": "85.5%"}}}
    empty_artifact = {}
    corrupted_artifact = {"telemetry": {"domain_context": {"AI Threat Score": "NotANumber%"}}}

    assert recorder._parse_threat_score(valid_artifact) == (85.5, "85.5%")
    assert recorder._parse_threat_score(empty_artifact) == (0.0, "0.0%")
    assert recorder._parse_threat_score(corrupted_artifact) == (0.0, "NotANumber%")


# ==============================================================================
# TEST 2: MARKDOWN GENERATION & FORMATTING
# ==============================================================================
def test_build_markdown_generates_context(recorder, mock_pipeline_state):
    """Proves the Markdown builder successfully weaves data into LLM context chunks."""
    parsed, unparsable, summary, session = mock_pipeline_state

    # Updated to match the new 6-parameter signature
    md_text = recorder._build_markdown(parsed, unparsable, summary, session, {})

    # 1. Verify Zero-Dependency Warning Injection
    assert "ZERO-DEPENDENCY MODE ACTIVE" in md_text

    # 2. Verify ML Threat Billboard
    assert "ML_CONFIRMED_THREAT_DETECTED" in md_text
    assert "XGBoost Structural Signatures model identified 1 malicious artifacts" in md_text

    # 3. Verify Risk Distributions
    assert "Tech Debt Exposure" in md_text

    # 4. Verify Architectural Choke Points
    assert "Top I/O Latency Risks" in md_text
    assert "src/api/handler.py" in md_text  # Our mock file has I/O hits

    # 5. Verify Prompt Injection / Agentic RCE surfacing
    assert "Prompt Injection Surface" in md_text


def test_house_of_cards_section_reads_fragile_dependency_chain(recorder, mock_pipeline_state):
    """
    Regression test for #370: the "House of Cards" section used to read
    sys_bots.get("house_of_cards", []) -- a key signal_processor.py's real
    bottleneck detector never produces (its actual key is
    "fragile_dependency_chain"). Proves a real fragile_dependency_chain
    entry now renders in that section.
    """
    parsed, unparsable, summary, session = mock_pipeline_state

    forensic_report = {
        "systemic_bottlenecks": {
            "fragile_dependency_chain": [
                {"path": "src/core/config_loader.py", "score": 12.5, "close": 0.8, "err": 15.6}
            ],
        }
    }

    md_text = recorder._build_markdown(parsed, unparsable, summary, session, forensic_report)

    assert "House of Cards" in md_text
    assert "src/core/config_loader.py" in md_text
    assert "Severity: 12.5" in md_text


# ==============================================================================
# TEST 3: SQLITE KNOWLEDGE GRAPH GENERATION
# ==============================================================================
def test_generate_sqlite_graph(recorder, mock_pipeline_state, tmp_path):
    """Proves the SQLite builder correctly provisions tables and inserts schema-aligned data."""
    parsed, _, summary, session = mock_pipeline_state
    db_path = tmp_path / "test_graph.sqlite"
    inbound_map = {"src/db/models.py": ["src/api/handler.py"]}

    # Execute DB Generation
    recorder._generate_sqlite_graph(parsed, summary, session, db_path, inbound_map)

    assert db_path.exists(), "SQLite database file was not created!"

    # Connect and Verify Schema & Data Integrity
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verify Meta Table
    cursor.execute("SELECT value FROM meta WHERE key='project'")
    assert cursor.fetchone()[0] == "TestProject"

    # Verify Artifacts Table
    cursor.execute("SELECT filename, lock_tier, tech_debt FROM artifacts")
    artifacts = cursor.fetchall()
    assert len(artifacts) == 2
    assert ("handler.py", 0, 80.0) in artifacts

    # Verify Directory Groups Table
    cursor.execute("SELECT name, file_count, total_mass FROM directory_groups")
    groups = cursor.fetchall()
    assert len(groups) == 2
    assert ("src/api", 1, 45.5) in groups

    # Verify Functions Table & JSON Serialization
    cursor.execute("SELECT name, big_o_depth, calls_out_to FROM functions")
    functions = cursor.fetchall()
    assert len(functions) == 1
    assert functions[0][0] == "process_request"
    assert functions[0][1] == 2
    assert "validate_token" in json.loads(functions[0][2])

    # Verify Dependency Network Links (Updated to artifact_id)
    cursor.execute("SELECT imported_path FROM outbound_dependencies WHERE artifact_id=1")
    assert cursor.fetchone()[0] == "src/db/models.py"

    conn.close()


# ==============================================================================
# TEST 4: EMPTY STATE & VOID HANDLING
# ==============================================================================
def test_llm_recorder_empty_state(recorder, tmp_path):
    """Proves the generator survives an empty repository without math/division errors."""
    output_md = tmp_path / "EmptyProject_galaxy_llm.md"
    output_db = tmp_path / "EmptyProject_galaxy_graph.sqlite"
    session = {"target": "EmptyProject"}

    # Passing empty lists/dicts
    recorder.generate_artifacts(
        parsed_files=[], unparsable_files=[], summary={}, session_meta=session, output_dir=str(tmp_path)
    )

    assert output_md.exists()
    assert output_db.exists()

    # Verify Markdown handled empty lists gracefully
    with open(output_md, "r", encoding="utf-8") as f:
        content = f.read()
        assert "SECURE_NO_THREATS_DETECTED" in content
        assert "*No complex functions detected.*" in content


# ==============================================================================
# TEST 5: FULL INTEGRATION PIPELINE
# ==============================================================================
def test_generate_artifacts_integration(recorder, mock_pipeline_state, tmp_path):
    """Proves the main entry point orchestrates both artifact generation sequences."""
    parsed, unparsable, summary, session = mock_pipeline_state

    recorder.generate_artifacts(
        parsed_files=parsed,
        unparsable_files=unparsable,
        summary=summary,
        session_meta=session,
        output_dir=str(tmp_path),
        forensic_report={"systemic_bottlenecks": {}},
    )

    assert (tmp_path / "TestProject_galaxy_llm.md").exists()
    assert (tmp_path / "TestProject_galaxy_graph.sqlite").exists()
