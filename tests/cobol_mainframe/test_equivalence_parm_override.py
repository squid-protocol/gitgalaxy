"""#5561: a batch run may carry its own PARM (a `faults` entry with `parm`, and no plan): the COBOL driver, the Java
test's system property and the fired-fault check all follow it. A run with only a PARM plans no fault, so
none having fired is not a failure; a run that plans one still must fire it."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_java as ej  # noqa: E402

CASE = {"name": "c", "program": "P", "parm": "1,3,1,7", "datasets": {}}


def test_a_run_gets_its_own_parm_else_the_cases():
    assert eq.run_parm(CASE) == "1,3,1,7"
    assert eq.run_parm(CASE, {"name": "f", "plan": []}) == "1,3,1,7"
    assert eq.run_parm(CASE, {"name": "f", "parm": "5,1,1,7"}) == "5,1,1,7"
    assert eq.run_parm({"name": "c", "program": "P"}, {"name": "f", "parm": "A"}) == "A"
    assert eq.run_parm({"name": "c", "program": "P"}) is None


def test_the_cobol_driver_passes_the_runs_parm_in_a_halfword_prefixed_area():
    text = eq.cobol_driver("P", eq.run_parm(CASE, {"name": "f", "parm": "5,1,1,7"}))
    assert "VALUE 7." in text and "VALUE '5,1,1,7'" in text and "USING JCL-PARM" in text
    assert "JCL-PARM" not in eq.cobol_driver("P", None)


def test_an_entry_case_cannot_override_the_parm():
    with pytest.raises(SystemExit):
        eq.run_parm({**CASE, "entries": [{"method": "executeP"}]}, {"name": "f", "parm": "x"})


@pytest.mark.parametrize("parm", ["a b", "a'b", 'a"b', "a\\b", ""])
def test_a_parm_that_cannot_travel_in_the_jvm_argline_is_refused(parm):
    with pytest.raises(ValueError):
        ej.run_parm(parm)
    assert ej.run_parm("1,1002,1,0000000000000007") == "1,1002,1,0000000000000007"


def test_the_java_test_reads_the_runs_parm_over_the_cases():
    case = {"name": "c", "program": "P", "parm": "1,3,1,7", "clock": "2026/10/01 10:30:15.00", "datasets": {}}
    assert 'System.getProperty("equivalence.parm", "1,3,1,7")' in ej.equivalence_test(case)
    case.pop("parm")
    assert 'System.getProperty("equivalence.parm")' in ej.equivalence_test(case)


def _run(fired_cobol, fired_java, fault):
    out = {"RETURN-CODE": b"12"}
    return eq.compare_run(
        {"name": "c", "datasets": {}},
        Path("."),
        {**out, "FAULTS": fired_cobol},
        {**out, "FAULTS": fired_java},
        fault=fault,
    )


def test_a_parm_only_run_needs_no_fault_to_fire_but_a_planned_fault_does():
    assert _run(b"", b"", {"name": "p", "parm": "5,1,1,7"})["ok"]
    planned = {"name": "p", "plan": [{"dd": "X", "op": "READ", "status": "23"}]}
    assert "never fired" in _run(b"", b"", planned)["summary"]
    assert _run(b"X READ 1 23\n", b"X READ 1 23\n", planned)["ok"]
    assert "faults fired differ" in _run(b"X READ 1 23\n", b"", {"name": "p", "parm": "x"})["summary"]
