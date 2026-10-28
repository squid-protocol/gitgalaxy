# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL Intrinsic Functions rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative function rules, categories, return types,
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

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.func import (
    FUNC_CATEGORIES,
    FUNC_RULES,
    FUNC_SPECS,
    FUNC_VECTORS,
    evaluate_date_of_integer_ansi,
    evaluate_integer_of_date_ansi,
    evaluate_mod,
    evaluate_numval,
    evaluate_numval_c,
    evaluate_rem,
)


def test_cobol_func_spec_has_no_problems():
    """Verify internal consistency of standards/cobol intrinsic function rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_func_generated_files_are_not_stale():
    """Verify committed FuncSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_func_categories_and_rules_defined():
    """Verify categories, specs, and rules are defined."""
    assert len(FUNC_CATEGORIES) == 5
    assert len(FUNC_RULES) == 12
    assert len(FUNC_SPECS) >= 20
    assert len(FUNC_VECTORS) >= 20


@pytest.mark.parametrize("vec", FUNC_VECTORS, ids=lambda v: v.id)
def test_func_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in FUNC_RULES
    meta = FUNC_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_func_simulation_mod_and_rem():
    """Verify MOD (floor) and REM (trunc) semantics."""
    assert evaluate_mod(Decimal("10"), Decimal("3")) == Decimal("1")
    assert evaluate_mod(Decimal("-10"), Decimal("3")) == Decimal("2")
    assert evaluate_mod(Decimal("10"), Decimal("0")) == Decimal("0")
    assert evaluate_rem(Decimal("-10"), Decimal("3")) == Decimal("-1")


def test_func_simulation_numval():
    """Verify NUMVAL and NUMVAL-C parsing."""
    assert evaluate_numval(" 123.45- ") == Decimal("-123.45")
    assert evaluate_numval(" 987.65CR ") == Decimal("-987.65")
    assert evaluate_numval_c(" $1,234,567.89 ") == Decimal("1234567.89")


def test_func_simulation_date_integer_ansi():
    """Verify INTEGER-OF-DATE and DATE-OF-INTEGER under ANSI."""
    assert evaluate_integer_of_date_ansi(16010101) == 1
    assert evaluate_date_of_integer_ansi(1) == 16010101
