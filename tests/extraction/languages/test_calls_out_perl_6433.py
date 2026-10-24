"""
#6433: Perl calls without parentheses. `CALLS_OUT_C_STYLE` needed `name(`; `CALLS_OUT_PERL` also
takes a `->method`, a bare unary built-in, and a statement-opening command with an argument. A
bare word is never a call: Perl cannot tell it from a bareword without a symbol table.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_PERL,
    QUALIFIED_CALLS_OUT_PATTERNS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _callees(line: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_PERL.finditer(line)]


@pytest.mark.parametrize(
    "line, expected",
    [
        # method calls, parens or not
        ("$o->save($x);", ["save"]),
        ("my $v = $o->name;", ["name"]),
        ("$o->a->b;", ["a", "b"]),
        ("$class->SUPER::new(%args);", ["new"]),
        ("Foo::Bar->new;", ["new"]),
        # plain parenthesised calls, as before
        ("foo(1)", ["foo"]),
        ("Foo::bar(1)", ["bar"]),
        ("&helper($x);", ["helper"]),
        # unary / list built-ins written bare
        ("my $x = shift;", ["shift"]),
        ("my $x = shift || 3;", ["shift"]),
        ("delete $h->{k};", ["delete"]),
        ("return defined $x;", ["defined"]),
        ("my @k = keys %h;", ["keys"]),
        # statement-opening commands with an argument
        ("plan tests => 4;", ["plan"]),
        ("    croak 'bad';", ["croak"]),
        ("blessed $x and 1;", ["blessed"]),
        ("my $v = fetch $k;", ["fetch"]),
        ("return blessed $x;", ["blessed"]),
        ("print <<EOF;", ["print"]),
        # slice 2: after a low-precedence operator, however many blanks
        ('defined $n  or die "x: $!";', ["defined", "die"]),
        ('eval { 1 } or warn "failed";', ["warn"]),
        ("$ok and print OUT $line;", ["print"]),
        # a regex, block, hash, qq string or file handle opens the argument list
        ("my @a = split /,/, $s;", ["split"]),
        ("my $v = first { $_ > 0 } @l;", ["first"]),
        ("my $s = bless {}, $class;", ["bless"]),
        ("tie %q, 'Pkg';", ["tie"]),
        ("system qq{title $t};", ["system"]),
        ('die "bad";', ["die"]),
        ("sub o { return sprintf '%o', shift }", ["sprintf", "shift"]),
    ],
)
def test_callees(line, expected):
    assert _callees(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "$self->{shift}",
        "$h{keys}",
        "shift => 1,",
        "{ length => 3 }",
        "my $shift = 2; $shift + 1;",
        "$length = 4;",
        "$x(1)",
        "use strict;",
        "use lib 'lib';",
        "package Foo::Bar;",
        "my $r = $a x $b;",
        "$x = $a eq $b;",
        "foo",
        "my $v = foo;",
        "$o->{name} = 1;",
        "$o->$method;",
        "   name => $x,",
        "$h{shift}",
        "my @x = map { $_ } @l;",
        "my @x = grep { $_ } @l;",
        "BEGIN { 1 }",
        "$o->{or} die",
        "my $r = $a % 3;",
        "$x = foo {a} + 1;",
    ],
)
def test_not_calls(line):
    assert _callees(line) == []


def test_registered_in_the_qualified_family():
    assert LANGUAGE_DEFINITIONS["perl"]["rules"]["calls_out"] is CALLS_OUT_PERL
    assert CALLS_OUT_PERL in QUALIFIED_CALLS_OUT_PATTERNS
    assert CALLS_OUT_PERL.groups == 1


def test_extractor_attributes_paren_less_calls_with_qualifiers():
    perl = LANGUAGE_DEFINITIONS["perl"]
    code = """
sub run {
    my $self = shift;
    my $v = $self->store->load;
    plan tests => 4;
    delete $self->{k};
    my $shift = 1;
}
"""
    res = StructuralExtractor("perl", {"perl": perl}).splice(code, "")
    fn = res["functions"][0]
    calls = fn["calls_out_to"]
    for name in ("shift", "store", "load", "plan", "delete"):
        assert name in calls
    assert "my" not in calls
    assert fn["calls_out_qualifiers"]["load"] == ["self.store"]


@pytest.mark.parametrize(
    "payload",
    [
        " " * 10000 + "(",
        "a " * 10000,
        "$o" + "->a" * 5000,
        "x" * 20000 + " ",
        "\n" + " \t" * 10000 + "name",
        "x " + "{" * 5000,
        "x { " + "a" * 20000,
        "or " * 10000,
        "x " + "A_" * 10000,
    ],
)
def test_redos_immune(payload):
    assert_redos_immune(CALLS_OUT_PERL, payload, timeout_sec=3.0)


def test_die_is_a_call():
    perl = LANGUAGE_DEFINITIONS["perl"]
    assert "die" not in perl["rules"]["_calls_out_ignore"]
    code = "sub run {\n    open(my $f, '<', $p) or die \"no $p\";\n    die 'x' unless $f;\n}\n"
    res = StructuralExtractor("perl", {"perl": perl}).splice(code, "")
    assert "die" in res["functions"][0]["calls_out_to"]
