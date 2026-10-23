"""CBSA L3 paragraph coverage (#6072): the scenario added to inqacccu.

JSON-only checks: the added scenario exists and injects the SQL failure its name says, at the
statement the case's COBOL source has on that line.
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
