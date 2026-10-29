# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL MOVE rules matrix (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative move rules, permissible matrix, and test vectors execute
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
from gitgalaxy.standards.cobol.move import (
    ACTIONS,
    CATEGORIES,
    KINDS,
    MOVE_MATRIX,
    MOVE_RULES,
    MOVE_VECTORS,
)


def test_cobol_standards_spec_has_no_problems():
    """Verify internal consistency of standards/cobol rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_standards_generated_files_are_not_stale():
    """Verify committed MoveSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_kinds_and_categories_defined():
    """Verify 9 Field.Kind entries exist and map cleanly."""
    assert len(KINDS) == 9
    assert len(CATEGORIES) == 5
    assert len(ACTIONS) == 14
    assert len(MOVE_MATRIX) == 81


@pytest.mark.parametrize("vec", MOVE_VECTORS, ids=lambda v: v.id)
def test_move_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in MOVE_RULES
    meta = MOVE_RULES[vec.rule_id]
    assert meta.id == vec.rule_id
    assert len(vec.input_bytes) > 0
    assert len(vec.expected_bytes) > 0


def test_same_zoned_shape_memcpy_invariance():
    """Verify rule RT-CBL-MOVE-SAME-ZONED-SHAPE (register C11): non-digits and sign are preserved."""
    vec = next(v for v in MOVE_VECTORS if v.id == "MV06-same-zoned-shape-memcpy")
    assert vec.input_bytes == vec.expected_bytes
    assert b" " in vec.input_bytes  # Contains non-digit space
    assert b"K" in vec.input_bytes  # Contains negative overpunch


def test_numeric_to_alnum_unpunches_sign():
    """Verify rule RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC: sign is de-punched into unsigned digit."""
    vec = next(v for v in MOVE_VECTORS if v.id == "MV07-numeric-to-alnum-unpunch")
    assert vec.input_bytes == b"0001K"
    assert vec.expected_bytes == b"00012"  # K (-2) -> 2
