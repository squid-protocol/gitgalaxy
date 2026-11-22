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


def _sort_job(writer_reclen, writer_program, reader_reclen):
    """A DFSORT-shaped writer feeding a reader (stub cases, no corpus): the join `_check_feed` judges."""
    writer = _step()
    writer["program"] = writer_program
    writer["datasets"]["OUT"]["reclen"] = writer_reclen
    reader = _step()
    reader["datasets"]["IN"]["reclen"] = reader_reclen
    job = {"steps": [{"case": "w"}, {"case": "r", "feeds": {"IN": {"step": "w", "dd": "OUT"}}}]}
    return job, {"w": writer, "r": reader}


def test_a_dfsort_outrec_shorter_than_the_next_lrecl_is_refused_with_the_ibm_citation_never_padded():
    """CardDemo CREASTMT STEP010 writes 328 bytes under a 350-byte SORTOUT LRECL. IBM: ICE043A reason code 9 ends the
    step (SC23-6879), so the join is refused with that citation; it is never padded (register F4)."""
    job, cases = _sort_job(328, ej.DFSORT_PROGRAM, 350)
    with pytest.raises(ej.Unsupported, match=r"record length 350, w\.OUT writes 328") as e:
        ej.check_job(job, cases)
    assert all(t in str(e.value) for t in ("ICE043A", "reason code 9", "no pad is guessed"))


def test_the_ice043a_citation_is_only_for_a_dfsort_step_writing_fewer_bytes_than_read():
    for writer_reclen, program in ((400, ej.DFSORT_PROGRAM), (328, "NOTDFSORT")):
        job, cases = _sort_job(writer_reclen, program, 350)
        with pytest.raises(ej.Unsupported, match=r"writes") as e:
            ej.check_job(job, cases)
        assert "ICE043A" not in str(e.value)


# -- ibm_stops (#8884): CREASTMT's SORT -> IDCAMS -> CBSTM03A, IBM ends it at STEP010 (stub cases, no corpus) ------------
def _stopped_job(writer_reclen=328, reader_reclen=350, program=None, stop=None):
    """A DFSORT-shaped writer, a middle step that reads it (the join IBM stops at) and a last step: three stub cases."""
    job, cases = _sort_job(writer_reclen, program or ej.DFSORT_PROGRAM, reader_reclen)
    job["steps"].append({"case": "z"})
    cases["z"] = _step()
    job["ibm_stops"] = stop or {"step": "w", "reason": "ICE043A"}
    return job, cases


def test_a_declared_ice043a_stop_makes_the_short_dfsort_join_acceptable_and_names_the_stopped_step():
    job, cases = _stopped_job()
    assert ej.ibm_stop(job) == 0
    ej.check_job(job, cases)
    del job["ibm_stops"]  # undeclared, the same join is still refused with the citation
    with pytest.raises(ej.Unsupported, match=r"record length 350, w\.OUT writes 328") as e:
        ej.check_job(job, cases)
    assert "ICE043A" in str(e.value)


def test_a_declared_stop_that_does_not_hold_is_refused():
    """Nothing is declared stopped that IBM would not stop: equal lengths, a non-DFSORT writer, a bad declaration or
    the last step."""
    job, cases = _stopped_job(reader_reclen=328)
    with pytest.raises(ej.Unsupported, match="IBM does not end the job there"):
        ej.check_job(job, cases)
    job, cases = _stopped_job(program="NOTDFSORT")
    with pytest.raises(ej.Unsupported):
        ej.check_job(job, cases)
    for bad in ({"step": "nope", "reason": "ICE043A"}, {"step": "w", "reason": "X"}):
        job, cases = _stopped_job(stop=bad)
        with pytest.raises(ej.Unsupported):
            ej.check_job(job, cases)
    job, cases = _stopped_job(stop={"step": "z", "reason": "ICE043A"})
    with pytest.raises(ej.Unsupported, match="last step"):
        ej.check_job(job, cases)
