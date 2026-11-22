"""#8708: a directory named `log`, `classes`, `docs`, ... is pruned on evidence, not by name.

DPDK's `lib/log/` (log.c, rte_log.h) and mesa's `.../nvidia/classes/` are first-party source; `var/log/app.log` is a
runtime log. A pruned directory is recorded with the reason `ignored directory: <name>`.
"""

import pytest

from gitgalaxy.core.aperture import EVIDENCE_DIRECTORY_NAMES, ApertureFilter, is_noise_directory
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

C_SRC = "int rte_log(int level) {\n    if (level > 3) {\n        return 1;\n    }\n    return 0;\n}\n"
NAMES = sorted(EVIDENCE_DIRECTORY_NAMES)


def _filter(root):
    return ApertureFilter(root, LANGUAGE_DEFINITIONS, APERTURE_CONFIG)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_ambiguous_names_are_not_matched_by_name():
    ignored = {d.lower() for d in APERTURE_CONFIG["IGNORED_DIRECTORIES"]}
    assert not (ignored & EVIDENCE_DIRECTORY_NAMES)
    assert {"node_modules", "__pycache__", "target", "build"} <= ignored


@pytest.mark.parametrize("name", NAMES + [n.upper() for n in NAMES])
def test_a_directory_holding_source_is_scanned(tmp_path, name):
    f = _write(tmp_path / "lib" / name / "log.c", C_SRC)
    r = _filter(tmp_path).is_in_scope(f, content=C_SRC)
    assert r["is_in_scope"], r["reason"]


@pytest.mark.parametrize("name", NAMES + [n.upper() for n in NAMES])
def test_a_directory_with_no_source_is_pruned_and_recorded(tmp_path, name):
    f = _write(tmp_path / "var" / name / "app.log", "started\n")
    r = _filter(tmp_path).is_in_scope(f, content="started\n")
    assert not r["is_in_scope"]
    assert f"ignored directory: {name.upper() if name.isupper() else name}" in r["reason"]


def test_source_in_a_nested_subdirectory_keeps_the_ambiguous_directory(tmp_path):
    f = _write(tmp_path / "lib" / "log" / "impl" / "x.c", C_SRC)
    _write(tmp_path / "lib" / "log" / "notes.txt", "n\n")
    r = _filter(tmp_path).is_in_scope(f, content=C_SRC)
    assert r["is_in_scope"], r["reason"]


def test_docs_holding_only_markup_is_pruned_and_docs_examples_are_scanned(tmp_path):
    md = _write(tmp_path / "a" / "docs" / "guide" / "intro.md", "# hi\n")
    ex = _write(tmp_path / "b" / "docs" / "examples" / "demo.c", C_SRC)
    assert not _filter(tmp_path / "a").is_in_scope(md, content="# hi\n")["is_in_scope"]
    assert _filter(tmp_path / "b").is_in_scope(ex, content=C_SRC)["is_in_scope"]


@pytest.mark.parametrize("name", ["node_modules", "__pycache__", "target"])
def test_names_nobody_uses_for_source_stay_pruned_by_name(tmp_path, name):
    f = _write(tmp_path / "pkg" / name / "x.c", C_SRC)
    r = _filter(tmp_path).is_in_scope(f, content=C_SRC)
    assert not r["is_in_scope"]
    assert f"ignored directory: {name}" in r["reason"]


def test_a_file_named_like_an_ambiguous_directory_is_still_excluded(tmp_path):
    f = _write(tmp_path / "LICENSE", "MIT\n")
    assert not _filter(tmp_path).is_in_scope(f, content="MIT\n")["is_in_scope"]


def test_the_directory_walk_prunes_by_evidence(tmp_path):
    _write(tmp_path / "lib" / "log" / "log.c", C_SRC)
    _write(tmp_path / "var" / "log" / "app.log", "x\n")
    flt = _filter(tmp_path)
    assert flt.evaluate_dir_integrity(tmp_path / "lib" / "log")
    assert not flt.evaluate_dir_integrity(tmp_path / "var" / "log")


def test_is_noise_directory_skips_by_name_pruned_subtrees(tmp_path):
    _write(tmp_path / "docs" / "node_modules" / "x.c", C_SRC)
    assert is_noise_directory(tmp_path / "docs", {"node_modules"})
    assert not is_noise_directory(tmp_path / "docs", set())
