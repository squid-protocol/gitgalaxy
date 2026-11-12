"""The LLM brief's signature lexicon stays in sync with the signal display names (gitgalaxy#8009, slice 2).

The lexicon named signals by hand-typed aliases (`linear`, `flux`, `danger`, `safety_neg`,
`freeze_hits`, `graveyard`) that matched neither the Structural Signatures lines nor the
persisted columns. It now renders each entry as the display name plus the raw rule key.
"""

import re

from gitgalaxy.recorders import llm_recorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, signal_display_name

SCHEMA = RECORDING_SCHEMAS["SIGNAL_SCHEMA"]
RETIRED_ALIASES = ("linear", "flux", "danger", "safety_neg", "freeze_hits", "graveyard")

# Signals the brief groups on its Structural Signatures lines but the lexicon does not gloss.
# A new grouped signal fails test_every_grouped_signal_is_glossed_or_listed until classified.
NOT_GLOSSED = {
    "class_start",
    "planned_debt",
    "fragile_debt",
    "unreferenced_by_name",
    "duplicate_logic",
    "test",
    "sync_locks",
    "doc",
}
GROUPED = {
    "branch",
    "structural_boundaries",
    "args",
    "func_start",
    "class_start",
    "high_risk_execution",
    "state_mutation",
    "dead_code",
    "safety_bypasses",
    "planned_debt",
    "fragile_debt",
    "unreferenced_by_name",
    "duplicate_logic",
    "io",
    "concurrency",
    "api",
    "import",
    "safety",
    "immutability_locks",
    "cleanup",
    "test",
    "sync_locks",
    "doc",
}


def _brief():
    session = {"engine": "t", "target": "T", "zero_dependency_mode": False, "git_audit": {}}
    return LLMRecorder()._build_markdown([], [], {}, session, {})


def _lexicon_keys():
    return [k for _, entries in llm_recorder._LEXICON_GROUPS for k, _ in entries]


def test_every_lexicon_key_is_a_signal():
    assert set(_lexicon_keys()) <= set(SCHEMA)
    assert len(_lexicon_keys()) == len(set(_lexicon_keys()))


def test_every_grouped_signal_is_glossed_or_listed():
    assert GROUPED <= set(SCHEMA)
    assert set(_lexicon_keys()) | NOT_GLOSSED == GROUPED
    assert not set(_lexicon_keys()) & NOT_GLOSSED


def test_lexicon_names_each_signal_by_display_name_and_rule_key():
    md = _brief()
    bullets = [ln for ln in md.splitlines() if ln.startswith("> * **") and "(`" in ln]
    text = "\n".join(bullets)
    for key in _lexicon_keys():
        assert f"**{signal_display_name(key)}** (`{key}`)" in text


def test_no_retired_alias_is_named_in_the_brief_prose():
    md = _brief()
    prose = "\n".join(ln for ln in md.splitlines() if ln.startswith(">"))
    for alias in RETIRED_ALIASES:
        assert not re.search(rf"`{alias}`", prose), alias
