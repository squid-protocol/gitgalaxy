"""#4247: a regex timeout that excluded a file must make golden bless and check refuse.

A synthetic audit holds one file in the excluded queue with the engine's real timeout
reason; the guard, the bless script, the check test and crucible_check's exit code are
driven against it.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import golden_timeout_guard as guard
import test_golden_crucible as check_module
import update_golden_master as bless

QUEUE = guard.EXCLUDED_QUEUE_KEY


def _entry(path, reason):
    return {"Path": path, "Diagnostic Reason": reason, "Forensic Category": "Excluded Artifact"}


TIMEOUT = _entry("src/big_generated.c", "Unparsable (Structural Saturation / Global Regex Timeout)")
THREAD_TIMEOUT = _entry("lib/other.js", "Thread Timeout (Regex ReDoS)")
BLOCKED = _entry("PROVENANCE.json", "Blocked (Massive Static Asset Blob: 3156 LOC)")


def test_finds_both_engine_timeout_reasons_and_ignores_ordinary_exclusions():
    audit = {QUEUE: [BLOCKED, TIMEOUT, THREAD_TIMEOUT]}
    assert [p for p, _ in guard.timeout_exclusions(audit)] == ["src/big_generated.c", "lib/other.js"]


@pytest.mark.parametrize("audit", [{}, {QUEUE: []}, {QUEUE: [BLOCKED]}])
def test_clean_runs_pass(audit):
    assert guard.timeout_exclusions(audit) == []


def test_refusal_names_the_files_and_suggests_a_quieter_rerun():
    message = guard.refusal_message(guard.timeout_exclusions({QUEUE: [TIMEOUT]}), "bless", load=42.0)
    assert "src/big_generated.c" in message
    assert "quieter" in message and "42.0" in message


def _synthetic_audit(tmp_path):
    path = tmp_path / "data_galaxy_audit.json"
    path.write_text(json.dumps({"Audit Protocol": "x", QUEUE: [BLOCKED, TIMEOUT]}))
    return path


def test_check_fails_naming_the_timed_out_file(tmp_path):
    with pytest.raises(pytest.fail.Exception) as excinfo:
        check_module.test_golden_crucible_matches_baseline(_synthetic_audit(tmp_path))
    assert "src/big_generated.c" in str(excinfo.value)
    assert "Regex timeout exclusion" in str(excinfo.value)


@pytest.fixture
def bless_env(tmp_path, monkeypatch):
    """update_golden_master.main() with the scan replaced by the synthetic audit."""
    audit = _synthetic_audit(tmp_path)
    written = []
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(bless, "CRUCIBLE_DATA_PATH", tmp_path / "data")
    monkeypatch.setattr(bless, "pin_mismatch", lambda _p: None)
    monkeypatch.setattr(bless.golden_store, "write", lambda data, path: written.append(path))

    def fake_scan(cmd, **kwargs):
        out = Path(cmd[cmd.index("--output") + 1].rstrip("/"))
        (out / "data_galaxy_audit.json").write_text(audit.read_text())
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(bless.subprocess, "run", fake_scan)
    monkeypatch.delenv(guard.FORCE_ENV, raising=False)
    return written


def test_bless_refuses_and_writes_nothing(bless_env, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["update_golden_master.py", "--yes"])
    with pytest.raises(SystemExit) as excinfo:
        bless.main()
    assert excinfo.value.code == 1
    assert bless_env == []
    assert "src/big_generated.c" in capsys.readouterr().out


def test_bless_proceeds_only_when_forced(bless_env, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["update_golden_master.py", "--yes", "--allow-timeouts"])
    bless.main()
    assert len(bless_env) == 1
    assert "FORCED" in capsys.readouterr().out


def test_crucible_check_update_exits_nonzero_when_a_leg_refuses(tmp_path, monkeypatch):
    import crucible_check

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(sys, "argv", ["crucible_check.py", "--update", "--yes", "--mode", "full"])
    monkeypatch.setattr(crucible_check, "CRUCIBLE_PATH", tmp_path)
    monkeypatch.setattr(crucible_check, "_check_corpus_pin", lambda: True)
    monkeypatch.setattr(crucible_check, "ensure_venv", lambda _m: Path(sys.executable))
    monkeypatch.setattr(crucible_check, "_check_unsafe_corpus_path", lambda _p: None)
    monkeypatch.setattr(crucible_check, "run_update", lambda *a, **k: False)
    assert crucible_check.main() == 1
