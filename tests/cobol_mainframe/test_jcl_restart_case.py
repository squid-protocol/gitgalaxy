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
from gitgalaxy.core.jcl_restart import JclRestartRefused, restart_flow

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "restart" / "scenarios.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["flow_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)


def test_every_jcl_line_fits_columns_1_to_72():
    for n, ln in enumerate(DOC["flow_jcl"], 1):
        assert len(ln) <= 72, (n, ln)


def test_the_reader_sees_each_restart_and_checkid():
    got = {r["name"]: (r.get("restart"), r.get("restart_checkid")) for r in ROWS if r["kind"] == "JOB"}
    assert got["RSTJOB1"] == ("S3", None)
    assert got["RSTJOB2"] == ("*", None)
    assert got["RSTJOB3"] == ("CALL1.P2", None)
    assert got["RSTJOB4"] == ("V3", "CK1")


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(s["id"] for s in DOC["scenarios"])
    for word in ("step-restart", "restart-star", "procstep-restart", "checkpoint-restart", "rd-"):
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


@pytest.mark.parametrize("r", DOC["refused"], ids=lambda r: r["id"])
def test_what_is_not_answered_is_refused_by_name(r):
    with pytest.raises(JclRestartRefused, match=r["match"]):
        restart_flow(ROWS, r["job"], {})


def test_a_job_with_no_restart_skips_nothing():
    text = "//J JOB\n//A EXEC PGM=X\n//B EXEC PGM=Y\n"
    assert restart_flow(job_flow.jcl_job_flow(text), "J", {"A": {"rc": 0}, "B": {"rc": 0}}) == {"A": "run", "B": "run"}
