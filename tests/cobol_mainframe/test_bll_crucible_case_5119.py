"""#5119 (oracle_assumptions.md X56): the cics-crucible `ca-bll-cells` case (CABLL), the one corpus program that uses BLL cells.

The case is hand-traced from IBM's CICS/MVS 2.1.2 Application Programmer's Reference (SC33-0512-1; Figure 3, the
SERVICE RELOAD example, Figure 5). This file pins, with no GnuCOBOL and no Docker, what the repo says about it:
- det/bll.py lowers CABLL whole (no refusal): the cells become POINTERs, each SERVICE RELOAD of a record is a
  SET ADDRESS OF, the ADD 4096 goes, MOVE cell TO cell is SET;
- tests/equivalence/cruc-ca-bll-cells restates exactly the crucible's scenarios (name and terminal step);
- the crucible's expected SEND TEXT reports are the hand-traced ones.
Skipped when no crucible checkout is found (CICS_CRUCIBLE_PATH, else beside the repo).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.det import bll as B

REPO = Path(__file__).resolve().parents[2]
CASE = "cases/commarea-mismatch/ca-bll-cells"
# hand-traced: R = READQ TS SET(cell) of the 12-byte item QUEUED-ITEM1; L = GETMAIN 5400 '*', HEAD at byte 1, TAIL-BYTES at
# byte 5001 (second cell's span), TS-REC aliased to the record through MOVE FRPTR TO TSPTR
REPORTS = {
    "read-set-cell": "MODE=R REC=QUEUED-ITEM1 LEN=12",
    "long-record": "MODE=L VIEW=HEAD****** TAIL=TAIL-BYTES",
}


def _root() -> Path:
    env = os.environ.get("CICS_CRUCIBLE_PATH")
    root = Path(env) if env else REPO.parent / "cics-crucible"
    if not (root / CASE).is_dir():
        pytest.skip("no ca-bll-cells case in the cics-crucible checkout (CICS_CRUCIBLE_PATH)")
    return root / CASE


def _lowered() -> str:
    src = (_root() / "src" / "CABLL.cbl").read_text(encoding="utf-8")
    return B.lower_text(src, [])


def test_the_crucible_program_is_lowered_whole_onto_the_pointer_lane():
    out = _lowered()
    body = out.split("PROCEDURE DIVISION")[1]
    live = [r for r in body.splitlines() if len(r) > 6 and r[6] not in "*/"]
    assert not any("SERVICE RELOAD" in r for r in live), "every SERVICE RELOAD is lowered"
    assert not re.search(r"ADD\s+4096", body), "the long record's ADD 4096 is dropped"
    assert re.search(r"SET\s+ADDRESS\s+OF\s+Q-REC\s+TO\s+QPTR", body)
    assert re.search(r"SET\s+ADDRESS\s+OF\s+FILE-REC\s+TO\s+FRPTR", body)
    assert re.search(r"SET\s+ADDRESS\s+OF\s+TS-REC\s+TO\s+TSPTR", body)
    assert re.search(r"SET\s+TSPTR\s+TO\s+FRPTR", body), "MOVE cell TO cell aliases the storage"
    assert re.search(r"QPTR\b[^.]*POINTER", out), "the cells are POINTERs"


def test_the_equivalence_case_restates_the_crucible_scenarios():
    root = _root()
    ours = json.loads((REPO / "tests/equivalence/cruc-ca-bll-cells/case.json").read_text(encoding="utf-8"))
    theirs = json.loads((root / "case.json").read_text(encoding="utf-8"))
    assert ours["program"] == "CABLL" and ours["transid"] == "CA0N"
    assert sorted(s["name"] for s in ours["scenarios"]) == sorted(REPORTS)
    assert {s["name"] for s in ours["scenarios"]} == {s["id"] for s in theirs["scenarios"]}
    assert {s["name"]: s["terminal"] for s in ours["scenarios"]} == {"read-set-cell": "CA0N R", "long-record": "CA0N L"}


@pytest.mark.parametrize("scenario", sorted(REPORTS))
def test_the_expected_report_is_the_hand_traced_one(scenario):
    exp = json.loads((_root() / "expected" / f"{scenario}.json").read_text(encoding="utf-8"))
    texts = [e["text"] for t in exp["tasks"] for e in t["events"] if e["event"] == "SEND-TEXT"]
    assert [t.rstrip() for t in texts] == [REPORTS[scenario]]
