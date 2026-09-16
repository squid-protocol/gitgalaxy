"""#3028: optional dependencies are tracked per package, not through one global flag.

- Each ML package (numpy, pandas, xgboost) is detected and reported separately.
- The SQLite recorder NULLs the AI threat columns when XGBoost inference did not
  run, regardless of which other package made the scan zero-dependency.
- repo_data records which packages a snapshot lacked.
"""

import json
import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy import galaxyscope
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.security import security_auditor
from gitgalaxy.security.security_auditor import SecurityAuditor

ALL_PRESENT = dict.fromkeys(["HAS_TIKTOKEN", "HAS_NUMPY", "HAS_PANDAS", "HAS_XGBOOST", "HAS_PYYAML"], True)


def _missing_with(**overrides):
    flags = {**ALL_PRESENT, **overrides}
    with patch.multiple(galaxyscope, **flags):
        return galaxyscope.missing_dependencies()


# ==============================================================================
# DETECTION: one key per package
# ==============================================================================
def test_nothing_missing_is_not_zero_dependency():
    missing = _missing_with()
    assert not any(missing.values())


def test_missing_pandas_is_reported_as_pandas_not_xgboost():
    missing = _missing_with(HAS_PANDAS=False)
    assert [pkg for pkg, gone in missing.items() if gone] == ["pandas"]


def test_missing_numpy_is_reported_on_its_own_key():
    missing = _missing_with(HAS_NUMPY=False)
    assert missing["numpy"] and not missing["xgboost"]


def test_ml_available_requires_all_three_packages():
    assert security_auditor.ML_AVAILABLE == (
        security_auditor.HAS_NUMPY and security_auditor.HAS_PANDAS and security_auditor.HAS_XGBOOST
    )


def test_optional_import_returns_none_for_an_absent_module():
    assert security_auditor._optional_import("gitgalaxy_no_such_module_3028") is None


# ==============================================================================
# AUDITOR: inference_ran is True only after scores are written
# ==============================================================================
def test_inference_does_not_run_without_a_model():
    auditor = SecurityAuditor()
    auditor.model = None
    auditor.audit_repository([{"path": "a.py", "telemetry": {}}])
    assert auditor.inference_ran is False


def test_failed_inference_leaves_inference_ran_false():
    auditor = SecurityAuditor()
    auditor.model = object()  # any truthy model; the feature matrix build is made to fail
    with patch.object(SecurityAuditor, "_construct_feature_matrix", side_effect=RuntimeError("boom")):
        auditor.audit_repository([{"path": "a.py", "telemetry": {}}])
    assert auditor.inference_ran is False


# ==============================================================================
# RECORDER: AI columns follow inference, repo_data keeps the per-package map
# ==============================================================================
def _scored_file():
    return {
        "path": "src/app.py",
        "lang_id": "python",
        "is_ml_threat": True,
        "telemetry": {"domain_context": {"AI Threat Score": "91.5%", "AI Threat Class": "Dropper / Webshell"}},
    }


def _record(tmp_path, session_extra):
    db = tmp_path / "scan.db"
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, **session_extra}
    RecordKeeper().record_mission([_scored_file()], [], {}, session, str(db))
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT ai_threat_class, ai_threat_confidence, ai_threat_score, is_malware FROM file_data"
    ).fetchone()
    repo = conn.execute("SELECT is_zero_dependency_mode, missing_dependencies FROM repo_data").fetchone()
    conn.close()
    return row, repo


def test_real_scores_survive_a_zero_dependency_scan_missing_only_pyyaml(tmp_path):
    missing = {"tiktoken": False, "numpy": False, "pandas": False, "xgboost": False, "pyyaml": True}
    row, repo = _record(
        tmp_path, {"zero_dependency_mode": True, "missing_dependencies": missing, "ml_inference_ran": True}
    )
    assert row == ("Dropper / Webshell", 91.5, 91.5, 1)
    assert repo[0] == 1
    assert json.loads(repo[1]) == missing


@pytest.mark.parametrize("zero_dep", [True, False])
def test_ai_columns_are_null_when_inference_did_not_run(tmp_path, zero_dep):
    # zero_dep=False: full precision with no model file still has no real scores.
    row, _ = _record(tmp_path, {"zero_dependency_mode": zero_dep, "ml_inference_ran": False})
    assert row == (None, None, None, None)


def test_caller_without_the_key_keeps_its_values(tmp_path):
    row, repo = _record(tmp_path, {"zero_dependency_mode": False})
    assert row[2] == 91.5
    assert repo[1] is None


def test_existing_repo_data_table_gains_the_column(tmp_path):
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, "missing_dependencies": {"pyyaml": True}}
    db = tmp_path / "old.db"
    RecordKeeper().record_mission([_scored_file()], [], {}, session, str(db))
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE repo_data DROP COLUMN missing_dependencies")  # a pre-#3028 database
    conn.commit()
    conn.close()

    RecordKeeper().record_mission([_scored_file()], [], {}, session, str(db))

    conn = sqlite3.connect(db)
    stored = conn.execute("SELECT missing_dependencies FROM repo_data").fetchone()[0]
    conn.close()
    assert json.loads(stored) == {"pyyaml": True}
