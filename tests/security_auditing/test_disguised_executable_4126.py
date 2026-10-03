"""#4126: a disguised executable -- executable magic at offset 0 under an extension that claims an
inert format -- is flagged through the real aperture and security lens; ordinary denied files
(an LFS pointer, an empty file, one image format under another image extension) are not."""

from __future__ import annotations

import os
import shutil
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.aperture import DENIED_EXTENSION, ApertureFilter, ApertureReason
from gitgalaxy.security.security_lens import detect_disguised_executable, executable_magic

REPO_ROOT = Path(__file__).resolve().parents[2]

ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 120


def _pe() -> bytes:
    head = bytearray(256)
    head[0:2] = b"MZ"
    head[0x3C:0x40] = struct.pack("<I", 0x80)
    head[0x80:0x84] = b"PE\x00\x00"
    return bytes(head)


LFS = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.parametrize(
    ("head", "ext", "fires"),
    [
        (ELF, ".png", True),
        (_pe(), ".jpg", True),
        (LFS, ".png", False),
        (b"", ".png", False),
        (PNG, ".jpg", False),  # one image format under another image extension
        (b"MZ" + b"\x00" * 100, ".gif", False),  # a bare MZ is not a PE
        (ELF, ".so", False),  # an executable under an executable extension is not disguised
    ],
)
def test_detector(head, ext, fires):
    assert bool(detect_disguised_executable(head, ext)) is fires


def test_executable_magic_names_the_container():
    assert executable_magic(ELF) == "ELF executable"
    assert executable_magic(_pe()) == "PE (Windows) executable"
    assert executable_magic(PNG) == ""


def test_gate_1_3_reason_carries_its_kind(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(ELF)
    from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG

    ok, _, reason = ApertureFilter(tmp_path, {}, APERTURE_CONFIG).evaluate_path_integrity(f)
    assert not ok
    assert isinstance(reason, ApertureReason) and reason.kind == DENIED_EXTENSION
    assert "Denied Extension" in reason  # the text is unchanged for every log and report reader


def test_reason_survives_pickling():
    import pickle

    r = pickle.loads(pickle.dumps(ApertureReason("Blocked (x)", DENIED_EXTENSION)))
    assert r == "Blocked (x)" and r.kind == DENIED_EXTENSION


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git for the census")
def test_end_to_end_scan_flags_only_disguised_executables(tmp_path):
    repo = tmp_path / "planted"
    repo.mkdir()
    (repo / "logo.png").write_bytes(ELF)
    (repo / "photo.jpg").write_bytes(_pe())
    (repo / "asset.png").write_bytes(LFS)
    (repo / "empty.png").write_bytes(b"")
    (repo / "real.jpg").write_bytes(PNG)
    (repo / "main.py").write_text("def f():\n    return 1\n")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)  # noqa: S603
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)  # noqa: S603
    subprocess.run([*git, "commit", "-qm", "planted"], cwd=repo, check=True)  # noqa: S603

    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gitgalaxy.galaxyscope", "."],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        timeout=600,
    )
    con = sqlite3.connect(next(repo.glob("*_galaxy_master.db")))
    flagged = {
        name for name, mismatch in con.execute("SELECT file_name, threat_extension_mismatch FROM file_data") if mismatch
    }
    assert flagged == {"logo.png", "photo.jpg"}
