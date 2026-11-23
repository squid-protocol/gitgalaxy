"""#8886 slice 2: CardDemo's nightly, the Spring jobs `BatchForge` generates, EXECUTED and set against the COBOL chain.

`tests/tools/equivalence_forged_spring.py` forges the estate with only its own programs as skeletons (the real forge),
compiles the generated `<Job>JobConfig` classes with the forge's runtime against Spring Batch 5.1 and runs them on an
in-memory `JobRepository`. A program step calls a stub service returning the chain's COBOL return code (the proven ports
are not linked: a later slice), so what is compared is the generated job's own behaviour: which jobs are generated, the
step order and guard under Spring, the utility steps (IDCAMS / SORT) the runtime runs or refuses.

Pinned result (evidence level: executed under Spring, program bodies stubbed): 2 of 9 case steps equal (POSTTRAN,
INTCALC). TRANBKP, COMBTRAN and TRANIDX are utility-only jobs: the forge lists them and generates no job. CREASTMT is
generated, but its first step (an IDCAMS with more than one command) is refused by the IDCAMS model, so the job fails
as shipped; with `skip-unimplemented` the utility steps log and return 0 and the SORT of STEP020 finds no dataset.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_forged_job as efj  # noqa: E402
import equivalence_forged_spring as efs  # noqa: E402
from test_forged_job_nightly_8886 import CASE, CORPUS, REPORT, SPEC  # noqa: E402

pytestmark = [
    pytest.mark.skipif(not CORPUS.is_dir(), reason="the CardDemo corpus is not checked out"),
    pytest.mark.skipif(shutil.which("javac") is None or efs.classpath() is None, reason="no JDK / Spring Batch jars"),
    pytest.mark.slow(reason="scan + javac of the forged job configs + two Spring runs, once per module"),
]


@pytest.fixture(scope="module")
def res():
    out = efs.scan_and_run(SPEC, CASE, REPORT, CORPUS, efj.chain_rcs)
    assert out is not None
    return out


def _row(res, case):
    return next(r for r in res["rows"] if r["case"] == case)


def test_only_the_application_jobs_are_generated(res):
    kinds = {j: v["kind"] for j, v in res["jobs"].items()}
    assert kinds == {
        "POSTTRAN": "application", "INTCALC": "application", "CREASTMT": "application",
        "TRANBKP": "utility", "COMBTRAN": "utility", "TRANIDX": "utility",
    }  # fmt: skip
    assert set(res["raw"]["strict"]) == {"POSTTRAN", "INTCALC", "CREASTMT"}


@pytest.mark.parametrize("case", ["carddemo-posttran", "carddemo-intcalc"])
def test_a_program_step_runs_under_spring_with_the_chains_return_code(res, case):
    for mode in ("strict", "skip"):
        assert _row(res, case)["modes"][mode]["status"] == "equal"
    assert _row(res, "carddemo-posttran")["modes"]["strict"]["got"] == {"STEP15": "RC=4"}


@pytest.mark.parametrize(
    "case", ["tranbkp-idcams", "carddemo-sort-combtran", "combtran-step10-idcams", "carddemo-tranidx"]
)
def test_a_utility_only_job_has_no_forged_job_to_run(res, case):
    for mode in ("strict", "skip"):
        md = _row(res, case)["modes"][mode]
        assert md["status"] == "no forged job"
        assert "listed not generated" in md["issues"][0]


def test_the_creastmt_chain_fails_as_shipped_and_diverges_when_the_utilities_are_skipped(res):
    strict = res["raw"]["strict"]["CREASTMT"]
    assert strict["status"] == "FAILED" and list(strict["steps"]) == ["DELDEF01"]
    assert "IDCAMS model refuses" in strict["steps"]["DELDEF01"][1]
    skip = res["raw"]["skip"]["CREASTMT"]
    assert skip["steps"]["DELDEF01"][0] == "RC=0" and skip["steps"]["STEP020"][0] == "FAILED"
    assert "NoSuchFileException" in skip["steps"]["STEP020"][1]
    assert "STEP040" not in skip["steps"]
    assert _row(res, "carddemo-sort-creastmt")["modes"]["skip"]["issues"] == ["STEP010: forged RC=0, chain RC=16"]


def test_two_of_nine_steps_are_equal_in_each_mode(res):
    out = efs.render(res, "carddemo-nightly")
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 2 of 9 steps (strict)" in out
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 2 of 9 steps (skip)" in out
    json.dumps(res)  # the result is plain data
