"""
Erlang (#6572): `.erl` / `.hrl` / `.escript` are mapped, a column-0 clause head is a func_start, `-module` /
`-behaviour` / `-record` are class_start hits, and `-include` / `-include_lib` / `-import` / `-behaviour` name their
target in `_dependency_capture` (no import is read from a `%` comment or a multi-line string). Every snippet is real
Erlang.
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

ERL = LANGUAGE_DEFINITIONS["erlang"]
RULES = ERL["rules"]

SRC = (
    "-module(shape).\n"
    "-behaviour(gen_server).\n"
    '-include("shape.hrl").\n'
    '% -include("hidden.hrl").\n'
    "-export([area/1]).\n"
    "\n"
    "-spec area(term()) -> number().\n"
    "area({circle, R}) when R > 0 ->\n"
    "    3.14 * R * R;\n"
    "area({square, S}) ->\n"
    "    S * S;\n"
    "area(_) ->\n"
    "    erlang:error(badarg).\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("erlang", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _starts(content: str) -> list[str]:
    return [m.group(1) for m in RULES["func_start"].finditer(content)]


def test_erlang_extensions_route_to_erlang():
    assert _route("src/shape.erl", SRC) == "erlang"
    assert _route("include/shape.hrl", SRC) == "erlang"
    assert _route("bin/run.escript", SRC) == "erlang"


def test_function_clauses_are_units_with_args():
    assert _starts(SRC) == ["area", "area", "area"]
    assert [m.group(1) for m in RULES["args"].finditer(SRC)] == ["{circle, R}", "{square, S}", "_"]
    fns = [(f["name"], f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"] if f["name"] == "area"]
    # the three clauses are one unit ending at the final `.`; the `3.14` float and `#r.f` field do not end it
    assert fns == [("area", 8, 13)]


def test_float_and_record_field_do_not_end_a_function():
    src = "f(S) ->\n    X = S#r.f * 2.5,\n    X + 1.\n\ng() ->\n    ok.\n"
    spans = [(f["name"], f["start_line"], f["end_line"]) for f in _splice(src)["functions"]]
    assert spans == [("f", 1, 3), ("g", 5, 6)]


def test_func_start_forms():
    src = (
        "init([]) ->\n    {ok, #{}}.\n"
        "'odd-name'(X) ->\n    X.\n"
        "handle_call(Req, _From, State) when is_atom(Req) ->\n    {reply, ok, State}.\n"
        "f(g(X), {A, B}) ->\n    ok.\n"
        "multi(\n    A) ->\n    A.\n"
    )
    assert _starts(src) == ["init", "'odd-name'", "handle_call", "f"]


def test_func_start_ignores_attributes_indented_calls_and_references():
    src = (
        "-export([a/0]).\n"
        "-spec a() -> ok.\n"
        "    helper(X) -> X.\n"
        "x() ->\n    F = fun a/0,\n    lists:map(fun b/1, []),\n    ok.\n"
        "%% commented(X) ->\n"
    )
    assert _starts(src) == ["x"]


def test_classes_are_found():
    src = "-module(my_srv).\n-behaviour(gen_server).\n-behavior(supervisor).\n-record(state, {a, b}).\n    -record(no, {}).\n"
    assert [m.group(1) for m in RULES["class_start"].finditer(src)] == ["my_srv", "gen_server", "supervisor", "state"]


def test_dependencies_capture_the_target():
    src = (
        '-include("shape.hrl").\n'
        '-include_lib("kernel/include/file.hrl").\n'
        "-import(lists, [map/2]).\n"
        "-behaviour(gen_server).\n"
        '%% -include("hidden.hrl").\n'
        '  -include("indented.hrl").\n'
    )
    got = [m.group(1) or m.group(2) for m in RULES["_dependency_capture"].finditer(src)]
    assert got == ["shape.hrl", "kernel/include/file.hrl", "lists", "gen_server"]


def test_import_capture_blank_hides_comments_and_multiline_strings_only():
    src = (
        '%% -include("Hidden1.hrl").\n'
        'X = "\n-include(\\"Hidden2.hrl\\").\n".\n'
        'Y = "% not a comment".\n'
        '-include("Real.hrl").\n'
        "-import(real2, []).\n"
    )
    blank = re.compile(ERL["import_capture_blank"])
    kept = blank.sub(lambda m: m.group() if "\n" not in m.group() else re.sub(r"[^\n]", " ", m.group()), src)
    assert ERL["import_capture_multiline_only"] is True
    assert [m.group(1) or m.group(2) for m in RULES["_dependency_capture"].finditer(kept)] == ["Real.hrl", "real2"]


def test_safety_bypasses_and_high_risk():
    assert _hits("safety_bypasses", "binary_to_term(B)\nbinary_to_term(B, [safe])\nlist_to_atom(L)\n") == [
        "binary_to_term(",
        "list_to_atom(",
    ]
    assert _hits("high_risk_execution", "os:cmd(C),\nopen_port({spawn, X}, [])\n") == ["os:cmd(", "open_port("]


def test_branches_and_concurrency():
    assert _hits("branch", "case X of\n    a -> 1\nend") == ["case", "of", "->"]
    assert _hits("concurrency", "Pid = spawn(fun() -> ok end),\nPid ! stop,\n") == ["spawn(", "! s"]


def test_doc_and_test_signals():
    assert _hits("doc", '%% @doc Hello\n-doc "x".\nx() -> ok. %% plain\n') == ["%% @doc", "-doc"]
    assert _hits("test", "a_test() ->\n    ?assertEqual(1, 1).\n") == ["_test(", "?assertEqual("]


def test_every_rule_survives_pathological_input():
    payloads = [
        "f(" + "a, " * 4000 + "\n",
        "f(" + "(" * 5000 + "\n",
        "a" * 20000 + "(\n",
        "'" + "a" * 20000 + "\n",
        "f(X) when " + "a, " * 5000 + "\n",
        'X = "' + "\\" * 5000 + "\n",
        '"' + "a\n" * 5000,
        "% " + "-include(" * 5000 + "\n",
        "-include(" + '"a' * 5000 + "\n",
        "-record(" + "-record(" * 3000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
