"""#1718: C++ digit separators vs. Prism's single-quote literal shield.

C++14 numeric literals may carry `'` digit separators (`512'000`,
`0xDE'AD'BE'EF`). The shared SHIELD_PATTERN's char-literal branch read such a
separator as an opening quote and ran to the next unrelated `'` later in the
file, so every real comment in between stayed in the code stream. C++ now gets
its own comment matrix (CPP_REGEX_MATRIX) whose shield claims separator-bearing
numbers before a (bounded) char literal; every other language is unchanged.

Drives Prism through the REAL config (like test_prism.py's
test_prism_strips_comments_against_the_real_config), since the bug lives in
how the real `standard_block` family pattern treats C++ source.
"""

import re
import time

import pytest

from gitgalaxy.core.prism import CPP_LITERAL_MASK_PATTERN, Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, PRISM_CONFIG

# The shared shield exactly as shipped in _prism_config.py -- #1718 must not
# change it by a single byte.
_SHARED_SHIELD_PATTERN = r'((?<!\\)"(?:\\.|[^"\\])*"|(?<!\\)\'(?:\\.|[^\'\\])*\'|(?<!\\)`(?:\\.|[^`\\])*`)'


@pytest.fixture(scope="module")
def real_prism():
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


# ------------------------------------------------------------------------------
# Comments after digit-separated literals are still stripped
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "literal",
    ["512'000", "1'000'000'000", "0xDE'AD'BE'EF", "0b1010'1010", "1'000.5", "1'000'000"],
)
def test_comment_after_digit_separator_literal_is_stripped(real_prism, literal):
    """A lone separator must not open a char literal that swallows the
    comments below it up to the next unrelated `'`."""
    content = (
        f"const auto kLimit = {literal};\n"
        "// first real comment\n"
        "int helper() { return 1; }\n"
        "/* block comment */\n"
        "char c = 'x';\n"
    )
    result = real_prism.split_streams(content, "cpp")

    assert "first real comment" not in result["code_stream"]  # noqa: S101
    assert "block comment" not in result["code_stream"]  # noqa: S101
    assert "first real comment" in result["comment_stream"]  # noqa: S101
    assert "block comment" in result["comment_stream"]  # noqa: S101
    # The literal itself and the surrounding code survive untouched.
    assert f"const auto kLimit = {literal};" in result["code_stream"]  # noqa: S101
    assert "int helper() { return 1; }" in result["code_stream"]  # noqa: S101
    assert "char c = 'x';" in result["code_stream"]  # noqa: S101
    # Line geometry is preserved (comments collapse to their newlines).
    assert result["code_stream"].count("\n") == content.count("\n")  # noqa: S101


def test_trailing_comment_on_separator_line_is_captured(real_prism):
    content = "int a = 512'000; // budget in bytes\nchar b = 'z';\n"
    result = real_prism.split_streams(content, "cpp")

    assert result["code_stream"] == "int a = 512'000; \nchar b = 'z';\n"  # noqa: S101
    assert result["comment_stream"] == "// budget in bytes"  # noqa: S101


def test_many_separator_literals_and_comments_interleaved(real_prism):
    content = (
        "long a = 512'000;      // one\n"
        "long b = 0xDE'AD'BE'EF; // two\n"
        "long c = 0b1010'1010;  /* three */\n"
        "double d = 1'000.5;    // four's apostrophe\n"
        "long e = 1'000'000'000; // five\n"
    )
    result = real_prism.split_streams(content, "cpp")

    for word in ("one", "two", "three", "four's apostrophe", "five"):
        assert word in result["comment_stream"]  # noqa: S101
        assert word not in result["code_stream"]  # noqa: S101
    for literal in ("512'000", "0xDE'AD'BE'EF", "0b1010'1010", "1'000.5", "1'000'000'000"):
        assert literal in result["code_stream"]  # noqa: S101


def test_positional_comment_stream_uses_cpp_shield(real_prism):
    """The positional variant picks its pattern the same way, so a comment
    after a separator literal lands on its own original line there too."""
    content = "int a = 512'000;\n// real doc comment\nchar f() { return '0'; }\n"
    positional = real_prism.split_positional_comment_stream(content, "cpp")

    lines = positional.split("\n")
    assert len(lines) == len(content.split("\n"))  # noqa: S101
    assert lines[0] == ""  # noqa: S101
    assert lines[1] == "// real doc comment"  # noqa: S101
    assert lines[2] == ""  # noqa: S101


# ------------------------------------------------------------------------------
# Real char literals are still shielded
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("char_literal", ["'/'", "'*'", "'a'", "'\\n'", "'\\''", "'\\x41'"])
def test_char_literals_are_not_treated_as_comments(real_prism, char_literal):
    content = f"char c = {char_literal}; char d = '/'; int x = 1; // trailing\nint y = 2;\n"
    result = real_prism.split_streams(content, "cpp")

    assert f"char c = {char_literal}; char d = '/'; int x = 1; " in result["code_stream"]  # noqa: S101
    assert result["comment_stream"] == "// trailing"  # noqa: S101


def test_comment_markers_split_across_char_literals_stay_code(real_prism):
    """`'/'` then `'/'` must not fuse into a `//` line comment, and `'/'`
    followed by `'*'` must not open a block comment."""
    content = "if (c == '/' && n == '/') ok();\nif (c == '/' && n == '*') more();\nint z = 1'000; // end\n"
    result = real_prism.split_streams(content, "cpp")

    assert "ok();" in result["code_stream"]  # noqa: S101
    assert "more();" in result["code_stream"]  # noqa: S101
    assert "int z = 1'000; " in result["code_stream"]  # noqa: S101
    assert result["comment_stream"] == "// end"  # noqa: S101


def test_string_literal_with_comment_markers_stays_code(real_prism):
    content = 'const char* url = "http://example.com/*x*/"; // real\n'
    result = real_prism.split_streams(content, "cpp")

    assert 'const char* url = "http://example.com/*x*/"; ' in result["code_stream"]  # noqa: S101
    assert result["comment_stream"] == "// real"  # noqa: S101


# ------------------------------------------------------------------------------
# Matrix wiring and non-C++ behaviour
# ------------------------------------------------------------------------------
def test_literal_mask_pattern_is_unchanged(real_prism):
    assert PRISM_CONFIG["SHIELD_PATTERN"] == _SHARED_SHIELD_PATTERN  # noqa: S101
    assert real_prism.LITERAL_MASK_PATTERN == _SHARED_SHIELD_PATTERN  # noqa: S101


def test_default_matrix_still_uses_shared_shield(real_prism):
    default_pattern = real_prism.REGEX_MATRIX["standard_block"].pattern
    assert default_pattern.startswith(_SHARED_SHIELD_PATTERN + "|")  # noqa: S101
    assert real_prism._compile_regex_matrix()["standard_block"].pattern == default_pattern  # noqa: S101
    assert real_prism._compile_regex_matrix(None)["standard_block"].pattern == default_pattern  # noqa: S101


def test_cpp_matrix_uses_cpp_shield_as_group_one(real_prism):
    cpp_pattern = real_prism.CPP_REGEX_MATRIX["standard_block"]
    assert cpp_pattern.pattern.startswith(CPP_LITERAL_MASK_PATTERN + "|")  # noqa: S101
    assert re.compile(CPP_LITERAL_MASK_PATTERN).groups == 1  # noqa: S101

    m = cpp_pattern.search("x = 512'000; // c")
    assert m is not None  # noqa: S101
    assert m.group(1) == "512'000"  # noqa: S101
    m2 = cpp_pattern.search("x = 1; // c")
    assert m2 is not None  # noqa: S101
    assert m2.group(1) is None  # noqa: S101
    assert m2.group(2) == "// c"  # noqa: S101


def test_explicit_literal_pattern_overrides_shield(real_prism):
    custom = r"(\[[^\]\n]{0,20}\])"
    matrix = real_prism._compile_regex_matrix(literal_pattern=custom)
    assert matrix["standard_block"].pattern.startswith(custom + "|")  # noqa: S101
    # multi_style_live's own LiveCode shield only applies to the default call.
    if "multi_style_live" in matrix:
        assert matrix["multi_style_live"].pattern.startswith(custom + "|")  # noqa: S101
        default_live = real_prism.REGEX_MATRIX["multi_style_live"].pattern
        assert default_live.startswith(real_prism.MULTI_STYLE_LIVE_LITERAL_MASK_PATTERN + "|")  # noqa: S101


def test_only_cpp_standard_block_selects_cpp_matrix(real_prism):
    assert real_prism._generic_family_pattern("cpp", "standard_block") is real_prism.CPP_REGEX_MATRIX["standard_block"]  # noqa: S101
    for lang in ("c", "javascript", "php", "java"):
        assert real_prism._generic_family_pattern(lang, "standard_block") is real_prism.REGEX_MATRIX["standard_block"]  # noqa: S101


def test_javascript_long_single_quoted_string_still_shielded(real_prism):
    """JS single-quoted strings are long and may hold `//` or digits next to
    quotes; they keep the shared, unbounded shield."""
    long_text = "see http://example.com/path // not a comment, " + "x" * 200
    content = f"var n = 512;\nvar s = '{long_text}';\n// real js comment\nvar t = '1'+'000';\n"
    result = real_prism.split_streams(content, "javascript")

    assert f"var s = '{long_text}';" in result["code_stream"]  # noqa: S101
    assert "var t = '1'+'000';" in result["code_stream"]  # noqa: S101
    assert result["comment_stream"] == "// real js comment"  # noqa: S101


def test_php_single_quoted_string_still_shielded(real_prism):
    long_text = "it\\'s /* not */ a comment // either " + "y" * 150
    content = f"<?php\n$s = '{long_text}';\n// real php comment\n$n = 5;\n"
    result = real_prism.split_streams(content, "php")

    assert "real php comment" in result["comment_stream"]  # noqa: S101
    assert "real php comment" not in result["code_stream"]  # noqa: S101
    assert "not */ a comment // either" not in result["comment_stream"]  # noqa: S101
    assert "$n = 5;" in result["code_stream"]  # noqa: S101


def test_cpp_shield_is_bounded_on_adversarial_input(real_prism):
    """Long runs of separator-like and quote-like text must be handled in
    linear-ish time (every C++-specific repetition is bounded)."""
    payload = ("1'" * 5000) + "\n" + ("'\\" * 5000) + "\n" + ("9e+" * 5000) + "\n// tail\n"
    start = time.perf_counter()
    result = real_prism.split_streams(payload, "cpp")
    assert time.perf_counter() - start < 2.0  # noqa: S101
    assert "// tail" in result["comment_stream"]  # noqa: S101
