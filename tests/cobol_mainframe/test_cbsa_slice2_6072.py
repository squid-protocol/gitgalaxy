"""#6072 slice 2: the CBSA CRDTAGY1-5 infeasible outcomes and the BNK1DCS PF5 delete chain. Unit tests need only the committed
case files; the proofs are the det sweep's (`det_port.py run cbsa-bnk1dcs`)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "tests" / "equivalence"
AGENCIES = [f"cbsa-crdtagy{n}" for n in range(1, 6)]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_crdtagy_case_states_its_delay_and_put_container_failure_arms():
    cases = _json(EQ / "infeasible_outcomes.json")["cases"]
    for case in AGENCIES:
        entries = cases[case]
        assert {(e["unit"], e["kind"], e["outcome"], e["family"]) for e in entries} == {("A010", "IF", "true", "R")}
        assert len({e["line"] for e in entries}) == 2
        assert all(e["reason"].strip() for e in entries)


def test_bnk1dcs_links_the_whole_delete_chain_with_its_db2():
    case = _json(EQ / "cbsa-bnk1dcs" / "case.json")
    assert {"DELCUS", "INQACCCU", "DELACC"} <= {p["program"] for p in case["programs"]}
    assert (EQ / "cbsa-bnk1dcs" / case["db2"]["seed"].removeprefix("@case/")).is_file()
    assert "DELCUS is not translated whole" not in case["notes"]


def test_bnk1dcs_pf5_scenarios_cover_success_not_found_and_delete_failure():
    case = _json(EQ / "cbsa-bnk1dcs" / "case.json")
    pf5 = {s["name"]: s for s in case["scenarios"] if s["aid"] == "DFHPF5"}
    assert {
        "delete-three-accounts", "delete-one-loan", "delete-null-statement-date", "delete-not-on-file", "delete-ioerr",
    } <= set(pf5)  # fmt: skip
    assert pf5["delete-ioerr"]["faults"][0]["cmd"] == "DELETE"
    for s in pf5.values():
        fields = s["receive"]["BNK1DC"]
        assert fields["CUSTNOI"] == fields.get("CUSTNO2I", fields["CUSTNOI"])
