"""#8413: IBM-written answers for JOB RESTART= when RD= is coded on a library procedure's steps or its calling EXEC.

`tests/equivalence/jcl/restart/rd.json` holds the JCL (four restarted jobs, two refused shapes), the JCLLIB member
and the answers: per step, skipped (before the restart step), run or bypass. RD governs the automatic restart of a
RUNNING job after an abend; JOB RESTART= is a deferred restart of a resubmission, so RD never moves the steps. The
answers were written from IBM's z/OS MVS JCL Reference (SA23-1385: EXEC RD, JOB RESTART) before the resolver was
checked on them; the tests reproduce every `expect` and every refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_proc import JclProcRefused
from gitgalaxy.core.jcl_restart import JclRestartRefused, restart_flow

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "restart" / "rd.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["library_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
LIBS = {lib: {m: "\n".join(ls) + "\n" for m, ls in ms.items()} for lib, ms in DOC["libraries"].items()}


def test_every_jcl_line_fits_columns_1_to_72():
    members = [ln for ms in DOC["libraries"].values() for ls in ms.values() for ln in ls]
    for n, ln in enumerate(DOC["library_jcl"] + members, 1):
        assert len(ln) <= 72, (n, ln)


def test_rd_is_coded_on_a_procedure_step_the_calling_exec_and_the_job_statement():
    members = " ".join(ln for ms in DOC["libraries"].values() for ls in ms.values() for ln in ls)
    assert "RD=R" in members and "RD=NR" in members and "RD=RNC" in members
    calls = [ln for ln in DOC["library_jcl"] if "EXEC RDQ,RD=" in ln or "EXEC RDP,RD=" in ln]
    assert len(calls) >= 3
    assert any(" JOB " in ln and "RD=" in ln for ln in DOC["library_jcl"])
    ids = [s["id"] for s in DOC["scenarios"]]
    assert len(ids) == len(set(ids))
    assert {s["assumed"] for s in DOC["scenarios"] if "assumed" in s} <= {a["id"] for a in DOC["assumed"]}
    assert all(s["basis"] for s in DOC["scenarios"])


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_rd_restart_answer(sc):
    got = restart_flow(ROWS, sc["job"], sc["given"], TEXT, LIBS)
    assert got == sc["expect"], sc["id"]
    assert list(got) == list(sc["expect"]), sc["id"]


@pytest.mark.parametrize("r", DOC["refused"], ids=lambda r: r["id"])
def test_an_rd_value_that_is_not_an_rd_value_is_refused_by_name(r):
    with pytest.raises((JclRestartRefused, JclProcRefused), match=r["match"]):
        restart_flow(ROWS, r["job"], {}, TEXT, LIBS)
