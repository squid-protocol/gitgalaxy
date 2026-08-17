"""
Strict/adversarial coverage for the #1145 naming-convention classifier in
detector.py: the `_var_decl_pattern` regex (StructuralExtractor.__init__) and
the `_classify_identifier_casing` static method it feeds, which together give
real producers to the previously-dead `core_var_decl`/`design_*` SIGNAL_SCHEMA
columns.

This isn't a per-language signature (see how_to_add_a_language.md) -- it's a
single universal mechanism applied once per file regardless of language, the
same precedent `indent_tabs`/`indent_spaces` already establish in
coding_analysis(). So this file follows the *spirit* of the per-language
`test_<lang>_strict.py` adversarial methodology (real positive/negative cases
verified by an actual `.search()` call rather than reasoned from pattern shape,
a ReDoS scaling sweep, boundary/ambiguity audits) adapted to one regex instead
of forty, plus a pure-Python classifier function instead of a regex family.
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent.parent / "extraction" / "languages")
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import _best_of_timing, assert_redos_immune  # noqa: E402 # type: ignore


@pytest.fixture(scope="module")
def var_decl_pattern() -> re.Pattern:
    # Universal (not per-language) -- any lang_id shares the same compiled pattern.
    return StructuralExtractor("python", LANGUAGE_DEFINITIONS)._var_decl_pattern


def _classify(name: str):
    return StructuralExtractor._classify_identifier_casing(name)


# ==============================================================================
# 1. PER-SIGNATURE POSITIVE CASES (var_decl pattern)
# Every case verified by an actual .search() call, not reasoned from the
# pattern's shape -- realistic code, not synthetic strings engineered to match.
# ==============================================================================
_VAR_DECL_POSITIVE_CASES = [
    ("bare snake_case", "my_variable_name = 5", "my_variable_name"),
    ("bare camelCase", "myVariableName = 5", "myVariableName"),
    ("bare PascalCase", "MyVariableName = 5", "MyVariableName"),
    ("bare UPPER_CASE", "MAX_RETRIES = 3", "MAX_RETRIES"),
    ("single-char", "x = 1", "x"),
    ("let-led (JS/Rust/Swift/Kotlin)", "let userName = 'joe';", "userName"),
    ("const-led", "const MAX_COUNT = 10;", "MAX_COUNT"),
    ("var-led", "var legacyFlag = true;", "legacyFlag"),
    ("val-led (Kotlin/Scala)", "val immutableName = 'x'", "immutableName"),
    ("mut-led (Rust)", "let mut counter = 0;", "counter"),
    ("C-style typed, no generics", "int typedVar = 5;", "typedVar"),
    ("C-style typed, string", 'String annotatedType = "hi";', "annotatedType"),
    (
        "C-style typed, nested generics + modifiers",
        "private final Map<String, Integer> counterMap = new HashMap<>();",
        "counterMap",
    ),
    ("arrow-function assignment (JS)", "const handler = (x) => x + 1;", "handler"),
    ("dunder", '__version__ = "1.0"', "__version__"),
    ("leading underscore", "_private_var = 1", "_private_var"),
    ("digit-suffixed identifier", "value2 = 5", "value2"),
    ("dict/object literal assigned to a var", 'config = {"key": 1}', "config"),
    ("f-string debug specifier on the RHS (Python 3.8+)", 'msg = f"{x=}"', "msg"),
    ("indented declaration inside a function body", "    local_var = 1", "local_var"),
]


@pytest.mark.parametrize(
    "label,snippet,expected", _VAR_DECL_POSITIVE_CASES, ids=[c[0] for c in _VAR_DECL_POSITIVE_CASES]
)
def test_var_decl_pattern_positive_cases(var_decl_pattern, label, snippet, expected):
    m = var_decl_pattern.search(snippet)
    assert m is not None, f"[{label}] expected a match on: {snippet!r}"
    assert m.group(1) == expected, f"[{label}] expected {expected!r}, got {m.group(1)!r}"


# ==============================================================================
# 2. NEGATIVE CASES -- comparisons, augmented assignment, and call-site kwargs
# must never be mistaken for a declaration. The `(?!=)` lookahead is the only
# thing standing between this rule and counting every `==` in the file as a
# variable declaration, so this is the single most safety-critical case here.
# ==============================================================================
_VAR_DECL_NEGATIVE_CASES = [
    ("equality comparison", "if x == 5:"),
    ("chained comparison", "if 0 <= x <= 10:"),
    ("not-equal comparison", "if x != y:"),
    ("greater-or-equal comparison", "if x >= y:"),
    ("less-or-equal comparison", "if x <= y:"),
    ("augmented add-assign", "x += 1"),
    ("augmented sub-assign", "total -= amount"),
    ("walrus operator", "if (x := compute()):"),
    ("keyword-arg call, no spaces (PEP8 style)", "foo(bar=5)"),
    ("keyword-arg call, with spaces", "foo(bar = 5)"),
    ("type annotation with no default", "x: int"),
]


@pytest.mark.parametrize("label,snippet", _VAR_DECL_NEGATIVE_CASES, ids=[c[0] for c in _VAR_DECL_NEGATIVE_CASES])
def test_var_decl_pattern_negative_cases(var_decl_pattern, label, snippet):
    m = var_decl_pattern.search(snippet)
    assert m is None, f"[{label}] expected NO match on {snippet!r}, but got {m.group(1)!r}"


def test_var_decl_pattern_chained_assignment_only_counts_first_target(var_decl_pattern):
    """Documented limitation, not a bug: `a = b = 5` only counts `a`. The `^`
    anchor (re.M) can't re-fire mid-line for `b`, since re.M's `^` only matches
    right after a real newline, not after an in-line `=`. Chained assignment is
    rare enough in real code that this is an acceptable v1 approximation --
    this test exists so a future "fix" doesn't silently change the count
    without the change being deliberate."""
    matches = list(var_decl_pattern.finditer("a = b = 5"))
    assert len(matches) == 1
    assert matches[0].group(1) == "a"


def test_var_decl_pattern_false_positives_on_no_space_default_param(var_decl_pattern):
    """Documented limitation, not a bug: a multi-line function signature's
    continuation line (`    x=5,`) is lexically indistinguishable from a real
    top-of-line declaration -- both are `IDENT=value` anchored at `^[ \\t]*`.
    This is the same class of approximation indent_tabs/indent_spaces already
    accept elsewhere in this file. Asserted explicitly (not just omitted from
    the negative-case list) so this known gap stays visible and isn't
    silently "fixed" into different behavior by accident."""
    m = var_decl_pattern.search("    x=5,")
    assert m is not None and m.group(1) == "x"


def test_var_decl_pattern_false_positives_on_commented_out_assignment(var_decl_pattern):
    """Documented contract, not a bug: this pattern runs against `code_stream`,
    which by architectural contract (prism.py) has ALREADY had comments split
    out before StructuralExtractor.splice() ever sees it -- see core/README.md's
    pipeline description. Fed a raw, un-split comment line directly (bypassing
    that contract), it can't distinguish `# x = 5` from a real declaration.
    This is expected given the precondition, not a regex defect; verified here
    so the contract is explicit rather than assumed."""
    m = var_decl_pattern.search("# x = not a real assignment")
    assert m is not None and m.group(1) == "x"


# ==============================================================================
# 3. REDOS / ADJACENT-QUANTIFIER AUDIT (Rule 14)
# `[^=\n]{0,80}` sits immediately next to a required `[ \t]+` boundary -- both
# can match whitespace, the exact adjacency shape Rule 14 warns about. The
# `{0,80}` cap is what keeps this linear instead of quadratic; these tests
# prove that empirically rather than trusting the cap by inspection.
# ==============================================================================
def test_var_decl_pattern_redos_immune_long_space_run(var_decl_pattern):
    # "never closes" adversarial payload: a long space run with no `=` anywhere.
    assert_redos_immune(var_decl_pattern, "a" + (" " * 100000), timeout_sec=2.0)


def test_var_decl_pattern_redos_immune_long_nonequals_run(var_decl_pattern):
    assert_redos_immune(var_decl_pattern, ("word " * 20000), timeout_sec=2.0)


def test_var_decl_pattern_redos_immune_many_comparisons(var_decl_pattern):
    # Every `==` is a near-miss that must be rejected via the (?!=) lookahead,
    # not just a plain absence of '=' -- a harder adversarial shape than a
    # pure no-match payload.
    assert_redos_immune(var_decl_pattern, ("x == y " * 20000), timeout_sec=2.0)


def test_var_decl_pattern_scales_linearly_not_quadratically(var_decl_pattern):
    """Scale-relative sanity check (not an absolute wall-clock threshold, which
    is flaky across CI hardware): doubling the payload should cost ~2x
    (linear), not ~4x (the O(n^2) catastrophic-backtracking signature)."""
    small = _best_of_timing(var_decl_pattern, "a" + (" " * 8000))
    large = _best_of_timing(var_decl_pattern, "a" + (" " * 16000))
    ratio = large / small if small > 0 else 0
    assert ratio < 3.0, (
        f"expected roughly linear (~2x) scaling on a payload doubling, got {ratio:.2f}x "
        f"({small:.5f}s -> {large:.5f}s) -- possible quadratic regression"
    )


# ==============================================================================
# 4. IDENTIFIER-CASING CLASSIFIER -- adversarial cases
# ==============================================================================
_CASING_CASES = [
    ("x", "design_snake_case"),
    ("X", "design_upper_case"),
    ("i", "design_snake_case"),
    ("ID", "design_upper_case"),
    ("Id", "design_pascal_case"),
    ("my_var", "design_snake_case"),
    ("myVar", "design_camel_case"),
    ("MyVar", "design_pascal_case"),
    ("MY_VAR", "design_upper_case"),
    ("__init__", "design_snake_case"),
    ("_private", "design_snake_case"),
    ("__dunder__", "design_snake_case"),
    ("value2", "design_snake_case"),
    ("Value2", "design_pascal_case"),
    ("VALUE2", "design_upper_case"),
    ("value_2", "design_snake_case"),
    ("a1b2c3", "design_snake_case"),
    ("HTMLParser", "design_pascal_case"),
    ("parseHTMLResponse", "design_camel_case"),
    ("HTML_PARSER", "design_upper_case"),
    ("MyCONST", "design_pascal_case"),
    ("ABC", "design_upper_case"),
    ("Abc", "design_pascal_case"),
    ("abc", "design_snake_case"),
    ("camelCase123", "design_camel_case"),
    ("PascalCase123", "design_pascal_case"),
    ("snake_case_123", "design_snake_case"),
    ("UPPER_123", "design_upper_case"),
]


@pytest.mark.parametrize("name,expected_bucket", _CASING_CASES, ids=[c[0] for c in _CASING_CASES])
def test_classify_identifier_casing(name, expected_bucket):
    assert _classify(name) == expected_bucket


_AMBIGUOUS_CASES = [
    ("already_snake_UPPER", "mixes a snake_case body with an ALL-CAPS segment -- neither convention cleanly"),
    ("_", "pure underscore, no letters to classify at all"),
    ("__", "pure underscore, no letters to classify at all"),
]


@pytest.mark.parametrize("name,reason", _AMBIGUOUS_CASES, ids=[c[0] for c in _AMBIGUOUS_CASES])
def test_classify_identifier_casing_returns_none_for_genuinely_ambiguous_names(name, reason):
    """Forcing a bucket on a genuinely mixed-convention identifier would corrupt
    the signal more than it clarifies it -- None is the correct, deliberate
    answer here, not a gap."""
    assert _classify(name) is None, f"{name!r} ({reason}) should not force into a bucket"


def test_classify_identifier_casing_mutual_exclusivity():
    """Every non-None classification must land in exactly one of the four
    design_* buckets -- the function is an if/elif chain by construction, but
    this is a direct regression guard against a future edit accidentally
    turning it into independent `if`s that double-count."""
    buckets = {"design_upper_case", "design_snake_case", "design_pascal_case", "design_camel_case"}
    all_names = [c[0] for c in _CASING_CASES]
    for name in all_names:
        result = _classify(name)
        assert result is None or result in buckets


# ==============================================================================
# 5. END-TO-END INTEGRATION -- StructuralExtractor.splice(), not the regex in
# isolation. This is what actually satisfies #1145's stated acceptance
# criteria: "a real file with PascalCase/snake_case/UPPER_CASE identifiers
# produces a nonzero count for the matching column."
# ==============================================================================
def test_splice_produces_nonzero_counts_for_every_design_bucket_python():
    code = """
my_variable_name = 5
myVariableName = 5
MyVariableName = 5
MAX_RETRIES = 3
def foo():
    local_var = 1
    return local_var
"""
    result = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(code, "")
    eq = result["equations"]

    assert eq["core_var_decl"] == 5
    assert eq["design_snake_case"] == 2  # my_variable_name, local_var
    assert eq["design_camel_case"] == 1  # myVariableName
    assert eq["design_pascal_case"] == 1  # MyVariableName
    assert eq["design_upper_case"] == 1  # MAX_RETRIES


def test_splice_produces_nonzero_counts_c_style_typed_declarations():
    code = """
public class Example {
    private int retryCount = 3;
    private String userName = "joe";
    private final Map<String, Integer> counterMap = new HashMap<>();
}
"""
    result = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")
    eq = result["equations"]

    assert eq["core_var_decl"] >= 3
    assert eq["design_camel_case"] >= 2  # retryCount, userName / counterMap


def test_splice_short_and_long_var_buckets():
    long_name = "a" * 30
    code = f"x = 1\n{long_name} = 2\n"
    result = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(code, "")
    eq = result["equations"]

    assert eq["design_short_vars"] == 1  # "x" (len 1)
    assert eq["design_long_vars"] == 1  # 30-char identifier


def test_splice_never_crashes_on_a_file_with_no_declarations():
    """Schema-completeness guard: even a file with zero matches must still
    carry all 7 keys at 0, never missing/None, since downstream consumers
    (signal_processor.py) call .get() on them unconditionally."""
    result = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice("if True:\n    pass\n", "")
    eq = result["equations"]
    for key in (
        "core_var_decl",
        "design_camel_case",
        "design_snake_case",
        "design_pascal_case",
        "design_upper_case",
        "design_short_vars",
        "design_long_vars",
    ):
        assert key in eq
        assert eq[key] == 0
