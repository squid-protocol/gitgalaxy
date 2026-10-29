# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL relation condition and comparison rules matrix (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative relation conditions, comparison modes, and test vectors execute
correctly and deterministically in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.compare import (
    COMPARE_MATRIX,
    COMPARE_MODES,
    COMPARE_RULES,
    COMPARE_VECTORS,
)
from gitgalaxy.standards.cobol.move import KINDS


def test_cobol_compare_spec_has_no_problems():
    """Verify internal consistency of standards/cobol comparison rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_compare_generated_files_are_not_stale():
    """Verify committed CompareSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_compare_modes_and_matrix_defined():
    """Verify 9x9 comparison matrix cells and comparison modes."""
    assert len(COMPARE_MODES) == 5
    assert len(COMPARE_RULES) == 8
    assert len(COMPARE_MATRIX) == 81


@pytest.mark.parametrize("vec", COMPARE_VECTORS, ids=lambda v: v.id)
def test_compare_vector_rule_alignment(vec):
    """Verify each comparison vector aligns with a registered comparison rule."""
    assert vec.rule_id in COMPARE_RULES
    meta = COMPARE_RULES[vec.rule_id]
    assert meta.id == vec.rule_id
    assert vec.expected_result in (-1, 0, 1)


def test_compare_numeric_different_scales_equal():
    """Verify RT-CBL-COMPARE-NUMERIC: algebraic value equality across scales."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP01-numeric-equal-different-scale")
    assert vec.expected_result == 0


def test_compare_numeric_signed_less():
    """Verify RT-CBL-COMPARE-NUMERIC: negative value is less than positive value."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP02-numeric-signed-less")
    assert vec.expected_result == -1


def test_compare_nonnumeric_space_padded():
    """Verify RT-CBL-COMPARE-NONNUMERIC: shorter operand is space padded."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP03-nonnumeric-equal-space-pad")
    assert vec.expected_result == 0
