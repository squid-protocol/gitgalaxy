"""#5089: the BNK1CCS create-customer scenarios run in the stated cases, on the L1 slack ruling (owner, 2026-10-23).

CRECUST's CEEDAYS picture is declared 10 bytes over 8; the 2 slack bytes are ruled blank (register L1, ASSUMED), so a date
of birth from 1601 on no longer ends the oracle's run. The two ENTERs that reach CEEDAYS used to live in a case of their
own (cbsa-bnk1ccs-create); these checks pin that they are in cbsa-bnk1ccs and cbsa-bnk1ccs-generated and that the
separate case is gone, without Docker, so quietly dropping a scenario or a hole note fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "tests/equivalence"
STATED = ("cbsa-bnk1ccs", "cbsa-bnk1ccs-generated")
CHILDREN = {f"OCR{n}": f"CRDTAGY{n}" for n in range(1, 6)}


def _case(name: str) -> dict:
    return json.loads((EQ / name / "case.json").read_text(encoding="utf-8"))


def test_the_separate_create_case_is_gone():
    assert not (EQ / "cbsa-bnk1ccs-create").exists()


def test_each_stated_case_holds_the_two_enters_that_reach_ceedays():
    for name in STATED:
        by_name = {s["name"]: s for s in _case(name)["scenarios"]}
        for scenario, year in (("create-customer", "1985"), ("born-in-the-future", "2099")):
            s = by_name[scenario]
            assert s["aid"] == "DFHENTER", (name, scenario)
            assert s["receive"]["BNK1CC"]["DOBYYI"] == year, (name, scenario)  # 1601 or later reaches CEEDAYS


def test_both_cases_run_the_five_children_and_the_proctran_compare():
    for name in STATED:
        case = _case(name)
        assert case["child_programs"] == CHILDREN
        assert {p["program"] for p in case["programs"]} >= {"CRECUST", "ABNDPROC", *CHILDREN.values()}
        assert "IBMUSER.PROCTRAN" in case["db2"]["compare"]
    assert _case("cbsa-bnk1ccs-generated")["db2"]["seed"] == "@generate"  # a hand seed would need a generated sibling


def test_notes_name_the_assumptions_and_no_longer_claim_a_refusal():
    for name in (*STATED, "cbsa-crecust", "cbsa-crecust-generated"):
        notes = _case(name)["notes"]
        assert "L1" in notes and "X18" in notes, name
        assert "refuses" not in notes and "NOT PROVABLE" not in notes, name
