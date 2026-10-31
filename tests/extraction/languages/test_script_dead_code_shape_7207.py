"""#7207 slice 4: python / shell dead_code counts a keyword-led `#` comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = {
    "python": [
        "# def foo(a, b):",
        "# class Foo:",
        "# import os",
        "# import os.path as p",
        "# if x > 3:",
        "# for i in range(3):",
        "# while True:",
        "# try:",
        "# return compute(a)",
    ],
    "shell": [
        "# if [ -f x ]; then",
        "# for f in *; do",
        '# echo "done"',
        "# echo $HOME",
        "# rm -rf build && ls",
        "# rm -rf /tmp/cache",
        "# ls -la",
        "# export PATH=/x:$PATH",
        "# function foo {",
        "# cd /tmp && ls",
        "# ls | wc -l",
    ],
}

NEGATIVES = {
    "python": [
        "# if the user cancels, we retry",
        "# for each item in the list",
        "# return value is ignored",
        "# import order matters",
        "# while waiting for input",
        "# class names are capitalised.",
        "# try again later",
        "# def is a keyword",
    ],
    "shell": [
        "# if the user cancels, we retry",
        "# for each item in the list",
        "# function names are lowercase",
        "# export is a builtin",
        "# cd to the build dir first",
        "# while waiting for input",
        "# echo is slow here",
        "# rm removes files",
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
    assert not _rule(lang).search("# if " + "(a " * 5000 + "\n")
    assert not _rule(lang).search("# def " + "a:" * 5000 + " x\n")
