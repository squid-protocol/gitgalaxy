"""#2986: the ML threat layer is unexercised (not exonerated) wherever no model runs.

No XGBoost model ships, so a scan reports its AI threat columns as NULL, never as a
clean 'Safe'. The boundary is documented in docs/zero_dependency_mode.md.
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.security.security_auditor import SecurityAuditor

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_COLUMNS = "ai_threat_class, ai_threat_confidence, ai_threat_score, is_malware"


def _artifacts():
    return [
        {
            "path": "src/main.py",
            "name": "main.py",
            "lang_id": "python",
            "raw_imports": [],
            "telemetry": {"popularity": 1},
            "hit_vector": [0] * 6,
            "file_impact": 0.2,
            "coding_loc": 20,
        }
    ]


def _recorded_columns(tmp_path, artifacts, inference_ran):
    db = tmp_path / "scan.db"
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, "ml_inference_ran": inference_ran}
    # The recorder reads the auditor's verdict (telemetry, is_ml_threat); the rest is
    # the minimal row shape test_per_package_dependencies.py also uses.
    rows = [
        {
            "path": a["path"],
            "lang_id": "python",
            "is_ml_threat": a.get("is_ml_threat", False),
            "telemetry": a["telemetry"],
        }
        for a in artifacts
    ]
    RecordKeeper().record_mission(rows, [], {}, session, str(db))
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT {AI_COLUMNS} FROM file_data").fetchone()
    finally:
        conn.close()


def test_no_model_scan_reads_unexercised_not_safe(tmp_path):
    # Same state as every public scan: the model file is absent.
    auditor = SecurityAuditor(model_path="does_not_exist_2986.json")
    audited = auditor.audit_repository(_artifacts())
    assert auditor.inference_ran is False
    assert "is_ml_threat" not in audited[0]
    assert _recorded_columns(tmp_path, audited, auditor.inference_ran) == (None, None, None, None)
    # The audit JSON must not read 0 infected files as a clean verdict either.
    out = tmp_path / "audit.json"
    AuditRecorder().generate_report(audited, [], {}, {}, {"ml_inference_ran": auditor.inference_ran}, str(out))
    ml = json.loads(out.read_text(encoding="utf-8"))["3. Forensic Security & Vulnerability Audit"]
    assert ml["ML Threat Intelligence (XGBoost)"]["Inference Ran"] is False


def test_scored_run_records_real_values(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    xgb = pytest.importorskip("xgboost")
    with patch.object(xgb, "XGBClassifier") as mock_class:
        model = mock_class.return_value
        model.feature_names_in_ = ["log_logic_loc"]
        model.predict_proba.return_value = np.array([[0.01, 0.99, 0.0, 0.0, 0.0]])
        auditor = SecurityAuditor(model_path="does_not_exist_2986.json")
        auditor.model = model
        auditor.feature_names = model.feature_names_in_
        audited = auditor.audit_repository(_artifacts())
    assert auditor.inference_ran is True
    row = _recorded_columns(tmp_path, audited, auditor.inference_ran)
    assert None not in row
    assert row[3] == 1


def test_boundary_is_documented_and_linked():
    doc = (REPO_ROOT / "docs" / "zero_dependency_mode.md").read_text(encoding="utf-8")
    assert "ML layer boundary for validation scans (#2986)" in doc
    for needle in ("not in this repository", "CVE-class", "unexercised, not exonerated", "ai_threat_score IS NULL"):
        assert needle in doc
    readme = (REPO_ROOT / "gitgalaxy" / "security" / "README.md").read_text(encoding="utf-8")
    assert "ML layer boundary" in readme


def test_full_extra_carries_every_package_the_ml_layer_needs():
    import tomllib

    extras = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]
    names = {spec.split(">")[0].split("=")[0].split("[")[0].strip().lower() for spec in extras["full"]}
    # XGBClassifier raises ImportError without scikit-learn, so the ML layer needs all four.
    assert {"xgboost", "scikit-learn", "pandas", "numpy"} <= names

    # CI installs the hash-locked set, not the extra: a lock without scikit-learn makes the real-model leg skip.
    for lock in ("engines.in", "engines.txt", "test.txt"):
        text = (REPO_ROOT / "ci" / "requirements" / lock).read_text(encoding="utf-8").lower()
        assert "scikit-learn" in text, lock
