"""#8883: the committed two-job GDG chain `tests/equivalence/jobs/carddemo-job-intcalc-combtran-gdg.json` (CardDemo
INTCALC STEP15 writes SYSTRAN(+1); COMBTRAN STEP05R reads TRANSACT.BKUP(0) and SYSTRAN(0)). Pins its wiring against the
two real step cases without Docker; the proof is `equivalence.py run carddemo-job-intcalc-combtran-gdg`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_gdg as gdg  # noqa: E402
import equivalence_job as ej  # noqa: E402

NAME = "carddemo-job-intcalc-combtran-gdg"
BKUP = "AWS.M2.CARDDEMO.TRANSACT.BKUP"
SYSTRAN = "AWS.M2.CARDDEMO.SYSTRAN"


@pytest.fixture(scope="module")
def job():
    return eq.load_case(NAME)


def _cases(job):
    return {n: eq.load_case(n) for n in ej.step_names(job)}


def test_the_chain_passes_check_job_over_the_real_step_cases(job):
    ej.check_job(job, _cases(job))
    assert ej.step_names(job) == ["carddemo-intcalc", "carddemo-sort-combtran"]
    assert gdg.job_names(job) == ["INTCALC", "COMBTRAN"]  # two jobs: relative numbers resolve afresh at COMBTRAN


def test_comb_tran_reads_the_generation_intcalc_catalogued_and_the_backup(job):
    cat = gdg.Catalog(gdg.check_declarations(job), {BKUP: [b"x" * 350]})
    cat.begin_step("INTCALC")
    assert cat.create(SYSTRAN, b"t" * 350) == f"{SYSTRAN}.G0001V00"
    with pytest.raises(gdg.Unsupported, match="held 0 generation"):
        cat.read(SYSTRAN, "0")  # (0) inside INTCALC is resolved at its start: SYSTRAN was empty
    cat.begin_step("COMBTRAN")
    assert cat.read(SYSTRAN, "0") == (f"{SYSTRAN}.G0001V00", [b"t" * 350])
    assert cat.read(BKUP, "0")[0] == f"{BKUP}.G0001V00"


def test_the_backup_generation_is_whole_350_byte_records(job):
    path = ej.JOBS / job["gdgs"][BKUP]["generations"][0]
    lines = path.read_text(encoding="latin-1").splitlines()
    assert len(lines) == 28 and {len(line) for line in lines} == {350}


def test_a_chain_run_in_one_job_would_not_see_the_generation(job):
    """Collapsing both steps into one job name makes SYSTRAN(0) the pre-job catalog, which is empty: refused."""
    one = {**job, "steps": [{**s, "job": "INTCALC"} for s in job["steps"]]}
    with pytest.raises(ej.Unsupported, match="held 0 generation"):
        ej.check_job(one, _cases(one))
