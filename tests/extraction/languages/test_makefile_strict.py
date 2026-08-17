"""makefile strict structural-signature coverage.

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
# MAKEFILE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #596, part of epic #518)
# ==============================================================================
MAKEFILE_RULES = LANGUAGE_DEFINITIONS["makefile"]["rules"]

_MAKEFILE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "ifeq ($(OS),Windows_NT)", "OS := Windows_NT"),
    ("branch", "else ifeq ($(CC),gcc)", "else:"),
    ("branch", "ifneq (,$(findstring foo,$(bar)))", "endif_flag := 1"),
    ("branch", "ifdef VERBOSE", "ifdef_target:"),
    ("branch", "ifndef V", "ifndef_flag=1"),
    ("branch", "\twhile read line; do \\", "\techo while"),
    ("branch", "\tcase $$var in \\", "\techo case"),
    ("args", "\t@echo $(1)", "\t@echo hello"),
    ("args", "\t@echo ${1}", "\t@echo hello"),
    ("args", "\t$(call my_macro,a,b)", "\t$(call_target)"),
    ("args", "\t${call my_macro,a,b}", "\t${call_target}"),
    ("args", "\t@echo $1", "\t@echo $$1"),
    ("structural_boundaries", "CC := gcc", "\techo hello"),
    ("structural_boundaries", "a+b = 2", "a+b += 2"),
    ("structural_boundaries", "a+ = 2", "a+= 2"),
    ("structural_boundaries", "VAR?=default", "VAR+=append"),
    ("structural_boundaries", "vpath %.c src", "vpath_target:"),
    ("structural_boundaries", "undefine FOO", "undefine_target:"),
    ("func_start", "build: main.o", ".PHONY: build"),
    ("func_start", "g++: main.o", "a=b:"),
    ("func_start", "gtk+-2.0: src", "gtk+-2.0 += src"),
    ("func_start", "a b c: deps", "\techo a b c: deps"),
    ("func_start", "target-1.0%: dep", "target-1.0% = dep"),
    # --- PHASE 2 ---
    ("safety", ".POSIX:", "\techo hi"),
    ("safety_bypasses", "\t-rm -f build/*.o", "\trm -f build/*.o"),
    ("high_risk_execution", "\tsudo rm -rf /var/cache", "\trm file.txt"),
    ("io", "\tcurl -O https://example.com/file.tar.gz", "\techo done"),
    ("api", ".PHONY: build", "deploy: main.o"),
    ("state_mutation", "CFLAGS += -Wall", "CFLAGS := -Wall"),
    ("dead_code", "# clean:", "# just a note"),
    ("doc", "## Build the project", "# just a note"),
    ("test", "\tpytest tests/", "\techo done"),
    # --- PHASE 3 ---
    ("concurrency", "\t$(MAKE) -j4", "\t$(MAKE) build"),
    ("globals", "\techo $(CURDIR)/build", "\techo $(TARGET)/build"),
    ("comprehensions", "$(foreach f,$(SOURCES),$(f).o)", "$(SOURCES)"),
    ("scientific", "\tawk '{print $1}' file.txt", "\techo file.txt"),
    ("reflection_metaprogramming", "$(eval $(call template,foo))", "$(wildcard *.c)"),
    ("import", "include config.mk", "config.mk"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: refactor build", "# done"),
    ("fragile_debt", "# HACK: workaround for broken toolchain", "# clean"),
    ("spec_exposure", "# [SPEC-123] audit tag", "# just a note"),
    ("macros", "define BUILD_RULE", "BUILD_RULE := foo"),
    # --- PHASE 5 ---
    ("telemetry", "$(info Building target)", "$(warning deprecated)"),
    ("debug_prints", "\t@echo Building...", "\ttrue"),
    ("panics_and_aborts", "$(error Missing dependency)", "$(info ok)"),
    ("thread_sleeps", "\tsleep 5", "\tdate"),
    ("sync_locks", ".NOTPARALLEL:", ".PHONY:"),
    ("immutability_locks", "override CFLAGS += -g", "CFLAGS += -g"),
    ("cleanup", "clean:", "build:"),
    ("encapsulation", "unexport SECRET_VAR", "export PUBLIC_VAR"),
    ("listeners", "\tinotifywait -m ./src", "\tls ./src"),
    ("test_skip", "SKIP_TESTS=1", "RUN_TESTS=1"),
    # --- HYBRID ---
    ("serialization_parsing", "\ttar -czf archive.tar.gz build/", "\tls build/"),
    ("regex_execution", "\tgrep -r TODO src/", "\tls -r src/"),
    ("time_date_logic", "\tdate +%Y-%m-%d", "\techo today"),
    ("ipc_rpc_bridges", "\tssh user@host 'ls'", "\techo host"),
]


@pytest.mark.parametrize("signature,positive,negative", _MAKEFILE_SIMPLE_CASES)
def test_makefile_signature_positive_and_negative(signature, positive, negative):
    pattern = MAKEFILE_RULES[signature]
    assert pattern is not None, f"makefile's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"makefile {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"makefile {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_makefile_dependency_capture_extracts_include_path():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact included
    path rather than just detecting presence. Covers all three real forms:
    plain `include`, error-tolerant `-include`, and the GNU-specific
    `sinclude` alias (functionally identical to `-include`).
    """
    pattern = MAKEFILE_RULES["_dependency_capture"]
    m = pattern.search("include config.mk")
    assert m and m.group(1) == "config.mk"
    m2 = pattern.search("-include .depend")
    assert m2 and m2.group(1) == ".depend"
    m3 = pattern.search("sinclude foo.mk")
    assert m3 and m3.group(1) == "foo.mk"
    m4 = pattern.search("  include ../common.mk")
    assert m4 and m4.group(1) == "../common.mk"


def test_makefile_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): makefile's lexical_family is
    `line_exclusive` -- Make natively uses `#` exclusively for line-level
    comments, with no block-comment delimiter to wire up in parallel. Unlike
    a `standard_block` language (which must cover both `//` and `/* */`),
    there is no second comment style for `dead_code` to silently miss. This
    test documents that the check was performed, not skipped.
    """
    pattern = MAKEFILE_RULES["dead_code"]
    assert pattern.search("# clean:")
    assert pattern.search("    # ifeq ($(DEBUG),1)")
    assert pattern.search("# CFLAGS := -O2")


def test_makefile_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because makefile is `line_exclusive` (no block
    comment delimiters at all), none of its structural regexes track
    open/close block-comment state -- every keyword-presence rule (e.g.
    `branch`'s `ifeq`/`endif`) matches via flat line-anchored scanning, not
    depth-tracking. The one native multi-line construct Make actually has is
    `define ... endef` (a macro/template body, not a comment), and since the
    engine performs no special-casing of it either, a stray `endif` or
    target-shaped line inside a `define` body is scanned exactly the same as
    anywhere else in the file -- there is no block-state tracker for it to
    fool.
    """
    branch = MAKEFILE_RULES["branch"]
    define_body_with_endif = "define TEMPLATE\nifeq ($(1),foo)\nbar:\nendif\nendef\n"
    assert branch.search(define_body_with_endif), (
        "branch should still see 'ifeq'/'endif' inside a define body -- there is no "
        "block-state tracker for it to be fooled by in the first place"
    )


def test_makefile_func_start_special_targets_no_false_positive_regression():
    """
    Regression test for a real bug: the negative-lookahead exclusion list
    that keeps GNU Make's built-in special targets (`.PHONY`, `.SECONDARY`,
    etc.) from being hallucinated as real func_start definitions had
    `.PRECIOUS` and `.SECONDARY` each listed *twice* (dead redundancy) while
    missing three legitimate special targets: `.ONESHELL` (single-shell
    recipes, a very common modern idiom), `.NOTINTERMEDIATE`, and
    `.LOW_RESOLUTION_TIME` -- both added in GNU Make 4.4, the exact
    `target_version` this language section targets per its `_meta`.

    Confirmed empirically against the OLD pattern: `.ONESHELL:`,
    `.NOTINTERMEDIATE:`, and `.LOW_RESOLUTION_TIME:` all matched func_start
    (capturing e.g. `.ONESHELL` as if it were a real target/function name),
    exactly the false-positive shape already documented for C++'s macro
    spiral. The new pattern excludes all three (with the duplicate
    PRECIOUS/SECONDARY entries collapsed) while still correctly matching a
    real target.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?!\.(?:PHONY|POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE|NOTPARALLEL|WAIT|SILENT|"
        r"EXPORT_ALL_VARIABLES|IGNORE|SUFFIXES|DEFAULT|PRECIOUS|INTERMEDIATE|SECONDARY|SECONDEXPANSION)\b)"
        r"([a-zA-Z0-9_./%-]+)(?=[ \t]*::?)",
        re.M,
    )
    assert old_pattern.search(".ONESHELL:"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(".NOTINTERMEDIATE:"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(".LOW_RESOLUTION_TIME:"), "sanity check: bug must reproduce against the old pattern"

    pattern = MAKEFILE_RULES["func_start"]
    assert pattern.pattern.count("PRECIOUS") == 1, "duplicate .PRECIOUS exclusion should have been collapsed"
    assert pattern.pattern.count("SECONDARY") == 1, "duplicate .SECONDARY exclusion should have been collapsed"
    assert not pattern.search(".ONESHELL:"), ".ONESHELL special target incorrectly hallucinated as a func_start"
    assert not pattern.search(".NOTINTERMEDIATE:"), ".NOTINTERMEDIATE special target incorrectly hallucinated"
    assert not pattern.search(".LOW_RESOLUTION_TIME:"), ".LOW_RESOLUTION_TIME special target incorrectly hallucinated"
    assert not pattern.search(".PHONY:"), "existing .PHONY exclusion regressed"
    assert not pattern.search(".PRECIOUS:"), "existing .PRECIOUS exclusion regressed"
    assert not pattern.search(".SECONDARY:"), "existing .SECONDARY exclusion regressed"

    m = pattern.search("build: main.o")
    assert m and m.group(1) == "build", "real target definition regressed"


def test_makefile_safety_bypasses_dash_whitespace_regression():
    """
    Regression test for a real bug, confirmed against the real `make`
    binary (GNU Make 4.3): the ignore-errors recipe prefix `-` was only
    matched when the command immediately followed it with no whitespace
    (`^\\t[ \\t]*-[a-zA-Z0-9_./$]`). But GNU Make strips the modifier
    character AND any whitespace after it before invoking the shell -- both
    `\\t-rm -f x` and `\\t- rm -f x` are valid, equally common ignore-errors
    forms (verified: running both through real `make` produces identical
    output, `rm -f x` with no leading `-` echoed either way). The
    dash-then-space form silently never matched under the old pattern.
    """
    old_pattern = re.compile(r"^\t[ \t]*-[a-zA-Z0-9_./$]|\|\|[ \t]*(?:true|exit[ \t]+0)\b", re.M)
    assert not old_pattern.search("\t- rm -f build/*.o"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search("\t-rm -f build/*.o"), "sanity check: no-space form already worked"

    pattern = MAKEFILE_RULES["safety_bypasses"]
    assert pattern.search("\t-rm -f build/*.o"), "no-space dash form regressed"
    assert pattern.search("\t- rm -f build/*.o"), "dash-then-space form still didn't match"
    assert pattern.search("\t-   rm -f build/*.o"), "dash-then-multiple-spaces form still didn't match"
    assert not pattern.search("\trm -f build/*.o"), "plain recipe with no ignore-errors prefix incorrectly matched"


def test_makefile_debug_prints_semicolon_recipe_regression():
    """
    Regression test for a real bug: `debug_prints` was anchored only to true
    line start (`^[ \\t]*@?(?:echo|printf)`), missing the very common
    one-liner recipe form where a short recipe is written on the same
    physical line as its target, separated by `;` (e.g.
    `check: ; @echo "ok"`). The `echo`/`printf` call there was silently
    never detected.
    """
    old_pattern = re.compile(r"^[ \t]*@?(?:echo|printf)[ \t]+|\$\(warning[ \t]+[^)\n]*\)", re.M)
    assert not old_pattern.search("check: ; @echo ok"), "sanity check: bug must reproduce against the old pattern"

    pattern = MAKEFILE_RULES["debug_prints"]
    assert pattern.search("check: ; @echo ok"), "semicolon one-liner recipe form still didn't match"
    assert pattern.search("foo: bar; echo hi"), "semicolon one-liner recipe form (no @) still didn't match"
    assert pattern.search("\techo hi"), "normal tab-indented echo form regressed"
    assert pattern.search("\t@printf 'building\\n'"), "normal tab-indented printf form regressed"
    assert not pattern.search("foo: bar; ls"), "one-liner recipe with no echo/printf incorrectly matched"


def test_makefile_nested_paren_capture_regression():
    """
    Nested-delimiter regression (Rule 11): `telemetry`'s `$(info ...)`,
    `debug_prints`' `$(warning ...)`, and `panics_and_aborts`' `$(error
    ...)` all used a flat `[^)\\n]*\\)` delimiter matcher, which cannot
    represent one level of nesting. A realistic nested call inside the
    message -- e.g. `$(error Missing dependency: $(call check_dep,foo))`,
    a common pattern for building a descriptive error/warning/info message
    from another macro -- truncated the match at the first (inner) `)`
    instead of capturing the full outer call. Upgraded to the
    one-level-nesting form from the project's Rule 11 playbook.
    """
    old_error = re.compile(r"\$\(error[ \t]+[^)\n]*\)")
    old_warning = re.compile(r"\$\(warning[ \t]+[^)\n]*\)")
    old_info = re.compile(r"\$\(info[ \t]+[^)\n]*\)")

    nested_error = "$(error Missing dependency: $(call check_dep,foo))"
    old_m = old_error.search(nested_error)
    assert old_m and old_m.group() == "$(error Missing dependency: $(call check_dep,foo)", (
        "sanity check: old pattern must reproduce the truncation bug"
    )

    error = MAKEFILE_RULES["panics_and_aborts"]
    m = error.search(nested_error)
    assert m and m.group() == nested_error, f"nested $(error ...) call truncated: {m.group() if m else None!r}"

    nested_warning = "$(warning deprecated: $(call check_dep,foo))"
    old_w = old_warning.search(nested_warning)
    assert old_w and old_w.group() != nested_warning, "sanity check: old pattern must reproduce the truncation bug"
    warning = MAKEFILE_RULES["debug_prints"]
    m2 = warning.search(nested_warning)
    assert m2 and m2.group() == nested_warning, f"nested $(warning ...) call truncated: {m2.group() if m2 else None!r}"

    nested_info = "$(info Building $(call get_target,foo))"
    old_i = old_info.search(nested_info)
    assert old_i and old_i.group() != nested_info, "sanity check: old pattern must reproduce the truncation bug"
    info = MAKEFILE_RULES["telemetry"]
    m3 = info.search(nested_info)
    assert m3 and m3.group() == nested_info, f"nested $(info ...) call truncated: {m3.group() if m3 else None!r}"

    # Non-nested forms must still match cleanly.
    assert error.search("$(error simple message)")
    assert warning.search("$(warning simple message)")
    assert info.search("$(info simple message)")


def test_makefile_nested_paren_redos_immunity():
    """
    ReDoS immunity for the Rule 11 upgrade above: the one-level-nesting
    form `(?:[^()\\n]|\\([^()\\n]*\\))*\\)` must stay linear on an unclosed
    run of nested-looking `(` characters (the two alternatives never match
    overlapping text). Confirmed empirically via direct scaling
    measurement before writing this test (n=2000/4000/8000/16000/32000 on
    `"$(error " + "(" * n`: ~0.00008s/0.00015s/0.00031s/0.00063s/0.00125s,
    a clean ~2x per doubling -- linear, not the ~4x/doubling signature of
    real O(n^2) backtracking).
    """
    error = MAKEFILE_RULES["panics_and_aborts"]
    warning = MAKEFILE_RULES["debug_prints"]
    info = MAKEFILE_RULES["telemetry"]
    assert_redos_immune(error, "$(error " + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(warning, "$(warning " + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(info, "$(info " + "(" * 20000, timeout_sec=3.0)
    assert error.search("$(error simple message)")


def test_makefile_hybrid_sensors_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS -- the most severe
    finding in this sweep. All four Hybrid Domain Sensor rules
    (`serialization_parsing`, `regex_execution`, `time_date_logic`,
    `ipc_rpc_bridges`) anchored their line-start alternative with `^\\s*`
    instead of the engine's mandated `^[ \\t]*` (this is the exact
    anti-pattern Rule 5 calls out by name: "NEVER use ^\\s*"). Under
    `re.M`, `\\s` matches `\\n`, so `^\\s*` can cross line boundaries --
    on a long run of blank lines with no keyword anywhere, every one of the
    N blank-line `^` positions re-scans forward through the entire rest of
    the run before failing, producing genuine O(n^2) behavior.

    Confirmed via direct scaling measurement against the OLD pattern on
    `"\\n" * n` (no keyword anywhere) before writing this test:
    n=500/1000/2000/4000/8000 -> 0.0034s/0.0136s/0.0520s/0.2089s/0.8229s
    for `serialization_parsing` -- a clean ~4x increase per doubling, the
    textbook signature of real quadratic backtracking (the other three
    rules showed the identical shape). Swapping to `^[ \\t]*` (which cannot
    cross a newline, bounding each `^` attempt to its own line) resolves it:
    the same n=500..32000 sweep against the new pattern comes in at
    0.00003s..0.00151s, a clean ~2x per doubling.
    """
    old_serialization_parsing = re.compile(r"(?m)^\s*(?:@|-)?(?:tar|unzip|gunzip|jq|sed|awk)\b")
    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed -- confirmed by
    # a real CI failure on an unrelated PR's smoke-test run hitting the
    # analogous absolute-threshold check in tcl's spec_exposure test): a
    # payload-size doubling should cost ~4x on the quadratic OLD pattern,
    # vs ~2x for linear.
    small_duration = _best_of_timing(old_serialization_parsing, "\n" * 1000)
    large_duration = _best_of_timing(old_serialization_parsing, "\n" * 2000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old ^\\s* pattern was expected to show quadratic (~4x) scaling on a "
        f"payload doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    for key in (
        "serialization_parsing",
        "regex_execution",
        "time_date_logic",
        "ipc_rpc_bridges",
    ):
        pattern = MAKEFILE_RULES[key]
        assert_redos_immune(pattern, "\n" * 200000, timeout_sec=3.0)

    assert MAKEFILE_RULES["serialization_parsing"].search("\ttar -czf archive.tar.gz build/")
    assert MAKEFILE_RULES["regex_execution"].search("\tgrep -r TODO src/")
    assert MAKEFILE_RULES["time_date_logic"].search("\tdate +%Y-%m-%d")
    assert MAKEFILE_RULES["ipc_rpc_bridges"].search("\tssh user@host 'ls'")


def test_makefile_io_and_dead_code_redos_immunity():
    """
    ReDoS immunity for `io`'s trailing `>>?[ \\t]*[^ \\t\\n/]+` (a single
    unbounded negated class stopping at whitespace/newline/slash) and
    `dead_code`'s target/assignment alternatives (each a single unbounded
    `[a-zA-Z0-9_./%-]+`/`[a-zA-Z0-9_.-]+` bounded by `\\n` via `re.M`'s `^`
    anchor). Neither has an adjacent second quantifier to backtrack
    against, so both should stay linear even on a long run of matching
    characters with no terminator.
    """
    io = MAKEFILE_RULES["io"]
    assert_redos_immune(io, ">" + "a" * 50000, timeout_sec=3.0)
    assert io.search(">output.log")

    dead_code = MAKEFILE_RULES["dead_code"]
    assert_redos_immune(dead_code, "#" + "a" * 50000, timeout_sec=3.0)
    assert dead_code.search("# clean:")


def test_makefile_cleanup_flag_pattern_redos_immunity():
    """
    ReDoS immunity for `cleanup`'s `\\brm[ \\t]+-[a-zA-Z]*f[a-zA-Z]*\\b` --
    two unbounded character classes flanking a single required literal `f`
    is the classic shape to check for catastrophic backtracking (each
    failed attempt to find `f` can in principle re-partition the consumed
    characters between the two classes). Confirmed linear via direct
    scaling measurement before writing this test on `"rm -" + "a" * n`
    (no `f` present anywhere, forcing the full backtrack range):
    n=2000/4000/8000/16000/32000 -> a clean ~2x per doubling, because only
    one `rm -` occurrence exists in the payload for the engine to anchor
    on and the two classes cannot overlap the same text.
    """
    cleanup = MAKEFILE_RULES["cleanup"]
    assert_redos_immune(cleanup, "rm -" + "a" * 50000, timeout_sec=3.0)
    assert cleanup.search("rm -rf build/")
    assert cleanup.search("clean:")


def test_makefile_macros_and_locks_redos_immunity():
    """
    ReDoS immunity sweep for the remaining single-unbounded-class rules
    anchored by a fixed keyword prefix: `macros` (`define NAME`),
    `encapsulation` (`unexport NAME`), and `immutability_locks`
    (`override NAME`). Each has exactly one quantified character class with
    no adjacent quantifier to backtrack against, so a long run of
    name-shaped characters with no terminator should resolve linearly.
    """
    macros = MAKEFILE_RULES["macros"]
    assert_redos_immune(macros, "define " + "a" * 50000, timeout_sec=3.0)
    assert macros.search("define BUILD_RULE")

    encapsulation = MAKEFILE_RULES["encapsulation"]
    assert_redos_immune(encapsulation, "unexport " + "a" * 50000, timeout_sec=3.0)
    assert encapsulation.search("unexport SECRET_VAR")

    immutability_locks = MAKEFILE_RULES["immutability_locks"]
    assert_redos_immune(immutability_locks, "override " + "a" * 50000, timeout_sec=3.0)
    assert immutability_locks.search("override CFLAGS")


def test_makefile_structural_boundaries_and_state_mutation_no_collision():
    """
    Known ambiguity pattern from the issue template: `structural_boundaries`
    (plain assignment: `:=`, `=`, `?=`, `::=`) and `state_mutation`
    (flux assignment: `+=`, `!=`) are explicitly documented as mutually
    exclusive -- `structural_boundaries`' operator alternative has a
    negative lookahead `(?![ \\t]*=)` specifically to keep `+=`/`!=`/`==`
    out, and neither pattern's keyword form (`vpath`/`undefine`) overlaps
    the other. Confirmed empirically across every real assignment operator
    shape: no line satisfies both signatures, and no legitimate operator
    form is missed by either.
    """
    structural_boundaries = MAKEFILE_RULES["structural_boundaries"]
    state_mutation = MAKEFILE_RULES["state_mutation"]

    for line in ("FOO := bar", "FOO ::= bar", "FOO = bar", "FOO ?= bar"):
        assert structural_boundaries.search(line), f"{line!r} should satisfy structural_boundaries"
        assert not state_mutation.search(line), f"{line!r} incorrectly satisfied state_mutation"

    for line in ("FOO += bar", "FOO != bar"):
        assert state_mutation.search(line), f"{line!r} should satisfy state_mutation"
        assert not structural_boundaries.search(line), f"{line!r} incorrectly satisfied structural_boundaries"


def test_makefile_api_and_cleanup_ambiguity_sweep_clean_target():
    """
    Ambiguity sweep: `api`'s named-target alternative
    (`(?:all|install|build|clean|test|run)[ \\t]*::?`) and `cleanup`'s
    `(?:dist)?clean[ \\t]*::?` both fire on a `clean:` target line.
    Confirmed genuine, intentional double-classification, not a bug: a
    `clean:` target is simultaneously part of the project's conventional
    public build-lifecycle surface (api) AND a resource-teardown routine
    (cleanup) -- both are correct. Also confirmed this is NOT accidentally
    exclusive: `distclean:` (a `cleanup`-only convention, never listed in
    api's named-target alternative) correctly fires cleanup alone, proving
    the overlap on `clean:` is deliberate rather than the two rules always
    moving in lockstep.
    """
    api = MAKEFILE_RULES["api"]
    cleanup = MAKEFILE_RULES["cleanup"]

    assert api.search("clean:")
    assert cleanup.search("clean:")

    assert cleanup.search("distclean:")
    assert not api.search("distclean:"), "distclean should not be part of api's named-target surface"


def test_makefile_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line macro
    construct hallucinating a function match, as seen with C++'s
    `#define` spiral): makefile's `macros` maps to `define NAME` template
    openers, which never produce the `name:`/`name::` colon shape
    `func_start` requires, so a `define` line never satisfies func_start.
    Also verified the reverse direction empirically: a realistic templated
    target line one might expect INSIDE a `define...endef` body (e.g.
    `$(1): $(2)`) does not accidentally satisfy func_start either, since
    `$` is not part of func_start's captured-name character class -- the
    engine has no special-case for `define` bodies (per the line_exclusive
    family's no-block-tracking behavior), it simply never happens to match
    this particular templated-target shape.
    """
    func_start = MAKEFILE_RULES["func_start"]
    macros = MAKEFILE_RULES["macros"]

    define_line = "define BUILD_TEMPLATE"
    assert macros.search(define_line)
    assert not func_start.search(define_line)

    target_line = "build: main.o"
    assert func_start.search(target_line)
    assert not macros.search(target_line)

    templated_target = "$(1): $(2)"
    assert not func_start.search(templated_target), (
        "templated target inside a define body should not satisfy func_start "
        "('$' is outside func_start's name character class)"
    )


def test_makefile_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript, or a
    collision with the shell `test`/`[ ... ]` builtin): verified
    empirically rather than assumed. Makefile's `test` signature is scoped
    to specific external test-runner invocations (`npm test`, `pytest`,
    `go test`, `cargo test`, `make test`, etc.) -- it does NOT include the
    bare shell `test` builtin or `[ ... ]` construct at all, so it
    structurally cannot collide with `regex_execution`'s
    `grep`/`egrep`/`sed`/`$(filter ...)` forms, nor with a recipe using
    `test -f foo` for a file-existence guard.
    """
    test_ = MAKEFILE_RULES["test"]
    regex_execution = MAKEFILE_RULES["regex_execution"]

    grep_line = "\tgrep -r TODO src/"
    assert regex_execution.search(grep_line)
    assert not test_.search(grep_line)

    make_test_line = "\tmake test"
    assert test_.search(make_test_line)
    assert not regex_execution.search(make_test_line)

    shell_test_builtin = "\ttest -f config.mk && echo present"
    assert not test_.search(shell_test_builtin), (
        "shell 'test' builtin should not satisfy makefile's test-framework signature"
    )
    assert not regex_execution.search(shell_test_builtin)
