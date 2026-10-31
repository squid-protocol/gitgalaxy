"""#7207 slice 2: c / cpp / java dead_code counts a keyword-led comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

LANGS = ["c", "cpp", "java"]

POSITIVES = {
    "c": [
        "// if (x) foo();",
        "// if (x) {",
        "// for (i = 0; i < n; i++) {",
        "/* while (running) { */",
        "// return x;",
        "// return foo(x)",
        "// int count = 0;",
        "// struct node {",
        "/* void helper(int a) */",
    ],
    "cpp": [
        "// auto it = v.begin();",
        "// std::cout << x << '\\n';",
        '// printf("%d", x);',
        "// class Foo {",
        "/* if (p) delete p; */",
    ],
    "java": [
        "// public void foo() {}",
        "// private int x = 3;",
        "// import java.util.List;",
        "/* return compute(a, b); */",
        "// for (String s : list) {",
    ],
}

NEGATIVES = [
    "// if the user cancels, we retry",
    "// for each item in the list",
    "// while waiting for input",
    "// return value is ignored",
    "// return the cached copy when present",
    "// void if the buffer is empty",
    "// int overflow is undefined here",
    "// struct layout matters for the ABI",
    "// public API, do not change",
    "// import order matters",
    "// class names are capitalised.",
    "/* if the list is empty, skip */",
    "/// return value is the count",
    "/* return value (see below) is ignored. */",
]


@pytest.mark.parametrize("lang,line", [(lang, ln) for lang in LANGS for ln in POSITIVES[lang]])
def test_commented_out_statement_counts(lang, line):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"].search(line + "\n")


@pytest.mark.parametrize("lang,line", [(lang, ln) for lang in LANGS for ln in NEGATIVES])
def test_prose_does_not_count(lang, line):
    assert not LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"].search(line + "\n")


def test_long_line_stays_fast():
    rule = LANGUAGE_DEFINITIONS["c"]["rules"]["dead_code"]
    assert not rule.search("// if " + "(a " * 5000 + "\n")
