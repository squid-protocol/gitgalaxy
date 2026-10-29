# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL Arithmetic and Rounding rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative arithmetic rules, rounding modes, size error conditions,
and deterministic test vectors execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.arith import (
    ARITH_RULES,
    ARITH_VECTORS,
    ROUNDING_MODES,
    SIZE_ERROR_CONDITIONS,
    calculate_divide_intermediate_scale,
    calculate_divide_remainder,
)
from gitgalaxy.standards.cobol.cli import problems, stale


def test_cobol_arith_spec_has_no_problems():
    """Verify internal consistency of standards/cobol arithmetic rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_arith_generated_files_are_not_stale():
    """Verify committed ArithSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_arith_modes_and_rules_defined():
    """Verify all rounding modes, size error specs, and rules are defined."""
    assert len(ROUNDING_MODES) == 7
    assert len(SIZE_ERROR_CONDITIONS) == 5
    assert len(ARITH_RULES) == 10
    assert len(ARITH_VECTORS) >= 12


@pytest.mark.parametrize("vec", ARITH_VECTORS, ids=lambda v: v.id)
def test_arith_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in ARITH_RULES
    meta = ARITH_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_divide_intermediate_scale_formula():
    """Verify intermediate quotient scale calculation."""
    assert calculate_divide_intermediate_scale(2, 1) == 39
    assert calculate_divide_intermediate_scale(0, 2) == 38
    assert calculate_divide_intermediate_scale(5, 0) == 43


def test_divide_remainder_scale_truncation():
    """Verify DIVIDE ... REMAINDER formula with scale truncation."""
    dividend = Decimal("100")
    divisor = Decimal("7")
    giving_scale = 1
    rem = calculate_divide_remainder(dividend, divisor, giving_scale)
    assert rem == Decimal("0.6")


def test_rounding_modes_mapping():
    """Verify each COBOL rounding mode maps to a valid decimal rounding mode."""
    for mode in ROUNDING_MODES.values():
        if mode.python_mode is not None:
            val = Decimal("1.25").quantize(Decimal("1.1"), rounding=mode.python_mode)
            assert isinstance(val, Decimal)
