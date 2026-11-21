"""#8413: the capability ledger's "JCL step flow" row counts the IBM-written GDG, restart and data-flow scenarios,
each reproduced live by its resolver (not read back from a stored number)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E402

import capability_ledger as cl  # noqa: E402


def _n(case: str) -> int:
    return len(json.loads((cl.JCL_CASES / case / "scenarios.json").read_text(encoding="utf-8"))["scenarios"])


def test_each_case_is_counted_in_full_and_every_answer_is_reproduced():
    got = cl.step_cases_live()
    assert set(got) == {"gdg", "restart", "dataflow"}
    for case, (ok, n) in got.items():
        assert n == _n(case) and n > 0, case
        assert ok == n, case


def test_the_step_flow_total_includes_those_scenarios():
    jf = cl.jcl_step_flow()
    ok, n = jf["fixture"]
    assert n >= sum(_n(c) for c in ("gdg", "restart", "dataflow"))
    assert ok == n


def _all_scenarios() -> list[dict]:
    out = []
    for f in cl._answer_files():
        doc = json.loads(f.read_text(encoding="utf-8"))
        out += doc.get("scenarios") or doc.get("resolve", []) + doc.get("flow", [])
    return out


def test_the_row_counts_every_answer_file_on_main_assumed_scenarios_apart():
    names = set(cl.jcl_answer_sets())
    assert {"fixture/ifflow_scenarios.json", "fixture/scenarios.json", "ifelse/scenarios.json", "proc/scenarios.json",
            "gdg/scenarios.json", "restart/scenarios.json", "dataflow/scenarios.json"} <= names  # fmt: skip
    allsc = _all_scenarios()
    assumed = sum(cl._is_assumed(s) for s in allsc)
    jf = cl.jcl_step_flow()
    assert jf["fixture"][1] == len(allsc) - assumed
    assert jf["assumed"][1] == assumed and assumed > 0
    assert jf["fixture"][0] == jf["fixture"][1] and jf["assumed"][0] == jf["assumed"][1]


def test_a_new_case_directory_is_counted_with_no_code_edit(tmp_path, monkeypatch):
    import shutil

    shutil.copytree(cl.JCL_CASES, tmp_path / "jcl")
    new = tmp_path / "jcl" / "brandnew"
    new.mkdir()
    (new / "FLOW.jcl").write_text(
        "//ONEJOB JOB\n//S1 EXEC PGM=IEFBR14\n//S2 EXEC PGM=IEFBR14,COND=(4,LT,S1)\n", encoding="utf-8"
    )
    doc = {"fixture": "FLOW.jcl", "scenarios": [
        {"id": "a", "job": "ONEJOB", "given": {"S1": {"rc": 0}, "S2": {"rc": 0}}, "expect": {"S1": "run", "S2": "run"}},
        {"id": "b", "job": "ONEJOB", "given": {"S1": {"rc": 8}}, "expect": {"S1": "run", "S2": "bypass"}, "assumed": "A1"},
    ]}  # fmt: skip
    (new / "scenarios.json").write_text(json.dumps(doc), encoding="utf-8")
    before = cl.jcl_step_flow()
    monkeypatch.setattr(cl, "JCL_CASES", tmp_path / "jcl")
    after = cl.jcl_step_flow()
    assert after["fixture"][1] == before["fixture"][1] + 1 and after["fixture"][0] == before["fixture"][0] + 1
    assert after["assumed"][1] == before["assumed"][1] + 1
    assert "brandnew/scenarios.json" in cl.mvs38j_tier2()["unchecked"]


def test_the_tier_two_note_is_read_from_the_probe_files_and_the_doc():
    t = cl.mvs38j_tier2()
    for name, v in t["checked"].items():
        probe = cl.JCL_CASES / name.split("/")[0] / cl.PROBE_FILE
        got = json.loads(probe.read_text(encoding="utf-8"))["results"]
        assert v["ran"] == len(got) and v["agree"] == sum(r["verdict"] == "agree" for r in got)
    assert {"fixture/scenarios.json", "proc/scenarios.json"} <= set(t["checked"])
    assert "fixture/ifflow_scenarios.json" in t["unchecked"] and "fixture/ifflow_scenarios.json" not in t["checked"]
    for construct in ("IF / THEN / ELSE", "JCLLIB", "INCLUDE", "SET", "CICS"):
        assert construct in t["cannot_test"]
