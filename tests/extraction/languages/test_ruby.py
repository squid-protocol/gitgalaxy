import sys
from pathlib import Path

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

import pytest  # noqa: E402
from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

RUBY_RULES = LANGUAGE_DEFINITIONS["ruby"]["rules"]


def test_ruby_func_start():
    valid = [
        ("def foo", "foo"),
        ("def self.class_method", "class_method"),
        ("def Module::NestedClass.method", "method"),
        ("def method_name?", "method_name?"),
        ("def destructive_method!", "destructive_method!"),
        ("def []", "[]"),
        ("def []=(key, val)", "[]="),
        ("def <<(item)", "<<"),
        ("def ==(other)", "=="),
        ("def =~(other)", "=~"),
        ("def `(cmd)", "`"),
        ("def foo = 'one-liner'", "foo"),
        ("def foo() = 42", "foo"),
        ("def \n crazy_whitespace \n ()", "crazy_whitespace"),
        ("def\ttabbed_method", "tabbed_method"),
        ("def ಠ_ಠ", "ಠ_ಠ"),
        ("define_method(:foo) do", "foo"),
    ]

    invalid = [
        ("def_method = 1", None),
        ("undef method_name", None),
        ("alias def new_def", None),
        ("method_call(def: 'value')", None),
        ("object.def_like_method", None),
    ]

    xfail_invalid = [
        ("# def foo", None),
        ('"def foo"', None),
        ("'def foo'", None),
        ("`def foo`", None),
        ("<<-RUBY\n def foo \nRUBY", None),
        ("puts 'def foo'", None),
    ]

    for payload, expected in valid:
        assert_valid_match(RUBY_RULES["func_start"], payload, expected, "ruby.func_start")

    for payload, _ in invalid:
        assert_invalid_no_match(RUBY_RULES["func_start"], payload, "ruby.func_start")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_ruby_class_start():
    valid = [
        ("class Foo", "Foo"),
        ("class Foo < Bar", "Foo"),
        ("class Module::NestedClass", "Module::NestedClass"),
        ("class << self", "<< self"),
        ("class << @object", "<< @object"),
        ("class Foo<Bar", "Foo"),
        ("class \n Foo \n < \n Bar", "Foo"),
        ("class Foo; end", "Foo"),
        ("class  ಠ_ಠ < Object", "ಠ_ಠ"),
    ]

    invalid = [
        ("class_eval do", None),
        ("class_variable_set(:@@foo, 1)", None),
        ("def class_method; end", None),
        ("foo.class", None),
        ("ActiveRecord::Base.class", None),
        ("some_class_method", None),
        ("klass = Class.new", None),
    ]

    xfail_invalid = [
        ("# class Foo", None),
        ('"class Foo"', None),
    ]

    for payload, expected in valid:
        assert_valid_match(RUBY_RULES["class_start"], payload, expected, "ruby.class_start")

    for payload, _ in invalid:
        assert_invalid_no_match(RUBY_RULES["class_start"], payload, "ruby.class_start")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_ruby_args():
    valid = [
        ("def foo()", "def foo()"),
        ("def foo(a)", "def foo(a)"),
        ("def foo(a, b)", "def foo(a, b)"),
        ("def foo(a = 1, b = 'str')", "def foo(a = 1, b = 'str')"),
        ("def foo(*args)", "def foo(*args)"),
        ("def foo(**kwargs)", "def foo(**kwargs)"),
        ("def foo(&block)", "def foo(&block)"),
        ("def foo(a, b=1, *c, d:, e: 2, **f, &g)", "def foo(a, b=1, *c, d:, e: 2, **f, &g)"),
        ("def foo(...)", "def foo(...)"),
        ("def foo(*, **)", "def foo(*, **)"),
        ("def foo(a, \n b)", "def foo(a, \n b)"),
        ("def foo(a = { x: 1, y: 'foo(bar)' })", "def foo(a = { x: 1, y: 'foo(bar)' })"),
        ("def foo(a = lambda { |x| x.foo })", "def foo(a = lambda { |x| x.foo })"),
        ("def foo(a = %w[one two three])", "def foo(a = %w[one two three])"),
        ("def foo(a: 1, b: 'def foo')", "def foo(a: 1, b: 'def foo')"),
        ('def foo(a="\\\"")', 'def foo(a="\\\"")'),
        ('def foo(a = ")", b = 2)', 'def foo(a = ")", b = 2)'),
        ("def foo(a = <<-EOF\n  multiline\nEOF\n)", "def foo(a = <<-EOF\n  multiline\nEOF\n)"),
        ("do |a, b|", "do |a, b|"),
        ("{ |a, b| }", "{ |a, b|"),
        ("->(a, b) { }", "->(a, b)"),
    ]

    invalid = [
        ("method_call(a, b)", None),
        ("[a, b]", None),
        ("{ a: 1, b: 2 }", None),
    ]

    xfail_invalid = [
        ("# (a, b)", None),
        ('"(a, b)"', None),
        ("'(a, b=1)'", None),
    ]

    for payload, expected in valid:
        assert_valid_match(RUBY_RULES["args"], payload, expected, "ruby.args")

    for payload, _ in invalid:
        assert_invalid_no_match(RUBY_RULES["args"], payload, "ruby.args")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_ruby_dependency_capture():
    valid = [
        ("require 'json'", "json"),
        ('require "net/http"', "net/http"),
        ("require_relative 'my_lib'", "my_lib"),
        ("include Enumerable", "Enumerable"),
        ("extend ActiveSupport::Concern", "ActiveSupport::Concern"),
        ("require('openssl')", "openssl"),
        ("require %q(foo)", "foo"),
        ("require %Q{bar}", "bar"),
        ("require %W[baz].first", "baz"),
        ("require \n 'foo'", "foo"),
        ("include(Foo::Bar)", "Foo::Bar"),
        ("require 'foo' # comment", "foo"),
        ('require_relative"foo"', "foo"),
    ]

    invalid = [
        ("def require_something", None),
        ("var = required_value", None),
        ("require_user_login!", None),
        ("included_modules", None),
        ("extended_method", None),
        ("require_all 'foo'", None),
        ("alias require old_require", None),
    ]

    xfail_invalid = [
        ("# require 'foo'", None),
        ('puts "require \'foo\'"', None),
        ('"include Enumerable"', None),
    ]

    for payload, expected in valid:
        assert_valid_dependency_match(RUBY_RULES["_dependency_capture"], payload, expected, "ruby._dependency_capture")

    for payload, _ in invalid:
        assert_invalid_no_match(RUBY_RULES["_dependency_capture"], payload, "ruby._dependency_capture")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


