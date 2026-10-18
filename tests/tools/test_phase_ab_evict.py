import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase_ab  # noqa: E402


def test_evict_tree_counts_regular_files_and_skips_links(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub" / "b.txt").write_text("b")
    os.symlink(tmp_path / "a.txt", tmp_path / "link.txt")
    expected = 2 if hasattr(os, "posix_fadvise") else 0
    assert phase_ab.evict_tree(tmp_path) == expected


def test_evict_tree_without_fadvise_is_a_noop(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a")
    monkeypatch.delattr(os, "posix_fadvise", raising=False)
    assert phase_ab.evict_tree(tmp_path) == 0


def test_evict_tree_survives_unreadable_and_failing_files(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a")

    def boom(*_a):
        raise OSError("nope")

    monkeypatch.setattr(os, "posix_fadvise", boom, raising=False)
    monkeypatch.setattr(os, "POSIX_FADV_DONTNEED", 4, raising=False)  # absent on macOS and Windows
    assert phase_ab.evict_tree(tmp_path) == 0


def test_parse_env_specs_groups_by_leg():
    legs = ["off", "on"]
    got = phase_ab.parse_env_specs(["off:GITGALAXY_PREFETCH=0", "on:GITGALAXY_PREFETCH=1", "on:X=a=b"], legs)
    assert got == {"off": {"GITGALAXY_PREFETCH": "0"}, "on": {"GITGALAXY_PREFETCH": "1", "X": "a=b"}}
    assert phase_ab.parse_env_specs([], legs) == {}


@pytest.mark.parametrize("spec", ["nocolon=1", "off:NOEQ", "off:=1", "ghost:K=V"])
def test_parse_env_specs_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        phase_ab.parse_env_specs([spec], ["off", "on"])
