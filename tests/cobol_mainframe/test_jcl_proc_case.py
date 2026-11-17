"""#8413 slice 2: IBM-written answers for PROC resolution and stepname.procstepname tests inside IF.

`tests/equivalence/jcl/proc/scenarios.json` holds the `flow_jcl` lines (seven jobs: unqualified EXEC PARM / COND, SET against PROC defaults and a nullified symbol, symbolics and SET, EXEC / DD overrides and an added DD,
JCLLIB ORDER and INCLUDE twice, an IF over a procedure steps), the JCLLIB library members, and the answers.
The answers were written from IBM's z/OS MVS JCL Reference (SA23-1385) BEFORE `gitgalaxy.core.jcl_proc` and
`jcl_flow` ran on them (the slice-3 PARM / COND / SET-precedence answers were read from the manual text in the same PR that
changed the resolver to give them; their `basis` quotes the page); ASSUMED entries are named in the file. The last tests reproduce every `expect`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow
from gitgalaxy.core.jcl_proc import JclProcRefused, expand_flow_rows, resolve_job

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "tests" / "equivalence" / "jcl" / "proc"
DOC = json.loads((CASE / "scenarios.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["flow_jcl"]) + "\n"
LIBS = {lib: {m: "\n".join(lines) + "\n" for m, lines in members.items()} for lib, members in DOC["libraries"].items()}


def test_every_jcl_line_fits_columns_1_to_72():
    texts = {"flow_jcl": TEXT} | {f"{lib}({m})": t for lib, ms in LIBS.items() for m, t in ms.items()}
    for name, text in texts.items():
        for n, ln in enumerate(text.splitlines(), 1):
            assert len(ln) <= 72, (name, n, ln)


def test_the_libraries_hold_the_members_the_scenarios_search_for():
    assert {k: sorted(v) for k, v in LIBS.items()} == {
        "LIB.A": ["PRC1", "PRC3", "PRC4", "STDDDS"],
        "LIB.B": ["PRC1", "PRC2", "PRC4", "STDDDS"],
    }


def test_each_resolve_scenario_names_a_call_of_its_job_and_gives_a_basis():
    ids = [s["id"] for s in DOC["resolve"] + DOC["flow"]]
    assert len(ids) == len(set(ids))
    for sc in DOC["resolve"]:
        assert all(k.split(".")[0] == sc["call"] for k in sc["expect"]), sc["id"]
        assert sc["basis"], sc["id"]
    assumed = {a["id"] for a in DOC["assumed"]}
    assert {sc["assumed"] for sc in DOC["resolve"] + DOC["flow"] if "assumed" in sc} <= assumed


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(s["id"] for s in DOC["resolve"] + DOC["flow"])
    assert "exec-parm-first-step-only" in ids and "set-loses-to-proc-default" in ids
    for word in (
        "sym-defaults",
        "exec-overrides",
        "set-",
        "parm-cond",
        "dd-override",
        "added-dd",
        "jcllib",
        "include",
        "ifp-",
    ):
        assert word in ids, word


def test_what_is_not_answered_is_refused_by_name():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("together with", "duplicate symbols", "assigned nowhere", "nested procedure"):
        assert name in refused, name


@pytest.mark.parametrize("sc", DOC["resolve"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_resolved_step_list(sc):
    got = resolve_job(TEXT, LIBS, sc["job"])
    for key, want in sc["expect"].items():
        assert key in got, (sc["id"], key)
        for field, value in want.items():
            assert got[key][field] == value, (sc["id"], key, field)
    assert [k for k in got if k.split(".")[0] == sc["call"]] == list(sc["expect"]), sc["id"]
    assert [list(v["dd"]) for k, v in got.items() if k in sc["expect"]] == [
        list(v["dd"]) for v in sc["expect"].values()
    ]


def test_the_flow_evaluator_reproduces_every_procstep_scenario():
    rows = job_flow.jcl_job_flow(TEXT)
    for sc in DOC["flow"]:
        flow = JclFlow(expand_flow_rows(rows, sc["job"], TEXT, LIBS))
        assert flow.run(sc["job"], sc["given"]).actions == sc["expect"], sc["id"]


def test_a_symbolic_assigned_nowhere_and_both_override_forms_at_once_are_refused():
    base = "//J JOB\n//PR PROC\n//A EXEC PGM=X,PARM='&NOPE'\n// PEND\n//C EXEC PR\n"
    with pytest.raises(JclProcRefused, match="assigned nowhere"):
        resolve_job(base, {}, "J")
    both = base.replace("PARM='&NOPE'", "PARM=Z").replace("EXEC PR", "EXEC PR,PARM=Q,PARM.A=R")
    with pytest.raises(JclProcRefused, match=r"PARM= together with PARM\.procstep="):
        resolve_job(both, {}, "J")
    with pytest.raises(JclProcRefused, match=r"COND= together with COND\.procstep="):
        resolve_job(both.replace("PARM", "COND"), {}, "J")


def test_a_library_procedure_in_if_flow_needs_the_libraries_and_the_member_to_exist():
    text = "//J JOB\n//C EXEC NOPE\n"
    rows = job_flow.jcl_job_flow(text)
    with pytest.raises(JclProcRefused, match="no libraries were given"):
        expand_flow_rows(rows, "J")
    with pytest.raises(JclProcRefused, match="in no library"):
        expand_flow_rows(rows, "J", text, {"LIB.A": {}})


def test_the_first_library_of_jcllib_order_supplies_the_flow_steps():
    text = "//J JOB\n//L JCLLIB ORDER=(LIB.A,LIB.B)\n//C EXEC PRC4\n"
    rows = expand_flow_rows(job_flow.jcl_job_flow(text), "J", text, LIBS)
    assert [r["step_name"] for r in rows if r["kind"] == "STEP"] == ["C.M1"]
