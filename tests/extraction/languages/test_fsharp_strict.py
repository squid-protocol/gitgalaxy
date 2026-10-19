"""
F# (#5623): `.fs` is claimed on content proof (GLSL fragment shaders and Forth also use it), `.fsi` / `.fsx` are
unambiguous, and the let / member / and function shapes are extracted through the indentation (offside) slicer.
Every snippet is a real F# shape. Routing runs through the real language lens in both collision directions.
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

FS = LANGUAGE_DEFINITIONS["fsharp"]
RULES = FS["rules"]

MODULE_SRC = (
    "module Demo.Core\n"
    "\n"
    "open System\n"
    "\n"
    "let add a b =\n"
    "    a + b\n"
    "let rec fact (n: int) : int =\n"
    "    if n <= 1 then 1 else n * fact (n - 1)\n"
    "let value = 42\n"
    "let mutable counter = 0\n"
    "type Shape =\n"
    "    | Circle of float\n"
    "    | Square of float\n"
    "let area s =\n"
    "    match s with\n"
    "    | Circle r -> 1.0\n"
    "    | Square a -> a\n"
)
TYPE_SRC = (
    "type Person(name: string) =\n"
    "    let mutable age = 0\n"
    "    member this.Name = name\n"
    "    member this.Greet(greeting: string, punct: string) =\n"
    "        greeting + name + punct\n"
    "    static member Create(n) =\n"
    "        Person(n)\n"
    "and Other(x: int) =\n"
    "    member _.Run x y =\n"
    "        x + y\n"
)
GLSL_FS = "#version 330 core\nin vec2 uv;\nout vec4 color;\nvoid main() {\n    color = vec4(uv, 0.0, 1.0);\n}\n"
FORTH_FS = ": square ( n -- n*n ) dup * ;\n: cube ( n -- n^3 ) dup square * ;\n10 square .\n"


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("fsharp", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


# --- routing ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Program.fs", "Sig.fsi", "build.fsx"])
def test_fsharp_source_routes_to_fsharp(name):
    assert _route(name, MODULE_SRC) == "fsharp"


def test_fs_is_claimed_only_on_proof():
    assert "fsharp" in LANGUAGE_DEFINITIONS and ".fs" in FS["extensions_needing_discriminator"]
    assert FS["internal_discriminator"].search(MODULE_SRC)
    assert FS["internal_discriminator"].search(TYPE_SRC)


@pytest.mark.parametrize("content", [GLSL_FS, FORTH_FS], ids=["glsl", "forth"])
def test_glsl_and_forth_fs_are_not_claimed(content):
    # F# is the only `.fs` claimant: it must still drop out of the lexical scan when its proof fails.
    assert not FS["internal_discriminator"].search(content)
    assert _route("shader.fs", content) != "fsharp"


# --- extraction ---------------------------------------------------------------
# Mode C needs a body line under a unit's header: a run of adjacent one-line `let f x = ...` bindings is not sliced
# into functions (the same limit Haskell has), so these snippets keep each body on its own line.


def test_let_functions_are_found_and_values_are_not():
    names = sorted(f["name"] for f in _splice(MODULE_SRC)["functions"])
    assert names == ["add", "area", "fact"]


def test_function_spans_follow_the_offside_rule():
    fns = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(MODULE_SRC)["functions"]}
    assert fns["add"] == (5, 6)
    assert fns["fact"] == (7, 8)
    assert fns["area"] == (14, 17)


def test_members_and_and_bindings_are_functions():
    names = {f["name"] for f in _splice(TYPE_SRC)["functions"]}
    assert {"Greet", "Create", "Run"} <= names
    assert "age" not in names


def test_mutable_binding_is_not_a_function_named_mutable():
    assert _hits("func_start", "let mutable counter = 0\n") == []


def test_unit_only_binding_has_no_arguments():
    fn = next(f for f in _splice("let go () =\n    ()\nlet two a b =\n    a\n")["functions"] if f["name"] == "go")
    assert fn["args"] == 0


def test_curried_and_tupled_arguments_are_counted():
    fns = {f["name"]: f["args"] for f in _splice(TYPE_SRC + "let add3 a b c =\n    a + b + c\n")["functions"]}
    assert fns["add3"] == 3
    assert fns["Greet"] == 2


# --- signals --------------------------------------------------------------------


def test_branch_counts_keywords_and_match_arms():
    assert _hits("branch", MODULE_SRC) == ["if", "match", "| Circle r ->", "| Square a ->"]


def test_union_case_declarations_are_not_branches():
    assert _hits("branch", "type Shape =\n    | Circle of float\n    | Square of float\n") == []


def test_state_mutation_is_assignment_only():
    src = "counter <- counter + 1\nr := 2\nlet x = a <- b\nlet f = fun a -> a\nlet ok = x <> y\n"
    assert _hits("state_mutation", src)[:2] == ["counter <-", "r :="]
    assert not _hits("state_mutation", "let f = fun a -> a\nlet ok = x <> y\n")


# --- ReDoS --------------------------------------------------------------------


def test_every_rule_survives_pathological_input():
    payloads = [
        "let " + "a " * 4000 + "\n",
        "let rec " + "inline " * 3000 + "x = 1\n",
        "type " + "A<" * 2000 + "\n",
        "    | " + "x " * 5000 + "\n",
        "let f(" + "a, " * 4000 + "\n",
        "(" * 5000 + "\n",
        "let " + "x" * 20000 + "\n",
        "open " + "A." * 4000 + "\n",
    ]
    pairs = [
        (rule, p)
        for rule in [r for r in RULES.values() if hasattr(r, "finditer")] + [FS["internal_discriminator"]]
        for p in payloads
    ]
    assert_redos_immune_all(pairs)
