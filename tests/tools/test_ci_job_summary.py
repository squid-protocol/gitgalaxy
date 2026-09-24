"""#935: the GitHub Actions Job Summary built from a scan's audit report.

Sibling-module import pattern per CLAUDE.md "Testing conventions" (no tests/__init__.py).
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ci_job_summary as cjs  # noqa: E402


def _file(path, lang, loc, magnitude, blast):
    return {
        "1. Artifact Identity": {"Path": path, "Language": lang},
        "3. Architectural Profile": {"Total LOC": loc, "Structural Magnitude": magnitude},
        "8. Dependency Network": {"Direct Downstream (Dependency Blast Radius)": blast},
    }


AUDIT = {
    cjs.TRAIL: {
        "Analysis Context": {
            "Target Root Name": "demo",
            "Total Scan Duration": "1.2 seconds",
            "Zero-Dependency Mode Active": False,
        },
        "Source Control Footprint (Immutable Anchor)": {"Commit Hash (SHA-1)": "0123456789abcdef"},
    },
    cjs.GLOBAL: {
        "summary": {"total_files": 12, "verified_files": 10, "total_loc": 3000, "dominant_language": "python"},
        "composition": {
            "python": {"files": 7, "loc": 2400},
            "markdown": {"files": 2, "loc": 0},
            "c": {"files": 1, "loc": 600},
        },
    },
    cjs.SECURITY: {
        "Audit Status": "SECURE_NO_THREATS_DETECTED",
        "ML Threat Intelligence (XGBoost)": {"Infected Files Detected": 0},
        "Exposed Secrets & Credentials (Quarantined Files)": [],
        "Raw Threat Signature Hits (Total Repository Occurrences)": {"_description": "x", "RCE": 2, "Other": 0},
    },
    cjs.PARSED: {
        "src": {
            "Files": {
                "src/a.py": _file("src/a.py", "Python", 1500, 10.0, 3),
                "src/b|c.py": _file("src/b|c.py", "Python", 900, 99.5, 7),
            }
        },
        "lib": {"Files": {"lib/x.c": _file("lib/x.c", "C", 600, 50.0, 0)}},
    },
}


def test_render_has_every_section():
    text = cjs.render(AUDIT, {"components": [{}, {}, {}]}, top=2)
    assert text.startswith("## GitGalaxy scan: `demo`")
    assert "| Files scanned | 10 |" in text
    assert "| Total LOC | 3,000 |" in text
    assert "| Commit | 0123456789ab |" in text
    assert "| Precision mode | Full Precision |" in text
    # languages ordered by LOC, with shares of total LOC
    assert text.index("| python | 7 | 2,400 | 80.0% |") < text.index("| c | 1 | 600 | 20.0% |")
    assert "| markdown | 2 | 0 | 0.0% |" in text
    # ranked by magnitude across groups, truncated to --top, pipes escaped
    assert "### Top 2 files by structural magnitude" in text
    assert text.index("`src/b\\|c.py`") < text.index("`lib/x.c`")
    assert "src/a.py" not in text
    assert "`SECURE_NO_THREATS_DETECTED`" in text
    assert "RCE: 2" in text and "Other" not in text and "_description" not in text
    assert "**SBOM components:** 3" in text


def test_missing_sections_are_skipped_not_fatal():
    text = cjs.render({cjs.GLOBAL: {"summary": {"total_loc": 5}}})
    assert text.startswith("## GitGalaxy scan\n")
    assert "| Total LOC | 5 |" in text
    assert "### Languages" not in text and "structural magnitude" not in text and "Security" not in text
    assert "none of the sections" in cjs.render({})


def test_main_appends_to_step_summary(tmp_path, monkeypatch):
    audit = tmp_path / "r_audit.json"
    audit.write_text(json.dumps(AUDIT), encoding="utf-8")
    summary = tmp_path / "summary.md"
    summary.write_text("earlier step\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert cjs.main([str(audit), "--sbom", str(tmp_path / "missing_sbom.json")]) == 0
    out = summary.read_text(encoding="utf-8")
    assert out.startswith("earlier step\n## GitGalaxy scan: `demo`")
    assert "SBOM" not in out


def test_main_fails_on_missing_or_unreadable_report(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert cjs.main([str(tmp_path / "nope.json")]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cjs.main([str(bad)]) == 1
