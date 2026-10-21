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


EOF_LOOP_CASES = {  # case: (flag, the loop's `PERFORM UNTIL` line)
    "carddemo-readcard": ("END-OF-FILE", 74),
    "carddemo-readxref": ("END-OF-FILE", 74),
    "carddemo-readcust": ("END-OF-FILE", 74),
    "carddemo-intcalc": ("END-OF-FILE", 188),
    "carddemo-posttran": ("END-OF-FILE", 202),
    "carddemo-trnrpt": ("END-OF-FILE", 170),
    "carddemo-dailyval": ("END-OF-DAILY-TRANS-FILE", 164),
}


def test_carddemo_batch_read_loop_guard_is_the_only_outcome_the_proof_leaves():
    """#5864: the CardDemo batch programs' `IF flag = 'N'` inside `PERFORM UNTIL flag = 'Y'` has no false outcome; it is
    the one outcome their committed proofs leave uncovered, and each entry takes exactly it out of the branch total."""
    ledger = io.load()
    for case, (flag, until) in EOF_LOOP_CASES.items():
        (e,) = ledger[case]
        assert (e["line"], e["kind"], e["outcome"], e["family"]) == (until + 1, "IF", "false", "C")
        assert flag in e["reason"] and f"line {until}" in e["reason"]
        record = json.loads((io.CASES / case / "evidence.json").read_text(encoding="utf-8"))["coverage"]
        assert [(b["line"], b["kind"], b["outcome"]) for b in record["uncovered_branches"]] == [
            (e["line"], "IF", "false")
        ]
        covered, total = record["branches"]["covered"], record["branches"]["total"]
        assert io.adjust(case, (1, 1, covered, total), record["uncovered_branches"], ledger)[0] == (
            1,
            1,
            covered,
            total - 1,
        )
