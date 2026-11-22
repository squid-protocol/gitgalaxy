"""#8131: fidelity_table --check refuses a corpus checkout that is behind its main."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

# Loaded by path under a private name: `fidelity_table` is also the engine's generated module.
_spec = importlib.util.spec_from_file_location(
    "fidelity_table_generator", Path(__file__).resolve().parent / "fidelity_table.py"
)
ft = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ft)

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git not installed")


def _git(cwd, *args):
    subprocess.run(  # noqa: S603 -- fixed args
        [GIT, "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True
    )


def _repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a").write_text("1")
    _git(tmp_path, "add", "a")
    _git(tmp_path, "commit", "-qm", "one")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def test_corpus_at_main_is_usable(tmp_path):
    assert ft.behind_main(_repo(tmp_path)) == ""


def test_corpus_ahead_of_main_is_usable(tmp_path):
    _repo(tmp_path)
    (tmp_path / "b").write_text("2")
    _git(tmp_path, "add", "b")
    _git(tmp_path, "commit", "-qm", "two")
    assert ft.behind_main(tmp_path) == ""


def test_corpus_on_a_branch_without_main_is_refused(tmp_path):
    _repo(tmp_path)
    _git(tmp_path, "checkout", "-q", "--orphan", "feature")
    (tmp_path / "c").write_text("3")
    _git(tmp_path, "add", "c")
    _git(tmp_path, "commit", "-qm", "side")
    assert "does not contain origin/main" in ft.behind_main(tmp_path)


def test_non_git_corpus_is_accepted(tmp_path):
    assert ft.behind_main(tmp_path) == ""
