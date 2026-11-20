"""gitgalaxy#8009: the museum AlphaFold teardown labels the 11 renamed signal columns by display name,
with a tooltip that matches what the rule counts (not the pre-rename prose)."""

from __future__ import annotations

import pathlib
import re

import pytest

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

PAGE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "wiki" / "museum-of-code" / "alphafold_teardown.html"
COLUMNS = {
    "struct_linear",
    "state_safety_neg",
    "state_heat_triggers",
    "struct_args",
    "state_flux",
    "state_bailout_hits",
    "state_halt_hits",
    "def_freeze_hits",
    "def_safety",
    "arch_api",
    "def_encapsulation",
}
STALE_TOOLTIP = ("Smooths geometry", "Declarative pathing", "Boiling Plasma", "Thermal Radiation", "Red Fragility")
HEADER = re.compile(r'data-sort="(\w+)"><span class="glossary-term" data-tooltip="([^"]*)">([^<]*)</span>')


def _headers():
    text = PAGE.read_text(encoding="utf-8")
    out: dict[str, list[tuple[str, str]]] = {}
    for col, tip, label in HEADER.findall(text):
        out.setdefault(col, []).append((tip, label))
    return out


@pytest.mark.parametrize("col", sorted(COLUMNS))
def test_header_uses_display_name_and_current_tooltip(col):
    name = next(n for c, n in SIGNAL_DISPLAY_NAMES.values() if c == col)
    rows = _headers()[col]
    assert len(rows) == 2  # both tables
    for tip, label in rows:
        assert label == name
        assert tip.startswith("Counts ")
        assert not any(s in tip for s in STALE_TOOLTIP)
