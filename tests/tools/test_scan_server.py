"""tests/tools/scan_server.py scans as galaxy_ir.scan_to_db does, from one import of the engine."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cobol_mainframe"))

import scan_server as ss  # noqa: E402

from gitgalaxy.tools.cobol_to_cobol import galaxy_ir  # noqa: E402

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="the server forks (POSIX)")


@pytest.fixture
def repo(tmp_path):
    import test_galaxy_ir as g

    root = tmp_path / "legacy"
    g._write_fixture(root)
    return root


def _rows(db: Path) -> dict[str, list[str]]:
    """Every table's rows (order aside)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {n: sorted(map(repr, con.execute(f'SELECT * FROM "{n}"'))) for n in names}  # noqa: S608
    finally:
        con.close()


def test_a_scan_writes_what_the_engines_own_scan_writes(repo, tmp_path):
    """The master DB, every table and row, as the engine's own subprocess scan writes it."""
    real = galaxy_ir.scan_to_db(repo, tmp_path / "real")
    served = ss.scan_to_db(repo, tmp_path / "served")
    assert served.name == real.name and _rows(served) == _rows(real)


def test_each_scan_starts_from_the_same_state(repo, tmp_path):
    first = ss.scan_to_db(repo, tmp_path / "one")
    second = ss.scan_to_db(repo, tmp_path / "two")
    assert _rows(first) == _rows(second)
    assert len(ss._SERVER) == 1  # one server for both


def test_a_failing_scan_raises_as_the_engines_does(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        galaxy_ir.scan_to_db(tmp_path / "missing", tmp_path / "real")
    with pytest.raises(subprocess.CalledProcessError):
        ss.scan_to_db(tmp_path / "missing", tmp_path / "served")


def test_switched_off_or_gone_it_is_the_engines_own(repo, tmp_path, monkeypatch):
    calls = []
    real = galaxy_ir.scan_to_db
    monkeypatch.setattr(galaxy_ir, "scan_to_db", lambda *a, **k: calls.append(a) or real(*a, **k))
    monkeypatch.setenv(ss.ENV, "0")
    ss.scan_to_db(repo, tmp_path / "off")
    assert len(calls) == 1
    monkeypatch.delenv(ss.ENV)
    ss.scan_to_db(repo, tmp_path / "on")
    (server,) = ss._SERVER
    server.proc.kill()
    server.proc.wait()
    ss.scan_to_db(repo, tmp_path / "again")  # a dead server is started again
    assert len(calls) == 1 and ss._SERVER[0] is not server
