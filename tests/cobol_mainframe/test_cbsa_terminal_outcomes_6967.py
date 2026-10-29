"""#6967: every open outcome of the burned CBSA BMS screens (the BNK1* programs and BNKMENU) is stated infeasible with a reason.

The terminal fault command exists (register X71: SEND MAP, SEND TEXT and RECEIVE MAP conditions). These checks read only
the committed sweep-coverage and infeasible-outcome files, so a new open SEND / RECEIVE arm fails here instead of
reading as covered. BNK1CAC keeps four open arms in the numeric-edit region (the DEEDIT item of #6967), allowlisted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = ("bnk1cac", "bnk1cca", "bnk1ccs", "bnk1cra", "bnk1dac", "bnk1dcs", "bnk1tfn", "bnk1uac", "bnkmenu")
DEEDIT_OPEN = {"bnk1cac": {(611, "true"), (637, "true"), (637, "false"), (717, "true")}}


def _load(kind: str, case: str) -> dict:
    path = ROOT / f"tests/equivalence/{kind}/cbsa-{case}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _key(branch: str) -> tuple[int, str]:
    line, outcome = branch.split(":", 1)
    return int(line), outcome


@pytest.mark.parametrize("case", CASES)
def test_every_uncovered_branch_is_stated_infeasible_or_a_known_deedit_arm(case):
    stated = {(int(e["line"]), e["outcome"]) for e in _load("infeasible_outcomes", case)["entries"] if "line" in e}
    uncovered = _load("det_sweep_coverage", case)["uncovered"]["branches"]
    open_arms = {_key(b) for b in uncovered if not b.startswith("paragraph:")} - stated
    assert open_arms == DEEDIT_OPEN.get(case, set())


@pytest.mark.parametrize("case", CASES)
def test_every_infeasible_entry_has_a_family_and_a_reason(case):
    for e in _load("infeasible_outcomes", case)["entries"]:
        assert e["family"] and len(e["reason"].strip()) > 20, e
