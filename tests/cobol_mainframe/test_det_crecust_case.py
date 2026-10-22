"""#4952: the CBSA CRECUST equivalence case (Db2 seed, five RUN children) is committed and its holes are named.

The case is never proven while a hole stands: L1 (CEEDAYS picture 10 over 8 bytes, refused by name) and X18 (the child
schedule is ASSUMED). These checks pin that state without running Docker, so a later change that quietly drops a hole,
a child, the Db2 seed or the sweep-baseline entry fails here instead of reading as a proof.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "tests/equivalence/cbsa-crecust"
REGISTER = ROOT / "docs/language_status/register"
CHILDREN = {f"OCR{n}": f"CRDTAGY{n}" for n in range(1, 6)}


def _case() -> dict:
    return json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))


def test_case_runs_the_five_children_and_has_a_db2_seed():
    case = _case()
    assert case["kind"] == "cics" and case["program"] == "CRECUST"
    assert case["child_programs"] == CHILDREN
    assert sorted(case["transactions"]) == sorted(CHILDREN)
    # every child is a program of the case, so RUN TRANSID has something to run
    assert {p["program"] for p in case["programs"]} >= set(CHILDREN.values())
    seed = CASE_DIR / "seed.sql"
    assert case["db2"]["seed"] == "@case/seed.sql" and seed.is_file()
    assert "IBMUSER.PROCTRAN" in case["db2"]["compare"]
    assert re.search(r"INSERT\s+INTO", seed.read_text(encoding="utf-8"), re.I)


def test_scenarios_cover_the_credit_check_and_the_paths_around_the_ceedays_hole():
    names = [s["name"] for s in _case()["scenarios"]]
    # create-customer and born-in-the-future reach CEEDAYS (L1); born-before-1601 ends before it
    assert names == ["create-customer", "born-before-1601", "born-in-the-future"]


def test_notes_name_every_hole_and_forbid_recording():
    notes = _case()["notes"]
    assert "NOT PROVABLE" in notes
    for hole in ("L1", "X18"):
        assert hole in notes
    assert "Never --record" in notes


def test_sweep_baseline_carries_the_holes_by_name():
    entry = json.loads((ROOT / "tests/equivalence/det_sweep_baseline.json").read_text(encoding="utf-8"))["det"][
        "cbsa-crecust"
    ]
    assert entry["issue"] == "#4952"
    assert "L1" in entry["why"] and "X18" in entry["why"]
    assert "picture not modelled" in entry["why"]


def test_register_entries_agree_the_case_is_refused_not_proven():
    l1 = (REGISTER / "L1.md").read_text(encoding="utf-8")
    x18 = (REGISTER / "X18.md").read_text(encoding="utf-8")
    assert "cbsa-crecust" in l1 and "REFUSED" in l1
    assert "tests/equivalence/cbsa-crecust" in x18 and "BNK1CCS" in x18
