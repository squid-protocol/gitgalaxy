"""#7954: a typed LINK given no area (dto_entry) enters the facade's byte overload with a null area.

Before, only `link_bytes` scenarios reached handleLink(request, byte[]), so a mutant of its `lastLinkBytes` bookkeeping
(`&&` -> `||`) was never run: a `harness-gap` row. A dto_entry scenario of a LINKed case now takes that overload, and
the driver requires lastLinkBytes() to answer null (no area was passed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

EQ = Path(__file__).resolve().parents[1] / "equivalence"
CASES = ("cbsa-getcompy", "cbsa-getscode", "cbsa-updacc")


def _src() -> str:
    import equivalence_cics as eq

    return Path(eq.__file__).read_text(encoding="utf-8")


def test_a_dto_entry_scenario_turns_the_byte_overload_on():
    src = _src()
    assert 'region.rawArea = sc.path("link_bytes").asBoolean(false) || sc.path("dto_entry").asBoolean(false);' in src


def test_the_java_scenario_carries_dto_entry_only_when_the_scenario_has_it():
    src = _src()
    assert '**({"dto_entry": True} if sc.get("dto_entry") else {})' in src


def test_the_null_area_answer_is_still_judged():
    src = _src()
    assert "scenario.linkAreaTaken() ? scenario.linkAreaView() : null" in src
    assert 'FacadeRefused("lastLinkBytes() of "' in src


def test_each_case_with_a_byte_overload_has_a_dto_entry_scenario_on_a_linked_case():
    for name in CASES:
        case = json.loads((EQ / name / "case.json").read_text(encoding="utf-8"))
        assert case.get("linked"), name
        assert any(s.get("dto_entry") and not s.get("link_bytes") for s in case["scenarios"]), name
