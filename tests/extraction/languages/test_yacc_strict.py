"""yacc strict structural-signature coverage.

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

from _strict_harness import assert_redos_immune, _best_of_timing  # noqa: E402 # type: ignore


# ==============================================================================
# YACC: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #616)
# ==============================================================================
YACC_RULES = LANGUAGE_DEFINITIONS["yacc"]["rules"]

_YACC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", 'if (state == ERROR) { yyerror("bad state"); }', "int x = 1;"),
    ("args", "$$ = $1 + $2;", "int x = 1;"),
    ("structural_boundaries", "%token NUMBER\n", "int x = 1;"),
    (
        "func_start",
        "expr:\n    expr '+' term { $$ = $1 + $3; }\n    | term\n    ;\n",
        "%token NUMBER\n",
    ),
    # --- PHASE 2 ---
    ("safety", "assert(x != NULL);", "int x = 1;"),
    ("safety_bypasses", "goto err;", "int x = 1;"),
    ("high_risk_execution", "exit(1);", "return 0;"),
    ("io", 'fp = fopen("grammar.log", "r");', "int x = 1;"),
    ("api", "%define api.pure full\n", "%token NUMBER\n"),
    ("state_mutation", "x = 5;", "if (x == 5) { }"),
    ("dead_code", "// if (x) foo();", "// just a comment"),
    ("doc", "/** @param x the lookahead token */", "/* just a comment */"),
    # --- PHASE 3 ---
    ("globals", "yylval.ival = 5;", "int x = 5;"),
    ("generics", "%type <expr> assignment\n", "%type expr\n"),
    ("reflection_metaprogramming", "%%\n", "int x;\n"),
    ("import", '#include "parser.h"\n', "int x;\n"),
    ("ownership", "// Author: Jane Doe\n", "// regular comment\n"),
    # --- PHASE 4 ---
    ("planned_debt", "// TODO: handle the error-recovery case\n", "// regular comment\n"),
    ("fragile_debt", "// HACK: workaround for a bison shift/reduce conflict\n", "// regular comment\n"),
    ("spec_exposure", "// [SPEC-123] grammar rule per spec\n", "// regular comment\n"),
    ("macros", "#define YYDEBUG 1\n", "int x;\n"),
    ("pointers", "x = *ptr;", "int x = 5;"),
    ("memory_alloc", "node = malloc(sizeof(Node));", "int x;\n"),
    # --- PHASE 5 ---
    ("telemetry", 'syslog(LOG_ERR, "parse failed");', "int x;\n"),
    ("debug_prints", 'printf("%d\\n", x);', "int x;\n"),
    ("explicit_casts", "x = (int)y;", "int x;\n"),
    ("panics_and_aborts", "abort();", "return 0;"),
    ("bitwise_ops", "flags = flags & MASK;", "flags = flags && other;"),
    ("immutability_locks", "const int MAX = 10;", "int x;\n"),
    ("cleanup", "free(ptr);", "int x;\n"),
    ("encapsulation", "static int counter = 0;", "int counter = 0;"),
]


@pytest.mark.parametrize("signature,positive,negative", _YACC_SIMPLE_CASES)
def test_yacc_signature_positive_and_negative(signature, positive, negative):
    pattern = YACC_RULES[signature]
    assert pattern is not None, f"yacc's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"yacc {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"yacc {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_yacc_structural_boundaries_percent_directive_leading_boundary_regression():
    """
    Regression test (Rule 9): `%token`/`%type`/`%left`/`%right`/`%nonassoc`
    all start with `%` (non-word), so the shared leading `\\b` inside
    `\\b(...)\\b` could only fire when a word character immediately preceded
    the `%` -- never true for how these grammar directives are actually
    written (always the first token on a line, preceded only by whitespace
    or nothing). All five directive alternatives never matched at all;
    only `return`/`goto`/`break`/`continue` (which start on a word char)
    ever fired. Fixed by pulling the `%`-prefixed alternatives out of the
    `\\b(...)\\b` group and anchoring each with only a trailing `\\b` (the
    `%` is already self-delimiting).
    """
    pattern = YACC_RULES["structural_boundaries"]
    assert pattern.search("%token NUMBER\n"), "%token at line start still didn't match"
    assert pattern.search("  %type <val> expr\n"), "%type after leading whitespace still didn't match"
    assert pattern.search("%left '+' '-'\n"), "%left still didn't match"
    assert pattern.search("%right '='\n"), "%right still didn't match"
    assert pattern.search("%nonassoc EQ\n"), "%nonassoc still didn't match"
    assert pattern.search("return x;"), "return regressed"
    assert pattern.search("goto err;"), "goto regressed"


def test_yacc_api_percent_directive_leading_boundary_regression():
    """
    Regression test (Rule 9): identical bug to structural_boundaries, in
    the same rule dict. `%define`/`%code`/`%provides`/`%requires` all
    start with `%` (non-word); wrapped in `\\b(...)\\b`, the leading `\\b`
    could never fire at the real start-of-line position preceded by
    whitespace/newline (both non-word), so `api` never matched a single
    one of its four documented directives. Fixed by dropping the leading
    `\\b` on each `%`-prefixed alternative (self-delimiting) while keeping
    the trailing `\\b`.
    """
    pattern = YACC_RULES["api"]
    assert pattern.search("%define api.pure full\n"), "%define still didn't match"
    assert pattern.search("%code requires {\n"), "%code still didn't match"
    assert pattern.search("%provides\n"), "%provides still didn't match"
    assert pattern.search("%requires\n"), "%requires still didn't match"


def test_yacc_safety_bypasses_void_pointer_trailing_boundary_regression():
    """
    Regression test (Rule 9, trailing-side variant): the two alternatives
    inside `\\b(goto|void\\s*\\*)\\b` don't share the same edge shape --
    `goto` ends on a word char, `void\\s*\\*` ends on a symbol (`*`). The
    shared trailing `\\b` required a word character to immediately follow
    the `*`, which only happens to be true for the no-space style
    (`void *ptr`). The equally common `void* ptr` (asterisk attached to
    the type) and any style with more than one space before the
    identifier (`void *  ptr`) failed the trailing boundary and never
    matched. Fixed by dropping the trailing `\\b` on the `void\\s*\\*`
    alternative (the `*` is already self-delimiting).
    """
    pattern = YACC_RULES["safety_bypasses"]
    assert pattern.search("void *ptr;"), "void *ptr (no-space) form regressed"
    assert pattern.search("void* ptr;"), "void* ptr (attached asterisk) still didn't match"
    assert pattern.search("void *  ptr;"), "void with multiple spaces before identifier still didn't match"
    assert pattern.search("static void *foo(void)"), "void* in a function signature still didn't match"
    assert pattern.search("goto err;"), "goto regressed"


def test_yacc_func_start_switch_case_and_access_specifier_false_positive_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: func_start's
    `identifier :` anchor is deliberately shaped to catch yacc grammar
    rule productions (`expr :`), but embedded C/C++ action code in the
    same file shares the identical textual shape for constructs that are
    NOT grammar rules or executable-logic starts (Rule 7):
    switch-statement `default:` labels, and (in `.ypp` C++ variant files)
    `public:`/`private:`/`protected:` class access specifiers. All of
    these previously false-positived as grammar rule starts. Fixed with a
    negative lookahead excluding `case`/`default`/`public`/`private`/
    `protected` from the captured identifier.
    """
    pattern = YACC_RULES["func_start"]
    assert pattern.search("expr:\n    expr '+' term\n    ;\n"), "real grammar rule regressed"
    assert pattern.search("stmt_list:\n"), "real grammar rule (no body on same line) regressed"

    switch_block = "    switch (x) {\n    case 1:\n        break;\n    default:\n        break;\n    }\n"
    assert not pattern.search(switch_block), "incorrectly matched a switch-case default: label as func_start"

    assert not pattern.search("public:\n    int foo();\n"), "incorrectly matched a C++ 'public:' access specifier"
    assert not pattern.search("private:\n"), "incorrectly matched a C++ 'private:' access specifier"
    assert not pattern.search("protected:\n"), "incorrectly matched a C++ 'protected:' access specifier"


def test_yacc_dead_code_comment_style_completeness_regression():
    """
    Regression test (Rule 12): yacc's `lexical_family` is `standard_block`
    (both `//` and `/* */` comments are valid, per this language's own
    `_meta` rationale that it "relies entirely on standard '/* */' and
    '//' comments"). The `dead_code` rule's `//` alternative covered
    `if|for|while|return|%token`, but its `/* */` alternative silently
    dropped `return` from the keyword list -- a block-commented-out
    `return` statement never fired as dead_code even though the identical
    line commented with `//` did. Fixed by adding `return` to the
    `/* */` alternative so both comment styles have parity.
    """
    pattern = YACC_RULES["dead_code"]
    assert pattern.search("// return x;"), "'//' style with return regressed"
    assert pattern.search("/* return x; */"), "'/* */' style with return still didn't match"
    assert pattern.search("// if (x) foo();"), "'//' style with if regressed"
    assert pattern.search("/* if (x) foo(); */"), "'/* */' style with if regressed"
    assert pattern.search("/* %token FOO */"), "'/* */' style with %token regressed"


def test_yacc_explicit_casts_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS vector: three
    sequential unbounded `\\s*` quantifiers (`\\s*` after `(`, `\\s*`
    after the type name, `\\s*` after the optional `\\*?`) with no
    closing `)` ever present in the payload force the engine to
    re-attempt every possible split of the whitespace run across the
    three quantifiers before failing at each starting offset -- classic
    polynomial backtracking. Verified genuine ~4x-per-doubling scaling
    on the unfixed pattern at n=2000/4000/8000/16000/32000: 0.0047s /
    0.0186s / 0.0743s / 0.2952s / 1.1790s (ratios ~3.96-3.99, the
    signature of O(n^2), not the ~2x/doubling of linear work). Fixed by
    bounding all three whitespace quantifiers to `[ \\t]{0,20}`.
    """
    pattern = YACC_RULES["explicit_casts"]

    # _best_of_timing (min-of-5) instead of a single perf_counter() sample
    # per size -- a lone scheduling hiccup on any one size (common on
    # contended CI runners) used to be indistinguishable from a real
    # regression. Same hardening already applied to the shared
    # _best_of_timing/ratio checks elsewhere in this file (#800).
    timings = [_best_of_timing(pattern, "(int" + " " * n) for n in (2000, 4000, 8000, 16000, 32000)]

    assert_redos_immune(pattern, "(int" + " " * 100000, timeout_sec=3.0)

    # After bounding, doubling the input must not multiply the runtime by
    # anywhere near 4x (the O(n^2) signature) -- a generous 2.5x ceiling
    # comfortably separates fixed-linear/constant behavior from a
    # regression back to catastrophic backtracking.
    for earlier, later in zip(timings, timings[1:]):
        assert later < max(earlier * 2.5, 0.01), f"explicit_casts scaling regressed toward O(n^2): {timings}"

    # Realistic cast forms must still match after bounding.
    assert pattern.search("$$ = (int)$1;"), "plain cast regressed"
    assert pattern.search("ptr = (char *)malloc(10);"), "pointer-cast regressed"
    assert pattern.search("ptr = (MyType*)base;"), "custom-type cast regressed"
    assert pattern.search("x = ( int )y;"), "spaced cast regressed"


def test_yacc_redos_immunity():
    """
    ReDoS scaling verification (Rule 5) for the remaining rules with
    unbounded-looking quantifiers, each fired against a never-closing
    adversarial payload at a large multiplier. None showed a real
    catastrophic-backtracking growth curve (all resolve in well under a
    millisecond even at n=100000), so no bounding was needed for these --
    included here as regression coverage against a future edit
    reintroducing an unbounded ambiguity.
    """
    assert_redos_immune(YACC_RULES["ownership"], "Author: " + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["import"], "#include <" + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["spec_exposure"], "[SPEC-1 [" + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["pointers"], "= *" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["cleanup"], "free" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["func_start"], "a" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["generics"], "<" + "a" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["dead_code"], "//" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["structural_boundaries"], "%token " * 20000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["api"], "%define " * 20000, timeout_sec=2.0)

    # Realistic-but-large inputs must still match after any bounding.
    assert YACC_RULES["ownership"].search("// Author: Jane Doe")
    assert YACC_RULES["import"].search('#include "parser.h"')
    assert YACC_RULES["spec_exposure"].search("[SPEC-123] audit trail")
    assert YACC_RULES["pointers"].search("x = *ptr;")
    assert YACC_RULES["cleanup"].search("free(ptr);")
    assert YACC_RULES["func_start"].search("expr:\n")
    assert YACC_RULES["generics"].search("%type <val> expr")


def test_yacc_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (explicit_casts vs
    pointers, previously found in C): checked and confirmed a structurally
    -forced non-collision, not a bug. `pointers`' asterisk alternative
    only fires via `(?<=[=(,])[ \\t]*\\*...` -- it requires the character
    immediately before the (optional whitespace then) `*` to be `=`, `(`,
    or `,`. In a cast like `(char *)ptr`, the `*` is instead preceded by
    the type name (`char`), so the lookbehind never matches. Per Rule 2
    (idiomatic paradigm alignment), pointer-typed casts are correctly
    routed to `explicit_casts` alone.
    """
    explicit_casts = YACC_RULES["explicit_casts"]
    pointers = YACC_RULES["pointers"]

    for snippet in ("ptr = (char *)base;", "ptr = (MyType*)base;", "x = (int)y;"):
        assert explicit_casts.search(snippet), f"explicit_casts should match: {snippet!r}"
        assert not pointers.search(snippet), f"pointers incorrectly matched a cast: {snippet!r}"

    real_pointer_deref = "foo(a, *ptr);"
    assert pointers.search(real_pointer_deref), "real pointer dereference regressed"


def test_yacc_pointers_and_bitwise_ops_address_of_intentional_overlap():
    """
    Ambiguity-sweep finding: `pointers`' bare `&\\w+` alternative (address-
    of) and `bitwise_ops`' `(?<!&)&(?!&)` alternative (bitwise AND,
    excluding `&&`) both fire on the same text for a no-space address-of
    expression like `&tree`, because C-family syntax genuinely reuses the
    single `&` glyph for both operations -- an AST-free regex engine
    cannot disambiguate them without type information. This is an
    accepted, intentional double-classification (both signatures are
    "correct" simultaneously), not a bug to narrow. Confirmed the two
    rules still diverge on their own unambiguous shapes: `flags & MASK`
    (spaced bitwise AND, not address-of) triggers bitwise_ops only, and
    `flags && other` (logical AND) triggers neither.
    """
    pointers = YACC_RULES["pointers"]
    bitwise_ops = YACC_RULES["bitwise_ops"]

    address_of = "node = &tree;"
    assert pointers.search(address_of)
    assert bitwise_ops.search(address_of)

    spaced_and = "flags = flags & MASK;"
    assert bitwise_ops.search(spaced_and)
    assert not pointers.search(spaced_and)

    logical_and = "flags = flags && other;"
    assert not bitwise_ops.search(logical_and)


def test_yacc_func_start_and_macros_no_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line
    #define/macro spiral hallucinating a function match, previously found
    in C++): checked and confirmed not applicable to yacc. func_start
    requires an identifier immediately followed by a colon at the
    physical start of a line; a `#define`/multi-line-continuation macro
    never produces that shape regardless of how many continuation lines
    it spans. Empirically confirmed no overlap.
    """
    func_start = YACC_RULES["func_start"]
    macros = YACC_RULES["macros"]

    macro_spiral = (
        "#define VERY_LONG_MACRO(x, y, z) \\\n    do { \\\n        foo(x); \\\n        bar(y); \\\n    } while (0)\n"
    )
    assert macros.search(macro_spiral)
    assert not func_start.search(macro_spiral)

    grammar_rule = "expr:\n    expr '+' term\n    ;\n"
    assert func_start.search(grammar_rule)
    assert not macros.search(grammar_rule)


def test_yacc_func_start_and_generics_no_collision():
    """
    Known ambiguity pattern from the issue template (func_start vs
    generics, previously found in C# via deeply nested generic return
    types): checked and confirmed not applicable to yacc. `generics`
    anchors on the `<identifier>` shape used by `%type <val>` union-tag
    declarations; `func_start` anchors on `identifier:` at line start.
    These are disjoint textual shapes with no shared literal token.
    Empirically confirmed no overlap, and no catastrophic backtracking
    from a deeply-repeated `<` payload either.
    """
    func_start = YACC_RULES["func_start"]
    generics = YACC_RULES["generics"]

    type_decl = "%type <expr> assignment\n"
    assert generics.search(type_decl)
    assert not func_start.search(type_decl)

    grammar_rule = "assignment:\n    ID '=' expr\n    ;\n"
    assert func_start.search(grammar_rule)
    assert not generics.search(grammar_rule)

    assert_redos_immune(generics, "<" * 100000, timeout_sec=2.0)


def test_yacc_spec_exposure_nested_bracket_not_a_realistic_construct():
    """
    Nested-delimiter audit (Rule 11): `spec_exposure`'s trailing
    `[^\\]]*\\]` is a flat negated-class delimiter matcher. Checked against
    a one-level-nested bracket input the same way generics/indexers are
    checked elsewhere. Unlike a generic return type or indexer, a
    bracketed spec/audit tag has no realistic nested-bracket form in
    practice (real usage is always a flat `[SPEC-123]`/`[audit]`), so
    there is no realistic input this flat class fails to detect -- it
    still matches (just truncating its span at the first `]`, which
    doesn't matter since spec_exposure has no paired capture-group rule
    extracting structured content from it, unlike `import`'s
    `_dependency_capture`). Confirmed not a bug: the boolean
    "does a spec/audit tag exist" signal is unaffected either way.
    """
    pattern = YACC_RULES["spec_exposure"]
    assert pattern.search("// [SPEC-123] grammar rule per spec")
    assert pattern.search("// [audit] traceability tag")
    # Nested case still detects presence of the tag (span truncates early,
    # which is inconsequential -- see docstring).
    assert pattern.search("// [SPEC-123 [ref-456]] audit trail")


def test_yacc_lexical_family_dead_code_fires_under_both_comment_styles():
    """
    Comment-style audit (Rule 12), confirming lexical_family parity beyond
    the single-keyword regression above: yacc is `standard_block`, so
    both native comment delimiters must independently trigger dead_code
    for the same underlying commented-out logic.
    """
    pattern = YACC_RULES["dead_code"]
    for keyword in ("if", "for", "while", "return"):
        line_style = f"// {keyword} (x) {{ }}"
        block_style = f"/* {keyword} (x) {{ }} */"
        assert pattern.search(line_style), f"'//' style with {keyword!r} didn't match"
        assert pattern.search(block_style), f"'/* */' style with {keyword!r} didn't match"
