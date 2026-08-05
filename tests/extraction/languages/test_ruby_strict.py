"""ruby strict structural-signature coverage.

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


# ==============================================================================
# RUBY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #607)
# ==============================================================================
RUBY_RULES = LANGUAGE_DEFINITIONS["ruby"]["rules"]

_RUBY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then", None),
    ("args", "def foo(x, y)", None),
    ("structural_boundaries", "require 'json'", None),
    ("func_start", "def foo", None),
    ("class_start", "class Foo", None),
    ("safety", "rescue => e", None),
    ("safety_bypasses", "eval(code)", None),
    ("high_risk_execution", 'exec("ls")', None),
    ("io", 'File.read("x")', None),
    ("api", "module_function", None),
    ("state_mutation", "arr.push(1)", None),
    ("dead_code", "# def foo", "# just a note"),
    ("doc", "# @param x [String] description", None),
    ("test", "describe 'Foo' do", None),
    ("concurrency", "Thread.new { }", None),
    ("ui_framework", "render :index", None),
    ("closures", "arr.each { |x| x }", None),
    ("globals", "ENV['PATH']", None),
    ("decorators", "validates :name, presence: true", None),
    ("generics", "Array[Integer]", None),
    ("comprehensions", "arr.map { |x| x * 2 }", None),
    ("scientific", "Math.sqrt(4)", None),
    ("reflection_metaprogramming", "define_method(:foo) { }", None),
    ("import", "require 'json'", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: refactor", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "respond_to do |format|", None),
    ("events", "broadcast(:event, data)", None),
    ("dependency_injection", "include Import[:foo]", None),
    ("macros", "attr_accessor :name", None),
    ("pointers", "FFI::Pointer.new(:int)", None),
    ("memory_alloc", "GC.start", None),
    ("telemetry", "Rails.logger.info('msg')", None),
    ("debug_prints", "puts 'debug'", None),
    ("explicit_casts", "Integer(x)", None),
    ("panics_and_aborts", "raise 'error'", None),
    ("thread_sleeps", "sleep 5", None),
    ("bitwise_ops", "a ^ b", None),
    ("sync_locks", "Mutex.new", None),
    ("immutability_locks", "freeze", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private", None),
    ("listeners", "bus.subscribe(topic)", None),
    ("test_skip", "skip 'reason'", None),
    ("serialization_parsing", "JSON.parse(str)", None),
    ("regex_execution", "Regexp.new(pattern)", None),
    ("time_date_logic", "Time.now", None),
    ("ipc_rpc_bridges", "Open3.capture3('ls')", None),
]


@pytest.mark.parametrize("signature,positive,negative", _RUBY_SIMPLE_CASES)
def test_ruby_signature_positive_and_negative(signature, positive, negative):
    pattern = RUBY_RULES[signature]
    assert pattern is not None, f"ruby's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"ruby {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"ruby {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_ruby_closures_leading_boundary_regression():
    """
    Regression test: all 4 alternatives shared one leading \\b, but the
    brace-block (`{ |x| ... }`) and stabby-lambda (`->(x) { ... }`) forms
    both start with a non-word character (`{`/`-`) -- the shared leading
    \\b could only fire when a word char immediately preceded them, never
    true for how these are actually written. Only the `do`-based forms
    ever matched; two of Ruby's most common closure forms never did.
    """
    pattern = RUBY_RULES["closures"]
    assert pattern.search("x = ->(n) { n * 2 }"), "the stabby lambda form still didn't match"
    assert pattern.search("x = -> (n) { n * 2 }")
    assert pattern.search("arr.map { |x| x }"), "the brace-block form still didn't match"
    assert pattern.search("arr.each do |x|")
    assert pattern.search("loop do")
    assert not pattern.search("x = { a: 1, b: 2 }"), "closures incorrectly matched a plain hash literal"


def test_ruby_state_mutation_bang_methods_boundary_regression():
    """
    Regression test: the 6 bang-method alternatives (`merge!`, `update!`,
    `gsub!`, `map!`, `select!`, `reject!`) all end on `!` (non-word), so
    the shared trailing \\b could never fire. None of Ruby's canonical
    in-place-mutation methods ever matched.
    """
    pattern = RUBY_RULES["state_mutation"]
    assert pattern.search("hash.merge!(other)")
    assert pattern.search("h.update!(k: v)")
    assert pattern.search('str.gsub!(/a/, "b")')
    assert pattern.search("arr.map! { |x| x * 2 }")
    assert pattern.search("arr.select! { |x| x > 0 }")
    assert pattern.search("arr.reject! { |x| x < 0 }")


def test_ruby_panics_and_aborts_exit_bang_boundary_regression():
    """
    Regression test: `exit!` ends on `!` (non-word), so the shared
    trailing \\b could never fire. Unlike high_risk_execution's copy of
    this same alternative (harmlessly masked by its own bare `exit`
    alternative), panics_and_aborts has no bare `exit` to save it.
    """
    pattern = RUBY_RULES["panics_and_aborts"]
    assert pattern.search("exit! unless ok"), "exit! still didn't match"
    assert pattern.search("raise ArgumentError")


def test_ruby_reflection_respond_to_missing_boundary_regression():
    pattern = RUBY_RULES["reflection_metaprogramming"]
    assert pattern.search("def respond_to_missing?(name, priv)"), "respond_to_missing? still didn't match"
    assert pattern.search("def method_missing(name, *args)")


def test_ruby_ipc_rpc_bridges_boundary_regression():
    """
    Regression test: `system\\s*\\(` ends on `(` and `%x\\{` both starts
    and ends on non-word characters (`%`/`{`) -- the shared \\b boundaries
    could never fire for either. Neither ever matched.
    """
    pattern = RUBY_RULES["ipc_rpc_bridges"]
    assert pattern.search('system("ls")'), "system(...) still didn't match"
    assert pattern.search("%x{ls -la}"), "%x{...} still didn't match"
    assert pattern.search('Open3.capture3("ls")')


def test_ruby_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for ruby:
    class_start<->dead_code and dead_code<->generics (sharing "class"),
    class_start<->generics (sharing "class"). All confirmed non-bugs:
    dead_code's `#` comment-prefix requirement disambiguates it from
    class_start, and generics's "class" hit is actually the distinct,
    capitalized Sorbet type `Class[...]` (case-sensitive, no re.I flag),
    which never collides with the lowercase `class` keyword in practice.

    Also documents a raw-regex-level collision the sweep didn't flag but
    was found during manual review: `doc`'s YARD `@raise` tag and
    `panics_and_aborts`'s bare `raise` both match the same comment line
    (`# @raise [ArgumentError] if invalid`), since "raise" is a literal
    substring of "@raise". This is expected and harmless in practice --
    comment text is stripped from the code stream by prism.py's
    lexical-family-based comment stripper before any signature other
    than dead_code/doc/ownership/planned_debt/fragile_debt ever sees it,
    so panics_and_aborts never actually evaluates raw comment text in the
    real pipeline. Not fixed, since narrowing panics_and_aborts to avoid
    this one YARD tag would be over-fitting a non-representative case.
    """
    class_start = RUBY_RULES["class_start"]
    dead_code = RUBY_RULES["dead_code"]
    generics = RUBY_RULES["generics"]
    doc = RUBY_RULES["doc"]
    panics = RUBY_RULES["panics_and_aborts"]

    live_class = "class Foo"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)

    commented_class = "# class Foo"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    sorbet_class_type = "sig { params(x: Class[Foo]).void }"
    assert generics.search(sorbet_class_type)
    assert not class_start.search(sorbet_class_type)
    assert not dead_code.search(sorbet_class_type)

    yard_raise = "# @raise [ArgumentError] if invalid"
    assert doc.search(yard_raise) and panics.search(yard_raise), (
        "documented raw-regex collision changed shape -- update this test's rationale"
    )


def test_ruby_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): ruby's explicit_casts
    (`Integer(x)`/`String(x)`/etc.) and pointers (`FFI::Pointer`/
    `Fiddle::Pointer`) don't share tokens and fire independently.
    """
    casts = RUBY_RULES["explicit_casts"]
    pointers = RUBY_RULES["pointers"]
    assert casts.search("Integer(x)")
    assert not casts.search("FFI::Pointer.new(:int)"), "explicit_casts incorrectly matched an FFI pointer type"
    assert pointers.search("FFI::Pointer.new(:int)")
    assert not pointers.search("Integer(x)"), "pointers incorrectly matched an explicit cast"
