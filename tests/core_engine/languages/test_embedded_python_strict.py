"""embedded_python strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py as part of
splitting that file into tests/core_engine/languages/, one file per language,
mirroring tests/extraction/languages/. See that file's git history for the
original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest
import re

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE REDOS SWEEP: "BARE IDENTIFIER BEFORE ARROW" FAMILY
# ==============================================================================
# All found by a systematic ReDoS sweep across every language's compiled
# patterns (not just the ones with an existing historical-bug comment):
# an unbounded identifier/word-run quantifier with no preceding \b anchor,
# immediately followed by a required-but-often-absent literal suffix
# (=>, ->, __c.getInstance, etc.). Because the leading character class has
# no boundary anchor, the engine retries the greedy-then-backtrack match at
# EVERY position in a long run of matching characters -- O(n^2) total, not
# exponential, but still a real DoS risk on a single pathologically long
# line (e.g. minified/obfuscated code). All bounded with numeric clamps
# instead of possessive quantifiers (`*+`), since those aren't available
# until Python 3.11 and this package supports 3.9+.


def test_embedded_python_comprehensions_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]["comprehensions"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert pattern.search("[x for x in range(10)]")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SWEEP: `@`-PREFIXED LEADING-\b BOUNDARY BUGS
# ==============================================================================
# Found while investigating dart's `test_skip` (`@Ignore` never matched) and
# broadening the earlier find_symbolic_boundary_bugs.py-style sweep to also
# check the START of each \b(...)\b alternative, not just the end. `@` is a
# non-word character, so a shared LEADING \b before a `@`-prefixed
# alternative can only fire when a word character immediately precedes the
# `@` -- never true for how annotations/attributes/decorators are actually
# written (always preceded by whitespace or a line start). This silently
# blinded 10 already-"closed" or partially-fixed languages to nearly all of
# their annotation-based structural signatures. Each language's own
# dedicated closure PR already covers this signature; these are targeted
# regressions for the specific alternatives found broken, bundled together
# the same way the earlier ReDoS (#631) and symbolic-\b (#637) cross-language
# sweeps were.


def test_embedded_python_route_decorators_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]
    assert r["ssr_boundaries"].search('@app.get("/")')
    assert r["ssr_boundaries"].search('@app.post("/")')


# ==============================================================================
# EMBEDDED_PYTHON: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #580)
# ==============================================================================
# NOTE: Two embedded_python regression tests already exist earlier in this
# file and are NOT duplicated here:
#   - test_embedded_python_comprehensions_redos_immunity (comprehensions bound)
#   - test_embedded_python_route_decorators_leading_boundary_regression
#     (ssr_boundaries' @app.get/@app.post leading-@ fix)
EP_RULES = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]

_EMBEDDED_PYTHON_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if button.value:\n    pass", "raise ValueError('x')"),
    ("args", "def blink(pin, times=3):", None),
    ("structural_boundaries", "import machine", None),
    ("func_start", "def blink():", None),
    ("class_start", "class Robot:", None),
    ("safety", "try:\n    read_sensor()\nexcept OSError:\n    pass", None),
    ("safety_bypasses", "except Exception:\n    pass", "except OSError:\n    handle(e)"),
    ("high_risk_execution", "machine.reset()", "print('safe')"),
    ("io", "i2c = I2C(0, scl=Pin(9), sda=Pin(8))", None),
    ("api", "def read_temperature():\n    pass", None),
    ("state_mutation", "led.value(1)", None),
    ("dead_code", "# def old_blink():", "# just a note"),
    ("doc", '"""Blink the onboard LED."""', None),
    ("test", "def test_login():\n    assert True", None),
    ("concurrency", "async def main():\n    await asyncio.sleep(1)", None),
    ("ui_framework", "display.fill(0)", None),
    ("closures", "cb = lambda pin: pin.value()", None),
    ("globals", "global counter", None),
    ("decorators", "@app.route('/status')\ndef status():", None),
    ("generics", "def read() -> Optional[int]:", None),
    ("comprehensions", "[x for x in range(10)]", None),
    ("scientific", "import ulab as np", None),
    ("reflection_metaprogramming", "getattr(sensor, 'read')", None),
    ("import", "from machine import Pin", None),
    ("ownership", "__author__ = 'Jane Doe'", None),
    ("planned_debt", "# TODO: add debouncing", None),
    ("fragile_debt", "# HACK: temporary polling workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the boot contract", None),
    ("ssr_boundaries", 'microdot.Response("ok")', None),
    ("events", "pin.irq(trigger=Pin.IRQ_FALLING, handler=on_press)", None),
    ("macros", "const(BAUD_RATE = 9600)", None),
    ("pointers", "addr = uctypes.addressof(buf)", None),
    ("memory_alloc", "buf = bytearray(64)", None),
    ("inline_asm", "@micropython.asm_thumb\ndef delay(r0):", None),
    ("telemetry", "logger.info('boot complete')", None),
    ("debug_prints", "print('debug value:', x)", None),
    ("explicit_casts", "int(raw_value)", None),
    ("panics_and_aborts", "raise ValueError('bad reading')", None),
    ("thread_sleeps", "time.sleep(1)", None),
    ("bitwise_ops", "mask = flags << 2", None),
    ("sync_locks", "lock = _thread.allocate_lock()", None),
    ("immutability_locks", "cfg = mappingproxy({'x': 1})", None),
    ("cleanup", "i2c.close()", None),
    ("encapsulation", "self._buffer = bytearray(16)", None),
    ("listeners", "pin.irq(handler=on_change)", None),
    ("test_skip", "@pytest.mark.skip", None),
    ("serialization_parsing", "data = ujson.loads(raw)", None),
    ("regex_execution", "m = ure.match(r'^boot', line)", None),
    ("time_date_logic", "now = utime.ticks_ms()", None),
    ("ipc_rpc_bridges", "i2c = machine.I2C(0)", None),
]


@pytest.mark.parametrize("signature,positive,negative", _EMBEDDED_PYTHON_SIMPLE_CASES)
def test_embedded_python_signature_positive_and_negative(signature, positive, negative):
    pattern = EP_RULES[signature]
    assert pattern is not None, f"embedded_python's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"embedded_python {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"embedded_python {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_embedded_python_test_signature_pytest_convention_boundary_regression():
    """
    Regression test for a confirmed real bug: `test_` was wrapped inside the
    shared `\\b(unittest|pytest|assert|test_|setUp|tearDown|Mock)\\b` group.
    `_` is a word character, so the trailing `\\b` after `test_` demands a
    NON-word character immediately follow -- never true for the standard
    pytest naming convention, where a name always continues with more word
    characters (`test_login`, `test_parse_url`). Only a bare, standalone
    trailing "test_" (unrealistic) ever matched.

    Reproduced directly against the *old* (buggy) pattern here, then verified
    the fix (anchored as `def[ \\t]+test_`, matching python's own fix for the
    identical trap) resolves it -- using snippets with no `assert`/`Mock`/etc
    present, so the other alternatives can't mask whether the `test_` path
    itself actually fires.
    """
    old_buggy_pattern = re.compile(r"\b(unittest|pytest|assert|test_|setUp|tearDown|Mock)\b")
    assert not old_buggy_pattern.search("def test_login():\n    pass"), (
        "sanity check failed: the old pattern was expected to NOT match this realistic case"
    )
    assert not old_buggy_pattern.search("def test_parse_url():\n    pass")
    assert old_buggy_pattern.search("test_ "), "sanity check: old pattern only matched the unrealistic trailing form"

    fixed_pattern = EP_RULES["test"]
    assert fixed_pattern.search("def test_login():\n    pass"), "fix did not resolve def test_login()"
    assert fixed_pattern.search("def test_parse_url():\n    pass"), "fix did not resolve def test_parse_url()"
    assert fixed_pattern.search("async def test_boot_sequence():\n    pass"), (
        "fix did not resolve an async pytest-style test function"
    )
    # The other alternatives must still work unaffected by the fix.
    assert fixed_pattern.search("import unittest")
    assert fixed_pattern.search("m = Mock()")
    assert fixed_pattern.search("def setUp(self):")
    assert fixed_pattern.search("def tearDown(self):")
    assert fixed_pattern.search("assert x == 1")


def test_embedded_python_generics_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `generics`'
    `\\[[^\\]]*\\]` was unbounded. On a run of repeated unclosed openers
    (e.g. "List[List[List[..."), every "List[" occurrence is a fresh,
    unanchored search start; at each one the engine greedily consumes to
    end-of-string then backtracks character-by-character looking for a "]"
    that never appears anywhere -- O(n) work per start position across O(n)
    start positions, for O(n^2) total.

    Confirmed via direct scaling measurement against the pre-fix pattern
    before bounding it (~4x runtime per size doubling at
    n=2000/4000/8000/16000 -- the signature of real catastrophic
    backtracking, not the ~2x of a linear scan): 0.0151s / 0.0595s /
    0.2366s / 0.9433s. Bounded to {0,300}; verify the fixed pattern stays
    immune and still matches realistic (including one-level-nested, per
    Rule 11) generic annotations.
    """
    old_buggy_pattern = re.compile(
        r"\b(?:List|Dict|Set|Tuple|Optional|Union|Any|Callable|Sequence|Iterable)\[[^\]]*\]|->"
    )
    import time as _time

    durations = []
    for n in (2000, 4000, 8000, 16000):
        payload = "List[" * n
        start = _time.perf_counter()
        list(old_buggy_pattern.finditer(payload))
        durations.append(_time.perf_counter() - start)
    # Each doubling should show a roughly 4x increase for real O(n^2); assert
    # the ratio between the last two measurements is well above the ~2x a
    # linear-time pattern would show, confirming this really is quadratic.
    assert durations[-1] / durations[-2] > 2.0, (
        f"expected quadratic scaling on the pre-fix pattern, got durations={durations}"
    )

    pattern = EP_RULES["generics"]
    assert_redos_immune(pattern, "List[" * 40000, timeout_sec=3.0)
    assert pattern.search("def read() -> Optional[int]:")
    assert pattern.search("def f(x: Dict[str, List[int]]) -> None: ..."), (
        "fixed pattern lost one-level-nesting coverage (Dict[str, List[int]])"
    )


def test_embedded_python_spec_exposure_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `spec_exposure`'s
    SPEC alternative chains `\\d+` (unbounded) directly into `[^\\]]*`
    (also unbounded, and its character class overlaps `\\d+`'s -- digits
    satisfy both). On a long run of digits with no closing "]" (e.g.
    "[SPEC-" + "1" * n), `\\d+` greedily consumes them all, then backtracks
    one digit at a time while `[^\\]]*` re-consumes the released digit and
    re-fails to find "]" -- the classic adjacent-overlapping-quantifier
    shape.

    Confirmed via direct scaling measurement against the pre-fix pattern
    (~4x runtime per size doubling at n=2000/4000/8000/16000: 0.0030s /
    0.0119s / 0.0473s / 0.1886s). Bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`; verify the fixed pattern stays immune and still
    matches realistic SPEC/audit tags.
    """
    old_buggy_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I)
    import time as _time

    durations = []
    for n in (2000, 4000, 8000, 16000):
        payload = "[SPEC-" + "1" * n
        start = _time.perf_counter()
        list(old_buggy_pattern.finditer(payload))
        durations.append(_time.perf_counter() - start)
    assert durations[-1] / durations[-2] > 2.5, (
        f"expected quadratic scaling on the pre-fix pattern, got durations={durations}"
    )

    pattern = EP_RULES["spec_exposure"]
    assert_redos_immune(pattern, "[SPEC-" + "1" * 80000, timeout_sec=3.0)
    assert pattern.search("# [SPEC-123] implements the boot contract")
    assert pattern.search("# [audit] verified")


def test_embedded_python_func_start_and_class_start_capture_names():
    fs = EP_RULES["func_start"]
    m = fs.search("def read_temp():")
    assert m is not None
    assert m.group(1) == "read_temp"
    assert fs.search("    @staticmethod\n    def read_temp():"), "func_start failed to step over a decorator"
    assert fs.search("async def read_temp():")

    cs = EP_RULES["class_start"]
    m2 = cs.search("class Robot:")
    assert m2 is not None
    assert m2.group(1) == "Robot"


def test_embedded_python_api_excludes_underscore_prefixed_definitions():
    """api captures implicit-public root defs/classes; a leading underscore is explicitly private."""
    pattern = EP_RULES["api"]
    assert pattern.search("def read_temperature():\n    pass")
    assert pattern.search("class Robot:\n    pass")
    assert not pattern.search("def _read_temperature():\n    pass"), (
        "api incorrectly matched an underscore-prefixed function"
    )
    assert not pattern.search("class _Internal:\n    pass"), "api incorrectly matched an underscore-prefixed class"


def test_embedded_python_import_dependency_capture():
    dep_pattern = EP_RULES["_dependency_capture"]
    m = dep_pattern.search("from machine import Pin")
    assert m is not None
    assert m.group(1) == "machine"

    m2 = dep_pattern.search("import network")
    assert m2 is not None
    assert m2.group(1) == "network"


def test_embedded_python_structural_boundaries_and_args():
    boundaries = EP_RULES["structural_boundaries"]
    for kw_snippet in ("def foo():", "class Foo:", "return x", "import os", "yield x", "nonlocal y"):
        assert boundaries.search(kw_snippet), f"structural_boundaries failed to match {kw_snippet!r}"

    args = EP_RULES["args"]
    assert args.search("def foo(a, b):")
    assert args.search("async def foo(a, b):")
    assert args.search("lambda x: x + 1")


def test_embedded_python_bitwise_ops_and_closures_do_not_collide():
    """
    Known ambiguity pattern from the issue template: Python's `lambda`
    keyword shares no token with `<<`, `>>`, `^`, `~`, `&`, `|`.
    """
    bitwise = EP_RULES["bitwise_ops"]
    closures = EP_RULES["closures"]
    assert bitwise.search("mask = flags << 2")
    assert not bitwise.search("cb = lambda pin: pin.value()"), "bitwise_ops false-positived on a lambda"
    assert closures.search("cb = lambda pin: pin.value()")
    assert not closures.search("mask = flags << 2"), "closures false-positived on a bitwise shift"


def test_embedded_python_explicit_casts_vs_pointers_no_overlap():
    """
    Known ambiguity pattern from the issue template: `explicit_casts`
    checks builtin type calls (int(, str(, ...) plus a bare `cast(`;
    `pointers` checks uctypes/machine.mem-specific tokens. No shared
    token between them.
    """
    casts = EP_RULES["explicit_casts"]
    pointers = EP_RULES["pointers"]
    assert casts.search("int(raw_value)")
    assert not casts.search("uctypes.addressof(buf)"), "explicit_casts false-positived on a uctypes call"
    assert pointers.search("uctypes.addressof(buf)")
    assert not pointers.search("int(raw_value)"), "pointers false-positived on a builtin cast"


def test_embedded_python_test_vs_regex_execution_no_collision():
    """
    Known ambiguity pattern from the issue template: embedded_python's
    regex library is `ure` (`ure.compile`/`ure.search`/`ure.match`/
    `ure.sub`), not a `.test(`-style method, so it shares no token with
    `test`'s unittest/pytest/assert/Mock/setUp/tearDown/def-test_
    alternatives.
    """
    test = EP_RULES["test"]
    regex_execution = EP_RULES["regex_execution"]
    assert test.search("def test_login():\n    pass")
    assert not regex_execution.search("def test_login():\n    pass"), (
        "regex_execution false-positived on a pytest-style test function"
    )
    assert regex_execution.search("m = ure.match(r'^boot', line)")
    assert not test.search("m = ure.match(r'^boot', line)"), "test false-positived on a ure.match call"


def test_embedded_python_func_start_vs_macros_no_collision():
    """
    Known ambiguity pattern from the issue template: `macros` maps to
    MicroPython's `const(...)` compile-time macro, which shares no
    `def`/`class` token with `func_start`'s executable-logic anchor.
    """
    func_start = EP_RULES["func_start"]
    macros = EP_RULES["macros"]
    assert macros.search("const(BAUD_RATE = 9600)")
    assert not func_start.search("const(BAUD_RATE = 9600)"), "func_start false-positived on a const() macro"
    assert func_start.search("def read_temp():")
    assert not macros.search("def read_temp():"), "macros false-positived on a function definition"


def test_embedded_python_safety_and_reflection_metaprogramming_intentional_double_classification():
    """
    Ambiguity sweep: `safety` and `reflection_metaprogramming` both list
    `hasattr`/`getattr` and both fire on the same
    `hasattr(sensor, 'read')`/`getattr(sensor, 'read')` call. Confirmed
    genuine, intentional double-classification (present identically in
    python's own already-hardened rules dict, not an embedded_python-only
    accident): a runtime attribute-existence probe is simultaneously a
    defensive validation technique (safety) AND a dynamic/reflective
    attribute access (reflection_metaprogramming) -- both are structurally
    true at once, the same accepted double-classification shape used
    elsewhere in this codebase (e.g. dockerfile's ENV firing both `globals`
    and `state_mutation`).
    """
    safety = EP_RULES["safety"]
    reflection = EP_RULES["reflection_metaprogramming"]

    line = "if hasattr(sensor, 'read'):"
    assert safety.search(line)
    assert reflection.search(line)

    line2 = "value = getattr(sensor, 'read', None)"
    assert safety.search(line2)
    assert reflection.search(line2)


def test_embedded_python_safety_bypasses_and_thread_sleeps_intentional_double_classification():
    """
    Ambiguity sweep: `safety_bypasses` and `thread_sleeps` both fire on
    `time.sleep(...)`. Confirmed genuine, intentional double-classification
    per the source comment on `safety_bypasses` ("blocking the event loop
    -- detrimental in embedded async"): a blocking sleep call is
    simultaneously a resource-management/thread-blocking event
    (thread_sleeps) AND, specifically in an embedded/async context, a
    safety bypass (it can starve a cooperative scheduler) -- both true at
    once, not an accidental duplication.
    """
    safety_bypasses = EP_RULES["safety_bypasses"]
    thread_sleeps = EP_RULES["thread_sleeps"]

    line = "time.sleep(5)"
    assert safety_bypasses.search(line)
    assert thread_sleeps.search(line)


def test_embedded_python_safety_bypasses_bare_except_vs_typed_except():
    """
    A bare `except:` or `except Exception:` swallows errors; a typed
    except does not. Bodies deliberately avoid a bare `pass` statement --
    `pass` is itself one of this rule's own alternatives, which would
    trigger a match for the wrong reason.
    """
    pattern = EP_RULES["safety_bypasses"]
    assert pattern.search("except:\n    log(e)")
    assert pattern.search("except Exception:\n    log(e)")
    assert not pattern.search("except OSError:\n    log(e)"), (
        "safety_bypasses incorrectly flagged a specific, typed except clause"
    )


def test_embedded_python_comprehensions_one_level_nesting():
    """
    Nested-delimiter audit (Rule 11): a comprehension nested one level
    deep inside another comprehension's iterable must still match within
    the {0,500}-bounded window fixed for ReDoS immunity.
    """
    pattern = EP_RULES["comprehensions"]
    assert pattern.search("[x for x in [y for y in range(10)]]")
    assert pattern.search("{k: v for k, v in {a: b for a, b in pairs}.items()}")
