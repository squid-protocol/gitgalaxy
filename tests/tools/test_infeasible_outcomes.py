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


def test_the_ledger_is_tracked():
    """A *.json ignore rule once kept a ledger out of a commit (#4606): this one must be in git."""
    import subprocess

    out = subprocess.run(["git", "ls-files", "--error-unmatch", str(io.LEDGER)], cwd=io.REPO, capture_output=True)
    assert out.returncode == 0, "tests/equivalence/infeasible_outcomes.json is not tracked: see .gitignore"


def test_genapp_vsam_no_commarea_outcomes_are_stated_where_the_proof_leaves_only_them():
    """#5252: lgacvs01 / lgdpvs01 / lgucvs01 leave only WRITE-ERROR-MESSAGE's `IF EIBCALEN > 0` false (a COMMAREA-less call, X23)."""
    ledger = io.load()
    for case, line in (("genapp-lgacvs01", 106), ("genapp-lgdpvs01", 117), ("genapp-lgucvs01", 121)):
        (e,) = ledger[case]
        assert (e["unit"], e["line"], e["kind"], e["outcome"]) == ("WRITE-ERROR-MESSAGE", line, "IF", "false")
        assert "X23" in e["reason"] and "LENGTH(" in e["reason"]
        uncovered = [{"line": line, "outcome": "false"}]
        assert io.adjust(case, (3, 3, 3, 4), uncovered, ledger)[0] == (3, 3, 3, 3)


def test_genapp_lgdpvs01_proof_stops_at_the_first_link_of_write_error_message():
    """#5252: lgdpvs01's 102-byte ERROR-MSG already overruns LGSTSQ's 95-byte WRITE-MSG (X6), so lines 117-118 are never reached."""
    (e,) = io.load()["genapp-lgdpvs01"]
    assert "102-byte ERROR-MSG" in e["reason"] and "X6" in e["reason"]
