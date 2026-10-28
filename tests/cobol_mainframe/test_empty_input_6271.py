"""#6271: empty-field inputs the harness cannot represent are stated or refused by name, never claimed proven.

X54: a field of typed blanks arrives with length 0 (oracle side). X26: BIF DEEDIT of a field with no digit leaves zeros (ASSUMED).
The stated infeasible outcomes BNK1CRA 988 / BNK1TFN 1026 rest on the first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_cics as ec  # noqa: E402


@pytest.mark.parametrize("text", ["", " ", "   ", " " * 12])
@pytest.mark.parametrize("justify", ["LEFT,BLANK", "RIGHT,ZERO", "RIGHT,BLANK", "LEFT,ZERO"])
def test_typed_blanks_justify_to_nothing(text, justify):
    """No text typed: the field is all fill, the length (text without trailing blanks) 0."""
    out = ec.justified(text, 12, justify)
    assert out == ("0" if "ZERO" in justify else " ") * 12
    assert len(text.rstrip(" ")) == 0


@pytest.mark.parametrize("text,length", [("12", 2), ("  12", 4), ("12  ", 2)])
def test_leading_blanks_count_trailing_do_not(text, length):
    assert len(text.rstrip(" ")) == length


def test_deedit_of_a_field_with_no_digit_is_no_longer_refused():
    from gitgalaxy.standards.cics.commands.task import BIF_DEEDIT

    assert not any("no digit left" in (r.java or "") for r in BIF_DEEDIT.runtime_refusals)


@pytest.mark.parametrize("case,line", [("cbsa-bnk1cra", 988), ("cbsa-bnk1tfn", 1026)])
def test_blank_with_length_arms_are_stated_under_x54(case, line):
    entries = json.loads((ROOT / "tests/equivalence/infeasible_outcomes" / f"{case}.json").read_text("utf-8"))[
        "entries"
    ]
    hit = [e for e in entries if e["line"] == line and e["outcome"] == "true"]
    assert len(hit) == 1 and "X54" in hit[0]["reason"]


def test_rate_overrun_stays_refused_by_name():
    case = json.loads((ROOT / "tests/equivalence/cbsa-bnk1cac/case.json").read_text("utf-8"))
    assert "rate-three-places" in case["bounds_refused"]
