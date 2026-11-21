"""#8413 slice 4: IBM-written answers for JOB RESTART= (deferred step / procedure-step / checkpoint restart).

`tests/equivalence/jcl/restart/scenarios.json` holds the `flow_jcl` lines (five restarted jobs and five refused shapes) and the
answers: per step, skipped (before the restart step), run or bypass. The answers were written from IBM's z/OS MVS JCL
Reference (SA23-1385, the JOB statement's RESTART parameter) BEFORE `gitgalaxy.core.jcl_restart` ran on them; ASSUMED
entries are named in the file. The last tests reproduce every `expect` and every refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_proc import JclProcRefused
from gitgalaxy.core.jcl_restart import JclRestartRefused, restart_flow

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "restart" / "scenarios.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["flow_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
LIBDOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "restart" / "library.json").read_text(encoding="utf-8"))
LIB_TEXT = "\n".join(LIBDOC["library_jcl"]) + "\n"
LIB_ROWS = job_flow.jcl_job_flow(LIB_TEXT)
LIBS = {lib: {m: "\n".join(ls) + "\n" for m, ls in ms.items()} for lib, ms in LIBDOC["libraries"].items()}


def test_every_jcl_line_fits_columns_1_to_72():
    members = [ln for ms in LIBDOC["libraries"].values() for ls in ms.values() for ln in ls]
    for n, ln in enumerate(DOC["flow_jcl"] + LIBDOC["library_jcl"] + members, 1):
        assert len(ln) <= 72, (n, ln)


def test_the_reader_sees_each_restart_and_checkid():
    got = {r["name"]: (r.get("restart"), r.get("restart_checkid")) for r in ROWS if r["kind"] == "JOB"}
    assert got["RSTJOB1"] == ("S3", None)
    assert got["RSTJOB2"] == ("*", None)
    assert got["RSTJOB3"] == ("CALL1.P2", None)
    assert got["RSTJOB4"] == ("V3", "CK1")
    assert got["RSTJOB11"] == ("*", "CKPT2")
    assert got["RSTJOB12"] == ("PAY.WEEKLY", "CHECK8")


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(s["id"] for s in DOC["scenarios"])
    for word in (
        "step-restart",
        "restart-star",
        "procstep-restart",
        "checkpoint-restart",
        "rd-",
        "cond-referback",
        "if-referback",
    ):
        assert word in ids, word
    assert len(ids.split()) == len(set(ids.split()))
    assumed = {a["id"] for a in DOC["assumed"]}
    assert {s["assumed"] for s in DOC["scenarios"] if "assumed" in s} <= assumed
    assert all(s["basis"] for s in DOC["scenarios"])


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_restart_answer(sc):
    got = restart_flow(ROWS, sc["job"], sc["given"])
    assert got == sc["expect"], sc["id"]
    assert list(got) == list(sc["expect"]), sc["id"]


@pytest.mark.parametrize("sc", LIBDOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_library_procedure_restart_answer(sc):
    got = restart_flow(LIB_ROWS, sc["job"], sc["given"], LIB_TEXT, LIBS)
    assert got == sc["expect"], sc["id"]
    assert list(got) == list(sc["expect"]), sc["id"]


@pytest.mark.parametrize("r", LIBDOC["refused"], ids=lambda r: r["id"])
def test_a_library_restart_that_is_not_answered_is_refused_by_name(r):
    with pytest.raises((JclRestartRefused, JclProcRefused), match=r["match"]):
        restart_flow(LIB_ROWS, r["job"], {}, LIB_TEXT, LIBS)


def test_a_library_procedure_with_no_libraries_given_is_refused():
    with pytest.raises(JclProcRefused, match="no libraries were given"):
        restart_flow(LIB_ROWS, "LIBJ1", {})


@pytest.mark.parametrize("r", DOC["refused"], ids=lambda r: r["id"])
def test_what_is_not_answered_is_refused_by_name(r):
    with pytest.raises(JclRestartRefused, match=r["match"]):
        restart_flow(ROWS, r["job"], {})


def test_a_job_with_no_restart_skips_nothing():
    text = "//J JOB\n//A EXEC PGM=X\n//B EXEC PGM=Y\n"
    assert restart_flow(job_flow.jcl_job_flow(text), "J", {"A": {"rc": 0}, "B": {"rc": 0}}) == {"A": "run", "B": "run"}


def test_an_unqualified_cond_with_a_procstep_cond_on_one_call_is_refused():
    from gitgalaxy.core.jcl_proc import JclProcRefused

    text = (
        "//J JOB RESTART=C.K2\n//PR PROC\n//K1 EXEC PGM=A\n//K2 EXEC PGM=B\n//K3 EXEC PGM=C\n//  PEND\n"
        "//C EXEC PR,COND=(0,NE),COND.K3=(4,LT,C.K2)\n"
    )
    with pytest.raises(JclProcRefused, match="COND.procstep"):
        restart_flow(job_flow.jcl_job_flow(text), "J", {"C.K2": {"rc": 0}, "C.K3": {"rc": 0}})
