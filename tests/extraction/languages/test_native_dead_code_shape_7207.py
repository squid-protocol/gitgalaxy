"""#7207 slice 3: go / kotlin / swift dead_code counts a keyword-led `//` comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = {
    "go": [
        "// func foo(a int) int {",
        "// const n = len(a)",
        "// var n = 3",
        "// if err != nil {",
        "// for i := 0; i < n; i++ {",
        '// return fmt.Errorf("bad")',
        "// switch x {",
    ],
    "kotlin": [
        "// val x = 3",
        "// fun foo(a: Int): Int {",
        "// if (x > 0) {",
        "// return compute(a)",
        "// for (s in list) {",
        "// var n: Int = 0",
    ],
    "swift": [
        "// let x = 3",
        "// func foo(a: Int) -> Int {",
        "// guard let y = x else { return }",
        "// if x > 0 {",
        "// return compute(a)",
        "// var n: Int = 0",
    ],
}

NEGATIVES = {
    "go": [
        "// if the user cancels, we retry",
        "// for each item in the list",
        "// return value is ignored",
        "// type switches are exhaustive here",
        "// import order matters",
        "// select the first ready channel",
        "// var is deprecated in this style",
        "// func literals capture by reference",
    ],
    "kotlin": [
        "// if the user cancels, we retry",
        "// for each item in the list",
        "// return value is ignored",
        "// val is immutable",
        "// object identity is not preserved",
        "// when the list is empty, skip",
        "// import order matters",
    ],
    "swift": [
        "// if the user cancels, we retry",
        "// return value is ignored",
        "// guard against nil input",
        "// let the caller decide",
        "// extension points live elsewhere",
        "// class names are capitalised.",
        "// var is mutable",
    ],
}


def _rule(lang):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"]


@pytest.mark.parametrize("lang,line", [(lang, ln) for lang, lns in POSITIVES.items() for ln in lns])
def test_commented_out_statement_counts(lang, line):
    assert _rule(lang).search(line + "\n")


@pytest.mark.parametrize("lang,line", [(lang, ln) for lang, lns in NEGATIVES.items() for ln in lns])
def test_prose_does_not_count(lang, line):
    assert not _rule(lang).search(line + "\n")


@pytest.mark.parametrize("lang", list(POSITIVES))
def test_long_line_stays_fast(lang):
    assert not _rule(lang).search("// if " + "(a " * 5000 + "\n")
