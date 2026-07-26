import pytest
import re
from unittest.mock import patch

# Adjust this import to match your project structure
from gitgalaxy.core.prism import Prism, PrismError

# ==============================================================================
# MOCK MATRIX CALIBRATION
# ==============================================================================
# We mock the language and comment definitions so the tests run deterministically
# regardless of what is inside your actual language_standards.py file.

# #386: these used to be a fictional taxonomy ("mechanical_families",
# "c_style_comment", "single_line_only", "recursive_c_style",
# "column_sensitive") that never matched the real config
# (gitgalaxy_config.py's LEXICAL_FAMILY_HEURISTICS uses "lexical_families",
# and real per-language "lexical_family" values are standard_block/
# line_exclusive/recursive_block/positional_anchored/block_exclusive/
# non_lexical) -- every test in this file passed anyway, because they never
# exercised the real config, which is exactly how prism.py's total failure
# to strip comments for any language went undetected. Renamed to match
# reality so this class of drift can't silently recur.
MOCK_COMMENT_DEFS = {
    "lexical_families": {
        "standard_block": {"delimiters": ["//", "/*", "*/"]},
        "line_exclusive": {"delimiters": ["#"]},
        "recursive_block": {"delimiters": ["//", "/*", "*/"]},
        "positional_anchored": {"delimiters": []},
    }
}

MOCK_LANG_DEFS = {
    "c": {"lexical_family": "standard_block"},
    "python": {"lexical_family": "line_exclusive"},
    "rust": {"lexical_family": "recursive_block"},
    "cobol": {"lexical_family": "positional_anchored"},
    "markdown": {"lexical_family": "prose"},
    "html": {"lexical_family": "xml"},
    "php": {"lexical_family": "standard_block"},
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


def test_prism_empty_content_short_circuits(prism_engine):
    """An empty content buffer must return the zeroed-out result shape directly, skipping all regex work."""
    result = prism_engine.split_streams("", primary_lang="python")
    assert result == {
        "code_stream": "",
        "comment_stream": "",
        "coding_loc": 0,
        "doc_loc": 0,
        "mitigations": [],
    }


def test_prism_catastrophic_failure_wraps_in_prism_error(prism_engine):
    """
    Stress test: if something inside the scan raises unexpectedly (not one
    of the specific, already-handled cases), split_streams must wrap it in a
    PrismError with the original exception chained -- never let a raw,
    unrelated exception type escape to the caller.
    """
    with patch.object(prism_engine, "_strip_segment_comments", side_effect=RuntimeError("simulated engine failure")):
        with pytest.raises(PrismError) as exc_info:
            prism_engine.split_streams("some code", primary_lang="python")

    assert "simulated engine failure" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


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


def test_prism_nested_block_peeling_reads_the_real_lexical_families_key(prism_engine):
    """
    Regression test for a #386 follow-up: _strip_nested_comments() looked up
    self.lexical_families.get("recursive_c_style", ...) -- the OLD dead name,
    missed in the original rename pass -- and only "worked" because its
    hardcoded fallback default (["//", "/*", "*/"]) happened to coincidentally
    match "recursive_block"'s real delimiters. Using non-default delimiters
    here proves the lookup key itself is correct, not just the fallback.
    """
    prism_engine.lexical_families["recursive_block"] = {"delimiters": ["##", "<<", ">>"]}

    content = "fn main() {\n    << Outer << Inner >> Back to outer >>\n    do_work();\n}"
    result = prism_engine.split_streams(content, primary_lang="rust")

    assert "do_work();" in result["code_stream"]
    assert "Outer" not in result["code_stream"]
    assert "Inner" in result["comment_stream"]


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
    prism_engine.languages["php"] = {"lexical_family": "standard_block"}
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
        "line_exclusive": {"delimiters": ["#", "<#", "#>"]},
        "multi_style_dash": {"delimiters": ["--", html_open, html_close, "{-", "-}"]},
        "embedded_syntax": {"delimiters": ["//", "/*", "*/", "#"]},
        "empty_delim": {"delimiters": []},
    }

    engine_primary = Prism(
        comment_definitions={"lexical_families": primary_families},
        language_definitions={},
    )

    assert "line_exclusive" in engine_primary.REGEX_MATRIX
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
        comment_definitions={"lexical_families": fallback_families},
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
# TEST 9.5: THE REAL CONFIG, NOT THE MOCK (#386)
# ==============================================================================
def test_prism_strips_comments_against_the_real_config():
    """
    Regression test for #386: every other test in this file drives Prism
    through MOCK_COMMENT_DEFS/MOCK_LANG_DEFS, which used to be a fictional,
    internally-consistent taxonomy that never matched the real
    gitgalaxy_config.py/language_standards.py config -- meaning NONE of them
    would have caught prism.py's total failure to strip comments for any of
    the 58 real languages. This test wires up the REAL config instead, and
    proves comment stripping actually works for one language per real family
    (standard_block, line_exclusive, recursive_block, positional_anchored).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    # standard_block (C)
    result = real_prism.split_streams(
        "// a comment\nint main() {\n    /* block */\n    return 0;\n}\n", "c"
    )
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # line_exclusive (Python)
    result = real_prism.split_streams("x = 1  # a comment\ny = 2\n", "python")
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # recursive_block (Rust)
    result = real_prism.split_streams(
        "fn main() {\n    // a comment\n}\n", "rust"
    )
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # positional_anchored (COBOL)
    result = real_prism.split_streams(
        "       IDENTIFICATION DIVISION.\n      * a comment\n", "cobol"
    )
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]


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