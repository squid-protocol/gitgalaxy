# ruff: noqa: S101, S603, S607
"""#7667: no tracked .py file uses syntax newer than the 3.11 floor.

A local 3.12 parses a backslash inside an f-string expression; the 3.11 CI legs raise SyntaxError. Ruff with
``--target-version py311`` reports that class (and other 3.12-only syntax) as ``invalid-syntax``.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ruff() -> list[str] | None:
    exe = shutil.which("ruff", path=str(Path(sys.executable).parent)) or shutil.which("ruff")
    return [exe] if exe else None


def _invalid_syntax(ruff: list[str], files: list[str]) -> list[str]:
    cmd = [*ruff, "check", "--isolated", "--no-cache", "--target-version", "py311"]
    cmd += ["--select", "F821", "--output-format", "concise", *files]
    out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False, encoding="utf-8")
    return [ln for ln in out.stdout.splitlines() if "invalid-syntax" in ln]


def _tracked_py() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO_ROOT, capture_output=True, text=True, check=True, encoding="utf-8"
    )
    return [f for f in out.stdout.split("\n") if f]


def test_flags_a_backslash_in_an_fstring_expression(tmp_path):
    ruff = _ruff()
    if ruff is None:
        pytest.skip("ruff not installed")
    bad = tmp_path / "bad.py"
    bad.write_text("x = f\"{'\\xe9'}\"\n", encoding="utf-8")
    assert _invalid_syntax(ruff, [str(bad)])


def test_no_tracked_file_needs_python_312():
    ruff = _ruff()
    if ruff is None:
        pytest.skip("ruff not installed")
    assert _invalid_syntax(ruff, _tracked_py()) == []
