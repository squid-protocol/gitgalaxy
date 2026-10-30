"""#4268: an IEBGENER / ICEGENER step of a generated JCL job runs as a copy only while its SYSIN is DUMMY or empty
(`dfsort.iebgener`, proven against GnuCOBOL in test_dfsort_4268.py); a control statement or a SYSIN dataset is refused by
name through `steps.utility`, never copied as if it were a plain copy."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/GEN.jcl"


def _forge(program: str, decks: list[dict], dds: list[dict]) -> BatchForge:
    steps = [
        {"step": "RUN", "ordinal": 1, "line": 2, "program": "POSTIT"},
        {"step": "GEN", "ordinal": 2, "line": 4, "program": program},
    ]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "GENJOB", "steps": steps}]},
        "job_dds": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, **d} for d in dds]},
        "job_sysin": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, "dd": "SYSIN", **d} for d in decks]},
    }
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _gen_tasklet(forge: BatchForge) -> str:
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if 'steps.copy("GEN"' in ln or 'steps.utility("GEN"' in ln)
    return line.strip()


@pytest.mark.parametrize("program", ["IEBGENER", "ICEGENER"])
@pytest.mark.parametrize("decks", [[], [{"body": ""}], [{"body": "* a comment line\n"}]])
def test_a_step_with_no_control_statement_is_a_copy(program, decks):
    assert _gen_tasklet(_forge(program, decks, [])).startswith('.tasklet(steps.copy("GEN"')


@pytest.mark.parametrize(
    "card", ["GENERATE MAXFLDS=1", "RECORD FIELD=(80,1,,1)", "MEMBER NAME=X", "EXITS INHDR=A", "LABELS DATA=NO"]
)
def test_a_control_statement_is_refused_by_name(card):
    line = _gen_tasklet(_forge("IEBGENER", [{"body": f" {card}\n"}], []))
    assert 'steps.utility("GEN"' in line and f"the IEBGENER {card.split()[0]} statement" in line


def test_a_sysin_dataset_is_refused_not_copied():
    line = _gen_tasklet(_forge("IEBGENER", [], [{"dd": "SYSIN", "dsn": "APP.CTL(GEN)"}]))
    assert 'steps.utility("GEN"' in line and "its SYSIN is a dataset of control statements" in line


def test_a_refused_step_counts_as_a_utility_step_to_port():
    f = _forge("IEBGENER", [{"body": " GENERATE MAXFLDS=1\n"}], [])
    assert "1 utility steps to port" in f.audit_line()
    assert "0 utility steps to port" in _forge("IEBGENER", [], []).audit_line()
