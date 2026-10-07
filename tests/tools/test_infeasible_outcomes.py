"""#4602: the reviewed ledger of branch outcomes no input can reach (tests/tools/infeasible_outcomes.py)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import infeasible_outcomes as io

E = {"unit": "P", "line": 9, "kind": "IF", "outcome": "true", "family": "G", "reason": "every caller sets it first"}


def test_adjust_takes_out_only_what_the_proof_left_uncovered():
    ledger = {"c": [E]}
    assert io.adjust("c", (3, 3, 4, 5), [{"line": 9, "outcome": "true"}], ledger) == ((3, 3, 4, 4), ["P:9:true"], [])
    assert io.adjust("c", (3, 3, 5, 5), [], ledger) == ((3, 3, 5, 5), [], ["P:9:true"])  # reached: refuted
    assert io.adjust("c", (3, 3, 4, 5), None, ledger) == ((3, 3, 4, 4), ["P:9:true"], [])  # counts only
    assert io.adjust("other", (3, 3, 4, 5), [], ledger) == ((3, 3, 4, 5), [], [])


def test_a_sweep_that_reaches_a_stated_outcome_fails():
    ledger = {"c": [E]}
    ok = {"c": {"proved": True, "uncovered": ["9:true", "12:false"]}}
    bad = {"c": {"proved": True, "uncovered": ["12:false"]}}
    assert io.check(ok, ledger)[0] == []
    problems = io.check(bad, ledger)[0]
    assert len(problems) == 1 and "P:9:true" in problems[0] and "reached" in problems[0]
    assert io.check({"c": {"proved": True}}, ledger)[1]  # no list kept: a warning, never a pass in silence


def test_the_committed_ledger_is_well_formed():
    assert io.problems_in(io.load()) == []
    for case, entries in io.load().items():
        assert entries, case
        for e in entries:
            assert len(e["reason"]) > 40, f"{case} {io.key(e)}: say why no input reaches it, citing the COBOL"


def test_stated_is_what_a_report_shows(tmp_path):
    f = tmp_path / "l.json"
    f.write_text(json.dumps({"format": io.FORMAT, "cases": {"c": [E]}}))
    assert io.stated("c", f) == [dict(E, key="P:9:true")]
    assert io.stated("nope", f) == []
