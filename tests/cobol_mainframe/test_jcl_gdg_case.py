"""#8413 slice 3: IBM-written answers for GDG relative generations.

`tests/equivalence/jcl/gdg/scenarios.json` holds the `flow_jcl` lines (six jobs: reading (0) / (-1) / (-2), a (+1)
created and read in one job, (+1) and (+2), abnormal dispositions, a bypassed creator, a PASSed generation) and the
answers: the absolute generation each DD names and the catalog after the job. The answers were written from IBM's
z/OS MVS JCL Reference (SA23-1385) and z/OS DFSMS Using Data Sets BEFORE `gitgalaxy.core.jcl_gdg` ran on them;
ASSUMED entries are named in the file. The last tests reproduce every `expect` and `catalog_after`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow
from gitgalaxy.core.jcl_gdg import JclGdgRefused, resolve_gdg

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "gdg" / "scenarios.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["flow_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
BY_ID = {s["id"]: s for s in DOC["scenarios"]}


def _run(text, job, catalog, given):
    rows = job_flow.jcl_job_flow(text)
    return resolve_gdg(rows, job, catalog, JclFlow(rows).run(job, given))


def test_every_jcl_line_fits_columns_1_to_72():
    for n, ln in enumerate(DOC["flow_jcl"], 1):
        assert len(ln) <= 72, (n, ln)


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(BY_ID)
    for word in ("rel-read", "create-then-read", "plus-one-plus-two", "abend-", "bypassed", "pass-then", "limit-"):
        assert word in ids, word
    assert len(BY_ID) == len(DOC["scenarios"])
    gens = {r["generation"] for r in ROWS if r["kind"] == "DD" and r.get("generation")}
    assert gens == {"0", "-1", "-2", "+1", "+2"}


def test_each_scenario_names_a_job_gives_a_basis_and_its_assumptions_exist():
    jobs = {r["name"] for r in ROWS if r["kind"] == "JOB"}
    assumed = {a["id"] for a in DOC["assumed"]}
    for sc in DOC["scenarios"]:
        assert sc["job"] in jobs and sc["basis"], sc["id"]
        assert ("catalog" in sc) != ("catalog_from" in sc), sc["id"]
        assert {sc["assumed"]} <= assumed if "assumed" in sc else True


def test_what_is_not_answered_is_refused_by_name():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("same (+n)", "read before any step creates", "PASSed generation", "DISP=MOD"):
        assert name in refused, name


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_generation_and_catalog_answer(sc):
    catalog = BY_ID[sc["catalog_from"]]["catalog_after"] if "catalog_from" in sc else sc["catalog"]
    flow = JclFlow(ROWS).run(sc["job"], sc["given"])
    names, after = resolve_gdg(ROWS, sc["job"], catalog, flow)
    assert names == sc["expect"], sc["id"]
    assert after == sc["catalog_after"], sc["id"]


def test_a_catalog_given_to_the_resolver_is_not_changed():
    sc = BY_ID["create-then-read-same-job"]
    before = json.dumps(sc["catalog"], sort_keys=True)
    _run(TEXT, sc["job"], sc["catalog"], sc["given"])
    assert json.dumps(sc["catalog"], sort_keys=True) == before


CAT = {"G.B": {"limit": 5, "generations": [1, 2]}}
HEAD = "//J JOB\n"


def test_two_new_plus_ones_a_read_before_create_and_a_missing_generation_are_refused():
    two = (
        HEAD
        + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,CATLG)\n//B EXEC PGM=X\n//P DD DSN=G.B(+1),DISP=(NEW,CATLG)\n"
    )
    with pytest.raises(JclGdgRefused, match="same"):
        _run(two, "J", CAT, {"A": {"rc": 0}, "B": {"rc": 0}})
    early = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match="before any step creates"):
        _run(early, "J", CAT, {"A": {"rc": 0}})
    gone = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(-2),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match="no cataloged generation"):
        _run(gone, "J", CAT, {"A": {"rc": 0}})
    nobase = HEAD + "//A EXEC PGM=X\n//O DD DSN=H.B(0),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match="no catalog entry"):
        _run(nobase, "J", CAT, {"A": {"rc": 0}})


def test_a_passed_generation_never_received_and_a_removing_disposition_are_refused():
    passed = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,PASS)\n"
    with pytest.raises(JclGdgRefused, match="never received"):
        _run(passed, "J", CAT, {"A": {"rc": 0}})
    scratch = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(0),DISP=(OLD,DELETE)\n"
    with pytest.raises(JclGdgRefused, match="removes an existing"):
        _run(scratch, "J", CAT, {"A": {"rc": 0}})


def test_a_new_generation_with_no_disposition_is_deleted_and_keep_is_not_cataloged():
    dflt = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW)\n"
    assert _run(dflt, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": [1, 2]}}
    keep = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,KEEP)\n"
    assert _run(keep, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": [1, 2]}}
