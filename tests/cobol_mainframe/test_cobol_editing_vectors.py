# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL Numeric Editing rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative editing rules, symbol categories, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
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
from gitgalaxy.standards.cobol.editing import (
    EDIT_CATEGORY_NAMES,
    EDITING_RULES,
    EDITING_SYMBOLS,
    EDITING_VECTORS,
    execute_editing,
    execute_shape,
    expand_picture,
)


def test_cobol_editing_spec_has_no_problems():
    """Verify internal consistency of standards/cobol numeric editing rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_editing_generated_files_are_not_stale():
    """Verify committed EditingSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_editing_symbols_and_rules_defined():
    """Verify editing symbols, categories, and rules are defined."""
    assert len(EDIT_CATEGORY_NAMES) == 7
    assert len(EDITING_SYMBOLS) == 14
    assert len(EDITING_RULES) == 5
    assert len(EDITING_VECTORS) >= 30


@pytest.mark.parametrize("vec", EDITING_VECTORS, ids=lambda v: v.id)
def test_editing_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in EDITING_RULES
    meta = EDITING_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", EDITING_VECTORS, ids=lambda v: v.id)
def test_editing_simulation_all_vectors(vec):
    """Verify pure-Python simulation produces expected output for each vector."""
    got = execute_editing(
        vec.picture,
        vec.value,
        decimal_comma=vec.decimal_comma,
        currency=vec.currency,
        raw_digits=vec.raw_digits,
        negative=vec.negative,
    )
    assert got == vec.expected, f"{vec.id}: expected {vec.expected!r}, got {got!r}"


def test_editing_picture_shape_simulation():
    """Verify shape calculation for integer and decimal digit positions."""
    assert execute_shape("ZZ,ZZ9.99") == (5, 2)
    assert execute_shape("Z(4)9(2).9(3)") == (6, 3)
    assert execute_shape("ZZ.ZZ9,99", decimal_comma=True) == (5, 2)
    assert execute_shape("$$$,$$9.99") == (5, 2)
    assert execute_shape("999B999") == (6, 0)


def test_editing_picture_expansion():
    """Verify repetition expansion in PICTURE strings."""
    assert expand_picture("Z(4)9(2)") == "ZZZZ99"
    assert expand_picture("9(3)V9(2)") == "999V99"
    assert expand_picture("S9(4)") == "9999"
