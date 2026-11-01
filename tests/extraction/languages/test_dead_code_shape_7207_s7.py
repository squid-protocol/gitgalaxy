"""#7207 slice 7: acs / crystal / db2_sql / easytrieve dead_code counts a keyword-led comment only with a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = {
    "acs": [
        "// if (x > 1) {",
        "// while (1)",
        "// return x;",
        "// script 1 OPEN",
        "// function int Foo(int a)",
        "// Delay(35);",
    ],
    "crystal": [
        "# def foo(a)",
        "# def foo",
        "# class Foo < Bar",
        "# struct Point",
        "# module Util",
        "# if x > 1",
        "# unless a.empty?",
        '# puts "x"',
    ],
    "db2_sql": [
        "-- SELECT * FROM t;",
        "-- select a, b FROM t where a > 1",
        "-- INSERT INTO t VALUES (1)",
        "-- UPDATE t SET a = 1",
        "-- DELETE FROM t",
        "-- CREATE TABLE t",
        "-- DROP INDEX ix1",
        "-- CALL MYPROC",
        "-- CALL myproc(1)",
        "-- DECLARE c1 CURSOR FOR",
        "-- COMMIT",
        "/* GRANT SELECT ON t TO u */",
    ],
    "easytrieve": [
        "* IF A = 1",
        "* IF AMT GT 100",
        "* PERFORM CLEANUP",
        "* GET INFILE",
        "* PUT OUTFILE",
        "* JOB INPUT INFILE",
        "* MACRO",
        "* MACRO MYMAC",
    ],
}

NEGATIVES = {
    "acs": [
        "// if the user cancels, we retry",
        "// for each item in the list",
        "// return value is ignored",
        "// script names are numbers",
        "// function of this block",
        "// while waiting for input",
    ],
    "crystal": [
        "# if the user cancels, we retry",
        "# class names are capitalised",
        "# def is a keyword",
        "# puts the item back",
        "# module order matters",
        "# p is for print",
        "# while waiting for input",
        "# struct layout is fixed",
    ],
    "db2_sql": [
        "-- select the first row",
        "-- update the record later",
        "-- create a new table here",
        "-- call this once at startup",
        "-- delete old rows nightly",
        "-- declare the cursor first",
        "-- drop the index when done",
        "-- commit often",
        "--- SELECT * FROM t",
    ],
    "easytrieve": [
        "* if the user cancels, we retry",
        "* get the next record",
        "* put the value back",
        "* perform cleanup after the loop",
        "* job runs nightly",
        "* macro expansion is lazy",
        "* If the total is large, stop",
    ],
}

MARKER = {"acs": "//", "crystal": "#", "db2_sql": "--", "easytrieve": "*"}


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
    m = MARKER[lang]
    assert not _rule(lang).search(m + " if " + "(a " * 5000 + "\n")
    assert not _rule(lang).search(m + " def " + "a:" * 5000 + " x\n")
    assert not _rule(lang).search(m + " select " + "a " * 5000 + "\n")
