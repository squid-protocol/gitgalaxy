"""#8413: IBM-written answers for JOB RESTART= into a library procedure that calls another library procedure.

`tests/equivalence/jcl/restart/nested.json` holds the JCL (six restarted jobs, three refused shapes), the two JCLLIB
library members and the answers: per step, skipped (before the restart step), run or bypass. The answers were written
from IBM's z/OS MVS JCL Reference (SA23-1385: JOB RESTART, EXEC COND, JCLLIB ORDER, nesting procedures) BEFORE
`gitgalaxy.core.jcl_proc.expand_flow_rows` handled a nested call; how a nested procedure's step is named is ASSUMED
(A2, in the file). The tests reproduce every `expect` and every refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_proc import JclProcRefused
from gitgalaxy.core.jcl_restart import JclRestartRefused, restart_flow

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "restart" / "nested.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["library_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
LIBS = {lib: {m: "\n".join(ls) + "\n" for m, ls in ms.items()} for lib, ms in DOC["libraries"].items()}


def test_every_jcl_line_fits_columns_1_to_72():
    members = [ln for ms in DOC["libraries"].values() for ls in ms.values() for ln in ls]
    for n, ln in enumerate(DOC["library_jcl"] + members, 1):
        assert len(ln) <= 72, (n, ln)


def test_the_scenarios_cover_a_restart_before_inside_and_after_the_inner_call():
    ids = " ".join(s["id"] for s in DOC["scenarios"])
    for word in (
        "first-inner-step",
        "cond-names-restart-step",
        "after-the-inner-call",
        "before-the-inner-call",
        "star",
        "checkpoint",
    ):
        assert word in ids, word
    assert len(ids.split()) == len(set(ids.split()))
    assumed = {a["id"] for a in DOC["assumed"]}
    assert {s["assumed"] for s in DOC["scenarios"] if "assumed" in s} <= assumed
    assert all(s["basis"] for s in DOC["scenarios"])


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_nested_restart_answer(sc):
    got = restart_flow(ROWS, sc["job"], sc["given"], TEXT, LIBS)
    assert got == sc["expect"], sc["id"]
    assert list(got) == list(sc["expect"]), sc["id"]


@pytest.mark.parametrize("r", DOC["refused"], ids=lambda r: r["id"])
def test_a_nested_restart_that_is_not_answered_is_refused_by_name(r):
    with pytest.raises((JclRestartRefused, JclProcRefused), match=r["match"]):
        restart_flow(ROWS, r["job"], {}, TEXT, LIBS)


def test_a_nested_call_in_an_in_stream_procedure_keeps_the_outer_call_name():
    text = (
        "//J JOB RESTART=C.N2\n//OUT PROC\n//O1 EXEC PGM=A\n//I1 EXEC INN\n//OUT PEND\n"
        "//INN PROC\n//N1 EXEC PGM=B\n//N2 EXEC PGM=C\n//INN PEND\n//C EXEC OUT\n"
    )
    got = restart_flow(job_flow.jcl_job_flow(text), "J", {"C.N2": {"rc": 0}})
    assert got == {"C.O1": "skipped", "C.N1": "skipped", "C.N2": "run"}


def test_a_cond_on_the_call_of_a_procedure_that_calls_procedures_is_refused():
    text = TEXT.replace(
        "//CALL1    EXEC OUTR\n//U2       EXEC PGM=PGMV,COND=(4,LT,CALL1.N2)\n//*\n//NST2",
        "//CALL1    EXEC OUTR,COND=(4,LT)\n//*\n//NST2",
        1,
    )
    with pytest.raises(JclProcRefused, match="calls procedures"):
        restart_flow(job_flow.jcl_job_flow(text), "NST1", {}, text, LIBS)
