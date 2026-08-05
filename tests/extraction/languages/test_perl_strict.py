"""perl strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SYMBOLIC-\b SWEEP (companion to #585's haskell =~ fix)
# ==============================================================================
# Found by a systematic scan for the same bug shape as haskell's
# regex_execution `=~` fix and javascript/typescript's encapsulation `#`
# fix: a purely-symbolic alternative (no letters/digits/underscore) wrapped
# in a shared \b(...)\b group. \b requires a word/non-word transition, so a
# symbolic alternative flanked by \b can only match with NO surrounding
# whitespace/punctuation at either edge -- never how real code is
# idiomatically formatted (operators and superglobals are almost always
# spaced or preceded by other punctuation, not bare word characters).


def test_perl_ipc_rpc_bridges_system_and_exec_calls():
    """
    Regression test: `system\\s*\\(` and `exec\\s*\\(` both end in a literal
    `(`, so the trailing \\b in the old shared wrapper could never match once
    followed by anything else non-word (a string quote, a variable sigil) --
    meaning `system("ls")` and `exec("ls")`, the two most common forms,
    never matched at all.
    """
    pattern = LANGUAGE_DEFINITIONS["perl"]["rules"]["ipc_rpc_bridges"]
    assert pattern.search('system("ls -la")'), "Failed to match system(...) -- the most common form"
    assert pattern.search('exec("ls -la")'), "Failed to match exec(...) -- the most common form"
    assert pattern.search("my $pid = fork();")
    assert pattern.search("my $out = `ls -la`;")
    assert not pattern.search("mysystem(1)"), "Incorrectly matched 'system' as a substring of another identifier"


# ==============================================================================
# PERL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #602)
# ==============================================================================
PERL_RULES = LANGUAGE_DEFINITIONS["perl"]["rules"]

_PERL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) { do_it(); }", None),
    ("args", "sub foo ($a, $b) { }", None),
    ("structural_boundaries", "my $x = 1;", None),
    ("func_start", "sub foo {", None),
    ("class_start", "package Foo;", None),
    ("safety", "eval { risky(); }", None),
    ("safety_bypasses", "eval $code;", None),
    ("high_risk_execution", 'system("ls");', None),
    ("io", "open(my $fh, '<', $file);", None),
    ("api", "use Exporter;", None),
    ("state_mutation", "push @arr, 1;", None),
    ("dead_code", "# my $x = 1;", "# just a comment"),
    ("doc", "=head1 NAME", None),
    ("test", "ok(1, 'passes');", None),
    ("concurrency", "my $pid = fork();", None),
    ("ui_framework", "use Template;", None),
    ("closures", "sub { return 1; }", None),
    ("globals", "print $$;", None),
    ("decorators", "sub foo : lvalue {", None),
    ("generics", "ArrayRef[Int]", None),
    ("comprehensions", "map { $_ * 2 } @list;", None),
    ("scientific", "sqrt(4);", None),
    ("reflection_metaprogramming", "bless($self, $class);", None),
    ("import", "use Foo::Bar;", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: fix this", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "render('index');", None),
    ("events", "$bus->emit('event');", None),
    ("dependency_injection", "my $c = container();", None),
    ("macros", "BEGIN { }", None),
    ("pointers", "$ref->[0];", None),
    ("memory_alloc", "undef $x;", None),
    ("inline_asm", "use Inline 'C';", None),
    ("telemetry", "$logger->info('msg');", None),
    ("debug_prints", 'print "debug";', None),
    ("explicit_casts", "int($x);", None),
    ("panics_and_aborts", "die 'error';", None),
    ("thread_sleeps", "sleep(5);", None),
    ("bitwise_ops", "$a & $b;", None),
    ("sync_locks", "lock($var);", None),
    ("immutability_locks", "use Readonly;", None),
    ("cleanup", "close($fh);", None),
    ("encapsulation", "state $x;", None),
    ("listeners", "$bus->on('event', sub {});", None),
    ("test_skip", "skip('reason', 1);", None),
    ("serialization_parsing", "JSON::decode_json($json);", None),
    ("regex_execution", "s/foo/bar/;", None),
    ("time_date_logic", "localtime();", None),
    ("ipc_rpc_bridges", "`ls -la`;", None),
]


@pytest.mark.parametrize("signature,positive,negative", _PERL_SIMPLE_CASES)
def test_perl_signature_positive_and_negative(signature, positive, negative):
    pattern = PERL_RULES[signature]
    assert pattern is not None, f"perl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"perl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"perl {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_perl_args_control_flow_shield_and_redos_immunity():
    pattern = PERL_RULES["args"]
    assert pattern.search("sub foo ($a, $b) { }")
    assert pattern.search("my ($a, $b) = @_;")
    assert pattern.search("shift;")
    assert not pattern.search("if ($x) {"), "args hallucinated on an if statement"
    poison = "sub foo (" + "a, " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_func_start_vertical_shield_and_name_capture():
    pattern = PERL_RULES["func_start"]
    m = pattern.search("sub foo {")
    assert m is not None
    assert m.group(1) == "foo"

    m2 = pattern.search("sub\nfoo\n{")
    assert m2 is not None
    assert m2.group(1) == "foo", "vertical subroutine shield failed to capture the name across newlines"

    m3 = pattern.search("method bar ($self) {")
    assert m3 is not None
    assert m3.group(1) == "bar"

    poison = "sub" + "\n" * 40000 + "foo {"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_class_start_captures_qualified_name_and_redos_immunity():
    pattern = PERL_RULES["class_start"]
    m = pattern.search("package Foo::Bar::Baz;")
    assert m is not None
    assert m.group(1) == "Foo::Bar::Baz"

    m2 = pattern.search("class Point;")
    assert m2 is not None
    assert m2.group(1) == "Point"

    poison = "package " + "A::" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_import_dependency_capture():
    dep_pattern = PERL_RULES["_dependency_capture"]
    m = dep_pattern.search("use Foo::Bar::Baz;")
    assert m is not None
    assert "Foo::Bar::Baz" in m.groups()

    # HISTORICAL BUG regression: `require` is runtime-evaluated and very
    # frequently scoped inside a conditional or subroutine -- the old `^`
    # line anchor blinded the engine to this common deferred-load idiom.
    m2 = dep_pattern.search("if ($need_heavy) { require Some::Heavy::Module; }")
    assert m2 is not None
    assert "Some::Heavy::Module" in m2.groups()


def test_perl_safety_eval_block_boundary_regression():
    """
    Regression test: `eval[ \t]*\\{` was inside a shared \\b(...)\\b wrapper.
    It ends on the literal `{` (non-word), so the trailing \\b only fired
    when a word character immediately followed the brace -- the far more
    common idiomatic style with a space after `{` (`eval { risky(); }`)
    never matched at all, silently blinding the safety sensor to the
    single most common Perl error-trapping idiom.
    """
    pattern = PERL_RULES["safety"]
    assert pattern.search("eval { risky_call(); }"), "the idiomatic spaced eval-block form still didn't match"
    assert pattern.search("eval{risky_call();}")
    assert pattern.search("eval\n{\n    risky_call();\n}"), "vertical eval-block placement still didn't match"
    assert pattern.search("use strict;")
    assert pattern.search('$x->isa("Foo")')
    assert not pattern.search("my $evaluation = 1;"), "safety incorrectly matched a bareword containing 'eval'"


def test_perl_safety_bypasses_eval_and_goto_boundary_regression():
    """
    Regression test: `eval\\s+(?!\\w|{)` and `goto\\s+\\&` both end on a
    non-word character by construction, so the old shared trailing \\b
    could never be satisfied -- silently dropping the two most common
    dangerous idioms: `eval $code;` / `eval($code);` (string-eval on a
    variable, not a literal) and `goto &$sub;` (dynamic dispatch).
    """
    pattern = PERL_RULES["safety_bypasses"]
    assert pattern.search("eval $code;"), "eval on a bare variable still didn't match"
    assert pattern.search("eval($code);"), "the no-space function-call form of eval still didn't match"
    assert pattern.search('eval "system($cmd)";')
    assert pattern.search("goto &$sub;"), "dynamic goto still didn't match"
    assert pattern.search("goto &sub;")
    assert pattern.search("no strict;")
    # The safe, non-bypass forms must remain excluded.
    assert not pattern.search("eval q{1};"), "incorrectly matched the safe bareword-block eval form"
    assert not pattern.search("eval { safe_call(); }"), "incorrectly matched the safe eval-block form"


def test_perl_globals_magic_variable_boundary_regression():
    """
    Regression test: `$$`, `$@`, `$!`, and `$?` were inside the shared
    trailing \\b group. Each ends on a symbolic, non-word character, so the
    trailing \\b could only fire when a word char immediately followed --
    never true for how these 4 special variables are actually written.
    """
    pattern = PERL_RULES["globals"]
    assert pattern.search("my $pid = $$;"), "$$ (PID) still didn't match"
    assert pattern.search("if ($@) { die $@; }"), "$@ (eval error) still didn't match"
    assert pattern.search("if ($!) { warn $!; }"), "$! (errno) still didn't match"
    assert pattern.search("my $code = $?;"), "$? (child exit status) still didn't match"
    assert pattern.search("print $a, $b;")
    assert pattern.search("my %h = %ENV;")
    assert not pattern.search("my $abc = 1;"), "incorrectly matched $a as a substring of $abc"


def test_perl_listeners_call_form_boundary_regression():
    """
    Regression test: `on\\s*\\(` and `subscribe\\s*\\(` both end in a
    literal `(`, so the shared trailing \\b could only fire when a word
    char immediately followed -- never true for the most common real call
    shape, `on('event', ...)`, where a quote follows the paren.
    """
    pattern = PERL_RULES["listeners"]
    assert pattern.search("$emitter->on('data', sub { });"), "on(...) still didn't match its most common form"
    assert pattern.search("$emitter->subscribe($topic);")
    assert pattern.search("add_listener($cb);")


def test_perl_regex_execution_bareword_variable_ambiguity_regression():
    """
    Regression test: the old `\\s*[/\\W]` delimiter check could be
    satisfied by an ordinary whitespace/punctuation character that has
    nothing to do with a regex delimiter (`\\W` matches any non-word char,
    including plain space) -- meaning an ordinary bareword-named scalar
    (`$s`, `$m`, `$y`) followed by any operator or even just a space was
    misclassified as the `s///`/`m//`/`y///` regex operator.
    """
    pattern = PERL_RULES["regex_execution"]
    assert not pattern.search("$s = 5;"), "incorrectly classified a variable named $s as the s/// operator"
    assert not pattern.search("$m = 10;"), "incorrectly classified a variable named $m as the m// operator"
    assert not pattern.search("my $y = 2026;"), "incorrectly classified a variable named $y as the y/// operator"
    assert not pattern.search("my $tr = 1;"), "incorrectly classified a variable named $tr as the tr/// operator"
    assert pattern.search("s/foo/bar/;")
    assert pattern.search("$str =~ s/foo/bar/;")
    assert pattern.search("tr/a-z/A-Z/;")
    assert pattern.search("m{foo};")
    assert pattern.search("qr/foo/;")
    assert pattern.search("$x !~ /foo/;")


def test_perl_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 4 pairs the automated ambiguity sweep flagged for sharing
    literal keywords ("sub"/"method"/"class"/"package"): args<->dead_code,
    args<->func_start, class_start<->dead_code, dead_code<->func_start.
    In every case, dead_code's leading `#` comment-prefix requirement
    already fully disambiguates it from the other two (which require the
    keyword NOT be preceded by a comment marker in context), and
    args<->func_start both correctly firing on the *same* real `sub foo (...)
    {` line is intentional overlap, not a false collision -- confirmed
    empirically here rather than trusted from the sweep tool's literal-only
    heuristic.
    """
    args = PERL_RULES["args"]
    dead_code = PERL_RULES["dead_code"]
    func_start = PERL_RULES["func_start"]
    class_start = PERL_RULES["class_start"]

    live_sub = "sub foo ($a, $b) { }"
    assert args.search(live_sub) and func_start.search(live_sub), (
        "both args and func_start should legitimately match the same live sub signature"
    )
    assert not dead_code.search(live_sub), "dead_code incorrectly matched a live (non-commented) sub"

    commented_sub = "# sub foo { }"
    assert dead_code.search(commented_sub)
    assert not func_start.search(commented_sub), "func_start incorrectly matched a commented-out sub"

    live_package = "package Foo::Bar;"
    assert class_start.search(live_package)
    assert not dead_code.search(live_package)

    commented_package = "# package Foo::Bar;"
    assert dead_code.search(commented_package)
    assert not class_start.search(commented_package), "class_start incorrectly matched a commented-out package"


def test_perl_state_mutation_chained_dereference_redos_immunity():
    pattern = PERL_RULES["state_mutation"]
    poison = "$x" + "->[0]" * 40000 + " ="
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_decorators_redos_immunity():
    pattern = PERL_RULES["decorators"]
    poison = ":" + "a" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)
