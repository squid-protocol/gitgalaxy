"""#6072 / #5867: the DBB mortgage det-sweep baseline entries name their real cause, not a stale one."""

from __future__ import annotations

import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / "equivalence" / "det_sweep_baseline.json"
DET = json.loads(BASELINE.read_text(encoding="utf-8"))["det"]


def test_the_callers_left_the_baseline_once_epsmpmt_had_no_hole():
    """EPSMPMT's ANNUITY was the callers' only cause (the called-hole rule); binary64 by owner decision (#5867)
    closed it, so mortgage-csmrt and mortgage-cmort are equal and must not be listed."""
    for case in ("mortgage-csmrt", "mortgage-cmort"):
        assert case not in DET, case


def test_epsmpmt_left_the_baseline_once_the_oracle_stated_binary64():
    """The oracle stand-in (equivalence_binary64.py, #5867 slice 2) proves it on 11 of 11 calls."""
    assert "mortgage-mpmt" not in DET
