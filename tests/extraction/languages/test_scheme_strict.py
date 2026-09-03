"""scheme strict structural-signature coverage.

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
# SCHEME: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #609, part of epic #518)
# ==============================================================================
# NOTE: scheme's #| ... |# nested block comments are NOT actually stripped as
# a whole block by the real pipeline today -- `line_exclusive` (the family
# scheme is tagged with) is a stateless, per-line stripper with no concept of
# tracking an "inside an unclosed block" state across lines, despite the
# family's shared delimiter table listing `#|`/`|#` as tokens. Confirmed via
# direct Prism.split_streams() execution and filed separately as #770 (same
# root-cause theme as #386/#691/#694/#697/#733 -- "prism.py doesn't correctly
# honor per-language/per-family delimiter config"). These tests exercise the
# rules dict's regexes directly against realistic snippets, matching how the
# real pipeline actually applies them today, not an idealized nested-block
# stripping that doesn't exist yet.
SCHEME_RULES = LANGUAGE_DEFINITIONS["scheme"]["rules"]

_SCHEME_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "(if (> x 0) 'positive 'negative)", "(+ x 1)"),
    ("args", "(define (foo x y) (+ x y))", "(+ x 1)"),
    ("structural_boundaries", "(let ((x 1)) x)", "(+ x 1)"),
    ("func_start", "(define (foo x) x)", "(+ x 1)"),
    ("class_start", "(define-record-type point (make-point x y) point?)", "(define (foo x) x)"),
    ("safety", "(guard (e (#t (display e))) (risky))", "(+ x 1)"),
    ("safety_bypasses", "(set-car! pair 5)", "(+ x 1)"),
    ("high_risk_execution", "(eval expr env)", "(+ x 1)"),
    ("io", '(display "hello")', "(+ x 1)"),
    ("api", "(export foo)", "(+ x 1)"),
    ("state_mutation", "(set! x 5)", "(+ x 1)"),
    ("dead_code", "; (define old-foo (lambda (x) x))", "; just a note"),
    ("doc", ";;; module docs", "; just a note"),
    ("test", "(test-assert (= 1 1))", "(+ x 1)"),
    ("concurrency", "(make-thread thunk)", "(+ x 1)"),
    ("closures", "(lambda (x) (+ x 1))", "(+ x 1)"),
    ("globals", "(define counter 0)", "(define (foo x) x)"),
    ("comprehensions", "(map foo lst)", "(+ x 1)"),
    ("scientific", "(sqrt 4)", "(+ x 1)"),
    ("reflection_metaprogramming", "(define-syntax my-macro (syntax-rules () ((_ x) x)))", "(+ x 1)"),
    ("import", "(import (scheme base))", "(+ x 1)"),
    ("_dependency_capture", "(import (scheme base))", "(+ x 1)"),
    ("ownership", "; Author: Jane Doe", "; just a note"),
    ("planned_debt", "; TODO: fix this", "; done"),
    ("fragile_debt", "; HACK: workaround", "; clean"),
    ("spec_exposure", "[SPEC-123]", "; just a note"),
    ("events", "(add-hook! my-hook proc)", "(+ x 1)"),
    ("macros", "(define-syntax my-macro (syntax-rules () ((_ x) x)))", "(+ x 1)"),
    ("memory_alloc", "(make-vector 10)", "(+ x 1)"),
    ("telemetry", '(log-info "msg")', '(display "msg")'),
    ("debug_prints", '(display "hello")', '(log-info "msg")'),
    ("explicit_casts", "(number->string 5)", "(+ x 1)"),
    ("panics_and_aborts", '(error "failed")', "(+ x 1)"),
    ("thread_sleeps", "(sleep 5)", "(+ x 1)"),
    ("bitwise_ops", "(bitwise-and a b)", "(+ x 1)"),
    ("sync_locks", "(mutex-lock! m)", "(+ x 1)"),
    ("immutability_locks", "(quote (1 2 3))", "(+ x 1)"),
    ("cleanup", "(close-input-port port)", "(+ x 1)"),
    ("encapsulation", "(define-private helper (lambda (x) x))", "(define (foo x) x)"),
    ("listeners", "(add-hook! my-hook proc)", "(+ x 1)"),
    ("test_skip", '(test-skip "broken test")', "(+ x 1)"),
]


@pytest.mark.parametrize("signature,positive,negative", _SCHEME_SIMPLE_CASES)
def test_scheme_signature_positive_and_negative(signature, positive, negative):
    pattern = SCHEME_RULES[signature]
    assert pattern is not None, f"scheme's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"scheme {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"scheme {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_scheme_func_start_arrow_convention_identifier_regression():
    """
    Real bug found and fixed: the identifier capture class
    `[a-zA-Z0-9_!?-]+` excluded `> < = * + / . ~ $ % ^ &`, but real Scheme
    identifiers are extremely permissive (R7RS special-initial/special-
    subsequent characters), and the "X->Y" type-conversion naming
    convention (`list->vector`, `string->number`, ...) is idiomatic in the
    standard library itself -- these exact procedures are this language's
    own `explicit_casts` positive cases. The truncated capture broke the
    entire trailing lookahead, so func_start silently failed to match ANY
    such definition at all, not just a partial-name capture.
    """
    old_pattern = re.compile(
        r"^[ \t\n]*\([ \t\n]*define[ \t\n]+\([ \t\n]*([a-zA-Z0-9_!?-]+)(?=[ \t\n)\]\r])",
        re.M,
    )
    for realistic in (
        "(define (list->vector x) x)",
        "(define (string->number s) s)",
        "(define (1+ x) (+ x 1))",
        "(define (foo* x) x)",
    ):
        assert not old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    func_start = SCHEME_RULES["func_start"]
    m1 = func_start.search("(define (list->vector x) x)")
    assert m1 and m1.group(1) == "list->vector"
    m2 = func_start.search("(define (string->number s) s)")
    assert m2 and m2.group(1) == "string->number"
    m3 = func_start.search("(define (1+ x) (+ x 1))")
    assert m3 and m3.group(1) == "1+"
    m4 = func_start.search("(define (foo* x) x)")
    assert m4 and m4.group(1) == "foo*"
    # the already-working plain form must still work
    m5 = func_start.search("(define (foo x) x)")
    assert m5 and m5.group(1) == "foo"


def test_scheme_class_start_angle_bracket_convention_regression():
    """
    Real bug found and fixed: same identifier-capture defect as func_start
    -- missed the extremely common `<TypeName>` angle-bracket naming
    convention for SRFI-9/R6RS record types (e.g. `<point>`).
    """
    old_pattern = re.compile(
        r"^[ \t]*\([ \t]*define-record-type\s+([a-zA-Z0-9_!?-]+)(?=[ \t)\]\n\r])",
        re.M,
    )
    realistic = "(define-record-type <point> (make-point x y) point?)"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    class_start = SCHEME_RULES["class_start"]
    m = class_start.search(realistic)
    assert m and m.group(1) == "<point>"
    m2 = class_start.search("(define-record-type point (make-point x y) point?)")
    assert m2 and m2.group(1) == "point"


def test_scheme_globals_arrow_convention_identifier_regression():
    """
    Real bug found and fixed: same identifier-capture defect as func_start/
    class_start -- a top-level binding using the "X->Y" convention (e.g.
    `default->value`) failed to match at all.
    """
    old_pattern = re.compile(r"^[ \t]*\([ \t]*define\s+[a-zA-Z0-9_!?-]+\s+[^(\s]", re.M)
    realistic = "(define default->value 5)"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    globals_rule = SCHEME_RULES["globals"]
    assert globals_rule.search(realistic)
    assert globals_rule.search("(define counter 0)")
    assert not globals_rule.search("(define (foo x) x)"), "function definitions must not count as globals"


def test_scheme_spec_exposure_redos_regression():
    """
    Real bug found and fixed: adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` immediately followed by `[^\\]]*`,
    which also matches digits) -- the same ReDoS shape already found and
    fixed independently in embedded_python, css, tcl, and matlab earlier
    in this epic (the 5th language now). Confirmed via scaling sweep
    (~4x per doubling before the fix, ~linear after bounding both
    quantifiers).
    """
    assert_redos_immune(SCHEME_RULES["spec_exposure"], "[SPEC-1" + "1" * 100000, timeout_sec=3.0)
    assert SCHEME_RULES["spec_exposure"].search("[SPEC-123]")


def test_scheme_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). scheme's
    func_start requires the `define` keyword with an inner-paren function
    signature, structurally distinct from macros' `define-syntax`/
    `define-macro`/`syntax-rules`/`syntax-case` keywords -- no realistic
    overlap.
    """
    func_start = SCHEME_RULES["func_start"]
    macros = SCHEME_RULES["macros"]

    macro_def = "(define-syntax my-macro (syntax-rules () ((_ x) x)))"
    assert macros.search(macro_def)
    assert not func_start.search(macro_def)

    fn_def = "(define (foo x) x)"
    assert func_start.search(fn_def)
    assert not macros.search(fn_def)


def test_scheme_bitwise_ops_vs_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in Rust
    `|a| a + 1` and C++ `std::cout <<`). scheme's closures use the
    `lambda` keyword and bitwise_ops uses named intrinsic procedures
    (bitwise-and/bitwise-ior/...), structurally distinct -- no realistic
    overlap.
    """
    closures = SCHEME_RULES["closures"]
    bitwise_ops = SCHEME_RULES["bitwise_ops"]

    lambda_expr = "(lambda (x) (+ x 1))"
    assert closures.search(lambda_expr)
    assert not bitwise_ops.search(lambda_expr)

    bit_call = "(bitwise-and a b)"
    assert bitwise_ops.search(bit_call)
    assert not closures.search(bit_call)


def test_scheme_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several scheme constructs legitimately fire
    two signatures representing different perspectives on the same
    underlying action -- intentional, not false collisions:
    - `mutex-lock!` -> concurrency (parallel-execution primitive) + sync_locks
      (explicit race-condition coordination)
    - `display`/`write`/`format`/`newline` -> io (output-port interaction) +
      debug_prints (ad-hoc console output)
    - `add-hook!` -> events (hook/pub-sub paradigm) + listeners (registering
      a broadcast listener)
    - `exit` -> high_risk_execution (process-killing) + panics_and_aborts
      (execution-interrupt)
    - `define-syntax`/`define-macro`/`syntax-rules`/`syntax-case` -> macros
      (compile-time code generation) + reflection_metaprogramming (Scheme's
      macro system IS its metaprogramming system, unlike languages with
      separate concepts) -- macros' full keyword set is a subset of
      reflection_metaprogramming's.
    """
    assert SCHEME_RULES["concurrency"].search("(mutex-lock! m)")
    assert SCHEME_RULES["sync_locks"].search("(mutex-lock! m)")

    display_call = '(display "hi")'
    assert SCHEME_RULES["io"].search(display_call)
    assert SCHEME_RULES["debug_prints"].search(display_call)

    hook_call = "(add-hook! my-hook proc)"
    assert SCHEME_RULES["events"].search(hook_call)
    assert SCHEME_RULES["listeners"].search(hook_call)

    assert SCHEME_RULES["high_risk_execution"].search("(exit)")
    assert SCHEME_RULES["panics_and_aborts"].search("(exit)")

    macro_def = "(define-syntax foo bar)"
    assert SCHEME_RULES["macros"].search(macro_def)
    assert SCHEME_RULES["reflection_metaprogramming"].search(macro_def)


def test_scheme_dead_code_requires_comment_prefix_not_just_keyword_presence():
    """
    Structurally-forced non-collision (mirrors the abap/fortran/m4 cases):
    `dead_code` requires a leading `;` comment marker before the
    commented-out keyword, so live, uncommented code containing the same
    keywords (`define`/`let`/`if`/`cond`/`lambda`) never double-counts as
    dead_code -- the comment-prefix anchor and func_start/branch/closures'
    own anchors are naturally mutually exclusive on the same text.
    """
    dead_code = SCHEME_RULES["dead_code"]
    live = "(define (foo x) x)"
    commented = "; (define (foo x) x)"
    assert not dead_code.search(live), "live code must not be misread as dead_code"
    assert dead_code.search(commented), "a genuine commented-out definition must still match"


def test_scheme_quote_shorthand_and_bare_keyword_immutability_locks():
    """
    immutability_locks has two alternatives: the bare `quote` keyword
    form and Scheme's `'(...)` quote shorthand (a lone `'` immediately
    followed by an open paren). Both represent the same semantic
    immutability-via-quotation concept.
    """
    immutability_locks = SCHEME_RULES["immutability_locks"]
    assert immutability_locks.search("(quote (1 2 3))")
    assert immutability_locks.search("'(1 2 3)")
    assert not immutability_locks.search("(+ x 1)")


def test_scheme_no_stray_closing_token_confuses_structural_rules():
    """
    Lexical-family audit (per the issue's note): line_exclusive has no
    real cross-line block-comment tracking (see the module-level NOTE and
    #770). Confirms a stray, unmatched closing token like `|#` on its own
    doesn't fool a structural rule at the raw-regex level -- none of
    scheme's rules reference `#|`/`|#` at all, so this is a non-issue for
    the rules themselves (the real gap lives in prism.py's stream
    splitting, tracked separately in #770).
    """
    branch = SCHEME_RULES["branch"]
    stray = "|#\n(if (> x 0) 'positive 'negative)"
    assert branch.search(stray), "branch should still see the real if-expression after a stray |#"


def test_scheme_redos_immunity_sweep():
    """
    ReDoS immunity sweep across scheme's rules with unbounded-looking
    quantifiers, verified via a systematic scaling sweep (n=2000/4000/
    8000/16000/32000) before writing this test -- all rules showed ~2x
    time per doubling (linear) after the spec_exposure fix, not the ~4x
    signature of catastrophic backtracking.
    """
    assert_redos_immune(SCHEME_RULES["func_start"], "(define (" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["class_start"], "(define-record-type " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["globals"], "(define " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["args"], "(define (foo " + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["dead_code"], ";" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["doc"], ";;;" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["ownership"], "; Author:" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(SCHEME_RULES["_dependency_capture"], "(import (" + " " * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert SCHEME_RULES["func_start"].search("(define (list->vector x) x)")
    assert SCHEME_RULES["class_start"].search("(define-record-type <point> (make-point x y) point?)")
    assert SCHEME_RULES["globals"].search("(define default->value 5)")


_SCHEME_DEEP_CASES = [
    # branch
    ("branch", "(\n  if a b c)", "xif"),
    ("branch", "if (a)", "if-var"),
    ("branch", "(cond\n (else 1))", "conditional"),
    ("branch", "(when (and a b))", "awhen"),
    ("branch", "unless", "runless"),
    # args
    ("args", "(define (foo \n x \n y)\n  ...)", "(define foo 5)"),
    ("args", "(define (foo))", "(define (foo"),
    ("args", "(define (foo . rest) ...)", "(define foo (lambda (x) x))"),
    ("args", "(define (foo!x y))", "(define foo!x)"),
    ("args", "(define (a-b-c d e))", "(+ 1 2)"),
    # func_start
    ("func_start", "(define (call/cc-wrapper x) ...)", "(define foo 5)"),
    ("func_start", "(\n  define (foo x))", "(define-syntax foo)"),
    ("func_start", "(define (* a b) ...)", None),
    ("func_start", "(define (1+ x) x)", "(define)"),
    ("func_start", "(define (foo))", "define (foo)"),  # space instead of (
    # class_start
    ("class_start", "(define-record-type point)", "(define-record-type)"),
    ("class_start", "(\n  define-record-type <point>)", "(define (define-record-type x))"),
    ("class_start", "(define-record-type (point x y))", "(+ 1 2)"),
    ("class_start", "(define-record-type point\n  (make-point))", "define-record-type x"),
    # structural_boundaries
    ("structural_boundaries", "(let ((x 1)) x)", "let-syntax"),
    ("structural_boundaries", "(let* ((x 1)) x)", "foo-let"),
    ("structural_boundaries", "(\n  letrec ((x 1)))", "letrec-syntax"),
    ("structural_boundaries", "begin", "abegin"),
    ("structural_boundaries", "(do ((i 0 (+ i 1))) ((= i 5)) i)", "redo"),
]


@pytest.mark.parametrize("signature,positive,negative", _SCHEME_DEEP_CASES)
def test_scheme_deep_cases(signature, positive, negative):
    pattern = SCHEME_RULES[signature]
    assert pattern is not None
    assert pattern.search(positive), f"Deep positive failed for {signature}: {positive!r}"
    if negative:
        assert not pattern.search(negative), f"Deep negative failed for {signature}: {negative!r}"


def test_scheme_debt_rules_ignore_hyphenated_symbols_regression():
    """#2537: scheme reproduces the hyphenated-identifier debt leak -- a
    `(define (probe-todo ...))` symbol recorded planned_debt alongside the
    real `;; TODO:` comment (the #1096 control corpus measured planned_debt
    2 for one planted marker). Kebab-case is THE Lisp-family naming
    convention, so ordinary symbols must never feed debt scoring."""
    planned = SCHEME_RULES["planned_debt"]
    fragile = SCHEME_RULES["fragile_debt"]

    corpus_shaped = "(define (probe-todo plan)\n  ;; TODO: fill in the probe body later\n  'planned)\n"
    assert len(planned.findall(corpus_shaped)) == 1, "planned_debt must count ONLY the ;; TODO: comment"

    for text in ("(fix-me-later x)", "(define bug-tracker '())", "(hack-level 9)"):
        assert not fragile.search(text), f"fragile_debt matched inside symbol: {text!r}"
        assert not planned.search(text), f"planned_debt matched inside symbol: {text!r}"


# ==============================================================================
# #2674: globals -- body position, not indentation, decides scope
# ==============================================================================
# The `globals` regex matches every `(define name value)`; in Scheme the same
# indented line is a LOCAL binding inside a lambda/let/procedure body and a
# GLOBAL inside a file-wrapping `(let () ...)`. detector.py's coding_analysis
# applies the registry-declared `lisp_body_position` scope filter, so these
# tests go through the real extractor, not the bare regex.


def _scheme_globals(code: str) -> int:
    from gitgalaxy.core.detector import StructuralExtractor

    return StructuralExtractor("scheme", LANGUAGE_DEFINITIONS).splice(code, "")["equations"]["globals"]


def test_scheme_scope_filter_is_declared_for_globals():
    assert SCHEME_RULES["_scope_filters"] == {"globals": "lisp_body_position"}


def test_scheme_globals_internal_define_inside_procedure_is_not_global():
    """The issue's own example: identical indentation, opposite meaning."""
    internal = "(define (f x)\n  (define y 5)\n  y)\n"
    assert SCHEME_RULES["globals"].search(internal), "sanity: the bare regex still matches the internal define"
    assert _scheme_globals(internal) == 0
    assert _scheme_globals("(define counter 0)\n" + internal) == 1


@pytest.mark.parametrize(
    "body_form",
    [
        "(lambda (x)\n  (define y 5)\n  y)",
        "(let ((a 1))\n  (define y 5)\n  y)",
        "(let loop ((i 0))\n  (define y 5)\n  y)",
        "(let* ([a 1])\n  (define y 5)\n  y)",
        "(letrec ((a 1))\n  (define y 5)\n  y)",
        "(when flag\n  (define y 5)\n  y)",
        "(case-lambda\n  [(x) (define y 5) y])",
        "(parameterize ([p 1])\n  (define y 5)\n  y)",
        "(cond\n  [else (define y 5) y])",
        "(do ((i 0 (+ i 1))) ((= i 3))\n  (define y 5))",
        "(define-syntax m\n  (syntax-rules ()\n    [(_ n) (define y 5)]))",
        "(define-record-type point\n  (define y 5))",
    ],
)
def test_scheme_globals_body_forms_hide_internal_defines(body_form):
    assert _scheme_globals(body_form) == 0


def test_scheme_globals_file_wrapping_let_is_module_scope():
    """
    Chez's cpnanopass.ss puts its whole body inside `(let () ...)`; its 682
    indented defines include every real global, and the #2651 column-0
    anchor would have zeroed them all.
    """
    code = "(let ()\n  (define track-counts #f)\n  (define (g)\n    (define z 1)\n    z)\n  (define other 2))\n"
    assert _scheme_globals(code) == 2


def test_scheme_globals_nested_empty_let_is_a_block_scope():
    """Only the OUTERMOST bindings-less let is the wrapper; syntax.ss's `(let () (define who ...))` runs are blocks."""
    code = "(let ()\n  (define g 1)\n  (let ()\n    (define who 'x)\n    (define tls 2)))\n"
    assert _scheme_globals(code) == 1


def test_scheme_globals_begin_and_let_syntax_splice_into_the_wrapper():
    """R7RS 5.6.1 `begin` and R6RS 11.18 `let-syntax` bodies splice into the enclosing context."""
    code = "(let-syntax ([m (syntax-rules () [(_) 1])])\n  (let ()\n    (begin\n      (define hook 1))\n    (define k 2)))\n"
    assert _scheme_globals(code) == 2


def test_scheme_globals_library_and_module_forms_are_module_scope():
    code = (
        "(library (foo)\n  (export a)\n  (import (rnrs))\n  (define a 1))\n"
        "(module bar racket\n  (define b 2))\n"
        "(define-library (baz)\n  (begin\n    (define c 3)))\n"
    )
    assert _scheme_globals(code) == 3


def test_scheme_globals_local_module_inside_a_body_is_internal():
    """Chez allows `(module ...)` wherever a definition can appear; inside a procedure it is local."""
    code = "(define (pass ir)\n  (module (helper)\n    (define helper 1))\n  helper)\n"
    assert _scheme_globals(code) == 0
    # ... but a module directly under the wrapper exports into file scope.
    assert _scheme_globals("(let ()\n  (module (x)\n    (define x 1)))\n") == 1


def test_scheme_globals_strings_and_char_literals_do_not_desync_the_walk():
    code = (
        '(define s "a ) ( (define q 1)")\n'
        "(define c #\\( )\n"
        "(define d #\\))\n"
        "(define e #\\space)\n"
        "(define (f)\n  (define local 1)\n  local)\n"
        "(define after 1)\n"
    )
    # s, c, d, e, after -- not the string's fake define, not `local`.
    assert _scheme_globals(code) == 5


def test_scheme_globals_square_brackets_open_body_scope_too():
    """Racket/R6RS `[` is a paren; a define inside a bracketed clause body is internal."""
    assert _scheme_globals("(define (f x)\n  (cond\n    [x (define y 1) y]\n    [else 2]))\n") == 0
    assert _scheme_globals("[define g 1]\n(define h 2)\n") == 1  # bracket form never matched the regex


def test_scheme_globals_filter_keeps_counts_spatial_map_and_locations_consistent():
    from gitgalaxy.core.detector import StructuralExtractor

    d = StructuralExtractor("scheme", LANGUAGE_DEFINITIONS)
    code = "(define a 1)\n(define (f)\n  (define b 2)\n  b)\n(define c 3)\n"
    counts, _mit, spatial_maps, _parents, locations = d.coding_analysis([("scheme", code, 0)])
    assert counts["globals"] == 2
    assert len(spatial_maps[0]["globals"]) == 2
    assert locations["globals"] == [1, 5]


def test_scheme_globals_unknown_scope_filter_name_is_ignored_not_zeroed():
    import copy

    from gitgalaxy.core.detector import StructuralExtractor

    defs = copy.deepcopy(LANGUAGE_DEFINITIONS)
    defs["scheme"]["rules"]["_scope_filters"] = {"globals": "no-such-filter"}
    code = "(define (f)\n  (define b 2)\n  b)\n"
    assert StructuralExtractor("scheme", defs).splice(code, "")["equations"]["globals"] == 1


def test_scheme_scope_walk_is_linear_on_pathological_input():
    """
    The scope pass is a tokenizer + stack, not a regex, so the strict
    harness's regex timer doesn't apply; time it directly on the shapes
    that would hurt a backtracking tokenizer.
    """
    import time

    from gitgalaxy.core.detector import StructuralExtractor

    d = StructuralExtractor("scheme", LANGUAGE_DEFINITIONS)
    payloads = [
        '"' + "(define x 1)\n" * 20000,  # unterminated string then a real file
        "(" * 200000,
        '"' * 200000,
        "(define (f)\n" * 20000 + "(define g 1)" + ")" * 20000,
        "#\\( " * 100000,
        "#| " + "(define x 1)\n" * 20000,
        '"' + "\\" * 200000,
    ]
    for payload in payloads:
        t0 = time.perf_counter()
        d._lisp_module_level_define_offsets(payload)
        assert time.perf_counter() - t0 < 3.0, f"scope walk too slow on {payload[:12]!r}..."
    # unterminated string only blinds its own line
    assert len(d._lisp_module_level_define_offsets(payloads[0])) == 19999
