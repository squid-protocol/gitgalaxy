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


def test_epsmpmt_is_listed_for_the_oracle_side_not_for_a_hole():
    why = DET["mortgage-mpmt"]["why"]
    assert "#5867" in why
    assert "binary32" in why  # the COMP-1 C on GnuCOBOL's side
    assert "599550.79" in why  # the differing call, measured
    assert "hole" not in why.replace("no hole", "")
