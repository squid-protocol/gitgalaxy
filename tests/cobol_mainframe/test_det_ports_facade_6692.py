"""#6692: CBSA INQACC and GenApp LGICDB01 are committed as the det translator's own ports.

The model-written ports did not reach Db2 through cobolrt.sql.DetSql (INQACC) or only through a hand-edited seam
(LGICDB01, #6882), so the java facade could not fire every declared sql_faults scenario (INQACC was 14/23).
"""

import json
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parents[1] / "equivalence"


@pytest.mark.parametrize(
    ("case", "program", "service"),
    [
        ("cbsa-inqacc", "INQACC", "InqaccService.java"),
        ("genapp-lgicdb01", "LGICDB01", "Lgicdb01Service.java"),
    ],
)
def test_the_committed_det_port_is_proven_through_both_sides(case, program, service):
    port = CASES / case / "port"
    prov = json.loads((port / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["program"], prov["translator"]) == (program, "det")
    assert "stale" not in prov
    assert (port / "service" / service).is_file()
    rec = json.loads((CASES / case / "evidence.json").read_text(encoding="utf-8"))
    proof = rec["proof"]
    assert proof["verdict"] == "proven" and not proof["java_failed"]
    assert rec["provenance"]["written_by"] == "det"
    facade = proof["facade"]
    assert facade["verdict"] == "proven" and facade["passed"] == facade["runs"] == proof["runs"]
    declared = [
        sc
        for sc in json.loads((CASES / case / "case.json").read_text(encoding="utf-8"))["scenarios"]
        if sc.get("sql_faults")
    ]
    assert declared and {sc["name"] for sc in declared} <= set(proof["outputs"])


def test_no_case_is_left_in_the_facade_baseline_for_6692():
    base = json.loads((CASES / "facade_baseline.json").read_text(encoding="utf-8"))
    assert not [k for k, v in base["cases"].items() if v.get("issue") == "#6692"]
