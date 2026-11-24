"""#8886: the proven det ports linked into the forge's generated Spring Batch jobs.

The job case `tests/equivalence/jobs/carddemo-job-posttran-intcalc-forged.json` runs CardDemo's POSTTRAN then INTCALC
program steps through `JclJobLauncher` (the generated `<Job>JobConfig`'s own DD wiring and PARM, the proven det port as
the step's service) and compares RETURN-CODE and every output with the same GnuCOBOL run. These tests pin the wiring
without Docker; the proof is `equivalence.py run carddemo-job-posttran-intcalc-forged` (gated e2e test below)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_java as ejava  # noqa: E402
import equivalence_job as ej  # noqa: E402

NAME = "carddemo-job-posttran-intcalc-forged"


def _case(**forged):
    fj = {"job": "POSTTRAN", "step": "STEP15", "config": "PosttranJobConfig", "dds": "DDS_STEP15"} | forged
    return {"name": "x", "program": "CBTRN02C", "datasets": {}, "forged_job": fj}


def _real():
    case = eq.load_case("carddemo-posttran")
    return case | {"forged_job": eq.load_case(NAME)["steps"][0]["forged_job"]}


def test_the_job_passes_check_job_over_the_real_step_cases():
    job = eq.load_case(NAME)
    ej.check_job(job, {n: eq.load_case(n) for n in ej.step_names(job)})
    assert ej.step_names(job) == ["carddemo-posttran", "carddemo-intcalc"]


def test_each_step_names_the_forges_generated_job_config():
    job = eq.load_case(NAME)
    got = [(s["forged_job"]["job"], s["forged_job"]["config"], s["forged_job"]["dds"]) for s in job["steps"]]
    assert got == [("POSTTRAN", "PosttranJobConfig", "DDS_STEP15"), ("INTCALC", "IntcalcJobConfig", "DDS_STEP15")]


def test_a_forged_case_enters_through_the_job_launcher():
    case = _real()
    entry, members = ejava.forged_job_parts(case)
    assert 'forgedJob("POSTTRAN", "STEP15", "PosttranJobConfig", "DDS_STEP15")' in entry
    assert "jobLauncher.launch(job)" in members
    text = ejava.equivalence_test(case)
    assert "forgedJob(" in text and "spring.batch.job.enabled=false" in text and "JclJobLauncher jobLauncher" in text


def test_a_step_the_job_never_ran_names_what_it_did_run():
    """CREASTMT STEP040 through the forged job (#8886): DELDEF01 runs, STEP010 FAILS (the forge has no LRECL for the TRANSACT
    KSDS: its RECORDSIZE is in TRANFILE.jcl, another job, and reading it as RECFM=F would be a guess) and COND=(0,NE)
    bypasses the rest. The harness says so instead of only "ran no step"."""
    _, members = ejava.forged_job_parts(_real())
    assert '"job " + job + " ran no step " + step + "; it ran "' in members
    assert "getExitStatus().getExitCode()" in members and "getFailureExceptions()" in members


def test_a_plain_case_is_unchanged():
    plain = {k: v for k, v in _real().items() if k != "forged_job"}
    text = ejava.equivalence_test(plain)
    assert "forgedJob(" not in text and "JclJobLauncher" not in text and "spring.batch.job.enabled" not in text


@pytest.mark.parametrize("bad", [{"job": "A B"}, {"step": "1X"}, {"config": "a.b"}, {"dds": ""}])
def test_a_forged_name_that_is_not_an_identifier_is_refused(bad):
    with pytest.raises(SystemExit):
        ejava.forged_job_parts(_case(**bad))


@pytest.mark.parametrize("extra", [{"entries": [{"method": "run"}]}, {"db2": {"x": 1}}])
def test_a_forged_job_with_an_entry_method_or_db2_is_refused(extra):
    with pytest.raises(SystemExit):
        ejava.forged_job_parts(_case() | extra)


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and shutil.which("docker") and shutil.which("mvn")


@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, docker, Maven and the CardDemo corpus")
@pytest.mark.slow(reason="GnuCOBOL chain in docker plus two Spring Boot runs over the forged estate")
def test_both_program_steps_are_equal_to_the_chain_through_the_forged_job():
    import subprocess

    out = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/equivalence.py"), "run", NAME],
        capture_output=True, text=True, encoding="utf-8", timeout=1500,
    )  # fmt: skip
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert "proven over 2 of 2 steps" in out.stdout
