"""Go decorators (#9343): a `//go:` pragma directly above a func counts; a blank line detaches it; the oracle reads `re.MatchString`."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import _go_leading_pragmas

sys.path.insert(0, str(Path(__file__).parent / "tools"))
import family_oracle_ts


def _above(src: str) -> int:
    lines = src.splitlines()
    return _go_leading_pragmas(lines, next(i for i, ln in enumerate(lines, 1) if ln.startswith("func f")))


@pytest.mark.parametrize(
    ("src", "n"),
    [
        ("package p\n//go:noinline\nfunc f() {}\n", 1),
        ("//go:nosplit\n//go:noinline\nfunc f() {}\n", 2),
        ("//go:noinline\n// f does a thing.\nfunc f() {}\n", 1),
        ("// f does a thing.\n//go:noinline\nfunc f() {}\n", 1),
        ("//go:build linux\nfunc f() {}\n", 1),
        ("//go:noinline\n\nfunc f() {}\n", 0),
        ("// just a comment\nfunc f() {}\n", 0),
        ("//go:noinline\nvar x = 1\nfunc f() {}\n", 0),
        ("// go:noinline\nfunc f() {}\n", 0),
        ("func f() {}\n", 0),
    ],
)
def test_leading_pragmas(src, n):
    assert _above(src) == n


def test_oracle_regex_reads_method_calls():
    pats = family_oracle_ts.SPECS["go"].calls["regex"]
    m = family_oracle_ts._matches
    assert m("re.MatchString", pats) and m("m.re.MatchString", pats) and m("regexp.MustCompile", pats)
    assert not m("x.MatchStrings", pats)
