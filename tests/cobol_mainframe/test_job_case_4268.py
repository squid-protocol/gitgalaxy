"""#4268: the committed job case `tests/equivalence/jobs/carddemo-job-tranrept.json` (CardDemo TRANREPT STEP05R ->
STEP10R). Pins its wiring against the two real step cases without Docker; the proof is `equivalence.py run
carddemo-job-tranrept`. A job case sits outside the per-case directory glob so the per-program enumerators never see it."""

from __future__ import annotations

import json

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_job as ej  # noqa: E402

NAME = "carddemo-job-tranrept"
CASE_FILE = "case" + ".json"


def test_the_job_case_loads_by_name_and_is_not_a_program_case():
    job = eq.load_case(NAME)
    assert job["kind"] == "job" and job["name"] == NAME
    assert not (eq.CASES / NAME / CASE_FILE).exists()
    assert NAME not in {p.parent.name for p in eq.CASES.glob("*/" + CASE_FILE)}


def test_the_job_wiring_passes_check_job_over_the_real_step_cases():
    job = eq.load_case(NAME)
    cases = {n: eq.load_case(n) for n in ej.step_names(job)}
    ej.check_job(job, cases)
    assert ej.step_names(job) == ["carddemo-sort-tranrept", "carddemo-trnrpt"]
    feed = job["steps"][1]["feeds"]["TRANFILE"]
    assert feed == {"step": "carddemo-sort-tranrept", "dd": "SORTOUT"}
    assert cases["carddemo-trnrpt"]["datasets"]["TRANFILE"]["reclen"] == 350


def test_the_job_case_file_is_valid_json_with_notes():
    text = (eq.CASES / "jobs" / f"{NAME}.json").read_text(encoding="utf-8")
    assert json.loads(text)["notes"]


def _step(**ds):
    return {"corpus": "c", "program": "P", "datasets": {"IN": {"organization": "sequential", "reclen": 10},
                                                          "PARM": {"organization": "sequential", "reclen": 10},
                                                          "OUT": {"organization": "sequential", "reclen": 10,
                                                                  "compare": True}}}  # fmt: skip


def test_the_shared_parameter_card_is_the_sort_window_not_the_step_cases_own():
    job = eq.load_case(NAME)
    card = (eq.CASES / "jobs" / job["steps"][1]["inputs"]["DATEPARM"]).read_text(encoding="utf-8")
    assert card.split() == ["2022-01-01", "2022-07-06"]  # STEP05R's SYMNAMES window (its sort case notes)


def test_an_input_override_is_checked_by_name():
    job = {"steps": [{"case": "a"}, {"case": "b", "feeds": {"IN": {"step": "a", "dd": "OUT"}},
                                     "inputs": {"PARM": "tranrept-dateparm.txt"}}]}  # fmt: skip
    cases = {"a": _step(), "b": _step()}
    ej.check_job(job, cases)
    for bad, why in (({"NOPE": "tranrept-dateparm.txt"}, "not one of its datasets"),
                     ({"IN": "tranrept-dateparm.txt"}, "also fed"),
                     ({"PARM": "missing.txt"}, "no file missing.txt")):  # fmt: skip
        job["steps"][1]["inputs"] = bad
        with pytest.raises(ej.Unsupported, match=why):
            ej.check_job(job, cases)


def test_the_posttran_intcalc_job_feeds_the_two_indexed_files_posttran_leaves():
    """#8879: INTCALC's ACCTFILE / TCATBALF are POSTTRAN's compared KSDS outputs (same keys and record lengths); its
    XREFFILE / DISCGRP are CardDemo's shipped files, so both steps agree on one data set."""
    job = eq.load_case("carddemo-job-posttran-intcalc")
    cases = {n: eq.load_case(n) for n in ej.step_names(job)}
    ej.check_job(job, cases)
    step = job["steps"][1]
    assert step["feeds"] == {dd: {"step": "carddemo-posttran", "dd": dd} for dd in ("ACCTFILE", "TCATBALF")}
    assert set(step["inputs"]) == {"XREFFILE", "DISCGRP"}
    assert all(v.startswith(ej.CORPUS_PREFIX + "app/data/ASCII/") for v in step["inputs"].values())
    assert cases["carddemo-intcalc"]["parm"] == "2022071800"


def test_the_real_cbstm03a_case_with_subprograms_is_a_valid_job_step():
    """#8884: CREASTMT STEP040 (CBSTM03A CALLs CBSTM03B) is a batch case with `subprograms`, so a job may run it."""
    cbstm = eq.load_case("carddemo-cbstm03a")
    assert cbstm["subprograms"] == ["app/cbl/CBSTM03B.CBL"]
    job = {"name": "j", "kind": "job", "job": "CREASTMT",
           "steps": [{"case": "carddemo-sort-tranrept"}, {"case": "carddemo-cbstm03a"}]}  # fmt: skip
    ej.check_job(job, {n: eq.load_case(n) for n in ej.step_names(job)})


def test_the_cbstm03a_port_carries_the_called_program_for_the_java_side():
    """#8884: the Java side of a job step runs the step case's own committed port, which holds CBSTM03B too."""
    port = eq.CASES / "carddemo-cbstm03a" / "port" / "service"
    assert {f.name for f in port.glob("*.java")} >= {"Cbstm03aService.java", "Cbstm03bService.java"}
