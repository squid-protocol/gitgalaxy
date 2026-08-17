from gitgalaxy.core.prism import Prism

LANG_DEFS = {
    "cpp": {"lexical_family": "standard_block"},
    "c": {"lexical_family": "standard_block"},
    "javascript": {"lexical_family": "standard_block"},
    "php": {"lexical_family": "standard_block"},
}

CONFIG = {
    "lexical_families": {
        "standard_block": {"delimiters": ["//", "/*", "*/"]},
    }
}


def test_issue_1718_digit_separator_does_not_pair_with_far_away_quote():
    """
    Regression test for #1718: C++ digit separators (512'000, 1'000'000'000)
    use a single quote that the unbounded shared literal shield misread as a
    char-literal opener, pairing it with the next unrelated `'` anywhere later
    in the file -- so every real // and /* */ comment in between was swallowed
    as one giant "literal" and never stripped.
    """
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
constexpr long long KB = 512'000;

// this comment should be stripped
int firstFunction(int x) {
    return x + 1;
}

/* this block comment should be stripped too */
int secondFunction(int y) {
    return y * 2;
}

char trigger = 'q';
"""

    result = prism.split_streams(code, "cpp")

    assert "// this comment should be stripped" not in result["code_stream"]  # noqa: S101
    assert "/* this block comment should be stripped too */" not in result["code_stream"]  # noqa: S101
    assert "firstFunction" in result["code_stream"]  # noqa: S101
    assert "secondFunction" in result["code_stream"]  # noqa: S101
    assert "512'000" in result["code_stream"]  # noqa: S101


def test_issue_1718_hex_and_multiple_digit_separators_kept():
    """Hex (0xDE'AD'BE'EF) and multi-group (1'000'000'000) separators stay intact."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
constexpr unsigned long long V = 0xDE'AD'BE'EF;
constexpr long long LARGE = 1'000'000'000;

// separator line comment
int first(int a) { return a; }
"""

    result = prism.split_streams(code, "cpp")

    assert "0xDE'AD'BE'EF" in result["code_stream"]  # noqa: S101
    assert "1'000'000'000" in result["code_stream"]  # noqa: S101
    assert "// separator line comment" not in result["code_stream"]  # noqa: S101


def test_issue_1718_comment_apostrophe_within_bound_still_stripped():
    """
    A comment apostrophe close to a digit separator ("it's") must not be
    re-paired: the separator is consumed as its own alternative first, so
    the comment line is still stripped.
    """
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
int f() {
    long long x = 512'000; // it's a lot
    return (int)x;
}
"""

    result = prism.split_streams(code, "cpp")

    assert "// it's a lot" not in result["code_stream"]  # noqa: S101
    assert "512'000" in result["code_stream"]  # noqa: S101


def test_issue_1718_real_char_literals_still_shielded():
    """The bound must not break genuine short char literals -- they stay intact."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
int f() {
    char a = 'x';
    char nl = '\n';
    char q = '\'';
    return a;
}
"""

    result = prism.split_streams(code, "cpp")

    assert "'x'" in result["code_stream"]  # noqa: S101
    assert "'\n'" in result["code_stream"]  # noqa: S101
    assert "'''" in result["code_stream"]  # noqa: S101


def test_issue_1718_prefixed_u8_char_literal_still_shielded():
    """u8-prefixed char literals must still shield like ordinary ones."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
int f() {
    char8_t c = u8'x'; // still a comment
    return c == u8'x' ? 1 : 0;
}
"""

    result = prism.split_streams(code, "cpp")

    assert "u8'x'" in result["code_stream"]  # noqa: S101
    assert "// still a comment" not in result["code_stream"]  # noqa: S101


def test_issue_1718_other_languages_keep_unbounded_single_quotes():
    """
    The fix is scoped to C++ only: JS/PHP (and C) single-quoted strings may be
    arbitrarily long and must keep the unbounded shared shield. A long string
    containing comment markers must survive whole.
    """
    prism = Prism(CONFIG, LANG_DEFS)

    js_code = """
const s = 'this is a long single-quoted string with // not a comment and /* also not */ inside';
function foo() { return s; }
"""

    js_result = prism.split_streams(js_code, "javascript")
    assert (
        "'this is a long single-quoted string with // not a comment and /* also not */ inside'"
        in js_result["code_stream"]
    )  # noqa: S101

    php_code = """
<?php
$s = 'a php string with // inside and /* not comment */';
function foo() { return $s; }
"""

    php_result = prism.split_streams(php_code, "php")
    assert "'a php string with // inside and /* not comment */'" in php_result["code_stream"]  # noqa: S101

    c_code = """
void f(void) {
    char *s = 'single quoted text // still one literal';
}
"""

    c_result = prism.split_streams(c_code, "c")
    assert "'single quoted text // still one literal'" in c_result["code_stream"]  # noqa: S101


def test_issue_1718_cpp23_named_escape_literal_stays_intact():
    """
    C++23 named character escapes (\\N{...}) are much longer than 10 chars
    and contain braces. The C++ char-literal branch must stay wide enough
    to shield them whole, so a real (if rare) literal isn't clipped.
    """
    prism = Prism(CONFIG, LANG_DEFS)

    code = "int main() {\n    char32_t c = '\\N{LATIN CAPITAL LETTER A}';\n    // a comment after the named escape\n    return 0;\n}\n"

    result = prism.split_streams(code, "cpp")

    assert r"\N{LATIN CAPITAL LETTER A}" in result["code_stream"]  # noqa: S101
    assert "// a comment after the named escape" not in result["code_stream"]  # noqa: S101
    assert "int main" in result["code_stream"]  # noqa: S101
