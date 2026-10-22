"""
Crystal (#5623): `.cr` source is mapped, `def` / `macro` units are sliced by their `end` (ruby's keyword-scope
shape plus struct / enum / lib / macro scopes), and bodyless `abstract def` declarations open no scope.
Every snippet is a real Crystal shape.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

CR = LANGUAGE_DEFINITIONS["crystal"]
RULES = CR["rules"]

SRC = (
    'require "json"\n'
    'require "./helper"\n'
    "\n"
    "module Doom\n"
    "  abstract class Thing\n"
    "    abstract def update(dt : Float64)\n"
    "  end\n"
    "\n"
    "  class Player < Thing\n"
    "    getter health : Int32\n"
    "\n"
    "    def initialize(@health : Int32 = 100)\n"
    "    end\n"
    "\n"
    "    def update(dt : Float64)\n"
    "      @health -= 1 if @health > 0\n"
    "      if @health == 0\n"
    '        puts "dead"\n'
    "      end\n"
    "    end\n"
    "\n"
    "    def self.spawn(x : Int32, y : Hash(String, Int32)) : Player\n"
    "      new(x)\n"
    "    end\n"
    "\n"
    "    def ==(other : Player)\n"
    "      health == other.health\n"
    "    end\n"
    "  end\n"
    "\n"
    "  struct Vec\n"
    "    def length\n"
    "      Math.sqrt(1.0)\n"
    "    end\n"
    "  end\n"
    "\n"
    "  macro make(name)\n"
    "    def {{name}}\n"
    "      1\n"
    "    end\n"
    "  end\n"
    "end\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("crystal", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def test_cr_routes_to_crystal():
    assert _route("player.cr", SRC) == "crystal"
    assert _route("spec/player_spec.cr", SRC) == "crystal"


def test_defs_and_macros_are_functions_and_abstract_def_is_not():
    names = sorted(f["name"] for f in _splice(SRC)["functions"] if f["name"] != "__global_context__")
    # `def {{name}}` inside the macro body is generated code with no static name.
    assert names == ["==", "Anonymous_Block", "initialize", "length", "make", "spawn", "update"]


def test_function_spans_follow_end():
    fns = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"]}
    assert fns["update"] == (15, 20)
    assert fns["spawn"] == (22, 24)
    assert fns["length"] == (32, 34)


def test_modifier_if_does_not_swallow_the_next_unit():
    # `@health -= 1 if @health > 0` is a statement modifier: it opens no scope, so `update` still ends at its own `end`.
    fns = {f["name"]: f["end_line"] for f in _splice(SRC)["functions"]}
    assert fns["update"] == 20


def test_shift_by_an_uppercase_constant_is_not_a_heredoc():
    # doo-cr `Doocr.f_w << FRACBITS`: a Ruby-style heredoc opener would blank the rest of the file (35 defs read as 3).
    src = "module M\n  def a\n    x = y << FRACBITS\n  end\n\n  def b\n    1\n  end\nend\n"
    assert [f["name"] for f in _splice(src)["functions"] if f["name"] != "__global_context__"] == ["a", "b"]
    heredoc = "def c\n  s = <<-EOS\n  def not_a_unit\n  EOS\nend\n"
    assert [f["name"] for f in _splice(heredoc)["functions"] if f["name"] != "__global_context__"] == ["c"]


def test_column_zero_fun_is_a_unit_and_a_lib_fun_declaration_is_not():
    src = (
        "lib LibDoom\n  fun doom_itoa(i : Int32) : Char*\nend\n\n"
        "fun doom_memset(ptr : Void*, value : Int32)\n  Doocr.memset(ptr, value)\nend\n\n"
        "def after\n  1\nend\n"
    )
    names = [f["name"] for f in _splice(src)["functions"] if f["name"] != "__global_context__"]
    assert names == ["doom_memset", "after"]


def test_classes_structs_and_modules_are_found():
    assert _hits("class_start", SRC) == [
        "module Doom",
        "abstract class Thing",
        "class Player",
        "struct Vec",
    ]


def test_arguments_are_counted_through_type_restrictions_and_generics():
    fns = {f["name"]: f["args"] for f in _splice(SRC)["functions"]}
    assert fns["spawn"] == 2
    assert fns["update"] == 1
    assert fns["length"] == 0


def test_dependencies_capture_require_paths():
    caps = [m.group(1) for m in RULES["_dependency_capture"].finditer(SRC)]
    assert caps == ["json", "./helper"]


def test_branch_counts_keywords_and_ternary_but_not_predicate_names():
    assert _hits("branch", "x = a ? b : c\nif x.nil?\nend\n") == ["?", "if"]


def test_annotations_and_macro_blocks_are_signals():
    assert _hits("decorators", '@[Link("c")]\nlib LibC\nend\n') == ['@[Link("c")]']
    assert _hits("reflection_metaprogramming", "{% for x in y %}\n{{x}}\n{% end %}\n")


def test_not_nil_is_a_safety_bypass():
    assert _hits("safety_bypasses", "x.not_nil!.foo\n") == ["not_nil!"]


def test_every_rule_survives_pathological_input():
    payloads = [
        "def " + "a" * 20000 + "\n",
        "def f(" + "a, " * 4000 + "\n",
        "def f(" + "(" * 5000 + "\n",
        "class " + "A::" * 4000 + "\n",
        "x" + "[" * 5000 + "\n",
        "{" + "{%" * 5000 + "\n",
        "->(" * 4000 + "\n",
        "  " * 5000 + "do |" + "a," * 3000 + "\n",
        "@[" + "A" * 20000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
