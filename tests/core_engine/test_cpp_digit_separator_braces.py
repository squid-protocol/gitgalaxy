"""#1718: C++ digit separators vs. the detector's brace-safe stream.

`_build_brace_safe_stream` shields string/char literals so a literal `{`/`}`
can't desync the brace-depth counter. Its default single-quote branch is
unbounded, so a C++ digit separator (`512'000`) opened a bogus char literal
that ran to the next unrelated `'` -- blanking the real braces of every
function in between, which the slicer then never found. C++ now claims
separator-bearing numbers first (kept verbatim) and bounds its char literals;
every other language keeps its existing shield.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(lang_id: str, code: str) -> dict[str, tuple[int, int]]:
    detector = StructuralExtractor(lang_id, LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "")
    return {f["name"]: (f["start_line"], f["end_line"]) for f in result["functions"]}


@pytest.mark.parametrize("literal", ["512'000", "0xDE'AD'BE'EF", "0b1010'1010", "1'000.5", "1'000'000'000"])
def test_functions_after_separator_literal_are_found(literal):
    code = (
        f"static const auto kValue = {literal};\n"
        "int alpha(int x) {\n"
        "    return x + 1;\n"
        "}\n"
        "int beta(int y) {\n"
        "    return y * 2;\n"
        "}\n"
        "char gamma_char() {\n"
        "    return 'q';\n"
        "}\n"
    )
    funcs = _functions("cpp", code)

    assert funcs.get("alpha") == (2, 4)  # noqa: S101
    assert funcs.get("beta") == (5, 7)  # noqa: S101
    assert funcs.get("gamma_char") == (8, 10)  # noqa: S101


def test_functions_after_million_literal_line_are_found():
    """Bodies that follow a line containing `1'000'000`, with another
    separator and a real char literal later in the file."""
    code = (
        "#include <cstdint>\n"
        "constexpr std::uint64_t kMillion = 1'000'000;\n"
        "constexpr std::uint64_t kBudget = 512'000;\n"
        "\n"
        "int scale(int v) {\n"
        "    if (v > 0) {\n"
        "        return v * 2;\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
        "\n"
        "void report() {\n"
        "    total += kMillion;\n"
        "}\n"
        "\n"
        "char sep() {\n"
        "    return '\\'';\n"
        "}\n"
    )
    funcs = _functions("cpp", code)

    assert funcs.get("scale") == (5, 10)  # noqa: S101
    assert funcs.get("report") == (12, 14)  # noqa: S101
    assert funcs.get("sep") == (16, 18)  # noqa: S101


def test_brace_safe_stream_keeps_numbers_and_blanks_char_braces():
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    code = "long n = 1'000'000; char open = '{'; char close = '}';\nint f() { return 0; }\n"
    safe = detector._build_brace_safe_stream(code, "cpp")

    assert len(safe) == len(code)  # noqa: S101
    assert safe.count("\n") == code.count("\n")  # noqa: S101
    # Separator-bearing number kept verbatim; char-literal braces blanked.
    assert "long n = 1'000'000;" in safe  # noqa: S101
    assert "'{'" not in safe  # noqa: S101
    assert "'}'" not in safe  # noqa: S101
    assert safe.count("{") == 1  # noqa: S101
    assert safe.count("}") == 1  # noqa: S101


@pytest.mark.parametrize("char_literal", ["'a'", "'\\n'", "'\\''", "'\\x41'", "'/'", "'{'"])
def test_real_char_literals_are_still_shielded(char_literal):
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    code = f"char c = {char_literal}; int k = 512'000;\n"
    safe = detector._build_brace_safe_stream(code, "cpp")

    assert char_literal not in safe  # noqa: S101
    assert "char c = " in safe  # noqa: S101
    assert "int k = 512'000;" in safe  # noqa: S101


def test_non_cpp_brace_stream_unchanged_for_js_single_quoted_string():
    """JS keeps the shared unbounded single-quote shield: a long string
    holding braces is fully blanked, and the function after it is found."""
    detector = StructuralExtractor("javascript", LANGUAGE_DEFINITIONS)
    long_text = "{ not a brace } " * 20
    code = f"var s = '{long_text}';\n"
    safe = detector._build_brace_safe_stream(code, "javascript")

    assert safe == "var s = " + " " * (len(long_text) + 2) + ";\n"  # noqa: S101


def test_c_default_shield_unchanged():
    """C (not C++) still uses the default, unbounded char pattern: a lone
    `'` pairs with the next one, exactly as before #1718."""
    detector = StructuralExtractor("c", LANGUAGE_DEFINITIONS)
    code = "int a = 5'0;\nint b = 'x';\n"
    safe = detector._build_brace_safe_stream(code, "c")

    # The span `'0;\nint b = '` is shielded (blanked, newline kept).
    assert safe == "int a = 5   \n" + " " * len("int b = '") + "x';\n"  # noqa: S101
