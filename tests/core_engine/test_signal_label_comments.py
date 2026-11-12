"""gitgalaxy#8009: language rule comments name panics_and_aborts by its display name,
not the pre-rename FRIENDLY_MAP label ("Fatal Aborts"), which misdescribes the rule.

KNOWN_STALE only shrinks: relabel a file's comment, then delete it from the set."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

LANGS = pathlib.Path(__file__).resolve().parents[2] / "gitgalaxy" / "standards" / "language_standards" / "languages"
STALE = "Execution Interrupts / Fatal Aborts"

KNOWN_STALE = {
    "m4",
    "matlab",
    "objectivec",
    "perl",
    "sqlite",
    "swift",
    "tcl",
    "zig",
}


def _stale_files() -> set[str]:
    return {p.stem for p in LANGS.glob("*.py") if STALE in p.read_text(encoding="utf-8")}


def test_stale_label_set_only_shrinks():
    stale = _stale_files()
    assert stale <= KNOWN_STALE, f"new stale panics_and_aborts comment: {sorted(stale - KNOWN_STALE)}"
    assert not (KNOWN_STALE - stale), f"relabelled, remove from KNOWN_STALE: {sorted(KNOWN_STALE - stale)}"


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
        "powershell",
        "scala",
        "scheme",
        "solidity",
    ):
        text = (LANGS / f"{stem}.py").read_text(encoding="utf-8")
        assert f"panics_and_aborts ({name}:" in text, stem
