"""#5089: the BNK1CCS create-customer scenarios are written, and refused by name until the L1 slack is ruled.

cbsa-bnk1ccs and cbsa-bnk1ccs-generated stop at born-before-1601 because a date of birth from 1601 on reaches CRECUST's
CEEDAYS call (L1: picture length 10 over 8 bytes), which the oracle refuses and with it the whole case. The two ENTERs
that reach it live in cbsa-bnk1ccs-create so the stated scenarios keep running. These checks pin that state without
Docker, so quietly dropping a hole, a child or a scenario fails here instead of reading as a proof.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "tests/equivalence"
CASE_DIR = EQ / "cbsa-bnk1ccs-create"
CHILDREN = {f"OCR{n}": f"CRDTAGY{n}" for n in range(1, 6)}


def _case(name: str = "cbsa-bnk1ccs-create") -> dict:
    return json.loads((EQ / name / "case.json").read_text(encoding="utf-8"))


def test_scenarios_are_the_two_enters_that_reach_ceedays():
    case = _case()
    assert case["program"] == "BNK1CCS"
    assert [s["name"] for s in case["scenarios"]] == ["create-customer", "born-in-the-future"]
    for s in case["scenarios"]:
        assert s["aid"] == "DFHENTER"
        year = int(s["receive"]["BNK1CC"]["DOBYYI"])
        assert year >= 1601  # an earlier year ends before CEEDAYS: that is the stated case's born-before-1601


def test_the_stated_cases_do_not_reach_ceedays():
    # a year from 1601 on in a stated case would make the whole case refuse (L1)
    for name in ("cbsa-bnk1ccs", "cbsa-bnk1ccs-generated"):
        for s in _case(name)["scenarios"]:
            year = ((s.get("receive") or {}).get("BNK1CC") or {}).get("DOBYYI")
            if year and year.strip("_ ").isdigit():
                assert int(year) < 1601 or len(year.strip("_ ")) < 4, (name, s["name"])


def test_case_runs_the_five_children_and_the_proctran_compare():
    case = _case()
    assert case["child_programs"] == CHILDREN
    assert {p["program"] for p in case["programs"]} >= {"CRECUST", "ABNDPROC", *CHILDREN.values()}
    assert "IBMUSER.PROCTRAN" in case["db2"]["compare"]
    assert case["db2"]["seed"] == "@generate"  # a hand seed would need a generated sibling (#4507)


def test_notes_name_every_hole_and_forbid_recording():
    notes = _case()["notes"]
    assert "NOT PROVABLE" in notes
    for hole in ("L1", "X18"):
        assert hole in notes
    assert "Never --record" in notes
