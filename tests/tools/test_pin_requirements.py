"""Tests for tests/tools/pin_requirements.py."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.tools.pin_requirements import (
    find_uv,
    main,
    verify_multiversion_markers,
)


def test_find_uv():
    uv_bin = find_uv()
    assert os.path.isfile(uv_bin)
    assert os.access(uv_bin, os.X_OK)


def test_verify_multiversion_markers_valid():
    content = """# Valid lockfile
numpy==2.2.6 ; python_full_version < '3.11' \\
    --hash=sha256:abc
numpy==2.4.6 ; python_full_version == '3.11.*' \\
    --hash=sha256:def
numpy==2.5.4 ; python_full_version >= '3.12' \\
    --hash=sha256:ghi
pytest==8.3.4 \\
    --hash=sha256:jkl
"""
    errors = verify_multiversion_markers("test.txt", content)
    assert errors == []


def test_verify_multiversion_markers_detects_dependabot_flattening():
    # Dependabot compiling on python 3.12 without universal resolver produces this:
    content = """# Flattened lockfile from flat Dependabot bump
numpy==2.5.3 \\
    --hash=sha256:abc \\
    --hash=sha256:def
pytest==8.3.4 \\
    --hash=sha256:jkl
"""
    errors = verify_multiversion_markers("test.txt", content)
    assert len(errors) == 1
    assert "numpy is pinned to a single version (2.5.3) without python_full_version markers" in errors[0]


def test_verify_multiversion_markers_detects_missing_marker_in_multiversion():
    content = """# Multiple versions but one missing marker
numpy==2.2.6 ; python_full_version < '3.11' \\
    --hash=sha256:abc
numpy==2.5.4 \\
    --hash=sha256:def
"""
    errors = verify_multiversion_markers("test.txt", content)
    assert len(errors) == 1
    assert "numpy==2.5.4 has multiple versions but lacks python environment markers" in errors[0]


def test_verify_multiversion_markers_ignores_non_multiversion_packages():
    content = """# Standard lockfile
requests==2.32.3 \\
    --hash=sha256:abc
urllib3==2.2.3 \\
    --hash=sha256:def
"""
    errors = verify_multiversion_markers("test.txt", content)
    assert errors == []


def test_pin_requirements_check_all():
    rc = main(["--check", "--target", "all"])
    assert rc == 0
