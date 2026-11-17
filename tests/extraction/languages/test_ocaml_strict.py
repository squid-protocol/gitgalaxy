"""
OCaml (#6572): `.ml` / `.mli` / `.mll` / `.mly` are mapped, a column-0 `let` / `let rec` / `and` binding that takes
a parameter is a func_start, `module` / `type` / `class` / `exception` are class_start hits, and `open` / `include`
/ `#require` name their target in `_dependency_capture` (no import is read from a `(* *)` comment). Every snippet is
real OCaml.
"""

import re
import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

ML = LANGUAGE_DEFINITIONS["ocaml"]
RULES = ML["rules"]

SRC = (
    "(* open Hidden *)\n"
    "open Core.Std\n"
    "\n"
    "let area ~r (s : float) : float =\n"
    "  let k = 3.14 in\n"
    "  k *. r *. s\n"
    "\n"
    "let rec go n =\n"
    "  if n > 0 then go (n - 1) else 0\n"
    "and stop = fun () ->\n"
    "  ()\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("ocaml", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _starts(content: str) -> list[str]:
    return [m.group(1) for m in RULES["func_start"].finditer(content)]


def test_ocaml_extensions_route_to_ocaml():
    for name in ("lib/a.ml", "lib/a.mli", "lib/lexer.mll", "lib/parser.mly"):
        assert _route(name, SRC) == "ocaml", name


def test_bindings_with_parameters_are_units():
    assert _starts(SRC) == ["area", "go", "stop"]
    assert [m.group(1) for m in RULES["args"].finditer(SRC)] == ["~r (s : float)", "n"]
    spans = [(f["name"], f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"]]
    assert ("area", 4, 6) in spans


def test_func_start_forms():
    src = (
        "let f a b =\n  a\n"
        "let rec g ~lbl ?(o = 1) (y : int) : int =\n  y\n"
        "and h = function A -> 1 | B -> 2\n"
        "let k : int -> int = fun x -> x\n"
        "let it' x' = x'\n"
    )
    assert _starts(src) == ["f", "g", "h", "k", "it'"]


def test_values_and_indented_bindings_are_not_units():
    src = (
        "let x = 1\n"
        "let () = ()\n"
        "let _ = ignore 1\n"
        "let v : int = 3\n"
        "let (a, b) = (1, 2)\n"
        "let rec = 1\n"
        "  let helper z = z\n"
        "(* let commented y = y *)\n"
        "let r = ref 0\n"
    )
    assert _starts(src) == []


def test_classes_are_found():
    src = (
        "module Foo = struct end\n"
        "module type S = sig end\n"
        "module rec A : S = struct end\n"
        "type t = A | B\n"
        "type 'a box = 'a list\n"
        "type ('a, 'b) pair = 'a * 'b\n"
        "type nonrec u = int\n"
        "exception Boom of string\n"
        "class point x = object end\n"
        "class virtual shape = object end\n"
        "  let module Local = Foo in ()\n"
    )
    assert [m.group(1) for m in RULES["class_start"].finditer(src)] == [
        "Foo",
        "S",
        "A",
        "t",
        "box",
        "pair",
        "u",
        "Boom",
        "point",
        "shape",
    ]


def test_dependencies_capture_the_target():
    src = (
        "open Core.Std\n"
        "open! Base\n"
        "include Foo_bar\n"
        '#require "lwt.unix"\n'
        "let open Local in x\n"
        "open struct end\n"
        "  open Indented\n"
    )
    got = [m.group(1) or m.group(2) for m in RULES["_dependency_capture"].finditer(src)]
    assert got == ["Core.Std", "Base", "Foo_bar", "lwt.unix", "Indented"]


def test_import_capture_blank_hides_comments():
    src = "(* open Hidden1 *)\n(* a\n   open Hidden2\n*)\nopen Real\n"
    blank = re.compile(ML["import_capture_blank"])
    kept = blank.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), src)
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(kept)] == ["Real"]


def test_safety_bypasses_and_high_risk():
    src = "Obj.magic x\nOption.get o\nList.hd l\nassert false\nlet _ = Marshal.from_string s 0\n"
    assert _hits("safety_bypasses", src) == [
        "Obj.magic",
        "Option.get",
        "List.hd",
        "assert false",
        "Marshal.from_string",
    ]
    assert _hits("high_risk_execution", "Sys.command cmd\nUnix.execvp p a\nUnix.system c\n") == [
        "Sys.command",
        "Unix.execvp",
        "Unix.system",
    ]


def test_branches_and_match_arms():
    # an arm's own `when` is part of the arm hit; a variant constructor `| C of int` has no arrow
    src = "match x with\n| A -> 1\n| B n when n > 0 -> 2\ntype t = | C of int | D\nif a then b else c\n"
    assert _hits("branch", src) == ["match", "| A ->", "| B n when n > 0 ->", "if"]


def test_state_mutation_and_concurrency():
    assert _hits("state_mutation", "r := !r + 1\nx.f <- 2\nincr n\nHashtbl.add t k v\n") == [
        ":=",
        "<-",
        "incr",
        "Hashtbl.add",
    ]
    assert _hits("concurrency", "let t = Thread.create f ()\nlet* x = y in\nMutex.lock m\n") == [
        "Thread.create",
        "let*",
        "Mutex.lock",
    ]


def test_doc_decorators_and_generics():
    assert _hits("doc", "(** documented *)\n(**)\n(* plain *)\n") == ["(**"]
    assert _hits("decorators", 'type t = A [@@deriving show]\n[@@@warning "-32"]\n') == ["[@@deriving", "[@@@warning"]
    assert _hits("generics", "type 'a t = 'a list\nlet c = 'x'\n") == ["'a", "'a"]


def test_every_rule_survives_pathological_input():
    payloads = [
        "let f " + "a " * 4000 + "\n",
        "let f " + "(" * 5000 + "\n",
        "let f " + "~a:(b) " * 3000 + "\n",
        "let " + "a" * 20000 + " x\n",
        "type (" + "a, " * 5000 + "\n",
        "type '" + "a" * 20000 + "\n",
        "(* " + "open " * 5000 + "\n",
        "(*" + "*" * 20000 + "\n",
        "class [" + "a, " * 5000 + "\n",
        "let f : " + "a -> " * 5000 + "\n",
        '#require "' + "a" * 20000 + "\n",
        "[@" + "@" * 5000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
    assert re.compile(ML["import_capture_blank"]).sub("", "(*" + "a" * 30000) is not None
