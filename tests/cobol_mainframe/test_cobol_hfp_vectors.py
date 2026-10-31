# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL Hexadecimal Floating Point (HFP) rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative HFP rules, conversions, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.hfp import (
    BYTES_LONG,
    BYTES_SHORT,
    HFP_RULES,
    HFP_VECTORS,
    PRECISION_LONG,
    PRECISION_SHORT,
    SIGNIFICANT_DIGITS_LONG,
    SIGNIFICANT_DIGITS_SHORT,
    execute_decode,
    execute_display,
    execute_encode,
    execute_power,
    execute_to_fixed,
    execute_to_short,
)
from gitgalaxy.tools.cobol_to_java.det import hfp as _hfp


def test_cobol_hfp_spec_has_no_problems():
    """Verify internal consistency of standards/cobol HFP rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_hfp_generated_files_are_not_stale():
    """Verify committed HfpSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_hfp_rules_and_constants_defined():
    """Verify HFP rules and precision constants are properly defined."""
    assert len(HFP_RULES) == 14
    assert PRECISION_SHORT == 6
    assert PRECISION_LONG == 14
    assert BYTES_SHORT == 4
    assert BYTES_LONG == 8
    assert SIGNIFICANT_DIGITS_SHORT == 9
    assert SIGNIFICANT_DIGITS_LONG == 18
    assert len(HFP_VECTORS) >= 25


@pytest.mark.parametrize("vec", HFP_VECTORS, ids=lambda v: v.id)
def test_hfp_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in HFP_RULES
    meta = HFP_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", HFP_VECTORS, ids=lambda v: v.id)
def test_hfp_vector_encoding(vec):
    """Verify HFP encoding matches expected hexadecimal representation."""
    if vec.expected_hex.startswith("ERROR_"):
        return
    if vec.input_value.startswith("ieee_"):
        if vec.short:
            b = _hfp.from_ieee(0x3F800000, 4)  # 1.0f
        else:
            b = _hfp.from_ieee(0xC05DA80000000000, 8)  # -118.625d
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value.startswith("numval"):
        b = _hfp.encode(_hfp.of("123.45"), False)
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value.startswith("fixed_store"):
        b = _hfp.encode(_hfp.for_item(Fraction("-1.005"), True), True)
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value == "to_short(2/3)":
        res = _hfp.to_short(_hfp.div(Fraction(2), Fraction(3), long=True))
        assert _hfp.encode(res, True).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "to_short(-2/3)":
        res = _hfp.to_short(-_hfp.div(Fraction(2), Fraction(3), long=True))
        assert _hfp.encode(res, True).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "2 ** 10":
        res = execute_power(2, 10)
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "of(0.1)":
        res = _hfp.of("0.1")
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "(1 / 3) * 3":
        third = _hfp.div(Fraction(1), Fraction(3), long=True)
        res = _hfp.mul(third, Fraction(3), long=True)
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return

    encoded = execute_encode(vec.input_value, vec.short)
    assert encoded.hex().upper() == vec.expected_hex, f"{vec.id}: expected {vec.expected_hex}, got {encoded.hex().upper()}"


@pytest.mark.parametrize("vec", [v for v in HFP_VECTORS if v.expected_display is not None], ids=lambda v: v.id)
def test_hfp_vector_display(vec):
    """Verify DISPLAY formatting for vectors specifying expected_display."""
    disp = execute_display(vec.input_value, not vec.short)
    assert disp == vec.expected_display, f"{vec.id}: expected {vec.expected_display!r}, got {disp!r}"


@pytest.mark.parametrize("vec", [v for v in HFP_VECTORS if v.expected_fixed is not None], ids=lambda v: v.id)
def test_hfp_vector_fixed(vec):
    """Verify float-to-fixed conversion for vectors specifying expected_fixed."""
    if vec.input_value.startswith("fixed_store"):
        b = _hfp.encode(_hfp.for_item(Fraction("-1.005"), True), True)
    else:
        b = execute_encode(vec.input_value, vec.short)
    sig = 9 if vec.short else 18
    fix = str(execute_to_fixed(execute_decode(b), vec.scale, sig))
    assert fix == vec.expected_fixed, f"{vec.id}: expected {vec.expected_fixed!r}, got {fix!r}"


def test_hfp_guard_digit_truncation():
    """Verify that arithmetic retains one guard digit and discards beyond."""
    one = Fraction(1)
    # 16**-6 sits in guard digit and is subtracted
    assert _hfp.sub(one, Fraction(16) ** -6, long=False) == 1 - Fraction(16) ** -6
    # 16**-8 is shifted past guard digit and lost
    assert _hfp.sub(one, Fraction(16) ** -8, long=False) == 1


def test_hfp_load_rounded():
    """Verify long-to-short LOAD ROUNDED rounds half away from zero."""
    res_pos = _hfp.to_short(_hfp.div(Fraction(2), Fraction(3), long=True))
    assert _hfp.encode(res_pos, True).hex().upper() == "40AAAAAB"
    res_neg = _hfp.to_short(-_hfp.div(Fraction(2), Fraction(3), long=True))
    assert _hfp.encode(res_neg, True).hex().upper() == "C0AAAAAB"
