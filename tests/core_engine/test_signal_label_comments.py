"""gitgalaxy#8009: language rule comments name panics_and_aborts by its display name,
not the pre-rename FRIENDLY_MAP label ("Fatal Aborts"), which misdescribes the rule.

No file may carry the stale label."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

LANGS = pathlib.Path(__file__).resolve().parents[2] / "gitgalaxy" / "standards" / "language_standards" / "languages"
STALE = "Execution Interrupts / Fatal Aborts"


def _stale_files() -> set[str]:
    return {p.stem for p in LANGS.glob("*.py") if STALE in p.read_text(encoding="utf-8")}


def test_no_stale_label_remains():
    assert not _stale_files(), f"stale panics_and_aborts comment: {sorted(_stale_files())}"


def test_relabelled_comments_use_the_display_name():
    name = SIGNAL_DISPLAY_NAMES["panics_and_aborts"][1].split(" (")[0]
    for stem in (
        "c",
        "cpp",
        "python",
        "javascript",
        "go",
        "rust",
        "java",
        "csharp",
        "abap",
        "agc_assembly",
        "apex",
        "assembly",
        "php",
        "shell",
        "typescript",
        "ruby",
        "cobol",
        "css",
        "dart",
        "dockerfile",
        "embedded_python",
        "fortran",
        "groovy",
        "haskell",
        "html",
        "kotlin",
        "livecode",
        "lua",
        "m4",
        "matlab",
        "objectivec",
        "perl",
        "sqlite",
        "swift",
        "tcl",
        "zig",
        "powershell",
        "scala",
        "scheme",
        "solidity",
    ):
        text = (LANGS / f"{stem}.py").read_text(encoding="utf-8")
        assert f"panics_and_aborts ({name}:" in text, stem


def test_reflection_metaprogramming_comments_use_the_display_name():
    name = SIGNAL_DISPLAY_NAMES["reflection_metaprogramming"][1].split(" (")[0]
    for stem in (
        "livecode",
        "solidity",
        "css",
        "zig",
        "python",
        "javascript",
        "c",
        "cpp",
        "go",
        "rust",
        "java",
        "csharp",
        "php",
        "kotlin",
        "typescript",
        "lua",
        "abap",
        "agc_assembly",
        "apex",
        "assembly",
    ):
        text = (LANGS / f"{stem}.py").read_text(encoding="utf-8")
        assert f"reflection_metaprogramming ({name}:" in text, stem
        assert "Metaprogramming & Reflection" not in text, stem
