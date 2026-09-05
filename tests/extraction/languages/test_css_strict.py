"""css strict structural-signature coverage.

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

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
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


def test_css_at_rules_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["css"]["rules"]
    assert r["branch"].search("@media (max-width: 600px) {")
    assert r["branch"].search("@container (min-width: 400px) {")
    assert r["structural_boundaries"].search("@keyframes spin {")
    assert r["structural_boundaries"].search("@font-face {")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


def test_css_attribute_selectors_already_quote_agnostic():
    """
    Issue #735 explicitly asked whether css shares html's double-quote-only
    gap. It doesn't: css's only rules that touch attribute-selector syntax
    (`test`, `test_skip`) never parse a quoted value in the first place --
    `test`'s pattern stops right after the `=` (`[ \\t]*[=\\]]`), so it's
    already agnostic to whatever quoting (or lack of it) follows. Confirmed
    empirically here rather than left as an unstated assumption; no fix
    needed on the css side.
    """
    test_rule = CSS_RULES["test"]
    for snippet in (
        '[data-testid="submit"] { color: red; }',
        "[data-testid='submit'] { color: red; }",
        "[data-testid] { color: red; }",
    ):
        assert test_rule.search(snippet), f"css test rule should match regardless of quoting: {snippet!r}"


# ==============================================================================
# CSS: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #577, part of epic #518)
# ==============================================================================
# NOTE: `branch`/`structural_boundaries` already carry BUG FIX comments from
# an earlier cross-language sweep (the leading-\b-before-@ trap) -- not
# re-litigated here, just covered by the positive/negative table below like
# any other already-correct rule.
CSS_RULES = LANGUAGE_DEFINITIONS["css"]["rules"]

_CSS_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "@media (min-width: 768px) {", ".foo { color: red; }"),
    ("args", "width: calc(100% - 10px);", "width: 100%;"),
    ("structural_boundaries", "@keyframes spin {", ".foo {"),
    ("func_start", "@media (min-width: 768px) {", ".foo {"),
    ("class_start", ".my-class {", "body {"),
    ("safety", "@supports (display: grid) {", ".foo { color: red; }"),
    ("safety_bypasses", "* { box-sizing: border-box; }", ".foo { color: red; }"),
    ("high_risk_execution", "width: expression(body.scrollTop);", "width: 100%;"),
    ("api", ":root { --main-color: blue; }", ".foo { color: blue; }"),
    ("io", "background-image: url('hero.png');", "color: red;"),
    ("dead_code", "/* .old-class { display: none; } */", ".live-class { display: block; }"),
    ("doc", "/** @param --color The theme color */", "/* just a note */"),
    ("test", "[data-testid='submit'] { color: red; }", ".foo { color: red; }"),
    ("ui_framework", "display: flex; justify-content: center;", "color: red;"),
    ("closures", ".parent {\n  & .child {\n    color: red;\n  }\n}", ".parent { color: red; }"),
    ("globals", ":root { --x: 1; }", ".foo { --x: 1; }"),
    ("scientific", "width: sqrt(100px);", "width: 100px;"),
    ("reflection_metaprogramming", "&& &", ".foo { color: red; }"),
    ("import", "@import url('base.css');", ".foo {}"),
    ("ownership", "/* @author Jane Doe */", "/* just a note */"),
    ("planned_debt", "/* TODO: refactor this */", "/* done */"),
    ("fragile_debt", "/* HACK: workaround */", "/* clean */"),
    ("spec_exposure", "/* [SPEC-123] compliance tag */", "/* just a note */"),
    ("events", "@scroll-timeline my-timeline {", ".foo {}"),
    ("panics_and_aborts", "all: unset;", "all: inherit;"),
    ("thread_sleeps", "transition-delay: 200ms;", "transition-duration: 200ms;"),
    ("immutability_locks", "color: red !important;", "color: red;"),
    ("encapsulation", "::part(header) {", ".foo {}"),
    ("listeners", "animation-timeline: scroll();", ".foo {}"),
    ("test_skip", "[data-skip] { display: none; }", ".foo {}"),
    # --- DEEP / ADVERSARIAL CASES FOR HIGH-AMBIGUITY SIGNATURES ---
    ("branch", "  @mEdIa screen and (min-width: 900px) {", None),
    ("branch", ":is(.header, .footer) > p {", None),
    ("branch", "article:has(> img) {", None),
    ("branch", "div:not(:where(.not-me)) {", None),
    ("branch", "div:not(.foo) {", None),
    ("branch", "@starting-style { opacity: 0; }", None),
    ("branch", "@media print {", ".has-error { color: red; }"),
    ("args", "width: calc(100% - var(--x, calc(20px + 10%)));", "width: min-content;"),
    ("args", "background: color-mix(in srgb, var(--bg-color) 50%, white);", "--calc-value: 10px;"),
    ("args", "clamp(0.5rem, calc(1rem + 2vw), 1.5rem)", ".min-width-class { }"),
    ("args", "color: lch(from var(--color) l c h / calc(alpha * 0.8));", None),
    ("args", 'background: url("data:image/svg+xml;utf8,<svg...</svg>");', None),
    ("io", "  src: url(icomoon.woff2) format('woff2');", "@import url('base.css');"),
    ("io", "background: #fff url(/img/refresh.svg) 5px 3px no-repeat;", 'background: url("data:image/svg+xml,%3Csvg/%3E");'),
    ("io", "--icon-token: url('../img/logo.svg');", "--icon-token: url(\"data:image/png;base64,iVBOR\");"),
    ("io", "src: local('Open Sans'), local('OpenSans'), url('OpenSans.ttf') format('truetype');", "clip-path: url(#clip0);"),
    ("io", "cursor: url(grab.cur), pointer;", "mask-image: url( #mask );"),
    ("func_start", "@media screen and (min-width: 900px), \\n print {", "@import url('foo.css');"),
    ("func_start", "  @keyframes slide-in {", 'content: "@media";'),
    ("func_start", "@supports not (display: grid) {", None),
    ("func_start", "@layer utilities {", None),
    ("func_start", "@container (width > 400px) {", None),
    ("func_start", "  @media (min-width: 500px) {", None),
    ("class_start", ".\\32xl-text {", "body {"),
    ("class_start", "#main\\:content {", "10% {"),
    ("class_start", ".foo > .bar + .baz {", "* {"),
    ("class_start", ".multi, \\n .line \\n .selector {", None),
    ("class_start", "  .indented-class:hover::before {", None),
    ("structural_boundaries", "@layer framework, utilities;", ".layer-class {"),
    ("structural_boundaries", "@SCOPE (.card) to (.content) {", "--property: value;"),
    ("structural_boundaries", "@font-face {", None),
    ("structural_boundaries", "@property --my-color {", None),
    ("structural_boundaries", '@charset "UTF-8";', None),
    ("safety", "var(--color, rgba(0, 0, 0, 0.5))", None),
    ("safety", "clamp(min(1vw, 2vw), 10vw, 100px)", None),
    ("reflection_metaprogramming", ":has(div:where(.foo):not(.bar):has(a))", None),
    ("reflection_metaprogramming", "calc(min(1px, 2px) + calc(10%))", None),
]


@pytest.mark.parametrize("signature,positive,negative", _CSS_SIMPLE_CASES)
def test_css_signature_positive_and_negative(signature, positive, negative):
    pattern = CSS_RULES[signature]
    assert pattern is not None, f"css's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"css {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"css {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_css_class_start_and_func_start_capture_and_no_collision():
    class_start = CSS_RULES["class_start"]
    func_start = CSS_RULES["func_start"]

    m = class_start.search(".my-class {")
    assert m and m.group(1) == ".my-class"
    m2 = class_start.search("#my-id {")
    assert m2 and m2.group(1) == "#my-id"

    assert func_start.search("@media (min-width: 768px) {")
    assert not class_start.search("@media (min-width: 768px) {"), "class_start incorrectly matched an at-rule"
    assert not func_start.search(".my-class {"), "func_start incorrectly matched a class selector"


def test_css_dependency_capture_extracts_import_path():
    pattern = CSS_RULES["_dependency_capture"]
    m = pattern.search("@import url('base.css');")
    assert m and m.group(1) == "base.css"
    m2 = pattern.search('@import "theme.css";')
    assert m2 and m2.group(1) == "theme.css"


# ==============================================================================
# Issue #2752: css `io` was `None`; url() resource fetches were invisible
# ==============================================================================
# `io` was wired to None under the rationale that a `url()`/`@import` fetch
# "does not block a computational thread". html's own `io` rule counts
# `src=`/`href=`/`<img>`/`<iframe>` -- the same non-blocking, paint-time
# loads -- so blocking-ness is not what separates io from not-io; a resource
# boundary is. The three exclusions below are what the old caution actually
# bought, and each is pinned here.


def test_css_io_counts_resource_fetching_declarations():
    """The positive surface: a declaration whose value loads an external file."""
    io = CSS_RULES["io"]
    assert io is not None, "css io was re-wired to None; #2752 made it a rule"
    for positive in (
        "background-image: url('hero.png');",
        "background:#fff url(/img/refresh.svg) 5px 3px no-repeat;",
        "  src: url('icomoon.eot?h6xgdm#iefix') format('embedded-opentype');",
        "list-style-image: url(bullet.svg);",
        "border-image-source: url(../frame.png);",
        "--brand-logo: url('../img/logo.svg');",
        "background : url(spaced-colon.png);",
        "BACKGROUND-IMAGE: URL(UPPER.PNG);",
    ):
        assert io.search(positive), f"css io missed a real resource fetch: {positive!r}"


def test_css_io_does_not_re_count_the_import_already_counted_twice():
    """
    Exclusion 1 (keyword-rosetta ledger `css-import-url-io-triple-overlap`):
    `@import url("a.css")` already produces `args` + `import` +
    `_dependency_capture`. io is anchored on a declaration's `:`, and an
    at-rule prelude has none, so it stays at those hits rather than a fourth.
    """
    io = CSS_RULES["io"]
    for at_rule in (
        '@import url("a.css");',
        "@import url('base.css') layer(base);",
        '@import "theme.css";',
    ):
        assert not io.search(at_rule), f"css io double-counted an @import: {at_rule!r}"
        assert CSS_RULES["import"].search(at_rule), "sanity: import must still own the @import"

    # ... and `@` is excluded from the value span, so a preceding declaration's
    # colon cannot bridge forward into the at-rule prelude either.
    assert not io.search('color: red\n@import url("a.css")')


def test_css_io_excludes_data_uris_and_in_document_fragments():
    """
    Exclusions 2 and 3. A `data:` URI is an inline payload and a `url(#id)`
    is a same-document reference -- neither crosses an I/O boundary. 59 of
    language-crucible's 117 `url(` tokens are data URIs, so this is the
    majority construct, not an edge case.
    """
    io = CSS_RULES["io"]
    for inline in (
        'background-image: url("data:image/svg+xml,%3Csvg/%3E");',
        "--bs-form-switch-bg: url(data:image/svg+xml,%3csvg%3e);",
        'background: url("data:image/png;base64,iVBORw0KGgo=");',
        "clip-path: url(#clip0_6958);",
        "mask-image: url( '#mask' );",
        "filter: url(#blur);",
    ):
        assert not io.search(inline), f"css io hallucinated a fetch on an inline payload: {inline!r}"


def test_css_io_does_not_walk_into_an_inlined_svg_payload():
    """
    The trap the `%`/`<>` value-span exclusions exist for: a
    `data:image/svg+xml` value is an entire SVG document inlined as text,
    carrying its OWN `url(#...)` references and `xmlns='http:`-shaped
    colons. Without the guard, the scan resumes inside the payload and
    scores one "fetch" per embedded icon -- measured 70 hits instead of 14
    across language-crucible's css corpus, 50 of them from this one file
    shape. Both the percent-escaped and the raw inlining styles are covered.
    """
    io = CSS_RULES["io"]
    escaped = (
        "background-image: url(\"data:image/svg+xml,%3Csvg width='1000' fill='none' "
        "xmlns='http://www.w3.org/2000/svg'%3E%3Cg clip-path='url(%23clip0_6958)'%3E%3C/g%3E%3C/svg%3E\");"
    )
    raw = (
        "background-image: url('data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\">"
        "<g fill=\"url(#grad)\"/></svg>');"
    )
    assert not io.search(escaped), "css io walked into a percent-escaped SVG data URI"
    assert not io.search(raw), "css io walked into a raw SVG data URI"

    # the guard must not cost the fetch that follows one in the next declaration
    assert io.search(escaped + "\nbackground-image: url(../img/real.png);")


def test_css_io_property_anchor_is_a_lookbehind_not_a_match_redos_regression():
    """
    Rule 14 regression. Spelling the property anchor as a match --
    `[-a-zA-Z_][-\\w]*[ \\t]*:` -- puts an unbounded `[-\\w]*` adjacent to a
    required `:`, so every identifier character becomes a start position
    that backtracks the entire identifier run. Measured quadratic before
    the fix (1.3s / 5.5s / 13.5s / 54s at 10k / 20k / 40k / 80k chars); the
    fixed-width lookbehind the rule ships is linear on the same inputs.
    """
    quadratic = re.compile(r"[-a-zA-Z_][-\w]*[ \t]*:[^;{}@%<>]{0,200}?\burl\s*\(", re.I)
    small = "background:" + "a" * 4000
    large = "background:" + "a" * 8000
    small_duration = _best_of_timing(quadratic, small)
    large_duration = _best_of_timing(quadratic, large)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: the match-anchored spelling was expected to show quadratic (~4x) scaling "
        f"on a payload doubling, but only scaled {ratio:.2f}x "
        f"({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    assert_redos_immune(CSS_RULES["io"], "background:" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["io"], "background:" + "a" * 100000 + "url(data:x)", timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["io"], "x:" * 50000, timeout_sec=3.0)
    assert CSS_RULES["io"].search("background-image: url(real.png);")


def test_css_args_and_scientific_nested_call_regression():
    """
    Regression test for a real bug (Rule 11): `[^)]*` cannot represent even
    one level of nesting. Modern CSS math functions nest constantly
    (`calc(var(--x) + 1px)`, `round(var(--x), 1px)`) -- confirmed the old
    patterns truncated at the first *inner* `)` instead of the true closing
    one.
    """
    old_args = re.compile(
        r"\b(?:calc|clamp|min|max|var|env|url|rgba?|hsla?|lch|oklch|color-mix|light-dark)\s*\([^)]*\)", re.I
    )
    nested = "calc(var(--x) + 1px)"
    old_m = old_args.search(nested)
    assert old_m and old_m.group(0) != nested, "sanity check: old pattern must reproduce the truncation"

    args = CSS_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == nested, f"nested calc(var(...)) truncated: {m.group(0) if m else None!r}"

    old_sci = re.compile(
        r"\b(?:sin|cos|tan|asin|acos|atan|atan2|hypot|abs|sign|mod|rem|round|pow|sqrt|exp|log)\s*\([^)]*\)", re.I
    )
    nested_sci = "round(var(--x), 1px)"
    old_sci_m = old_sci.search(nested_sci)
    assert old_sci_m and old_sci_m.group(0) != nested_sci, "sanity check: old pattern must reproduce the truncation"

    scientific = CSS_RULES["scientific"]
    m2 = scientific.search(nested_sci)
    assert m2 and m2.group(0) == nested_sci, f"nested round(var(...)) truncated: {m2.group(0) if m2 else None!r}"

    # non-nested forms must still match cleanly
    assert args.search("calc(100% - 10px)").group(0) == "calc(100% - 10px)"
    assert scientific.search("sqrt(100px)").group(0) == "sqrt(100px)"


def test_css_args_and_scientific_nested_call_redos_immunity():
    assert_redos_immune(CSS_RULES["args"], "calc(" + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["scientific"], "sqrt(" + "(" * 20000, timeout_sec=3.0)
    assert CSS_RULES["args"].search("calc(100% - 10px)")


def test_css_class_start_lookahead_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `class_start`'s
    trailing lookahead had two adjacent quantifiers, `[ \\t,>+~:]*` then
    `[^{]*`, where the first's character set is a strict subset of the
    second's -- every character the first alternative can consume, the
    second can too, so on a long run of combinator/whitespace characters
    with no `{` ever appearing, the engine tries every possible split point
    between them before failing.

    Confirmed via direct scaling measurement against the OLD pattern before
    writing this test (payload: ".foo" + " ,>+~:" repeated n times, no "{"
    anywhere): n=500/1000/2000/4000 -> 0.0058s/0.0231s/0.0920s/0.3673s, a
    clean ~4x per doubling (the textbook O(n^2) signature). The fix simply
    drops the redundant first quantifier (`[^{]*` alone already matches
    everything it did) -- post-fix scaling at n=2000/8000/32000 is
    0.0001s/0.0004s/0.0016s, clean ~2x per doubling (linear).
    """
    old_pattern = re.compile(r"^[ \t]*(\.[a-zA-Z_][\w-]*|#[a-zA-Z_][\w-]*)(?=[ \t,>+~:]*[^{]*\{)", re.M)

    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed): a doubling of
    # payload size should cost ~4x on the quadratic OLD pattern, vs ~2x for
    # linear. This is the same discipline used everywhere else in this
    # epic's ReDoS scaling sweeps.
    small_duration = _best_of_timing(old_pattern, ".foo" + (" ,>+~:" * 1000))
    large_duration = _best_of_timing(old_pattern, ".foo" + (" ,>+~:" * 2000))
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    class_start = CSS_RULES["class_start"]
    assert_redos_immune(class_start, ".foo" + (" ,>+~:" * 200000), timeout_sec=3.0)
    assert class_start.search(".foo, .bar > .baz {")
    assert class_start.search(".foo > .bar {")


def test_css_spec_exposure_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the SPEC
    alternative's unbounded `\\d+` sits directly adjacent to the
    also-unbounded `[^\\]]*`, whose character class fully overlaps digits --
    classic adjacent-overlapping-quantifier shape (same bug class already
    found and fixed in embedded_python's independent copy of this pattern).
    Confirmed ~4x runtime per doubling on "[SPEC-" + digits with no closing
    bracket before writing this test; bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`.
    """
    old_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]|\bfigma\.com/file/", re.I)

    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed): a doubling of
    # payload size should cost ~4x on the quadratic OLD pattern, vs ~2x for
    # linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 16000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = CSS_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + "1" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


def test_css_dead_code_multi_char_selector_and_brace_spacing_regression():
    """
    Regression test for 2 real bugs sharing one root cause (a shared
    trailing `\\b` across mismatched alternative shapes):

    1. `\\.[a-zA-Z]`/`#[a-zA-Z]` matched exactly ONE letter after the
       dot/hash with no continuation quantifier -- a realistic
       multi-character class/id name (`.old-class`, `#old-id`) never
       matched at all, only ever a contrived single-letter name would.
    2. The `{`-ending tag-selector alternative shared that same trailing
       `\\b`. `{` is non-word, and the character immediately following a
       real opening brace is very commonly whitespace (`div { display:
       none; }`) -- also non-word -- so `\\b` between two non-word
       characters never fired; only the no-space form (`div{display`)
       ever matched.
    """
    old_pattern = re.compile(
        r"/\*[ \t]*(?:@media|@container|@supports|@keyframes|\.[a-zA-Z]|#[a-zA-Z]|[a-zA-Z][\w-]*[ \t]*{)\b",
        re.I,
    )
    assert not old_pattern.search("/* .old-class { */"), "sanity check: bug must reproduce for multi-letter class"
    assert not old_pattern.search("/* #old-id { */"), "sanity check: bug must reproduce for multi-letter id"
    assert not old_pattern.search("/* div { display:none; } */"), "sanity check: bug must reproduce for spaced brace"
    assert old_pattern.search("/* div{display:none;} */"), "sanity check: no-space form already worked"

    dead_code = CSS_RULES["dead_code"]
    assert dead_code.search("/* .old-class { */"), "multi-letter class still didn't match"
    assert dead_code.search("/* #old-id { */"), "multi-letter id still didn't match"
    assert dead_code.search("/* div { display:none; } */"), "spaced-brace tag selector still didn't match"
    assert dead_code.search("/* div{display:none;} */"), "no-space form regressed"
    assert dead_code.search("/* @media (min-width: 768px) { */"), "@-rule form regressed"
    assert not dead_code.search(".live-class { color: red; }"), "live, uncommented code incorrectly matched"


def test_css_safety_and_branch_supports_intentional_double_classification():
    """
    Ambiguity sweep: `safety` and `branch` both list `@supports\\b`.
    Confirmed genuine, intentional double-classification, not a bug: an
    `@supports` feature query is simultaneously a defensive fallback
    mechanism (safety) AND a conditional branch (branch) -- both readings
    are correct for the same construct.
    """
    safety = CSS_RULES["safety"]
    branch = CSS_RULES["branch"]
    supports_query = "@supports (display: grid) {"
    assert safety.search(supports_query)
    assert branch.search(supports_query)


def test_css_encapsulation_and_structural_boundaries_scope_intentional_double_classification():
    """
    Ambiguity sweep: `encapsulation` and `structural_boundaries` both list
    `@scope\\b`. Confirmed intentional: `@scope` is simultaneously a
    structural at-rule boundary AND an explicit encapsulation/scoping
    mechanism -- both readings are correct.
    """
    encapsulation = CSS_RULES["encapsulation"]
    structural_boundaries = CSS_RULES["structural_boundaries"]
    scope_rule = "@scope (.card) to (.content) {"
    assert encapsulation.search(scope_rule)
    assert structural_boundaries.search(scope_rule)


def test_css_lexical_family_dual_comment_style_dead_code_audit():
    """
    Comment-style audit (Rule 12): css's lexical_family is `standard_block`,
    which per the doc's family definition supports block comments (`/* */`)
    natively; SCSS/Less/Stylus preprocessors (all sharing this language
    entry via extensions .scss/.less/.styl) also commonly use `//`
    line comments. dead_code is only wired to `/* */` -- confirmed it does
    NOT fire on a `//`-commented-out selector, which is a real gap for the
    preprocessor dialects but consistent with `standard_block`'s baseline
    (line-comment support for SCSS/Less specifically isn't part of this
    issue's checklist; documented here rather than silently assumed clean).
    """
    dead_code = CSS_RULES["dead_code"]
    assert dead_code.search("/* .old-class { display: none; } */")
    assert not dead_code.search("// .old-class { display: none; }")


def test_css_redos_immunity_sweep():
    """
    ReDoS immunity sweep across css's remaining unbounded-quantifier rules
    not covered by the dedicated regression tests above. Each has a single
    quantified segment with no adjacent overlapping-charset quantifier to
    backtrack against.
    """
    assert_redos_immune(CSS_RULES["safety"], "clamp(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["api"], "::part(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["ownership"], "/* @author " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["globals"], ":root {" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["events"], "animation-timeline: scroll(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["_dependency_capture"], "@import url(" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert CSS_RULES["safety"].search("@supports (display: grid) {")
    assert CSS_RULES["api"].search(":root { --x: 1; }")
