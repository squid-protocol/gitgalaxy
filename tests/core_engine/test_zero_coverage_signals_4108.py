# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108: end-to-end guard for signals that fire on no language-crucible file.

The golden master cannot catch a regression in a signal the crucible never exercises
(`tests/signal_coverage_baseline.json`). Until keyword-rosetta carries planted cases, these
tests scan a temp repo of planted files through the real CLI and read the per-file
"Structural Signatures" label the golden reads, so a broken rule or a renamed label fails here.
Characters are built with chr() (X-Ray flags literal non-ASCII runs).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGS = "7. Structural Signatures (Net Mitigated Signals)"
HOMOGLYPH = "Non-Standard Unicode / Homoglyphs"
INVISIBLE = "Invisible Unicode Payload Smuggling"

CYR_E = chr(0x0435)  # Cyrillic small ie, passes for Latin e
GREEK_O = chr(0x03BF)  # Greek small omicron, passes for Latin o
MATH_BOLD_R = chr(0x1D42B)  # mathematical bold small r
HANGUL_FILLER = chr(0x3164)
VARIATION_RUN = "".join(chr(0xE0100 + i) for i in range(8))
TAG_RUN = "".join(chr(0xE0041 + i) for i in range(8))
RUSSIAN_WORD = "".join(chr(c) for c in (0x043F, 0x0440, 0x0438, 0x0432, 0x0435, 0x0442))  # a word, not a spoof

# path -> (source, homoglyph fires, invisible fires)
PLANTS = {
    "cyrillic.py": (f"import r{CYR_E}quests\n\n\ndef f():\n    return 1\n", True, False),
    "greek.js": (f"const x = require('l{GREEK_O}dash');\nfunction f() {{ return x; }}\n", True, False),
    "mathalpha.py": (f"import {MATH_BOLD_R}equests\n\n\ndef f():\n    return 1\n", True, False),
    "filler.py": (f"import os{HANGUL_FILLER}\n\n\ndef f():\n    return 1\n", True, False),
    "variation.js": (f"const s = '{VARIATION_RUN}';\nfunction f() {{ return s; }}\n", False, True),
    "tags.js": (f"const s = '{TAG_RUN}';\nfunction f() {{ return s; }}\n", False, True),
    "control_word.py": (f"import {RUSSIAN_WORD}\n\n\ndef f():\n    return 1\n", False, False),
    "control_ascii.py": ("import os\n\n\ndef f():\n    return os.getcwd()\n", False, False),
}


@pytest.fixture(scope="module")
def signatures(tmp_path_factory):
    root = tmp_path_factory.mktemp("planted") / "repo"
    (root / "src").mkdir(parents=True)
    for name, (source, _, _) in PLANTS.items():
        (root / "src" / name).write_text(source, encoding="utf-8")
    out = tmp_path_factory.mktemp("out")
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT), env.get("PYTHONPATH", "")]))
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(root), "--audit-only", "--output", str(out / "o")],
        check=True,
        env=env,
        capture_output=True,
        cwd=str(out),
        timeout=120,
    )
    audit = json.loads(next((out / "o").glob("*_galaxy_audit.json")).read_text(encoding="utf-8"))
    found = {}
    for group in audit["6. Parsed Files (Scanned Artifacts)"].values():
        for path, rec in group["Files"].items():
            found[Path(path).name] = rec[SIGS]
    return found


@pytest.mark.parametrize("name", sorted(PLANTS))
def test_planted_file_fires_exactly_its_signal(signatures, name):
    _, homoglyph, invisible = PLANTS[name]
    assert name in signatures, "planted file was not parsed"
    assert (signatures[name][HOMOGLYPH] > 0) is homoglyph
    assert (signatures[name][INVISIBLE] > 0) is invisible


# --- Sec Extension Mismatch: the #4126 sensor, read through the audit label the golden reads ---
MISMATCH = "Sec Extension Mismatch"
ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 120
LFS = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"
# path -> (bytes, fires)
BINARY_PLANTS = {
    "disguised.png": (ELF, True),
    "disguised.pdf": (ELF, True),
    "lfs_pointer.png": (LFS, False),
    "empty.png": (b"", False),
}


@pytest.fixture(scope="module")
def mismatch_signatures(tmp_path_factory):
    root = tmp_path_factory.mktemp("planted_bin") / "repo"
    root.mkdir()
    for name, (data, _) in BINARY_PLANTS.items():
        (root / name).write_bytes(data)
    (root / "main.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)  # noqa: S603
    subprocess.run([*git, "add", "-A"], cwd=root, check=True)  # noqa: S603
    subprocess.run([*git, "commit", "-qm", "planted"], cwd=root, check=True)  # noqa: S603
    out = tmp_path_factory.mktemp("out_bin")
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT), env.get("PYTHONPATH", "")]))
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(root), "--audit-only", "--output", str(out / "o")],
        check=True,
        env=env,
        capture_output=True,
        cwd=str(out),
        timeout=120,
    )
    audit = json.loads(next((out / "o").glob("*_galaxy_audit.json")).read_text(encoding="utf-8"))
    found = {}
    for group in audit["6. Parsed Files (Scanned Artifacts)"].values():
        for path, rec in group["Files"].items():
            found[Path(path).name] = rec[SIGS]
    return found


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git for the census")
@pytest.mark.parametrize("name", sorted(BINARY_PLANTS))
def test_disguised_executable_fires_the_audit_label(mismatch_signatures, name):
    fires = BINARY_PLANTS[name][1]
    if fires:
        assert mismatch_signatures[name][MISMATCH] > 0
    else:
        assert mismatch_signatures.get(name, {}).get(MISMATCH, 0) == 0
    assert mismatch_signatures["main.py"][MISMATCH] == 0
