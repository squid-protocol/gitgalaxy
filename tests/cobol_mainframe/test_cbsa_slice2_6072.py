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


def test_every_crdtagy_case_states_its_delay_and_put_container_failure_arms():
    for case in AGENCIES:
        entries = _json(EQ / "infeasible_outcomes" / f"{case}.json")["entries"]
        assert {(e["unit"], e["kind"], e["outcome"], e["family"]) for e in entries} == {("A010", "IF", "true", "R")}
        assert len({e["line"] for e in entries}) == 2
        assert all(e["reason"].strip() for e in entries)
