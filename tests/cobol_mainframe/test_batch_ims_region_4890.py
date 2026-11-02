"""#4890: a DFSRRC00 step's PARM is the IMS region (`det/ims_region.py`), not the program's parameter: the program runs
with no PARM; another region type, an IMS region option or a symbolic value is refused by name through `steps.utility`."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.det import dfsort, ims_region
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/IMS.jcl"


def _forge(parm: str | None) -> BatchForge:
    runs = [{"program": "POSTIT", "via": "DFSRRC00", "region": "BMP", "psb": "POSTPSB"}]
    steps = [{"step": "BMP", "ordinal": 1, "line": 2, "program": "DFSRRC00", "parm": parm, "runner_programs": runs}]
    sections = {"job_steps": {"facts": [{"file": FILE, "job": "IMSJOB", "steps": steps}]}}
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _tasklet(forge: BatchForge) -> str:
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if 'steps.program("BMP"' in ln or 'steps.utility("BMP"' in ln)
    return line.strip()


@pytest.mark.parametrize("parm", ["BMP,POSTIT,POSTPSB", "dli,postit,", "DBB,POSTIT", "BMP,POSTIT,,,"])
def test_the_program_runs_with_no_parm(parm):
    line = _tasklet(_forge(parm))
    assert "steps.program" in line and "runBatch(DDS_BMP, null)" in line and "POSTPSB" not in line


def test_the_parser_reads_region_program_and_psb():
    assert ims_region.parse("bmp,postit,postpsb") == ims_region.Region("BMP", "POSTIT", "POSTPSB")
    assert ims_region.parse("DLI,POSTIT").psb is None


@pytest.mark.parametrize(
    ("parm", "named"),
    [
        (None, "no DFSRRC00 PARM"),
        ("MSG,POSTIT,POSTPSB", "region type 'MSG'"),
        ("BMP,POSTIT,POSTPSB,1,2", "PARM position 4"),
        ("BMP,POSTIT,POSTPSB,,IMSA", "PARM position 5"),
        ("BMP,&PGM,POSTPSB", "symbolic DFSRRC00 PARM value"),
        ("BMP,,POSTPSB", "program \\(empty\\)"),
        ("BMP,POSTIT,TOOLONGPSB", "PSB \\(TOOLONGPSB\\)"),
    ],
)
def test_other_forms_are_refused_by_name(parm, named):
    with pytest.raises(dfsort.Refused, match=named):
        ims_region.parse(parm)
    line = _tasklet(_forge(parm))
    assert "steps.utility" in line and "DFSRRC00 model refuses" in line
    assert "1 utility steps to port" in _forge(parm).audit_line()


def test_a_program_the_parm_does_not_name_is_refused():
    line = _tasklet(_forge("BMP,OTHERPG,POSTPSB"))
    assert "steps.utility" in line and "runs OTHERPG in its PARM, not POSTIT" in line
