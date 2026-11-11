"""The LLM brief names each signal by its reader-facing display name (gitgalaxy#8009, slice 2).

`struct_linear` read as "linear code" when the rule counts `return`; the brief's
Structural Signatures lines and the mixed-responsibility "Top Architectural
Signatures" line carry the display name first and keep the raw rule key beside it.
The rendering is pinned for every key in all four signature groups.
"""

import pytest

from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, signal_display_name

GROUPS = {
    "Structure": ["branch", "structural_boundaries", "args", "func_start", "class_start"],
    "Risk/State": [
        "high_risk_execution",
        "state_mutation",
        "dead_code",
        "safety_bypasses",
        "planned_debt",
        "fragile_debt",
        "unreferenced_by_name",
        "duplicate_logic",
    ],
    "Architecture": ["io", "concurrency", "api", "import"],
    "Defense": ["safety", "immutability_locks", "cleanup", "test", "sync_locks", "doc"],
}
SCHEMA = RECORDING_SCHEMAS["SIGNAL_SCHEMA"]


def _file(path, hits, fingerprint=None):
    return {
        "path": path,
        "name": path,
        "lang_id": "python",
        "directory_group": "src",
        "lock_tier": 0,
        "total_loc": 10,
        "coding_loc": 10,
        "file_impact": 5.0,
        "raw_imports": [],
        "telemetry": {"popularity": 0, "archetype_fingerprint": fingerprint or {}},
        "risk_vector": [0.0] * len(RECORDING_SCHEMAS["RISK_SCHEMA"]),
        "hit_vector": hits,
        "functions": [],
    }


def _brief(files):
    session = {"engine": "t", "target": "T", "zero_dependency_mode": False, "git_audit": {}}
    return LLMRecorder()._build_markdown(files, [], {}, session, {})


def _hits(keys):
    vec = [0] * len(SCHEMA)
    for n, key in enumerate(keys, start=2):
        vec[SCHEMA.index(key)] = n
    return vec


def test_every_group_key_is_in_the_signal_schema():
    for keys in GROUPS.values():
        assert set(keys) <= set(SCHEMA)


@pytest.mark.parametrize("label", sorted(GROUPS))
def test_structural_signatures_line_leads_with_the_display_name(label):
    keys = GROUPS[label]
    md = _brief([_file("a.py", _hits(keys))])
    line = next(ln for ln in md.splitlines() if ln.startswith(f"* *{label}:*"))
    for n, key in enumerate(keys, start=2):
        assert f"{signal_display_name(key)} `{key}: {n}`" in line


def test_structural_keywords_not_linear_code():
    md = _brief([_file("a.py", _hits(["structural_boundaries"]))])
    assert "Structural Keywords (return/def/void/export) `structural_boundaries: 2`" in md
    assert "Sequential Logic" not in md


def test_mixed_responsibility_line_uses_display_names():
    fp = {"Alpha": 1.0, "Beta": 1.01}
    md = _brief([_file("a.py", _hits(["structural_boundaries", "safety_bypasses"]), fp)])
    line = next(ln for ln in md.splitlines() if "Top Architectural Signatures:" in ln)
    for n, key in ((3, "safety_bypasses"), (2, "structural_boundaries")):
        assert f"{signal_display_name(key)} ({key}: {n})" in line
