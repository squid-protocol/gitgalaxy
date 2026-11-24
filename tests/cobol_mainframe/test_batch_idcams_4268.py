"""#4268: an IDCAMS step of a generated JCL job runs as a record copy only while its SYSIN is one
`REPRO INFILE(dd) OUTFILE(dd)` over two datasets of the step (`det/idcams.py`, proven against GnuCOBOL in
test_dfsort_4268.py); any other deck the IDCAMS model (`det/idcams_model.py`, #8886) can run becomes `steps.idcams`, and what the model
refuses is refused by name through `steps.utility`."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/IDC.jcl"
DDS = [{"dd": "IN1", "dsn": "APP.IN"}, {"dd": "OUT1", "dsn": "APP.OUT"}]


def _forge(decks: list[str], dds: list[dict] = DDS, members: dict | None = None) -> BatchForge:
    steps = [
        {"step": "RUN", "ordinal": 1, "line": 2, "program": "POSTIT"},
        {"step": "IDC", "ordinal": 2, "line": 4, "program": "IDCAMS"},
    ]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "IDCJOB", "steps": steps}]},
        "job_dds": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, **d} for d in dds]},
        "job_sysin": {
            "facts": [{"file": FILE, "ordinal": 2, "proc_step": None, "dd": "SYSIN", "body": b} for b in decks]
        },
    }
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(
        skeletons, {"sections": sections, "control_members": members or {}}, "com.gitgalaxy", load_target(None)
    )


def _tasklet(forge: BatchForge) -> str:
    cfg = next(t for k, t in forge.sources()[("base_pkg", "batch")].items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if any(f'steps.{m}("IDC"' in ln for m in ("copy", "utility", "idcams")))
    return line.strip()


@pytest.mark.parametrize(
    "deck",
    [
        " REPRO INFILE(IN1) OUTFILE(OUT1)\n",
        " REPRO IFILE(IN1) OFILE(OUT1)\n",
        " repro outfile(out1) infile(in1)\n",
        " REPRO INFILE(IN1) -\n       OUTFILE(OUT1)\n",
        " /* copy */ REPRO INFILE(IN1) OUTFILE(OUT1)\n",
    ],
)
def test_a_repro_is_a_copy_over_its_two_dds(deck):
    line = _tasklet(_forge([deck]))
    assert '.tasklet(steps.copy("IDC"' in line and 'DDS_IDC, "IN1", "OUT1"), tx)' in line
    assert "0 utility steps to port" in _forge([deck]).audit_line()


@pytest.mark.parametrize(
    ("deck", "named"),
    [
        (" LISTCAT ENTRIES(APP.IN)\n", "the IDCAMS LISTCAT command"),
        (" PRINT INFILE(IN1)\n", "the IDCAMS PRINT command"),
        (" REPRO INFILE(IN1) OUTFILE(NOPE)\n", "names the DD NOPE"),
    ],
)
def test_what_the_model_refuses_is_refused_by_name(deck, named):
    line = _tasklet(_forge([deck]))
    assert 'steps.utility("IDC"' in line and named in line
    assert "1 utility steps to port" in _forge([deck]).audit_line()


@pytest.mark.parametrize(
    "deck",
    [
        " DELETE APP.OUT\n",
        " DEFINE CLUSTER(NAME(APP.K))\n",
        " REPRO INFILE(IN1) OUTFILE(OUT1)\n DELETE APP.IN\n",
    ],
)
def test_a_deck_the_model_runs_is_lowered_with_its_text(deck):
    forge = _forge([deck])
    line = _tasklet(forge)
    assert 'steps.idcams("IDC"' in line and 'DDS_IDC, "' in line and "\n" not in line
    assert "0 utility steps to port" in forge.audit_line()
    sources = forge.sources()
    assert "Idcams" in sources[("base_pkg", "cobolrt/job")]
    (steps,) = (t for k, t in sources[("base_pkg", "batch")].items() if k.endswith("JclSteps"))
    assert "public Tasklet idcams(" in steps and "cobolrt.job.Idcams" in steps and "//{" not in steps


def test_an_estate_with_no_lowered_idcams_step_carries_no_model():
    forge = _forge([" REPRO INFILE(IN1) OUTFILE(OUT1)\n"])
    sources = forge.sources()
    assert ("base_pkg", "cobolrt/job") not in sources
    (steps,) = (t for k, t in sources[("base_pkg", "batch")].items() if k.endswith("JclSteps"))
    assert "Idcams" not in steps and "//{" not in steps


def test_a_sysin_dataset_is_refused_not_copied():
    line = _tasklet(_forge([], [*DDS, {"dd": "SYSIN", "dsn": "APP.CTL(IDC)"}]))
    assert 'steps.utility("IDC"' in line and "its SYSIN is a dataset of control statements" in line


SYSIN_DS = [*DDS, {"dd": "SYSIN", "dsn": "&CNTLLIB(REPROCT)"}]


def test_a_sysin_member_the_estate_supplied_is_read_as_the_deck():
    """#8886 slice 9: `&CNTLLIB(REPROCT)` with the member's text (IDCAMS comments dropped) is one REPRO: a copy."""
    ctl = "/* Copyright */\n    REPRO INFILE(IN1) OUTFILE(OUT1)\n"
    line = _tasklet(_forge([], SYSIN_DS, {"reproct": ctl}))
    assert '.tasklet(steps.copy("IDC"' in line and 'DDS_IDC, "IN1", "OUT1"), tx)' in line


def test_a_sysin_member_the_estate_did_not_supply_stays_refused():
    other = _forge([], SYSIN_DS, {"OTHER": " REPRO INFILE(IN1) OUTFILE(OUT1)\n"})
    assert "its SYSIN is a dataset of control statements" in _tasklet(other)


def test_a_supplied_member_that_the_model_refuses_is_refused_by_name():
    assert "refuses" in _tasklet(_forge([], SYSIN_DS, {"REPROCT": " LISTCAT ALL\n"}))


def test_no_in_stream_sysin_is_refused():
    assert "no single in-stream SYSIN" in _tasklet(_forge([]))


def test_the_java_copy_is_one_method_for_both_utilities():
    src = _forge([" REPRO INFILE(IN1) OUTFILE(OUT1)\n"]).sources()[("base_pkg", "batch")]
    (steps,) = (t for k, t in src.items() if k.endswith("JclSteps"))
    assert steps.count("public Tasklet copy(") == 2 and "inDd, outDd" in steps
    assert '"SYSUT1", "SYSUT2"' in steps
