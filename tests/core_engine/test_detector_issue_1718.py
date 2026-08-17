"""
Regression tests for issue #1718: C++14+ digit separators (512'000,
1'000'000'000, 0xDE'AD'BE'EF) use a single quote inside numeric literals.

_build_brace_safe_stream's single-quote branch used to be unbounded for cpp,
so a separator quote was read as the opener of a char literal and paired with
the NEXT unrelated apostrophe anywhere later in the file -- blanking every real
{/} in between, including real function bodies, and desyncing the brace scan so
functions after the separator were dropped entirely. The digit separator must be
consumed as its own alternative and the char-literal branch bounded to 64 chars,
matching the bound #1302/#1426 already apply to rust/zig and prism.py.
"""
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def test_detector_cpp_digit_separator_does_not_blank_function_bodies():
    code = (
        "constexpr long long KB = 512'000;\n"
        "\n"
        "bool firstFunction(const String &p_state) {\n"
        "    return !force_background;\n"
        "}\n"
        "\n"
        "// a comment with a stray apostrophe: it's here\n"
        "int secondFunction(int y) {\n"
        "    return y * 2;\n"
        "}\n"
        "\n"
        "char trigger = 'q';\n"
        "\n"
        "int thirdFunction(int z) {\n"
        "    return z * 3;\n"
        "}\n"
    )
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["cpp"]["rules"]
    satellites, _ = detector._slice_by_braces(code, "cpp", rules, 0, {})
    names = [s["name"] for s in satellites]
    assert "firstFunction" in names, f"firstFunction should be found: {names}"
    assert "secondFunction" in names, f"secondFunction must not be swallowed: {names}"
    assert "thirdFunction" in names, f"thirdFunction must survive after the digit separator: {names}"
    second = next(s for s in satellites if s["name"] == "secondFunction")
    assert second["loc"] <= 3, f"secondFunction body must stay bounded: loc={second['loc']}"
    third = next(s for s in satellites if s["name"] == "thirdFunction")
    assert third["loc"] <= 3, f"thirdFunction body must stay bounded: loc={third['loc']}"


def test_issue_1718_cpp23_named_escape_literal_stays_intact():
    r"""
    C++23 named character escapes (\N{...}) are much longer than 10 chars
    and contain braces. The C++ char-literal branch must stay wide enough
    to shield them whole, so a real (if rare) literal isn't clipped and
    doesn't desync the brace tracker.
    """
    code = (
        "int main() {\n"
        "    char32_t c = '\\N{LATIN CAPITAL LETTER A}';\n"
        "    // a comment after the named escape\n"
        "    return 0;\n"
        "}\n"
        "int nextFunction() {\n"
        "    return 1;\n"
        "}\n"
    )
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["cpp"]["rules"]
    satellites, _ = detector._slice_by_braces(code, "cpp", rules, 0, {})
    names = [s["name"] for s in satellites]
    
    assert "main" in names, f"main should be found: {names}"
    assert "nextFunction" in names, f"nextFunction should be found: {names}"