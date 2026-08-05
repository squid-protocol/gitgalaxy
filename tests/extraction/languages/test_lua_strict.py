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


# ==============================================================================
# LUA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #594)
# ==============================================================================
LUA_RULES = LANGUAGE_DEFINITIONS["lua"]["rules"]

_LUA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then", None),
    ("args", "function foo(x)", None),
    ("structural_boundaries", "local x = 5", None),
    ("func_start", "function foo()", None),
    ("class_start", "---@class Foo", None),
    ("safety", "local ok, err = pcall(foo)", None),
    ("safety_bypasses", "rawget(t, k)", None),
    ("high_risk_execution", 'os.execute("ls")', None),
    ("io", "io.open(path)", None),
    ("api", "function foo()", None),
    ("state_mutation", "x = 5", None),
    ("dead_code", "-- local x = 5", None),
    ("doc", "---@param x string", None),
    ("test", 'describe("foo", function() end)', None),
    ("concurrency", "coroutine.create(f)", None),
    ("ui_framework", "love.draw()", None),
    ("closures", "local f = function(x) end", None),
    ("globals", "_G.foo = 1", None),
    ("decorators", "---@public", None),
    ("generics", "---@generic T", None),
    ("comprehensions", "for k,v in pairs(t) do end", None),
    ("scientific", "math.sqrt(4)", None),
    ("reflection_metaprogramming", "__index", None),
    ("import", 'require("foo")', None),
    ("ownership", "-- Author: Jane Doe", None),
    ("planned_debt", "-- TODO: refactor", None),
    ("fragile_debt", "-- HACK: workaround", None),
    ("spec_exposure", "-- [SPEC-123]", None),
    ("ssr_boundaries", 'ngx.say("hi")', None),
    ("events", "part.Connect(func)", None),
    ("dependency_injection", 'container:resolve("foo")', None),
    ("pointers", 'ffi.new("int[1]")', None),
    ("memory_alloc", "ffi.C.malloc(10)", None),
    ("telemetry", 'log.info("msg")', None),
    ("debug_prints", 'print("debug")', None),
    ("explicit_casts", "tonumber(x)", None),
    ("panics_and_aborts", 'error("err")', None),
    ("thread_sleeps", "task.wait(1)", None),
    ("bitwise_ops", "a & b", None),
    ("sync_locks", "local mutex = Mutex.new()", None),
    ("immutability_locks", "local x <const> = 5", None),
    ("cleanup", "file:close()", None),
    ("encapsulation", "local x = 5", None),
    ("listeners", "emitter:on('event', cb)", None),
    ("test_skip", 'xit("skip this")', None),
    ("serialization_parsing", "cjson.decode(str)", None),
    ("regex_execution", "string.match(s, pattern)", None),
    ("time_date_logic", "os.time()", None),
    ("ipc_rpc_bridges", 'os.execute("ls")', None),
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
