"""#3028: optional dependencies are tracked per package, not through one global flag.

- Each optional package (tiktoken, PyYAML) is detected and reported separately.
- repo_data records which packages a snapshot lacked.
- #8430: the ML packages (numpy, pandas, xgboost) are no longer optional engines, so they are not reported.
"""

import json
import sqlite3
from unittest.mock import patch

from gitgalaxy import galaxyscope
from gitgalaxy.recorders.record_keeper import RecordKeeper

ALL_PRESENT = dict.fromkeys(["HAS_TIKTOKEN", "HAS_PYYAML"], True)


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


def test_missing_tiktoken_is_reported_on_its_own_key():
    missing = _missing_with(HAS_TIKTOKEN=False)
    assert [pkg for pkg, gone in missing.items() if gone] == ["tiktoken"]


def test_missing_pyyaml_is_reported_on_its_own_key():
    missing = _missing_with(HAS_PYYAML=False)
    assert [pkg for pkg, gone in missing.items() if gone] == ["pyyaml"]


def test_the_ml_packages_are_not_reported_any_more():
    assert set(_missing_with()) == {"tiktoken", "pyyaml"}


# ==============================================================================
# RECORDER: repo_data keeps the per-package map; no AI threat columns are written
# ==============================================================================
def _file():
    return {"path": "src/app.py", "lang_id": "python", "telemetry": {}}


def _record(tmp_path, session_extra):
    db = tmp_path / "scan.db"
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, **session_extra}
    RecordKeeper().record_mission([_file()], [], {}, session, str(db))
    conn = sqlite3.connect(db)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
    repo = conn.execute("SELECT is_zero_dependency_mode, missing_dependencies FROM repo_data").fetchone()
    conn.close()
    return columns, repo


def test_a_scan_missing_only_pyyaml_records_the_map(tmp_path):
    missing = {"tiktoken": False, "pyyaml": True}
    _, repo = _record(tmp_path, {"zero_dependency_mode": True, "missing_dependencies": missing})
    assert repo[0] == 1
    assert json.loads(repo[1]) == missing


def test_file_data_has_no_ai_threat_columns(tmp_path):
    columns, _ = _record(tmp_path, {"zero_dependency_mode": False})
    assert not {"ai_threat_class", "ai_threat_confidence", "ai_threat_score", "is_malware"} & columns


def test_caller_without_the_key_records_no_map(tmp_path):
    _, repo = _record(tmp_path, {"zero_dependency_mode": False})
    assert repo[1] is None


def test_existing_repo_data_table_gains_the_column(tmp_path):
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, "missing_dependencies": {"pyyaml": True}}
    db = tmp_path / "old.db"
    RecordKeeper().record_mission([_file()], [], {}, session, str(db))
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE repo_data DROP COLUMN missing_dependencies")  # a pre-#3028 database
    conn.commit()
    conn.close()

    RecordKeeper().record_mission([_file()], [], {}, session, str(db))

    conn = sqlite3.connect(db)
    stored = conn.execute("SELECT missing_dependencies FROM repo_data").fetchone()[0]
    conn.close()
    assert json.loads(stored) == {"pyyaml": True}
