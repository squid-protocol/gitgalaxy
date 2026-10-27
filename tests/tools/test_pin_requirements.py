# ruff: noqa: S101
"""Tests for tests/tools/pin_requirements.py."""

from __future__ import annotations

import os

import pytest

from tests.tools.pin_requirements import (
    find_uv,
    main,
    verify_multiversion_markers,
)


def _check_has_uv() -> bool:
    try:
        find_uv()
        return True
    except FileNotFoundError:
        return False


HAVE_UV = _check_has_uv()


@pytest.mark.skipif(not HAVE_UV, reason="uv executable not installed in this environment")
def test_find_uv():
    uv_bin = find_uv()
    assert os.path.isfile(uv_bin)
    assert os.access(uv_bin, os.X_OK)


def test_find_uv_not_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.setattr("pathlib.Path.is_file", lambda _self: False)
    with pytest.raises(FileNotFoundError, match="uv executable not found"):
        find_uv()


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


@pytest.mark.skipif(not HAVE_UV, reason="uv executable not installed in this environment")
def test_pin_requirements_check_all():
    rc = main(["--check", "--target", "all"])
    assert rc == 0


def test_lockfile_floor_is_python_311():
    """#3322: the universal compile floor is 3.11, and no lockfile keeps a <3.11 backport marker."""
    from pathlib import Path

    from tests.tools import pin_requirements as pr

    src = Path(pr.__file__).read_text(encoding="utf-8")
    assert '"--python-version",\n        "3.11",' in src
    stale = [
        p.as_posix()
        for d in (pr.CI_REQS, pr.TEMPLATE_REQS)
        for p in sorted(d.glob("*.txt"))
        if "python_full_version < '3.11'" in p.read_text(encoding="utf-8")
        or "python_full_version < '3.10" in p.read_text(encoding="utf-8")
    ]
    assert stale == []
