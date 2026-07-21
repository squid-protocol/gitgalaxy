import pytest
import re
from unittest.mock import patch

# Adjust this import to match your project structure
from gitgalaxy.core.prism import Prism

# ==============================================================================
# MOCK MATRIX CALIBRATION
# ==============================================================================
# We mock the language and comment definitions so the tests run deterministically
# regardless of what is inside your actual language_standards.py file.

MOCK_COMMENT_DEFS = {
    "mechanical_families": {
        "c_style_comment": {"delimiters": ["//", "/*", "*/"]},
        "single_line_only": {"delimiters": ["#"]},
        "recursive_c_style": {"delimiters": ["//", "/*", "*/"]},
        "column_sensitive": {"delimiters": []},
    }
}

MOCK_LANG_DEFS = {
    "c": {"lexical_family": "c_style_comment"},
    "python": {"lexical_family": "single_line_only"},
    "rust": {"lexical_family": "recursive_c_style"},
    "cobol": {"lexical_family": "column_sensitive"},
    "markdown": {"lexical_family": "prose"},
    "html": {"lexical_family": "xml"},
    "php": {"lexical_family": "c_style_comment"},
}


@pytest.fixture
def prism_engine():
    """Initializes the Prism with a controlled, deterministic regex matrix."""
    # We patch the SHIELD_PATTERN just in case the standard library is missing it during test time
    with patch(
        "gitgalaxy.core.prism.PRISM_CONFIG",
        {
            "SHIELD_PATTERN": r'(?P<shield>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)',
            "PYTHON_DOC_PATTERN": r"(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')",
            "PHP_HEREDOC_PATTERN": r"<<<EOT[\s\S]*?EOT;",
            "PHP_MULTILINE_STRING": r"'(?:\\'|[^'])*'",
        },
    ):
        return Prism(
            comment_definitions=MOCK_COMMENT_DEFS, language_definitions=MOCK_LANG_DEFS
        )


# ==============================================================================
# TEST 1: THE BYPASS PROTOCOLS
# ==============================================================================
@pytest.mark.smoke
def test_prism_prose_bypass(prism_engine):
    """Proves that Markdown and XML are routed entirely to the Documentation stream."""
    content = "# Title\n\nThis is a markdown file.\nIt has no active logic."
    result = prism_engine.split_streams(content, primary_lang="markdown")

    assert result["code_stream"] == ""
    assert result["comment_stream"] == content
    assert result["coding_loc"] == 0
    assert result["doc_loc"] == 3


def test_prism_metadata_guard(prism_engine):
    """Proves that Shebangs bypass the comment stripper and stay in the logic stream."""
    content = "#!/usr/bin/env python3\n# This is a comment\nprint('Hello')"
    result = prism_engine.split_streams(content, primary_lang="python")

    assert "#!/usr/bin/env python3" in result["code_stream"]
    assert "print('Hello')" in result["code_stream"]
    assert "# This is a comment" not in result["code_stream"]
    assert "This is a comment" in result["comment_stream"]


# ==============================================================================
# TEST 2: STRING MASKING
# ==============================================================================
def test_prism_string_shield_protection(prism_engine):
    """Proves that string literals containing comment delimiters do not trigger the stripper."""
    content = (
        'let url = "https://github.com"; // Set the target URL\n'
        'let str_block = "/* DO NOT STRIP ME */";\n'
        "/* Real block comment */"
    )
    result = prism_engine.split_streams(content, primary_lang="c")

    code = result["code_stream"]
    docs = result["comment_stream"]

    assert "https://" + "github.com" in code
    assert "/* DO NOT STRIP ME */" in code
    assert "Set the target URL" in docs
    assert "Real block comment" in docs


# ==============================================================================
# TEST 3: NESTED BLOCK PEELER
# ==============================================================================
def test_prism_nested_block_peeling(prism_engine):
    """Proves the iterative peel loop correctly extracts recursive block comments."""
    content = (
        "fn main() {\n"
        "    /* Outer comment\n"
        "       /* Inner comment */\n"
        "       Back to outer */\n"
        "    println!('Done');\n"
        "}"
    )
    result = prism_engine.split_streams(content, primary_lang="rust")

    code = result["code_stream"]
    docs = result["comment_stream"]

    assert "fn main() {" in code
    assert "println!('Done');" in code
    assert "Outer comment" not in code
    assert "Inner comment" in docs


# ==============================================================================
# TEST 4: POSITIONAL ANCHORS
# ==============================================================================
def test_prism_positional_anchors(prism_engine):
    """Proves legacy column-anchored and inline comments are handled correctly."""
    content = (
        "      * This is a COBOL column 7 comment\n"
        "       MOVE A TO B. *> This is an inline comment\n"
        "C This is a Fortran column 1 comment\n"
        "       X = 1 ! This is a Fortran inline comment"
    )

    prism_engine.POSITIONAL_ANCHORS = {"*", "C", "c", "!"}
    result = prism_engine.split_streams(content, primary_lang="cobol")

    code = result["code_stream"]
    docs = result["comment_stream"]

    assert "MOVE A TO B." in code
    assert "This is a COBOL column 7 comment" not in code
    assert "This is an inline comment" in docs


# ==============================================================================
# TEST 5: HARDENED PYTHON DOCSTRINGS
# ==============================================================================
def test_prism_python_docstring_extraction(prism_engine):
    """Proves multi-line string literals acting as docstrings are extracted."""
    content = (
        "def compute_hash():\n"
        '    """\n'
        "    This is a module docstring.\n"
        '    """\n'
        "    return True"
    )
    result = prism_engine.split_streams(content, primary_lang="python")

    assert "def compute_hash():" in result["code_stream"]
    assert "This is a module docstring." in result["comment_stream"]


# ==============================================================================
# TEST 6: FORMAT & METADATA BYPASSES
# ==============================================================================
def test_prism_format_and_xml_bypass(prism_engine):
    """Proves unknown and unparsable languages skip the scanner entirely."""
    content = "some raw code // comment"
    res_unknown = prism_engine.split_streams(content, primary_lang="undeterminable")
    assert res_unknown["code_stream"] == content
    assert res_unknown["comment_stream"] == ""

    # We use chr() to prevent the HTML comment from vanishing when copying
    xml_content = (
        "<?xml version='1.0'?>\n<data>"
        + chr(60)
        + "!-- comment --"
        + chr(62)
        + "</data>"
    )
    res_xml = prism_engine.split_streams(xml_content, primary_lang="xml")
    assert res_xml["code_stream"] == ""
    assert chr(60) + "!-- comment --" + chr(62) in res_xml["comment_stream"]

    php_content = "<?php\n// This is a comment\n$x = 1;"
    res_php = prism_engine.split_streams(php_content, primary_lang="php")
    assert "<?php" in res_php["code_stream"]


# ==============================================================================
# TEST 7: PHP HEREDOC AND MULTILINE STRINGS
# ==============================================================================
def test_prism_php_string_extraction(prism_engine):
    """Proves PHP Heredoc and large strings are stripped to the documentation stream."""
    prism_engine.languages["php"] = {"lexical_family": "c_style_comment"}
    prism_engine.PHP_HEREDOC_PATTERN = re.compile(r"<<<EOT[\s\S]*?EOT;", re.M)
    prism_engine.PHP_MULTILINE_STRING = re.compile(r"'(?:\\'|[^'])*'", re.M)

    content = "<?php\n$a = <<<EOT\nMassive Text\nEOT;\n$b = 'Multi\nLine';\n// comment"
    res = prism_engine.split_streams(content, primary_lang="php")

    assert "<<<EOT" not in res["code_stream"]
    assert '""' in res["code_stream"]
    assert "Massive Text" in res["comment_stream"]


# ==============================================================================
# TEST 8: EMBEDDED PARTITIONING & BALANCED END ESCAPING
# ==============================================================================
def test_prism_embedded_partitioning_and_escaping(prism_engine):
    """Proves the Embedded Triggers accurately isolate languages."""
    prism_engine.EMBEDDED_TRIGGERS = [
        {
            "trigger": re.compile(r"<script>", re.I),
            "end": re.compile(r"</script>", re.I),
            "target": "javascript",
            "pair": None,
        },
        {
            "trigger": re.compile(r"\{", re.I),
            "end": None,
            "target": "css",
            "pair": ("{", "}"),
        },
    ]

    prism_engine.EMBEDDED_LOOKAHEAD_LIMIT = 20
    html_content = "<html><script>let x = 1; // js"
    res1 = prism_engine.split_streams(html_content, primary_lang="html")
    assert "let x = 1;" in res1["code_stream"]

    prism_engine.EMBEDDED_LOOKAHEAD_LIMIT = 50000
    css_content = r"body { content: 'escaped \}'; /* comment */ }"
    idx = prism_engine._find_balanced_end(css_content, 5, "{", "}")

    assert css_content[idx - 1] == "}"


# ==============================================================================
# TEST 9: DYNAMIC REGEX MATRIX CALIBRATION
# ==============================================================================
def test_prism_regex_matrix_calibration_edge_cases():
    """Proves all complex and fallback regex families compile correctly."""

    # We construct HTML comments dynamically to completely bypass UI clipboard erasing
    html_open = chr(60) + "!--"
    html_close = "--" + chr(62)

    # 1. Primary Branches (Full Delimiter Sets)
    primary_families = {
        "single_line_only": {"delimiters": ["#", "<#", "#>"]},
        "multi_style_dash": {"delimiters": ["--", html_open, html_close, "{-", "-}"]},
        "embedded_syntax": {"delimiters": ["//", "/*", "*/", "#"]},
        "empty_delim": {"delimiters": []},
    }

    engine_primary = Prism(
        comment_definitions={"mechanical_families": primary_families},
        language_definitions={},
    )

    assert "single_line_only" in engine_primary.REGEX_MATRIX
    assert "multi_style_dash" in engine_primary.REGEX_MATRIX
    assert re.escape("{-") in engine_primary.REGEX_MATRIX["multi_style_dash"].pattern
    assert "embedded_syntax" in engine_primary.REGEX_MATRIX
    # Regression for #258: confirms the 4th delimiter ("#") wasn't silently
    # dropped by the unreachable duplicate elif branch.
    assert "#" in engine_primary.REGEX_MATRIX["embedded_syntax"].pattern

    # 2. Fallback Branches (Partial Delimiter Sets)
    fallback_families = {
        "multi_style_dash": {"delimiters": ["--", html_open, html_close]},
        "embedded_syntax": {"delimiters": ["//", "/*", "*/"]},
    }

    engine_fallback = Prism(
        comment_definitions={"mechanical_families": fallback_families},
        language_definitions={},
    )

    assert "multi_style_dash" in engine_fallback.REGEX_MATRIX

    # We check if the safely escaped version of '
    
def test_prism_embedded_syntax_fourth_delimiter_not_dropped(prism_engine):
    """
    Regression test for #258: an embedded_syntax family configured with a
    4th delimiter must actually use it when stripping comments, not silently
    lose it to an unreachable duplicate elif branch.
    """
    prism_engine.languages["configlang"] = {"lexical_family": "embedded_syntax"}
    prism_engine.lexical_families["embedded_syntax"] = {
        "delimiters": ["//", "/*", "*/", "#"]
    }
    prism_engine.REGEX_MATRIX = prism_engine._compile_regex_matrix()

    content = "value = 1 # this is a hash comment\nother = 2"
    result = prism_engine.split_streams(content, primary_lang="configlang")

    assert "value = 1" in result["code_stream"]
    assert "this is a hash comment" in result["comment_stream"]
    assert "this is a hash comment" not in result["code_stream"]

# ==============================================================================
# TEST 10: INLINE SUPPRESSION EXTRACTION (Devious Edge Cases)
# ==============================================================================
def test_prism_inline_suppression_extraction(prism_engine):
    """
    DEVIOUS EDGE CASES: 
    1. Case insensitivity (GALAXYscope:IGNORE)
    2. Multiple tags on a single line
    3. The "String Trap" (Extraction from within a literal)
    4. Dashes and underscores in risk names
    """
    content = """
    // Normal suppression
    // galaxyscope:ignore logic_bomb

    /* Weird casing suppression */
    /* GALAXYscope:IGNORE MeMoRy_CoRrUpTiOn */

    # Multiple suppressions on one line with erratic spacing
    # galaxyscope:ignore tech_debt       galaxyscope:ignore secrets-risk

    let warning = "Do not galaxyscope:ignore injection_surface in this block!";
    """

    result = prism_engine.split_streams(content, primary_lang="javascript")

    mitigations = result.get("mitigations", [])

    # Assert it caught everything and lowercased the risk names
    assert "logic_bomb" in mitigations, "Failed to extract standard suppression."
    assert "memory_corruption" in mitigations, "Failed to handle erratic casing."
    assert "tech_debt" in mitigations, "Failed to extract multiple tags (1)."
    assert "secrets-risk" in mitigations, "Failed to handle dashes in risk names."
    
    # The "String Trap" - Because extraction happens at the top of split_streams, 
    # it WILL extract from string literals. This test explicitly proves this behavior.
    assert "injection_surface" in mitigations, "Failed the String Trap extraction."

# ==============================================================================
# TEST 11: THE SUPPRESSION REGEX BOMB (Memory / ReDoS Exhaustion)
# ==============================================================================
import time

def test_prism_suppression_regex_bomb(prism_engine):
    """
    DEVIOUS EDGE CASE: An attacker uploads a file with 100,000 inline suppressions 
    to trigger Catastrophic Backtracking (ReDoS) and starve the worker thread, 
    or consume all available RAM with the mitigations array.
    """
    # Generate a massive file with 100,000 suppression tags
    massive_content = "// galaxyscope:ignore everything \n" * 100000
    
    start_time = time.time()
    result = prism_engine.split_streams(massive_content, primary_lang="javascript")
    duration = time.time() - start_time
    
    mitigations = result.get("mitigations", [])
    
    # Assert it processed the 100k tags in under 1 second (proving O(N) linear time)
    assert duration < 1.0, f"Suppression regex triggered ReDoS! Took {duration}s"
    
    # Assert the array handled the mass allocation without dropping data
    assert len(mitigations) == 100000, "Failed to allocate massive mitigation array."