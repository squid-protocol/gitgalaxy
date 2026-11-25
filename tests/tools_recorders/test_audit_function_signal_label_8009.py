"""gitgalaxy#8009: the audit's per-function metaprogramming count is named by the signal's display name."""

import json

from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.standards.analysis_lens import signal_display_name


def test_function_analysis_key_is_the_display_name(tmp_path):
    out = tmp_path / "audit.json"
    unit = {"name": "fn", "loc": 3, "hit_vector": {"reflection_metaprogramming": 4}}
    AuditRecorder().generate_report(
        [
            {
                "path": "src/a.py",
                "name": "a.py",
                "lang_id": "python",
                "directory_group": "src",
                "total_loc": 10,
                "telemetry": {},
                "functions": [unit],
            }
        ],
        [],
        {"directory_groups": {}},
        {},
        {"engine": "Test", "target_directory": str(tmp_path)},
        str(out),
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    fn = payload["6. Parsed Files (Scanned Artifacts)"]["src"]["Files"]["src/a.py"]["5. Function Analysis"][0]
    key = f"{signal_display_name('reflection_metaprogramming')} Hits"
    assert fn[key] == 4
    assert "Reflection Hits" not in fn
