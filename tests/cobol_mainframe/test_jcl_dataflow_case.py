"""#8413 slice 5: IBM-written answers for data flow between steps.

`tests/equivalence/jcl/dataflow/scenarios.json` holds the `flow_jcl` lines (seven jobs: `&&` temporaries passed and
deleted, default dispositions, a bypassed creator, DUMMY / NULLFILE, concatenation read order, a concatenation of
temporaries, SYSOUT classes and OUTPUT references) and the answers: what each DD of a step that runs names, and each
temporary's creator, receivers and deletion. The answers were written from IBM's z/OS MVS JCL Reference (SA23-1385)
BEFORE `gitgalaxy.core.jcl_dataflow` ran on them; ASSUMED entries are named in the file. The last tests reproduce every
`expect` and `temporaries`, and each refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_dataflow import JclDataflowRefused, resolve_dataflow
from gitgalaxy.core.jcl_flow import JclFlow

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "dataflow" / "scenarios.json").read_text(encoding="utf-8"))
ROWS = job_flow.jcl_job_flow("\n".join(DOC["flow_jcl"]) + "\n")
BY_ID = {s["id"]: s for s in DOC["scenarios"]}


def _run(text, job, given, msgclass=None):
    rows = job_flow.jcl_job_flow(text)
    return resolve_dataflow(rows, job, JclFlow(rows).run(job, given), msgclass)


def test_every_jcl_line_fits_columns_1_to_72():
    for n, ln in enumerate(DOC["flow_jcl"], 1):
        assert len(ln) <= 72, (n, ln)


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(BY_ID)
    for word in (
        "temp-pass",
        "temp-default",
        "bypassed",
        "dummy-and-nullfile",
        "concat-read",
        "concat-temp",
        "sysout-",
    ):
        assert word in ids, word
    assert len(BY_ID) == len(DOC["scenarios"])
    kinds = {r["kind"] for r in ROWS}
    assert {"DUMMY", "SYSOUT", "TEMP", "OUTPUT"} <= kinds
    assert any(r.get("dsn", "").startswith("&&") for r in ROWS if r["kind"] == "DD")
    assert any(r["dd_name"] == "IN" and r["step_name"] == "M1" for r in ROWS if r["kind"] == "DD")


def test_each_scenario_names_a_job_gives_a_basis_and_its_assumptions_exist():
    jobs = {r["name"] for r in ROWS if r["kind"] == "JOB"}
    assumed = {a["id"] for a in DOC["assumed"]}
    for sc in DOC["scenarios"]:
        assert sc["job"] in jobs and sc["basis"], sc["id"]
        assert {sc["assumed"]} <= assumed if "assumed" in sc else True


def test_what_is_not_answered_is_refused_by_name():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("before any step creates it", "CATLG", "DUMMY coded on a DD inside", "SYSOUT with no class", "OUTPUT"):
        assert name in refused, name


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_dd_and_temporary_answer(sc):
    flow = JclFlow(ROWS).run(sc["job"], sc["given"])
    answers, temps = resolve_dataflow(ROWS, sc["job"], flow, sc.get("msgclass"))
    assert answers == sc["expect"], sc["id"]
    assert temps == sc["temporaries"], sc["id"]


HEAD = "//J JOB\n"
MK = "//A EXEC PGM=X\n//O DD DSN=&&T,DISP=(NEW,PASS),UNIT=SYSDA,SPACE=(TRK,1)\n"


def test_a_temporary_received_before_creation_after_deletion_or_created_twice_is_refused():
    early = HEAD + "//A EXEC PGM=X\n//I DD DSN=&&T,DISP=OLD\n"
    with pytest.raises(JclDataflowRefused, match="before a step creates it"):
        _run(early, "J", {"A": {"rc": 0}})
    gone = HEAD + MK + "//B EXEC PGM=X\n//I DD DSN=&&T,DISP=(OLD,DELETE)\n//C EXEC PGM=X\n//I DD DSN=&&T,DISP=OLD\n"
    with pytest.raises(JclDataflowRefused, match="after it was deleted"):
        _run(gone, "J", {s: {"rc": 0} for s in "ABC"})
    twice = HEAD + MK + "//B EXEC PGM=X\n//O DD DSN=&&T,DISP=(NEW,PASS),UNIT=SYSDA,SPACE=(TRK,1)\n"
    with pytest.raises(JclDataflowRefused, match="created twice"):
        _run(twice, "J", {"A": {"rc": 0}, "B": {"rc": 0}})


def test_a_reader_of_a_bypassed_creators_temporary_is_refused():
    text = HEAD + "//Z EXEC PGM=X\n" + MK.replace("//A EXEC PGM=X", "//A EXEC PGM=X,COND=(0,LT,Z)")
    text += "//B EXEC PGM=X\n//I DD DSN=&&T,DISP=OLD\n"
    with pytest.raises(JclDataflowRefused, match="before a step creates it"):
        _run(text, "J", {"Z": {"rc": 4}, "B": {"rc": 0}})


def test_a_retained_temporary_a_dummy_in_a_concatenation_and_a_classless_sysout_are_refused():
    keep = HEAD + "//A EXEC PGM=X\n//O DD DSN=&&T,DISP=(NEW,CATLG),UNIT=SYSDA,SPACE=(TRK,1)\n"
    with pytest.raises(JclDataflowRefused, match="not answered"):
        _run(keep, "J", {"A": {"rc": 0}})
    cat = HEAD + "//A EXEC PGM=X\n//I DD DSN=P.Q,DISP=SHR\n// DD DUMMY\n"
    with pytest.raises(JclDataflowRefused, match="DUMMY inside a concatenation"):
        _run(cat, "J", {"A": {"rc": 0}})
    star = HEAD + "//A EXEC PGM=X\n//P DD SYSOUT=*\n"
    with pytest.raises(JclDataflowRefused, match="no class"):
        _run(star, "J", {"A": {"rc": 0}})
    blank = HEAD + "//A EXEC PGM=X\n//P DD SYSOUT=(,),OUTPUT=*.O1\n//O1 OUTPUT CLASS=B\n"
    with pytest.raises(JclDataflowRefused, match="no class"):
        _run(blank, "J", {"A": {"rc": 0}}, "X")


def test_an_output_reference_to_no_output_statement_is_refused():
    text = HEAD + "//A EXEC PGM=X\n//P DD SYSOUT=A,OUTPUT=*.NOPE\n"
    with pytest.raises(JclDataflowRefused, match="names no OUTPUT"):
        _run(text, "J", {"A": {"rc": 0}})


def test_an_abended_step_applies_its_abnormal_disposition_to_a_temporary():
    text = HEAD + "//A EXEC PGM=X\n//O DD DSN=&&T,DISP=(NEW,PASS,DELETE),UNIT=SYSDA,SPACE=(TRK,1)\n"
    assert _run(text, "J", {"A": {"abend": "S0C7"}})[1]["&&T"]["deleted_after"] == "A"
    assert _run(text, "J", {"A": {"rc": 0}})[1]["&&T"]["deleted_after"] == "JOB"
