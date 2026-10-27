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
    f = tmp_path / "l"
    io.write_case("c", [E], f)
    assert io.stated("c", f) == [dict(E, key="P:9:true")]
    assert io.stated("nope", f) == []


def test_the_ledger_is_tracked():
    """A *.json ignore rule once kept a ledger out of a commit (#4606): this one must be in git."""
    import subprocess

    out = subprocess.run(["git", "ls-files", "--error-unmatch", str(io.LEDGER)], cwd=io.REPO, capture_output=True)
    assert out.returncode == 0, "tests/equivalence/infeasible_outcomes/ is not tracked: see .gitignore"
    for case in ("carddemo-cardlist", "cbsa-bnk1cra"):  # a *.json ignore rule hides a file only per file
        f = io.LEDGER / f"{case}.json"
        assert (
            subprocess.run(["git", "ls-files", "--error-unmatch", str(f)], cwd=io.REPO, capture_output=True).returncode
            == 0
        )


def test_the_old_single_file_is_gone_and_each_case_has_its_own_sorted_file():
    assert not (
        io.CASES / "infeasible_outcomes.json"
    ).exists()  # a rebased branch re-adding it would double the entries
    files = sorted(io.LEDGER.glob("*.json"))
    assert len(files) == len(io.load()) >= 47
    for f in files:
        body = json.loads(f.read_text(encoding="utf-8"))
        assert (body["format"], body["case"]) == (io.FORMAT, f.stem)
        assert body["entries"] == sorted(body["entries"], key=io.sort_key)
        assert f.read_text(encoding="utf-8") == json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def test_load_reads_a_directory_and_the_old_single_file(tmp_path):
    io.write_case("c", [E], tmp_path / "infeasible_outcomes")
    (tmp_path / "infeasible_outcomes.json").write_text(json.dumps({"cases": {"old": [E]}}))
    assert io.load(tmp_path / "infeasible_outcomes") == {"c": [E], "old": [E]}
    assert io.load(tmp_path / "nothing") == {}


PARA = {"unit": "6000-EXIT", "kind": "PARAGRAPH", "outcome": "entered", "family": "G", "reason": "no caller gets here"}


def test_a_paragraph_entry_leaves_the_live_paragraph_total_when_the_proof_left_it():
    ledger = {"c": [PARA, E]}
    unc = ["9:true", "paragraph:6000-EXIT", "paragraph:OTHER-PARA"]
    assert io.key(PARA) == "6000-EXIT:paragraph"
    assert io.adjust("c", (15, 16, 3, 4), unc, ledger) == ((15, 15, 3, 3), ["6000-EXIT:paragraph", "P:9:true"], [])
    assert io.adjust("c", (15, 16, 3, 4), [{"name": "6000-EXIT", "line": 348}], ledger)[1:] == (
        ["6000-EXIT:paragraph"],
        ["P:9:true"],
    )
    assert io.adjust("c", (16, 16, 4, 4), [], ledger)[2] == ["6000-EXIT:paragraph", "P:9:true"]  # reached: refuted
    assert io.adjust("c", (15, 16, 3, 4), None, ledger)[0] == (15, 15, 3, 3)  # counts only: every entry taken
    assert io.outcome_set(unc) == {(9, "true")} and io.paragraph_set(unc) == {"6000-EXIT", "OTHER-PARA"}


def test_a_sweep_that_entered_a_stated_paragraph_fails():
    ledger = {"c": [PARA]}
    assert io.check({"c": {"proved": True, "uncovered": ["paragraph:6000-EXIT"]}}, ledger)[0] == []
    (problem,) = io.check({"c": {"proved": True, "uncovered": ["12:false"]}}, ledger)[0]
    assert "6000-EXIT:paragraph" in problem and "reached" in problem


def test_uncovered_of_lists_branch_outcomes_then_paragraphs():
    cov = {
        "branches": {"uncovered": [{"line": 340, "outcome": "true"}]},
        "paragraphs": {"uncovered": [{"name": "X", "line": 3}]},
    }
    assert io.uncovered_of(cov) == ["340:true", "paragraph:X"]
    assert io.uncovered_of({"branches": {"uncovered": []}}) == []


def _case(tmp_path, name="c"):
    d = tmp_path / "cases" / name
    d.mkdir(parents=True)
    (d / "case.json").write_text("{}")
    (d / "evidence.json").write_text(json.dumps({"coverage": {"uncovered_branches": [
        {"line": 9, "kind": "IF", "outcome": "true", "unit": "P"}]}}))  # fmt: skip
    return tmp_path / "cases", tmp_path / "out"


def test_add_writes_sorted_entries_and_takes_unit_and_kind_from_the_evidence(tmp_path):
    cases, out = _case(tmp_path)
    kw = {"family": "G", "reason": "every caller set it first", "cases_dir": cases, "directory": out}
    io.add("c", paragraph="Z-EXIT", **kw)
    e = io.add("c", line=9, arm="true", **kw)
    assert (e["unit"], e["kind"]) == ("P", "IF")
    assert io.add("c", line=4, arm="false", unit="Q", kind="EVALUATE", **kw)["unit"] == "Q"
    assert [x["unit"] for x in io.load(out)["c"]] == ["Z-EXIT", "Q", "P"]  # line-less first, then by line
    assert io.problems_in(io.load(out), cases) == []


def test_add_refuses_a_duplicate_an_unknown_case_a_missing_unit_and_a_bad_family(tmp_path):
    import pytest

    cases, out = _case(tmp_path)
    kw = {"family": "G", "reason": "r", "cases_dir": cases, "directory": out}
    io.add("c", paragraph="X", **kw)
    with pytest.raises(ValueError, match="listed twice"):
        io.add("c", paragraph="X", **kw)
    with pytest.raises(ValueError, match="no such case"):
        io.add("nope", paragraph="X", **kw)
    with pytest.raises(ValueError, match="--unit and --kind"):
        io.add("c", line=77, arm="true", **kw)
    with pytest.raises(ValueError, match="--paragraph NAME"):
        io.add("c", **kw)
    with pytest.raises(ValueError, match="unknown family"):
        io.add("c", paragraph="Y", **{**kw, "family": "Z"})
    assert [x["unit"] for x in io.load(out)["c"]] == ["X"]  # nothing half-written


def test_the_planner_proves_the_case_whose_file_changed():
    import det_sweep_plan as plan

    cases = {"alpha": {}, "beta": {}}
    p = plan.plan(["tests/equivalence/infeasible_outcomes/beta.json"], "pull_request", cases)
    assert (p["mode"], p["cases"]) == ("narrow", ["beta"])
    p = plan.plan(["tests/equivalence/infeasible_outcomes/ghost.json"], "pull_request", cases)
    assert p["mode"] == "full"  # a file of no case: when in doubt, full


def test_genapp_vsam_no_commarea_outcomes_are_stated_where_the_proof_leaves_only_them():
    """#5252: lgacvs01 / lgdpvs01 / lgucvs01 / lgapvs01 / lgupvs01 leave only WRITE-ERROR-MESSAGE's `IF EIBCALEN > 0` false (a COMMAREA-less call, X23)."""
    ledger = io.load()
    for case, line in (("genapp-lgacvs01", 106), ("genapp-lgdpvs01", 117), ("genapp-lgucvs01", 121)):
        (e,) = ledger[case]
        assert (e["unit"], e["line"], e["kind"], e["outcome"]) == ("WRITE-ERROR-MESSAGE", line, "IF", "false")
        assert "X23" in e["reason"] and "LENGTH(" in e["reason"]
        uncovered = [{"line": line, "outcome": "false"}]
        assert io.adjust(case, (3, 3, 3, 4), uncovered, ledger)[0] == (3, 3, 3, 3)
    for case, line in (("genapp-lgapvs01", 173), ("genapp-lgupvs01", 191)):
        (e,) = ledger[case]
        assert (e["unit"], e["line"], e["kind"], e["outcome"]) == ("WRITE-ERROR-MESSAGE", line, "IF", "false")
        assert "X23" in e["reason"] and "LENGTH(" in e["reason"]
        uncovered = [{"line": line, "outcome": "false"}]
        assert io.adjust(case, (3, 3, 8, 9), uncovered, ledger)[0] == (3, 3, 8, 8)


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


def test_carddemo_menu_admin_only_guard_and_readacct_loop_guard_are_stated():
    """#5864: COMEN01C's `IF CDEMO-USRTYP-USER AND ... USRTYPE(WS-OPTION) = 'A'` never sees an 'A' (all 11 COMEN02Y options
    are 'U'); it is the one outcome the committed proof leaves besides the three entries already stated. CBACT01C's
    read-loop guard (`IF END-OF-FILE = 'N'` inside `PERFORM UNTIL END-OF-FILE = 'Y'`) is the one outcome its proof
    leaves (43/44 with the debit-bearing account 51 and the first-VB-write fault, tests/equivalence/carddemo-readacct)."""
    ledger = io.load()
    (e,) = [x for x in ledger["carddemo-menu"] if x["line"] == 136]
    assert (e["unit"], e["kind"], e["outcome"], e["family"]) == ("PROCESS-ENTER-KEY", "IF", "true", "C")
    assert "VALUE 'U'" in e["reason"] and "COMEN02Y" in e["reason"]
    record = json.loads((io.CASES / "carddemo-menu" / "evidence.json").read_text(encoding="utf-8"))["coverage"]
    left = {(b["line"], b["kind"], b["outcome"]) for b in record["uncovered_branches"]}
    assert (136, "IF", "true") in left
    covered, total = record["branches"]["covered"], record["branches"]["total"]
    assert io.adjust("carddemo-menu", (1, 1, covered, total), record["uncovered_branches"], ledger)[0] == (
        1,
        1,
        covered,
        covered,
    )  # 29/29 net
    (r,) = ledger["carddemo-readacct"]
    assert (r["line"], r["kind"], r["outcome"], r["family"]) == (148, "IF", "false", "C")
    assert "END-OF-FILE" in r["reason"] and "line 147" in r["reason"]
    case = json.loads((io.CASES / "carddemo-readacct" / "case.json").read_text(encoding="utf-8"))
    assert case["datasets"]["ACCTFILE"]["input"] == "@case/acctdata.txt"
    assert any(f["name"] == "vbrcfile-first-write-error" for f in case["faults"])
    rows = (io.CASES / "carddemo-readacct" / "acctdata.txt").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 51 and rows[-1][:11] == "00000000051"
    assert (
        rows[-1][90:102] != "00000000000{"
    )  # the nonzero ACCT-CURR-CYC-DEBIT 1300-POPUL-ACCT-RECORD's false arm needs


def test_cbsa_delacc_and_bankdata_state_the_one_outcome_their_proof_leaves():
    """#5864: DELACC's `IF SQLCODE = 0` (line 363) never sees another SQLCODE (+100 jumped, anything else abended); BANKDATA's
    100-failed-draws arm (line 917) is a probability near zero. Each is the one outcome the det sweep left (13/14, 47/48)."""
    ledger = io.load()
    for case, line, outcome, family, total in (
        ("cbsa-delacc", 363, "false", "G", 14),
        ("cbsa-bankdata", 917, "true", "C", 48),
    ):
        (e,) = ledger[case]
        assert (e["line"], e["kind"], e["outcome"], e["family"]) == (line, "IF", outcome, family)
        uncovered = [{"line": line, "outcome": outcome}]
        assert io.adjust(case, (1, 1, total - 1, total), uncovered, ledger)[0] == (1, 1, total - 1, total - 1)
    assert "RAD999" in ledger["cbsa-delacc"][0]["reason"] and "HRAC" in ledger["cbsa-delacc"][0]["reason"]
    assert "2014" in ledger["cbsa-bankdata"][0]["reason"] and "1900" in ledger["cbsa-bankdata"][0]["reason"]


def test_cbsa_custctrl_reaches_the_sysiderr_retry_with_a_scenario():
    """#5864: CUSTCTRL's SYSIDERR retry (l.171) was the one outcome unreached (3/4); a first-READ SYSIDERR now covers it (4/4)."""
    case = json.loads((io.CASES / "cbsa-custctrl" / "case.json").read_text(encoding="utf-8"))
    (s,) = [x for x in case["scenarios"] if x["name"] == "read-sysiderr-retried"]
    assert [(f["cmd"], f["resp"], f["nth"]) for f in s["faults"]] == [("READ", "SYSIDERR", 1)]
    assert "is not reached: SYSIDERR is not an injectable" not in case["notes"]
    assert "cbsa-custctrl" not in io.load()


def test_cobtupdt_open_guard_and_sqlcode_evaluates_are_stated_for_both_cases():
    """#4507: COBTUPDT's proofs leave 16/20 branches; the four others are the OPEN status guard (84) and the three
    `EVALUATE TRUE` that name no positive SQLCODE but +100 (151 insert, 177 update, 207 delete), stated on both cases."""
    ledger = io.load()
    want = [
        ("0001-OPEN-FILES", 84, "IF", "false", "G"),
        ("10031-INSERT-DB", 151, "EVALUATE", "none", "R"),
        ("10032-UPDATE-DB", 177, "EVALUATE", "none", "R"),
        ("10033-DELETE-DB", 207, "EVALUATE", "none", "R"),
    ]
    for case in ("carddemo-cobtupdt", "carddemo-cobtupdt-generated"):
        assert [(e["unit"], e["line"], e["kind"], e["outcome"], e["family"]) for e in ledger[case]] == want
        assert all(e["reason"] for e in ledger[case])
        uncovered = [{"line": line, "kind": kind, "outcome": outcome} for _, line, kind, outcome, _ in want]
        assert io.adjust(case, (9, 9, 16, 20), uncovered, ledger)[0] == (9, 9, 16, 16)
