"""#6967: every open outcome of the burned CBSA BMS screens (the BNK1* programs and BNKMENU) and of CRECUST is stated infeasible with a reason.

The terminal fault command exists (register X71: SEND MAP, SEND TEXT and RECEIVE MAP conditions). These checks read only
the committed sweep-coverage and infeasible-outcome files, so a new open SEND / RECEIVE arm fails here instead of
reading as covered. BNK1CAC keeps four open arms in the numeric-edit region (the DEEDIT item of #6967): stated family U,
"undefined by IBM" (owner ruling 2026-10-29, `.claude/rules/mainframe-evidence-policy.md` section 7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = ("bnk1cac", "bnk1cca", "bnk1ccs", "bnk1cra", "bnk1dac", "bnk1dcs", "bnk1tfn", "bnk1uac", "bnkmenu", "crecust")
UNDEFINED_BY_IBM = {"bnk1cac": {(611, "true"), (637, "true"), (637, "false"), (717, "true")}}


def _load(kind: str, case: str) -> dict:
    path = ROOT / f"tests/equivalence/{kind}/cbsa-{case}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _key(branch: str) -> tuple[int, str]:
    line, outcome = branch.split(":", 1)
    return int(line), outcome


@pytest.mark.parametrize("case", CASES)
def test_every_uncovered_branch_is_stated_infeasible_or_undefined_by_ibm(case):
    entries = [e for e in _load("infeasible_outcomes", case)["entries"] if "line" in e]
    stated = {(int(e["line"]), e["outcome"]) for e in entries}
    uncovered = _load("det_sweep_coverage", case)["uncovered"]["branches"]
    open_arms = {_key(b) for b in uncovered if not b.startswith("paragraph:")} - stated
    assert open_arms == set()
    undefined = {(int(e["line"]), e["outcome"]) for e in entries if e["family"] == "U"}
    assert undefined == UNDEFINED_BY_IBM.get(case, set())


@pytest.mark.parametrize("case", CASES)
def test_every_infeasible_entry_has_a_family_and_a_reason(case):
    for e in _load("infeasible_outcomes", case)["entries"]:
        assert e["family"] and len(e["reason"].strip()) > 20, e


def test_bnk1cac_437_is_taken_not_stated():
    """BIF DEEDIT of a field with no digit left is zeros (X26, assumed; #6940), so 437:true is covered, not refused or stated."""
    uncovered = _load("det_sweep_coverage", "bnk1cac")["uncovered"]["branches"]
    assert "437:true" not in uncovered
    assert 437 not in {e.get("line") for e in _load("infeasible_outcomes", "bnk1cac")["entries"]}


def test_crecust_has_no_undefined_by_ibm_outcome():
    entries = _load("infeasible_outcomes", "crecust")["entries"]
    assert {e["family"] for e in entries} <= {"G", "R"}
