# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""The shared function-population predicate (#4110)."""

import ast
from pathlib import Path

import pytest

from gitgalaxy.core.function_population import is_population_function, population_functions

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "unit,expected",
    [
        ({"name": "f"}, True),
        ({"name": "__global_context__", "is_synthetic_slice": True}, False),
        ({"name": "__global_context__", "is_synthetic_slice": True, "calls_only": True}, False),
        ({"name": "__global_context__", "calls_only": True}, False),
        ({"name": "Anonymous_Block", "is_synthetic_slice": True}, False),
        ("not-a-dict", False),
        (None, False),
    ],
)
def test_is_population_function(unit, expected):
    assert is_population_function(unit) is expected


def test_population_functions_handles_none():
    assert population_functions(None) == []
    assert population_functions([{"name": "f"}, {"name": "x", "is_synthetic_slice": True}]) == [{"name": "f"}]


# Sites that LIST or COUNT functions for reporting must use the shared predicate,
# not hand-pick a flag (#4110). Sites that deliberately keep synthetic slices
# (file mass, the archetype feature trained with its own definition, language
# identity) are not listed here.
_REPORTING_MODULES = [
    "gitgalaxy/recorders/audit_recorder.py",
    "gitgalaxy/recorders/llm_recorder.py",
    "gitgalaxy/recorders/record_keeper.py",
]


@pytest.mark.parametrize("rel", _REPORTING_MODULES)
def test_reporting_modules_use_the_shared_predicate(rel):
    src = (REPO_ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert names & {"is_population_function", "population_functions"}, rel
    # No hand-rolled calls_only filter left for counting/listing.
    assert 'not func.get("calls_only")' not in src and 'not u.get("calls_only")' not in src, rel
