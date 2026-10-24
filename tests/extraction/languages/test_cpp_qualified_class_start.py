"""#3772: a class written with its namespace qualifier (`struct fmt::formatter<T>`) is the unit `formatter<T>`."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]

CASES = [
    ("struct fmt::formatter<Foo> {", "formatter<Foo>"),
    ("template <> struct std::hash<Foo> {", "hash<Foo>"),
    ("class a::b::C : public Base {", "C"),
    ("struct Plain {", "Plain"),
    ("class Vec<int> {", "Vec<int>"),
]


@pytest.mark.parametrize("payload,name", CASES)
def test_class_start_takes_the_last_qualified_segment(payload, name):
    m = RULES["class_start"].search(payload)
    got = m.group(1) if m else None
    if got != name:
        pytest.fail(f"{payload!r}: got {got!r}, want {name!r}")


def test_class_start_qualifier_walk_is_bounded():
    payload = "struct " + "a::" * 5000 + "{"
    RULES["class_start"].search(payload)
