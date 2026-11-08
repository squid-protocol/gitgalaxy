"""#8074: the no-.git fallback walk judged DIRECTORIES with the file extension gates, so a z/OS
dataset-name directory (`FAKE.APP.COPYLIB`, whose "extension" is `.copylib`) was pruned with its whole
subtree, silently: no copybook reached the scan and `COPY` stayed unresolved. Directories are now pruned
by path rules only (ignored / hidden / vendored), and files are judged one by one, as the git census does."""

import subprocess

import pytest

from gitgalaxy.galaxyscope import Orchestrator
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_CONFIG = {"LANGUAGE_DEFINITIONS": LANGUAGE_DEFINITIONS, "APERTURE_CONFIG": APERTURE_CONFIG}

DATASET_SUFFIXES = ["COPYLIB", "DBRMLIB", "PROCLIB", "MACLIB", "SRCLIB", "CPYLIB", "LOADLIB", "INCLUDE"]

PROGRAM = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       PROCEDURE DIVISION.\n           COPY FAKECPY.\n           GOBACK.\n"
COPYBOOK = "       01  FAKE-REC.\n           05  FAKE-ID   PIC X(8).\n"


def _build(root, dirname):
    d = root / dirname
    d.mkdir(parents=True)
    (d / "FAKECPY.cpy").write_text(COPYBOOK, encoding="utf-8")
    (d / "FAKEPGM.cbl").write_text(PROGRAM, encoding="utf-8")
    return d


def _census(root):
    scope = Orchestrator(str(root), _CONFIG)
    scope._build_file_census()
    return set(scope.stem_map), scope


def _git_init(root):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "x"]):
        subprocess.run(["git", *args], cwd=root, check=True, env={**env, "PATH": "/usr/bin:/bin"}, capture_output=True)  # noqa: S603, S607


@pytest.mark.parametrize("suffix", DATASET_SUFFIXES)
def test_a_dataset_name_directory_keeps_its_members_on_the_walk(tmp_path, suffix):
    _build(tmp_path, f"FAKE.APP.{suffix}")
    keys, _ = _census(tmp_path)
    assert f"FAKE.APP.{suffix}/FAKECPY.cpy" in keys
    assert f"FAKE.APP.{suffix}/FAKEPGM.cbl" in keys


@pytest.mark.parametrize("dirname", ["v1.2", "a.b.c", "x.exe", "FAKE.APP.COPYLIB.BACKUP"])
def test_any_dotted_directory_name_is_not_an_extension(tmp_path, dirname):
    _build(tmp_path, dirname)
    keys, _ = _census(tmp_path)
    assert f"{dirname}/FAKECPY.cpy" in keys


def test_the_walk_and_the_git_census_agree(tmp_path):
    for sfx in ("COPYLIB", "DBRMLIB", "COBOL"):
        _build(tmp_path, f"FAKE.APP.{sfx}")
    walk_keys, _ = _census(tmp_path)
    _git_init(tmp_path)
    git_keys, _ = _census(tmp_path)
    assert walk_keys == git_keys
    assert "FAKE.APP.COPYLIB/FAKECPY.cpy" in git_keys


@pytest.mark.parametrize("pruned", ["node_modules", ".hidden", "FAKE.APP.COPYLIB/node_modules"])
def test_ignored_directories_are_still_pruned(tmp_path, pruned):
    _build(tmp_path, "FAKE.APP.COPYLIB")
    _build(tmp_path, pruned) if "/" not in pruned else _build(tmp_path / "FAKE.APP.COPYLIB", "node_modules")
    keys, _ = _census(tmp_path)
    assert not any("node_modules" in k or ".hidden" in k for k in keys)
    assert "FAKE.APP.COPYLIB/FAKECPY.cpy" in keys


def test_a_file_with_a_denied_extension_inside_a_dataset_dir_is_still_judged(tmp_path):
    d = _build(tmp_path, "FAKE.APP.COPYLIB")
    (d / "tool.exe").write_bytes(b"MZ\x00\x00")
    keys, scope = _census(tmp_path)
    assert "FAKE.APP.COPYLIB/tool.exe" not in keys
    assert "FAKE.APP.COPYLIB/FAKECPY.cpy" in keys
