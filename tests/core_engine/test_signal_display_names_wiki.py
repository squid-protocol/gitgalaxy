"""gitgalaxy#8009: the Claim 5 wiki page names signals by their display names,
not the pre-rename FRIENDLY_MAP labels."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES

PAGE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "wiki" / "03-05-claim-5-file-archetypes.md"
OLD_LABELS = (
    "Sequential Logic Declarations",
    "Type/Safety Bypasses",
    "Type Safety Bypasses",
    "Metaprogramming & Reflection",
    "Function Parameters",
    "State Mutations",
    "Fatal Aborts & Exceptions",
    "Thread Sleeps",
    "Immutable Data Declarations",
    "Defensive Programming Constructs",
    "Exposed API / Public Exports",
    "Private / Encapsulated Scopes",
    "Private Encapsulated Scopes",
)


def test_page_uses_no_pre_rename_signal_label():
    text = PAGE.read_text(encoding="utf-8")
    stale = [label for label in OLD_LABELS if f"**{label}" in text]
    assert not stale, f"pre-rename signal labels in {PAGE.name}: {stale}"


def test_state_mutation_bullet_uses_the_display_name():
    name = SIGNAL_DISPLAY_NAMES["state_mutation"][1]
    assert f"**{name}:**" in PAGE.read_text(encoding="utf-8")
