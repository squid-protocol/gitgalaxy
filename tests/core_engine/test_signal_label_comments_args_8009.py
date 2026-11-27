"""gitgalaxy#8009: rule comments name args by its display name, not the pre-rename
"Parameters / Coupling" label (the column is struct_args and counts call and definition
sites that carry arguments, not parameters or coupling)."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

LANGS = pathlib.Path(__file__).resolve().parents[2] / "gitgalaxy" / "standards" / "language_standards" / "languages"
STALE = "args (Parameters / Coupling)"
RELABELLED = (
    "c",
    "cpp",
    "python",
    "javascript",
    "sqlite",
    "dockerfile",
    "tcl",
    "fortran",
    "agc_assembly",
    "kotlin",
    "ruby",
    "scheme",
    "php",
    "groovy",
    "m4",
    "typescript",
    "csharp",
    "java",
    "go",
    "rust",
    "dart",
    "assembly",
    "shell",
    "embedded_python",
    "css",
    "swift",
    "html",
    "lua",
    "powershell",
    "zig",
)


def test_relabelled_files_carry_no_stale_label():
    for stem in RELABELLED:
        assert STALE not in (LANGS / f"{stem}.py").read_text(encoding="utf-8"), stem


def test_relabelled_comments_use_the_display_name():
    name = SIGNAL_DISPLAY_NAMES["args"][1]
    for stem in RELABELLED:
        assert f"args ({name})" in (LANGS / f"{stem}.py").read_text(encoding="utf-8"), stem
