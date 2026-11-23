"""#8884: CREASTMT's steps as one job case, read against the real `app/jcl/CREASTMT.JCL`.

The job cases (`carddemo-job-creastmt`, with the ICE043A stop at STEP010, and `carddemo-job-creastmt-padded`, which runs
the whole chain) are pinned elsewhere against stubs and their own JSON. This reads the JCL itself (`job_flow`) and checks
the step order, the dataset wiring and the record lengths the cases claim, plus that the SORT control statements lower to
the committed SORT cases. No Docker; the run is `equivalence.py run carddemo-job-creastmt-padded`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.source_text import read_source

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_job as ej  # noqa: E402

ORIGINAL, PADDED = "carddemo-job-creastmt", "carddemo-job-creastmt-padded"
JCL = (
    Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    / "aws-mainframe-modernization-carddemo/app/jcl/CREASTMT.JCL"
)
# JCL steps a job case does not run, each named in the case notes: DELDEF01 (the KSDS starts empty, its definition is the
# STEP020 DD spec) and STEP030 (IEFBR14 deleting the statement files).
NOT_RUN = ["DELDEF01", "STEP030"]


@pytest.fixture(scope="module")
def rows():
    if not JCL.is_file():
        pytest.skip(f"no CardDemo clone at {JCL}")
    return job_flow.jcl_job_flow(read_source(JCL).text)


def _steps(rows):
    return {r["step_name"]: r for r in rows if r["kind"] == "STEP"}


def _dsn(rows, step, dd):
    (row,) = [r for r in rows if r["kind"] == "DD" and r["step_name"] == step and r["dd_name"] == dd]
    return row["dsn"]


def _sysin(rows, step):
    (row,) = [r for r in rows if r["kind"] == "INSTREAM" and r["step_name"] == step and r["dd_name"] == "SYSIN"]
    return row["instream"]


def test_the_jcl_steps_are_the_job_cases_steps_plus_the_two_the_notes_name(rows):
    steps = _steps(rows)
    assert [(n, s["program"], s["cond"]) for n, s in steps.items()] == [
        ("DELDEF01", "IDCAMS", None),
        ("STEP010", "SORT", None),
        ("STEP020", "IDCAMS", "(0,NE)"),
        ("STEP030", "IEFBR14", "(0,NE)"),
        ("STEP040", "CBSTM03A", "(0,NE)"),
    ]
    for name in (ORIGINAL, PADDED):
        job = eq.load_case(name)
        assert job["job"] == "CREASTMT"
        assert ej.step_names(job)[1:] == ["creastmt-step020", "carddemo-cbstm03a"]
        for skipped in NOT_RUN:
            assert skipped in job["notes"], (name, skipped)


@pytest.mark.parametrize("name", [ORIGINAL, PADDED])
def test_the_feeds_and_the_cluster_are_the_datasets_the_jcl_hands_from_step_to_step(rows, name):
    job = eq.load_case(name)
    sort, idc, prog = job["steps"]
    # STEP010 SORTOUT is STEP020 INFILE; STEP020 OUTFILE is STEP040 TRNXFILE (the same KSDS).
    seq = _dsn(rows, "STEP010", "SORTOUT")
    assert seq == _dsn(rows, "STEP020", "INFILE")
    ksds = _dsn(rows, "STEP020", "OUTFILE")
    assert ksds == _dsn(rows, "STEP040", "TRNXFILE")
    assert idc["feeds"] == {"INFILE": {"step": sort["case"], "dd": "SORTOUT"}}
    assert prog["feeds"] == {"TRNXFILE": {"step": idc["case"], "dd": "OUTFILE"}}
    assert idc["idcams"]["dds"]["OUTFILE"]["cluster"] == ksds
    assert "REPRO INFILE(INFILE) OUTFILE(OUTFILE)" in _sysin(rows, "STEP020")
    assert (ej.JOBS / idc["idcams"]["deck"]).read_text(encoding="utf-8").split() == _sysin(rows, "STEP020").split()


@pytest.mark.usefixtures("rows")  # skips the test with no clone
def test_the_jcl_record_lengths_are_the_idcams_dds_and_only_the_original_sort_misses_them():
    text = read_source(JCL).text
    assert "LRECL=350" in text and "RECORDSIZE(350 350)" in text
    orig, padded = eq.load_case(ORIGINAL), eq.load_case(PADDED)
    for job in (orig, padded):
        dds = job["steps"][1]["idcams"]["dds"]
        assert dds["INFILE"]["reclen"] == dds["OUTFILE"]["reclen"] == 350
    assert eq.load_case("carddemo-sort-creastmt")["datasets"]["SORTOUT"]["reclen"] == 328
    assert eq.load_case("carddemo-sort-creastmt-padded")["datasets"]["SORTOUT"]["reclen"] == 350
    assert orig["ibm_stops"] == {"step": "carddemo-sort-creastmt", "reason": "ICE043A"}
    assert "ibm_stops" not in padded


def test_the_two_variants_differ_only_in_the_sort_step():
    orig, padded = eq.load_case(ORIGINAL), eq.load_case(PADDED)
    assert orig["steps"][0] == {"case": "carddemo-sort-creastmt"}
    assert padded["steps"][0] == {"case": "carddemo-sort-creastmt-padded"}

    def renamed(steps):  # the IDCAMS step's feed names the SORT step; make that one name
        return [
            {**s, "feeds": {k: {**v, "step": "SORT"} for k, v in s["feeds"].items()}} if "idcams" in s else s
            for s in steps
        ]

    assert renamed(orig["steps"][1:]) == renamed(padded["steps"][1:])


def test_the_jcl_sort_statements_lower_to_the_original_case_and_the_padded_one_adds_the_pad(rows):
    from gitgalaxy.tools.cobol_to_java.det import dfsort

    sysin = _sysin(rows, "STEP010")
    assert "OUTREC FIELDS=(1:263,16,17:1,262,279:279,50)" in " ".join(sysin.split())
    want = dfsort.cobol_program(dfsort.parse(sysin), 350, ["SORTIN"])
    assert (eq.CASES / "carddemo-sort-creastmt" / "DFSORTST.cbl").read_text(encoding="utf-8") == want
    padded = dfsort.parse(" SORT FIELDS=(263,16,CH,A,1,16,CH,A)\n OUTREC FIELDS=(1:263,16,17:1,262,279:279,50,329:22X)")
    want = dfsort.cobol_program(padded, 350, ["SORTIN"])
    assert (eq.CASES / "carddemo-sort-creastmt-padded" / "DFSORTST.cbl").read_text(encoding="utf-8") == want


def test_both_variants_pass_check_job_over_the_real_step_cases():
    for name in (ORIGINAL, PADDED):
        job = eq.load_case(name)
        ej.check_job(job, ej.load_steps(job, eq.load_case))
