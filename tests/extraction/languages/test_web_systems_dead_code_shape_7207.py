"""#7207 slice 2: csharp / typescript / javascript / rust dead_code counts a keyword-led comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = {
    "csharp": [
        "// public void Foo() {}",
        "// private int x = 3;",
        "// using System.Linq;",
        "/* return Compute(a, b); */",
        "// foreach (var s in list) {",
    ],
    "typescript": [
        "// if (x) foo();",
        "// export const a = 1;",
        "// import { a } from './a';",
        "/* function foo(a: number) { */",
        "// return x;",
    ],
    "javascript": [
        "// const a = require('a');",
        "// let n = 0",
        "// var x = foo(1);",
        "// function foo(a) {",
        "// for (const s of list) {",
    ],
    "rust": [
        "// let mut x = 5;",
        "// use std::fmt;",
        "// fn foo(a: i32) -> i32 {",
        "/* match x { */",
        "// loop {",
        "// return Ok(());",
    ],
}

NEGATIVES = {
    "csharp": [
        "// public API, do not change",
        "// using the cache when present",
        "// class names are capitalised.",
        "// return value is ignored",
        "// if the user cancels, we retry",
        "/// for each item in the list",
    ],
    "typescript": [
        "// import order matters",
        "// export the table when ready",
        "// function names are capitalised.",
        "// return the cached copy when present",
        "// while waiting for input",
        "/* if the list is empty, skip */",
        "/* return value (see below) is ignored. */",
    ],
    "javascript": [
        "// const values are frozen",
        "// let the caller decide",
        "// var is function scoped",
        "// import order matters",
        "// for each item in the list",
        "// if the user cancels, we retry",
    ],
    "rust": [
        "// use the cached copy when present",
        "// fn pointers are not closures",
        "// let the caller decide",
        "// match the piece against the board",
        "// loop until the buffer is empty",
        "// return value is ignored",
        "// mod names are lowercase",
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
