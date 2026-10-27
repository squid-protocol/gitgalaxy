# ruff: noqa: S101
"""#3322: every tool that pins a Python version agrees with the 3.11 floor."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _cfg():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_requires_python_is_311():
    assert _cfg()["project"]["requires-python"] == ">=3.11"


def test_ruff_targets_311():
    assert _cfg()["tool"]["ruff"]["target-version"] == "py311"


def test_mypy_targets_311():
    assert _cfg()["tool"]["mypy"]["python_version"] == "3.11"
