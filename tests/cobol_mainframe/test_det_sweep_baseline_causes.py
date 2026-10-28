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


def test_the_evidence_notes_state_binary64_as_an_owner_assumption_not_a_zos_capture():
    """#5867: EPSMPMT's float power / ANNUITY is the owner's stated IEEE binary64; the record must not call it a hole,
    an unproven case or a pending z/OS capture."""
    equivalence = Path(__file__).resolve().parents[1] / "equivalence"
    notes = json.loads((equivalence / "mortgage-mpmt" / "case.json").read_text(encoding="utf-8"))["notes"]
    assert "Owner decision 2026-10-27" in notes
    assert "NOT a z/OS calibration" in notes
    assert "not proven on purpose" not in notes
    assert "stay for a z/OS capture" not in notes
