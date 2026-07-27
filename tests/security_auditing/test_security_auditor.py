import pytest
import numpy as np
from unittest.mock import patch

# We patch the schemas before importing so the Auditor doesn't fail on boot
MOCK_SCHEMAS = {"SIGNAL_SCHEMA": ["high_risk_execution", "io", "state_mutation", "safety", "dead_code", "structural_tab_indentations"]}

with patch("gitgalaxy.security.security_auditor.RECORDING_SCHEMAS", MOCK_SCHEMAS):
    from gitgalaxy.security.security_auditor import SecurityAuditor


@pytest.fixture
def mock_artifacts():
    """Provides a baseline payload with a circular dependency to test the graph resolver."""
    return [
        {
            "path": "src/main.py",
            "name": "main.py",
            "raw_imports": ["src/utils.py"],
            "telemetry": {"popularity": 5, "control_flow_ratio": 0.5},
            "hit_vector": [5, 2, 0, 0, 0, 0],  # High danger, some IO
            "file_impact": 0.8,
            "structural_mass": 0.9,  # High mass for shadow patch testing
            "coding_loc": 100,
        },
        {
            "path": "src/utils.py",
            "name": "utils.py",
            "raw_imports": ["src/main.py"],  # Circular loop!
            "telemetry": {"popularity": 1},
            "hit_vector": [0, 0, 0, 0, 0, 0],
            "file_impact": 0.2,
            "coding_loc": 20,
        },
    ]


# ==============================================================================
# TEST 1: DEPENDENCY GRAPH RESOLUTION (NetworkX vs Pure Python Deque)
# ==============================================================================
def test_dependency_graph_pure_python(mock_artifacts):
    """Proves the pure-Python O(1) Deque resolver survives circular dependencies."""
    auditor = SecurityAuditor()

    with patch("gitgalaxy.security.security_auditor.HAS_NETWORKX", False):
        resolved_artifacts = auditor._resolve_dependency_graph(mock_artifacts)

    main_artifact = next(s for s in resolved_artifacts if s["name"] == "main.py")
    assert "dependency_network" in main_artifact
    # The deque BFS considers the node itself as a visited descendant/ancestor in a circular loop
    assert main_artifact["dependency_network"]["total_upstream"] == 2
    assert main_artifact["dependency_network"]["total_downstream"] == 2


def test_dependency_graph_networkx(mock_artifacts):
    """Proves the C-optimized NetworkX resolver handles the exact same circular loop."""
    auditor = SecurityAuditor()

    with patch("gitgalaxy.security.security_auditor.HAS_NETWORKX", True):
        resolved_artifacts = auditor._resolve_dependency_graph(mock_artifacts)

    main_artifact = next(s for s in resolved_artifacts if s["name"] == "main.py")
    assert main_artifact["dependency_network"]["total_upstream"] == 1


# ==============================================================================
# TEST 2: PANDAS FEATURE MATRIX CONSTRUCTION
# ==============================================================================
def test_construct_feature_matrix(mock_artifacts):
    """Proves the matrix builder accurately maps artifact metrics to a Pandas DataFrame."""
    auditor = SecurityAuditor()

    # Explicitly inject the schema into the instance so the dictionary mapping works
    auditor.SIGNAL_SCHEMA = ["high_risk_execution", "io", "state_mutation", "safety", "dead_code"]
    auditor._resolve_dependency_graph(mock_artifacts)  # Pre-load graph data

    df = auditor._construct_feature_matrix(mock_artifacts)

    assert not df.empty
    assert len(df) == 2
    # Ensure the log_density math didn't crash
    assert "log_density_hit_high_risk_execution" in df.columns
    assert "log_logic_loc" in df.columns


def test_construct_feature_matrix_exception_fallback():
    """Proves a corrupted artifact payload generates a safe, empty fallback row."""
    auditor = SecurityAuditor()
    corrupted_artifacts = [{"path": "broken.py", "telemetry": "THIS_SHOULD_BE_A_DICT"}]

    df = auditor._construct_feature_matrix(corrupted_artifacts)
    assert not df.empty

    # Pandas get_dummies converts 'language' into 'language_unknown'
    assert "language_unknown" in df.columns
    assert df.iloc[0]["language_unknown"] in [True, 1]
    assert df.iloc[0]["structural_mass"] == 0.0


# ==============================================================================
# TEST 3: XGBOOST MULTICLASS INFERENCE & SHADOW PATCHES
# ==============================================================================
@patch("gitgalaxy.security.security_auditor.xgb.XGBClassifier")
def test_audit_repository_ml_inference(mock_xgb_class, mock_artifacts):
    """
    Proves the orchestrator successfully formats data, predicts Multiclass threats,
    and injects the Shadow Patch override when a heavy file mutates silently.
    """
    # 1. Setup the Mock Model
    mock_model = mock_xgb_class.return_value
    mock_model.feature_names_in_ = ["log_logic_loc", "log_density_hit_high_risk_execution"]

    # Predict probabilities for 2 files across 5 classes (0=Safe, 1=Botnet, 2=Trojan, etc)
    # File 1: 99% confident it's a Botnet (Class 1)
    # File 2: 99% confident it's Safe Code (Class 0)
    mock_model.predict_proba.return_value = np.array(
        [[0.01, 0.99, 0.0, 0.0, 0.0], [0.99, 0.01, 0.0, 0.0, 0.0]]
    )

    auditor = SecurityAuditor()
    auditor.model = mock_model  # Inject the mock model
    auditor.feature_names = mock_model.feature_names_in_

    # 2. Run the Audit WITH Shadow Patch enabled
    audited_artifacts = auditor.audit_repository(mock_artifacts, is_shadow_patch=True)

    main_artifact = audited_artifacts[0]
    utils_artifact = audited_artifacts[1]

    # 3. Assert Shadow Patch Override (main.py has structural_mass > 0.5)
    # Even though the model predicted Class 1 (Botnet), the Shadow Patch forces it to Class 2 (Trojan/Stealer)
    assert main_artifact["is_ml_threat"] is True
    assert (
        main_artifact["telemetry"]["domain_context"]["AI Threat Class"]
        == "Stealer / Trojan"
    )
    assert (
        "SHADOW PATCH: Hash mutated"
        in main_artifact["telemetry"]["domain_context"]["alert"]
    )

    # 4. Assert Safe File (utils.py)
    assert utils_artifact["is_ml_threat"] is False

    # 5. Regression test for #364: the producer must write "AI Threat Score",
    # not the near-miss "AI Threat Confidence" every consumer except
    # sarif_recorder.py used to fall through past. (100.0%, not 99.0%, because
    # the Shadow Patch override above also forces ml_score to 100.0.)
    assert main_artifact["telemetry"]["domain_context"]["AI Threat Score"] == "100.0%"
    assert "AI Threat Confidence" not in main_artifact["telemetry"]["domain_context"]


# ==============================================================================
# TEST 4: END-TO-END REGRESSION (#364 -- the real chain, not a hand-mocked one)
# ==============================================================================
@patch("gitgalaxy.security.security_auditor.xgb.XGBClassifier")
def test_ai_threat_score_survives_from_auditor_into_recorders(mock_xgb_class, mock_artifacts):
    """
    Every existing recorder test mocked "domain_context": {"AI Threat Score": ...}
    directly -- which meant they all quietly assumed the correct producer shape
    without ever exercising the real producer, and none of them would have caught
    #364 (the producer actually wrote "AI Threat Confidence"). This drives a REAL
    SecurityAuditor.audit_repository() artifact through the exact one-line reads
    gpu_recorder.py and record_keeper.py use, proving the real score -- not a
    0.0%/"0.0%" fallback -- survives into both.
    """
    mock_model = mock_xgb_class.return_value
    mock_model.feature_names_in_ = ["log_logic_loc", "log_density_hit_high_risk_execution"]
    mock_model.predict_proba.return_value = np.array(
        [[0.01, 0.99, 0.0, 0.0, 0.0], [0.99, 0.01, 0.0, 0.0, 0.0]]
    )

    auditor = SecurityAuditor()
    auditor.model = mock_model
    auditor.feature_names = mock_model.feature_names_in_

    audited_artifacts = auditor.audit_repository(mock_artifacts, is_shadow_patch=False)
    real_domain_context = audited_artifacts[0]["telemetry"]["domain_context"]

    # gpu_recorder.py's exact extraction (gitgalaxy/recorders/gpu_recorder.py:248)
    gpu_ai_score_str = real_domain_context.get("AI Threat Score", "0.0%")
    assert gpu_ai_score_str != "0.0%"
    assert float(gpu_ai_score_str.replace("%", "")) == 99.0

    # record_keeper.py's exact extraction (gitgalaxy/recorders/record_keeper.py:423-425)
    rk_ai_threat_str = real_domain_context.get("AI Threat Score", "0.0%")
    assert float(rk_ai_threat_str.replace("%", "")) == 99.0


# ==============================================================================
# TEST 4: FATAL DESYNC & EXCEPTION CATCHING
# ==============================================================================
@patch("gitgalaxy.security.security_auditor.xgb.XGBClassifier")
def test_audit_repository_fatal_desync(mock_xgb_class, mock_artifacts):
    """Proves the engine aborts cleanly if XGBoost returns the wrong number of rows."""
    mock_model = mock_xgb_class.return_value
    mock_model.feature_names_in_ = ["log_logic_loc"]

    # Return 1 prediction for 2 files (Fatal Desync)
    mock_model.predict_proba.return_value = np.array([[0.99, 0.01, 0.0, 0.0, 0.0]])

    auditor = SecurityAuditor()
    auditor.model = mock_model
    auditor.feature_names = mock_model.feature_names_in_

    # It should log the error and return the artifacts unmodified without crashing
    audited_artifacts = auditor.audit_repository(mock_artifacts)
    assert "is_ml_threat" not in audited_artifacts[0]


def test_audit_repository_no_model(mock_artifacts):
    """Proves the engine gracefully skips ML if the model file is missing."""
    auditor = SecurityAuditor(model_path="does_not_exist.json")

    # Should resolve graphs but skip ML
    audited_artifacts = auditor.audit_repository(mock_artifacts)
    assert "dependency_network" in audited_artifacts[0]
    assert "is_ml_threat" not in audited_artifacts[0]


# ==============================================================================
# TEST 5: THRESHOLD GATING & FALSE POSITIVE SUPPRESSION
# ==============================================================================
@patch("gitgalaxy.security.security_auditor.xgb.XGBClassifier")
def test_audit_repository_threshold_gating(mock_xgb_class, mock_artifacts):
    """Proves that a threat prediction below the strict AI_THREAT_THRESHOLD is safely ignored."""
    mock_model = mock_xgb_class.return_value
    mock_model.feature_names_in_ = ["log_logic_loc"]

    # Predict Class 1 (Botnet) with 85% confidence
    mock_model.predict_proba.return_value = np.array(
        [[0.15, 0.85, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0, 0.0]]
    )

    auditor = SecurityAuditor()
    auditor.model = mock_model
    auditor.feature_names = mock_model.feature_names_in_
    auditor.ai_threshold = 90.0  # Require 90% confidence minimum

    audited_artifacts = auditor.audit_repository(mock_artifacts)

    # 85% is less than 90%, so it should NOT be flagged as a threat
    assert audited_artifacts[0]["is_ml_threat"] is False
    assert audited_artifacts[1]["is_ml_threat"] is False


# ==============================================================================
# TEST 6: FEATURE MATRIX EXCLUSION LIST VERIFICATION
# ==============================================================================
def test_construct_feature_matrix_exclusion_list(mock_artifacts):
    """Ensures noisy signals (like indentation factions) are stripped before ML evaluation."""
    auditor = SecurityAuditor()
    auditor.SIGNAL_SCHEMA = ["high_risk_execution", "structural_tab_indentations"]
    
    # Inject the excluded signal into the mock artifact
    mock_artifacts[0]["hit_vector"] = [5, 100]

    auditor._resolve_dependency_graph(mock_artifacts)
    df = auditor._construct_feature_matrix(mock_artifacts)

    assert "log_density_hit_high_risk_execution" in df.columns
    assert "log_density_hit_structural_tab_indentations" not in df.columns, (
        "Exclusion list failed! Noisy signal leaked into the feature matrix."
    )


# ==============================================================================
# TEST 7: EMPTY STATE & VOID HANDLING
# ==============================================================================
def test_audit_repository_empty_state():
    """Proves the auditor safely exits without crashing if the repository has 0 artifacts."""
    auditor = SecurityAuditor()
    
    # Passing an empty array should instantly return an empty array
    result = auditor.audit_repository([])
    assert result == [], "Empty state handling failed!"

# ==============================================================================
# TEST 8: PANDAS NaN SPARSITY HANDLING (ZERO-DEPENDENCY MODE)
# ==============================================================================
def test_construct_feature_matrix_nan_handling(mock_artifacts):
    """
    Proves that missing columns (from Zero-Dependency mode) and Inf values 
    are properly converted to np.nan, preserving the native sparsity required 
    by XGBoost and preventing artificial data poisoning (Issue #98).
    """
    auditor = SecurityAuditor()
    
    # 1. Define a schema that includes a feature completely missing from the artifacts
    auditor.SIGNAL_SCHEMA = ["high_risk_execution"]
    auditor.feature_names = [
        "log_logic_loc",
        "log_density_hit_high_risk_execution",
        "missing_ml_feature",  # This column does NOT exist in the artifact data
        "ownership_entropy"    # Added so Pandas doesn't drop it during reindex
    ]
    
    # 2. Inject an intentional Infinity value to trigger the sanitization block
    # (e.g. simulating a division by zero that slipped through log1p)
    mock_artifacts[0]["telemetry"]["ownership_entropy"] = np.inf

    auditor._resolve_dependency_graph(mock_artifacts)
    df = auditor._construct_feature_matrix(mock_artifacts)

    # 3. Simulate the exact Pandas reindexing/sanitization logic from audit_repository()
    X = df.reindex(columns=auditor.feature_names, fill_value=np.nan)
    X = X.replace([np.inf, -np.inf], np.nan)

    # Assert 1: The missing feature was created but filled with NaN, NOT 0.0
    assert "missing_ml_feature" in X.columns
    assert np.isnan(X.iloc[0]["missing_ml_feature"]), (
        "Data Poisoning Bug! Missing features were forced to 0 instead of NaN."
    )

    # Assert 2: The infinite ownership_entropy was safely converted to NaN, NOT 0.0
    assert np.isnan(X.iloc[0]["ownership_entropy"]), (
        "Data Poisoning Bug! Infinity values were forced to 0 instead of NaN."
    )
    
    # Assert 3: Valid data remained perfectly intact
    assert X.iloc[0]["log_logic_loc"] > 0.0, "Valid data was accidentally wiped!"
    
# ==============================================================================
# TEST 9: SHADOW PATCH WHITESPACE GUARD (UNHAPPY PATH)
# ==============================================================================
@patch("gitgalaxy.security.security_auditor.xgb.XGBClassifier")
def test_shadow_patch_whitespace_guard(mock_xgb_class, mock_artifacts):
    """
    Proves that a file with a mutated hash (Shadow Patch) does NOT trigger 
    the malware override if its structural impact is too low (e.g., a simple whitespace change).
    """
    mock_model = mock_xgb_class.return_value
    mock_model.feature_names_in_ = ["log_logic_loc"]
    # Predict Safe Code (Class 0)
    mock_model.predict_proba.return_value = np.array([[0.99, 0.01, 0.0, 0.0, 0.0], [0.99, 0.01, 0.0, 0.0, 0.0]])
    
    auditor = SecurityAuditor()
    auditor.model = mock_model
    auditor.feature_names = ["log_logic_loc"]
    
    # Modify main.py to have almost zero structural mass (e.g., a whitespace change)
    mock_artifacts[0]["file_impact"] = 0.1
    
    # Run the audit with the Shadow Patch flag engaged
    audited = auditor.audit_repository(mock_artifacts, is_shadow_patch=True)
    
    # Because file_impact < 0.5, it should remain Safe Code, bypassing the Trojan override
    assert audited[0]["is_ml_threat"] is False, "Whitespace change was falsely flagged as a Shadow Patch Trojan!"

