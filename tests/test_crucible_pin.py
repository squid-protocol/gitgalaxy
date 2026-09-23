"""#3386: an off-pin language-crucible checkout fails with the exact fix command."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _crucible_pin

ALLOW_UNPINNED_ENV = _crucible_pin.ALLOW_UNPINNED_ENV


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path):
    repo = tmp_path / "language-crucible"
    repo.mkdir()
    _git(repo, "init", "-q")
    for msg in ("old", "pinned"):
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", msg)
        _git(repo, "tag", "v0.0.1" if msg == "old" else _crucible_pin.PINNED_TAG)
    return repo


def test_on_pin_passes(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    assert _crucible_pin.pin_mismatch(_repo(tmp_path)) is None


def test_off_pin_names_the_checkout_command(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "v0.0.1")
    message = _crucible_pin.pin_mismatch(repo)
    assert "v0.0.1" in message
    assert f"git -C {repo} fetch --tags origin && git -C {repo} checkout {_crucible_pin.PINNED_TAG}" in message


def test_missing_pinned_tag_is_a_mismatch(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    repo = _repo(tmp_path)
    monkeypatch.setattr(_crucible_pin, "PINNED_TAG", "v99.0.0")
    assert "v99.0.0" in _crucible_pin.pin_mismatch(repo)


def test_escape_hatch_and_non_git_corpus_pass(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "v0.0.1")
    monkeypatch.setenv(ALLOW_UNPINNED_ENV, "1")
    assert _crucible_pin.pin_mismatch(repo) is None
    monkeypatch.delenv(ALLOW_UNPINNED_ENV)
    assert _crucible_pin.pin_mismatch(tmp_path / "unpacked-archive") is None
