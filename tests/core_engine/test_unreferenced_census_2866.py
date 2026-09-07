# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The undefined family resolved (#2866): the census's last six languages.

#2806 stated the `unreferenced_by_name` contract and deferred one population --
css, dockerfile, html, markdown, sqlite, yaml, all reading 0.00 against a 2.50
corpus median because nothing extracted for them carried a real name. #2866
resolves each one against the existing corollaries rather than adding new ones:

- **css is censused** (corollary 3's recurrence test, over real names): a
  `@keyframes` block is the one css unit the language reaches BY NAME
  (`animation-name: slide` / `animation: slide 2s`), so its custom-ident is
  captured as the unit name. The other at-rules stay keyword buckets,
  excluded by derivation (#2728).
- **dockerfile, sqlite, yaml, html join jcl's positional family** (corollary
  4): instructions, statements, steps and script/style elements execute in
  written order, and no syntax reaches an extracted unit by its extracted
  name. The membership literal and its gate live in
  `test_unreferenced_by_name_contract_2806.py::POSITIONAL_LANGUAGES`.
- **markdown records nothing** -- no `func_start` rule, no population; its
  cell goes n/a by rule absence (the #2795 inference), report-side.

Same cross-language-table shape as the other contract modules: a language that
disagrees is a row, not a missing file.
"""

from __future__ import annotations

from gitgalaxy.core.detector import INVOCATION_POSITIONAL, StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from tests.extraction.languages._strict_harness import assert_redos_immune


def _splice(lang: str, code: str) -> dict:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")


def _census(lang: str, code: str) -> int:
    return _splice(lang, code)["equations"].get("unreferenced_by_name", 0)


# --- css: the one member measured INTO the census -----------------------------


def test_css_lonely_keyframes_is_one_hit():
    """A @keyframes nothing animates is the construct this census exists for.

    Tailwind's theme.css carries four of these (referenced only through
    `--animate-*` custom-property VALUES, whose name recurrence corollary 3
    counts -- so the real file reads 0; strip the recurrence and it must not).
    """
    lonely = "@keyframes lonely-frames { from { opacity: 0; } }\n"
    assert _census("css", lonely) == 1


def test_css_animation_reference_clears_the_flag():
    used = "@keyframes used-frames { to { opacity: 1; } }\n.x { animation: used-frames 1s ease-in; }\n"
    assert _census("css", used) == 0

    by_longhand = "@keyframes fade-in { to { opacity: 1; } }\n.y { animation-name: fade-in; }\n"
    assert _census("css", by_longhand) == 0


def test_css_webkit_prefixed_keyframes_is_the_same_unit():
    assert _census("css", "@-webkit-keyframes spin { to { transform: rotate(1turn); } }\n") == 1


def test_css_keyword_at_rules_stay_out_of_the_census():
    """@media/@supports/@container/@layer are keyword buckets (#2728), not names.

    Before #2866 the whole rule was one literal alternation and `keyframes`
    itself was such a bucket; the split must not let the remaining four leak
    into the census the way html's embedded `media` bucket did.
    """
    buckets = (
        "@media (min-width: 600px) { body { color: red; } }\n"
        "@supports (display: grid) { main { display: grid; } }\n"
        "@container (min-width: 1px) { .c { color: blue; } }\n"
        "@layer base { p { margin: 0; } }\n"
    )
    assert _census("css", buckets) == 0


def test_css_mixed_file_counts_only_the_lonely_named_units():
    """The corpus main.css shape: buckets + one referenced + one lonely name."""
    mixed = (
        "@keyframes probe-dispatch { from { opacity: 0; } }\n"
        "@keyframes probe-io { to { opacity: 1; } }\n"
        "@media (min-width: 1px) { .m { color: red; } }\n"
        ".rosetta { animation: probe-io 1s; }\n"
    )
    assert _census("css", mixed) == 1


def test_css_nameless_keyframes_is_not_a_unit():
    """`@keyframes {` is invalid CSS; it stops matching rather than bucketing."""
    assert _census("css", "@keyframes { from { opacity: 0; } }\n") == 0
    assert _splice("css", "@keyframes { from { opacity: 0; } }\n")["functions"] == []


# --- the positional four: real-shaped files, census structurally absent -------

# Each snippet DOES carry a lonely name a by-name census would flag; the
# declaration is what keeps it out, not an accident of the plant.
POSITIONAL_CASES = {
    "dockerfile": ("FROM alpine AS builder\nRUN echo build\nHEALTHCHECK CMD curl -f http://localhost/ || exit 1\n"),
    "sqlite": ("CREATE INDEX lonely_idx ON t (col);\nSELECT col FROM t WHERE col > 0;\n"),
    "yaml": ("jobs:\n  build:\n    steps:\n      - name: lonely step\n        run: echo hi\n      - run: echo bye\n"),
    "html": (
        "<html><head><style>\n"
        "@media (min-width: 600px) { body { color: red; } }\n"
        "</style></head><body>\n"
        "<script>\nfunction orphanJs() { return 2; }\n</script>\n"
        "</body></html>\n"
    ),
}


def test_positional_languages_never_record_a_census():
    for lang, code in POSITIONAL_CASES.items():
        assert LANGUAGE_DEFINITIONS[lang].get("invocation_model") == INVOCATION_POSITIONAL, lang
        assert _census(lang, code) == 0, f"{lang} recorded a census despite declaring positional"


def test_html_embedded_media_bucket_cannot_read_unreferenced():
    """The measured leak (#2866): cpython_jinja/layout.html read 1.

    An embedded-css `@media` bucket inside `<style>` carried a name the HOST
    language's keyword-bucket exclusion cannot know (it derives from html's own
    `func_start` literals, script|style). Ten crucible html files carried the
    phantom; the positional declaration is what zeroes it, so this pin is on
    the html file shape specifically.
    """
    style_only = "<style>\n@media (min-width: 600px) { body { color: red; } }\n</style>\n"
    assert _census("html", style_only) == 0


# --- markdown: no population, nothing to declare ------------------------------


def test_markdown_extracts_no_censusable_population():
    doc = "# Title\n\nSome prose.\n\n```python\ndef f():\n    pass\n```\n\n[ref]: https://example.com\n"
    assert _splice("markdown", doc)["functions"] == []
    assert _census("markdown", doc) == 0


# --- the new css alternation cannot detonate ----------------------------------


def test_css_func_start_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["css"]["rules"]["func_start"]
    payloads = [
        "@keyframes " + "a-" * 5000 + "\n",
        "@keyframes name " + "x" * 20000,  # no `{` ever arrives
        ("@media " + "(" * 2000) + "\n@keyframes t {",
        ("  @keyframes  n {\n" * 2000),
    ]
    for payload in payloads:
        assert_redos_immune(pattern, payload)
