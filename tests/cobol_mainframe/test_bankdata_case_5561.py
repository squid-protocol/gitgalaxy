"""#5561: CBSA BANKDATA's equivalence case compares what the program writes (the CUSTOMER VSAM file and the two Db2
tables) and carries a det-sweep coverage entry, so its evidence level can reach L2. Pins the case shape, not a count."""

import json
from pathlib import Path

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"


def _case(name):
    return json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))


def test_bankdata_compares_the_vsam_file_and_both_db2_tables():
    case = _case("cbsa-bankdata")
    assert case["program"] == "BANKDATA"
    assert case["datasets"]["VSAM"]["compare"] is True
    assert case["datasets"]["VSAM"]["organization"] == "indexed"
    assert case["db2"]["compare"] == ["IBMUSER.ACCOUNT", "IBMUSER.CONTROL"]
    assert (EQUIVALENCE / "cbsa-bankdata" / "seed.sql").is_file()


def test_bankdata_has_a_det_sweep_entry_with_every_paragraph_covered():
    entry = json.loads((EQUIVALENCE / "det_sweep_coverage" / "cbsa-bankdata.json").read_text(encoding="utf-8"))
    assert entry["scenarios"] >= 1
    assert entry["paragraphs"]["covered"] == entry["paragraphs"]["live"] > 0

