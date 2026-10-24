"""#6072: the DBB mortgage det-sweep baseline entries name their real cause (EPSMPMT's one hole), not a stale one."""

from __future__ import annotations

import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / "equivalence" / "det_sweep_baseline.json"
DET = json.loads(BASELINE.read_text(encoding="utf-8"))["det"]
CASES = ("mortgage-mpmt", "mortgage-csmrt", "mortgage-cmort")


def test_the_three_mortgage_ports_are_listed():
    for case in CASES:
        assert case in DET, case


def test_each_names_the_annuity_hole_and_its_owner_issue():
    for case in CASES:
        why = DET[case]["why"]
        assert "FUNCTION ANNUITY" in why, case
        assert "#5867" in why, case


def test_the_callers_say_it_is_the_called_hole_rule_not_a_differing_port():
    for case in ("mortgage-csmrt", "mortgage-cmort"):
        why = DET[case]["why"]
        assert "EPSMPMT" in why, case
        assert "the proof passes" in why, case
        assert "no longer a hole since #5999" in why, case
