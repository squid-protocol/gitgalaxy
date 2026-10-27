"""#6072 slice 2: the CBSA CRDTAGY1-5 infeasible outcomes. Unit tests need only the committed ledger; the proofs are the
det sweep's (`det_port.py run cbsa-crdtagy1`)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "tests" / "equivalence"
AGENCIES = [f"cbsa-crdtagy{n}" for n in range(1, 6)]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_crdtagy_case_states_its_put_container_failure_arm_and_plans_the_delay_fault():
    # The DELAY failure arm is no longer infeasible: a planned DELAY fault reaches it (#6271, register X72).
    for case in AGENCIES:
        entries = _json(EQ / "infeasible_outcomes" / f"{case}.json")["entries"]
        assert {(e["unit"], e["kind"], e["outcome"], e["family"]) for e in entries} == {("A010", "IF", "true", "R")}
        assert len({e["line"] for e in entries}) == 1
        assert all("PUT CONTAINER" in e["reason"] for e in entries)
        faults = [f for s in _json(EQ / case / "case.json")["scenarios"] for f in s.get("faults", [])]
        assert any(f["cmd"] == "DELAY" for f in faults)
