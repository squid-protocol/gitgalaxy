# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL SORT and MERGE rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative sort rules, key comparisons, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.sort_ops import (
    COLLATING_EBCDIC,
    COLLATING_LITERAL,
    COLLATING_NAMES,
    COLLATING_NATIVE,
    DIRECTION_NAMES,
    PHRASE_NAMES,
    SORT_RULES,
    SORT_VECTORS,
    execute_collating_compare,
    execute_merge,
    execute_sort,
)


def test_cobol_sort_spec_has_no_problems():
    """Verify internal consistency of standards/cobol sort rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_sort_generated_files_are_not_stale():
    """Verify committed SortSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_sort_rules_and_constants_defined():
    """Verify sort rules, direction names, and collating modes are defined."""
    assert len(SORT_RULES) == 7
    assert len(DIRECTION_NAMES) == 2
    assert len(COLLATING_NAMES) == 3
    assert len(PHRASE_NAMES) == 4
    assert len(SORT_VECTORS) >= 15


@pytest.mark.parametrize("vec", SORT_VECTORS, ids=lambda v: v.id)
def test_sort_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in SORT_RULES
    meta = SORT_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", SORT_VECTORS, ids=lambda v: v.id)
def test_sort_simulation_all_vectors(vec):
    """Verify pure-Python simulation produces expected output for each vector."""
    got = execute_sort(
        vec.records,
        vec.keys,
        collating=vec.collating,
        alphabet_entries=vec.alphabet_entries,
    )
    assert got == vec.expected, f"{vec.id}: expected {vec.expected!r}, got {got!r}"


def test_merge_simulation_two_files():
    """Verify merge of two pre-sorted files preserves file order on equal keys."""
    from gitgalaxy.standards.cobol.sort_ops import SortKeySpec

    file1 = ["010 FILE1-A", "030 FILE1-B"]
    file2 = ["010 FILE2-A", "020 FILE2-B"]
    keys = [SortKeySpec(offset=0, length=3, is_numeric=True, ascending=True)]
    merged = execute_merge([file1, file2], keys)
    assert merged == ["010 FILE1-A", "010 FILE2-A", "020 FILE2-B", "030 FILE1-B"]


def test_collating_compare_ebcdic():
    """Verify PROGRAM COLLATING SEQUENCE character ordering."""
    # Under EBCDIC: 'A' precedes '1'
    assert execute_collating_compare("A", "1", collating=COLLATING_EBCDIC) < 0
    # Under Native (ASCII): '1' precedes 'A'
    assert execute_collating_compare("A", "1", collating=COLLATING_NATIVE) > 0
