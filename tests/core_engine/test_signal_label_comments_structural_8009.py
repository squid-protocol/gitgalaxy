"""gitgalaxy#8009: rule comments name structural_boundaries by its display name, not the
pre-rename "linear: Sequential I/O & Network Boundaries" label (the column is
struct_linear but counts return/def/void/export, not linear code or I/O)."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

LANGS = pathlib.Path(__file__).resolve().parents[2] / "gitgalaxy" / "standards" / "language_standards" / "languages"
STALE = "linear: Sequential I/O & Network Boundaries"
# Slice 2 relabelled these; the rest are listed in the PR under Remaining slices.
RELABELLED = ("abap", "apex", "cobol", "dart")


def test_relabelled_files_carry_no_stale_label():
    for stem in RELABELLED:
        assert STALE not in (LANGS / f"{stem}.py").read_text(encoding="utf-8"), stem


def test_relabelled_comments_use_the_display_name():
    name = SIGNAL_DISPLAY_NAMES["structural_boundaries"][1].split(" (")[0]
    for stem in RELABELLED:
        assert f"structural_boundaries ({name})" in (LANGS / f"{stem}.py").read_text(encoding="utf-8"), stem
