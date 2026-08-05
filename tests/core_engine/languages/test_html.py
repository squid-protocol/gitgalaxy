"""html strict structural-signature coverage.

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


# ==============================================================================
# HTML: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #587, part of epic #518)
# ==============================================================================
# NOTE: html is currently tagged `lexical_family: "line_exclusive"`, which is
# wrong (it should be `block_exclusive`) -- filed separately as issue #733,
# not fixed here. Confirmed empirically that <!-- --> comments are NEVER
# stripped from code_stream for html today; the whole raw file (comments
# included) is what every rule below actually scans in a real run. Tests here
# are written against that real behavior, not an idealized stripped-comment
# one -- e.g. dead_code/macros search for the literal "<!--" prefix directly,
# which only works because comments survive unstripped.
HTML_RULES = LANGUAGE_DEFINITIONS["html"]["rules"]

_HTML_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", '<div v-if="cond">', '<div class="x">'),
    ("args", '<input data-foo="bar">', '<input type="text">'),
    ("structural_boundaries", "<div>", "<not-a-real-boundary-tag>"),
    ("func_start", "<script>", "<div>"),
    ("class_start", "<form>", "<div>"),
    ("safety", "<input required>", '<input type="text">'),
    ("safety_bypasses", 'href="javascript:alert(1)"', 'href="https://example.com"'),
    ("io", 'src="app.js"', "<div>plain text</div>"),
    ("api", 'id="main"', "<div>"),
    ("dead_code", '<!-- <div class="old"></div> -->', "<div>live content</div>"),
    ("doc", "<title>Page Title</title>", "<div>Page Title</div>"),
    ("test", 'data-testid="submit-btn"', 'id="submit-btn"'),
    ("concurrency", "<script async>", "<script>"),
    ("ui_framework", "<strong>bold</strong>", "<div>plain</div>"),
    ("closures", '<template shadowrootmode="open">', "<template>"),
    ("decorators", "<div hidden>", "<div>"),
    ("generics", "<slot></slot>", "<div></div>"),
    ("comprehensions", 'v-for="item in items"', "<div>"),
    ("scientific", "<svg></svg>", "<div></div>"),
    ("reflection_metaprogramming", 'onclick="doThing()"', "<div>"),
    ("import", '<script type="module">', "<script>"),
    ("ownership", '<meta name="author" content="Jane Doe">', '<meta name="viewport">'),
    ("planned_debt", "<!-- TODO: fix this -->", "<!-- done -->"),
    ("fragile_debt", "<!-- HACK: workaround -->", "<!-- clean -->"),
    ("spec_exposure", "<!-- [SPEC-123] compliance tag -->", "<!-- just a note -->"),
    ("ssr_boundaries", "<%= value %>", "<div></div>"),
    ("events", 'hx-trigger="click"', "<div></div>"),
    ("dependency_injection", '<script type="importmap">', "<script>"),
    ("macros", '<!--#include file="header.html" -->', "<!-- regular comment -->"),
    ("telemetry", '<script src="https://www.google-analytics.com/analytics.js">', '<script src="app.js">'),
    ("debug_prints", "console.log('debug')", "logger.info('ok')"),
    ("panics_and_aborts", "window.close()", "window.open()"),
    ("thread_sleeps", "setTimeout(fn, 1000)", "requestAnimationFrame(fn)"),
    ("immutability_locks", "<input readonly>", "<input>"),
    ("cleanup", "clearTimeout(t)", "setTimeout(fn, 0)"),
    ("encapsulation", "<template></template>", "<div></div>"),
    ("listeners", "addEventListener('click', fn)", "<div>no listener here</div>"),
    ("test_skip", "data-skip", "data-run"),
]


@pytest.mark.parametrize("signature,positive,negative", _HTML_SIMPLE_CASES)
def test_html_signature_positive_and_negative(signature, positive, negative):
    pattern = HTML_RULES[signature]
    assert pattern is not None, f"html's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"html {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"html {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_html_dependency_capture_extracts_src_and_href():
    pattern = HTML_RULES["_dependency_capture"]
    m = pattern.search('<script src="app.js"></script>')
    assert m and m.group(1) == "app.js"
    m2 = pattern.search('<link href="styles.css">')
    assert m2 and m2.group(1) == "styles.css"


def test_html_func_start_and_class_start_no_capture_group_expected():
    # func_start/class_start don't capture a name in html (unlike many
    # languages) -- they anchor on the tag keyword itself. Confirm the match
    # span is the tag, and that they don't collide with each other.
    func_start = HTML_RULES["func_start"]
    class_start = HTML_RULES["class_start"]
    assert func_start.search("<script>")
    assert not class_start.search("<script>"), "func_start's <script>/<style> incorrectly matched by class_start"
    assert class_start.search("<form>")
    assert not func_start.search("<form>"), "class_start's tags incorrectly matched by func_start"


def test_html_star_ngif_leading_boundary_regression():
    """
    Regression test for a real bug: `branch`'s `*ngIf` (Angular's structural
    directive) was inside the shared `\\b(...)"[^"]*"` group. `*` is a
    non-word character always preceded by whitespace in real markup
    (`<div *ngIf="cond">`) -- a `\\b` between two non-word characters can
    never fire, so `*ngIf` never matched at all. Same shape confirmed
    separately for `comprehensions`' `*ngFor` below.
    """
    old_pattern = re.compile(
        r'<(?:details|summary|noscript)\b|\b(?:v-if|ng-if|\*ngIf|x-if|hx-swap)="[^"]*"'
        r"|\{%\s*(?:if|elif|else|endif)\s*[^%]*%\}|\{\{#if\s+[^}]+\}\}",
        re.I,
    )
    realistic = '<div *ngIf="cond">'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    branch = HTML_RULES["branch"]
    assert branch.search(realistic), "*ngIf still didn't match"
    assert branch.search('<div v-if="cond">'), "v-if form regressed"


def test_html_star_ngfor_leading_boundary_regression():
    old_pattern = re.compile(
        r'\b(?:v-for|ng-repeat|\*ngFor|x-for)="[^"]*"|\{%\s*for\b[^%]*%\}|\{\{#each\b[^}]*\}\}',
        re.I,
    )
    realistic = '<li *ngFor="let item of items">'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    comprehensions = HTML_RULES["comprehensions"]
    assert comprehensions.search(realistic), "*ngFor still didn't match"
    assert comprehensions.search('<li v-for="item in items">'), "v-for form regressed"


def test_html_safety_quoted_attribute_trailing_boundary_regression():
    """
    Regression test for a real bug: `pattern="..."`, `sandbox="..."`,
    `rel="noopener..."`, and `integrity="..."` were all inside the shared
    `\\b(...)\\b` group. Each ends on a literal `"`, and the character
    immediately following a closing attribute quote (space or `>`) is also
    non-word -- `\\b` between two non-word characters can never fire, so
    none of the four quote-terminated alternatives ever matched; only the
    bare-word alternatives (required/readonly/disabled) worked.
    """
    old_pattern = re.compile(
        r'\b(?:required|readonly|disabled|pattern="[^"]*"|sandbox="[^"]*"|rel="noopener(?: noreferrer)?"'
        r'|integrity="[^"]*")\b|<meta\s+http-equiv="Content-Security-Policy"',
        re.I,
    )
    for snippet in (
        '<input pattern="[0-9]+">',
        '<iframe sandbox="allow-scripts">',
        '<a rel="noopener">',
        '<script integrity="sha384-abc">',
    ):
        assert not old_pattern.search(snippet), f"sanity check: bug must reproduce for {snippet!r}"

    safety = HTML_RULES["safety"]
    assert safety.search('<input pattern="[0-9]+">'), "pattern=... still didn't match"
    assert safety.search('<iframe sandbox="allow-scripts">'), "sandbox=... still didn't match"
    assert safety.search('<a rel="noopener">'), "rel=noopener still didn't match"
    assert safety.search('<a rel="noopener noreferrer">'), "rel=noopener noreferrer still didn't match"
    assert safety.search('<script integrity="sha384-abc">'), "integrity=... still didn't match"
    assert safety.search("<input required>"), "bare-word required regressed"
    assert not safety.search('<input type="text">'), "unrelated attribute incorrectly matched"


def test_html_concurrency_quoted_attribute_trailing_boundary_regression():
    """
    Same shared-`\\b`-after-quote trap as safety, in `concurrency`.
    `decoding="async"` happened to still match under the old pattern (a
    coincidental self-heal: "async" is also a standalone earlier
    alternative, and it appears as the *value* of decoding= too) -- but
    `loading="lazy"` and `fetchpriority="high"/"low"` have no such rescue and
    never matched at all.
    """
    old_pattern = re.compile(
        r'\b(?:async|defer|loading="lazy"|fetchpriority="(?:high|low)"|decoding="async")\b'
        r'|<link\s+rel="(?:preload|prefetch|preconnect|modulepreload|prerender)"',
        re.I,
    )
    assert not old_pattern.search('<img loading="lazy">'), "sanity check: bug must reproduce for loading=lazy"
    assert not old_pattern.search('<img fetchpriority="high">'), "sanity check: bug must reproduce for fetchpriority"
    assert old_pattern.search('<img decoding="async">'), "sanity check: decoding=async self-heals on old pattern too"

    concurrency = HTML_RULES["concurrency"]
    assert concurrency.search('<img loading="lazy">'), "loading=lazy still didn't match"
    assert concurrency.search('<img fetchpriority="high">'), "fetchpriority=high still didn't match"
    assert concurrency.search('<img fetchpriority="low">'), "fetchpriority=low still didn't match"
    assert concurrency.search("<script async>"), "bare-word async regressed"
    assert concurrency.search("<script defer>"), "bare-word defer regressed"


def test_html_decorators_bare_boolean_attribute_regression():
    """
    Regression test for a real bug: `hidden`/`inert` are true HTML boolean
    attributes, almost always written bare (`<div hidden>`) with no `=` at
    all -- the old pattern required `[ \\t]*=` unconditionally after every
    alternative in the group, so the dominant real-world bare form of these
    two never matched (only `hidden=""`/`hidden="until-found"` would have).
    Found while writing this test's own positive case, not pre-derived.
    """
    old_pattern = re.compile(
        r"\b(?:class|style|hidden|inert|tabindex|draggable|spellcheck|dir|lang|translate)[ \t]*="
        r'|hx-[a-z-]+="[^"]*"|x-[a-z-]+="[^"]*"|v-[a-z-]+="[^"]*"',
        re.I,
    )
    assert not old_pattern.search("<div hidden>"), "sanity check: bug must reproduce for bare hidden"
    assert not old_pattern.search("<div inert>"), "sanity check: bug must reproduce for bare inert"

    decorators = HTML_RULES["decorators"]
    assert decorators.search("<div hidden>"), "bare hidden still didn't match"
    assert decorators.search("<div inert>"), "bare inert still didn't match"
    assert decorators.search('<div hidden="until-found">'), "explicit-value hidden form regressed"
    assert decorators.search('<div class="x">'), "class=... (always requires a value) regressed"
    assert not decorators.search("<div class>"), (
        "bare class with no value incorrectly matched -- class always requires an explicit value in real markup"
    )


def test_html_dependency_injection_trailing_boundary_regression():
    """
    Regression test for a real bug: `<script\\s+type="importmap"\\b` had a
    trailing `\\b` right after the closing `"`. The character following a
    closing attribute quote (space or `>`) is non-word, same as `"` itself
    -- `\\b` between two non-word characters can never fire, so this rule
    never matched at all, regardless of input.
    """
    old_pattern = re.compile(r'<script\s+type="importmap"\b', re.I)
    assert not old_pattern.search('<script type="importmap">'), "sanity check: bug must reproduce"
    assert not old_pattern.search('<script type="importmap" src="x">'), "sanity check: bug must reproduce"

    dependency_injection = HTML_RULES["dependency_injection"]
    assert dependency_injection.search('<script type="importmap">'), "closing > form still didn't match"
    assert dependency_injection.search('<script type="importmap" src="x">'), (
        "trailing-attribute form still didn't match"
    )


def test_html_reflection_metaprogramming_style_semicolon_regression():
    """
    Regression test for a real bug: `style="[^"]*;"` required a literal
    trailing semicolon immediately before the closing quote. CSS allows
    omitting the last declaration's semicolon, and most real inline styles
    don't carry one -- neither a single declaration nor a multi-declaration
    style with no trailing `;` matched under the old pattern.
    """
    old_pattern = re.compile(r'style="[^"]*;"|\bon[a-z]+="[^"]*"', re.I)
    assert not old_pattern.search('<div style="color:red">'), "sanity check: bug must reproduce (no trailing ;)"
    assert not old_pattern.search('<div style="color:red;font-size:12px">'), (
        "sanity check: bug must reproduce (multi-declaration, no trailing ;)"
    )
    assert old_pattern.search('<div style="color:red;">'), "sanity check: trailing-; form already worked"

    reflection = HTML_RULES["reflection_metaprogramming"]
    assert reflection.search('<div style="color:red">'), "no-trailing-semicolon style still didn't match"
    assert reflection.search('<div style="color:red;font-size:12px">'), (
        "multi-declaration no-trailing-semicolon style still didn't match"
    )
    assert reflection.search('<div style="color:red;">'), "trailing-semicolon form regressed"
    assert reflection.search('<div onclick="doThing()">'), "on* event handler form regressed"


def test_html_immutability_locks_aria_disabled_trailing_boundary_regression():
    """
    Same shared-`\\b`-after-quote trap as safety/concurrency, in
    `immutability_locks`. `aria-disabled="true"` happened to still match
    under the old pattern via an accidental self-heal ("disabled" is a
    substring of "aria-disabled", and the bare `disabled` alternative's own
    `\\b` fires correctly on that embedded substring) -- meaning it matched
    regardless of whether the value was "true" or "false", which was never
    the intent. Pulled the alternative out so the match is for the right
    reason and confirm it still fires.
    """
    old_pattern = re.compile(r'\b(?:readonly|disabled|inert|aria-disabled="true")\b', re.I)
    assert old_pattern.search('<button aria-disabled="true">'), (
        "sanity check: old pattern self-heals via the embedded 'disabled' substring"
    )

    immutability_locks = HTML_RULES["immutability_locks"]
    assert immutability_locks.search('<button aria-disabled="true">'), "aria-disabled=true still didn't match"
    assert immutability_locks.search("<input readonly>"), "bare-word readonly regressed"


def test_html_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor-shaped lines fooling func_start, as seen in C++). html's
    func_start is scoped to `<script`/`<style` tags only; macros maps to
    SSI directive comments (`<!--#include ...-->`) -- structurally distinct
    token shapes (`<script`/`<style` vs `<!--#`), no realistic overlap.
    """
    func_start = HTML_RULES["func_start"]
    macros = HTML_RULES["macros"]

    ssi_directive = '<!--#include file="header.html" -->'
    assert macros.search(ssi_directive)
    assert not func_start.search(ssi_directive)

    script_tag = "<script>"
    assert func_start.search(script_tag)
    assert not macros.search(script_tag)


def test_html_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (deeply nested generic
    return types triggering catastrophic backtracking against func_start,
    as seen in C#). html's generics maps to `<slot>` tags; func_start maps
    to `<script`/`<style` -- distinct tag names, no overlap, and neither
    pattern has adjacent unbounded quantifiers for a nested-slot payload to
    exploit.
    """
    func_start = HTML_RULES["func_start"]
    generics = HTML_RULES["generics"]

    slot_tag = '<slot name="header"></slot>'
    assert generics.search(slot_tag)
    assert not func_start.search(slot_tag)

    assert_redos_immune(generics, "<slot " + 'a="b" ' * 20000, timeout_sec=3.0)


def test_html_dead_code_and_macros_rely_on_unstripped_comments():
    """
    Documents the interaction with issue #733 (html's lexical_family is
    mistagged, so <!-- --> comments are never actually stripped from
    code_stream -- confirmed via direct Prism.split_streams() execution).
    dead_code and macros both search for the literal "<!--" prefix directly
    against raw text, which is why they still function correctly today
    despite that pipeline bug -- they were evidently authored already
    assuming comments survive unstripped, not against an idealized
    stripped-comment code_stream. This test exists to make that dependency
    explicit rather than leaving it implicit.
    """
    dead_code = HTML_RULES["dead_code"]
    assert dead_code.search('<!-- <div class="old-widget"></div> -->')
    assert dead_code.search("<!--<script>legacy()</script>-->")
    assert not dead_code.search("<div>this is live, uncommented code</div>")

    macros = HTML_RULES["macros"]
    assert macros.search('<!--#include file="header.html" -->')
    assert not macros.search("<!-- a normal, non-SSI comment -->")


def test_html_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit (Rule per how_to_add_a_language.md): none of
    html's rules track open/close comment-block state themselves -- every
    keyword-presence rule matches via flat scanning. Confirms a stray
    closing `-->` with no matching opener doesn't fool any rule into a
    false structural match.
    """
    branch = HTML_RULES["branch"]
    stray_close = 'some text --> <div v-if="cond">'
    assert branch.search(stray_close), "branch should still see v-if regardless of the stray --> before it"


def test_html_redos_immunity_sweep():
    """
    ReDoS immunity sweep across html's unbounded-quantifier rules (mostly
    `[^"]*"`-delimited attribute values, each a single quantifier bounded
    by its own closing delimiter with no adjacent overlapping-charset
    quantifier to backtrack against). Verified via a systematic scaling
    sweep before writing this test (payload shapes: unterminated quotes,
    parens, angle brackets, template braces, hyphen-chains, dotted calls,
    at n=2000/8000/32000) -- nothing in html's rules exceeded 0.5s at
    n=32000 against any shape, confirming linear behavior throughout. This
    test locks that in with assert_redos_immune's subprocess-kill timeout.
    """
    assert_redos_immune(HTML_RULES["args"], '<input data-foo="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["safety"], '<input pattern="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["io"], 'src="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["api"], 'id="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["ui_framework"], 'class="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["decorators"], 'hx-foo="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["comprehensions"], "{% for " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["scientific"], 'd="' + "M" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["reflection_metaprogramming"], 'style="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["ssr_boundaries"], "{{ " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["events"], '@click="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["spec_exposure"], "[SPEC-123 " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["class_start"], "<" + ("a-" * 20000), timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["_dependency_capture"], "<script " + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert HTML_RULES["args"].search('<input data-foo="bar">')
    assert HTML_RULES["safety"].search("<input required>")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


_HTML_SINGLE_QUOTE_TARGETS = [
    # (rule_name, single-quoted snippet, double-quoted snippet)
    ("branch", "<div v-if='cond'>", '<div v-if="cond">'),
    ("args", "<input data-foo='bar'>", '<input data-foo="bar">'),
    ("safety", "<input pattern='[0-9]+'>", '<input pattern="[0-9]+">'),
    ("safety_bypasses", "<a target='_blank'>", '<a target="_blank">'),
    ("io", "<img src='x.png'>", '<img src="x.png">'),
    ("api", "<div id='main'>", '<div id="main">'),
    ("doc", "<meta name='description' content='hi'>", '<meta name="description" content="hi">'),
    ("concurrency", "<img loading='lazy'>", '<img loading="lazy">'),
    ("ui_framework", "<div class='flex'>", '<div class="flex">'),
    ("closures", "<template shadowrootmode='open'>", '<template shadowrootmode="open">'),
    ("decorators", "<div hx-get='/x'>", '<div hx-get="/x">'),
    ("reflection_metaprogramming", "<div style='color:red'>", '<div style="color:red">'),
    ("import", "<script type='module'>", '<script type="module">'),
    ("ownership", "<meta name='author' content='Jane Doe'>", '<meta name="author" content="Jane Doe">'),
    ("ssr_boundaries", "<div data-reactroot='true'>", '<div data-reactroot="true">'),
    ("events", "<div hx-trigger='click'>", '<div hx-trigger="click">'),
    ("dependency_injection", "<script type='importmap'>", '<script type="importmap">'),
    ("telemetry", "<script src='gtag.js'>", '<script src="gtag.js">'),
    ("immutability_locks", "<input aria-disabled='true'>", '<input aria-disabled="true">'),
    ("comprehensions", "<li v-for='x in y'>", '<li v-for="x in y">'),
]

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


@pytest.mark.parametrize("signature,single_quoted,double_quoted", _HTML_SINGLE_QUOTE_TARGETS)
def test_html_single_quoted_attribute_values_regression(signature, single_quoted, double_quoted):
    """
    Regression test for issue #735: every one of these 20 rules originally
    hard-coded a literal `"..."` delimiter around attribute values
    (`"[^"]*"`). Real-world markup legally uses single quotes for attribute
    values (`<div class='flex'>`) just as often, and none of these rules
    recognized that form at all. Fixed by widening each to the
    `["'][^"']*["']` idiom already used elsewhere in this file
    (`_dependency_capture`) -- a quote-character-class for the delimiters
    plus a content class excluding both quote characters, rather than an
    alternation -- so there's no added unbounded quantifier and thus no new
    ReDoS surface.
    """
    pattern = HTML_RULES[signature]
    assert pattern is not None, f"html's {signature!r} rule is unexpectedly None"
    assert pattern.search(single_quoted), f"html {signature!r} still didn't match the single-quoted form"
    assert pattern.search(double_quoted), f"html {signature!r} regressed on the double-quoted form"


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


def test_html_single_quote_bug_reproduces_on_old_double_quote_only_patterns():
    """
    Sanity check that the bug fixed above was real: reconstruct two of the
    original double-quote-only patterns and confirm they genuinely failed
    to match single-quoted markup before the fix.
    """
    old_branch = re.compile(
        r'<(?:details|summary|noscript)\b|\b(?:v-if|ng-if|x-if|hx-swap)="[^"]*"'
        r'|\*ngIf="[^"]*"|\{%\s*(?:if|elif|else|endif)\s*[^%]*%\}|\{\{#if\s+[^}]+\}\}',
        re.I,
    )
    assert not old_branch.search("<div v-if='cond'>"), "sanity check: bug must reproduce on old branch pattern"

    old_ui_framework = re.compile(
        r"<(?:b|i|u|strong|em|mark|small|del|ins|sub|sup)\b"
        r'|\bclass="[^"]*(?:flex|grid|absolute|relative|block|inline-block|container|row|col-[0-9]+'
        r'|justify-center|items-center|w-full|h-full)[^"]*"',
        re.I,
    )
    assert not old_ui_framework.search("<div class='flex'>"), (
        "sanity check: bug must reproduce on old ui_framework pattern"
    )

    branch = HTML_RULES["branch"]
    ui_framework = HTML_RULES["ui_framework"]
    assert branch.search("<div v-if='cond'>")
    assert ui_framework.search("<div class='flex'>")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


def test_html_ownership_single_quoted_capture_group_preserved():
    """
    `ownership` is the one rule in this sweep with a capture group
    (`content="..."` captured via `([^"]+)`). Confirm the fix preserved a
    single group (not duplicated per quote style) and that it captures
    correctly under both quote forms.
    """
    ownership = HTML_RULES["ownership"]
    m_double = ownership.search('<meta name="author" content="Jane Doe">')
    m_single = ownership.search("<meta name='author' content='Jane Doe'>")
    assert m_double and m_double.group(1) == "Jane Doe"
    assert m_single and m_single.group(1) == "Jane Doe"


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# Issue #735: html attribute-value rules assumed double-quoted attributes only
# ==============================================================================


def test_html_single_quote_fix_does_not_introduce_redos():
    """
    Widening `[^"]*` to `[^"']*` adds one more excluded character to an
    existing single quantifier -- it doesn't add a quantifier or change the
    adjacency shape, so ReDoS immunity should be unaffected. Confirmed via a
    scaling sweep (n=2000/4000/8000, unterminated single-quoted payloads)
    before writing this test: linear growth throughout, same as the
    double-quote form already covered by test_html_redos_immunity_sweep.
    """
    assert_redos_immune(HTML_RULES["ui_framework"], "<div class='" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["args"], "<input data-foo='" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["telemetry"], "<script src='" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["ownership"], "<meta name='author' content='" + "a" * 100000, timeout_sec=3.0)
