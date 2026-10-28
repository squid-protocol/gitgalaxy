"""#4049: the test-strengthening loop (tests/tools/strengthen.py). The pure parts: the model's answer parsed,
malformed proposals refused with the reason, a proposal turned into a case entry (the model's expected result is
never taken -- there is none), the prompt carrying the gaps and the oracle's limits, and the inputs a port fails."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import strengthen as st  # noqa: E402

CALL = {"name": "c", "kind": "call", "program": "P", "using": [{"name": "A", "size": 4}, {"name": "B", "size": 6}],
        "calls": [{"name": "one", "args": ["AB", "X"]}]}  # fmt: skip
CICS = {"name": "m", "kind": "cics", "program": "M",
        "scenarios": [{"name": "first", "aid": "DFHENTER", "commarea": {"CA-USER-TYPE": "U", "CA-CONTEXT": 0}}]}  # fmt: skip


def test_the_answer_is_one_json_array_of_proposals():
    text = 'Here:\n```json\n[{"name": "a", "args": ["x", "y"]}, "noise"]\n```\nthanks'
    assert st.parse(text) == [{"name": "a", "args": ["x", "y"]}]
    assert st.parse("no json here") == []


def test_malformed_proposals_are_refused_with_the_reason():
    taken = {"one"}
    assert st.validate(CALL, {"name": "two", "args": ["ABCD", "XYZ"]}, taken) is None
    assert "not a new" in st.validate(CALL, {"name": "one", "args": ["A", "B"]}, taken)
    assert "args must be 2" in st.validate(CALL, {"name": "two", "args": ["A"]}, taken)
    assert "at most 4" in st.validate(CALL, {"name": "two", "args": ["ABCDE", "X"]}, taken)
    assert st.validate(CICS, {"name": "admin", "aid": "DFHPF3", "commarea": {"CA-USER-TYPE": "A"}}, set()) is None
    assert "not in the existing" in st.validate(CICS, {"name": "x", "commarea": {"CA-SECRET": "1"}}, set())
    assert "DFH AID" in st.validate(CICS, {"name": "x", "aid": "ENTER"}, set())


def test_an_entry_keeps_the_input_and_never_an_expected_result():
    p = {"name": "two", "args": ["A", "B"], "expected": "Date is valid", "targets": ["A000-MAIN:128:WHEN@131"],
         "why": "reaches the first WHEN"}  # fmt: skip
    e = st.as_entry(CALL, p)
    assert set(e) == {"name", "args", "why"} and "expected" not in e
    assert e["why"].startswith("#4049 (proposed for A000-MAIN:128:WHEN@131)")


def test_the_prompt_carries_the_gaps_the_inputs_and_the_oracles_limits():
    src = [f"LINE {i}" for i in range(1, 200)]
    gaps = [{"unit": "A000-MAIN", "line": 128, "kind": "EVALUATE", "outcome": "WHEN@131"}]
    hints = [{"file": "S.java", "line": 9, "before": "a > 0", "after": "a >= 0"}]
    text = st.prompt(CALL, src, gaps, hints, ["- `x`: refused"], "CEEDAYS refuses month 13")
    assert "A000-MAIN:128:WHEN@131" in text and "  128 LINE 128" in text
    assert '"name": "one"' in text and "`a > 0` -> `a >= 0`" in text
    assert "CEEDAYS refuses month 13" in text and "`x`: refused" in text
    assert "Never an expected result" in text and "unreachable" in text


def test_the_inputs_a_port_fails_are_named():
    report = {"outputs": {"CALLS": {"diffs": [{"record": 1}]}}}
    assert st.failing_entries(CALL, report) == ["one"]
    cics = {"outputs": {"first": {"equal": 1, "records": 2, "diffs": [{}]}, "ok": {"equal": 1, "records": 1}}}
    assert st.failing_entries(CICS, cics) == ["first"]


# ---- batch cases: new records built from an existing one and its layout ----------------------------------------
BATCH = {"name": "b", "kind": "batch", "program": "B", "datasets": {}}
FIELDS = [{"name": "ACCT-ID", "offset": 0, "bytes": 4, "pic": "9(4)", "usage": None},
          {"name": "EXP-DATE", "offset": 4, "bytes": 10, "pic": "X(10)", "usage": None},
          {"name": "BAL", "offset": 14, "bytes": 3, "pic": "S9(5)", "usage": "COMP-3"}]  # fmt: skip
INPUTS = {"ACCT": {"fields": FIELDS, "records": [b"00012024-01-31\x00\x00\x0c", b"00022025-12-31\x00\x00\x0c"],
                   "spec": {"organization": "indexed", "keys": [{"offset": 0, "length": 4}]}}}  # fmt: skip


def test_a_new_record_is_an_existing_one_with_named_display_fields_changed():
    rec, bad = st.build_record(BATCH, INPUTS, {"dataset": "ACCT", "based_on": 2, "set": {"ACCT-ID": 7,
                                                                                         "EXP-DATE": "2025-01-31"}})  # fmt: skip
    assert bad is None and rec == b"00072025-01-31\x00\x00\x0c"  # BAL's bytes copied, untouched


def test_a_malformed_record_proposal_is_refused_with_the_reason():
    def why(p):
        return st.build_record(BATCH, INPUTS, p)[1]

    assert "not an input" in why({"dataset": "NOPE", "based_on": 1})
    assert "record number 1..2" in why({"dataset": "ACCT", "based_on": 3})
    assert "no field" in why({"dataset": "ACCT", "based_on": 1, "set": {"NAME": "X"}, "x": 1})
    assert "COMP-3" in why({"dataset": "ACCT", "based_on": 1, "set": {"BAL": 5}})  # keeps a text file text
    assert "already a record's" in why({"dataset": "ACCT", "based_on": 1, "set": {"EXP-DATE": "2026-01-01"}})


def test_a_value_with_more_decimals_than_its_picture_is_refused_not_rounded():
    fields = [{"name": "AMT", "offset": 0, "bytes": 5, "pic": "S9(3)V99", "usage": None}]
    inputs = {"T": {"fields": fields, "records": [b"0010{"], "spec": {}}}
    assert st.build_record(BATCH, inputs, {"dataset": "T", "based_on": 1, "set": {"AMT": "1.25"}})[1] is None
    assert "more decimals" in st.build_record(BATCH, inputs, {"dataset": "T", "based_on": 1, "set": {"AMT": 1.999}})[1]


# ---- #4049: survivor-driven rounds (--case-gaps) -------------------------------------------------------------
def test_the_case_gaps_are_the_survivors_the_committed_results_triaged_so(tmp_path):
    results = {"ports": [
        {"case": "c", "program": "P", "survivors": [{"id": "a1", "verdict": "case_gap"},
                                                     {"id": "b2", "verdict": "equivalent"}]},
        {"case": "crucible:x", "program": "Q", "survivors": [{"id": "c3", "verdict": "case_gap"}]},
        {"case": "crucible:x", "program": "R", "survivors": [{"id": "d4", "verdict": "case_gap"}]}]}  # fmt: skip
    f = tmp_path / "scores.json"
    f.write_text(st.json.dumps(results), encoding="utf-8")
    assert st.case_gaps(f, "c") == {"a1"}
    assert st.case_gaps(f, "crucible:x", "Q") == {"c3"}
    assert st.case_gaps(f, "nope") == set()


def test_a_cics_proposal_may_set_any_commarea_field_of_the_layout_and_plan_a_fault():
    names = {"CA-USER-TYPE", "CA-CONTEXT", "CA-LAST-MAP"}
    ok = {"name": "x", "aid": "DFHENTER", "commarea": {"CA-LAST-MAP": "M1"},
          "faults": [{"cmd": "XCTL", "program": "PROG1", "resp": "PGMIDERR", "resp2": 3}]}  # fmt: skip
    assert st.validate(CICS, ok, set(), names) is None
    assert "COMMAREA layout" in st.validate(CICS, {"name": "x", "commarea": {"CA-SECRET": "1"}}, set(), names)
    bad = {"name": "x", "faults": [{"cmd": "SEND", "program": "P", "resp": "PGMIDERR"}]}  # not a fault command
    assert "fault" in st.validate(CICS, bad, set(), names)


_FAULT_KEY = {"XCTL": "program", "LINK": "program", "WRITEQ-TS": "queue", "START": "transid", "CANCEL": "reqid",
              "ENQ": "resource", "SEND-MAP": "map", "RECEIVE-MAP": "map"}  # fmt: skip
_FAULT_RESP = {
    "ENQ": ("ENQBUSY", 0),
    "SEND-MAP": ("TSIOERR", 0),
    "RECEIVE-MAP": ("INVMPSZ", 0),
    "RETURN": ("INVREQ", 1),
    "SYNCPOINT": ("INVREQ", 200),
    "ROLLBACK": ("INVREQ", 200),
    "DELAY": ("INVREQ", 6),
    "SEND-TEXT": ("TSIOERR", 0),
    "SET-TERMINAL": ("INVREQ", 43),
    "INQ-TERMINAL": ("TERMIDERR", 1),
    "RUN-TRANSID": ("TRANSIDERR", 1),
    "FETCH-ANY": ("NOTFND", 1),
}  # #6271 (X71, X72)
_NAMELESS = (
    "RETRIEVE",
    "RETURN",
    "SYNCPOINT",
    "ROLLBACK",
    "DELAY",
    "SEND-TEXT",
    "SET-TERMINAL",
    "INQ-TERMINAL",
    "RUN-TRANSID",
    "FETCH-ANY",
)  # fault_lines names them "-"  # #5089 (X60): the one condition IBM lists for ENQ that a plan raises; no RESP2


def _fault_member_scenario(cmd):
    resp, resp2 = _FAULT_RESP.get(cmd, ("NOTAUTH", 101))
    plan = {"cmd": cmd, "resp": resp, **({"resp2": resp2} if resp2 else {})}
    if cmd not in _NAMELESS:
        plan[_FAULT_KEY.get(cmd, "file")] = "TARGET1"
    return {"name": "x", "faults": [plan]}


@pytest.mark.parametrize("cmd", st.eq_cics().FAULT_COMMANDS)
def test_the_strengthen_loop_plans_a_fault_for_every_fault_command(cmd):
    """Every FAULT_COMMANDS member the equivalence harness takes, the loop's validator accepts (#4648 added LINK)."""
    sc = _fault_member_scenario(cmd)
    ec = st.eq_cics()
    assert st.validate(CICS, sc, set(), set()) is None
    name = "-" if cmd in _NAMELESS else "TARGET1"
    resp, resp2 = _FAULT_RESP.get(cmd, ("NOTAUTH", 101))
    assert ec.fault_lines(sc) == [f"{cmd} {name} 1 {ec.CICS_RESP.get(resp) or ec.DFHRESP[resp]} {resp2}"]


@pytest.mark.parametrize("cmd", st.eq_cics().FAULT_COMMANDS)
def test_a_fault_plan_for_a_fault_command_still_needs_a_known_condition(cmd):
    sc = _fault_member_scenario(cmd)
    sc["faults"][0]["resp"] = "NOSUCHCOND"
    assert "fault" in st.validate(CICS, sc, set(), set())


def test_the_prompt_names_the_survivors_to_kill_by_id():
    src = [f"LINE {i}" for i in range(1, 50)]
    hints = [{"id": "abc123", "file": "S.java", "line": 9, "before": "a > 0", "after": "a >= 0"}]
    text = st.prompt(CALL, src, [], hints, [], "")
    assert "`abc123` S.java:9" in text and "targets" in text


def _scenarios(case):
    import json

    path = Path(__file__).resolve().parents[1] / "equivalence" / case / "case.json"
    return {s["name"]: s for s in json.loads(path.read_text(encoding="utf-8"))["scenarios"]}


def test_the_menu_case_carries_every_commarea_field_the_program_copies_through():
    sc = _scenarios("carddemo-menu")["carried-commarea-fields"]
    carried = {"CDEMO-TO-TRANID", "CDEMO-TO-PROGRAM", "CDEMO-CUST-LNAME", "CDEMO-ACCT-STATUS"}
    assert carried <= set(sc["commarea"]) and all(sc["commarea"][f].strip() for f in carried)
    assert sc["why"].startswith("#4049") and "expected" not in sc


def test_the_account_view_case_carries_fields_and_a_low_values_caller():
    scs = _scenarios("carddemo-acctview")
    carried = scs["carried-account-status"]["commarea"]
    assert all(carried[f].strip() for f in ("CDEMO-ACCT-STATUS", "CDEMO-TO-TRANID", "CDEMO-TO-PROGRAM"))
    low = scs["pf3-low-values-caller"]
    assert low["aid"] == "DFHPF3"
    assert set(low["commarea"]["CDEMO-FROM-TRANID"]) == set(low["commarea"]["CDEMO-FROM-PROGRAM"]) == {"\x00"}
    assert all(s["why"].startswith("#4049") for s in (scs["carried-account-status"], low))


def _gap_scenarios(case):
    return {n: s for n, s in _scenarios(case).items() if s.get("why", "").startswith("#4049")}


def test_the_menu_family_cases_take_the_blank_and_low_values_program_scenarios():
    for case, field, names in (
        ("carddemo-adminmenu", "CDEMO-TO-PROGRAM", ("pf3-blank-to-program", "pf3-low-values-to-program")),
        ("carddemo-useradd", "CDEMO-TO-PROGRAM", ("pf3-blank-to-program", "pf3-low-values-to-program")),
        ("carddemo-userdel", "CDEMO-TO-PROGRAM", ("pf3-blank-to-program",)),
        # COTRN01C's PF3 reads the caller (FROM-PROGRAM) and overwrites TO-PROGRAM
        ("carddemo-tranview", "CDEMO-FROM-PROGRAM", ("pf3-blank-from-program", "pf3-low-values-from-program")),
    ):
        scs = _gap_scenarios(case)
        assert all("expected" not in s for s in scs.values())
        for name in names:
            assert scs[name]["aid"] == "DFHPF3"
            value = scs[name]["commarea"][field]
            assert value.strip("\x00") == "" and (value == "" or "low" in name)


def test_the_admin_menu_case_picks_two_digit_and_non_digit_options():
    scs = _gap_scenarios("carddemo-adminmenu")
    opts = {
        n: s["receive"]["COADM1A"]["OPTIONI"]
        for n, s in scs.items()
        if "receive" in s and "OPTIONI" in s["receive"].get("COADM1A", {})
    }
    assert {opts["option-10"], opts["option-12"], opts["option-colon"], opts["option-less-than"]} == {
        "10",
        "12",
        ":",
        "<",
    }
    carried = scs["carried-commarea-fields"]["commarea"]
    assert all(
        str(carried[f]).strip()
        for f in ("CDEMO-TO-TRANID", "CDEMO-TO-PROGRAM", "CDEMO-CUST-LNAME", "CDEMO-ACCT-STATUS")
    )


def test_the_user_cases_carry_fields_the_screens_never_show():
    add = _gap_scenarios("carddemo-useradd")
    assert add["input-screen-with-errmsg"]["receive"]["COUSR1A"]["ERRMSGI"].strip()
    assert all(
        add["carried-status-and-last-map"]["commarea"][f].strip() for f in ("CDEMO-ACCT-STATUS", "CDEMO-LAST-MAP")
    )
    dele = _gap_scenarios("carddemo-userdel")
    assert dele["no-commarea-enter"]["commarea"] is None
    assert set(dele["low-values-selected-user"]["commarea"]["CDEMO-CU03-USR-SELECTED"]) == {"\x00"}
    assert dele["input-lname-echoed"]["receive"]["COUSR3A"]["LNAMEI"].strip()


def test_the_transaction_view_case_fails_the_pf3_xctl():
    s = _gap_scenarios("carddemo-tranview")["pf3-xctl-fails"]
    assert s["aid"] == "DFHPF3" and s["faults"][0]["cmd"] == "XCTL" and s["faults"][0]["resp"] == "PGMIDERR"


def test_the_generated_transaction_view_case_takes_the_same_survivor_scenarios():
    # #4049 slice 4: the generated variant runs the same port, so it needs the inputs its survivors point at
    gen, hand = _gap_scenarios("carddemo-tranview-generated"), _scenarios("carddemo-tranview")
    names = ("pf3-blank-from-program", "pf3-low-values-from-program", "pf3-xctl-fails", "lookup-io-error")
    for name in names:
        assert gen[name]["aid"] == hand[name]["aid"] and gen[name].get("faults") == hand[name].get("faults")
        assert "expected" not in gen[name]
    assert gen["pf3-xctl-fails"]["faults"][0]["resp"] == "PGMIDERR"
    assert gen["lookup-io-error"]["faults"][0]["resp"] == "IOERR"
    assert gen["pf3-blank-from-program"]["commarea"]["CDEMO-FROM-PROGRAM"] == ""
    assert set(gen["pf3-low-values-from-program"]["commarea"]["CDEMO-FROM-PROGRAM"]) == {"\x00"}


def test_the_eibcalen_scenarios_state_a_length_inside_the_commarea():
    # #5401: a short COMMAREA only on field boundaries whose unset numerics are not read (a blank numeric is IBM-undefined)
    for case, names, whole in (
        ("carddemo-userupd", ("short-commarea-185", "short-commarea-186"), 194),
        ("carddemo-report", ("short-commarea-146", "short-commarea-153"), 160),
        ("carddemo-tranlist", ("enter-short-commarea",), 218),
        ("carddemo-billpay", ("short-commarea-200", "short-commarea-201"), 218),
        ("carddemo-tranadd", ("short-commarea-200", "short-commarea-201"), 218),
    ):
        scs = _scenarios(case)
        for name in names:
            s = scs[name]
            assert s["commarea"] is not None
            assert 1 <= s["commarea_length"] < whole
            assert s["why"].startswith("#5401")


def test_cardview_and_cardlist_state_only_the_whole_commarea():
    # #5401: both programs move DFHCOMMAREA past 160 bytes whatever EIBCALEN is, so a shorter length is an X23 refusal
    for case, whole in (("carddemo-cardview", 172), ("carddemo-cardlist", 414)):
        s = _scenarios(case)["full-commarea-length"]
        assert s["commarea"] is not None
        assert s["commarea_length"] == whole
        assert s["why"].startswith("#5401")


def test_the_menu_family_cases_pin_the_slice_3_inputs():
    # #4049 slice 3: the stated EIBCALEN, the mapset the SEND MAP must name, a blank COMMAREA that reaches the output
    # (no COMMAREA plus a failing XCTL), and an empty id with a process date the found record cannot overwrite
    scs = _scenarios("carddemo-useradd")
    for name in ("short-commarea-147", "short-commarea-150"):
        assert scs[name]["commarea"] is not None and 1 <= scs[name]["commarea_length"] < 160
        assert scs[name]["why"].startswith("#4049 slice 3")
    import json

    path = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-useradd" / "case.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    assert case["maps"] == {"COUSR1A": {"mapset": "COUSR01"}}
    s = _scenarios("carddemo-adminmenu")["no-commarea-xctl-fails"]
    assert s["commarea"] is None and s["faults"][0]["cmd"] == "XCTL" and s["faults"][0]["resp"] == "PGMIDERR"
    s = _scenarios("carddemo-tranview")["enter-empty-transaction-id-with-process-date"]
    assert s["receive"]["COTRN1A"]["TPROCDTI"].strip()


def test_the_signon_case_takes_the_eibcalen_zero_survivor_scenario():
    # #4049: a COMMAREA of stated length 0 (EIBCALEN 0 with the area present) is an input only, never an expected result
    z = _scenarios("carddemo-signon")["eibcalen-zero-with-commarea"]
    assert z["commarea"] is not None and z["commarea_length"] == 0 and z["aid"] == "DFHENTER"
    assert z["why"].startswith("#4049") and "expected" not in z


def test_the_signon_case_takes_the_z_credential_survivor_scenarios():
    # #4049: the end of UPPER-CASE's a-z range, on an id and a password that are on file once folded; inputs only
    scs = _scenarios("carddemo-signon")
    on_file = (Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-signon" / "usrsec.txt").read_text()
    for name, fold in (("lowercase-z-credentials", True), ("uppercase-z-credentials", False)):
        s = scs[name]
        got = s["receive"]["COSGN0A"]
        assert "z" in got["USERIDI"].lower() and "z" in got["PASSWDI"].lower()
        assert (got["USERIDI"] != got["USERIDI"].upper()) is fold
        assert got["USERIDI"].upper() + "ZELDA" in on_file and got["PASSWDI"].upper() + "U" in on_file
        assert s["why"].startswith("#4049") and "expected" not in s


def test_the_userlist_case_takes_the_short_commarea_and_endbr_fault_scenarios():
    # #4049: a COMMAREA cut at or past the last numeric field (a shorter one leaves PIC 9 as spaces, undefined in IBM),
    # and ENDBR faults IBM lists for ENDBR (ILLOGIC, NOTAUTH; ITEMERR / PGMIDERR are not listed, IOERR has no abend
    # code in the oracle table); inputs only, never an expected result
    scs = _scenarios("carddemo-userlist")
    for n in (184, 185, 186):
        s = scs[f"short-commarea-{n}"]
        assert s["commarea_length"] == n and s["why"].startswith("#4049") and "expected" not in s
    for name, resp in (
        ("endbr-illogic-after-a-page-forward", "ILLOGIC"),
        ("endbr-notauth-after-a-page-back", "NOTAUTH"),
    ):
        s = scs[name]
        assert [(f["cmd"], f["file"], f["resp"]) for f in s["faults"]] == [("ENDBR", "USRSEC", resp)]
        assert s["why"].startswith("#4049") and "expected" not in s


def test_the_updacc_case_judges_each_nullable_column_of_the_select_alone():
    # #4049: UPDACC's SELECT INTO has no indicator variables, so any NULL column is SQLCODE -305. The old seed's only
    # NULL was ACCOUNT_LAST_STATEMENT, which hid every && / || mix-up among the other columns of the null test: one
    # seed row per column, each with exactly one NULL, and a scenario that LINKs it (inputs only, no expected result)
    case_dir = Path(__file__).resolve().parents[1] / "equivalence" / "cbsa-updacc"
    scs = _scenarios("cbsa-updacc")
    rows = {}
    for line in (case_dir / "seed.sql").read_text().splitlines():
        cells = line.strip().lstrip("(").rstrip(",;)").split(",")
        if len(cells) == 12:
            rows[int(cells[3].strip("'"))] = [i for i, c in enumerate(cells) if c.strip() == "NULL"]
    # seed column order: eyecatcher, customer, sortcode, accno, type, rate, opened, overdraft, last, next, avail, actual
    column = {
        "null-eyecatcher": 0,
        "null-customer-number": 1,
        "null-next-statement": 9,
        "null-available-balance": 10,
        "null-actual-balance": 11,
        "null-account-type": 4,
        "null-interest-rate": 5,
        "null-overdraft-limit": 7,
    }
    for name, col in column.items():
        s = scs[name]
        assert rows[int(s["commarea"]["COMM-ACCNO"])] == [col], name
        assert "#4049" in s["why"] and "expected" not in s
