"""#7065 / #4891: the CardDemo JclFlow case (`tests/equivalence/jcl/carddemo/`).

`scenarios.json` gives, for each CardDemo job that carries an EXEC COND, the run / bypass answer per step for several
return-code and abend outcomes. The answers were written from IBM's z/OS MVS JCL Reference (SA23-1385, EXEC COND) and the
job text before `gitgalaxy.core.jcl_flow` ran on them (policy 5). This file pins the members, checks the reader sees the
steps the answers assume, reproduces every answer, and sweeps the corpus so a job with a COND cannot go unlisted.
The corpus is the pinned CardDemo checkout under GITGALAXY_MAINFRAME_CORPORA; the tests skip when it is absent.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow
from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "tests" / "equivalence" / "jcl" / "carddemo" / "scenarios.json"
DOC = json.loads(CASE.read_text(encoding="utf-8"))
CORPUS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora")) / DOC["corpus"]
SCENARIOS = [(j["job"], s) for j in DOC["jobs"] for s in j["scenarios"]]

needs_corpus = pytest.mark.skipif(not CORPUS.is_dir(), reason="the CardDemo corpus is not checked out")


def _text(member: str) -> str:
    return read_source(CORPUS / member).text


def _flow(member: str) -> list[dict]:
    return job_flow.jcl_job_flow(_text(member))


def _by_job() -> dict[str, dict]:
    return {j["job"]: j for j in DOC["jobs"]}


def test_every_scenario_names_only_the_jobs_steps_and_gives_each_step_an_answer():
    for j in DOC["jobs"]:
        for s in j["scenarios"]:
            assert set(s["given"]) <= set(j["steps"]), (j["job"], s["id"])
            assert set(s["expect"]) == set(j["steps"]), (j["job"], s["id"])
            assert set(s["expect"].values()) <= {"run", "bypass"}, (j["job"], s["id"])
            assert s["basis"].strip(), (j["job"], s["id"])
        assert len({s["id"] for s in j["scenarios"]}) == len(j["scenarios"]), j["job"]
    assert len({j["job"] for j in DOC["jobs"]}) == len(DOC["jobs"])


def test_the_class_has_every_input_form_the_jobs_use():
    """Whole input class: an all-zero run, a boundary rc, an rc above it, and an abend, for every COND shape present."""
    ids = {s["id"] for _, s in SCENARIOS}
    assert {"all-zero", "step10-abend", "trn-rc4", "trn-rc8"} <= ids
    conds = {j["job"]: {s["expect"][st] for s in j["scenarios"] for st in j["steps"]} for j in DOC["jobs"]}
    assert all(v == {"run", "bypass"} for k, v in conds.items() if k != "TXT2PDF1"), conds


@needs_corpus
def test_the_members_are_the_ones_the_answers_were_written_from():
    for j in DOC["jobs"]:
        assert hashlib.sha256((CORPUS / j["member"]).read_bytes()).hexdigest() == j["sha256"], j["member"]


@needs_corpus
def test_the_reader_sees_each_job_and_its_steps_in_order():
    for j in DOC["jobs"]:
        rows = _flow(j["member"])
        jobs = [r["name"] for r in rows if r["kind"] == "JOB"]
        assert jobs == [j["job"]], j["member"]
        assert [r["step_name"] for r in rows if r["kind"] == "STEP"] == j["steps"], j["member"]
        assert not any(r.get("if_cond") for r in rows if r["kind"] == "STEP"), j["member"]


@needs_corpus
@pytest.mark.parametrize("job,scenario", SCENARIOS, ids=[f"{j}-{s['id']}" for j, s in SCENARIOS])
def test_jclflow_reproduces_the_answer_written_before_it_ran(job, scenario):
    member = _by_job()[job]["member"]
    result = JclFlow(_flow(member)).run(job, scenario["given"])
    assert result.actions == scenario["expect"], scenario["basis"]


@needs_corpus
def test_every_carddemo_member_with_an_exec_cond_is_modelled_or_named_as_not_modelled():
    with_cond = set()
    for p in CORPUS.rglob("*"):
        if p.suffix.lower() in (".jcl", ".prc", ".proc") and ".git" not in p.parts:
            if any(
                r["kind"] == "STEP" and (r.get("cond") or r.get("if_cond"))
                for r in job_flow.jcl_job_flow(read_source(p).text)
            ):
                with_cond.add(p.relative_to(CORPUS).as_posix())
    modelled = {j["member"] for j in DOC["jobs"]}
    named = {n["member"] for n in DOC["not_modelled"] if "*" not in n["member"]}
    assert with_cond == modelled | (named & with_cond), sorted(with_cond ^ modelled)
    assert modelled <= with_cond
    assert with_cond - modelled <= named
    for n in DOC["not_modelled"]:
        assert n["reason"].strip()
        if "*" not in n["member"]:
            assert (CORPUS / n["member"]).is_file(), n["member"]


@needs_corpus
def test_typrun_scan_is_stated_as_refused_not_silently_assumed():
    text = _text("app/app-transaction-type-db2/jcl/CREADB21.jcl")
    assert "TYPRUN=SCAN" in text
    assert any("TYPRUN" in r["construct"] for r in DOC["refused"])
    assert not any("TYPRUN" in s["basis"] for _, s in SCENARIOS)


@needs_corpus
def test_the_recorded_run_the_status_slide_reads_matches_a_live_run():
    """measured.json is what the docs run shows without the corpus (capability_ledger.jcl_step_flow); it must be the
    run of these answers. Re-record with `python tests/tools/capability_ledger.py jcl-measure CORPORA`."""
    import sys

    sys.path.insert(0, str(REPO / "tests" / "tools"))
    import capability_ledger as cl

    rec = json.loads(cl.JCL_MEASURED.read_text(encoding="utf-8"))
    assert rec["answers_sha256"] == hashlib.sha256(CASE.read_bytes()).hexdigest()
    assert (rec["matched"], rec["of"]) == cl.carddemo_jcl_live(CORPUS)
