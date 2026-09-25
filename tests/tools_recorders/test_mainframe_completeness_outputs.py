"""
#3506: the mainframe skeleton-completeness report in a scan's own outputs.

  1. Only a scan holding COBOL, JCL, BMS or CSD reads the IR back from the master
     DB; any other scan returns None before touching it (no cost).
  2. The audit report renders GalaxyIR.completeness() as section 7 (end to end in
     tests/golden_master_audit/7_mainframe_skeleton_completeness).
  3. The LLM brief gets one line: the score and the top three missing inputs.
"""

import pytest

from gitgalaxy.galaxyscope import Orchestrator
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder

REPORT = {
    "score": 0.6123,
    "channels": {
        "program calls": {
            "resolved": 3,
            "total": 4,
            "system": 2,
            "ratio": 0.75,
            "gaps": {"missing program": 1, "dynamic target": 0},
        },
        "IMS PSBs": {"resolved": 0, "total": 0, "system": 0, "ratio": None, "gaps": {"DL/I program with no PSB": 0}},
    },  # fmt: skip
    "missing_inputs": [
        {"input": "copybook libraries", "count": 7, "examples": ["CPY1 (a.cbl)"]},
        {"input": "application programs (source or load-module list)", "count": 1, "examples": ["X (a.cbl:9)"]},
        {"input": "BMS map source", "count": 3, "examples": ["M1 (b.cbl:4)"]},
        {"input": "scheduler export (CA-7 / Control-M / TWS)", "count": 12, "examples": ["cross-job order ..."]},
    ],
}


def test_a_scan_without_mainframe_languages_never_reads_the_db(tmp_path):
    graph = [{"path": "a.py", "lang_id": "python"}, {"path": "b.pli", "lang_id": "pli"}]
    assert Orchestrator._mainframe_completeness(graph, str(tmp_path / "absent.db"), "R") is None
    assert Orchestrator._mainframe_completeness([], str(tmp_path / "absent.db"), "R") is None


@pytest.mark.parametrize("lang", ["cobol", "jcl", "bms", "csd"])
def test_a_mainframe_scan_reads_the_ir_back(tmp_path, lang):
    with pytest.raises(FileNotFoundError):  # it went to the DB: here, one that is not there
        Orchestrator._mainframe_completeness([{"path": "x", "lang_id": lang}], str(tmp_path / "absent.db"), "R")


def test_the_audit_section_labels_the_report():
    block = AuditRecorder._completeness_block(REPORT)
    assert block["Score (Mean Channel Ratio)"] == "61.2%"
    assert block["Channels"]["program calls"] == {
        "Resolved": 3,
        "Total": 4,
        "Ratio": "75.0%",
        "System Names (Not Gaps)": 2,
        "Gaps": {"missing program": 1, "dynamic target": 0},
    }
    assert block["Channels"]["IMS PSBs"]["Ratio"] == "N/A"
    assert [m["Input"] for m in block["Missing Inputs"]][0] == "copybook libraries"


def test_the_brief_line_names_the_score_and_the_three_largest_missing_inputs():
    (line, blank) = LLMRecorder._completeness_lines(REPORT)
    assert blank == ""
    assert line.startswith("- **Mainframe skeleton completeness:** 61%")
    assert line.endswith(
        "Top missing inputs: scheduler export (CA-7 / Control-M / TWS) (12 gaps); "
        "copybook libraries (7 gaps); BMS map source (3 gaps)."
    )
    assert LLMRecorder._completeness_lines(None) == []
    assert "n/a" in LLMRecorder._completeness_lines({"score": None, "channels": {}, "missing_inputs": []})[0]
