"""#8886 slice 2: CardDemo's nightly, the Spring jobs `BatchForge` generates, EXECUTED and set against the COBOL chain.

`tests/tools/equivalence_forged_spring.py` forges the estate with only its own programs as skeletons (the real forge),
compiles the generated `<Job>JobConfig` classes with the forge's runtime against Spring Batch 5.1 and runs them on an
in-memory `JobRepository`. A program step calls a stub service returning the chain's COBOL return code (the proven ports
are not linked here: the job case `carddemo-job-posttran-intcalc-forged` runs POSTTRAN and INTCALC with them, #8886), so what is compared is the generated job's own behaviour: which jobs are generated, the
step order and guard under Spring, the utility steps (IDCAMS / SORT) the runtime runs or refuses.

Pinned result (evidence level: executed under Spring, program bodies stubbed, SORT run on seeded data): 8 of 9 case
steps equal (CREASTMT's three by its ICE043A stop, slice 15) in return code (POSTTRAN, INTCALC, #8886 slice 9's TRANBKP (its three IDCAMS steps; STEP05R's SYSIN is the member
REPROCT of the estate's control library, read from app/ctl), #8886 slice 7's COMBTRAN STEP05R and slice 8's COMBTRAN STEP10 (GDG (+1) resolved once per job), whose SORT over the concatenated
BKUP(0) + SYSTRAN(0) seeds is also checked record by record). TRANBKP, COMBTRAN and TRANIDX are utility-only jobs: the forge lists them and
generates no job by design, so (#8886 slice 6) the harness plans them as application jobs on request (spec key
`forge_utility_jobs`; the forge is untouched) and their steps RUN: their steps end in the forge's own named refusal
or a missing input, but for COMBTRAN STEP05R (a step `skip-unimplemented` returned 0 for is reported "not run", never equal).
#8886 slice 10: TRANIDX's catalog starts with the KSDS TRANBKP STEP10 DEFINEs (spec `catalog_seeds`): STEP20 and STEP25 run
to RC=0, STEP30 (BLDINDEX) is refused by name; the TRANIDX row stays "differs".
#8886 slice 11: the catalogued KSDS holds the records of its dataset file (the 100 TRANSACT seeds), so STEP30 meets the chain's
named refusal: the busiest key's AIX record over RECORDSIZE(350 350) (the chain's data needed 5055 bytes, the seeds 1631).
CREASTMT is generated. DELDEF01 runs through the IDCAMS model's Java twin (RC=0). #8886 slice 15: STEP010's OUTREC builds
328 bytes under SORTOUT's fixed LRECL=350, so the forge emits `steps.ended` RC=16 (DFSORT ICE043A reason 9, SC23-6879; register F4,
no pad guessed) and COND=(0,NE) bypasses STEP020..STEP040, as the chain does: 8 of 9 case steps equal (TRANIDX STEP30 is the
IDC1646I refusal).
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
    # #8886 slices 10-11: the KSDS is catalogued as TRANBKP STEP10 DEFINEs it and loaded from its dataset file, so STEP20 /
    # STEP25 run to RC=0 and the job stops at BLDINDEX, whose busiest-key record is over RECORDSIZE (the chain's refusal)
    "carddemo-tranidx": ("STEP30", "BLDINDEX record for the busiest key needs 1631 bytes, over RECORDSIZE maximum 350"),
}


def test_tranidx_defines_its_alternate_index_and_path_over_the_catalogued_ksds(res):
    """#8886 slice 10: TRANIDX's job catalog starts with TRANBKP STEP10's DEFINE CLUSTER (spec `catalog_seeds`), so
    STEP20 (DEFINE ALTERNATEINDEX RELATE(KSDS)) and STEP25 (DEFINE PATH) end RC=0 under Spring, as the chain's did."""
    for mode in ("strict", "skip"):
        steps = res["raw"][mode]["TRANIDX"]["steps"]
        assert steps["STEP20"] == ("RC=0", None) and steps["STEP25"] == ("RC=0", None)


def test_the_catalog_seed_deck_is_the_named_steps_instream_sysin():
    jcl = "//J JOB\n//A EXEC PGM=X\n//SYSIN DD *\n WRONG\n/*\n//B EXEC PGM=IDCAMS\n//SYSIN DD *\n DEFINE X\n  Y\n/*\n"
    assert efs.jcl_instream_deck(jcl, "B") == " DEFINE X\n  Y"
    with pytest.raises(ValueError):
        efs.jcl_instream_deck(jcl, "C")


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
    if (
        case == "carddemo-tranidx"
    ):  # #8886 slice 12: the refusal cites IDC1646I (register F4), the model's and Java's words agree
        assert "IDC1646I" in strict["issues"][0]
    skip = row["modes"]["skip"]
    assert skip["status"] == "differs"
    # a step the forge declines is `steps.utility` (skip returns 0: "not run"); an IDCAMS deck the model runs and
    # refuses (TRANIDX's BLDINDEX over the loaded KSDS) fails the same in both modes
    head = f"{step}: failed:" if case == "carddemo-tranidx" else f"{step}: not run, skip-unimplemented returned RC=0"
    assert any(i.startswith(head) for i in skip["issues"])


def test_combtrans_sort_concatenates_both_gdg_inputs_and_orders_them_by_the_ebcdic_key(res):
    """#8886 slice 7: BKUP(0) and SYSTRAN(0) are SORTIN's concatenation (the second DD has no name), their DCB (350, F/FB)
    stated by the jobs that write them and attached to COMBTRAN, the seeds the job case's two input files. STEP05R is
    lowered and runs: COMBINED(+1) holds all 50 records (28 + 22), in the EBCDIC order of TRAN-ID (CH), computed here
    from the seeds, not by the port. "equal" for the step is the return code only; the records are checked here."""
    recs = [
        r
        for f in ("sortin1", "sortin2")
        for r in (REPO / f"tests/equivalence/carddemo-sort-combtran/{f}.txt").read_bytes().split(b"\n")
        if r
    ]
    recs.sort(key=lambda r: r[:16].decode("ascii").encode("cp037"))
    want = {"size": 50 * 350, "sha256": hashlib.sha256(b"".join(recs)).hexdigest()}
    for mode in ("strict", "skip"):
        assert res["raw"][mode]["COMBTRAN"]["steps"]["STEP05R"] == ("RC=0", None)
        assert res["raw"]["datasets"][mode]["AWS.M2.CARDDEMO.TRANSACT.COMBINED(G0001V00)"] == want
        assert _row(res, "carddemo-sort-combtran")["modes"][mode]["status"] == "equal"


def test_combtrans_reinput_step_reads_the_generation_the_sort_wrote_in_the_same_job(res):
    """#8886 slice 8: z/OS resolves COMBINED(+1) once per job, so STEP10 reads the generation STEP05R wrote (G0001V00).
    Before, the DatasetResolver counted again after the write, asked for G0002V00 and failed with NoSuchFileException.
    STEP10's REPRO now lands COMBINED's 50 records (17500 bytes) in the TRANSACT KSDS, byte for byte."""
    row = _row(res, "combtran-step10-idcams")
    assert row["kind"] == "utility (forged)"
    for mode in ("strict", "skip"):
        assert row["modes"][mode]["status"] == "equal"
        assert row["modes"][mode]["issues"] == []
        ds = res["raw"]["datasets"][mode]
        want = ds["AWS.M2.CARDDEMO.TRANSACT.COMBINED(G0001V00)"]
        assert want["size"] == 50 * 350
        assert ds["AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS"] == want
        assert "AWS.M2.CARDDEMO.TRANSACT.COMBINED(G0002V00)" not in ds


def test_creastmts_idcams_deck_runs_under_spring_through_the_model(res):
    """#8886 slice 4: DELDEF01 (DELETE, DELETE CLUSTER, SET MAXCC, DEFINE CLUSTER with DATA CISZ) is lowered to
    `steps.idcams` (the det model's Java twin, the catalog kept per job), not `steps.utility`: it ends RC=0 in both modes."""
    assert [x for x in res["idcams_lowered"] if x.startswith("CREASTMT.")] == ["CREASTMT.DELDEF01"]
    for mode in ("strict", "skip"):
        assert res["raw"][mode]["CREASTMT"]["steps"]["DELDEF01"] == ("RC=0", None)


def test_the_creastmt_job_stops_at_step010_as_the_chain_does_in_both_modes(res):
    """#8886 slice 15: STEP010's OUTREC builds 328 bytes under SORTOUT's fixed LRECL=350, so DFSORT ends it (ICE043A reason 9,
    SC23-6879; register F4): the forged step is `steps.ended` RC=16 and COND=(0,NE) bypasses STEP020..STEP040, as in the chain."""
    for mode in ("strict", "skip"):
        job = res["raw"][mode]["CREASTMT"]
        assert job["status"] == "COMPLETED"
        assert {k: v[0] for k, v in job["steps"].items()} == {
            "DELDEF01": "RC=0", "STEP010": "RC=16", "STEP020": "BYPASSED", "STEP030": "BYPASSED", "STEP040": "BYPASSED",
        }  # fmt: skip


def test_the_stopped_sort_writes_no_dataset(res):
    """The step ends before it sorts: no sorted TRXFL generation exists in either mode (the chain's STEP010 wrote none either)."""
    for mode in ("strict", "skip"):
        assert "AWS.M2.CARDDEMO.TRXFL.SEQ" not in res["raw"]["datasets"][mode]


def test_the_forged_job_stops_where_the_chain_stopped(res):
    """The chain's STEP010 ended RC=16 (register F4) and bypassed STEP020 / STEP040: the forged job does the same, no issue."""
    for mode in ("strict", "skip"):
        for case in ("carddemo-sort-creastmt", "creastmt-step020", "carddemo-cbstm03a"):
            assert _row(res, case)["modes"][mode]["issues"] == []


def test_eight_of_nine_steps_are_equal_in_each_mode(res):
    out = efs.render(res, "carddemo-nightly")
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 8 of 9 steps (strict)" in out
    assert "carddemo-nightly: executed Spring jobs equal to the chain over 8 of 9 steps (skip)" in out
    json.dumps(res)  # the result is plain data


def test_tranbkps_repro_reads_its_sysin_from_the_control_library_member_and_copies_the_ksds(res):
    """#8886 slice 9: STEP05R.PRC001's SYSIN is `&CNTLLIB(REPROCT)`, a dataset member, not an in-stream deck. The forge
    refused it by name; with the estate's own member (app/ctl/REPROCT.ctl, `REPRO INFILE(FILEIN) OUTFILE(FILEOUT)`)
    the step is a record copy: BKUP(+1) (G0002V00, after the seeded G0001V00) is the KSDS's 100 records byte for byte,
    then STEP05 / STEP10 delete and redefine the cluster through the IDCAMS model, all RC=0 (the chain's tranbkp-idcams)."""
    row = _row(res, "tranbkp-idcams")
    assert row["kind"] == "utility (forged)"
    for mode in ("strict", "skip"):
        assert row["modes"][mode]["status"] == "equal" and row["modes"][mode]["issues"] == []
        assert res["raw"][mode]["TRANBKP"]["steps"] == {
            "STEP05R.PRC001": ("RC=0", None), "STEP05": ("RC=0", None), "STEP10": ("RC=0", None),
        }  # fmt: skip
        ds = res["raw"]["datasets_by_job"][mode]["TRANBKP"]
        seed = (REPO / "tests/equivalence/carddemo-sort-creastmt/sortin.txt").read_bytes().split(b"\n")
        want = {"size": 100 * 350, "sha256": hashlib.sha256(b"".join(r for r in seed if r)).hexdigest()}
        assert ds["AWS.M2.CARDDEMO.TRANSACT.BKUP(G0002V00)"] == want


def test_the_jobs_final_datasets_are_set_against_what_the_chain_catalogued(res):
    """#8886 slice 17: the chain's report records each generation a step catalogued (size and SHA-256, `gdg_created`);
    the harness reads the same from the Spring run's datasets directory and compares. All three differ, and each says
    why: the Spring jobs run on seeded fixtures (BKUP 100 records, SYSTRAN/BKUP for COMBTRAN 50), not the bytes the
    chain's earlier steps wrote (BKUP 264 records, COMBINED 314), and INTCALC's program step is a stub that writes no
    SYSTRAN. None is rounded to equal; slice 18 seeds a run from the chain's own bytes where the chain exports them (below)."""
    rows = {d["dataset"]: d for d in res["datasets"]}
    assert set(rows) == {
        "AWS.M2.CARDDEMO.SYSTRAN", "AWS.M2.CARDDEMO.TRANSACT.BKUP", "AWS.M2.CARDDEMO.TRANSACT.COMBINED",
    }  # fmt: skip
    for mode in ("strict", "skip"):
        assert rows["AWS.M2.CARDDEMO.SYSTRAN"]["modes"][mode]["status"] == "differs"
        assert "wrote no new generation" in rows["AWS.M2.CARDDEMO.SYSTRAN"]["modes"][mode]["issue"]
        bkup = rows["AWS.M2.CARDDEMO.TRANSACT.BKUP"]["modes"][mode]
        assert (bkup["status"], bkup["got"]["size"], bkup["generation"]) == (
            "differs", 100 * 350, "AWS.M2.CARDDEMO.TRANSACT.BKUP(G0002V00)",
        )  # fmt: skip
        assert rows["AWS.M2.CARDDEMO.TRANSACT.BKUP"]["chain"]["size"] == 264 * 350
        comb = rows["AWS.M2.CARDDEMO.TRANSACT.COMBINED"]["modes"][mode]
        assert (comb["status"], comb["got"]["size"]) == ("differs", 50 * 350)
        assert rows["AWS.M2.CARDDEMO.TRANSACT.COMBINED"]["chain"]["size"] == 314 * 350
    text = "\n".join(efs.render(res, "n"))
    assert "n dataset AWS.M2.CARDDEMO.TRANSACT.BKUP [TRANBKP, step tranbkp-idcams] strict: differs" in text


def test_a_dataset_equal_to_the_chains_in_size_and_digest_is_equal_and_any_other_is_not():
    """The comparison itself, on a synthetic run: the newest unseeded generation of the base is read, and size and digest
    must both match."""
    spec = {"steps": [{"case": "s", "job": "J"}], "datasets": {"A.B": {"gdg": True, "seed": "x", "lrecl": 1}}}
    good = {"size": 4, "sha256": "ab" * 32}
    report = {"steps": [{"case": "s", "gdg_created": {"A.B": good}}]}

    def run(listing):
        return {"datasets_by_job": {m: {"J": listing} for m in ("strict", "skip")}}

    same = efs.compare_datasets(
        spec, report, run({"A.B(G0001V00)": {"size": 9, "sha256": "00"}, "A.B(G0002V00)": good})
    )
    assert [r["modes"][m]["status"] for r in same for m in ("strict", "skip")] == ["equal", "equal"]
    other = efs.compare_datasets(spec, report, run({"A.B(G0002V00)": {**good, "sha256": "cd" * 32}}))
    assert other[0]["modes"]["strict"]["status"] == "differs"
    seeded_only = efs.compare_datasets(spec, report, run({"A.B(G0001V00)": good}))
    assert "wrote no new generation" in seeded_only[0]["modes"]["strict"]["issue"]


def test_a_gdg_base_the_chain_catalogued_is_seeded_with_the_chains_generations_not_the_fixture(tmp_path):
    """#8886 slice 18: `seed_datasets(..., chain)` copies the chain's generations of a GDG base byte for byte, under their
    own numbers; a base the chain never held keeps the fixture seed; the seeded names follow."""
    chain = tmp_path / "chain"
    (chain / "A.B").mkdir(parents=True)
    (chain / "A.B" / "G0002V00").write_bytes(b"x" * 8)
    (chain / "A.B" / "G0003V00").write_bytes(b"y" * 8)
    fixture = tmp_path / "fx.txt"
    fixture.write_bytes(b"z" * 4 + b"\n")
    ds = {
        "A.B": {"gdg": True, "lrecl": 4, "seed": str(fixture)},
        "C.D": {"gdg": True, "lrecl": 4, "seed": str(fixture)},
    }
    root = tmp_path / "root"
    root.mkdir()
    efs.seed_datasets(ds, root, chain)
    assert sorted(p.name for p in (root / "A.B").iterdir()) == ["G0002V00", "G0003V00"]
    assert (root / "A.B" / "G0003V00").read_bytes() == b"y" * 8
    assert [p.name for p in (root / "C.D").iterdir()] == ["G0001V00"]
    assert efs.seeded_names(ds, chain) == {"A.B(G0002V00)", "A.B(G0003V00)", "C.D(G0001V00)"}
    assert efs.seeded_names(ds) == {"A.B(G0001V00)", "C.D(G0001V00)"}
    (chain / "A.B" / "G0004V00").write_bytes(b"w" * 5)
    with pytest.raises(ValueError, match="whole records"):
        efs.seed_datasets(ds, tmp_path / "again", chain)


def test_the_chain_exports_every_generation_it_holds_as_bytes(tmp_path):
    import equivalence_gdg as gdg
    import equivalence_job as ej

    cat = gdg.Catalog({"A.B": {"limit": 5, "reclen": 2}}, {"A.B": [b"aa", b"bbbb"]})
    cat.begin_step("J")
    cat.create("A.B", b"cc")
    assert ej._export_generations(cat, tmp_path / "g")
    assert sorted((p.name, p.read_bytes()) for p in (tmp_path / "g" / "A.B").iterdir()) == [
        ("G0001V00", b"aa"), ("G0002V00", b"bbbb"), ("G0003V00", b"cc"),
    ]  # fmt: skip
    assert not ej._export_generations(gdg.Catalog({}), tmp_path / "none")


def test_combtran_reads_the_chains_newest_generation_when_the_chain_exports_one(tmp_path):
    """#8886 slice 18, end to end: with a chain directory holding BKUP generations (the newest 10 records) and SYSTRAN's
    (22), COMBTRAN's SORT reads those, not the fixtures: COMBINED(+1) is 32 records, and the seeded generations are not
    reported as written by the job."""
    seeds = REPO / "tests/equivalence/carddemo-sort-combtran"
    b1 = [r for r in (seeds / "sortin1.txt").read_bytes().split(b"\n") if r]
    b2 = [r for r in (seeds / "sortin2.txt").read_bytes().split(b"\n") if r]
    chain = tmp_path / "chain"
    for base, gens in (("AWS.M2.CARDDEMO.TRANSACT.BKUP", [b1, b1[:10]]), ("AWS.M2.CARDDEMO.SYSTRAN", [b2])):
        (chain / base).mkdir(parents=True)
        for n, recs in enumerate(gens, 1):
            (chain / base / f"G{n:04d}V00").write_bytes(b"".join(recs))
    out = efs.scan_and_run(SPEC, CASE, REPORT, CORPUS, efj.chain_rcs, chain)
    assert out is not None
    for mode in ("strict", "skip"):
        ds = out["raw"]["datasets_by_job"][mode]["COMBTRAN"]
        assert ds["AWS.M2.CARDDEMO.TRANSACT.COMBINED(G0001V00)"]["size"] == 32 * 350
        assert ds["AWS.M2.CARDDEMO.TRANSACT.BKUP(G0002V00)"]["size"] == 10 * 350
        assert "AWS.M2.CARDDEMO.TRANSACT.BKUP(G0001V00)" in ds
    bkup = next(d for d in out["datasets"] if d["dataset"] == "AWS.M2.CARDDEMO.TRANSACT.BKUP")
    assert bkup["modes"]["strict"]["generation"] == "AWS.M2.CARDDEMO.TRANSACT.BKUP(G0003V00)"  # TRANBKP's, not a seed


def test_the_chain_exports_each_steps_output_bytes_and_a_dataset_is_seeded_from_the_one_that_fed_it(tmp_path):
    """#8886 slice 21: a dataset the chain fed from a step's output (TRANBKP's KSDS holds POSTTRAN's TRANFILE) is seeded with
    those bytes (spec `chain_feed`), not the fixture; without the export it keeps the fixture."""
    import equivalence_job as ej

    assert ej._export_outputs({"s": {"DD": b"abcd", "ABEND": "x"}}, tmp_path / "o")
    assert (tmp_path / "o" / "s" / "DD").read_bytes() == b"abcd" and not (tmp_path / "o" / "s" / "ABEND").exists()
    assert not ej._export_outputs({}, tmp_path / "none")
    fixture = tmp_path / "fx.txt"
    fixture.write_bytes(b"zzzz\n")
    ds = {"K": {"lrecl": 4, "seed": str(fixture), "chain_feed": {"case": "s", "dd": "DD"}}}
    root = tmp_path / "root"
    root.mkdir()
    efs.seed_datasets(ds, root, None, tmp_path / "o")
    assert (root / "K").read_bytes() == b"abcd"
    again = tmp_path / "again"
    again.mkdir()
    efs.seed_datasets(ds, again, None, tmp_path / "missing")
    assert (again / "K").read_bytes() == b"zzzz"
    (tmp_path / "o" / "s" / "DD").write_bytes(b"abcde")
    with pytest.raises(ValueError, match="whole records"):
        efs.seed_datasets(ds, tmp_path / "bad", None, tmp_path / "o")


def test_tranbkp_copies_the_ksds_the_chain_fed_it(tmp_path):
    """#8886 slice 21, end to end: with POSTTRAN's TRANFILE output exported (here 12 of the fixture's records) TRANBKP's
    REPRO writes BKUP(+1) of those 12 records, as the chain's does of its 264 (the pinned nightly's digest equals the chain's
    when the chain is run: `equivalence.py run carddemo-nightly`, then the Spring harness over its report)."""
    recs = [r for r in (REPO / "tests/equivalence/carddemo-sort-creastmt/sortin.txt").read_bytes().split(b"\n") if r]
    out_dir = tmp_path / "outputs" / "carddemo-posttran"
    out_dir.mkdir(parents=True)
    (out_dir / "TRANFILE").write_bytes(b"".join(recs[:12]))
    out = efs.scan_and_run(SPEC, CASE, REPORT, CORPUS, efj.chain_rcs, None, tmp_path / "outputs")
    assert out is not None
    for mode in ("strict", "skip"):
        ds = out["raw"]["datasets_by_job"][mode]["TRANBKP"]
        assert ds["AWS.M2.CARDDEMO.TRANSACT.BKUP(G0002V00)"]["size"] == 12 * 350
