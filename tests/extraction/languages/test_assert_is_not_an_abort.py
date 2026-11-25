"""`assert` is not an abort for `panics_and_aborts` (owner ruling 2026-11-24, #8862; part of #8863).

The contract names a throw/raise, panic, unreachable marker, fatal-error, revert or process exit. A runtime assertion is a
check (the `safety` family's), so no language's `panics_and_aborts` rule may count a bare assertion. Two forms that ARE
contract forms stay: OCaml `assert false` (an unreachable marker) and Nim `raiseAssert` (an unconditional raise).
"""

import re

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# language -> the assertion-named forms that are abort forms by the contract wording
ALLOWED = {
    "ocaml": ["assert false"],
    "nim": ["raiseAssert"],
}

BARE_ASSERTS = [
    "assert x > 0",
    "assert(x > 0);",
    "assert_eq!(a, b);",
    "ASSERT x > 0;",
    "@assert x > 0",
    "static_assert(x, 'm');",
    "assertTrue(x)",
]


def _abort_rules():
    for name, definition in LANGUAGE_DEFINITIONS.items():
        rule = definition.get("rules", {}).get("panics_and_aborts")
        if hasattr(rule, "search"):
            yield name, rule


@pytest.mark.parametrize("lang,rule", list(_abort_rules()), ids=lambda v: v if isinstance(v, str) else "")
def test_a_bare_assertion_is_not_an_abort(lang, rule):
    for line in BARE_ASSERTS:
        assert not rule.search(line), f"{lang}: panics_and_aborts counts {line!r}"


def test_the_allowed_forms_are_still_abort_forms():
    rules = dict(_abort_rules())
    for lang, forms in ALLOWED.items():
        for form in forms:
            assert rules[lang].search(form), (lang, form)


def test_julia_and_postgresql_keep_their_real_abort_forms():
    rules = dict(_abort_rules())
    assert rules["julia"].search('error("boom")') and rules["julia"].search("throw(ArgumentError())")
    assert rules["postgresql"].search("RAISE EXCEPTION 'x';")
    assert re.search(r"RAISE", "RAISE;") and rules["postgresql"].search("  RAISE;")
