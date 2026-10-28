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
    # create-customer, born-in-the-future, born-30-feb and born-over-150 reach CEEDAYS (L1); born-before-1601 ends before it
    assert names[:5] == ["create-customer", "born-before-1601", "born-in-the-future", "born-30-feb", "born-over-150"]
    # #6072: the CUSTOMER control-record and new-record fault scenarios (the SYSIDERR retries and the other RESPs)
    assert names[5:] == [
        "control-read-sysiderr-retried",
        "control-read-io-error",
        "control-rewrite-sysiderr-retried",
        "control-rewrite-io-error",
        "write-sysiderr-retried",
        "write-sysiderr-exhausted",
        # #6882: RUN TRANSID and FETCH ANY faults
        "run-transid-first-transiderr",
        "fetch-any-notfinished-nothing-retrieved",
        "fetch-any-notfinished-after-a-reply",
        "fetch-any-notfnd-nothing-retrieved",
        "fetch-any-notfnd-after-a-reply",
    ]


def test_notes_name_the_assumptions_and_forbid_reading_the_level_from_them():
    notes = _case()["notes"]
    for word in ("L1", "X18", "ASSUMED", "Not recorded as evidence"):
        assert word in notes
    assert "NOT PROVABLE" not in notes


def test_sweep_baseline_no_longer_carries_the_case():
    # #5089: the slack is ruled blank (L1), so the det proof holds and the baseline is a two-way ratchet
    det = json.loads((ROOT / "tests/equivalence/det_sweep_baseline.json").read_text(encoding="utf-8"))["det"]
    assert "cbsa-crecust" not in det and "cbsa-bnk1ccs-create" not in det


def test_register_entries_agree_the_case_is_refused_not_proven():
    l1 = (REGISTER / "L1.md").read_text(encoding="utf-8")
    x18 = (REGISTER / "X18.md").read_text(encoding="utf-8")
    assert "cbsa-crecust" in l1 and "REFUSED" in l1
    assert "tests/equivalence/cbsa-crecust" in x18 and "BNK1CCS" in x18
