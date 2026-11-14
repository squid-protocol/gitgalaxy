"""
Julia (#6572): `.jl` is mapped, `function` units are sliced by their `end` (a `x[end]` index and a mid-line
comprehension `for` / `if` open or close nothing), `struct` / `module` are classes, and `using` / `import` name their
module in `_dependency_capture` (no import is read from a comment, docstring or string). Every snippet is real Julia.
"""

import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

JL = LANGUAGE_DEFINITIONS["julia"]
RULES = JL["rules"]

SRC = (
    "module Doom\n"
    "using LinearAlgebra\n"
    "import Base: show\n"
    "using .Local\n"
    "\n"
    "struct Player\n"
    "    hp::Int\n"
    "end\n"
    "\n"
    "function tick(p::Player, dt)\n"
    "    if p.hp > 0\n"
    "        return [x for x in 1:dt if x > 1]\n"
    "    end\n"
    "    last = xs[end]\n"
    "    xs[end-1]\n"
    "end\n"
    "\n"
    "total(xs) = sum(xs)\n"
    "\n"
    "function run(f)\n"
    "    open(f) do io\n"
    "        read(io)\n"
    "    end\n"
    "end\n"
    "end\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("julia", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _names(content: str) -> list[str]:
    return sorted(f["name"] for f in _splice(content)["functions"] if f["name"] != "__global_context__")


def test_jl_extension_routes_to_julia():
    assert _route("player.jl", SRC) == "julia"
    assert _route("test/runtests.jl", SRC) == "julia"


def test_function_blocks_are_units_and_short_form_is_a_func_start_hit():
    assert _names(SRC) == ["run", "tick"]
    # a short-form `total(xs) = ...` opens no scope, so it is no sliced unit (known gap, like a Lua one-liner before
    # #2438), but the func_start signal still counts it
    assert "total(xs) =" in _hits("func_start", SRC)


def test_function_spans_follow_end_and_index_end_opens_nothing():
    fns = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"]}
    # `[x for x in ...  if ...]` and `xs[end]` / `xs[end-1]` do not unbalance the unit
    assert fns["tick"] == (10, 16)
    # the `do` block closes inside `run`
    assert fns["run"] == (20, 24)


def test_func_start_forms():
    src = (
        "function a(x) end\n"
        "@inline function b(x)\n  x\nend\n"
        "function Base.show(io, p)\n  nothing\nend\n"
        "function c(x::T) where {T}\n  x\nend\n"
        "d(x) = x\n"
        "e(x::Int)::Int = x\n"
        "f(x::T) where T = x\n"
        "g{T}(x) = x\n"
    )
    names = sorted((m.group(1) or m.group(2)) for m in RULES["func_start"].finditer(src))
    assert names == ["a", "b", "c", "d", "e", "f", "g", "show"]


def test_func_start_ignores_comparisons_and_calls():
    src = "x == y\nf(x) == 2\nprintln(x)\nf(x) => 1\nif f(x) = 1\n"
    assert _hits("func_start", src) == []


def test_classes_are_found():
    src = (
        "module M\nstruct A\nend\nmutable struct B{T}\nend\nabstract type C <: Any end\nprimitive type D 8 end\n"
        "baremodule E\nend\n"
    )
    assert [m.group(1) for m in RULES["class_start"].finditer(src)] == ["M", "A", "B", "C", "D", "E"]


def test_arguments_are_counted():
    fns = {f["name"]: f["args"] for f in _splice(SRC)["functions"]}
    assert fns["tick"] == 2
    assert fns["run"] == 1


def test_dependencies_capture_the_module():
    caps = [m.group(1) for m in RULES["_dependency_capture"].finditer(SRC)]
    assert caps == ["LinearAlgebra", "Base", ".Local"]
    src = "using A.B\nimport Base.Iterators\nusing ..Parent\nusing A, B\n"
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(src)] == [
        "A.B",
        "Base.Iterators",
        "..Parent",
        "A",
    ]


def test_import_capture_blank_hides_comments_docstrings_and_strings():
    import re

    blank = re.compile(JL["import_capture_blank"])
    src = (
        "#= block\nusing Hidden1\n=#\n"
        '"""\nusing Hidden2\n"""\n'
        '"multi\nusing Hidden3\n"\n'
        "# using Hidden4\n"
        "c = '\"'\n"
        "using Real\n"
    )
    kept = blank.sub(lambda m: " " * len(m.group(0)), src)
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(kept)] == ["Real"]


def test_unsafe_and_inbounds_are_safety_bypasses():
    assert _hits("safety_bypasses", "@inbounds x[i]\nunsafe_load(p)\n") == ["@inbounds", "unsafe_load("]


def test_every_rule_survives_pathological_input():
    payloads = [
        "function " + "a" * 20000 + "\n",
        "function f(" + "a, " * 4000 + "\n",
        "function f(" + "(" * 5000 + "\n",
        "using " + "A." * 5000 + "\n",
        "f{" + "{" * 5000 + "\n",
        "  " * 5000 + "x = [" + "a for " * 3000 + "\n",
        "# " + "function " * 5000 + "\n",
        "@" + "a " * 5000 + "function\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
