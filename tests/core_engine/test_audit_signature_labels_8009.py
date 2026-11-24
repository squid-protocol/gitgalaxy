"""The audit JSON names each signal by its display name (gitgalaxy#8009, slice 2).

"7. Structural Signatures (Net Mitigated Signals)" used to be keyed by FRIENDLY_MAP
labels (title-cased keys where it had none), which disagreed with the display
layer and the LLM brief for ~80 signals. Pinned here for every SIGNAL_SCHEMA key.
"""

import json

from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, signal_display_name

SCHEMA = RECORDING_SCHEMAS["SIGNAL_SCHEMA"]
SIGS = "7. Structural Signatures (Net Mitigated Signals)"


def _signatures(tmp_path, hit_vector):
    out = tmp_path / "audit.json"
    AuditRecorder().generate_report(
        [
            {
                "path": "src/a.py",
                "name": "a.py",
                "lang_id": "python",
                "directory_group": "src",
                "total_loc": 10,
                "telemetry": {},
                "hit_vector": hit_vector,
                "functions": [],
            }
        ],
        [],
        {"directory_groups": {}},
        {},
        {"engine": "Test", "target_directory": str(tmp_path)},
        str(out),
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    return payload["6. Parsed Files (Scanned Artifacts)"]["src"]["Files"]["src/a.py"][SIGS]


def test_every_signal_is_keyed_by_its_display_name_in_schema_order(tmp_path):
    hits = list(range(1, len(SCHEMA) + 1))
    sigs = _signatures(tmp_path, hits)
    expected = [signal_display_name(k) for k in SCHEMA]
    assert len(set(expected)) == len(SCHEMA), "display names must stay unique or the dict drops keys"
    assert list(sigs) == expected
    assert list(sigs.values()) == hits


def test_the_issue_named_signals_read_as_what_they_count(tmp_path):
    sigs = _signatures(tmp_path, [1] * len(SCHEMA))
    assert signal_display_name("structural_boundaries") in sigs
    assert "Sequential Logic Declarations" not in sigs


def test_weighted_view_mitigation_keys_use_display_names(tmp_path):
    from gitgalaxy.metrics.signal_processor import WEIGHTED_SIGNALS

    keys = sorted(WEIGHTED_SIGNALS)
    out = tmp_path / "audit.json"
    AuditRecorder().generate_report(
        [
            {
                "path": "src/a.py",
                "name": "a.py",
                "lang_id": "python",
                "directory_group": "src",
                "total_loc": 10,
                "telemetry": {"weighted_signals": dict.fromkeys(keys, 1.5)},
                "hit_vector": [],
                "functions": [],
            }
        ],
        [],
        {"directory_groups": {}},
        {},
        {"engine": "Test", "target_directory": str(tmp_path)},
        str(out),
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    prof = payload["6. Parsed Files (Scanned Artifacts)"]["src"]["Files"]["src/a.py"]
    labels = {k for sect in prof.values() if isinstance(sect, dict) for k in sect if k.endswith("(Weighted View)")}
    for key in keys:
        shown = signal_display_name(key)
        if shown != key:
            assert f"{shown} (Weighted View)" in labels
    assert "High-Risk Execution Commands (Weighted View)" not in labels
