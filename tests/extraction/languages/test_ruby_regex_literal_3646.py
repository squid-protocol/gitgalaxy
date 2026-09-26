"""
#3646: a ruby `/.../` regex literal is a literal. The shield never blanked one, so a keyword
inside it -- `/<p\\s+class="footnote"/`, `x =~ /if|do/` -- opened a Mode-D scope that no `end`
closed. rails' `generator.rb` `extract_anchors` ran to EOF and took the next method's calls.
`_apply_literal_shield` now blanks a regex opened in value position; division never is one.

Two more shapes ran a method to EOF the same way (brew's download_strategy.rb), fixed with it:
- prism cut a line at the `#{` inside `%r{^https?://#{DOMAIN}/}o`, taking it for a comment; the
  stranded `"` after it opened a multi-line string. Ruby's `#` delimiter now skips `#{`.
- `@module = T.let(` counted `module` as a scope opener. `@`/`$` variables are names, never keywords.
"""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.galaxyscope import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _extractor() -> StructuralExtractor:
    return StructuralExtractor("ruby", LANGUAGE_DEFINITIONS)


def _shield(text: str) -> str:
    return _extractor()._apply_literal_shield(text, "ruby")


_RAILS_SHAPE = (
    "class Generator\n"
    "  def extract_anchors(html)\n"
    "    anchors = Set.new\n"
    '    anchors += Set.new(html.scan(/<p\\s+class="footnote"\\s+id="([^"]+)/).flatten)\n'
    '    anchors += Set.new(html.scan(/<sup\\s+class="footnote"\\s+id="([^"]+)/).flatten)\n'
    "    anchors\n"
    "  end\n"
    "\n"
    "  def check_fragment_identifiers(html, anchors)\n"
    "    guess = checker.correct(html).first\n"
    "    unescape(guess)\n"
    "  end\n"
    "end\n"
)


def test_keyword_inside_a_regex_no_longer_runs_the_method_to_eof():
    funcs = {f["name"]: f for f in _extractor().splice(_RAILS_SHAPE, "")["functions"]}
    anchors = funcs["extract_anchors"]
    assert (anchors["start_line"], anchors["end_line"]) == (2, 7)
    assert anchors["calls_out_to"] == ["new", "scan", "flatten"]
    assert funcs["check_fragment_identifiers"]["calls_out_to"] == ["correct", "first", "unescape"]


@pytest.mark.parametrize(
    "text, shielded",
    [
        ('s += S.new(h.scan(/<p\\s+class="f"/).flatten)', 's += S.new(h.scan("").flatten)'),
        ("x =~ /if|while|do/", 'x =~ ""'),
        ("when /class (\\w+)/ then go", 'when "" then go'),
        ("r = cond ? /a/ : /b/", 'r = cond ? "" : ""'),
        ("x = /[a/b]+/i if y", 'x = "" if y'),  # `/` inside a character class
        ('v = x.gsub(/#{pat}/, "")', 'v = x.gsub("", "")'),
        ("h[/re/]", 'h[""]'),
        ("return /end/ unless x", 'return "" unless x'),
    ],
)
def test_regex_in_value_position_is_blanked(text, shielded):
    assert _shield(text) == shielded


@pytest.mark.parametrize(
    "text",
    [
        "a = b / c / d",
        "total/2 + x/3",
        "xs.map { |p| p / 2 }",
        "p [1,2].reduce(:/)",
    ],
)
def test_division_is_not_a_regex(text):
    assert _shield(text) == text


def test_regex_inside_a_string_or_comment_is_left_to_that_literal():
    assert _shield('puts "a /if/ b" # x =~ /do/') == 'puts "" '


@pytest.mark.parametrize(
    "payload",
    [
        "x = /" + "[" * 50000,
        "x = /" + "\\" * 100000,
        "(" * 100000,
        "x = /[" + "a" * 100000,
        "x =~ /" + "a" * 100000,
        "x = /" + "[a" * 50000,
        ("x = /a" + "\\\\" + "\n") * 20000,
    ],
)
def test_ruby_regex_shield_is_linear(payload):
    # The regex alternative runs inside the whole shield pass; time that pass directly.
    start = time.perf_counter()
    _shield(payload)
    assert time.perf_counter() - start < 3.0


def _scan(code: str) -> dict[str, dict]:
    # prism first, as a scan runs it: the `#{` bug lived there, not in the detector
    refraction = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(code, "ruby")
    functions = _extractor().splice(refraction["code_stream"], refraction["comment_stream"], raw_content=code)
    return {f["name"]: f for f in functions["functions"]}


def test_interpolation_in_a_percent_regex_is_not_a_comment():
    code = (
        "class D\n"
        "  def fetch(url, domain)\n"
        '    url = url.sub(%r{^https?://#{DOMAIN}/}o, "#{domain.chomp("/")}/")\n'
        "    go(url) if url\n"
        "  end\n"
        "\n"
        "  def size\n"
        "    measure(1)\n"
        "  end\n"
        "end\n"
    )
    funcs = _scan(code)
    assert (funcs["fetch"]["start_line"], funcs["fetch"]["end_line"]) == (2, 5)
    assert funcs["size"]["calls_out_to"] == ["measure"]


def test_real_hash_comment_is_still_a_comment():
    refraction = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams('x = "#{a}" # note\n', "ruby")
    assert refraction["code_stream"] == 'x = "#{a}" \n'


@pytest.mark.parametrize("sigil", ["@", "$"])
def test_keyword_named_variable_is_not_a_scope(sigil):
    code = (
        "class S\n"
        "  def initialize(meta)\n"
        f"    {sigil}module = T.let(meta, String)\n"
        f"    {sigil}end = 1\n"
        "  end\n"
        "\n"
        "  def env\n"
        "    build(1)\n"
        "  end\n"
        "end\n"
    )
    funcs = _scan(code)
    assert (funcs["initialize"]["start_line"], funcs["initialize"]["end_line"]) == (2, 5)
    assert funcs["env"]["calls_out_to"] == ["build"]
