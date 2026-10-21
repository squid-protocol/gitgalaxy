"""#5500: crucible_path_check runs its two scans together and still reports every kind of difference."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crucible_path_check as cpc  # noqa: E402


def _run(monkeypatch, tmp_path, fake_scan):
    corpus = tmp_path / "data"
    corpus.mkdir()
    (corpus / "a.txt").write_text("x")
    monkeypatch.setattr(cpc, "scan", fake_scan)
    return cpc.main(["--corpus", str(corpus), "--work-dir", str(tmp_path)])


def test_the_two_scans_overlap(monkeypatch, tmp_path):
    barrier = threading.Barrier(2, timeout=10)

    def fake(target, out):
        barrier.wait()  # raises BrokenBarrierError unless the other scan is running at the same time
        return {"k": 1}, None

    assert _run(monkeypatch, tmp_path, fake) == 0


def test_a_differing_side_fails(monkeypatch, tmp_path, capsys):
    def fake(target, out):
        return {"k": 2 if "docs" in target.parts else 1}, None

    assert _run(monkeypatch, tmp_path, fake) == 1
    assert "FAIL" in capsys.readouterr().out


def test_an_unreadable_side_fails_even_when_audits_match(monkeypatch, tmp_path, capsys):
    def fake(target, out):
        return {"k": 1}, ("OSError: boom" if "docs" in target.parts else None)

    assert _run(monkeypatch, tmp_path, fake) == 1
    assert "scan outputs" in capsys.readouterr().out


def test_identical_sides_pass(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, lambda target, out: ({"k": 1}, None)) == 0
