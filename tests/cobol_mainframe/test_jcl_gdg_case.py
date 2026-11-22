"""#8413 slice 3: IBM-written answers for GDG relative generations.

`tests/equivalence/jcl/gdg/scenarios.json` holds the `flow_jcl` lines (sixteen jobs: GDGBIAS=STEP, GDG DDs in procedure steps, deleting the group or its oldest generation, reading (0) / (-1) / (-2), a (+1)
created and read in one job, (+1) and (+2), abnormal dispositions, a bypassed creator, a PASSed generation, a lone (+2), NEW,KEEP) and the
answers: the absolute generation each DD names and the catalog after the job. The answers were written from IBM's
z/OS MVS JCL Reference (SA23-1385) and z/OS DFSMS Using Data Sets BEFORE `gitgalaxy.core.jcl_gdg` ran on them;
GDGBIAS=STEP is from the User's Guide, Appendix A, pp. 235-237 and 246. ASSUMED entries are named in the file. The last tests reproduce every `expect` and `catalog_after`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow
from gitgalaxy.core.jcl_gdg import JclGdgRefused, resolve_gdg
from gitgalaxy.core.jcl_proc import expand_flow_rows
from gitgalaxy.core.jcl_restart import resolve_gdg_restart

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "gdg" / "scenarios.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["flow_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
BY_ID = {s["id"]: s for s in DOC["scenarios"]}


def _run(text, job, catalog, given):
    rows = expand_flow_rows(job_flow.jcl_job_flow(text), job)
    return resolve_gdg(rows, job, catalog, JclFlow(rows).run(job, given))


def test_every_jcl_line_fits_columns_1_to_72():
    for n, ln in enumerate(DOC["flow_jcl"], 1):
        assert len(ln) <= 72, (n, ln)


def test_the_scenarios_cover_every_construct_of_the_checklist_line():
    ids = " ".join(BY_ID)
    for word in (
        "rel-read",
        "create-then-read",
        "plus-one-plus-two",
        "abend-",
        "bypassed",
        "pass-then",
        "limit-",
        "mod-plus-one",
        "delete-whole-group",
        "delete-the-oldest",
        "step-bias-",
        "job-bias-",
        "proc-step-gdg",
        "proc-called-twice",
        "restart-step-",
        "restart-star-",
        "restart-checkpoint-same",
        "restart-checkpoint-keep",
        "pass-never-received",
        "wraparound-",
        "after-a-wraparound",
        "one-step-adds-three",
        "next-job-reads-minus-two",
    ):
        assert word in ids, word
    assert len(BY_ID) == len(DOC["scenarios"])
    gens = {r["generation"] for r in ROWS if r["kind"] == "DD" and r.get("generation")}
    assert gens == {"0", "-1", "-2", "+1", "+2", "+3"}


def test_each_scenario_names_a_job_gives_a_basis_and_its_assumptions_exist():
    jobs = {r["name"] for r in ROWS if r["kind"] == "JOB"}
    assumed = {a["id"] for a in DOC["assumed"]}
    for sc in DOC["scenarios"]:
        assert sc["job"] in jobs and sc["basis"], sc["id"]
        assert ("catalog" in sc) != ("catalog_from" in sc), sc["id"]
        assert {sc["assumed"]} <= assumed if "assumed" in sc else True


def test_what_is_not_answered_is_refused_by_name():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("same (+n)", "read before any step creates", "DISP=MOD"):
        assert name in refused, name
    for name in ("other than the oldest", "deleted earlier in the job", "whole group"):
        assert name in refused, name
    for name in ("GDGBIAS value other than", "two calls of a procedure", "PASSed or KEEP-deferred", "overrides"):
        assert name in refused, name


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_generation_and_catalog_answer(sc):
    catalog = BY_ID[sc["catalog_from"]]["catalog_after"] if "catalog_from" in sc else sc["catalog"]
    if sc.get("restart"):
        names, after = resolve_gdg_restart(ROWS, sc["job"], catalog, sc["given"])
    else:
        rows = expand_flow_rows(ROWS, sc["job"])
        names, after = resolve_gdg(rows, sc["job"], catalog, JclFlow(rows).run(sc["job"], sc["given"]))
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


def test_a_passed_generation_never_received_is_scratched_and_a_removing_disposition_is_refused():
    passed = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,PASS)\n"
    names, after = _run(passed, "J", CAT, {"A": {"rc": 0}})
    assert names == {"A.O": 3} and after["G.B"]["generations"] == [1, 2]
    uncat = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(0),DISP=(OLD,UNCATLG)\n"
    with pytest.raises(JclGdgRefused, match="removes an existing"):
        _run(uncat, "J", CAT, {"A": {"rc": 0}})
    group = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B,DISP=(OLD,UNCATLG)\n"
    with pytest.raises(JclGdgRefused, match="UNCATLG of a generation group"):
        _run(group, "J", CAT, {"A": {"rc": 0}})


def test_creations_across_the_9999_wrap_roll_in_oldest_first_and_the_limit_drops_the_oldest():
    cat = {"G.B": {"limit": 3, "generations": [9998, 9999]}}
    two = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+2),DISP=(NEW,CATLG)\n//P DD DSN=G.B(+1),DISP=(NEW,CATLG)\n"
    names, after = _run(two, "J", cat, {"A": {"rc": 0}})
    assert names == {"A.O": 2, "A.P": 1}
    assert after["G.B"]["generations"] == [9999, 1, 2]


def test_a_new_generation_with_no_disposition_is_deleted_and_keep_is_a_deferred_roll_in():
    dflt = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW)\n"
    assert _run(dflt, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": [1, 2]}}
    keep = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,KEEP)\n"
    assert _run(keep, "J", CAT, {"A": {"rc": 0}})[1] == {
        "G.B": {"limit": 5, "generations": [1, 2], "deferred_rollin": [3]}
    }


def test_a_group_with_no_generation_to_name_is_refused_and_empty_is_carried_to_the_next_job():
    first = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(0),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match=r"no cataloged generation \(0\)"):
        _run(first, "J", {"G.B": {"limit": 2, "generations": []}}, {"A": {"rc": 0}})
    make = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,CATLG)\n"
    after = _run(make, "J", {"G.B": {"limit": 2, "empty": True, "generations": [1, 2]}}, {"A": {"rc": 0}})[1]
    assert after == {"G.B": {"limit": 2, "empty": True, "generations": [3]}}
    assert "empty" not in _run(make, "J", CAT, {"A": {"rc": 0}})[1]["G.B"]


def test_mod_of_an_absent_plus_one_is_new_and_mod_of_an_absent_zero_or_minus_n_is_refused():
    mod = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(MOD,CATLG)\n"
    assert _run(mod, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": [1, 2, 3]}}
    gone = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(-2),DISP=(MOD,CATLG)\n"
    with pytest.raises(JclGdgRefused, match="no cataloged generation"):
        _run(gone, "J", CAT, {"A": {"rc": 0}})


def test_deleting_the_oldest_removes_it_and_any_other_generation_is_refused_by_name():
    oldest = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(-1),DISP=(OLD,DELETE)\n"
    assert _run(oldest, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": [2]}}
    newest = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(0),DISP=(OLD,DELETE)\n"
    with pytest.raises(JclGdgRefused, match="other than the oldest"):
        _run(newest, "J", CAT, {"A": {"rc": 0}})
    # an abended step applies the abnormal disposition: KEEP leaves the oldest cataloged
    keep = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(-1),DISP=(OLD,DELETE,KEEP)\n"
    assert _run(keep, "J", CAT, {"A": {"abend": "S0C7"}})[1] == {"G.B": {"limit": 5, "generations": [1, 2]}}
    # a bypassed step deletes nothing
    bypass = (
        HEAD
        + "//A EXEC PGM=X\n//O DD DSN=G.B,DISP=(OLD,DELETE)\n//B EXEC PGM=Y,COND=(0,LE)\n//P DD DSN=G.B(0),DISP=SHR\n"
    )
    assert _run(bypass, "J", CAT, {"A": {"rc": 0}})[1] == {"G.B": {"limit": 5, "generations": []}}


def test_a_group_delete_ignores_a_dataset_that_is_not_a_group_and_refuses_a_deleted_read_or_a_mixed_job():
    plain = HEAD + "//A EXEC PGM=X\n//O DD DSN=OTHER.DS,DISP=(OLD,DELETE)\n"
    assert _run(plain, "J", CAT, {"A": {"rc": 0}})[1] == CAT
    gone = HEAD + "//A EXEC PGM=X\n//R DD DSN=G.B(0),DISP=SHR\n//B EXEC PGM=X\n//D DD DSN=G.B,DISP=(OLD,DELETE)\n"
    gone += "//C EXEC PGM=X\n//S DD DSN=G.B(0),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match="deleted earlier in the job"):
        _run(gone, "J", CAT, {"A": {"rc": 0}, "B": {"rc": 0}, "C": {"rc": 0}})
    mixed = (
        HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,CATLG)\n//B EXEC PGM=X\n//D DD DSN=G.B,DISP=(OLD,DELETE)\n"
    )
    with pytest.raises(JclGdgRefused, match="created a generation"):
        _run(mixed, "J", CAT, {"A": {"rc": 0}, "B": {"rc": 0}})
    shr = HEAD + "//A EXEC PGM=X\n//O DD DSN=G.B,DISP=SHR\n"
    assert _run(shr, "J", CAT, {"A": {"rc": 0}})[1] == CAT


STEP = "//J JOB GDGBIAS=STEP\n"


def test_step_bias_rolls_in_at_step_end_and_job_bias_waits_for_the_job_end():
    two = "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,CATLG)\n//B EXEC PGM=X\n//P DD DSN=G.B(0),DISP=SHR\n"
    given = {"A": {"rc": 0}, "B": {"rc": 0}}
    assert _run(STEP + two, "J", CAT, given)[0] == {"A.O": 3, "B.P": 3}
    assert _run(HEAD + two, "J", CAT, given)[0] == {"A.O": 3, "B.P": 2}
    assert _run("//J JOB GDGBIAS=job\n" + two, "J", CAT, given)[0] == {"A.O": 3, "B.P": 2}


def test_a_gdgbias_other_than_job_or_step_and_a_passed_generation_under_step_are_refused():
    with pytest.raises(JclGdgRefused, match="is not JOB or STEP"):
        _run("//J JOB GDGBIAS=BOTH\n//A EXEC PGM=X\n//O DD DSN=G.B(0),DISP=SHR\n", "J", CAT, {"A": {"rc": 0}})
    passed = STEP + "//A EXEC PGM=X\n//O DD DSN=G.B(+1),DISP=(NEW,PASS)\n//B EXEC PGM=X\n//P DD DSN=G.B(0),DISP=SHR\n"
    with pytest.raises(JclGdgRefused, match="passed or deferred"):
        _run(passed, "J", CAT, {"A": {"rc": 0}, "B": {"rc": 0}})


def test_a_procedure_step_override_of_a_gdg_dd_is_refused_by_name():
    text = (
        HEAD
        + "//GP PROC\n//M1 EXEC PGM=X\n//OUT DD DSN=G.B(+1),DISP=(NEW,CATLG)\n//  PEND\n//C1 EXEC GP\n"
        + "//M1.OUT DD DSN=G.B(+1),DISP=(NEW,CATLG)\n"
    )
    with pytest.raises(JclGdgRefused, match="overrides a procedure step"):
        _run(text, "J", CAT, {"C1.M1": {"rc": 0}})


def _restart(text, job, catalog, given):
    return resolve_gdg_restart(job_flow.jcl_job_flow(text), job, catalog, given)


def test_a_step_restart_reading_the_original_plus_one_is_refused():
    sc = BY_ID["restart-step-present-numbers"]
    with pytest.raises(JclGdgRefused, match="before any step creates"):
        _restart(TEXT, "RSTOLD", sc["catalog"], {"STEP3": {"rc": 0}})


def test_a_checkpoint_restart_under_step_bias_is_refused_and_the_catalog_given_is_not_changed():
    sc = BY_ID["restart-checkpoint-same-numbers"]
    before = json.dumps(sc["catalog"], sort_keys=True)
    _restart(TEXT, "RCHK", sc["catalog"], sc["given"])
    assert json.dumps(sc["catalog"], sort_keys=True) == before
    step_bias = TEXT.replace(
        "//RCHK     JOB (ACCT),'GDG RESTART',CLASS=A,MSGCLASS=X,", "//RCHK     JOB (ACCT),'GDG RESTART',GDGBIAS=STEP,"
    )
    assert step_bias != TEXT
    with pytest.raises(JclGdgRefused, match="GDGBIAS=JOB"):
        _restart(step_bias, "RCHK", sc["catalog"], sc["given"])


def test_the_restart_refusals_are_named_in_the_file():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    assert "original relative generation" in refused or "reads a generation by the number" in refused
    assert "checkpoint restart" in refused


LIBDOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "gdg" / "library.json").read_text(encoding="utf-8"))
LIB_TEXT = "\n".join(LIBDOC["library_jcl"]) + "\n"
LIB_ROWS = job_flow.jcl_job_flow(LIB_TEXT)
LIBS = {lib: {m: "\n".join(ls) + "\n" for m, ls in ms.items()} for lib, ms in LIBDOC["libraries"].items()}


def test_every_library_case_line_fits_columns_1_to_72():
    members = [ln for ms in LIBDOC["libraries"].values() for ls in ms.values() for ln in ls]
    assert all(len(ln) <= 72 for ln in LIBDOC["library_jcl"] + members)


@pytest.mark.parametrize("sc", LIBDOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_library_procedure_gdg_restart_answer(sc):
    names, after = resolve_gdg_restart(LIB_ROWS, sc["job"], sc["catalog"], sc["given"], LIB_TEXT, LIBS)
    assert names == sc["expect"], sc["id"]
    assert after == sc["catalog_after"], sc["id"]


@pytest.mark.parametrize("r", LIBDOC["refused"], ids=lambda r: r["id"])
def test_a_library_gdg_restart_that_is_not_answered_is_refused_by_name(r):
    with pytest.raises(JclGdgRefused, match=r["match"]):
        resolve_gdg_restart(
            LIB_ROWS, r["job"], {"PAY.GDG": {"limit": 6, "generations": [6, 7]}}, r["given"], LIB_TEXT, LIBS
        )
