"""lua strict structural-signature coverage.

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

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# LUA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #594)
# ==============================================================================
LUA_RULES = LANGUAGE_DEFINITIONS["lua"]["rules"]

_LUA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then", "local total = sum + offset"),
    ("args", "function foo(x)", "foo(x)"),
    ("structural_boundaries", "local x = 5", "x = 5"),
    ("func_start", "function foo()", "local f = function() end"),
    ("class_start", "---@class Foo", "-- @class Foo (removed)"),
    ("safety", "local ok, err = pcall(foo)", "local ok, err = try_call(foo)"),
    ("safety_bypasses", "rawget(t, k)", "local value = t[k]"),
    ("high_risk_execution", 'os.execute("ls")', "os.getenv('PATH')"),
    ("io", "io.open(path)", "io.write(msg)"),
    ("api", "function foo()", "local function _internal() end"),
    ("state_mutation", "x = 5", "if x == 5 then"),
    ("dead_code", "-- local x = 5", "-- this needs fixing later"),
    ("doc", "---@param x string", "-- regular comment, not doc"),
    ("test", 'describe("foo", function() end)', "local item = fetchItem()"),
    ("concurrency", "coroutine.create(f)", "coroutine.running()"),
    ("ui_framework", "love.draw()", "local w, h = display.getSize()"),
    ("closures", "local f = function(x) end", "function foo(x) end"),
    ("globals", "_G.foo = 1", "local Foo = 1"),
    ("decorators", "---@public", "-- @public (not a real annotation)"),
    ("generics", "---@generic T", "---@param T string"),
    ("comprehensions", "for k,v in pairs(t) do end", "for i=1,10 do end"),
    ("scientific", "math.sqrt(4)", "local half = x / 2"),
    ("reflection_metaprogramming", "__index", "local _index = 1"),
    ("import", 'require("foo")', "local isRequired = true"),
    ("ownership", "-- Author: Jane Doe", "-- Reviewed: Jane Doe"),
    ("planned_debt", "-- TODO: refactor", "-- DONE: refactored, no further action"),
    ("fragile_debt", "-- HACK: workaround", "-- NOTE: applied a clean, permanent fix"),
    ("spec_exposure", "-- [SPEC-123]", "-- [TICKET-456]"),
    ("ssr_boundaries", 'ngx.say("hi")', "ngx.log(ngx.ERR, msg)"),
    ("events", "part.Connect(func)", "part.Disconnect(func)"),
    ("dependency_injection", 'container:resolve("foo")', 'container:has("foo")'),
    ("pointers", 'ffi.new("int[1]")', 'ffi.load("mylib")'),
    ("memory_alloc", "ffi.C.malloc(10)", "ffi.C.strlen(s)"),
    ("telemetry", 'log.info("msg")', 'log.setLevel("debug")'),
    ("debug_prints", 'print("debug")', "io.read()"),
    ("explicit_casts", "tonumber(x)", "tostringify(x)"),
    ("panics_and_aborts", 'error("err")', "assert_equals(a, b)"),
    ("thread_sleeps", "task.wait(1)", "task.spawn(fn)"),
    ("bitwise_ops", "a & b", "if a ~= b then"),
    ("sync_locks", "local mutex = Mutex.new()", "local locker = KeyHolder.new()"),
    ("immutability_locks", "local x <const> = 5", "local x <close> = 5"),
    ("cleanup", "file:close()", "local data = file:read()"),
    ("encapsulation", "local x = 5", "x = 5"),
    ("listeners", "emitter:on('event', cb)", "emitter:off('event', cb)"),
    ("test_skip", 'xit("skip this")', 'it("runs normally")'),
    ("serialization_parsing", "cjson.decode(str)", "cjson.safe.decode(str)"),
    ("regex_execution", "string.match(s, pattern)", "string.format(s, val)"),
    ("time_date_logic", "os.time()", 'os.getenv("PATH")'),
    ("ipc_rpc_bridges", 'os.execute("ls")', "coroutine.status(co)"),
]


_LUA_DEEP_CASES = [
    # --- branch ---
    ("branch", "goto skip_label", "my_goto = 1"),
    ("branch", "continue", "local continue_flag = true"),
    ("branch", "elseif\n  condition\nthen", "local if_true = 1"),
    ("branch", "for i, v in ipairs(t) do", "local format = 1"),
    ("branch", "repeat\nuntil x == 0", "local until_now = 0"),

    # --- args ---
    ("args", "function obj:method(x, y)", "obj:method(x, y)"),
    ("args", "function foo<T>(x: T)", "local function_pointer = foo"),
    ("args", "function foo<T, U = Array<T>>(x: T)", "foo<T>(x)"),
    ("args", "function \n foo \n ( \n x \n )", "function_name = 1"),
    ("args", "function(a, b, ...)", "if function_called then"),

    # --- func_start ---
    ("func_start", "export function my_api()", "local f = function() end"),
    ("func_start", "local\nfunction\nfoo\n()", "return function()"),
    ("func_start", "function tbl.foo:bar()", "function_name = 1"),
    ("func_start", "function generic_func<T>()", "generic_func<T>()"),
    ("func_start", "function deeply_nested<T, U = Array<T>>()", "deeply_nested()"),

    # --- class_start ---
    ("class_start", "export type User = {", "local lowercase_type = {}"),
    ("class_start", "type GameState = {", "type(GameState) == 'table'"),
    ("class_start", "export MyClass = {", "MyClass.foo = 1"),
    ("class_start", "local SomeObject\n = \n {", "local SomeObject = 1"),
    ("class_start", "---@class My_Class", "-- @class My_Class"),

    # --- structural_boundaries ---
    ("structural_boundaries", "export type", "exported = true"),
    ("structural_boundaries", "local x < const > = 1", "x = 1"),
    ("structural_boundaries", "<toclose>", "toclose = true"),
    ("structural_boundaries", "module('mymod')", "module_name = 1"),
    ("structural_boundaries", "require  (  'mod'  )", "requires_auth = true"),
]

@pytest.mark.parametrize("signature,positive,negative", _LUA_SIMPLE_CASES)
def test_lua_signature_positive_and_negative(signature, positive, negative):
    pattern = LUA_RULES[signature]
    assert pattern is not None, f"lua's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"lua {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"lua {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


@pytest.mark.parametrize("signature,positive,negative", _LUA_DEEP_CASES)
def test_lua_signature_deep_cases(signature, positive, negative):
    pattern = LUA_RULES[signature]
    assert pattern is not None, f"lua's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"lua {signature!r} failed to match deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), (
            f"lua {signature!r} incorrectly matched deep negative case: {negative!r}"
        )


def test_lua_listeners_on_call_boundary_regression():
    """
    Regression test: `on\\s*\\(` ends on `(` (non-word), so the shared
    trailing \\b could only fire when a word char immediately followed
    the paren -- never true for the common real call shape
    `emitter:on('event', cb)`, where a quote follows.
    """
    pattern = LUA_RULES["listeners"]
    assert pattern.search("emitter:on('event', cb)"), "on(...) still didn't match its most common form"
    assert pattern.search("emitter:subscribe(topic)")
    assert pattern.search("part.Connect(func)")


def test_lua_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 7 pairs the automated ambiguity sweep flagged, mostly
    centered on Lua 5.4's `<const>`/`<close>` attribute syntax
    (cleanup<->concurrency, cleanup<->safety, cleanup<->
    structural_boundaries, concurrency<->safety, concurrency<->
    structural_boundaries, safety<->structural_boundaries) plus
    dead_code<->doc (sharing "return"). All confirmed non-bugs:
    - A `<close>`-attributed local variable is genuinely triple-
      classified by design (it's simultaneously a safety mechanism, a
      structural declaration modifier, and a cleanup signal) -- verified
      directly, not a false collision.
    - "close" appearing in both `uv.close` (concurrency) and `io.close`/
      `ffi.C.free` (cleanup) are different, correctly-namespaced tokens
      that don't actually collide on the same real code.
    - dead_code's `--`/`--[=*[` comment-prefix requirement fully
      disambiguates it from doc's `---@return` EmmyLua tag (three
      dashes, not two) -- confirmed neither matches the other's positive
      case.
    """
    dead_code = LUA_RULES["dead_code"]
    doc = LUA_RULES["doc"]
    cleanup = LUA_RULES["cleanup"]
    safety = LUA_RULES["safety"]
    structural_boundaries = LUA_RULES["structural_boundaries"]
    concurrency = LUA_RULES["concurrency"]

    emmy_return = "---@return string"
    assert doc.search(emmy_return)
    assert not dead_code.search(emmy_return)

    commented_return = "-- return x"
    assert dead_code.search(commented_return)
    assert not doc.search(commented_return)

    close_var = "local f <close> = io.open(path)"
    assert cleanup.search(close_var) and safety.search(close_var) and structural_boundaries.search(close_var)

    uv_close = "uv.close(handle)"
    assert concurrency.search(uv_close)
    assert not cleanup.search(uv_close), "cleanup incorrectly matched uv.close (a distinct, namespaced token)"


def test_lua_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): lua's explicit_casts
    (`tonumber`/`tostring`/`ffi.cast`) and pointers (`ffi.new`/
    `ffi.cdef`/etc.) share `ffi.cast` intentionally (it's both a cast AND
    an FFI pointer operation), but don't otherwise collide.
    """
    casts = LUA_RULES["explicit_casts"]
    pointers = LUA_RULES["pointers"]
    assert casts.search("tonumber(x)")
    assert not casts.search('ffi.new("int[1]")'), "explicit_casts incorrectly matched an unrelated ffi.new call"
    assert pointers.search('ffi.new("int[1]")')
    assert not pointers.search("tonumber(x)"), "pointers incorrectly matched an explicit cast"


def test_lua_redos_immunity_sweep():
    """
    Issue #1070: lua had zero per-language ReDoS regression coverage.
    `args` is an explicit 3-level manually-nested paren structure
    (`\\([^()]*(?:\\([^()]*(?:\\([^()]*\\)[^()]*)*\\)[^()]*)*\\)`), the
    "nested quantifiers" shape epic #518 flagged repeatedly elsewhere.
    Diagnosed clean via `check_redos_scaling` (consistent ~2x-per-doubling
    ratios) before writing this as a permanent regression pin.
    """
    assert_redos_immune(LUA_RULES["args"], "function foo(" + "(" * 100000, timeout_sec=3.0)
