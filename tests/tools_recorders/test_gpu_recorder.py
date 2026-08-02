import pytest
from gitgalaxy.recorders.gpu_recorder import GPURecorder


@pytest.fixture
def recorder():
    """Initializes the GPURecorder for WebGL payload generation testing."""
    return GPURecorder(version="6.3.2")


@pytest.fixture
def mock_pipeline_state():
    """Provides a standardized pipeline state for testing the columnar pivot."""
    # NOTE: The GPURecorder processes files in REVERSE order via .pop()
    # Index 0 in this list will become Index 1 in the output arrays.
    # Index 1 in this list will become Index 0 in the output arrays.
    artifacts = [
        {
            "path": "src/api/router.py",
            "name": "router.py",
            "lang_id": "python",
            "directory_group": "src/api",
            "total_loc": 200,
            "coding_loc": 150,
            "file_impact": 45.5,
            "raw_imports": ["src/db/models.py"],
            "telemetry": {
                "ownership": "BackendTeam",
                "archetype_fingerprint": {"API Controller": 0.2, "Data Model": 0.5},
                "domain_context": {"AI Threat Score": "95.5%"},
            },
            "functions": [
                {
                    "name": "process_request",
                    "loc": 50,
                    "branch": 10,
                    "impact": 15.0,
                    "start_line": 10,
                    "end_line": 60,
                }
            ],
        },
        {
            "path": "src/db/models.py",
            "name": "models.py",
            "lang_id": "python",
            "directory_group": "src/db",
            "total_loc": 50,
            "coding_loc": 40,
            "file_impact": 10.0,
            "raw_imports": [],
            "telemetry": {
                "ownership": "BackendTeam",
                "archetype_fingerprint": {"Data Model": 0.1},
                "domain_context": {"AI Threat Score": "10.0%"},
            },
            "functions": [],
        },
    ]

    excluded_artifacts = [
        {"path": "assets/logo.png", "reason": "Security Shielding (Format Excluded)", "size_bytes": 1024}
    ]

    summary = {"unparsable_files": {}}

    return artifacts, excluded_artifacts, summary


# ==============================================================================
# TEST 1: DESTRUCTIVE RAM EVICTION
# ==============================================================================
def test_destructive_ram_eviction(recorder, mock_pipeline_state):
    """
    Verifies Stage 3.3: Destructive RAM Eviction.
    Ensures the GPU Recorder physically destroys the input arrays via .pop()
    to free memory, preventing OOM crashes on massive enterprise repositories.
    """
    artifacts, excluded, summary = mock_pipeline_state

    # Verify they actually have data before we start
    assert len(artifacts) == 2
    assert len(excluded) == 1

    result = recorder.record_mission(
        parsed_files=artifacts,
        unparsable_files=excluded,
        summary=summary,
        repo_name="test_repo",
    )

    # A) Did it actually build the payload successfully?
    assert "galaxy" in result
    assert len(result["galaxy"]["paths"]) == 2

    # B) THE EVICTION CONTRACT: Are the original RAM arrays completely destroyed?
    assert len(artifacts) == 0, "FATAL: GPU Recorder failed to evict artifacts from RAM!"
    assert len(excluded) == 0, "FATAL: GPU Recorder failed to evict excluded artifacts from RAM!"


# ==============================================================================
# TEST 2: TEXT INTERNING & COMPRESSION
# ==============================================================================
def test_string_interning_compression(recorder, mock_pipeline_state):
    """
    Proves that repetitive strings (like languages and authors) are correctly
    interned into O(1) integer IDs to compress the final JSON payload.
    """
    artifacts, excluded, summary = mock_pipeline_state

    result = recorder.record_mission(artifacts, excluded, summary, "test")
    galaxy = result["galaxy"]
    lookups = result["meta"]["schemas"]["lookups"]

    # Both files are "python" and owned by "BackendTeam"
    assert len(lookups["languages"]) == 1
    assert lookups["languages"][0] == "python"
    assert galaxy["lang_ids"] == [0, 0]  # Both point to index 0

    assert len(lookups["authors"]) == 1
    assert lookups["authors"][0] == "BackendTeam"
    assert galaxy["tel_aid"] == [0, 0]


# ==============================================================================
# TEST 3: DEPENDENCY EDGE MAPPING & REVERSE ALIGNMENT
# ==============================================================================
def test_dependency_edge_mapping(recorder, mock_pipeline_state):
    """
    Proves that inbound and outbound edges are perfectly mapped,
    accounting for the reverse-index processing caused by the .pop() loop.
    """
    artifacts, excluded, summary = mock_pipeline_state

    result = recorder.record_mission(artifacts, excluded, summary, "test")
    galaxy = result["galaxy"]

    # WebGL requires:
    # models.py is popped first -> becomes Output Index 0
    # router.py is popped second -> becomes Output Index 1
    assert galaxy["names"][0] == "models.py"
    assert galaxy["names"][1] == "router.py"

    # router.py (Idx 1) imports models.py (Idx 0)
    # Therefore, router.py's outbound edge should point to 0
    assert galaxy["outbound_edges"][1] == [0]

    # And models.py's inbound edge should point to 1
    assert galaxy["edges"][0] == [1]


# ==============================================================================
# TEST 4: AI THREAT SCORE QUANTIZATION
# ==============================================================================
def test_ai_threat_score_quantization(recorder, mock_pipeline_state):
    """
    Proves that XGBoost AI Threat Scores are safely stripped of their percentage
    signs and quantized into integer arrays for WebGL processing.
    """
    artifacts, excluded, summary = mock_pipeline_state

    result = recorder.record_mission(artifacts, excluded, summary, "test")
    galaxy = result["galaxy"]

    # models.py (Idx 0) had "10.0%" -> Quantized to 10000
    assert galaxy["ai_threats"][0] == 10000

    # router.py (Idx 1) had "95.5%" -> Quantized to 95500
    assert galaxy["ai_threats"][1] == 95500


# ==============================================================================
# TEST 5: FUNCTION CSR FLATTENING (Compressed Sparse Row)
# ==============================================================================
def test_function_csr_flattening(recorder, mock_pipeline_state):
    """
    Proves the nested functions dictionary is correctly flattened into the
    `satellite_data_flat` array (groups of 10 data points), and that
    `satellite_offsets` accurately tracks the boundaries for the WebGL shader.
    """
    artifacts, excluded, summary = mock_pipeline_state

    result = recorder.record_mission(artifacts, excluded, summary, "test")
    galaxy = result["galaxy"]

    # models.py (Idx 0) has 0 functions.
    # router.py (Idx 1) has 1 function (10 flattened parameters).

    assert len(galaxy["satellite_data_flat"]) == 10
    assert galaxy["satellite_data_flat"][0] == "process_request"  # The name
    assert galaxy["satellite_data_flat"][1] == 50  # The LOC

    # The offsets array tracks the *cumulative* function count at each file index.
    # Start: [0]
    # After models.py (0 funcs): [0, 0]
    # After router.py (1 func): [0, 0, 1]
    assert galaxy["satellite_offsets"] == [0, 0, 1]


# ==============================================================================
# TEST 6: UNSCANNED ARTIFACT FALLBACK (ISSUE #100)
# ==============================================================================
def test_unscanned_risk_vector_fallback(recorder, mock_pipeline_state):
    """
    Proves that artifacts missing a risk_vector (due to parser bypass or
    Zero-Dependency mode) default to -1.0 (quantized to -10) rather than 0.0.
    This prevents the WebGL engine from fabricating a 'Safe' visual state.
    """
    artifacts, excluded, summary = mock_pipeline_state

    # Explicitly ensure the mock artifacts have NO risk vector
    for artifact in artifacts:
        artifact.pop("risk_vector", None)

    result = recorder.record_mission(artifacts, excluded, summary, "test")
    galaxy = result["galaxy"]

    # Since both files lack a risk vector, EVERY entry in the flattened risk
    # array must be exactly -10 (which represents -1.0 in the WebGPU shader).
    risks_flat = galaxy["risks_flat"]

    assert len(risks_flat) > 0, "Flat risk array should not be empty!"
    assert all(val == -10 for val in risks_flat), (
        "FATAL: Recorder injected 0.0 instead of -10 for missing risk vectors!"
    )
