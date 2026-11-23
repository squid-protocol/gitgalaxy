"""#8886 slice 2: CardDemo's nightly, the Spring jobs `BatchForge` generates, EXECUTED and set against the COBOL chain.

`tests/tools/equivalence_forged_spring.py` forges the estate with only its own programs as skeletons (the real forge),
compiles the generated `<Job>JobConfig` classes with the forge's runtime against Spring Batch 5.1 and runs them on an
in-memory `JobRepository`. A program step calls a stub service returning the chain's COBOL return code (the proven ports
are not linked: a later slice), so what is compared is the generated job's own behaviour: which jobs are generated, the
step order and guard under Spring, the utility steps (IDCAMS / SORT) the runtime runs or refuses.

Pinned result (evidence level: executed under Spring, program bodies stubbed, SORT run on seeded data): 2 of 9 case
steps equal (POSTTRAN, INTCALC). TRANBKP, COMBTRAN and TRANIDX are utility-only jobs: the forge lists them and
generates no job by design, so (#8886 slice 6) the harness plans them as application jobs on request (spec key
`forge_utility_jobs`; the forge is untouched) and their steps RUN: every step ends in the forge's own named refusal
or a missing input, none equal (a step `skip-unimplemented` returned 0 for is reported "not run", never equal).
CREASTMT is generated and (#8886 slice 5) runs to RC=0 on all five steps in both modes: DELDEF01
through the IDCAMS model's Java twin, STEP010's SORT on the 100 TRANSACT records the job case reads (the dataset's
RECORDSIZE(350 350) in TRANFILE.jcl is the DCB the forge cannot see in CREASTMT.JCL), STEP020's REPRO, STEP040 on its
stub. The chain's STEP010 ended RC=16 (OUTREC 328 bytes under the DD's LRECL 350, register F4: no pad guessed) and
COND=(0,NE) bypassed STEP020 / STEP040: the forged job runs past where the chain stopped, and the rows say so.
"""

from __future__ import annotations

import hashlib
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


def test_the_utility_only_jobs_are_generated_on_request_and_marked(res):
    kinds = {j: v["kind"] for j, v in res["jobs"].items()}
    assert kinds == {  # the forged-on-request jobs keep their utility class
        "POSTTRAN": "application", "INTCALC": "application", "CREASTMT": "application",
        "TRANBKP": "utility (forged)", "COMBTRAN": "utility (forged)", "TRANIDX": "utility (forged)",
    }  # fmt: skip
    assert set(res["raw"]["strict"]) == set(kinds)


@pytest.mark.parametrize("case", ["carddemo-posttran", "carddemo-intcalc"])
def test_a_program_step_runs_under_spring_with_the_chains_return_code(res, case):
    for mode in ("strict", "skip"):
        assert _row(res, case)["modes"][mode]["status"] == "equal"
    assert _row(res, "carddemo-posttran")["modes"]["strict"]["got"] == {"STEP15": "RC=4"}


BLOCKED = {  # case -> a fragment of the forge's own refusal (strict), the step it fails on
    "tranbkp-idcams": ("STEP05R.PRC001", "SYSIN is a dataset of control statements"),
    "carddemo-sort-combtran": ("STEP05R", "carry no record length (LRECL)"),
    "carddemo-tranidx": ("STEP20", "RELATE(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS) is not in the catalog"),
}


@pytest.mark.parametrize("case", sorted(BLOCKED))
def test_a_forged_utility_job_stops_at_the_forges_named_refusal(res, case):
    """#8886 slice 6: TRANBKP / COMBTRAN / TRANIDX are generated on request; strict fails the job at the step the forge
    names, skip-unimplemented returns 0 for it, and the row says "not run" (never equal)."""
    step, why = BLOCKED[case]
    row = _row(res, case)
    assert row["kind"] == "utility (forged)"
    strict = row["modes"]["strict"]
    assert strict["status"] == "differs" and strict["got"][step] == "FAILED"
    assert why in strict["issues"][0]
    skip = row["modes"]["skip"]
    assert skip["status"] == "differs"
    # a step the forge declines is `steps.utility` (skip returns 0: "not run"); an IDCAMS deck the model runs and
    # refuses (TRANIDX's AIX against a catalog that does not hold the cluster) fails the same in both modes
    head = f"{step}: failed:" if case == "carddemo-tranidx" else f"{step}: not run, skip-unimplemented returned RC=0"
    assert any(i.startswith(head) for i in skip["issues"])


def test_combtrans_reinput_step_never_finds_the_dataset_its_sort_would_write(res):
    """STEP10 REPROs COMBINED(+1), which STEP05R (refused) never wrote: not started in strict, no file in skip."""
    row = _row(res, "combtran-step10-idcams")
    assert row["kind"] == "utility (forged)"
    assert row["modes"]["strict"]["issues"] == ["STEP10: not started (job FAILED before it)"]
    assert "NoSuchFileException" in row["modes"]["skip"]["issues"][0]


def test_creastmts_idcams_deck_runs_under_spring_through_the_model(res):
    """#8886 slice 4: DELDEF01 (DELETE, DELETE CLUSTER, SET MAXCC, DEFINE CLUSTER with DATA CISZ) is lowered to
    `steps.idcams` (the det model's Java twin, the catalog kept per job), not `steps.utility`: it ends RC=0 in both modes."""
    assert [x for x in res["idcams_lowered"] if x.startswith("CREASTMT.")] == ["CREASTMT.DELDEF01"]
    for mode in ("strict", "skip"):
        assert res["raw"][mode]["CREASTMT"]["steps"]["DELDEF01"] == ("RC=0", None)


def test_the_seeded_creastmt_job_runs_to_the_end_in_both_modes(res):
    """With the TRANSACT dataset seeded and its DCB stated, the SORT is lowered and runs: no refusal, no missing file."""
    for mode in ("strict", "skip"):
        job = res["raw"][mode]["CREASTMT"]
        assert job["status"] == "COMPLETED"
        assert {k: v[0] for k, v in job["steps"].items()} == dict.fromkeys(
            ("DELDEF01", "STEP010", "STEP020", "STEP030", "STEP040"), "RC=0"
        )


def test_the_forged_sort_rebuilds_the_seeded_records_as_the_control_statements_say(res):
    """SORT FIELDS=(263,16,CH,A,1,16,CH,A), OUTREC FIELDS=(1:263,16,17:1,262,279:279,50), computed here from the seed
    (not by the port): 100 records of 328 bytes, the card number first, in (card, TRAN-ID) order."""
    seed = (REPO / SPEC["datasets"]["AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS"]["seed"]).read_bytes().split(b"\n")
    recs = sorted((r for r in seed if r), key=lambda r: (r[262:278], r[0:16]))
    want = b"".join(r[262:278] + r[0:262] + r[278:328] for r in recs)
    assert len(recs) == 100 and len(want) == 100 * 328
    for mode in ("strict", "skip"):
        got = res["raw"]["datasets"][mode]["AWS.M2.CARDDEMO.TRXFL.SEQ"]
        assert got == {"size": 32800, "sha256": hashlib.sha256(want).hexdigest()}


def test_the_forged_job_runs_past_the_step_the_chain_stopped_at(res):
    """The chain's STEP010 ended RC=16 (register F4) and bypassed STEP020 / STEP040: the rows differ, by name."""
    for mode in ("strict", "skip"):
        assert _row(res, "carddemo-sort-creastmt")["modes"][mode]["issues"] == ["STEP010: forged RC=0, chain RC=16"]


def test_two_of_nine_steps_are_equal_in_each_mode(res):
    out = efs.render(res, "carddemo-nightly")
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 2 of 9 steps (strict)" in out
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 2 of 9 steps (skip)" in out
    json.dumps(res)  # the result is plain data
