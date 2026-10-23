"""CBSA L3 coverage (#6072): the scenarios added to inqacccu and dbcrfun, and the stated BNKMENU / DBCRFUN arms.

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


def test_bnkmenu_and_dbcrfun_state_their_unreachable_arms():
    data = json.loads((EQUIV / "infeasible_outcomes.json").read_text(encoding="utf-8"))["cases"]
    menu = {(e["unit"], e["line"], e["outcome"]): e for e in data["cbsa-bnkmenu"]}
    assert ("IOT010", 897, "false") in menu
    assert menu[("A010", 178, "true")]["family"] == "R"
    assert data["cbsa-dbcrfun"][0]["line"] == 569
    assert all(e["reason"] for case in ("cbsa-bnkmenu", "cbsa-dbcrfun") for e in data[case])
