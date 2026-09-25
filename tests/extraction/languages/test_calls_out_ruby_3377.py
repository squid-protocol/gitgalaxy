"""
#3377: Ruby calls without parentheses. `CALLS_OUT_C_STYLE` needed `name(` and found a
third of Ruby's calls; `CALLS_OUT_RUBY` also takes a receiver-dot call, a `?`/`!`
method name, and a statement-opening command with an argument. A bare word is
never a call: Ruby cannot tell `foo` the local variable from `foo` the call
without a symbol table.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_RUBY,
    QUALIFIED_CALLS_OUT_PATTERNS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _callees(line: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_RUBY.finditer(line)]


@pytest.mark.parametrize(
    "line, expected",
    [
        # receiver-dot calls, parens or not
        ("x = obj.to_s", ["to_s"]),
        ("xs.each do |y|", ["each"]),
        ("result.stdout.chomp", ["stdout", "chomp"]),
        ("obj&.name", ["name"]),
        ('"".upcase', ["upcase"]),
        ("3.times { }", ["times"]),
        ("  .map(&:to_s)", ["map"]),
        ("x.y = 1", ["y"]),
        ("Foo::bar(1)", ["bar"]),
        # `?` / `!` method names
        ("hash.key?(k)", ["key?"]),
        ("valid?(x)", ["valid?"]),
        ("if quiet?", ["quiet?"]),
        ("  fetch_api!", ["fetch_api!"]),
        ("a.b? ? c : d", ["b?"]),
        # statement-opening commands
        ("puts x", ["puts"]),
        ('  puts ""', ["puts"]),
        ('command! "", ""', ["command!"]),
        ("attr_reader :a", ["attr_reader"]),
        ("foo(1)", ["foo"]),
    ],
)
def test_ruby_calls(line, expected):
    assert _callees(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "x = foo",  # a bare word: variable or call, unknowable
        "value if cond",  # statement modifier, not an argument
        "ready ? a : b",  # ternary, not `ready?`
        "cond ? a : b",
        "a != b",
        "a =~ /x/",
        "x = y",
        "x ||= y",
        "a, b = c",
        "foo -1",
        "return x",
        "when x then y",
        "unless (x)",
        "1..n",
        "Foo::Bar",
        "x = :sym?",
        "    installed_on_request?:    x || false,",  # a `name?:` hash label
        "f[:installed_on_request?]",
    ],
)
def test_ruby_non_calls(line):
    assert _callees(line) == []


def test_ruby_rides_the_qualified_family():
    """detector.py gives ruby's pattern the C-style treatment: qualifiers and the C5 check."""
    assert LANGUAGE_DEFINITIONS["ruby"]["rules"]["calls_out"] is CALLS_OUT_RUBY
    assert CALLS_OUT_RUBY in QUALIFIED_CALLS_OUT_PATTERNS


def test_ruby_calls_through_splice():
    code = (
        "def run(items)\n"
        "  puts items.size\n"
        "  items.each do |i|\n"
        "    cache.store!(i) if i.valid?\n"
        "  end\n"
        "  count = items.count\n"
        "  quiet? ? nil : log(count)\n"
        "end\n"
    )
    fns = StructuralExtractor("ruby", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    run = next(f for f in fns if f["name"] == "run")
    assert set(run["calls_out_to"]) == {"puts", "size", "each", "store!", "valid?", "count", "quiet?", "log"}
    assert run["calls_out_qualifiers"]["store!"] == ["cache"]
    assert run["calls_out_qualifiers"]["size"] == ["items"]


@pytest.mark.parametrize(
    "payload",
    [
        "a" * 100000,
        "a" + " " * 100000,
        "a " * 50000,
        "\n".join(["  x" + " " * 200] * 500),
        "." * 100000,
        "a." * 50000 + "b",
        "a?" * 50000,
    ],
)
def test_ruby_calls_out_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_RUBY, payload, timeout_sec=3.0)


def test_ruby_methods_belong_to_their_class():
    """A Ruby class body ends at its `end`, found by indentation like Python's.
    The brace search it used before stopped at the first `{` -- a hash literal
    or a block -- so no Ruby method had a class, and a bare `puts` anywhere
    resolved `unique` to a private `def puts` in some class (#3377)."""
    code = (
        "module Brew\n"
        "  class Strategy\n"
        "    DEFAULTS = { quiet: false }\n"
        "\n"
        "    def fetch(timeout: nil)\n"
        "      items.each { |i| puts i }\n"
        "    end\n"
        "\n"
        "    private\n"
        "\n"
        "    def puts(*args)\n"
        "      super unless quiet?\n"
        "    end\n"
        "  end\n"
        "\n"
        "  class Other\n"
        "    def run\n"
        "      1\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    fns = StructuralExtractor("ruby", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    owner = {f["name"]: f.get("parent_class_name") for f in fns}
    assert owner["fetch"] == "Strategy"
    assert owner["puts"] == "Strategy"
    assert owner["run"] == "Other"
