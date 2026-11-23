"""
#8908: Perl `branch`, `decorators` and `bitwise_ops` do not read string or regex-literal text
as code, and a ternary is one decision counted at its `?` (as java/ruby, #2833).
Goes through the real extractor: the `perl_literals` scope filter never runs on a bare regex.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _counts(code: str) -> tuple[int, int, int]:
    from gitgalaxy.core.detector import StructuralExtractor

    counts, *_ = StructuralExtractor("perl", LANGUAGE_DEFINITIONS).coding_analysis([("perl", code, 0)])
    return counts["branch"], counts["bitwise_ops"], counts["decorators"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # the issue's measured cases
        ("sub tern { my $a = shift; return $a ? 1 : 2; }", (1, 0, 0)),
        ("sub rx { my $s = shift; return $s =~ /^(?:a|b)$/; }", (0, 0, 0)),
        ('sub dsn { return "dbi:mysql:host"; }', (0, 0, 0)),
        ("sub real_if { my $a = shift; if ($a) { return 1 } return 0 }", (1, 0, 0)),
        # the rest of the class
        ("sub f { my $s = shift; return $s =~ m{^(?:a|b)$}x; }", (0, 0, 0)),
        ("sub f { my $s = shift; return qr/(?:a|b)/; }", (0, 0, 0)),
        ("sub f { my $s = shift; $s =~ s/(?:a|b)/x/g; return $s; }", (0, 0, 0)),
        ("sub f { my $s = shift; $s =~ s{(?:a|b)}{x:y}g; return $s; }", (0, 0, 0)),
        ("sub f { my $s = shift; return split /\\|/, $s; }", (0, 0, 0)),
        ("sub f { return 'if a ? b : c'; }", (0, 0, 0)),
        ('sub f { return "a if b"; }', (0, 0, 0)),
        # still code
        ("sub f { my $x = shift; return $x // 0; }", (1, 0, 0)),
        ("sub f { my $x = shift; return $x / 2 + 1 ? 1 : 0; }", (1, 0, 0)),
        ("sub f { my $x = shift; return $x | 4; }", (0, 1, 0)),
        ("sub f { my $x = shift; return $x ? ($x ? 1 : 2) : 3; }", (2, 0, 0)),
        ("sub f { Foo::Bar->new; }", (0, 0, 0)),
    ],
)
def test_perl_literal_and_ternary_counts(code, expected):
    assert _counts(code) == expected


def test_perl_literal_shield_redos_immune():
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from _timing import assert_cpu_below

    from gitgalaxy.core.detector import _build_perl_safe_stream

    # unterminated openers and slash runs: honest cost is a few ms, a backtracking blowup is seconds
    for poison in ('"' + "\\a" * 20000, "'" + "a" * 20000, "s/" + "a/" * 20000, "m{" + "{a}" * 20000, "/ " * 20000):
        assert_cpu_below(lambda p=poison: _build_perl_safe_stream(p), 1.0, what="perl literal shield")
