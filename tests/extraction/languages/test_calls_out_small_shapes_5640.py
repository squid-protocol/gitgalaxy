"""
#5640: call-graph small shapes found by the DOOM corpus checks (#5630).

* shell: a command word is a call (it was declared blind); the resolver keeps the ones naming a script's functions.
* scheme: `(define name (lambda ...))` is a procedure definition, so its calls have an owner.
* shell: a function defined and closed on one line (`name() { cmd; }`) is a unit that owns its calls.
* tcl: a one-line brace body (`catch {qux}`, `if {$a} {foo}`, `after 10 {zed}`) is command position.
* scheme: the formals list of a `lambda` is not a call.
* lua / tcl: the shapes the issue named (a call after `..` or `not`, a command after `}`) are pinned as working.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _calls(lang: str, code: str, unit: str) -> list[str]:
    return _functions(lang, code)[unit]["calls_out_to"]


# --- shell ---------------------------------------------------------------------------------------


def _shell(body: str) -> list[str]:
    return _calls("shell", "#!/bin/bash\nrun() {\n" + body + "\n}\n", "run")


@pytest.mark.parametrize(
    "body, callee",
    [
        ("  log_info start", "log_info"),
        ("  wait_for_http \"$url\" || die 'no'", "wait_for_http"),
        ("  cmd && stop_one", "stop_one"),
        ("  cmd | consume", "consume"),
        ('  id=$(project_id "$x")', "project_id"),
        ("  id=$(project_id)", "project_id"),
        ("  if check_ready; then x=1; fi", "check_ready"),
        ("  [ -f x ] && log_warn y", "log_warn"),
        ("  if [ -f x ]; then log_warn y; fi", "log_warn"),
        ("  while ! probe_it; do sleep 1; done", "probe_it"),
        ("  until probe_it; do :; done", "probe_it"),
        ("  case $1 in\n    start) do_start ;;\n  esac", "do_start"),
        ("  case $1 in\n    a|b) do_ab ;;\n  esac", "do_ab"),
        ("  { cleanup; }", "cleanup"),
    ],
)
def test_shell_command_word_is_a_call(body, callee):
    assert callee in _shell(body)


@pytest.mark.parametrize(
    "body, not_callee",
    [
        ("  x=1", "x"),
        ("  n=$(( count + 1 ))", "count"),
        ("  case $1 in\n    start) : ;;\n  esac", "start"),
        ("  # note_helper is only a comment\n  :", "note_helper"),
        ("  echo helper_name", "helper_name"),
        ("  for f in a b; do :; done", "f"),
        ("  if true; then :; fi", "then"),
    ],
)
def test_shell_non_command_words_are_not_calls(body, not_callee):
    assert not_callee not in _shell(body)


def test_shell_keywords_and_builtins_are_not_calls():
    calls = _shell("  if true; then\n    echo hi\n    return 0\n  fi")
    assert not {"if", "then", "fi", "echo", "return", "true"} & set(calls)


def test_shell_script_function_calls_another():
    code = 'log_info() {\n  echo "$1"\n}\nstart_frontend() {\n  log_info up\n  wait_for_http\n}\n'
    assert _calls("shell", code, "start_frontend") == ["log_info", "wait_for_http"]
    assert "log_info" not in _calls("shell", code, "log_info")


def test_shell_pattern_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["shell"]["rules"]["calls_out"]
    assert pattern.groups == 1
    assert_redos_immune(pattern, "a" * 50000 + "=")
    assert_redos_immune(pattern, "$(" * 20000)
    assert_redos_immune(pattern, "; " * 20000 + "x:")


@pytest.mark.parametrize(
    "code, units",
    [
        ("foo() { bar; baz; }\nbar() { :; }\n", {"foo": ["bar", "baz"], "bar": []}),
        ("function foo { bar; }\nbar() { :; }\n", {"foo": ["bar"], "bar": []}),
        ("a() { b; }\nb() { a; }\nc() {\n  a\n}\n", {"a": ["b"], "b": ["a"], "c": ["a"]}),
    ],
)
def test_shell_one_line_function_is_a_unit(code, units):
    assert {n: f["calls_out_to"] for n, f in _functions("shell", code).items()} == units


def test_shell_one_line_keyword_block_is_not_a_function():
    assert "if" not in _functions("shell", "if() { x; }\nwhile() { y; }\nreal() { z; }\n")


# --- scheme --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "(define a-sarg-attack\n  (lambda (mo) (fx* (fx+ (fxremainder (p-random) 8) 1) 3)))\n",
        "(define a-sarg-attack (lambda () (fx* (fx+ (fxremainder (p-random) 8) 1) 3)))\n",
        "(define a-sarg-attack\n  (case-lambda ((mo) (fx* (p-random) 3))))\n",
        "(define a-sarg-attack (named-lambda (sarg mo) (fx* (p-random) 3)))\n",
    ],
)
def test_scheme_define_of_a_lambda_is_a_unit_that_owns_the_calls_in_it(code):
    calls = _calls("scheme", "(define (p-random) 4)\n" + code, "a-sarg-attack")
    assert {"fx*", "p-random"} <= set(calls)


def test_scheme_lambda_formals_do_not_hide_the_name():
    functions = _functions("scheme", "(define (p-random) 4)\n(define a-head-attack (lambda (actor) (p-random)))\n")
    assert "a-head-attack" in functions and "p-random" in functions


@pytest.mark.parametrize(
    "code",
    [
        "(define table (map (lambda (x) (f x)) items))\n",
        "(define limit 35)\n",
        "(define handlers (list (lambda () 1)))\n",
    ],
)
def test_scheme_define_of_a_value_is_not_a_unit(code):
    assert _functions("scheme", code + "(define (helper a) a)\n").keys() == {"helper"}


@pytest.mark.parametrize(
    "code",
    [
        "(define (g) ((lambda (y) (h y)) 1))\n",
        "(define (g) (map (lambda (y) (h y)) l))\n",
        "(define (g) (named-lambda (fn y) (h y)))\n",
    ],
)
def test_scheme_lambda_formals_are_not_calls(code):
    calls = _calls("scheme", code + "(define (h z) z)\n", "g")
    assert "h" in calls and not {"y", "fn"} & set(calls)


def test_scheme_procedure_define_is_unchanged():
    functions = _functions("scheme", "(define (f x)\n  (g x))\n(define (g y) y)\n")
    assert functions["f"]["calls_out_to"] == ["g"]


# --- lua and tcl: pinned, they already extract these shapes ------------------------------------------


def test_lua_call_after_concat_and_not():
    code = (
        "local function run_command(reason)\n"
        "  dbg_writeln(reason..format_stack_frame_info(1))\n"
        "  while not frame_has_line(2) do x = 1 end\n"
        "end\n"
    )
    assert {"dbg_writeln", "format_stack_frame_info", "frame_has_line"} <= set(_calls("lua", code, "run_command"))


def test_tcl_command_after_a_closing_brace():
    code = "proc main {} {\n    foreach x $l {\n        puts $x\n    }\n    startClient\n    if {$a} {\n        foo\n    }\n    start\n}\n"
    assert {"startClient", "foo", "start"} <= set(_calls("tcl", code, "main"))


def test_tcl_command_substitution_is_a_call():
    code = "proc main {} {\n    set a [foo 1]\n    puts [ bar [baz]]\n}\nproc foo {x} {}\nproc bar {x} {}\nproc baz {} {}\n"
    assert {"foo", "bar", "baz"} <= set(_calls("tcl", code, "main"))


@pytest.mark.parametrize(
    "line, callee",
    [
        ("catch {qux}", "qux"),
        ("catch { qux 1 } err", "qux"),
        ("after 10 {zed}", "zed"),
        ("if {$a} {foo}", "foo"),
        ("if {$a} {foo} else {bar}", "bar"),
        ("try {baz} finally {cleanup}", "cleanup"),
        ("eval {run_it}", "run_it"),
    ],
)
def test_tcl_one_line_brace_body_is_a_call(line, callee):
    assert callee in _calls("tcl", "proc main {} {\n    " + line + "\n}\n", "main")


def test_tcl_data_braces_are_not_calls():
    calls = _calls("tcl", "proc main {} {\n    set l {alpha beta}\n    puts {gamma}\n}\n", "main")
    assert not {"alpha", "beta", "gamma"} & set(calls)


def test_tcl_pattern_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["tcl"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "[" * 50000)
    assert_redos_immune(pattern, "[ " * 20000 + "x:")
    assert_redos_immune(pattern, "} " * 20000 + "{ " * 20000)
    assert_redos_immune(pattern, "catch " * 20000 + "{")
