"""#4891: the level fixture for JCL step flow (EXEC COND, IF / THEN / ELSE / ENDIF).

`tests/equivalence/jcl/fixture/FLOW.jcl` holds three jobs; `scenarios.json` gives, per scenario, each step's return code or
abend and the run / bypass answer. The answers were written from IBM's z/OS MVS JCL Reference (SA23-1385) BEFORE any
evaluator existed (policy 5: level estates first); each scenario's `basis` cites the rule. This file checks the fixture's
shape and that the engine's job-flow reader sees the structure the scenarios assume. `gitgalaxy/core/jcl_flow.py` is the execution model: the last test reproduces every `expect` here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from gitgalaxy.core import job_flow

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "equivalence" / "jcl" / "fixture"
DOC = json.loads((FIXTURE / "scenarios.json").read_text(encoding="utf-8"))
FLOW = job_flow.jcl_job_flow((FIXTURE / "FLOW.jcl").read_text(encoding="utf-8"))


def _steps_by_job() -> dict[str, list[dict]]:
    jobs: dict[str, list[dict]] = {}
    current = None
    for row in FLOW:
        if row["kind"] == "JOB":
            current = row["name"]
            jobs[current] = []
        elif row["kind"] == "STEP":
            jobs[current].append(row)
    return jobs


def test_every_line_of_the_jcl_fits_columns_1_to_72():
    for n, ln in enumerate((FIXTURE / "FLOW.jcl").read_text(encoding="utf-8").splitlines(), 1):
        assert len(ln) <= 72, (n, ln)


def test_the_reader_sees_the_three_jobs_and_their_steps_in_order():
    jobs = _steps_by_job()
    assert {j: [s["step_name"] for s in steps] for j, steps in jobs.items()} == {
        "CONDJOB": ["S1", "S2", "S3", "S4", "S5", "S6"],
        "EVNJOB": ["T1", "T2", "T3"],
        "IFJOB": ["I1", "I2", "I3", "I4", "I5", "I6"],
    }


def test_the_reader_keeps_each_exec_cond_as_written():
    conds = {s["step_name"]: s["cond"] for steps in _steps_by_job().values() for s in steps}
    assert conds["S1"] is None
    assert conds["S2"] == "(4,LT,S1)"
    assert conds["S3"] == "((8,LE,S1),(0,NE,S2))"
    assert conds["S4"] == "(4,GT)"
    assert conds["S5"] == "EVEN"
    assert conds["S6"] == "ONLY"
    assert conds["T2"] == "((4,LT,T1),EVEN)"
    assert conds["T3"] == "((4,LT,T1),ONLY)"


def test_the_reader_attaches_each_if_clause_to_its_step():
    ifs = {s["step_name"]: s["if_cond"] for s in _steps_by_job()["IFJOB"]}
    assert ifs["I1"] is None
    assert ifs["I2"] == "(I1.RC = 0)"
    assert ifs["I3"] == "NOT (I1.RC = 0)"
    assert ifs["I4"] == "(RC > 4 | I2.RC = 4)"
    assert ifs["I5"] == "(ABEND = TRUE)"
    assert ifs["I6"] == "(I3.RUN = FALSE)"


def test_the_reader_binds_the_dds_the_dataset_note_relies_on():
    dds = [(r["step_name"], r["dd_name"], r["dsn"], r["disp"]) for r in FLOW if r["kind"] == "DD"]
    assert dds == [
        ("S1", "OUT", "APP.LEVEL.WORK", "NEW"),
        ("S2", "IN", "APP.LEVEL.WORK", "SHR"),
    ]


def test_each_scenario_answers_every_step_of_its_job_and_gives_input_only_to_steps_that_start():
    jobs = _steps_by_job()
    ids = [s["id"] for s in DOC["scenarios"]]
    assert len(ids) == len(set(ids))
    for sc in DOC["scenarios"]:
        names = [s["step_name"] for s in jobs[sc["job"]]]
        assert list(sc["expect"]) == names, sc["id"]
        assert set(sc["expect"].values()) <= {"run", "bypass"}, sc["id"]
        assert set(sc["given"]) == {n for n, a in sc["expect"].items() if a == "run"}, sc["id"]
        for given in sc["given"].values():
            assert (list(given) == ["rc"] and 0 <= given["rc"] <= 4095) or (
                list(given) == ["abend"] and re.fullmatch(r"S[0-9A-F]{3}|U\d{4}", given["abend"])
            ), (sc["id"], given)
        assert sc["basis"], sc["id"]


def test_the_scenarios_reach_every_branch_the_fixture_exists_to_pin():
    by_id = {s["id"]: s["expect"] for s in DOC["scenarios"]}
    assert {a for s in DOC["scenarios"] if s["job"] == "CONDJOB" for a in [s["expect"]["S2"]]} == {"run", "bypass"}
    assert {s["expect"]["S6"] for s in DOC["scenarios"] if s["job"] == "CONDJOB"} == {"run", "bypass"}  # ONLY
    assert {s["expect"]["S5"] for s in DOC["scenarios"] if s["job"] == "CONDJOB"} == {"run"}  # EVEN, no test coded
    assert {s["expect"]["T2"] for s in DOC["scenarios"] if s["job"] == "EVNJOB"} == {"run", "bypass"}
    for step in ("I2", "I3", "I4", "I5", "I6"):
        assert {s["expect"][step] for s in DOC["scenarios"] if s["job"] == "IFJOB"} == {"run", "bypass"}, step
    # an abend of the first step runs only the steps whose condition names it (COND EVEN / ONLY, IF ABEND)
    assert by_id["cond-s1-abend"]["S4"] == "bypass"
    assert by_id["if-i1-abend"]["I4"] == "bypass"


def test_what_is_not_found_in_ibms_text_is_refused_or_assumed_by_name():
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("JOB statement COND", "COND on a step inside", "final completion code", "RESTART", "AND and OR mixed"):
        assert name in refused, name
    assert [a["id"] for a in DOC["assumed"]] == ["A1", "A2", "A3", "A4"]
    assert "undefined by IBM" in DOC["datasets"].replace("Undefined by IBM", "undefined by IBM")


def test_the_flow_evaluator_reproduces_every_scenario():
    from gitgalaxy.core.jcl_flow import JclFlow

    flow = JclFlow(FLOW)
    for sc in DOC["scenarios"]:
        assert flow.run(sc["job"], sc["given"]).actions == sc["expect"], sc["id"]


# --- #8413 tier 1: IF / THEN / ELSE / ENDIF beyond the first fixture (IFFLOW.jcl, ifflow_scenarios.json) ---

IF_DOC = json.loads((FIXTURE / "ifflow_scenarios.json").read_text(encoding="utf-8"))
IF_FLOW = job_flow.jcl_job_flow((FIXTURE / "IFFLOW.jcl").read_text(encoding="utf-8"))


def _if_steps_by_job() -> dict[str, list[str]]:
    jobs: dict[str, list[str]] = {}
    current = None
    for row in IF_FLOW:
        if row["kind"] == "JOB":
            current = row["name"]
            jobs[current] = []
        elif row["kind"] == "STEP":
            jobs[current].append(row["step_name"])
    return jobs


def test_ifflow_every_line_of_the_jcl_fits_columns_1_to_72():
    for n, ln in enumerate((FIXTURE / "IFFLOW.jcl").read_text(encoding="utf-8").splitlines(), 1):
        assert len(ln) <= 72, (n, ln)


def test_ifflow_scenarios_cite_a_basis_and_use_valid_outcomes():
    jobs = _if_steps_by_job()
    assert IF_DOC["issue"] == 8413
    ids = [s["id"] for s in IF_DOC["scenarios"]]
    assert len(ids) == len(set(ids)) == 28
    assert {s["job"] for s in IF_DOC["scenarios"]} == {"NESTJOB", "ABNJOB", "NOTJOB", "PRC5JOB", "PRC6JOB", "MIXJOB"}
    for sc in IF_DOC["scenarios"]:
        assert sc["basis"], sc["id"]
        assert set(sc["expect"].values()) <= {"run", "bypass"}, sc["id"]
        assert set(sc["given"]) == {n for n, a in sc["expect"].items() if a == "run"}, sc["id"]
        for given in sc["given"].values():
            assert (list(given) == ["rc"] and 0 <= given["rc"] <= 4095) or (
                list(given) == ["abend"] and re.fullmatch(r"S[0-9A-F]{3}|U\d{4}", given["abend"])
            ), (sc["id"], given)
        if not sc["job"].startswith("PRC"):
            assert list(sc["expect"]) == jobs[sc["job"]], sc["id"]
    assert [a["id"] for a in IF_DOC["assumed"]] == ["B1", "B2"]
    assert len(IF_DOC["refused"]) == 6


def test_ifflow_reader_nests_if_and_else_into_each_steps_condition():
    ifs = {r["step_name"]: r["if_cond"] for r in IF_FLOW if r["kind"] == "STEP"}
    assert ifs["N1"] is None
    assert all(ifs[s] for s in ("A2", "A4", "A5", "A6", "A7", "T2", "M3", "M4", "M5"))
    assert ifs["A4"].startswith("NOT ")  # ELSE of the first IF
    assert " AND " in ifs["A6"]  # ELSE of the second IF, then the nested IF


def test_ifflow_the_flat_reader_rows_do_not_expand_a_proc_call():
    # The reader alone lists a PROC definition's steps at top level; `jcl_proc.expand_flow_rows` makes them CALL.PROCSTEP.
    seen = {r["step_name"] for r in IF_FLOW if r["kind"] == "STEP"}
    for sc in IF_DOC["scenarios"]:
        if sc["job"].startswith("PRC"):
            assert not set(sc["given"]) <= seen, sc["id"]


def test_ifflow_the_evaluator_matches_every_ibm_answer():
    from gitgalaxy.core.jcl_flow import JclFlow
    from gitgalaxy.core.jcl_proc import expand_flow_rows

    for sc in IF_DOC["scenarios"]:
        rows = expand_flow_rows(IF_FLOW, sc["job"]) if sc["job"].startswith("PRC") else IF_FLOW
        assert JclFlow(rows).run(sc["job"], sc["given"]).actions == sc["expect"], sc["id"]


def test_ifflow_an_if_construct_is_evaluated_once():
    # IBM Example 9: ABNJOB's first IF is true at A2; A2 then abends, A3 still runs and the ELSE step A4 stays bypassed.
    chain = {r["step_name"]: r.get("if_chain") for r in IF_FLOW if r["kind"] == "STEP"}
    assert chain["N1"] is None
    assert chain["A2"][0][0] == chain["A3"][0][0] == chain["A4"][0][0]
    assert [c[2] for c in (chain["A2"][0], chain["A4"][0])] == [False, True]
    assert chain["A6"][1][2] is False and chain["A6"][0][2] is True  # nested IF inside an ELSE
