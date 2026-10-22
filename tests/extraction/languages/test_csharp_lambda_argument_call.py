"""#5685: a C# call passing a lambda is not a definition of the callee (siblings of #5462)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _extraction_harness import assert_redos_immune  # type: ignore

RULES = LANGUAGE_DEFINITIONS["csharp"]["rules"]


def _names(payload):
    return [next((g for g in m.groups() if g), None) for m in RULES["func_start"].finditer(payload)]


# The enclosing method is the only definition: the lambda's `(x) =>` or a later `) {` used to match.
CALLS = [
    "void Outer(Node n) {\n    Walk( node, (x) => { Use(x); if (Check(x)) {\n",
    "void Outer(Node n) {\n    Walk(n, (x) =>\n    {\n        Use(x);\n        if (Check(x)) {\n",
    "void Outer(Node n) {\n    Walk(n, delegate (Node x) { Use(x); if (Check(x)) {\n",
    "void Outer(Node n) {\n    var r = Walk(n, x => { Use(x); if (Check(x)) {\n",
    "void Outer(Node n) {\n    Run(n, async (x) => { await Use(x); if (Check(x)) {\n",
    "void Outer(Node n) {\n    Walk(n, (x) => Use(x));\n    if (Check(n)) {\n",
]


@pytest.mark.parametrize("payload", CALLS)
def test_call_with_lambda_argument_is_not_a_definition(payload):
    assert _names(payload) == ["Outer"]


DEFINITIONS = [
    ("public int Run(Func<int, int> f = null) {", "Run"),
    ('int F(string s = "a", int[] a = null)\n{', "F"),
    ("bool Eq(int a) => a == 1;", "Eq"),
    ("void M() { }", "M"),
    ("int G(int a = H(J(1)))\n{", "G"),
]


@pytest.mark.parametrize("payload,name", DEFINITIONS)
def test_parameter_lists_still_match(payload, name):
    assert _names(payload) == [name]


@pytest.mark.parametrize(
    "payload",
    [
        "f(" + "a, (b) => c, " * 400,
        "f(" + "(" * 400,
        "f(a, (x) => {" + " g(x);" * 400,
    ],
)
def test_parameter_block_redos(payload):
    assert_redos_immune(RULES["func_start"], payload)
