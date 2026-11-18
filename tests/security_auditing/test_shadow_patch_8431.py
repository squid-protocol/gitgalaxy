"""Shadow-patch detection (#8431): changed content + unchanged manifest version flags; a bump or no change does not."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from gitgalaxy.security.shadow_patch import (
    detect_against_ref,
    find_shadow_patches,
    nearest_manifest,
    read_manifest_version,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        [shutil.which("git"), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, version: str = "1.0.0") -> Path:
    (tmp_path / "package.json").write_text(json.dumps({"name": "p", "version": version}), encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("a();\n", encoding="utf-8")
    (tmp_path / "src" / "b.js").write_text("b();\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_changed_file_with_unchanged_version_flags(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "a.js").write_text("a(); exfil();\n", encoding="utf-8")
    hits = detect_against_ref(str(repo), "HEAD")
    assert [h["path"] for h in hits] == ["src/a.js"]
    assert hits[0]["version"] == "1.0.0"


def test_changed_file_with_version_bump_does_not_flag(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "a.js").write_text("a(); exfil();\n", encoding="utf-8")
    (repo / "package.json").write_text(json.dumps({"name": "p", "version": "1.0.1"}), encoding="utf-8")
    assert detect_against_ref(str(repo), "HEAD") == []


def test_unchanged_files_never_flag(tmp_path):
    repo = _repo(tmp_path)
    assert detect_against_ref(str(repo), "HEAD") == []


def test_only_the_changed_file_flags(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "b.js").write_text("b(); evil();\n", encoding="utf-8")
    assert [h["path"] for h in detect_against_ref(str(repo), "HEAD")] == ["src/b.js"]


def test_manifest_edit_alone_is_not_a_shadow_patch(tmp_path):
    repo = _repo(tmp_path)
    (repo / "package.json").write_text(json.dumps({"name": "q", "version": "1.0.0"}), encoding="utf-8")
    assert detect_against_ref(str(repo), "HEAD") == []


def test_unreadable_ref_flags_nothing(tmp_path):
    repo = _repo(tmp_path)
    assert detect_against_ref(str(repo), "no-such-ref") == []


def test_file_without_a_manifest_never_flags():
    assert find_shadow_patches(["x/a.py"], {"y": "1"}, {"y": "1"}) == []


def test_nearest_manifest_governs_a_nested_package():
    base = {"": "1.0.0", "pkg": "2.0.0"}
    cur = {"": "1.0.1", "pkg": "2.0.0"}
    # root bumped, the nested package did not: the nested file flags, the root-level one does not
    flagged = find_shadow_patches(["pkg/m.py", "top.py"], base, cur)
    assert [f["path"] for f in flagged] == ["pkg/m.py"]
    assert nearest_manifest("pkg/m.py", ["", "pkg"]) == "pkg"
    assert nearest_manifest("pkgx/m.py", ["", "pkg"]) == ""


@pytest.mark.parametrize(
    ("name", "text", "want"),
    [
        ("package.json", '{"version": "3.2.1"}', "3.2.1"),
        ("package.json", "{not json", None),
        ("package.json", '{"name": "x"}', None),
        ("pyproject.toml", '[project]\nversion = "0.4"\n', "0.4"),
        ("pyproject.toml", '[tool.poetry]\nversion = "0.5"\n', None),
        ("Cargo.toml", '[package]\nversion = "1.2.3"\n', "1.2.3"),
        ("Cargo.toml", "[package", None),
    ],
)
def test_read_manifest_version(name, text, want):
    assert read_manifest_version(name, text) == want
