"""#7589: the three cics-crucible harness gaps that closed on main stay closed.

CACCSID (CCSID 1208 container data, #7637), CAGMZ / CAGMPT (the POINTER numeric view, #7651) and HCRDST
(ridfld bytes in EBCDIC, #7562; the case, #7599 / #7616 / #7632) each have an equivalence case whose committed
det-sweep ledger records what its scenarios execute. This pins those records, so a case or ledger that
regresses to "the oracle refuses it" fails here.

HCRDST reads 8/9 in docs/language_status/cics_crucible.md and 9/9 here, and both are right: the doc table counts
the crucible's own four scenarios (tests/cics_crucible/coverage.json); the equivalence case adds a fifth,
`unmatched-mode`, that reaches the one branch the crucible's scenarios never take (EVALUATE with no WHEN arm).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEDGERS = ROOT / "tests" / "equivalence" / "det_sweep_coverage"
CASES = ROOT / "tests" / "equivalence"
CRUCIBLE_COVERAGE = ROOT / "tests" / "cics_crucible" / "coverage.json"


def _ledger(case: str) -> dict:
    return json.loads((LEDGERS / f"{case}.json").read_text(encoding="utf-8"))


# case, scenarios, paragraphs (covered, live), branches (covered, total)
EXPECTED = [
    ("cruc-ca-container-ccsid", 1, (3, 3), (0, 0)),
    ("cruc-ca-getmain-pointer-zero", 1, (3, 3), (4, 4)),
    ("cruc-ca-getmain-pointer", 1, (2, 2), (3, 6)),
    ("cruc-hc-file-read-set", 5, (8, 8), (9, 9)),
]


@pytest.mark.parametrize(("case", "scenarios", "paras", "branches"), EXPECTED, ids=[e[0] for e in EXPECTED])
def test_the_closed_gap_has_a_runnable_case_with_its_coverage(case, scenarios, paras, branches):
    led = _ledger(case)
    assert led["scenarios"] == scenarios
    assert (led["paragraphs"]["covered"], led["paragraphs"]["live"]) == paras
    assert (led["branches"]["covered"], led["branches"]["total"]) == branches


def test_every_branch_of_cagmpt_not_executed_is_a_reviewed_infeasible_outcome():
    led = _ledger("cruc-ca-getmain-pointer")
    infeasible = json.loads((CASES / "infeasible_outcomes" / "cruc-ca-getmain-pointer.json").read_text("utf-8"))
    reviewed = {f"{e['line']}:{e['outcome']}" for e in infeasible["entries"]}
    assert set(led["uncovered"]["branches"]) == reviewed


def test_the_ccsid_case_covers_the_1208_container_by_name():
    case = json.loads((CASES / "cruc-ca-container-ccsid" / "case.json").read_text("utf-8"))
    assert [s["name"] for s in case["scenarios"]] == ["convert"]
    assert "1208" in case["notes"]


def test_hcrdst_doc_figure_counts_only_the_crucibles_scenarios():
    prog = json.loads(CRUCIBLE_COVERAGE.read_text("utf-8"))["programs"]["hc-file-read-set/HCRDST"]
    crucible = {o for s in prog["scenarios"].values() for o in s["outcomes"]}
    case = json.loads((CASES / "cruc-hc-file-read-set" / "case.json").read_text("utf-8"))
    names = {s["name"] for s in case["scenarios"]}
    assert len(prog["scenarios"]) == 4
    assert len(crucible) == 8 and prog["outcomes"] == 9  # the doc's 8/9
    assert "unmatched-mode" in names  # the equivalence-only scenario that closes the ninth
    assert _ledger("cruc-hc-file-read-set")["branches"] == {"covered": 9, "total": 9}
