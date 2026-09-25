"""span_anchor_audit.py (#3543): a start_line on the line that ENDS other code is
mis-anchored; one on an annotation, attribute or return type is not."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import span_anchor_audit as saa


def test_the_3543_shapes_are_misanchored():
    ts = ["export class A {", "  constructor(x: number) {}", "}"]
    assert saa.misanchored(ts, 1, "constructor", "typescript") is True
    member = ["  a: () => 1,", "  b: () => 2,"]
    assert saa.misanchored(member, 1, "b", "typescript") is True
    php = ["/**", " * Docs.", " */", "function f() {}"]
    assert saa.misanchored(php, 3, "f", "php") is True


def test_declaration_prefix_lines_are_not_misanchored():
    assert saa.misanchored(["@Override", "public void run() {"], 1, "run", "java") is False
    assert saa.misanchored(["#[inline]", "fn run() {"], 1, "run", "rust") is False
    assert saa.misanchored(["static int", "run(void) {"], 1, "run", "c") is False
    assert saa.misanchored(["template <typename T>", "T run(T x) {"], 1, "run", "cpp") is False
    assert saa.misanchored(["def run():"], 1, "run", "python") is False


def test_unjudgeable_units_are_skipped():
    assert saa.misanchored(["x"], 5, "run", "c") is None  # out of range
    assert saa.misanchored(["{", "}"], 1, "run", "c") is None  # name never appears


def test_regressions_read_a_rise_and_skip_small_languages():
    base = {"php": {"units": 100, "misanchored_pct": 20.0}, "kotlin": {"units": 5, "misanchored_pct": 0.0}}
    assert saa.regressions({"php": {"misanchored_pct": 20.4}, "kotlin": {"misanchored_pct": 40.0}}, base) == []
    assert saa.regressions({"php": {"misanchored_pct": 21.0}}, base) == ["php: misanchored_pct 20.0 -> 21.0"]
    assert saa.regressions({"php": {"misanchored_pct": 0.0}}, base) == []  # a fix is never a regression
