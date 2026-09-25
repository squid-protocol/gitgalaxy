"""
#3543: a unit's start_line is the line its declaration is on. TS/JS func_start
opens with `[ \t\n]*` and PHP's consumes one boundary character (usually the
previous line's newline), so the match used to start on the line before: a class
`{`, the previous member's `},`, a docblock's `*/`, or several lines up when
PRISM had blanked a doc comment. Run through the real PRISM config, as a scan does.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(src, lang):
    code = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, lang)["code_stream"]
    return {f["name"]: f for f in StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]}


def _line_of(src, needle):
    return next(i for i, line in enumerate(src.split("\n"), 1) if needle in line)


TS = """export class ExportStatement extends Statement {
  constructor(public x: number) {
    super();
  }

  /**
   * Docs that PRISM blanks.
   */
  run(): void {
    return;
  }
}

const handlers = {
  a: () => 1,
  b: () => 2,
};
"""

PHP = """<?php
/**
 * Sanitizes an option.
 *
 * @since 2.0.0
 */
function sanitize_option($option, $value) {
    return $value;
}

class A {
    public function first() {
        return 1;
    }
    public function second() {
        return 2;
    }
}
"""


@pytest.mark.parametrize("name, needle", [("constructor", "constructor("), ("run", "run():")])
def test_typescript_units_start_on_their_declaration_line(name, needle):
    unit = _units(TS, "typescript")[name]
    assert unit["start_line"] == _line_of(TS, needle)


@pytest.mark.parametrize(
    "name, needle",
    [("sanitize_option", "function sanitize_option"), ("first", "function first"), ("second", "function second")],
)
def test_php_units_start_on_their_declaration_line(name, needle):
    unit = _units(PHP, "php")[name]
    assert unit["start_line"] == _line_of(PHP, needle)


def test_the_anchor_keeps_the_declaration_indentation_and_end_line():
    unit = _units(TS, "typescript")["run"]
    assert unit["end_line"] == _line_of(TS, "return;") + 1
