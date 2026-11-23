"""#8885: the CardDemo nightly as one job case, `tests/equivalence/jobs/carddemo-nightly.json` (POSTTRAN, INTCALC, TRANBKP,
COMBTRAN, CREASTMT, TRANIDX). Pins the wiring and the harness rules it needed (a generation on an IDCAMS step, a KSDS read
by a sort, an IBM stop that ends one JCL job) without Docker; the proof is `equivalence.py run carddemo-nightly`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_gdg as gdg  # noqa: E402
import equivalence_job as ej  # noqa: E402

NAME = "carddemo-nightly"


@pytest.fixture(scope="module")
def job():
    return eq.load_case(NAME)


@pytest.fixture(scope="module")
def cases(job):
    return ej.load_steps(job, eq.load_case)


def test_the_nightly_passes_check_job_over_the_real_step_cases(job, cases):
    ej.check_job(job, cases)
    assert gdg.job_names(job) == ["POSTTRAN", "INTCALC", "TRANBKP", "COMBTRAN", "COMBTRAN", "CREASTMT", "CREASTMT",
                                  "CREASTMT", "TRANIDX"]  # fmt: skip
    assert job["notes"]


def test_the_backup_generation_is_tranbkps_and_combtran_reads_it_with_intcalcs(job):
    steps = {s["case"]: s for s in job["steps"]}
    assert steps["tranbkp-idcams"]["gdg_out"] == {"FILEOUT": "AWS.M2.CARDDEMO.TRANSACT.BKUP"}
    assert steps["carddemo-sort-combtran"]["gdg_in"]["SORTIN1"]["base"] == "AWS.M2.CARDDEMO.TRANSACT.BKUP"
    assert steps["carddemo-intcalc"]["gdg_out"] == {"TRANSACT": "AWS.M2.CARDDEMO.SYSTRAN"}
    assert not any(spec.get("generations") for spec in job["gdgs"].values())  # every generation is a step's output


def test_the_stop_ends_creastmt_and_tranidx_still_runs(job):
    assert ej.ibm_stop(job) == 5
    jobs = gdg.job_names(job)
    assert [n for n, j in zip(ej.step_names(job), jobs, strict=True) if j == "CREASTMT"] == [
        "carddemo-sort-creastmt", "creastmt-step020", "carddemo-cbstm03a"]  # fmt: skip
    assert jobs[-1] == "TRANIDX"


def test_a_later_job_may_not_read_a_step_the_stop_never_reached(job, cases):
    bad = {**job, "steps": [*job["steps"][:-1], {**job["steps"][-1], "feeds": {
        "TRANKSDS": {"step": "creastmt-step020", "dd": "OUTFILE"}}}]}  # fmt: skip
    with pytest.raises(ej.Unsupported, match="never reached"):
        ej.check_job(bad, cases)


def test_a_generation_on_a_cluster_dd_is_refused(job, cases):
    steps = [dict(s) for s in job["steps"]]
    steps[2] = {**steps[2], "gdg_out": {"FILEIN": "AWS.M2.CARDDEMO.TRANSACT.BKUP"}}
    with pytest.raises(ej.Unsupported, match="sequential DD"):
        ej.check_job({**job, "steps": steps}, cases)


def test_a_sequential_dd_may_not_read_a_ksds_unless_an_idcams_step_left_it(job, cases):
    steps = [dict(s) for s in job["steps"]]
    steps[5] = {**steps[5], "feeds": {"SORTIN": {"step": "carddemo-posttran", "dd": "TRANFILE"}}}
    with pytest.raises(ej.Unsupported, match="indexed dataset on both sides"):
        ej.check_job({**job, "steps": steps}, cases)
