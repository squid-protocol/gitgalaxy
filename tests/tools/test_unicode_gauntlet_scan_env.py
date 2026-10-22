"""The gauntlet runs --jobs scans at once, so each scan must stay single-worker (#4896, #3913)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unicode_gauntlet as ug  # noqa: E402


def _scan_env(monkeypatch, tmp_path, preset=None):
    import scan_server as ir  # #5882: the scan_to_db unicode_gauntlet.scan calls

    seen = {}

    def fake(estate, out, extra_args=()):
        import os

        seen["workers"] = os.environ.get("GALAXYSCOPE_MAX_WORKERS")
        return out

    monkeypatch.setattr(ir, "scan_to_db", fake)
    monkeypatch.delenv("GALAXYSCOPE_MAX_WORKERS", raising=False)
    if preset:
        monkeypatch.setenv("GALAXYSCOPE_MAX_WORKERS", preset)
    ug.scan(tmp_path / "e__utf-8", tmp_path / "out")
    return seen["workers"]


def test_scan_env_pins_one_worker(monkeypatch, tmp_path):
    assert _scan_env(monkeypatch, tmp_path) == "1"


def test_scan_env_respects_explicit_value_and_restores(monkeypatch, tmp_path):
    import os

    assert _scan_env(monkeypatch, tmp_path, preset="3") == "3"
    assert os.environ["GALAXYSCOPE_MAX_WORKERS"] == "3"


def test_scan_env_does_not_leak(monkeypatch, tmp_path):
    import os

    _scan_env(monkeypatch, tmp_path)
    assert "GALAXYSCOPE_MAX_WORKERS" not in os.environ
