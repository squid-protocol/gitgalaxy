"""#8886 slice 1: CardDemo's nightly, the job `BatchForge` generates against the COBOL chain of #8885.

`tests/tools/equivalence_forged_job.py` forges each JCL job of `carddemo-nightly` from the real JCL, replays the forged
guard (`JclConditions`, compiled with javac) over the chain's step return codes and compares the step order, run or
bypass and the DD wiring with the case. The chain's report is embedded here (the shape `equivalence.py run
carddemo-nightly` writes, trimmed to what the comparison reads), so no Docker is needed; the corpus and a JDK are.

Pinned result: 9 of 9 steps equal. TRANBKP's `//PRC001.FILEIN` / `FILEOUT` are PROC override DDs; slice 1 found
`galaxy_ir.job_dds` dropped them (7 of 9), and it now reads them (the override replaces the procedure's DD of that name
for that procedure step, else is added; `test_batch_jobs.py`). One feed stays unchecked: TRANIDX's `TRANKSDS`.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence_forged_job as efj  # noqa: E402

SPEC = json.loads((REPO / "tests/equivalence/jobs/carddemo-nightly.forged.json").read_text(encoding="utf-8"))
CASE = json.loads((REPO / "tests/equivalence/jobs/carddemo-nightly.json").read_text(encoding="utf-8"))
CORPUS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora")) / SPEC["corpus"]

needs_corpus = pytest.mark.skipif(not CORPUS.is_dir(), reason="the CardDemo corpus is not checked out")
needs_javac = pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")


def _cobol(rc: str) -> dict:
    return {"return_code": {"cobol": rc, "java": rc}}


REPORT = {
    "case": "carddemo-nightly",
    "ibm_stop": {
        "step": "carddemo-sort-creastmt",
        "reason": "ICE043A",
        "job": "CREASTMT",
        "not_reached": ["creastmt-step020", "carddemo-cbstm03a"],
    },
    "steps": [
        {"case": "carddemo-posttran", **_cobol("4")},
        {"case": "carddemo-intcalc", **_cobol("0")},
        {"case": "tranbkp-idcams", "rc": 0, "model_only": False},
        {"case": "carddemo-sort-combtran", **_cobol("0")},
        {"case": "combtran-step10-idcams", "rc": 0, "model_only": False},
        {"case": "carddemo-sort-creastmt", **_cobol("0")},
        {"case": "carddemo-tranidx", "model_only": True, "stopped": "the IDCAMS model refuses"},
    ],
}


def test_the_chain_rcs_come_from_the_report_and_the_stop_gets_the_stop_rc():
    assert efj.chain_rcs(REPORT) == {
        "carddemo-posttran": 4,
        "carddemo-intcalc": 0,
        "tranbkp-idcams": 0,
        "carddemo-sort-combtran": 0,
        "combtran-step10-idcams": 0,
        "carddemo-sort-creastmt": efj.STOP_RC,
        "carddemo-tranidx": None,
    }


def test_the_spec_names_every_step_of_the_case_once_in_order():
    assert [m["case"] for m in SPEC["steps"]] == [s["case"] for s in CASE["steps"]]


@pytest.fixture(scope="module")
def result():
    return efj.compare(SPEC, CASE, REPORT, CORPUS)


@needs_corpus
@needs_javac
def test_every_step_of_the_nightly_is_equal(result):
    status = {r["case"]: r["status"] for r in result["rows"]}
    assert [c for c, s in status.items() if s != "equal"] == []
    assert sum(s == "equal" for s in status.values()) == 9


@needs_corpus
@needs_javac
def test_the_proc_override_dds_are_in_the_forged_plan(result):
    rows = {r["case"]: r for r in result["rows"]}
    assert rows["tranbkp-idcams"]["issues"] == []
    assert rows["combtran-step10-idcams"]["issues"] == []
    assert [o["dd"] for o in result["overrides"]["TRANBKP"]] == ["FILEIN", "FILEOUT"]
    (step,) = (s for s in result["forged"]["TRANBKP"] if s["name"] == "STEP05R.PRC001")
    assert "FILEOUT" in step["dds"] and "FILEIN" in step["dds"]
    assert rows["carddemo-tranidx"]["notes"] == ["feeds TRANKSDS: unchecked, no forged DD TRANKSDS"]


@needs_corpus
def test_the_forge_reads_the_scans_job_dds_rows_not_a_mirror_of_the_override_rule(tmp_path):
    """Slice 1 of #8886 part 2: the facts come from a real scan of CardDemo's JCL (`GalaxyIR.job_dds` / `job_steps`)."""
    ir = efj.scan_estate(CORPUS / SPEC["jcl_dir"], CORPUS / SPEC["proc_dir"], tmp_path)
    fact, dds, over = efj.job_facts(ir, "jcl/TRANBKP.jcl")
    assert dds == [d for d in ir.job_dds() if d["file"] == "jcl/TRANBKP.jcl"] and fact in ir.job_steps()
    assert [(o["proc_step"], o["dd"], o["source"]) for o in over] == [
        ("PRC001", "FILEIN", "jcl/TRANBKP.jcl"),
        ("PRC001", "FILEOUT", "jcl/TRANBKP.jcl"),
    ]
    assert all(d["source"].startswith("proc/") for d in dds if d["proc_step"] and d not in over)


@needs_corpus
@needs_javac
def test_the_forged_guard_runs_the_chain_and_bypasses_what_it_did_not_reach(result):
    rows = {r["case"]: r for r in result["rows"]}
    assert rows["carddemo-sort-creastmt"]["decision"] == {"STEP010": "run"}
    assert rows["creastmt-step020"]["decision"] == {"STEP020": "bypass"}
    assert rows["carddemo-cbstm03a"]["decision"] == {"STEP040": "bypass"}
    assert rows["carddemo-tranidx"]["decision"] == dict.fromkeys(("STEP20", "STEP25", "STEP30"), "run")
    assert rows["tranbkp-idcams"]["decision"]["STEP10"] == "run"  # COND=(4,LT) with every earlier RC 0
    assert result["unmodelled"] == {"CREASTMT": ["DELDEF01", "STEP030"]}


@needs_corpus
@needs_javac
def test_a_chain_that_ran_a_step_the_forged_guard_bypasses_is_a_difference():
    report = copy.deepcopy(REPORT)
    report["ibm_stop"]["not_reached"] = []  # the chain says STEP020 and STEP040 ran after the RC 16 step
    rows = {r["case"]: r for r in efj.compare(SPEC, CASE, report, CORPUS)["rows"]}
    assert rows["creastmt-step020"]["status"] == "differs"
    assert rows["creastmt-step020"]["issues"] == ["STEP020: forged guard bypass, chain ran"]
