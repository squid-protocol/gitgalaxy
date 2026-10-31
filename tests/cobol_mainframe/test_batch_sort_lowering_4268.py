"""#4268: a DFSORT step (PGM=SORT / ICEMAN / DFSORT) whose job states the record length (`DCB=(LRECL=..,RECFM=FB)`,
the `lrecl` / `recfm` of a job_dds row) is lowered to the COBOL SORT / MERGE program `dfsort.cobol_program` writes
(proven against GnuCOBOL in test_dfsort_4268.py) and kept as a resource; the forge runs its det translation
(test_batch_sort_run_4268.py). What the job does not state, or states unusably, is refused by name: a named utility step."""

import json

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.det import dfsort
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/SRT.jcl"
FB80 = {"lrecl": 80, "recfm": "FB"}


def _forge(dds: list[dict], sysin: str = " SORT FIELDS=(1,4,CH,A)\n", program: str = "SORT", symnames: str = "",
           other: list[dict] | None = None) -> BatchForge:  # fmt: skip
    steps = [
        {"step": "PRE", "ordinal": 1, "line": 2, "program": "POSTIT"},
        {"step": "SRT", "ordinal": 2, "line": 4, "program": program},
    ]
    decks = [("SYSIN", sysin)] + ([("SYMNAMES", symnames)] if symnames else [])
    facts = [{"file": FILE, "ordinal": 2, "proc_step": None, **d} for d in dds]
    facts += [{"file": FILE, "ordinal": 1, "proc_step": None, **d} for d in other or []]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "SRTJOB", "steps": steps}]},
        "job_dds": {"facts": facts},
        "job_sysin": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, "dd": k, "body": b} for k, b in decks]},
    }
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _sort_in(**dcb) -> list[dict]:
    return [{"dd": "SORTIN", "dsn": "APP.IN", **dcb}, {"dd": "SORTOUT", "dsn": "APP.OUT"}]


def _step(forge: BatchForge):
    (job,) = forge.applications
    return job.steps[1]


def _line(forge: BatchForge) -> str:
    src = forge.sources()[("base_pkg", "batch")]
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if "steps." in ln and '("SRT"' in ln)
    return line.strip()


@pytest.mark.parametrize("program", ["SORT", "ICEMAN", "DFSORT"])
@pytest.mark.parametrize(
    ("sysin", "verb"),
    [(" SORT FIELDS=(1,4,CH,A)\n", "SORT"), (" SORT FIELDS=COPY\n", "COPY")],
)
def test_a_step_with_a_stated_lrecl_is_lowered(program, sysin, verb):
    f = _forge(_sort_in(**FB80), sysin, program)
    st = _step(f)
    assert st.refused is None and st.lowered == dfsort.cobol_program(dfsort.parse(sysin), 80, ["SORTIN"], "SORTOUT")
    assert "80-byte fixed records" in st.lowered_note
    assert st.sort_service and "steps.program(" in _line(f) and "steps.utility" not in _line(f)


def test_the_lowered_program_is_a_resource_and_no_longer_a_utility_step_to_port():
    f = _forge(_sort_in(**FB80))
    (path,) = (k for k in f.resources() if k.startswith("batch/sort/"))
    assert f.resources()[path] == _step(f).lowered and path.endswith("-SRT.cbl")
    assert "0 utility steps to port" in f.audit_line()
    assert json.loads(f.resources()["batch/jcl-jobs.json"])  # the job index is still written


def test_a_merge_takes_its_sortinnn_dds():
    dds = [{"dd": "SORTIN01", "dsn": "A", **FB80}, {"dd": "SORTIN02", "dsn": "B"}, {"dd": "SORTOUT", "dsn": "C"}]
    st = _step(_forge(dds, " MERGE FIELDS=(1,4,CH,A),EQUALS\n"))
    assert st.refused is None and "SORTIN01-FILE" not in st.lowered and "ASSIGN TO SORTIN02" in st.lowered


def test_a_merge_without_its_inputs_is_refused():
    line = _line(_forge(_sort_in(**FB80), " MERGE FIELDS=(1,4,CH,A),EQUALS\n"))
    assert "SORTINnn is not a dataset" in line


def test_a_concatenation_with_one_stated_length_is_lowered():
    dds = [{"dd": "SORTIN", "dsn": "A", **FB80}, {"dd": "SORTIN", "dsn": "B"}, {"dd": "SORTOUT", "dsn": "C"}]
    assert _step(_forge(dds)).lowered


def test_concatenated_lengths_must_agree():
    dds = [{"dd": "SORTIN", "dsn": "A", **FB80}, {"dd": "SORTIN", "dsn": "B", "lrecl": 100, "recfm": "FB"}]
    assert "states different LRECLs (80, 100)" in _line(_forge([*dds, {"dd": "SORTOUT", "dsn": "C"}]))


@pytest.mark.parametrize("recfm", ["F", "FB", "FBA", "FBM", "FBS", "fb"])
def test_every_fixed_recfm_is_lowered(recfm):
    assert _step(_forge(_sort_in(lrecl=80, recfm=recfm))).lowered


@pytest.mark.parametrize("recfm", ["VB", "V", "U", "VBA"])
def test_a_variable_or_undefined_recfm_is_refused(recfm):
    line = _line(_forge(_sort_in(lrecl=80, recfm=recfm)))
    assert f"RECFM={recfm}, not fixed-length records" in line


def test_a_length_without_a_recfm_is_not_guessed():
    assert "LRECL=80 but no RECFM" in _line(_forge(_sort_in(lrecl=80)))


@pytest.mark.parametrize("dds", [_sort_in(), _sort_in(recfm="FB")])
def test_no_stated_length_is_refused(dds):
    assert "the job facts carry no record length (LRECL)" in _line(_forge(dds))


def test_the_length_comes_from_the_step_that_wrote_the_dataset():
    other = [{"dd": "SORTOUT", "dsn": "APP.IN", **FB80}]
    st = _step(_forge(_sort_in(), other=other))
    assert st.lowered and "the same dataset elsewhere in the job" in st.lowered_note


def test_a_length_without_a_recfm_is_not_overruled_by_a_later_tier():
    other = [{"dd": "SORTOUT", "dsn": "APP.IN", "lrecl": 100, "recfm": "FB"}]
    line = _line(_forge(_sort_in(lrecl=80), other=other))
    assert "states LRECL=100, but the input DD states LRECL=80 but no RECFM" in line


def test_a_later_tier_supplies_the_recfm_of_the_same_length():
    st = _step(_forge(_sort_in(lrecl=80), other=[{"dd": "SORTOUT", "dsn": "APP.IN", **FB80}]))
    assert st.lowered and "the same dataset elsewhere in the job" in st.lowered_note


def test_the_length_comes_from_sortout_without_outrec_but_not_with_it():
    out = [{"dd": "SORTIN", "dsn": "APP.IN"}, {"dd": "SORTOUT", "dsn": "APP.OUT", **FB80}]
    assert _step(_forge(out)).lowered
    line = _line(_forge(out, " SORT FIELDS=(1,4,CH,A)\n OUTREC FIELDS=(1,4)\n"))
    assert "no record length (LRECL)" in line


@pytest.mark.parametrize("missing", ["SORTIN", "SORTOUT"])
def test_a_dd_that_is_not_a_dataset_is_refused(missing):
    dds = [d for d in _sort_in(**FB80) if d["dd"] != missing]
    assert f"{missing} is not a dataset" in _line(_forge(dds))


def test_a_field_outside_the_record_is_refused_by_lowering():
    line = _line(_forge(_sort_in(lrecl=2, recfm="FB")))
    assert "lowering refuses" in line and "outside the 2-byte record" in line


def test_the_modelled_refusals_still_come_first():
    assert "the OUTFIL statement" in _line(_forge(_sort_in(**FB80), " SORT FIELDS=(1,4,CH,A)\n OUTFIL FNAMES=O\n"))
