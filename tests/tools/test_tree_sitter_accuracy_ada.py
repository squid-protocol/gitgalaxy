"""Ada in the tree-sitter accuracy audit: what counts as a function, how its name and parameters are read.
GitGalaxy's Ada func_start matches only a subprogram that has a body, so the reference does too."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tree_sitter_accuracy_audit as audit

ts = pytest.importorskip("tree_sitter_language_pack")

SRC = b"""package body P is
  procedure Foo (L, R : Boolean; X : in out Integer) is begin null; end Foo;
  function Bar return Integer is begin return 1; end Bar;
  function Baz (Y : Integer) return Integer is (Y + 1);
  procedure Spec_Only (Z : Integer);
  procedure Nul is null;
end P;
"""


def _nodes():
    tree = ts.get_parser("ada").parse(SRC)
    found = {}

    def walk(n):
        if n.type in audit.NODE_MAPS["ada"]["func_node_types"]:
            found[audit._get_node_name(n)] = n
        for c in n.children:
            walk(c)

    walk(tree.root_node)
    return found


def test_bodies_and_expression_functions_count_but_specs_and_null_procedures_do_not():
    assert set(_nodes()) == {"Foo", "Bar", "Baz"}  # Spec_Only (a declaration) and Nul (is null) are not functions


def test_parameter_count_counts_every_name_in_a_shared_declaration():
    nodes = _nodes()
    assert audit._get_param_count(nodes["Foo"], "ada") == 3  # L, R and X
    assert audit._get_param_count(nodes["Bar"], "ada") == 0
    assert audit._get_param_count(nodes["Baz"], "ada") == 1


def test_ada_is_measured_and_no_longer_listed_as_gitgalaxy_only():
    assert "ada" in audit.NODE_MAPS
    assert "ada" not in audit._gg_only_langs()
