import json
from unittest.mock import patch

import pytest

from gitgalaxy.recorders.audit_recorder import AuditRecorder


@pytest.fixture
def recorder():
    """Initializes the AuditRecorder for forensic JSON generation testing."""
    # We patch the schema dynamically so our tests are immune to upstream schema changes
    mock_schemas = {
        "RISK_SCHEMA": ["secrets_risk", "tech_debt"],
        "SIGNAL_SCHEMA": ["sec_hardcoded_secrets", "sec_high_risk_execution"],
        "EXPOSURE_LABELS": {
            "secrets_risk": "Secrets Risk Exposure",
            "tech_debt": "Tech Debt Exposure",
        },
    }
    with patch("gitgalaxy.recorders.audit_recorder.config.RECORDING_SCHEMAS", mock_schemas):
        yield AuditRecorder()  # <--- CHANGED TO YIELD


# ==============================================================================
# TEST 1: TERMINOLOGY TRANSLATION & DESCALING
# ==============================================================================
def test_audit_recorder_format_label_and_descale(recorder):
    """Proves the recorder correctly strips internal suffixes and scales metrics."""
    assert recorder.format_label("raw_cognitive_complexity_x10") == "Raw Cognitive Complexity"
    assert recorder.descale("metric_x1000", 5500) == 5.5
    assert recorder.descale("metric_x10", 25) == 2.5
    assert recorder.descale("standard_metric", 10) == 10


# ==============================================================================
# TEST 2: FORENSIC JSON PAYLOAD (ML THREATS & BYPASSES)
# ==============================================================================
def test_audit_recorder_generate_ml_threat_report(recorder, tmp_path):
    """
    Proves the recorder prioritizes ML threats, processes Parser Bypasses,
    and correctly maps 'System Purpose'.
    """
    output_file = tmp_path / "forensic_ml_audit.json"

    mock_parsed = [
        {
            "path": "src/core/auth.py",
            "name": "auth.py",
            "lang_id": "python",
            "directory_group": "src/core",
            "telemetry": {
                "domain_context": {"Purpose": "Handles JWT Validation", "AI Threat Score": "99.9%"},
            },
            "is_ml_threat": True,
            "risk_vector": [10.0, 50.0, 0.0],
            "hit_vector": [1, 1],
            "total_loc": 150,
        }
    ]

    mock_unparsable = [
        {
            "path": "configs/secret.key",
            "reason": "Security Shielding (Format Excluded)",
            "size_bytes": 2048,
            "identity_confidence": 1.0,
        }
    ]

    mock_summary = {
        "directory_groups": {"src/core": {"total_mass": 45.5, "file_count": 1}},
        "unparsable_files": {"unparsable_artifacts": ["dist/bundle.min.js"]},
    }

    mock_session = {"engine": "Test", "target_directory": str(tmp_path)}

    recorder.generate_report(mock_parsed, mock_unparsable, mock_summary, {}, mock_session, str(output_file))

    with open(output_file, encoding="utf-8") as f:
        payload = json.load(f)

    # Validate File Identity overrides
    artifact = payload["6. Parsed Files (Scanned Artifacts)"]["src/core"]["Files"]["src/core/auth.py"]
    assert artifact["1. Artifact Identity"]["System Purpose"] == "Handles JWT Validation"

    # Validate Unparsable formatting
    unparsable = payload["5. Unparsable Artifacts (Excluded Artifacts Queue)"]
    assert len(unparsable) == 2
    assert unparsable[1]["Forensic Category"] == "Parser Bypass"

    # Validate ML Threat Supremacy
    security = payload["3. Forensic Security & Vulnerability Audit"]
    assert security["Audit Status"] == "ML_CONFIRMED_THREAT_DETECTED"
    assert security["ML Threat Intelligence (XGBoost)"]["Infected Files Detected"] == 1


# ==============================================================================
# TEST 3: RULE-BASED THREAT FALLBACK
# ==============================================================================
def test_audit_recorder_rule_based_threat_routing(recorder, tmp_path):
    """
    Proves that if XGBoost clears a file, but the rule-based engine flags a
    quarantined hardcoded secret, the Audit Status downgrades to Rule-Based safely.
    """
    output_file = tmp_path / "forensic_rule_audit.json"

    mock_parsed = [
        {
            "path": "src/hardcoded.py",
            "telemetry": {
                "domain_context": {
                    "alert": "CRITICAL LEAK BYPASS",
                    # #374: the real key signal_processor.py's ghost_meta spread
                    # produces is "reason" (aperture.py), not "aperture_reason".
                    "reason": "CRITICAL LEAK (Exposed Secret: 'hardcoded.py')",
                }
            },
            "is_ml_threat": False,  # ML missed it or deemed it safe
            "risk_vector": [100.0, 50.0, 0.0],  # 100% Secrets Risk
        }
    ]

    recorder.generate_report(mock_parsed, [], {}, {}, {}, str(output_file))

    with open(output_file, encoding="utf-8") as f:
        payload = json.load(f)

    security = payload["3. Forensic Security & Vulnerability Audit"]
    assert security["Audit Status"] == "CRITICAL_THREATS_DETECTED (Rule-Based)"
    quarantined = security["Exposed Secrets & Credentials (Quarantined Files)"]
    assert len(quarantined) == 1
    assert "CRITICAL LEAK (Exposed Secret: 'hardcoded.py')" in quarantined[0]["Diagnostic"], (
        "Diagnostic must surface the real Aperture reason text, not the 'Manual Bypass' fallback!"
    )


# ==============================================================================
# TEST 4: INDENTATION FACTION & DOC SYNTHESIS
# ==============================================================================
def test_audit_recorder_formatting_edge_cases(recorder, tmp_path):
    """
    Proves the recorder dynamically pads missing Markdown risk vectors to prevent
    dimension desyncs, and surfaces indentation_style telemetry as-is (#1147:
    indentation is descriptive identity, not a risk exposure to translate).
    """
    output_file = tmp_path / "forensic_edge_cases.json"

    mock_parsed = [
        {
            "path": "README.md",
            "lang_id": "markdown",
            "risk_vector": [],  # Pipeline stripped the vector because it's text
            "telemetry": {},
        },
        {
            "path": "src/tabs.py",
            "lang_id": "python",
            "risk_vector": [0.0, 0.0],
            "telemetry": {"indentation_style": "Tabs"},
        },
        {
            "path": "src/spaces.py",
            "lang_id": "python",
            "risk_vector": [0.0, 0.0],
            "telemetry": {"indentation_style": "Spaces"},
        },
    ]

    recorder.generate_report(mock_parsed, [], {}, {}, {}, str(output_file))

    with open(output_file, encoding="utf-8") as f:
        payload = json.load(f)

    files = payload["6. Parsed Files (Scanned Artifacts)"]["__monolith__"]["Files"]

    # 1. Verify Missing Vector Strict Labeling (Issue #100)
    # Because README.md has no risk_vector, it MUST be explicitly labeled as unscanned
    readme = files["README.md"]["4. Vulnerability & Risk Exposures"]
    assert len(readme) == 2, "Failed to map the missing markdown risk vector!"
    assert readme["Secrets Risk Exposure"] == "[UNSCANNED - NO DATA]", "Failed to flag missing risk as unscanned!"

    # 2. Verify indentation_style telemetry surfaces as plain identity, not a risk exposure
    assert files["src/tabs.py"]["1. Artifact Identity"]["Indentation Style"] == "Tabs"
    assert files["src/spaces.py"]["1. Artifact Identity"]["Indentation Style"] == "Spaces"


# ==============================================================================
# TEST 5: EMPTY STATE / VOID HANDLING
# ==============================================================================
def test_audit_recorder_empty_state(recorder, tmp_path):
    """Proves the JSON generator survives a completely empty repository."""
    output_file = tmp_path / "forensic_empty.json"

    # Pass completely empty arrays and dictionaries
    recorder.generate_report([], [], {}, {}, {}, str(output_file))

    assert output_file.exists(), "Recorder crashed on an empty repository state!"

    with open(output_file, encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["6. Parsed Files (Scanned Artifacts)"] == {}
    assert payload["3. Forensic Security & Vulnerability Audit"]["Audit Status"] == "SECURE_NO_THREATS_DETECTED"
