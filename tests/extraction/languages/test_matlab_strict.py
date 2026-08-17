"""matlab strict structural-signature coverage.

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

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# MATLAB: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #598, part of epic #518)
# ==============================================================================
MATLAB_RULES = LANGUAGE_DEFINITIONS["matlab"]["rules"]

_MATLAB_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x == 1", "x = 1;"),
    ("args", "function y = foo(x)", "x = 1;"),
    ("structural_boundaries", "classdef Foo", "x = 1;"),
    ("func_start", "function y = foo(x)", "classdef Foo"),
    ("class_start", "classdef Foo", "function y = foo(x)"),
    ("safety", "try", "x = 1;"),
    ("safety_bypasses", "eval('x = 1')", "x = 1;"),
    ("high_risk_execution", "system('ls')", "x = 1;"),
    ("io", "fopen('file.txt')", "x = 1;"),
    ("api", "methods", "methods (Access = private)"),
    ("state_mutation", "x = 5;", "if x == 1"),
    ("dead_code", "% if x == 1", "% just a note"),
    ("doc", "%% SECTION", "% just a note"),
    ("test", "verifyEqual(testCase, x, 5)", "x = 1;"),
    ("concurrency", "parfor i = 1:10", "x = 1;"),
    ("ui_framework", "figure;", "x = 1;"),
    ("closures", "f = @(x) x + 1;", "x = 1;"),
    ("globals", "global x", "x = 1;"),
    ("decorators", "properties (Access = private)", "x = 1;"),
    ("comprehensions", "arrayfun(@(x) x^2, v)", "x = 1;"),
    ("scientific", "svd(A)", "x = 1;"),
    ("reflection_metaprogramming", "feval(@sin, 0)", "x = 1;"),
    ("import", "import mypackage.MyClass", "x = 1;"),
    ("ownership", "% Author: Jane Doe", "% just a note"),
    ("planned_debt", "% TODO: fix this", "% done"),
    ("fragile_debt", "% HACK: workaround", "% clean"),
    ("spec_exposure", "[SPEC-123]", "% just a note"),
    ("ssr_boundaries", "webwindow(url)", "x = 1;"),
    ("events", "notify(obj, 'MyEvent')", "x = 1;"),
    ("pointers", "libpointer('int32Ptr', 5)", "x = 1;"),
    ("memory_alloc", "zeros(3, 3)", "x = 1;"),
    ("telemetry", "logger.info('msg')", "disp('msg')"),
    ("debug_prints", "disp('hello')", "logger.info('msg')"),
    ("explicit_casts", "int8(x)", "x = 1;"),
    ("panics_and_aborts", "error('failed')", "logger.error('failed')"),
    ("thread_sleeps", "pause(5)", "x = 1;"),
    ("bitwise_ops", "bitand(5, 3)", "x = 1;"),
    ("sync_locks", "labBarrier()", "x = 1;"),
    ("immutability_locks", "Constant", "x = 1;"),
    ("cleanup", "fclose(fid)", "x = 1;"),
    ("encapsulation", "Access = private", "Access = public"),
    ("listeners", "addlistener(obj, 'Event', @callback)", "x = 1;"),
    ("test_skip", "assumeTrue(testCase, x)", "x = 1;"),
    ("serialization_parsing", "jsondecode(str)", "x = 1;"),
    ("regex_execution", "regexp(str, 'pat')", "x = 1;"),
    ("time_date_logic", "datetime('now')", "x = 1;"),
    ("ipc_rpc_bridges", "tcpclient('host', 80)", "x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _MATLAB_SIMPLE_CASES)
def test_matlab_signature_positive_and_negative(signature, positive, negative):
    pattern = MATLAB_RULES[signature]
    assert pattern is not None, f"matlab's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"matlab {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"matlab {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_matlab_dependency_capture_extracts_import_path():
    m = MATLAB_RULES["_dependency_capture"].search("import mypackage.MyClass")
    assert m and m.group(1) == "mypackage.MyClass"


def test_matlab_func_start_excludes_control_flow_and_classdef():
    func_start = MATLAB_RULES["func_start"]
    for excluded in ("if (x)", "for i=1:10", "while (x)", "switch (x)", "catch e", "classdef Foo"):
        assert not func_start.search(excluded), f"func_start incorrectly matched {excluded!r}"


def test_matlab_func_start_vertical_output_array_shield():
    """
    MATLAB function declarations put the output array before the name
    (`function [a, b] = foo(x)`), and developers frequently wrap that array
    across multiple physical lines. func_start's documented "vertical
    output array shield" fix upgraded the horizontal-only `[ \\t]*`
    constraints inside the optional output-array matcher to `[ \\t\\n]*` to
    tolerate this.
    """
    func_start = MATLAB_RULES["func_start"]
    for line in (
        "function [a, b] =\nfoo(x)",
        "function [a, b]\n= foo(x)",
        "function\n[a, b] = foo(x)",
        "function [a,\n b] = foo(x)",
        "function [a, b] = foo(x)",
        "function y = foo(x)",
        "function foo(x)",
    ):
        m = func_start.search(line)
        assert m and m.group(1) == "foo", f"func_start failed on {line!r}"


def test_matlab_func_start_comments_and_semicolons():
    """
    func_start's lookahead must tolerate trailing comments (`%`) and
    semicolons (`;`) after the function name when there are no parens.
    """
    func_start = MATLAB_RULES["func_start"]

    for line in (
        "function foo%",
        "function foo % comment",
        "function foo;",
        "function foo ; % comment",
    ):
        m = func_start.search(line)
        assert m and m.group(1) == "foo", f"func_start failed on {line!r}"


def test_matlab_args_vertical_output_array_shield():
    """
    MATLAB function declarations frequently wrap the output array across
    multiple physical lines. `args` must use `[ \\t\\n]` internally to
    safely bridge these gaps without breaking. (Ported from the identical
    fix in `func_start`).
    """
    args = MATLAB_RULES["args"]

    for line in (
        "function [a, b] =\nfoo(x)",
        "function [a, b]\n= foo(x)",
        "function\n[a, b] = foo(x)",
        "function [a,\n b] = foo(x)",
        "function [a, b] = foo(x)",
        "function y = foo(x)",
    ):
        assert args.search(line), f"args failed on {line!r}"

    # Negative cases: shouldn't match if no parameter list is given
    assert not args.search("function foo")
    assert not args.search("function [a] = foo")


def test_matlab_class_start_with_and_without_attributes():
    class_start = MATLAB_RULES["class_start"]
    m = class_start.search("classdef (ConstructOnLoad) MyClass")
    assert m and m.group(1) == "MyClass"

    m2 = class_start.search("classdef MyClass")
    assert m2 and m2.group(1) == "MyClass"


def test_matlab_class_start_newlines_and_comments():
    """
    Ensures class_start handles vertical formatting (`[ \\t\\n]`) and
    trailing comments (`%`) or semicolons (`;`) without failing the lookahead.
    """
    class_start = MATLAB_RULES["class_start"]

    # Vertically wrapped inheritance without `...` (MATLAB allows this in some contexts, or devs try it)
    m1 = class_start.search("classdef \n (Sealed) \n MyClass \n < handle")
    assert m1 and m1.group(1) == "MyClass"

    # No space before comment
    m2 = class_start.search("classdef MyClass% a comment")
    assert m2 and m2.group(1) == "MyClass"

    # No space before semicolon
    m3 = class_start.search("classdef MyClass;")
    assert m3 and m3.group(1) == "MyClass"


def test_matlab_branch_adversarial_boundaries():
    """
    Ensures `branch` keywords require proper boundaries and don't misfire
    on identifiers that contain branch keywords as substrings.
    """
    branch = MATLAB_RULES["branch"]

    # Negative cases
    assert not branch.search("if_var = 1;")
    assert not branch.search("my_if = 1;")
    assert not branch.search("catchME_outside = true;")
    assert not branch.search("try_count = 5;")

    # Positive cases
    assert branch.search("if (x)")
    assert branch.search("catch ME")
    assert branch.search("try")


def test_matlab_structural_boundaries_adversarial():
    """
    Ensures `structural_boundaries` keywords respect word boundaries.
    """
    sb = MATLAB_RULES["structural_boundaries"]

    assert not sb.search("classdef_name = 'foo';")
    assert not sb.search("my_methods = [];")
    assert not sb.search("events_list = {};")
    assert not sb.search("global_var = 1;")

    assert sb.search("events")
    assert sb.search("global x")


def test_matlab_api_leading_boundary_regression():
    """
    Real bug found and fixed: the bare `methods` literal had no trailing
    boundary at all (not even `\\b`), so it matched as a false-positive
    prefix of any identifier merely starting with "methods"
    (`methodsList = getMethods();`).
    """
    old_pattern = re.compile(r"^[ \t]*methods(?:[ \t]*\([ \t]*Access[ \t]*=[ \t]*public[ \t]*\))?", re.M | re.I)
    realistic = "methodsList = getMethods();"
    assert old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    api = MATLAB_RULES["api"]
    assert not api.search(realistic), "methodsList assignment must not be misread as a methods block"
    assert api.search("methods"), "bare methods block (implicit public) must still match"
    assert api.search("methods (Access = public)"), "explicit public methods block must still match"


def test_matlab_api_access_exclusion_semantic_regression():
    """
    Real bug found and fixed (Rule 1, Semantic Intent Over Keyword
    Matching): the Access=public check was an optional *positive* group
    instead of a *negative* exclusion, so it never actually gated
    anything -- `methods (Access = private)` and `methods (Access =
    protected)` both still matched via the bare `methods\\b` alone,
    directly contradicting this rule's own documented purpose ("Methods
    blocks that don't declare private access"). No real MATLAB corpus
    file in language-crucible exercises classdef/methods at all (pure
    legacy script-style repos), so this fix produces zero golden_crucible
    diff -- confirmed via `grep`, not assumed, per the doc's "a zero-diff
    result is not automatically a clean bill of health" rule.
    """
    old_pattern = re.compile(r"^[ \t]*methods\b(?:[ \t]*\([ \t]*Access[ \t]*=[ \t]*public[ \t]*\))?", re.M | re.I)
    for realistic in ("methods (Access = private)", "methods (Access = protected)"):
        assert old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    api = MATLAB_RULES["api"]
    assert not api.search("methods (Access = private)")
    assert not api.search("methods (Access = protected)")
    # multi-attribute lists, private/protected not necessarily first
    assert not api.search("methods (Static, Access = private)")
    assert not api.search("methods (Access = private, Static)")
    # implicit-public default (Rule 1: implicitly-public languages) must still match
    assert api.search("methods")
    assert api.search("methods (Access = public)")


def test_matlab_state_mutation_nested_index_regression():
    """
    Real bug found and fixed (Rule 11, nested-delimiter coverage): the flat
    `[^)]*`/`[^}]*` classes broke on one level of nested indexing, e.g.
    `data(idx(1)) = value;` -- a common, realistic MATLAB pattern (indexing
    an array by another array/function's result). The truncated inner
    match left a stray closing bracket unconsumed, which broke the
    required trailing `=`, so the WHOLE assignment went undetected -- a
    true false negative (unlike a bare boolean-only rule, where truncation
    still finds *a* match).
    """
    old_pattern = re.compile(
        r"^[ \t]*[a-zA-Z_]\w*(?:\([^)]*\)|\{[^}]*\}|\.[a-zA-Z_]\w*){0,5}[ \t]*=[ \t]*[^=]|\b(?:clear|clearvars)\b",
        re.M,
    )
    realistic = "data(idx(1)) = value;"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    state_mutation = MATLAB_RULES["state_mutation"]
    assert state_mutation.search(realistic)
    assert state_mutation.search("cache{lookup(1)} = value;"), "nested brace-indexing form must also work"
    # non-nested forms that already worked must still work
    assert state_mutation.search("x = 5;")
    assert state_mutation.search("data(1) = value;")
    assert state_mutation.search("s.a.b = 5;")


def test_matlab_spec_exposure_redos_regression():
    """
    Real bug found and fixed: adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` immediately followed by `[^\\]]*`,
    which also matches digits) -- the same ReDoS shape already found and
    fixed independently in embedded_python, css, and tcl earlier in this
    epic. Confirmed via scaling sweep (~4x per doubling before the fix,
    ~2x/linear after bounding both quantifiers).
    """
    old_pattern = re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I)
    assert_redos_immune(MATLAB_RULES["spec_exposure"], "[SPEC-1" + "1" * 100000, timeout_sec=3.0)
    # sanity: old pattern really is the vulnerable shape (adjacent \d+ and [^\]]*)
    assert old_pattern.search("[SPEC-123]")
    assert MATLAB_RULES["spec_exposure"].search("[SPEC-123]")


def test_matlab_ipc_rpc_bridges_missing_multiline_flag_regression():
    """
    Real bug found and fixed (epic recurring bug class #6): the shell-
    escape alternative (`^\\s*!`, MATLAB's native `!cmd` shell escape) had
    no `re.M` flag at all, so `^` anchored to true string start only --
    the escape could only ever fire if `!` were the very first character
    of the entire file, never on any later line where a real shell-escape
    command actually appears in practice (MATLAB scripts virtually never
    open with a bare `!` on line 1).
    """
    old_pattern = re.compile(r"\b(system|dos|unix|tcpclient|tcpserver|parpool|parfor)\b|^\s*!")
    realistic = "function foo()\n    x = 1;\n    !ls -la\nend"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    ipc_rpc_bridges = MATLAB_RULES["ipc_rpc_bridges"]
    assert ipc_rpc_bridges.search(realistic)
    assert ipc_rpc_bridges.search("!ls -la"), "shell escape on the very first line must still match"
    assert ipc_rpc_bridges.search("tcpclient('host', 80)")


def test_matlab_panics_and_aborts_logger_error_false_positive_regression():
    """
    Real bug found and fixed (Rule 3, Annotation & Execution Isolation):
    the bare `error` alternative fired on `logger.error(...)`/
    `log.error(...)` -- a custom logging framework's benign structured-
    logging call (already captured by `telemetry`), not MATLAB's built-in
    `error()` function, which actually throws and halts execution. Fixed
    with a negative lookbehind excluding a preceding dot.
    """
    old_pattern = re.compile(r"\b(?:error|throw|rethrow|MException|throwAsCaller)\b")
    realistic = "logger.error('failed');"
    assert old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    panics_and_aborts = MATLAB_RULES["panics_and_aborts"]
    assert not panics_and_aborts.search(realistic)
    assert not panics_and_aborts.search("log.error('failed')")
    # the real builtin error() call must still match
    assert panics_and_aborts.search("error('failed');")
    assert panics_and_aborts.search("throw(MException('id', 'msg'))")
    assert panics_and_aborts.search("rethrow(ME)")
    # telemetry must still independently capture the logging call
    assert MATLAB_RULES["telemetry"].search(realistic)


def test_matlab_bitwise_ops_vs_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in Rust
    `|a| a + 1` and C++ `std::cout <<`). MATLAB's closures use `@(...)`
    syntax and bitwise_ops uses named intrinsic functions (bitand/bitor/
    ...), structurally distinct -- no realistic overlap.
    """
    closures = MATLAB_RULES["closures"]
    bitwise_ops = MATLAB_RULES["bitwise_ops"]

    anon_fn = "f = @(x) x + 1;"
    assert closures.search(anon_fn)
    assert not bitwise_ops.search(anon_fn)

    bit_call = "bitand(5, 3)"
    assert bitwise_ops.search(bit_call)
    assert not closures.search(bit_call)


def test_matlab_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). MATLAB's
    explicit_casts uses intrinsic type-conversion function-call syntax
    (int8/typecast/cast/...) and pointers uses `libpointer`/`calllib`/
    `< handle`, structurally distinct -- no realistic overlap.
    """
    explicit_casts = MATLAB_RULES["explicit_casts"]
    pointers = MATLAB_RULES["pointers"]

    cast_call = "int8(x)"
    assert explicit_casts.search(cast_call)
    assert not pointers.search(cast_call)

    ptr_call = "libpointer('int32Ptr', 5)"
    assert pointers.search(ptr_call)
    assert not explicit_casts.search(ptr_call)


def test_matlab_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` miscounted as a test-framework call). MATLAB's
    `test` signature is the unittest framework's verify*/assert* family,
    structurally distinct from `regex_execution`'s regexp/regexpi/
    regexprep intrinsics -- no realistic overlap.
    """
    test = MATLAB_RULES["test"]
    regex_execution = MATLAB_RULES["regex_execution"]

    test_call = "verifyEqual(testCase, x, 5)"
    assert test.search(test_call)
    assert not regex_execution.search(test_call)

    regex_call = "regexp(str, 'pat')"
    assert regex_execution.search(regex_call)
    assert not test.search(regex_call)


def test_matlab_structural_keyword_dual_classification_sweep():
    """
    Ambiguity sweep finding: a handful of MATLAB structural keywords
    legitimately fire both `structural_boundaries` (bounding scope) and a
    more specific semantic signature -- both true simultaneously,
    intentional double-classifications (the same pattern seen across many
    languages in this epic for class/function/import-style keywords):
    - `classdef Foo` -> structural_boundaries + class_start
    - `methods (Access = public)` -> structural_boundaries + api + decorators
    - `global x` -> structural_boundaries + globals
    """
    structural_boundaries = MATLAB_RULES["structural_boundaries"]

    classdef_line = "classdef Foo"
    assert structural_boundaries.search(classdef_line)
    assert MATLAB_RULES["class_start"].search(classdef_line)

    methods_line = "methods (Access = public)"
    assert structural_boundaries.search(methods_line)
    assert MATLAB_RULES["api"].search(methods_line)
    assert MATLAB_RULES["decorators"].search(methods_line)

    global_line = "global x"
    assert structural_boundaries.search(global_line)
    assert MATLAB_RULES["globals"].search(global_line)


def test_matlab_resource_action_dual_classification_sweep():
    """
    Ambiguity sweep finding: several MATLAB resource/process actions
    legitimately fire two signatures representing different perspectives
    on the same underlying action -- intentional, not false collisions:
    - `try`/`catch` -> branch (decision point) + safety (defensive programming)
    - `clear all` -> high_risk_execution (destructive wipe) + state_mutation
      (workspace mutation) + cleanup (resource release)
    - `fclose(fid)` -> io (file operation) + cleanup (handle release)
    - `system(...)` -> high_risk_execution (OS bypass) + ipc_rpc_bridges
      (inter-process bridge)
    - `load(...)` -> io (disk read) + serialization_parsing (deserializing
      structured data)
    - `parpool`/`parfor` -> concurrency (parallel execution) +
      ipc_rpc_bridges (worker-process bridging)
    """
    assert MATLAB_RULES["branch"].search("try")
    assert MATLAB_RULES["safety"].search("try")

    clear_all = "clear all"
    assert MATLAB_RULES["high_risk_execution"].search(clear_all)
    assert MATLAB_RULES["state_mutation"].search(clear_all)
    assert MATLAB_RULES["cleanup"].search(clear_all)

    fclose_call = "fclose(fid)"
    assert MATLAB_RULES["io"].search(fclose_call)
    assert MATLAB_RULES["cleanup"].search(fclose_call)

    system_call = "system('ls')"
    assert MATLAB_RULES["high_risk_execution"].search(system_call)
    assert MATLAB_RULES["ipc_rpc_bridges"].search(system_call)

    load_call = "load('data.mat')"
    assert MATLAB_RULES["io"].search(load_call)
    assert MATLAB_RULES["serialization_parsing"].search(load_call)

    assert MATLAB_RULES["concurrency"].search("parpool")
    assert MATLAB_RULES["ipc_rpc_bridges"].search("parpool")
    assert MATLAB_RULES["concurrency"].search("parfor i = 1:10")
    assert MATLAB_RULES["ipc_rpc_bridges"].search("parfor i = 1:10")


def test_matlab_api_vs_encapsulation_mutually_exclusive_by_design():
    """
    Following the api Access=private/protected exclusion fix, `api` and
    `encapsulation` are now cleanly complementary on the same Access
    declaration -- a methods block is classified as EITHER public API OR
    encapsulated (private/protected), never both, unlike the other
    intentional overlaps in this rule set.
    """
    assert MATLAB_RULES["api"].search("methods (Access = public)")
    assert not MATLAB_RULES["encapsulation"].search("methods (Access = public)")

    assert not MATLAB_RULES["api"].search("methods (Access = private)")
    assert MATLAB_RULES["encapsulation"].search("Access = private")


def test_matlab_no_block_comment_family_confusion():
    """
    Lexical-family audit: matlab is `line_exclusive` -- it has no native
    multi-line block-comment syntax at the rule level (the real `%{ %}`
    block form is handled by prism.py's family-level delimiter table, not
    by any of these per-language rules). Confirms a stray C-style `/* */`
    sequence doesn't accidentally trigger dead_code or doc.
    """
    stray = "/* not a real matlab comment */"
    assert not MATLAB_RULES["dead_code"].search(stray)
    assert not MATLAB_RULES["doc"].search(stray)


def test_matlab_redos_immunity_sweep():
    """
    ReDoS immunity sweep across matlab's rules with unbounded-looking
    quantifiers, verified via a systematic scaling sweep (n=2000/4000/
    8000/16000/32000) before writing this test -- all rules showed ~2x
    time per doubling (linear) after the spec_exposure fix, not the ~4x
    signature of catastrophic backtracking.
    """
    assert_redos_immune(MATLAB_RULES["func_start"], "function " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["class_start"], "classdef (" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["args"], "function foo(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["state_mutation"], "data" + "(" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["state_mutation"], "data" + "{" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["memory_alloc"], "zeros(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["closures"], "@(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["decorators"], "methods(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["api"], "methods (" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["import"], "import " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["_dependency_capture"], "import " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["doc"], "%%" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(MATLAB_RULES["ownership"], "% Author:" + " " * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert MATLAB_RULES["func_start"].search("function y = foo(x)")
    assert MATLAB_RULES["class_start"].search("classdef Foo")
    assert MATLAB_RULES["state_mutation"].search("data(idx(1)) = value;")
