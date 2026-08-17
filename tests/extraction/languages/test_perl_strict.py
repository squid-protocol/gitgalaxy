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
    ("branch", "if ($x) { do_it(); }", "my $total = $a + $b;"),
    ("args", "sub foo ($a, $b) { }", "foo($a, $b);"),
    ("structural_boundaries", "my $x = 1;", "$x = 1;"),
    ("func_start", "sub foo {", "foo();"),
    ("class_start", "package Foo;", "my $package = 'Foo';"),
    ("safety", "eval { risky(); }", "my $evaluation = 1;"),
    ("safety_bypasses", "eval $code;", "eval { safe_call(); }"),
    ("high_risk_execution", 'system("ls");', "mysystem(1);"),
    ("io", "open(my $fh, '<', $file);", 'print $fh "data";'),
    ("api", "use Exporter;", "use Moo;"),
    ("state_mutation", "push @arr, 1;", "if ($x == 1) { }"),
    ("dead_code", "# my $x = 1;", "# just a comment"),
    ("doc", "=head1 NAME", "# regular comment, not POD"),
    ("test", "ok(1, 'passes');", "okay(1, 'fine');"),
    ("concurrency", "my $pid = fork();", "my $pid = getpid();"),
    ("ui_framework", "use Template;", "use JSON;"),
    ("closures", "sub { return 1; }", "sub foo { return 1; }"),
    ("globals", "print $$;", "my $abc = 1;"),
    ("decorators", "sub foo : lvalue {", "my %h = (foo => 1);"),
    ("generics", "ArrayRef[Int]", "my @arr = (1, 2, 3);"),
    ("comprehensions", "map { $_ * 2 } @list;", "foreach my $item (@list) { }"),
    ("scientific", "sqrt(4);", "my $x = $y ** 2;"),
    ("reflection_metaprogramming", "bless($self, $class);", "$self->new($class);"),
    ("import", "use Foo::Bar;", "my $user = 'Foo::Bar';"),
    ("ownership", "# Author: Jane Doe", "# Reviewed by: Jane Doe"),
    ("planned_debt", "# TODO: fix this", "# DONE: refactored, no further action"),
    ("fragile_debt", "# HACK: workaround", "# NOTE: applied a clean, permanent fix"),
    ("spec_exposure", "# [SPEC-123] implements the contract", "# [TICKET-456] fix later"),
    ("ssr_boundaries", "render('index');", "renderer('index');"),
    ("events", "$bus->emit('event');", "$bus->publish('event');"),
    ("dependency_injection", "my $c = container();", "my $c = factory();"),
    ("macros", "BEGIN { }", "INIT { }"),
    ("pointers", "$ref->[0];", "$ref->method();"),
    ("memory_alloc", "undef $x;", "delete $h{$x};"),
    ("inline_asm", "use Inline 'C';", "use Inline::Python;"),
    ("telemetry", "$logger->info('msg');", "$logger->format('msg');"),
    ("debug_prints", 'print "debug";', 'log_info("debug");'),
    ("explicit_casts", "int($x);", "sprintf('%d', $x);"),
    ("panics_and_aborts", "die 'error';", "warn 'something odd';"),
    ("thread_sleeps", "sleep(5);", "sleepy_worker();"),
    ("bitwise_ops", "$a & $b;", "$a && $b;"),
    ("sync_locks", "lock($var);", "unlock($var);"),
    ("immutability_locks", "use Readonly;", "use constant PI => 3.14;"),
    ("cleanup", "close($fh);", "$closed_handles++;"),
    ("encapsulation", "state $x;", "our $x;"),
    ("listeners", "$bus->on('event', sub {});", "$bus->off('event');"),
    ("test_skip", "skip('reason', 1);", "todo('reason', 1);"),
    ("serialization_parsing", "JSON::decode_json($json);", "JSON::encode_json($data);"),
    ("regex_execution", "s/foo/bar/;", "my $y = 2026;"),
    ("time_date_logic", "localtime();", "my $now = DateTime->now();"),
    ("ipc_rpc_bridges", "`ls -la`;", "waitpid($pid, 0);"),
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
    assert pattern.search("my $x = shift;")
    assert not pattern.search("if ($x) {"), "args hallucinated on an if statement"
    poison = "sub foo (" + "a, " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_args_shift_excludes_explicit_array_argument():
    """
    #1519: bare `shift`/`shift;` (implicitly shifts @_, the arg-unpacking
    idiom) must still match, but `shift @other`/`shift(@other)` -- shifting
    a DIFFERENT array, unrelated to this sub's own arguments -- must not.
    """
    pattern = PERL_RULES["args"]
    assert pattern.search("shift;")
    assert pattern.search("my $x = shift;")
    m = pattern.search("shift @some_queue;")
    assert not (m and m.group(0).rstrip(";") == "shift"), "matched bare 'shift' inside 'shift @some_queue'"
    m2 = pattern.search("shift(@some_queue);")
    assert not (m2 and m2.group(0).rstrip(";") == "shift"), "matched bare 'shift' inside 'shift(@some_queue)'"


def test_perl_args_bare_array_catchall_and_redos_immunity():
    """
    #1519: `my @statuses = @_;` (a parenless array catching every remaining
    positional arg, e.g. after `my $class = shift;` already took the first
    one) is a distinct, extremely common idiom from `my (...) = @_` -- both
    must match `args`.
    """
    pattern = PERL_RULES["args"]
    assert pattern.search("my @statuses = @_;")
    assert not pattern.search("my @statuses = @other_array;"), (
        "matched a bare array assignment that wasn't actually catching @_"
    )
    poison = "my @" + "a" * 40000 + " = @_;"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_args_findall_sum_multi_statement_arity():
    """
    #1519: traditional Perl commonly unpacks args across MULTIPLE
    statements in one sub (`my $class = shift;` for the invocant, then
    `my ($a, $b) = @_;` for the rest) -- detector.py's counter must SUM
    every matching statement's contribution across the whole block, not
    just count the first one it finds.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    payload = "sub check {\n  my $class = shift;\n  my ($param, $field) = @_;\n  return 1;\n}\n"
    segments = extractor._partition_segments(payload, "perl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    check_fn = next(f for f in functions if f["name"] == "check")
    assert check_fn["args"] == 3, f"expected 3 (1 shift + 2-tuple), got {check_fn['args']}"


def test_perl_args_shift_excludes_sigil_prefixed_variable_name():
    """
    #1607 follow-up: `\\bshift\\b` alone matches the "shift" substring inside
    a variable literally NAMED `$shift` (`$` is a non-word char, so a word
    boundary exists right after it) -- a real, if ironic, idiom (exiftool's
    `ConvertDateTime` stores its GlobalTimeShift option in `my $shift =
    ...`, then references it repeatedly). Every bare reference to that
    variable must NOT be read as its own `shift` builtin call.
    """
    pattern = PERL_RULES["args"]
    assert pattern.search("shift;")
    m = pattern.search("if ($shift) {")
    assert not (m and m.group(0).strip() == "shift"), "matched bare 'shift' inside variable name '$shift'"
    m2 = pattern.search("$shift =~ s/foo//;")
    assert not (m2 and m2.group(0).strip() == "shift"), "matched bare 'shift' inside '$shift =~ ...'"


def test_perl_args_prototype_falls_through_to_body_idiom_scan():
    """
    #1607: a legacy Perl PROTOTYPE (`sub Get8u($$)`) is a sequence of bare
    sigils with NO commas, ever, regardless of true arity -- unlike a real
    named signature (`sub foo($a, $b)`), where the #1199 comma-count
    heuristic is correct. A prototype-only sub must fall through to the
    same body-idiom scan (shift/my-unpack) #1519 already built for
    signature-less traditional subs, not get locked at a false count of 1.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    payload = "sub Options($$;@)\n{\n  my $self = shift;\n  my $param = shift;\n  my $newVal = shift;\n}\n"
    segments = extractor._partition_segments(payload, "perl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    fn = next(f for f in functions if f["name"] == "Options")
    assert fn["args"] == 3, f"expected 3 (three sequential shifts), got {fn['args']}"

    zero_arg_payload = "sub Get8u($$) { return DoUnpackStd('C', @_); }\n"
    segments2 = extractor._partition_segments(zero_arg_payload, "perl")
    functions2, _ = extractor._function_slice(segments2, [{} for _ in segments2], {}, {}, None)
    fn2 = next(f for f in functions2 if f["name"] == "Get8u")
    assert fn2["args"] == 0, f"expected 0 (no shift/my-unpack in body), got {fn2['args']}"

    # A REAL named signature (commas, real identifiers) must still use the
    # #1199 comma-count heuristic, unaffected by the prototype fallthrough.
    real_sig_payload = "sub add($a, $b) {\n  return $a + $b;\n}\n"
    segments3 = extractor._partition_segments(real_sig_payload, "perl")
    functions3, _ = extractor._function_slice(segments3, [{} for _ in segments3], {}, {}, None)
    fn3 = next(f for f in functions3 if f["name"] == "add")
    assert fn3["args"] == 2, f"expected 2 (real named signature), got {fn3['args']}"


def test_perl_brace_safe_stream_escaped_brace_in_regex_does_not_desync():
    """
    #1517: an escaped `\\{`/`\\}` inside a bare `/regex/` literal (never
    shielded at all -- perl regex literals are out of scope for this
    method's quote-op shielding) reads as a real structural brace to the
    naive balanced-brace counter, silently extending a function's body far
    past its real end. Confirmed on exiftool/exiftool's `SuggestedExtension`
    (a real 57-line function measured as swallowing 1206 lines because of
    one escaped `\\{` in an RTF-detection regex).
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    payload = (
        "sub Detect($$)\n{\n"
        "    my ($self, $val) = @_;\n"
        "    if ($val =~ /^[\\n\\r]*\\{[\\n\\r]*\\\\rtf/) {\n"
        "        return 'rtf';\n"
        "    }\n"
        "    return 'txt';\n"
        "}\n"
        "\n"
        "sub After {\n"
        "    return 1;\n"
        "}\n"
    )
    segments = extractor._partition_segments(payload, "perl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    names = [f["name"] for f in functions]
    assert "After" in names, f"escaped brace in regex swallowed the following sub; found {names}"
    detect_fn = next(f for f in functions if f["name"] == "Detect")
    assert detect_fn["loc"] < 12, f"escaped brace in regex desynced the brace counter, loc={detect_fn['loc']}"


def test_perl_brace_safe_stream_slash_delimited_quote_op_stray_quote_does_not_desync():
    """
    #1517: a slash-delimited quote-like operator (`y/"//d`, `s/pat/repl/`,
    `tr/a-z/A-Z/`) can contain a bare `"`/`'` in its own content that is NOT
    a real string delimiter (e.g. `y/"//d` transliterates away literal
    double-quotes) -- without recognizing the operator itself first, the
    general quote shield reads that bare quote as an opening string
    delimiter and false-pairs it with an unrelated real quote later,
    corrupting everything in between (confirmed via
    language-crucible/data/perl/mojo/Template.pm).
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    payload = (
        'sub clean {\n  my $name = shift;\n  $name =~ y/"//d;\n  return $name;\n}\n\nsub After {\n  return 1;\n}\n'
    )
    segments = extractor._partition_segments(payload, "perl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    names = [f["name"] for f in functions]
    assert "After" in names, f'stray quote inside y/"//d desynced the shield; found {names}'


def test_perl_pod_contraction_apostrophe_does_not_swallow_following_sub():
    """
    #1606: perl POD documentation prose is never stripped from the code
    stream (a separate, pre-existing gap), so an English contraction's
    apostrophe ("doesn't") used to be misread by the brace-safety shield's
    single-quote alternative as an OPENING string delimiter -- it would then
    hunt up to 200 chars forward for the next real `'` to close it, blanking
    everything in between (including a real `sub name { ... }` a few lines
    below) before `_slice_by_braces`'s func_start search ever saw it.
    Confirmed on the real corpus: spamassassin/Message.pm's POD prose
    "doesn't have a root node ..." swallowed `sub parse_body {` whole.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    payload = (
        "=item parse_body()\n\n"
        "parse_body() doesn't create a new sub-tree on the first call.\n\n"
        "=cut\n\n"
        "sub parse_body {\n"
        "  my ($self) = @_;\n"
        "  return 1;\n"
        "}\n"
    )
    segments = extractor._partition_segments(payload, "perl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    names = [f["name"] for f in functions]
    assert "parse_body" in names, f"POD contraction apostrophe swallowed the following sub; found {names}"


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


def test_perl_branch_colon_ambiguity_and_defined_or():
    pattern = PERL_RULES["branch"]
    assert pattern.search("$x ? 1 : 2;"), "ternary colon should match"
    assert pattern.search("LABEL: while(1) {}"), "statement label colon should match"
    assert pattern.search("$x // 0;"), "defined-or should match"
    assert not pattern.search("Foo::Bar"), "package separator :: should NOT match"
    assert not pattern.search("$hash{key}"), "unrelated should not match"


def test_perl_args_anonymous_and_qualified_signatures():
    pattern = PERL_RULES["args"]
    assert pattern.search("sub ($x, $y) { }"), "anonymous sub with space should match"
    assert pattern.search("sub($x) { }"), "anonymous sub without space should match"
    assert pattern.search("method ($self, $x) { }"), "anonymous method should match"
    assert pattern.search("sub Foo::Bar::baz ($x) { }"), "qualified sub with signature should match"
    assert not pattern.search("sub Foo::Bar::baz { }"), (
        "missing signature should not match here (handled by func_start)"
    )
    assert not pattern.search("method foo { }"), "missing signature should not match here"


def test_perl_func_start_qualified_names_and_attributes():
    pattern = PERL_RULES["func_start"]
    m = pattern.search("sub Foo::Bar::baz {")
    assert m and m.group(1) == "Foo::Bar::baz", "must capture fully qualified name"
    m2 = pattern.search("sub foo:lvalue {")
    assert m2 and m2.group(1) == "foo", "must handle missing space before colon attribute"
    m3 = pattern.search("sub foo\n{")
    assert m3 and m3.group(1) == "foo", "must handle vertical brace placement"
    assert not pattern.search("sub Foo::Bar::baz;"), "forward declaration without attrs/block should not match"


def test_perl_class_start_corinna_and_versions():
    pattern = PERL_RULES["class_start"]
    m = pattern.search("package Foo::Bar 1.23;")
    assert m and m.group(1) == "Foo::Bar", "must handle package versions"
    m2 = pattern.search("class Point v1.0.0 {")
    assert m2 and m2.group(1) == "Point", "must handle class versions"
    m3 = pattern.search("class Point :isa(Shape) {")
    assert m3 and m3.group(1) == "Point", "must handle Corinna attributes"
    m4 = pattern.search("role Throwable;")
    assert m4 and m4.group(1) == "Throwable", "must handle roles"
    assert not pattern.search("my $class = 'Point';"), "should not match string"


def test_perl_structural_boundaries_sub_and_method():
    pattern = PERL_RULES["structural_boundaries"]
    assert pattern.search("sub foo {")
    assert pattern.search("method bar {")
    assert pattern.search("class Point {")
    assert pattern.search("role Throwable {")
    assert not pattern.search("my_sub()"), "should not match substrings"
