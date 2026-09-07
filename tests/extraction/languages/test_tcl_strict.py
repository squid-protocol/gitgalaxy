"""tcl strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import _best_of_timing, assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# TCL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #614, part of epic #518)
# ==============================================================================
TCL_RULES = LANGUAGE_DEFINITIONS["tcl"]["rules"]

_TCL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if {$x == 0} {", "set x 5"),
    ("args", "proc add {a b} {\n    return [expr {$a + $b}]\n}", "set x 5"),
    ("structural_boundaries", "proc foo {} {", "set x 5"),
    ("func_start", "proc add {a b} {", "set x 5"),
    ("class_start", "oo::class create Point {", "proc add {a b} {"),
    ("safety", "catch {risky} err", "risky"),
    ("safety_bypasses", "eval $cmd", "puts $cmd"),
    ("high_risk_execution", "exec ls -la", "puts hello"),
    ("io", "set f [open $path r]", "set x 5"),
    ("api", "package provide mypkg 1.0", "set x 5"),
    ("state_mutation", "set x 5", "puts $x"),
    ("dead_code", "# proc oldFunc {} {}", "# just a note"),
    ("doc", "# @param x the input value", "# just a note"),
    ("test", "do_test basic-1.1 {expr {1+1}} {2}", "expr {1+1}"),
    ("concurrency", "after 100 callback", "set x 5"),
    ("ui_framework", "button .b -text Hi", "set x 5"),
    ("closures", "set fn [apply {{x} {return $x}} 5]", "proc fn {x} {return $x}"),
    ("globals", "global x y", "set x 5"),
    ("comprehensions", "lmap x $list {expr {$x * 2}}", "foreach x $list {}"),
    ("scientific", "expr {sin($x)}", "set x 5"),
    ("reflection_metaprogramming", "trace add variable x write cb", "set x 5"),
    ("import", "package require Tcl 8.6", "set x 5"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    ("planned_debt", "# TODO: refactor this", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] compliance tag", "# just a note"),
    ("events", "bind .b <Button-1> callback", "set x 5"),
    ("telemetry", "logger::init myapp", "puts hello"),
    ("debug_prints", "puts hello", "logger::init myapp"),
    ("explicit_casts", "expr int($x)", "set x 5"),
    ("panics_and_aborts", 'error "bad state"', "return"),
    ("thread_sleeps", "after 1000", "after idle callback"),
    ("bitwise_ops", "set mask [expr {$a & $b}]", "set sum [expr {$a + $b}]"),
    ("sync_locks", "thread::mutex lock $m", "set x 5"),
    ("immutability_locks", "trace add variable x write lockCb", "set x 5"),
    ("cleanup", "close $f", "set x 5"),
    ("encapsulation", "namespace eval ::myns {", "proc publicFn {} {}"),
    ("listeners", "fileevent $sock readable cb", "set x 5"),
    ("test_skip", "-constraints unix", "set x 5"),
    # --- ADVERSARIAL & DEEP CASES ---
    # branch
    ("branch", "foreach x $items {", "try { foo } trap {POSIX} {} finally { bar }"),  # 2822 corollary 1
    ("branch", "switch -exact -- $val {", "switch_off"),
    ("branch", "elseif {$y == 2} {", "set elseif_val 1"),
    # args
    ("args", "proc foo {a {b {nested default}}} {\n    puts $a\n}", "set x 5"),  # 2 levels of nesting
    ("args", "proc bar {a {b {nested {deeply} default}}} {\n}", "set x 5"),  # 3 levels of nesting
    ("args", "proc my-cmd {a b c} {", "set x 5"),
    # func_start
    ("func_start", "proc my-command-name {a b} {", "set x 5"),
    ("func_start", "proc my::namespace::func? {x} {", "set x 5"),
    ("func_start", "proc -hidden-proc {a} {", "set x 5"),
    ("func_start", "proc is_valid!? {x} {", "set x 5"),
    ("func_start", "proc   \n  spaced_proc   \n {a} {", "set x 5"),
    # class_start
    ("class_start", "oo::class create my-class::sub-class {", "proc foo {} {"),
    ("class_start", "itcl::class MyClass? {", "proc foo {} {"),
    ("class_start", "snit::type -my-type- {", "proc foo {} {"),
    # globals
    ("globals", "set path $::env(HOME)", "set env_var 5"),
    ("globals", "upvar   #0   myvar localvar", "set upvar_var 5"),
    ("globals", "global a-b c? d!", "set global_val 5"),
]


@pytest.mark.parametrize("signature,positive,negative", _TCL_SIMPLE_CASES)
def test_tcl_signature_positive_and_negative(signature, positive, negative):
    pattern = TCL_RULES[signature]
    assert pattern is not None, f"tcl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"tcl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"tcl {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_tcl_func_start_and_class_start_capture_names():
    func_start = TCL_RULES["func_start"]
    m = func_start.search("proc add {a b} {")
    assert m and m.group(1) == "add"
    m2 = func_start.search("proc ::my::func {} {")
    assert m2 and m2.group(1) == "::my::func", "func_start should capture namespaced proc names"

    class_start = TCL_RULES["class_start"]
    m3 = class_start.search("oo::class create Point {")
    assert m3 and m3.group(1) == "Point"
    m4 = class_start.search("snit::type Widget {")
    assert m4 and m4.group(1) == "Widget"

    assert not class_start.search("proc add {a b} {"), "class_start incorrectly matched a proc"
    assert not func_start.search("oo::class create Point {"), "func_start incorrectly matched a class"


def test_tcl_args_nested_default_value_brace_regression():
    """
    Regression test for a real bug (Rule 11, nested-delimiter): `[^}]*` is a
    flat negated class, can't represent even one level of nesting. Tcl's
    optional-argument-with-default syntax nests braces directly inside the
    arg list (`proc foo {a {b 10}} {...}` -- `a` is required, `b` defaults
    to 10 -- a routine, idiomatic Tcl pattern), confirmed the old pattern
    truncated at the *inner* `}` instead of the true closing one.
    """
    old_pattern = re.compile(r"^[ \t]*proc[ \t\n]+[a-zA-Z0-9_:]+[ \t\n]+\{([^}]*)\}", re.M)
    nested = "proc foo {a {b 10}} {\n    return $a\n}"
    old_m = old_pattern.search(nested)
    assert old_m and old_m.group(0) == "proc foo {a {b 10}", "sanity check: old pattern must truncate"

    args = TCL_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == "proc foo {a {b 10}}", (
        f"nested default-value brace truncated: {m.group(0) if m else None!r}"
    )
    assert args.search("proc bar {x y} {return $x}").group(0) == "proc bar {x y}"


def test_tcl_args_nested_redos_immunity():
    assert_redos_immune(TCL_RULES["args"], "proc foo {" + "{" * 20000, timeout_sec=3.0)
    assert TCL_RULES["args"].search("proc bar {x y} {return $x}")


def test_tcl_globals_env_leading_boundary_regression():
    """
    Regression test for a real bug: `::env` starts with `::` (non-word)
    inside the shared `\\b(...)\\b` group. Real usage (`$::env(HOME)`)
    always precedes it with `$`, also non-word -- `\\b` between two
    non-word characters can never fire, so `::env` never matched at all.
    """
    old_pattern = re.compile(r"\b(?:global|::env)\b|upvar[ \t]+#0")
    realistic = "set path $::env(HOME)"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    globals_ = TCL_RULES["globals"]
    assert globals_.search(realistic), "::env still didn't match"
    assert globals_.search("global x y"), "bare-word global form regressed"
    assert globals_.search("upvar #0 x localX"), "upvar #0 form regressed"


def test_tcl_spec_exposure_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the SPEC
    alternative's unbounded `\\d+` sits directly adjacent to the
    also-unbounded `[^\\]]*`, whose character class fully overlaps digits.
    Same bug shape already found and fixed in embedded_python's and css's
    independent copies of this pattern. Bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`.
    """
    old_pattern = re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I)

    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed -- this exact
    # test failed on CI for this reason): a payload-size doubling should
    # cost ~4x on the quadratic OLD pattern, vs ~2x for linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 16000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = TCL_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + "1" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


def test_tcl_namespace_double_colon_self_delimiting_confirmed_no_bug():
    """
    Symbolic-boundary audit (Rule 9): io/test/ui_framework/telemetry all
    have a `namespace::`-shaped alternative (`vfs::`, `tcltest::`, `ttk::`,
    `logger::`) ending in `::` inside a shared `\\b(...)\\b` group. Verified
    empirically -- unlike the confirmed globals bug above, these all
    self-heal correctly: a Tcl namespace-qualifier is *never* followed by
    whitespace/nothing in real usage, it's always immediately followed by
    more identifier characters (`vfs::mount`, `tcltest::configure`,
    `ttk::button`, `logger::init`), so the trailing `\\b` correctly fires
    against that following word character every time. Documented here as a
    verified non-bug, not silently assumed safe.
    """
    io = TCL_RULES["io"]
    test_ = TCL_RULES["test"]
    ui_framework = TCL_RULES["ui_framework"]
    telemetry = TCL_RULES["telemetry"]

    assert io.search("vfs::mount $path")
    assert test_.search("tcltest::configure -verbose 1")
    assert ui_framework.search("ttk::button .b -text Hi")
    assert telemetry.search("logger::init myapp")


def test_tcl_bitwise_ops_and_closures_do_not_collide():
    """
    Known ambiguity pattern from the issue template (Rust's `|a| a + 1`
    miscounted as bitwise-OR, C++'s `std::cout <<` miscounted as a bitwise
    shift). Verified empirically: Tcl's closure syntax (`apply {{args}
    body}`) uses literal braces, not pipe/angle-bracket tokens, so it
    structurally cannot collide with bitwise_ops' `&`/`|`/`<<`/`>>`/`^`/`~`.
    """
    bitwise_ops = TCL_RULES["bitwise_ops"]
    closures = TCL_RULES["closures"]

    closure_sample = "set fn [apply {{x} {return $x}} 5]"
    assert closures.search(closure_sample)
    assert not bitwise_ops.search(closure_sample)

    bitwise_sample = "set mask [expr {$a & $b}]"
    assert bitwise_ops.search(bitwise_sample)
    assert not closures.search(bitwise_sample)


def test_tcl_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: tcl is `line_exclusive` (Tcl natively uses only
    `#` for line comments, no block comments -- developers sometimes hack
    `if 0 { ... }` but that's not a real comment delimiter) -- no rule
    tracks open/close block-comment state. Confirms a stray unmatched `}`
    doesn't fool any rule into a false structural match.
    """
    branch = TCL_RULES["branch"]
    stray_close = "some text } if {$x == 0} {"
    assert branch.search(stray_close), "branch should still see 'if' regardless of the stray } before it"


def test_tcl_redos_immunity_sweep():
    """
    ReDoS immunity sweep across tcl's remaining unbounded-quantifier rules
    not covered by the dedicated regression tests above.
    """
    assert_redos_immune(TCL_RULES["func_start"], "proc " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["class_start"], "oo::class create " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["state_mutation"], "set " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["ownership"], "# Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["cleanup"], "rename " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["encapsulation"], "proc _" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert TCL_RULES["func_start"].search("proc add {a b} {")
    assert TCL_RULES["class_start"].search("oo::class create Point {")


# ==============================================================================
# TCL: MODE B BODY-ANCHOR REGRESSION (Issue #2763)
# ==============================================================================
# A tcl `proc` has TWO brace groups -- the parameter list and the body -- so the
# shared `_slice_by_braces` fallback, which anchored its brace search at the
# match's START, measured the PARAMETER LIST as the body: every tcl function in
# every scan recorded loc 1 / branch 0 (13/13 in keyword-rosetta/data/tcl,
# 376/376 in language-crucible/data/tcl). The fix anchors at `match.end()`, which
# `func_start` has already advanced past the parameter group, and is GATED TO TCL
# -- see the branch's own comment for the measurements that rule out a blanket
# Mode B change (c 1756/1756 and cpp 1247/1247 matches would move).


def _tcl_slice(code):
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("tcl", LANGUAGE_DEFINITIONS)
    sats, _impact = extractor._slice_by_braces(code, "tcl", TCL_RULES, 0, {})
    return {s["name"]: s for s in sats}


def test_tcl_2763_single_line_proc_body_is_not_the_parameter_list():
    code = "proc probe_globals {env_kit} {\n    global region\n    ::env\n}\n"
    sats = _tcl_slice(code)
    assert "probe_globals" in sats
    assert sats["probe_globals"]["loc"] == 4, "body span must cover the whole proc, not just `{env_kit}`"
    assert code[sats["probe_globals"]["end_idx"] - 1] == "}"


def test_tcl_2763_vertical_proc_body_is_not_the_parameter_list():
    """The "vertical proc shield": `proc`, name and both brace groups split across lines."""
    code = "proc\n  probe_vertical\n  {a b}\n  {\n    set x 1\n    set y 2\n}\n"
    sats = _tcl_slice(code)
    assert "probe_vertical" in sats
    assert sats["probe_vertical"]["loc"] == 7


def test_tcl_2763_proc_nested_in_namespace_eval():
    code = "namespace eval ::probe {\n    proc inner {a} {\n        set x $a\n        return $x\n    }\n}\n"
    sats = _tcl_slice(code)
    assert "inner" in sats
    assert sats["inner"]["loc"] == 4, "the nested proc's own body, not the enclosing namespace block"


def test_tcl_2763_braced_default_value_parameter_list():
    """`proc f {{a 1} {b 2}} {...}` -- the depth-aware parameter shape #1512 added."""
    code = "proc probe_defaults {{a 1} {b 2}} {\n    incr a\n    incr b\n    return $a\n}\n"
    sats = _tcl_slice(code)
    assert "probe_defaults" in sats
    assert sats["probe_defaults"]["loc"] == 5


def test_tcl_2763_non_brace_body_still_records_a_function():
    """A tcl body need not be a brace group at all -- it is just another word.

    `proc name {params} $var` (sqlite/malloc_common.tcl:347) has no brace after
    the parameter list, so the new anchor finds nothing. The fallback keeps the
    old parameter-group span rather than dropping the declaration, so the fix is
    a strict superset of the previous behaviour and the function COUNT never
    moves (crucible: 376 before, 376 after).
    """
    code = "proc probe_varbody {testrc testresult} $O(-test)\nproc probe_real {x} {\n    set y $x\n}\n"
    sats = _tcl_slice(code)
    assert "probe_varbody" in sats, "a variable-bodied proc must not be dropped"
    assert "probe_real" in sats
    assert sats["probe_real"]["loc"] == 3


def test_tcl_2763_url_in_source_does_not_unbalance_the_brace_shield():
    """`//` is not a tcl comment -- shielding from it blanked the rest of the line.

    Exactly perl's #1437 bug one language over. `_build_brace_safe_stream` carried
    the C-family `//[^\\n]*|/\\*.*?\\*/` branch for tcl, so a URL inside real code
    (`{http://} $env(x)] != 0`) lost the `}` after it and threw the depth counter
    off -- measured as loc 515 for a real 37-line proc in
    macports_port_api/portfetch.tcl. Invisible before #2763 because a tcl body was
    never brace-walked at all.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("tcl", LANGUAGE_DEFINITIONS)
    line = "            && [string compare -length 7 {http://} $env($varname)] != 0\n"
    safe = extractor._build_brace_safe_stream(line, "tcl")
    assert safe.count("{") == line.count("{")
    assert safe.count("}") == line.count("}"), "a URL's `//` must not blank the rest of the line"

    code = "proc probe_url {args} {\n" + line + "    set x 1\n}\nproc probe_next {a} {\n    set y 2\n}\n"
    sats = _tcl_slice(code)
    assert sats["probe_url"]["loc"] == 4, "must stop at its own `}`, not run into the next proc"
    assert sats["probe_next"]["loc"] == 3
