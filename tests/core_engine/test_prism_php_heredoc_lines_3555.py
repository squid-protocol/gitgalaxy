"""
#3555: PRISM shields a PHP heredoc/nowdoc as `""` without losing its lines. It
used to collapse the whole literal to `""`, so every line after one was numbered
early (wordpress/functions.php lost 10) and every later function's start_line
with it. Run through the real PRISM config, as a scan does.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _code(src):
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, "php")["code_stream"]


@pytest.mark.parametrize("opener", ["<<<EOD", "<<<'EOD'", '<<<"EOD"'])  # heredoc, nowdoc, quoted heredoc
def test_a_heredoc_keeps_its_line_count_and_statement_terminator(opener):
    src = f"<?php\nfunction a() {{\n $x = {opener}\nline1\nfunction fake() {{}}\nline3\nEOD;\n  return $x;\n}}\n"
    code = _code(src)
    assert code.count("\n") == src.count("\n")
    assert '$x = "";' in code  # the statement keeps its `;`
    assert "fake" not in code  # the body is still shielded
    assert code.split("\n")[7] == "  return $x;"  # the line after the heredoc is still line 8


def test_functions_after_a_heredoc_keep_their_lines():
    src = "<?php\nfunction a() {\n  $x = <<<EOD\n1\n2\n3\n4\n5\nEOD;\n}\n\nfunction b() {\n}\n"
    code = _code(src)
    lines = {
        f["name"]: f["start_line"]
        for f in StructuralExtractor("php", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    }
    # `b` is declared on line 12 -- not 7 lines early, the way the collapsed heredoc
    # numbered it, nor one early on the blank line (#3543).
    assert lines["b"] == 12
