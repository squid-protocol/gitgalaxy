"""gitgalaxy#8012: FUNCTION_LEVEL_ABSENT_SIGNALS names real signals, gives a reason for each, and
docs/signals.md marks every one of them."""

from __future__ import annotations

import pathlib

from gitgalaxy.standards.analysis_lens import FUNCTION_LEVEL_ABSENT_SIGNALS, RECORDING_SCHEMAS, SIGNAL_DISPLAY_NAMES

DOC = pathlib.Path(__file__).resolve().parents[2] / "docs" / "signals.md"


def test_every_entry_is_a_signal_with_a_reason():
    assert set(FUNCTION_LEVEL_ABSENT_SIGNALS) <= set(RECORDING_SCHEMAS["SIGNAL_SCHEMA"])
    assert all(r.startswith(("file-level only:", "never set:")) for r in FUNCTION_LEVEL_ABSENT_SIGNALS.values())


def test_docs_mark_every_function_level_absent_column():
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## Not measured per function", 1)[1]
    missing = [
        SIGNAL_DISPLAY_NAMES[k][0]
        for k in FUNCTION_LEVEL_ABSENT_SIGNALS
        if f"`{SIGNAL_DISPLAY_NAMES[k][0]}`" not in section
    ]
    assert not missing, missing
