"""SOP-002-v1 gap-cell decoy suite for PHP (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers ONLY the two php code-stream families that had a rule but no decoy row: `api` and `telemetry`,
through the real Prism.split_streams() + StructuralExtractor.splice() pipeline.
PHP comment forms exercised: `//`, `#`, `/* */`, `/** */` (and `?>` ending a `//` line comment).
PHP block comments do NOT nest, so `/* a /* b */ S */` leaves S as code (asserted as a positive control).
Text outside `<?php ... ?>` is HTML output, not code: the engine counts it today (xfail, filed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("php", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"

_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"
_HASH_COMMENT = _ISSUES + "9443"
_INLINE_HTML = _ISSUES + "9444"
_OPENER_LINE = _ISSUES + "9445"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "php")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


def _php(body: str) -> str:
    """A file whose first line is the bare opening tag, then `body` as PHP code."""
    return "<?php\n" + body


PHP_FAMILIES: dict[str, str] = {
    "api": "public function run(): void {}",
    "telemetry": 'Log::info("user created");',
}
_ATTRIBUTE = '#[Route("/users")]'  # the second `api` alternative
_SNIPPETS = {"api": PHP_FAMILIES["api"], "api_attribute": _ATTRIBUTE, "telemetry": PHP_FAMILIES["telemetry"]}
_FAMILY_OF = {"api": "api", "api_attribute": "api", "telemetry": "telemetry"}


def test_php_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    allowed = (defined["php"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(PHP_FAMILIES) <= allowed


def test_php_baseline_has_a_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["php"]
    for fam in PHP_FAMILIES:
        assert rows[fam]["protocol"] == "SOP-002-v1", fam
        assert rows[fam]["corpus"] == "decoy-spec", fam


@pytest.mark.parametrize("key", sorted(_SNIPPETS))
def test_php_g1_positive_control(key: str):
    assert _hits(_FAMILY_OF[key], _php(_SNIPPETS[key] + "\n")) >= 1


# --- Req A: PHP comment forms --------------------------------------------------------------------------------
_COMMENT_FORMS: list[tuple[str, str]] = [
    ("line_slashes", "// {S}\n"),
    ("block", "/* {S} */\n"),
    ("docblock", "/** {S} */\n"),
    ("block_multiline", "/*\n{S}\n*/\n"),
    ("docblock_multiline_tag", "/**\n * @return {S}\n */\n"),
    ("inline_trailing_line", "$x = 1; // {S}\n"),
    ("inline_trailing_block", "$x = 1; /* {S} */\n"),
    ("inline_between_tokens", "$x = /* {S} */ 1;\n"),
    ("string_then_line", '$u = "http://x"; // {S}\n'),
    ("single_quoted_string_then_line", "$u = 'http://x'; // {S}\n"),
    ("string_then_block", '$u = "http://x"; /* {S} */\n'),
    ("string_escaped_quote_then_line", '$u = "a \\" b"; // {S}\n'),
    # `?>` ends a // comment AND PHP mode: what follows is output text, so S is not code either way
    ("line_comment_closed_by_tag", "// note ?> {S}\n"),
    ("one_line_tag_block", "<?php // x ?>\n<?php // {S} ?>\n"),
    ("heredoc_body", "$s = <<<EOT\n{S}\nEOT;\n"),
    ("nowdoc_body", "$s = <<<'EOT'\n{S}\nEOT;\n"),
]


@pytest.mark.parametrize(("form", "template"), _COMMENT_FORMS, ids=[f for f, _ in _COMMENT_FORMS])
@pytest.mark.parametrize("key", sorted(_SNIPPETS))
def test_php_comment_forms_do_not_count(key: str, form: str, template: str):
    src = template.format(S=_SNIPPETS[key])
    if not src.startswith("<?php"):
        src = _php(src)
    assert _hits(_FAMILY_OF[key], src) == 0, f"php.{key} leaks in {form}"


# `#` is a PHP line comment. The engine does not strip it today.
_HASH_FORMS: list[tuple[str, str]] = [
    ("hash_line", "# {S}\n"),
    ("hash_inline_trailing", "$x = 1; # {S}\n"),
    ("hash_after_string", '$u = "http://x"; # {S}\n'),
]


@pytest.mark.parametrize(("form", "template"), _HASH_FORMS, ids=[f for f, _ in _HASH_FORMS])
@pytest.mark.parametrize("key", ["api", "telemetry"])
@pytest.mark.xfail(strict=True, reason=_HASH_COMMENT)
def test_php_hash_line_comment_does_not_count(key: str, form: str, template: str):
    assert _hits(_FAMILY_OF[key], _php(template.format(S=_SNIPPETS[key]))) == 0


def test_php_hash_bracket_is_an_attribute_not_a_comment():
    """`#[` is an attribute (PHP 8), not a comment: the attribute fires `api`."""
    assert _hits("api", _php(_ATTRIBUTE + "\nfunction f() {}\n")) >= 1


@pytest.mark.parametrize("key", ["api_attribute"])
@pytest.mark.xfail(strict=True, reason=_HASH_COMMENT)
def test_php_commented_out_attribute_after_hash(key: str):
    assert _hits("api", _php("# " + _ATTRIBUTE + "\n")) == 0


# A comment on the opening-tag line of line 1.
@pytest.mark.parametrize("key", sorted(_SNIPPETS))
@pytest.mark.parametrize("template", ["<?php // {S}\n", "<?php /* {S} */\n"], ids=["line", "block"])
@pytest.mark.xfail(strict=True, reason=_OPENER_LINE)
def test_php_comment_on_the_opening_tag_line(key: str, template: str):
    assert _hits(_FAMILY_OF[key], template.format(S=_SNIPPETS[key])) == 0


# Text outside the tags is output, not code.
@pytest.mark.parametrize("key", sorted(_SNIPPETS))
@pytest.mark.xfail(strict=True, reason=_INLINE_HTML)
def test_php_inline_html_is_not_code(key: str):
    assert _hits(_FAMILY_OF[key], f"<p>{_SNIPPETS[key]}</p>\n<?php $x = 1; ?>\n") == 0


# Look-alikes that are NOT comments: the snippet is code.
_NOT_A_COMMENT: list[tuple[str, str]] = [
    # PHP block comments do not nest: the first `*/` ends the comment.
    ("block_does_not_nest", "/* a /* b */\n{S}\n"),
    ("tag_inside_block_comment", "/* ?> */ {S}\n"),
    ("hash_inside_block_comment", "/* # */ {S}\n"),
    ("block_marker_inside_line_comment", "// /* \n{S}\n"),
    ("block_marker_in_string", '$s = "/*"; {S}\n'),
]


@pytest.mark.parametrize(("form", "template"), _NOT_A_COMMENT, ids=[f for f, _ in _NOT_A_COMMENT])
@pytest.mark.parametrize("key", sorted(_SNIPPETS))
def test_php_comment_lookalikes_do_not_hide_code(key: str, form: str, template: str):
    assert _hits(_FAMILY_OF[key], _php(template.format(S=_SNIPPETS[key]))) >= 1, f"hidden by {form}"


def test_php_a_backslash_does_not_continue_a_line_comment():
    """Unlike C++, a trailing backslash does not extend a PHP `//` comment: the next line is code."""
    assert _hits("telemetry", _php('// note \\\nLog::info("x");\n')) >= 1


# --- G6: keyword inside a string / heredoc ------------------------------------------------------------------
def test_php_quoted_string_content_counts_by_design_heredoc_does_not():
    """#2535: quoted strings count today. Heredoc and nowdoc bodies are blanked, so they do not."""
    assert _hits("telemetry", _php('$s = "Log::info(x)";\n')) >= 1
    assert _hits("telemetry", _php("$s = 'Log::info(x)';\n")) >= 1
    assert _hits("api", _php('$s = "public function run() {}";\n')) >= 1
    assert _hits("telemetry", _php('$s = <<<EOT\nLog::info("x");\nEOT;\n')) == 0
    assert _hits("api", _php("$s = <<<'EOT'\npublic function run() {}\nEOT;\n")) == 0


# --- Req B: every literal alternation branch -------------------------------------------------------------------
_API_MEMBERS = [
    "public function run() {}",
    "public static function run() {}",
    "public final function run() {}",
    "public abstract function run();",
    "public const LIMIT = 1;",
    "public $count = 0;",
    "public static $shared;",
    "public ?string $name;",
    "public int $id;",
]


@pytest.mark.parametrize("member", _API_MEMBERS)
def test_php_api_public_member_branch(member: str):
    assert _hits("api", _php(member + "\n")) >= 1
    assert _hits("api", _php("my_" + member + "\n")) == 0
    assert _hits("api", _php("x" + member + "\n")) == 0


def test_php_api_public_requires_a_member_declaration_not_the_bare_word():
    for src in ("public\n", "public_function run() {}\n", "public functions run() {}\n", "public constant X\n"):
        assert _hits("api", _php(src)) == 0, src
    for src in ("private function run() {}\n", "protected function run() {}\n", "function run() {}\n"):
        assert _hits("api", _php(src)) == 0, src


@pytest.mark.parametrize("attr", ["ApiResource", "Route", "Get", "Post", "Put", "Delete", "Patch"])
def test_php_api_attribute_branches(attr: str):
    assert _hits("api", _php(f'#[{attr}("/x")]\n')) >= 1
    assert _hits("api", _php(f'#[My{attr}("/x")]\n')) == 0  # name prefix


@pytest.mark.parametrize("attr", ["Get", "Post", "Put", "Delete", "Patch", "Route", "ApiResource"])
def test_php_api_attribute_name_boundary(attr: str):
    """An attribute named `<Branch>Something` is a different attribute (no boundary after the name)."""
    assert _hits("api", _php(f"#[{attr}Helper]\n")) == 0


@pytest.mark.parametrize(
    "src",
    [
        'Log::info("x");',
        'Log::debug("x");',
        'Log::notice("x");',
        'Log::critical("x");',
        'Log::alert("x");',
        'Log::emergency("x");',
        'Log::error("x");',
        'Log::warning("x");',
    ],
)
def test_php_telemetry_log_facade_with_every_severity(src: str):
    assert _hits("telemetry", _php(src + "\n")) >= 1


@pytest.mark.parametrize(
    "decoy",
    [
        'MyLog::info("x");',  # Log:: branch with identifier prefix
        'my_Log::info("x");',
        "function f(MyLoggerInterface $l) { }",  # LoggerInterface branch with prefix
        'new MyMonolog\\Handler(); $l->error("x");',  # Monolog\ branch with prefix
        'use MyPsr\\Log\\X; $l->debug("x");',  # Psr\Log branch with prefix
        'my_error_log("an error");',  # error_log branch with prefix
        'myerror_log("an error");',
        'Log::infoX("x");',  # severity is a longer word
        'Log::information("x");',
    ],
)
def test_php_telemetry_branch_boundaries(decoy: str):
    assert _hits("telemetry", _php(decoy + "\n")) == 0


@pytest.mark.parametrize("src", ['my_logger()->info("x");', 'mylogger()->info("x");'])
def test_php_telemetry_logger_call_boundary(src: str):
    assert _hits("telemetry", _php(src + "\n")) == 0


def test_php_telemetry_logger_helper_and_psr_forms_fire():
    assert _hits("telemetry", _php('logger()->info("x");\n')) >= 1
    assert _hits("telemetry", _php('function f(LoggerInterface $l) { $l->info("x"); }\n')) >= 1
    assert _hits("telemetry", _php('$l = new Monolog\\Logger("a"); $l->error("x");\n')) >= 1
    assert _hits("telemetry", _php('error_log("an error");\n')) >= 1


def test_php_telemetry_severity_must_be_the_method():
    assert _hits("telemetry", _php("Log::get($info);\n")) == 0


def test_php_telemetry_error_log_is_a_log_call():
    assert _hits("telemetry", _php('error_log("x", 3, "/tmp/app.log");\n')) >= 1


# --- Req D: contract negatives ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # telemetry: a bare print/echo/dump is debug_prints, not a framework log call
        ("telemetry", 'echo "info";\n'),
        ("telemetry", 'print("error");\n'),
        ("telemetry", "var_dump($info);\n"),
        ("telemetry", "print_r($error);\n"),
        ("telemetry", 'printf("info");\n'),
        ("telemetry", 'trigger_error("x", E_USER_WARNING);\n'),
        ("telemetry", '$logger->info("x");\n'),  # a variable named logger is not the facade
        ("telemetry", "Log::channel('stack');\n"),
        # api: only a PUBLIC declaration or a routing attribute; other visibility and plain code are not the API
        ("api", "private function run() {}\n"),
        ("api", "protected static function run() {}\n"),
        ("api", "function helper() {}\n"),
        ("api", "$public = 1;\n"),
        ("api", '#[Deprecated("x")]\n'),
        ("api", "#[Attribute]\n"),
        ("api", "#[Override]\n"),
    ],
)
def test_php_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, _php(negative_src)) == 0
