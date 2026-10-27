"""CBSA L3 coverage (#6072): the scenarios added to inqacccu and dbcrfun, and the stated BNKMENU arms.

JSON-only checks: each added scenario exists and injects the SQL failure its name says, at the
statement the case's COBOL source has on that line; the infeasible-outcome entries exist per case.
"""

import json
from pathlib import Path

EQUIV = Path(__file__).resolve().parents[1] / "equivalence"


def _scenarios(case):
    data = json.loads((EQUIV / case / "case.json").read_text(encoding="utf-8"))
    return {s["name"]: s for s in data["scenarios"]}


def test_inqacccu_covers_cursor_close_failing():
    sc = _scenarios("cbsa-inqacccu")["cursor-close-fails"]
    assert sc["sql_faults"] == [
        {"program": "INQACCCU", "line": 348, "sqlcode": -501, "why": sc["sql_faults"][0]["why"]},
    ]
    assert sc["sql_faults"][0]["why"]
    assert sc["commarea"]["CUSTOMER-NUMBER"] == "1"


def test_dbcrfun_covers_update_and_proctran_insert_failing():
    sc = _scenarios("cbsa-dbcrfun")
    faults = {
        n: sc[n]["sql_faults"]
        for n in ("update-fails-deadlock", "update-fails-connection-lost", "proctran-insert-fails")
    }
    assert faults["update-fails-deadlock"] == [
        {"program": "DBCRFUN", "table": "ACCOUNT", "verb": "UPDATE", "sqlcode": -911}
    ]
    assert faults["update-fails-connection-lost"] == [
        {"program": "DBCRFUN", "table": "ACCOUNT", "verb": "UPDATE", "sqlcode": 923, "sqlstate": "57015"}
    ]
    assert faults["proctran-insert-fails"] == [
        {"program": "DBCRFUN", "table": "PROCTRAN", "verb": "INSERT", "sqlcode": -803}
    ]
    assert all(sc[n]["why"] for n in faults)


def test_bnkmenu_states_its_unreachable_arms():
    path = EQUIV / "infeasible_outcomes" / "cbsa-bnkmenu.json"
    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    menu = {(e["unit"], e.get("line"), e["outcome"]): e for e in entries}
    assert ("IOT010", 897, "false") in menu
    # IOT999 is entered only by falling out of INVOKE-OTHER-TXNS, and every path out of it ends the task (#6072)
    assert ("IOT999", None, "entered") in menu
    # the RESP-fault scenarios (#6292) reach the failing-RETURN / SEND MAP arms, and a planned INVREQ on the
    # plain RETURN TRANSID reaches A010's (#6271), so those are no longer stated
    assert ("IOT010", 394, "true") not in menu
    assert ("A010", 178, "true") not in menu
    assert all(e["reason"] for e in entries)


def test_dbcrfun_states_only_the_storm_drain_tail():
    path = EQUIV / "infeasible_outcomes" / "cbsa-dbcrfun.json"
    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    assert {(e["unit"], e["kind"], e["outcome"]) for e in entries} == {
        ("AH999", "PARAGRAPH", "entered"),
        ("AH010", "IF", "false"),
    }
    assert all(e["reason"] for e in entries)
