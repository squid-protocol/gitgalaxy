"""#4890: an IKJEFT01 step runs `RUN PROGRAM(x)` with the PARMS the command carries (`det/tso.py`), not the EXEC PARM
(the TSO command line); any other subcommand, RUN keyword or a second RUN is refused by name through `steps.utility`."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.det import dfsort, tso
from gitgalaxy.tools.cobol_to_java.java_target import load_target

FILE = "jcl/TSO.jcl"
RUN = "RUN PROGRAM(POSTIT) PLAN(PLN1) LIB('PROD.LOAD')"


def _forge(deck: str, parm: str | None = None) -> BatchForge:
    runs = [{"program": "POSTIT", "via": "RUN PROGRAM", "plan": "PLN1"}]
    steps = [{"step": "DB2", "ordinal": 1, "line": 2, "program": "IKJEFT01", "parm": parm, "runner_programs": runs}]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "TSOJOB", "steps": steps}]},
        "job_sysin": {"facts": [{"file": FILE, "ordinal": 1, "proc_step": None, "dd": "SYSTSIN", "body": deck}]},
    }
    skeletons = {"POSTIT": {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _tasklet(forge: BatchForge) -> str:
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    (line,) = (ln for ln in cfg.splitlines() if 'steps.program("DB2"' in ln or 'steps.utility("DB2"' in ln)
    return line.strip()


def test_parms_reach_the_program_not_the_exec_parm():
    deck = f" DSN SYSTEM(DB2P)\n {RUN} -\n   PARMS('/ALIGN(MID)')\n END\n"
    line = _tasklet(_forge(deck, parm="ignored"))
    assert 'runBatch(DDS_DB2, "/ALIGN(MID)")' in line and "ignored" not in line


def test_a_run_without_parms_gets_no_parm():
    line = _tasklet(_forge(f" DSN SYSTEM(DB2P)\n {RUN}\n END\n", parm="ignored"))
    assert "runBatch(DDS_DB2, null)" in line


def test_the_parser_reads_every_operand():
    run = tso.parse(f"DSN SYSTEM(db2p)\n{RUN} PARMS('A''B')\nEND\n")
    assert (run.program, run.ssid, run.plan, run.lib, run.parms) == ("POSTIT", "DB2P", "PLN1", "PROD.LOAD", "A'B")


@pytest.mark.parametrize(
    ("deck", "named"),
    [
        (f"DSN SYSTEM(D)\n{RUN}\nDSN SYSTEM(E)\n", "a second DSN command"),
        (f"DSN SYSTEM(D)\n{RUN}\n{RUN}\n", "more than one RUN PROGRAM"),
        ("DSN SYSTEM(D)\nBIND PLAN(P)\n", "the BIND command"),
        ("DSN SYSTEM(D)\nFREE PLAN(P)\n", "the FREE command"),
        (f"DSN SYSTEM(D)\n{RUN} CP\n", "the RUN CP keyword"),
        ("RUN PROGRAM(POSTIT)\n", "a RUN without a DSN command before it"),
        ("DSN SYSTEM(D)\nRUN PROGRAM(POSTIT) PARMS(ABC)\n", "a RUN PARMS that is not one quoted string"),
        ("DSN SYSTEM(D)\nEND\n", "no RUN PROGRAM"),
    ],
)
def test_other_commands_are_refused_by_name(deck, named):
    with pytest.raises(dfsort.Refused, match=named):
        tso.parse(deck)
    line = _tasklet(_forge(deck))
    assert "steps.utility" in line and "IKJEFT01 model refuses" in line
    assert "1 utility steps to port" in _forge(deck).audit_line()
