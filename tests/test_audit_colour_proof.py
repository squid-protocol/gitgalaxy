"""#4551: the mypy/ruff audits must report known errors even when the caller forces colour."""

import importlib
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_baseline
import mypy_audit
import ruff_audit

COLOUR = {"FORCE_COLOR": "3", "MYPY_FORCE_COLOR": "1", "PY_COLORS": "1", "TERM": "xterm-256color"}


@pytest.fixture
def forced_colour(monkeypatch):
    for k, v in COLOUR.items():
        monkeypatch.setenv(k, v)


def test_strip_ansi_and_parser_accept_coloured_lines():
    line = "\x1b[1mpkg/m.py\x1b[m:3: \x1b[1m\x1b[31merror:\x1b[m bad  \x1b[33m[assignment]\x1b[m"
    assert "\x1b" not in lint_baseline.strip_ansi(line)
    assert len(mypy_audit.parse_mypy_output(line, Path("/nonexistent"))) == 1


@pytest.mark.skipif(shutil.which("mypy") is None, reason="mypy not installed")
def test_mypy_reports_known_error_under_forced_colour(forced_colour, tmp_path, monkeypatch):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text("x: int = 'not an int'\n")
    monkeypatch.setattr(mypy_audit, "SCAN_ROOT", pkg)
    monkeypatch.setattr(mypy_audit, "REPO_ROOT", tmp_path)
    findings = mypy_audit.run_mypy_findings()
    assert [f.code for f in findings.values()] == ["assignment"]


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_ruff_reports_known_error_under_forced_colour(forced_colour, tmp_path):
    (tmp_path / "m.py").write_text("import os\n")
    findings = ruff_audit.run_ruff_findings(tmp_path, tmp_path)
    assert [f.code for f in findings.values()] == ["F401"]


def test_unparsed_failure_is_loud():
    with pytest.raises(SystemExit):
        lint_baseline.require_parsed("mypy", "garbled output", 1, 0)
