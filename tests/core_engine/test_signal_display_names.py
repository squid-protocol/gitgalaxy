"""gitgalaxy#8009: SIGNAL_DISPLAY_NAMES contract -- one entry per SIGNAL_SCHEMA
signal, its column equal to the recorder's persisted column, unique names, and
docs/signals.md listing every signal."""

from __future__ import annotations

import pathlib

from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, SIGNAL_DISPLAY_NAMES, signal_display_name

SIGNALS = RECORDING_SCHEMAS["SIGNAL_SCHEMA"]
DOC = pathlib.Path(__file__).resolve().parents[2] / "docs" / "signals.md"


def test_every_signal_has_exactly_one_entry():
    assert set(SIGNAL_DISPLAY_NAMES) == set(SIGNALS)


def test_columns_match_the_recorder():
    short = RecordKeeper().SHORT_KEY_MAP
    wrong = {k: (col, short.get(k, k)) for k, (col, _) in SIGNAL_DISPLAY_NAMES.items() if col != short.get(k, k)}
    assert not wrong, f"column drifted from RecordKeeper.SHORT_KEY_MAP: {wrong}"


def test_names_and_columns_are_unique_and_nonempty():
    cols = [c for c, _ in SIGNAL_DISPLAY_NAMES.values()]
    names = [n for _, n in SIGNAL_DISPLAY_NAMES.values()]
    assert all(n.strip() for n in names)
    assert len(set(cols)) == len(cols)
    assert len(set(names)) == len(names)


def test_lookup_accepts_rule_key_or_column():
    assert signal_display_name("structural_boundaries") == signal_display_name("struct_linear")
    assert "Structural Keywords" in signal_display_name("struct_linear")
    assert "Unsafe Constructs" in signal_display_name("state_safety_neg")
    assert signal_display_name("not_a_signal") == "not_a_signal"


def test_docs_table_lists_every_signal():
    text = DOC.read_text(encoding="utf-8")
    missing = [col for col, _ in SIGNAL_DISPLAY_NAMES.values() if f"`{col}`" not in text]
    assert not missing, f"docs/signals.md is missing: {missing}"
