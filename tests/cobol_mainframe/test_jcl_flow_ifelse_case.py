"""#8413 slice 1: IBM-written answers for IF / THEN / ELSE / ENDIF step flow.

`tests/equivalence/jcl/ifelse/` holds FLOW.jcl (four jobs: nested IFs, ABEND / ABENDCC, an IF around a PROC step, IF
with a grouped AND / OR) and scenarios.json. The answers were written from IBM's z/OS MVS JCL Reference (SA23-1385)
BEFORE `gitgalaxy.core.jcl_flow` ran on them; each scenario's `basis` names the rule, and anything the manual does
not state is an ASSUMED entry. The last test reproduces every `expect` with the evaluator.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "tests" / "equivalence" / "jcl" / "ifelse"
DOC = json.loads((CASE / "scenarios.json").read_text(encoding="utf-8"))
FLOW = job_flow.jcl_job_flow((CASE / "FLOW.jcl").read_text(encoding="latin-1"))


def _steps_by_job() -> dict[str, list[dict]]:
    jobs: dict[str, list[dict]] = {}
    for row in FLOW:
        if row["kind"] == "JOB":
            jobs[row["name"]] = []
            current = row["name"]
        elif row["kind"] == "STEP":
            jobs[current].append(row)
    return jobs


def test_every_line_of_the_jcl_fits_columns_1_to_72():
    for n, ln in enumerate((CASE / "FLOW.jcl").read_text(encoding="latin-1").splitlines(), 1):
        assert len(ln) <= 72, (n, ln)


def test_the_reader_sees_the_four_jobs_and_their_steps_in_order():
    names = {j: [s["step_name"] for s in steps] for j, steps in _steps_by_job().items()}
    assert names == {
        "NESTJOB": ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"],
        "ABNJOB": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"],
        "PRCJOB": ["B1", "B2", "B3", "B4"],
        "CMBJOB": ["C1", "C2", "C3", "C4", "C6", "C5", "C7"],
    }


def test_the_reader_attaches_each_nested_if_and_else_clause_to_its_step():
    ifs = {s["step_name"]: s["if_cond"] for steps in _steps_by_job().values() for s in steps}
    assert ifs["N3"] == "(N1.RC <= 4)"
    assert ifs["N4"] == "(N1.RC <= 4) AND (N3.RC = 0)"
    assert ifs["N5"] == "(N1.RC <= 4) AND NOT (N3.RC = 0)"
    assert ifs["N6"] == "NOT (N1.RC <= 4)"
    assert ifs["A4"] == "NOT (ABEND = TRUE)"
    assert ifs["C3"] == "((C1.RC = 0 & C2.RC = 0) | C1.RC = 4)"


def test_the_if_around_a_proc_call_and_the_cond_steps_are_read_as_written():
    steps = {s["step_name"]: s for steps in _steps_by_job().values() for s in steps}
    assert steps["B2"]["proc"] == "MYPROC" and steps["B2"]["if_cond"] == "(B1.RC = 0)"
    assert [steps[n]["cond"] for n in ("A8", "A9", "B4", "C5", "C7")] == ["EVEN", "ONLY", "EVEN", "(8,LE)", "ONLY"]


def test_each_scenario_answers_every_step_of_its_job_and_gives_input_only_to_steps_that_start():
    jobs = _steps_by_job()
    ids = [s["id"] for s in DOC["scenarios"]]
    assert len(ids) == len(set(ids))
    for sc in DOC["scenarios"]:
        assert list(sc["expect"]) == [s["step_name"] for s in jobs[sc["job"]]], sc["id"]
        assert set(sc["expect"].values()) <= {"run", "bypass"}, sc["id"]
        assert set(sc["given"]) == {n for n, a in sc["expect"].items() if a == "run"}, sc["id"]
        for given in sc["given"].values():
            assert (list(given) == ["rc"] and 0 <= given["rc"] <= 4095) or (
                list(given) == ["abend"] and re.fullmatch(r"S[0-9A-F]{3}|U\d{4}", given["abend"])
            ), (sc["id"], given)
        assert sc["basis"], sc["id"]


def test_the_scenarios_reach_both_branches_of_every_if_clause_and_the_cond_steps():
    for job, steps in (
        ("NESTJOB", "N3 N4 N5 N6 N7 N8"),
        ("ABNJOB", "A3 A4 A5 A6 A7 A9"),
        ("PRCJOB", "B2 B3"),
        ("CMBJOB", "C3 C4 C5 C6 C7"),
    ):
        for step in steps.split():
            seen = {s["expect"][step] for s in DOC["scenarios"] if s["job"] == job}
            assert seen == {"run", "bypass"}, step
    assert {s["expect"]["A8"] for s in DOC["scenarios"] if s["job"] == "ABNJOB"} == {"run"}  # EVEN always runs here


def test_what_the_manual_does_not_state_is_assumed_or_refused_by_name():
    assert [a["id"] for a in DOC["assumed"]] == ["A3", "A5", "A6"]
    refused = " ".join(r["construct"] for r in DOC["refused"])
    for name in ("procstepname", "bare ABEND", "ABENDCC compared", "AND and OR mixed"):
        assert name in refused, name


def test_the_flow_evaluator_reproduces_every_scenario():
    flow = JclFlow(FLOW)
    for sc in DOC["scenarios"]:
        assert flow.run(sc["job"], sc["given"]).actions == sc["expect"], sc["id"]
