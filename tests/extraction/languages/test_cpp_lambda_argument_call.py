"""#5462: a call passing a lambda after its first argument is not a definition of the callee."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _extraction_harness import assert_redos_immune  # type: ignore

RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]


def _names(payload):
    return [next((g for g in m.groups() if g), None) for m in RULES["func_start"].finditer(payload)]


# The enclosing definition is the only one: the call's lambda body used to reach a later `) {`.
CALLS = [
    # body with a statement before the next `) {`, behind a post-parameter tail
    "void outer(item_t& n) {\n"
    "    walk(\n"
    "        n,\n"
    "        [&](const item_t& it) noexcept {\n"
    "            const int v = get(it);\n"
    "            if (keep(v)) {\n",
    # no statement before the next `) {`
    "void outer(item_t& n) {\n    walk(n, [&](const item_t& it) {\n        if (check(it)) {\n",
    # comment between the capture and the body (opening brace on its own line)
    "void outer(item_t& n) {\n    walk(n, x, [&](item_t* s) // each one\n    {\n        use(s);\n        if (f(s)) {\n",
    # trailing return type, stateless capture
    "void outer(item_t& n) {\n    walk(n, [](item_t* s, void* c) -> bool {\n        if (!ok(s)) {\n",
    # an event binding with a mutable lambda
    "void outer(item_t& n) {\n    Bind(EV_IDLE, [this](Event& e) mutable\n    {\n        for (auto it = b(); it != e(); ++it)\n        {\n",
    # a GNU statement expression as an argument
    "void outer(item_t& n) {\n    run(n, ({ int y = g(n); y; }),\n        n);\n    if (h(n)) {\n",
]


@pytest.mark.parametrize("payload", CALLS)
def test_call_with_lambda_argument_is_not_a_definition(payload):
    assert _names(payload) == ["outer"]


# Parameter lists that keep matching: brace-init defaults, function pointers, arrays.
DEFINITIONS = [
    ("void f(std::vector<int> v = {}) {", "f"),
    ("void f(Pt p = {1, 2}, int q = 3) {", "f"),
    ("void f(\n    Pt p = { 1, 2 },\n    int q) {", "f"),
    ("void f(void (*cb)(int), int n) {", "f"),
    ("int f(const char* const names[], int (&arr)[4]) {", "f"),
    ("Widget::Widget(int a, Opts o = {})\n    : a_(a), o_(o)\n{", "Widget::Widget"),
]


@pytest.mark.parametrize("payload,name", DEFINITIONS)
def test_parameter_lists_still_match(payload, name):
    assert _names(payload) == [name]


@pytest.mark.parametrize(
    "payload",
    [
        "f(" + "a, {b}, " * 400,
        "f(" + "{" * 400,
        "f(a, [&](int x) {" + " g(x);" * 400,
    ],
)
def test_parameter_block_redos(payload):
    assert_redos_immune(RULES["func_start"], payload)
