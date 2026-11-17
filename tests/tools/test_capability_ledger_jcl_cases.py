"""#8413: the capability ledger's "JCL step flow" row counts the IBM-written GDG, restart and data-flow scenarios,
each reproduced live by its resolver (not read back from a stored number)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E402

import capability_ledger as cl  # noqa: E402


def _n(case: str) -> int:
    return len(json.loads((cl.JCL_CASES / case / "scenarios.json").read_text(encoding="utf-8"))["scenarios"])


def test_each_case_is_counted_in_full_and_every_answer_is_reproduced():
    got = cl.step_cases_live()
    assert set(got) == {"gdg", "restart", "dataflow"}
    for case, (ok, n) in got.items():
        assert n == _n(case) and n > 0, case
        assert ok == n, case


def test_the_step_flow_total_includes_those_scenarios():
    jf = cl.jcl_step_flow()
    ok, n = jf["fixture"]
    assert n >= sum(_n(c) for c in ("gdg", "restart", "dataflow"))
    assert ok == n
