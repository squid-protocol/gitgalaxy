"""#4268: a DFSORT step (PGM=SORT / ICEMAN / DFSORT) of a generated JCL job goes through `dfsort.parse` (SYSIN with its
SYMNAMES): what the model refuses is named as the model names it, and a step it covers but whose job states no record
length says so (test_batch_sort_lowering_4268.py covers the lowering once it does). Every such step is a
`steps.utility` that fails the job: never a silent success."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/SRT.jcl"
DATASETS = [{"dd": "SORTIN", "dsn": "APP.IN"}, {"dd": "SORTOUT", "dsn": "APP.OUT"}]  # no DCB stated


def _forge(program: str, decks: dict[str, str], dds: list[dict] | None = None) -> BatchForge:
    steps = [
        {"step": "RUN", "ordinal": 1, "line": 2, "program": "POSTIT"},
        {"step": "SRT", "ordinal": 2, "line": 4, "program": program},
    ]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "SRTJOB", "steps": steps}]},
        "job_dds": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, **d} for d in DATASETS + (dds or [])]},
        "job_sysin": {
            "facts": [{"file": FILE, "ordinal": 2, "proc_step": None, "dd": dd, "body": b} for dd, b in decks.items()]
        },
    }
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _line(forge: BatchForge) -> str:
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if 'steps.utility("SRT"' in ln)
    return line.strip()


@pytest.mark.parametrize("program", ["SORT", "ICEMAN", "DFSORT"])
@pytest.mark.parametrize(
    ("sysin", "verb"),
    [
        (" SORT FIELDS=(1,4,CH,A)\n", "SORT"),
        (" SORT FIELDS=COPY\n", "COPY"),
        (" MERGE FIELDS=(1,4,CH,A),EQUALS\n", "MERGE"),
    ],
)
def test_a_modelled_step_says_why_it_is_not_run(program, sysin, verb):
    merge_ins = [{"dd": "SORTIN01", "dsn": "APP.IN1"}, {"dd": "SORTIN02", "dsn": "APP.IN2"}]
    line = _line(_forge(program, {"SYSIN": sysin}, merge_ins if verb == "MERGE" else None))
    assert f"a DFSORT {verb} the model lowers" in line and "no record length (LRECL)" in line


def test_symnames_are_read_with_the_sysin():
    line = _line(_forge("SORT", {"SYSIN": " SORT FIELDS=(KEY,A)\n", "SYMNAMES": "KEY,1,4,CH\n"}))
    assert "a DFSORT SORT the model lowers" in line


@pytest.mark.parametrize(
    ("sysin", "named"),
    [
        (" SORT FIELDS=(1,4,CH,A)\n OUTFIL FNAMES=OUT1\n", "the OUTFIL statement"),
        (" SORT FIELDS=(1,4,FI,A)\n", "FI"),
        (" SORT FIELDS=(1,4,CH,A)\n SUM FIELDS=NONE\n", "the SUM statement"),
        ("", "no SORT or MERGE statement"),
    ],
)
def test_what_the_model_refuses_is_named(sysin, named):
    line = _line(_forge("SORT", {"SYSIN": sysin}))
    assert "which the DFSORT model refuses" in line and named in line


@pytest.mark.parametrize("dd", ["SORTCNTL", "DFSPARM"])
def test_a_merged_control_deck_is_refused(dd):
    line = _line(_forge("SORT", {"SYSIN": " SORT FIELDS=(1,4,CH,A)\n", dd: " OPTION EQUALS\n"}))
    assert f"has a {dd}" in line


def test_a_control_dataset_is_refused():
    line = _line(_forge("SORT", {}, [{"dd": "SYSIN", "dsn": "APP.CTL(SRT)"}]))
    assert "has its control statements in a dataset" in line


@pytest.mark.parametrize("program", ["SYNCSORT", "ICETOOL"])
def test_another_sort_product_is_refused(program):
    assert f"is {program}, not DFSORT control statements" in _line(_forge(program, {"SYSIN": " SORT FIELDS=COPY\n"}))


def test_a_sort_step_counts_as_a_utility_step_to_port():
    assert "1 utility steps to port" in _forge("SORT", {"SYSIN": " SORT FIELDS=COPY\n"}).audit_line()
