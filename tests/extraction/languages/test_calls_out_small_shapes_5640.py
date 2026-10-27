"""
#5640: call-graph small shapes found by the DOOM corpus checks (#5630).

* shell: a command word is a call (it was declared blind); the resolver keeps the ones naming a script's functions.
* scheme: `(define name (lambda ...))` is a procedure definition, so its calls have an owner.
* shell: a subshell, process substitution, `VAR=1 cmd`, redirect prefix, `trap handler` and a pipeline stage in `$(...)`
  open a command, and a call reaches a function of a sourced file.
* shell: a function defined and closed on one line (`name() { cmd; }`) is a unit that owns its calls.
* tcl: a one-line brace body (`catch {qux}`, `if {$a} {foo}`, `after 10 {zed}`) is command position.
* scheme: the formals list of a `lambda` is not a call.
* lua / tcl: the shapes the issue named (a call after `..` or `not`, a command after `}`) are pinned as working.
* tcl: top-level script after a proc is no proc's call (the oracle's `main` misses).

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
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
        ("  time foo", "foo"),
        ("  time -p foo", "foo"),
        ("  exec bar", "bar"),
        ("  nohup qux &", "qux"),
        ("  x=$(time foo)", "foo"),
        ("  if time foo; then :; fi", "foo"),
        ("  cmd && exec bar", "bar"),
        ("  ( sub_a )", "sub_a"),
        ("  (sub_b; other)", "sub_b"),
        ("  (cd dir && sub_c)", "sub_c"),
        ("  diff <(feed_a) <(feed_b)", "feed_b"),
        ("  while read l; do :; done < <(feed_c)", "feed_c"),
        ("  x=$(a | piped_a)", "piped_a"),
        ("  x=$(a && listed_a)", "listed_a"),
        ("  x=$(a || listed_b)", "listed_b"),
        ("  FOO=1 envcmd_a", "envcmd_a"),
        ("  FOO=1 BAR=$x envcmd_b arg", "envcmd_b"),
        ("  cmd | FOO=1 envcmd_c", "envcmd_c"),
        ("  x=$(FOO=1 envcmd_d)", "envcmd_d"),
        ("  >/dev/null redir_a", "redir_a"),
        ("  2>&1 redir_b", "redir_b"),
        ("  trap cleanup_a EXIT", "cleanup_a"),
        ("  trap cleanup_b INT TERM", "cleanup_b"),
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
        ("  exec >log", "log"),
        ("  exec 3>&1", "3"),
        ("  time", "time"),
        ("  echo time foo", "foo"),
        ("  if true; then :; fi", "then"),
        ("  arr=(one two)", "one"),
        ("  arr+=(one two)", "two"),
        ("  n=$(( count + 1 ))", "count"),
        ("  (( count++ ))", "count"),
        ("  (( count = other + 1 ))", "other"),
        ("  x=$(a | b)", "x"),
        ("  FOO=1 BAR=2", "BAR"),
        ("  FOO=$(inner_a arg) bar_a", "arg"),
        ("  >/dev/null", "dev"),
        ("  trap - EXIT", "EXIT"),
        ("  trap EXIT", "EXIT"),
        ("  trap '' INT", "INT"),
        ("  echo a | b", "a"),
        ('  [[ "$l" =~ ^(HOMEBREW_|(all|no)_proxy=) ]] || continue', "HOMEBREW_"),
        ('  [[ "$l" =~ ^(HOMEBREW_|(all|no)_proxy=) ]] || continue', "all"),
        ("  [[ $x =~ (alpha|beta) ]]", "alpha"),
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


def test_shell_calls_resolve_across_sourced_files():
    """The command words of one script reach the functions of the files it sources (and `. file`)."""
    lib = 'log_info() {\n  echo "$1"\n}\nstop_one() {\n  log_info stopping\n}\n'
    run = 'source "$DIR/lib.sh"\nstart() {\n  log_info up\n  id=$(stop_one x | cat)\n  ( other_one )\n}\n'
    dot = ". ./lib.sh\ngo() {\n  FOO=1 stop_one\n}\n"
    files = []
    for path, code in (("s/lib.sh", lib), ("s/run.sh", run), ("s/dot.sh", dot)):
        parsed = StructuralExtractor("shell", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append({"path": path, "lang_id": "shell", "functions": parsed["functions"], "classes": []})
    edges = [{"src": "s/run.sh", "dst": "s/lib.sh"}, {"src": "s/dot.sh", "dst": "s/lib.sh"}]
    sites, _ = resolve_calls(files, edges)
    resolved = {(x["src_name"], x["dst_name"], x["dst_path"]) for x in sites if x["dst_name"]}
    assert resolved == {
        ("stop_one", "log_info", "s/lib.sh"),
        ("start", "log_info", "s/lib.sh"),
        ("start", "stop_one", "s/lib.sh"),
        ("go", "stop_one", "s/lib.sh"),
    }


def test_shell_pattern_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["shell"]["rules"]["calls_out"]
    assert pattern.groups == 1
    assert_redos_immune(pattern, "a=b " * 20000 + "=")
    assert_redos_immune(pattern, "(" * 20000)
    assert_redos_immune(pattern, "$(a " + "| " * 20000 + "x")
    assert_redos_immune(pattern, ">a " * 20000 + "=")
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


@pytest.mark.parametrize(
    "block",
    ["if ! up; then\n  sleep 1\nfi\n", "while up; do\n  sleep 1\ndone\n", "case $x in\n  a) up ;;\nesac\n"],
)
def test_shell_nameless_block_after_a_one_line_function_does_not_borrow_its_name(block):
    """#6266: `if ! up; then` below `up() { psql; }` was a second `up` that ran to the `fi` (sqldoom run_with_server.sh)."""
    code = "#!/bin/bash\nup() { psql; }\n" + block
    units = StructuralExtractor("shell", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert [(f["start_line"], f["loc"]) for f in units if f["name"] == "up"] == [(2, 1)]


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


@pytest.mark.parametrize(
    "form",
    [
        "(let ((tmp (h z))) tmp)",
        "(let* ((tmp (h z)) (n 1)) tmp)",
        "(letrec ((tmp (h z))) tmp)",
    ],
)
def test_scheme_first_let_binding_name_is_not_a_call(form):
    calls = _calls("scheme", "(define (g z)\n  " + form + ")\n(define (h z) z)\n", "g")
    assert "h" in calls and "tmp" not in calls


def test_scheme_cond_clause_test_is_still_a_call():
    assert "even?" in _calls("scheme", "(define (g z)\n  (cond ((even? z) 1) (else 2)))\n", "g")


def test_scheme_procedure_define_is_unchanged():
    functions = _functions("scheme", "(define (f x)\n  (g x))\n(define (g y) y)\n")
    assert functions["f"]["calls_out_to"] == ["g"]


# --- lua and tcl: pinned, they already extract these shapes ------------------------------------------


def _lua(body: str) -> list[str]:
    return _calls("lua", "local function run(reason)\n  " + body + "\nend\n", "run")


@pytest.mark.parametrize(
    "body, callee",
    [
        ("dbg_writeln(reason..format_stack_frame_info(1))", "format_stack_frame_info"),
        ("x = reason .. y .. z1(1) .. w1(2)", "w1"),
        ("x = reason..a2(1)..b2(2)", "b2"),
        ("x = obj:m1(1)..obj.m2(2)", "m2"),
        ("while not frame_has_line(2) do x = 1 end", "frame_has_line"),
        ("if not g(1) then x = 1 end", "g"),
        ("repeat x = 1 until not h(2)", "h"),
        ("x = not i(3) and j(4)", "j"),
        ("y = (not k(5))", "k"),
        ("z = not not l(6)", "l"),
        ("while not obj:m(1) do x = 1 end", "m"),
        ("print(not ok(1), (not pk(2)))", "pk"),
        ("local t = {not a1(1), b1(2)}", "b1"),
        ("a = not (c1(1))", "c1"),
    ],
)
def test_lua_call_after_concat_or_not(body, callee):
    assert callee in _lua(body)


def test_lua_anonymous_function_calls_belong_to_the_enclosing_unit():
    """C8: a function expression inside a named unit is part of it (`debugger.lua` `repl = function` is top level)."""
    code = "local function f()\n  local cb = function(x)\n    foo(x)\n  end\n  g(function() bar() end)\nend\n"
    assert set(_calls("lua", code, "f")) == {"foo", "g", "bar"}


def test_lua_top_level_function_expression_is_not_a_named_unit():
    """`repl = function(r) ... end` at file level has no enclosing named unit (anonymous is never func_start, #5685):
    its calls sit in a synthetic bucket the DB does not store, so the #5630 oracle, which hands them to the previous
    unit, reports them as `run_command` misses (edge-classic debugger.lua:456)."""
    code = "local function a()\n  x()\nend\nrepl = function(r)\n  while not frame_has_line(1) do y() end\nend\n"
    functions = _functions("lua", code)
    assert functions["a"]["calls_out_to"] == ["x"]
    assert "repl" not in functions
    assert {"frame_has_line", "y"} <= set(functions["Anonymous_Block"]["calls_out_to"])


def test_tcl_command_after_a_closing_brace():
    code = "proc main {} {\n    foreach x $l {\n        puts $x\n    }\n    startClient\n    if {$a} {\n        foo\n    }\n    start\n}\n"
    assert {"startClient", "foo", "start"} <= set(_calls("tcl", code, "main"))


def test_tcl_top_level_script_after_a_proc_is_not_the_procs_call():
    """odamex `tests/bugs/*.tcl`: `startClient` / `start` follow `proc main {...}`'s closing brace at file level, so
    they are script, not part of `main`. The tcl rule has no top-level unit (its calls are not stored); the #5630
    oracle hands everything after the last `proc` to it and reports them as `main` misses."""
    code = (
        "proc main {} {\n    wait\n    if {$a} {\n        foo\n    }\n}\n"
        "startClient\nset error [catch { main }]\nif { $error } {\n puts bad\n}\nstart\nend\n"
    )
    functions = _functions("tcl", code)
    assert set(functions) == {"main"}
    assert set(functions["main"]["calls_out_to"]) == {"wait", "foo"}


def test_tcl_foreach_switch_namespace_bodies():
    code = (
        "proc main {} {\n    foreach x $l {\n        puts $x\n    }\n    switch $a {\n        y {\n            doY\n        }\n"
        "    }\n    namespace eval ns {\n        nsCall\n    }\n    after_all\n}\n"
    )
    assert {"doY", "nsCall", "after_all"} <= set(_calls("tcl", code, "main"))


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
