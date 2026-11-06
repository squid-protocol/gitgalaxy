"""#7863 (siblings of #4108): an alternation member that starts with a non-word char must not sit behind a
leading `\\b`, which can never match after whitespace or punctuation."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

JAVA_RULES = LANGUAGE_DEFINITIONS["java"]["rules"]
KOTLIN_RULES = LANGUAGE_DEFINITIONS["kotlin"]["rules"]
SCALA_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]


@pytest.mark.parametrize(
    "line",
    [
        "boolean ok = s.matches(re);",  # after a word char (matched before)
        'boolean ok = "abc".matches("a.c");',  # after a quote, string-literal arg
        "boolean ok = f().matches(re);",  # after a paren
        "boolean ok = a\n    .matches(re);",  # after whitespace
        "Pattern.compile(re);",
        "m.find();Matcher.find(x)",
    ],
)
def test_java_regex_execution_matches(line):
    assert JAVA_RULES["regex_execution"].search(line)


@pytest.mark.parametrize("line", ["Pattern.quote(re);", "xPattern.compile(re)", "s.matched(re)"])
def test_java_regex_execution_negatives(line):
    assert not JAVA_RULES["regex_execution"].search(line)


@pytest.mark.parametrize(
    "line",
    ["if (x !is String) {", "if (!(x !is Foo)) {", "when (v) { !is Int -> 1 }", "if (x is String) {", "check(x)"],
)
def test_kotlin_safety_not_is(line):
    assert KOTLIN_RULES["safety"].search(line)


def test_kotlin_not_is_counts_once():
    assert len(KOTLIN_RULES["safety"].findall("x !is String")) == 1


@pytest.mark.parametrize("line", ["val this_is = 1", "val x = islands"])
def test_kotlin_safety_negatives(line):
    assert not KOTLIN_RULES["safety"].search(line)


@pytest.mark.parametrize(
    "line",
    ["val v = !ptr", "val v = (!ptr)", "p(!ptr)", "val v = ptr.value", "import scala.scalanative.unsafe._", "CFuncPtr"],
)
def test_scala_pointers(line):
    assert SCALA_RULES["pointers"].search(line)


@pytest.mark.parametrize("line", ["val v = a!ptr", "val v = !ptrs", "val v = a-!ptr", "x != ptr"])
def test_scala_pointers_negatives(line):
    assert not SCALA_RULES["pointers"].search(line)
