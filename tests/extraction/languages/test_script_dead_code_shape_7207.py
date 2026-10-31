"""#7207 slices 4-6: python / shell / ruby / perl / php / lua / abap / ada / apex / dart dead_code counts a keyword-led comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = {
    "abap": [
        "* DATA lv_old TYPE i.",
        "* IF lv_x = 1.",
        "* SELECT * FROM mara INTO TABLE lt_mara.",
        "* WRITE 'hi'.",
        "* METHOD run.",
        "* DATA lv_x.",
        '" IF lv_a > 0.',
        "* WRITE: / 'x'.",
    ],
    "ada": [
        "-- if X > 0 then",
        "-- procedure Foo is",
        "-- for I in 1 .. 3 loop",
        "-- begin",
        "-- end Foo;",
        "-- function F (A : Integer) return Integer;",
        "-- type T is new Integer;",
        "-- package Util is",
    ],
    "apex": [
        "// public class Foo",
        "// class Foo extends Bar",
        "// if (x) {",
        "// insert acc;",
        "// System.debug('x');",
        "// [SELECT Id FROM Account]",
        "/* trigger T on Account (before insert) */",
        "// private with sharing class Svc",
    ],
    "dart": [
        "// class Foo extends Bar",
        "// mixin Util",
        "// if (x) {",
        "// print('x');",
        "// return x;",
        "/* void main() */",
        "// var x = foo();",
        "// Widget build(BuildContext c)",
    ],
    "ruby": [
        "# def foo(a)",
        "# class Foo < Bar",
        "# module Util",
        '# puts "x"',
        "# unless ready?(a)",
        "# if foo(1)",
        "# p @x",
    ],
    "perl": [
        "# my $x = 1;",
        "# sub foo {",
        "# package Foo::Bar",
        '# print "hi"',
        "# our @list",
        "# if ($x) {",
        "# say $y",
    ],
    "php": [
        "// function foo() {",
        "// class Foo extends Bar",
        "// use Foo\\Bar;",
        "/* foreach ($a as $b) { */",
        '// echo "x";',
        "// $x = 1;",
        "# $x = foo();",
        "// }",
        "// return $x;",
    ],
    "lua": [
        "-- local x = 1",
        "-- function foo(a)",
        "-- function M.foo",
        "-- return x",
        "-- if x > 3 then",
        '-- print("x")',
        "--[[ for i = 1, 3 do",
    ],
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
    "abap": [
        "* if the user cancels, we retry",
        "* write the total to the log.",
        "* data is read from the table.",
        "* Select the first row.",
        "* method for sorting",
        "* if the user cancels.",
        "* Data loaded.",
        "* IF the value from the list.",
    ],
    "ada": [
        "-- if the user cancels, we retry",
        "-- for each item in the list",
        "-- procedure call overhead is high",
        "-- begin the scan here",
        "-- end of the loop",
        "-- type of the result",
        "-- while waiting for input",
        "--- if x then",
    ],
    "apex": [
        "// if the user cancels, we retry",
        "// class names are capitalised",
        "// public API is stable",
        "// update the record later",
        "// for each item in the list",
        "// private data stays here",
        "// insert order matters",
        "// [SELECT is slow]",
    ],
    "dart": [
        "// if the user cancels, we retry",
        "// for each item in the list",
        "// return value is ignored",
        "// class names are capitalised",
        "// print the result later",
        "// void is not nullable",
        "// while waiting for input",
        "// mixin order matters",
    ],
    "ruby": [
        "# if the user cancels, we retry",
        "# class names are capitalised",
        "# def is a keyword",
        "# puts the result",
        "# p is short",
    ],
    "perl": [
        "# if the user cancels, we retry",
        "# my notes are below",
        "# sub is called twice",
        "# print the result",
        "# package names matter",
    ],
    "php": [
        "// if the user cancels, we retry",
        "// return value is ignored",
        "// use the cache",
        "// class names are capitalised",
        "// echo is slow",
        "/* foreach item in the list */",
        "// $x is the total",
        "//\n}",
    ],
    "lua": [
        "-- if the user cancels, we retry",
        "-- return value is ignored",
        "-- local variables are fast",
        "-- print the result",
        "--- if the user cancels, we retry",
        "-- function names are lowercase",
        "-- return value is ignored here",
    ],
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


MARKER = {"abap": "*", "ada": "--", "apex": "//", "dart": "//", "lua": "--", "php": "//"}


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
    m = MARKER.get(lang, "#")
    assert not _rule(lang).search(m + " if " + "(a " * 5000 + "\n")
    assert not _rule(lang).search(m + " def " + "a:" * 5000 + " x\n")
