"""#4891: the JclFlow evaluator (gitgalaxy/core/jcl_flow.py) beyond the fixture's 14 scenarios: the rules it refuses by name,
the COND / IF forms it reads, and the contract on `given`."""

from __future__ import annotations

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_flow import JclFlow, JclFlowRefused, StepResult, _Run, evaluate_if, parse_cond


def _flow(jcl: str) -> JclFlow:
    return JclFlow(job_flow.jcl_job_flow(jcl))


def _state(**steps) -> _Run:
    run = _Run()
    for name, (rc, abend) in steps.items():
        run.out[name] = StepResult(name, "run", rc=rc, abend=abend)
    return run


def test_parse_cond_reads_every_form_the_fixture_uses():
    assert parse_cond(None) == ([], False, False)
    assert parse_cond("(4,LT,S1)") == ([(4, "<", "S1")], False, False)
    assert parse_cond("(4,GT)") == ([(4, ">", None)], False, False)
    assert parse_cond("EVEN") == ([], True, False)
    assert parse_cond("((8,LE,S1),(0,NE,S2))")[0] == [(8, "<=", "S1"), (0, "!=", "S2")]
    assert parse_cond("((4,LT,T1),ONLY)") == ([(4, "<", "T1")], False, True)


@pytest.mark.parametrize(
    "cond",
    ["(4,LT,P.S1)", "(" + ",".join(["(1,EQ,A)"] * 9) + ")", "(" + ",".join(["(1,EQ,A)"] * 8) + ",EVEN)", "(x,LT)"],
)
def test_cond_that_is_invalid_or_unsettled_is_refused_by_name(cond):
    with pytest.raises(JclFlowRefused):
        parse_cond(cond)


def test_a_cond_with_eight_tests_is_valid_without_even_or_only():
    assert len(parse_cond("(" + ",".join(["(1,EQ,A)"] * 8) + ")")[0]) == 8


def test_if_operators_in_every_spelling():
    run = _state(A=(4, None))
    for expr, want in [
        ("A.RC = 4", True),
        ("A.RC EQ 4", True),
        ("A.RC NE 4", False),
        ("A.RC ¬= 4", False),
        ("A.RC GE 5", False),
        ("A.RC LE 4", True),
        ("A.RC NG 3", False),
        ("A.RC NL 4", True),
        ("RC < 5", True),
        ("A.RC > 3 & RC < 5", True),
        ("A.RC > 3 AND RC < 4", False),
        ("NOT (A.RC = 4)", False),
        ("(A.RC = 0 | A.RC = 4) AND (RC = 4)", True),
        ("A.RUN = TRUE", True),
        ("B.RUN = FALSE", True),
        ("B.RC = 0", False),
        ("B.ABEND = FALSE", False),
        ("ABEND = FALSE", True),
    ]:
        assert evaluate_if(expr, run) is want, expr


def test_abend_and_abendcc_tests():
    run = _state(A=(None, "S0C7"), B=(0, None))
    assert evaluate_if("ABEND = TRUE", run)
    assert evaluate_if("A.ABEND = TRUE", run)
    assert evaluate_if("B.ABEND = FALSE", run)
    assert evaluate_if("ABENDCC = S0C7", run)
    assert not evaluate_if("ABENDCC = U0001", run)
    assert not evaluate_if("B.ABENDCC = S0C7", run)
    assert not evaluate_if("A.RC = 0", run)  # an abended step has no RC


@pytest.mark.parametrize(
    "expr",
    ["A.RC = 0 & B.RC = 0 | RC = 4", "ABEND", "RC = 0", "A.RC", "A.RC ?? 0", "A.ABENDCC > S000", "RUN = TRUE"],
)
def test_what_ibm_does_not_settle_is_refused_by_name(expr):
    with pytest.raises(JclFlowRefused):
        evaluate_if(expr, _Run() if expr.startswith("RC") else _state(A=(0, None)))


def test_rc_with_no_stepname_is_the_highest_so_far_and_ignores_an_abended_step():
    run = _state(A=(3, None), B=(None, "S0C4"), C=(9, None))
    assert evaluate_if("RC = 9", run)
    assert not evaluate_if("RC < 9", run)


def test_given_must_match_the_steps_that_start():
    flow = _flow("//J JOB (A)\n//A EXEC PGM=X\n//B EXEC PGM=Y,COND=(0,EQ,A)\n")
    assert flow.run("J", {"A": {"rc": 1}, "B": {"rc": 0}}).actions == {"A": "run", "B": "run"}
    assert flow.run("J", {"A": {"rc": 0}}).actions == {"A": "run", "B": "bypass"}
    with pytest.raises(KeyError):
        flow.run("J", {"A": {"rc": 1}})
    with pytest.raises(KeyError):
        flow.run("J", {"A": {"rc": 0}, "B": {"rc": 0}})


def test_highest_rc_ignores_bypassed_and_abended_steps():
    flow = _flow("//J JOB (A)\n//A EXEC PGM=X\n//B EXEC PGM=Y\n//C EXEC PGM=Z,COND=EVEN\n")
    res = flow.run("J", {"A": {"rc": 4}, "B": {"abend": "S806"}, "C": {"rc": 8}})
    assert res.highest_rc == 8
    assert res.steps["B"].abend == "S806" and res.steps["B"].rc is None
