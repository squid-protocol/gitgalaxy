"""Weighted-view labels use the signal display names (gitgalaxy#8009, slice 2c).

The brief and the audit JSON print a "(weighted view)" line beside each proximity-weighted
signal. Both used to title-case the raw rule key ("Memory Alloc"); they now use
SIGNAL_DISPLAY_NAMES, and a key that is no signal keeps the old form.
"""

import pytest

from gitgalaxy.metrics.signal_processor import WEIGHTED_SIGNALS
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import _weighted_label
from gitgalaxy.standards.analysis_lens import SIGNAL_DISPLAY_NAMES


# A weighted key outside SIGNAL_SCHEMA (a derived tally) keeps the Title Case form.
SIGNAL_KEYS = sorted(k for k in WEIGHTED_SIGNALS if k in SIGNAL_DISPLAY_NAMES)
DERIVED_KEYS = sorted(k for k in WEIGHTED_SIGNALS if k not in SIGNAL_DISPLAY_NAMES)


def test_most_weighted_keys_are_signals():
    assert SIGNAL_KEYS
    assert set(DERIVED_KEYS) <= {"memory_scraping"}


@pytest.mark.parametrize("key", DERIVED_KEYS)
def test_derived_weighted_key_keeps_title_case(key):
    assert _weighted_label(key) == key.replace("_", " ").title()


@pytest.mark.parametrize("key", SIGNAL_KEYS)
def test_brief_weighted_label_is_the_display_name(key):
    assert _weighted_label(key) == SIGNAL_DISPLAY_NAMES[key][1]


@pytest.mark.parametrize("key", SIGNAL_KEYS)
def test_audit_label_is_the_display_name_unless_friendly_map_names_it(key):
    rec = AuditRecorder()
    label = rec.format_label(key)
    assert label in (SIGNAL_DISPLAY_NAMES[key][1], rec._friendly_map.get(key))
    assert label != key.replace("_", " ").title() or key.replace("_", " ").title() == SIGNAL_DISPLAY_NAMES[key][1]


def test_non_signal_key_keeps_title_case():
    assert _weighted_label("amplified_cascading_flux") == "Amplified Cascading Flux"
    assert AuditRecorder().format_label("amplified_cascading_flux") == "Amplified Cascading Flux"
