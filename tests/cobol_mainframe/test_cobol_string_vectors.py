# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL String Manipulation rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative string rules, inspect modes, phrase types,
and deterministic test vectors execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.string_ops import (
    INSPECT_MODES,
    PHRASE_TYPES,
    STRING_RULES,
    STRING_VECTORS,
    execute_string,
    execute_unstring,
)


def test_cobol_string_spec_has_no_problems():
    """Verify internal consistency of standards/cobol string manipulation rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_string_generated_files_are_not_stale():
    """Verify committed StringSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_string_modes_and_rules_defined():
    """Verify inspect modes, phrase types, and string rules are defined."""
    assert len(INSPECT_MODES) == 4
    assert len(PHRASE_TYPES) == 3
    assert len(STRING_RULES) == 4
    assert len(STRING_VECTORS) >= 14


@pytest.mark.parametrize("vec", STRING_VECTORS, ids=lambda v: v.id)
def test_string_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in STRING_RULES
    meta = STRING_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_string_simulation_basic_and_no_pad():
    """Verify STRING statement simulation preserves unwritten receiver positions."""
    out, ptr, ovf = execute_string("ABCDEFGHIJ", [("123", None)], pointer=1)
    assert out == "123DEFGHIJ"
    assert ptr == 4
    assert not ovf


def test_string_simulation_overflow():
    """Verify STRING overflow on receiver capacity exceeded."""
    out, ptr, ovf = execute_string("..........", [("1234567890EXTRA", None)], pointer=1)
    assert out == "1234567890"
    assert ptr == 11
    assert ovf


def test_unstring_simulation_delimited_by_all():
    """Verify UNSTRING simulation with DELIMITED BY ALL."""
    results, ptr, ovf = execute_unstring("ONE    TWO   THREE", [(" ", True)], [5, 5, 5], pointer=1)
    assert results == ["ONE  ", "TWO  ", "THREE"]
    assert ptr == 19
    assert not ovf
