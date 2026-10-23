"""#4507 [c:a7f4b905]: every CBSA case seeded by a hand-written seed.sql has a generated-Db2 sibling.

The class is "a cbsa-* equivalence case whose db2.seed is @case/seed.sql". Each member proves on Db2 rows generated
from the DDL as `<name>-generated` (db2.seed @generate, same program), except the named exemptions below. Pure file
reads: no corpus, Docker or Db2.
"""

import json
from pathlib import Path

CASES = Path(__file__).resolve().parents[1] / "equivalence"

# name -> why it has no generated sibling
EXEMPT = {
    "cbsa-bankdata": "batch loader: DELETEs its sortcode's rows, then writes them; it reads no seeded row",
    "cbsa-updacc-faults": "SQL-fault case for UPDACC (det-translated, no port): its generated sibling is cbsa-updacc-generated",
}


def _db2(name):
    return json.loads((CASES / name / "case.json").read_text(encoding="utf-8")).get("db2") or {}


def _program(name):
    return json.loads((CASES / name / "case.json").read_text(encoding="utf-8"))["program"]


def _hand_seeded():
    return sorted(
        p.name
        for p in CASES.glob("cbsa-*")
        if not p.name.endswith("-generated")
        and (p / "case.json").exists()
        and _db2(p.name).get("seed") == "@case/seed.sql"
    )


def test_every_hand_seeded_cbsa_case_has_a_generated_sibling_or_a_named_reason():
    missing = [n for n in _hand_seeded() if n not in EXEMPT and not (CASES / f"{n}-generated" / "case.json").exists()]
    assert missing == []


def test_each_generated_sibling_generates_rows_for_the_same_program():
    for name in _hand_seeded():
        sibling = CASES / f"{name}-generated" / "case.json"
        if not sibling.exists():
            continue
        assert _db2(f"{name}-generated").get("seed") == "@generate", name
        assert _program(f"{name}-generated") == _program(name), name


def test_the_exemptions_are_live():
    hand = set(_hand_seeded())
    for name in EXEMPT:
        assert name in hand, f"{name} no longer hand-seeded: drop its exemption"
        assert not (CASES / f"{name}-generated").exists(), name


def test_the_only_exemptions_are_the_batch_loader_and_the_fault_case():
    assert set(EXEMPT) == {"cbsa-bankdata", "cbsa-updacc-faults"}
