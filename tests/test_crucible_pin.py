"""#3386: an off-pin language-crucible checkout fails with the exact fix command."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _crucible_pin
from _crucible_pin import ALLOW_UNPINNED_ENV, PINNED_TAG, pin_mismatch


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path):
    repo = tmp_path / "language-crucible"
    repo.mkdir()
    _git(repo, "init", "-q")
    for msg in ("old", "pinned"):
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", msg)
        _git(repo, "tag", "v0.0.1" if msg == "old" else PINNED_TAG)
    return repo


def test_on_pin_passes(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    assert pin_mismatch(_repo(tmp_path)) is None


def test_off_pin_names_the_checkout_command(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "v0.0.1")
    message = pin_mismatch(repo)
    assert "v0.0.1" in message
    assert f"git -C {repo} fetch --tags origin && git -C {repo} checkout {PINNED_TAG}" in message


def test_missing_pinned_tag_is_a_mismatch(tmp_path, monkeypatch):
    monkeypatch.delenv(ALLOW_UNPINNED_ENV, raising=False)
    monkeypatch.setattr(_crucible_pin, "PINNED_TAG", "v99.0.0")
    assert "v99.0.0" in pin_mismatch(_repo(tmp_path))


def test_escape_hatch_and_non_git_corpus_pass(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "v0.0.1")
    monkeypatch.setenv(ALLOW_UNPINNED_ENV, "1")
    assert pin_mismatch(repo) is None
    monkeypatch.delenv(ALLOW_UNPINNED_ENV)
    assert pin_mismatch(tmp_path / "unpacked-archive") is None
