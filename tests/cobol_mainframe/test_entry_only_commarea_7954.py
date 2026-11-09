"""#7954 slice 12: `"entry_only": true` enters a port with COMMAREA bytes and no link area (the byte[] entry alone).

With a link area, the `task.linkArea()` re-copy (#7589) overwrites the byte[] entry copy, so a mutant of that copy never
shows. A det caller's RETURN / XCTL passes a copy (DetCics.commareaOut), so no caller reads an end area back.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

EQ = Path(__file__).resolve().parents[1] / "equivalence"
CASES = ["cbsa-getcompy", "cbsa-getscode", "cbsa-acctctrl", "cbsa-updcust", "cbsa-abndproc"]


def _eq():
    import equivalence_cics as eq

    return eq


def _sc(**kw):
    return {"name": "s", "commarea_hex": "C1C2C3", **kw}


def test_the_key_absent_false_or_true_with_hex_states_the_bytes():
    eq = _eq()
    assert eq.untyped_commarea({}, _sc(), []) == bytes.fromhex("C1C2C3")
    assert eq.untyped_commarea({}, _sc(entry_only=True), []) == bytes.fromhex("C1C2C3")


@pytest.mark.parametrize("bad", [False, 1, "yes", 0])
def test_a_value_other_than_true_is_refused(bad):
    eq = _eq()
    with pytest.raises(eq.Unsupported, match="entry_only"):
        eq.untyped_commarea({}, _sc(entry_only=bad), [])


def test_the_key_without_hex_or_with_link_bytes_is_refused():
    eq = _eq()
    with pytest.raises(eq.Unsupported, match="entry_only"):
        eq.untyped_commarea({}, {"name": "s", "entry_only": True}, [])
    with pytest.raises(eq.Unsupported, match="entry_only"):
        eq.untyped_commarea({}, _sc(entry_only=True, link_bytes=True), [])


@pytest.mark.parametrize("n", [1, 40, 98, 99, 2000])
def test_the_java_scenario_carries_no_link_area_only_when_entry_only(n):
    eq = _eq()
    hexs = "C1" * n
    plain = eq._java_untyped_commarea({}, _sc(commarea_hex=hexs), [])
    only = eq._java_untyped_commarea({}, _sc(commarea_hex=hexs, entry_only=True), [])
    assert "area" in plain and "area" not in only
    assert only["commarea_hex"] == plain["commarea_hex"] and only["untyped_length"] == plain["untyped_length"]


def test_the_closing_commarea_event_is_left_out_on_both_sides_only_when_entry_only():
    eq = _eq()
    ev = [{"event": "READ"}, {"event": "COMMAREA"}]
    kept = eq.mask_absent_commarea(_sc(), list(ev), list(ev), None)
    assert kept == (ev, ev)
    cut = eq.mask_absent_commarea(_sc(entry_only=True), list(ev), list(ev), None)
    assert cut == ([{"event": "READ"}], [{"event": "READ"}])


def test_each_burned_cbsa_case_states_entry_only_scenarios_beside_its_raw_entry_ones():
    for name in CASES:
        scs = json.loads((EQ / name / "case.json").read_text(encoding="utf-8"))["scenarios"]
        only = [s for s in scs if s.get("entry_only")]
        assert only, name
        for s in only:
            assert s["commarea_hex"] and not s.get("link_bytes") and s.get("why"), (name, s["name"])
