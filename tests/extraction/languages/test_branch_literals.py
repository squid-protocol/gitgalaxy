# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `branch` contract's literal corollary (docs/branch_rule_contract.md, "Literals"):
a keyword, `?` or `:` inside a string or char literal is not a decision.

The code stream keeps string literals (the stream contract), so every C-family
`branch` rule counted them: a JDBC `"INSERT ... values (?, ?, ?, ?, ?)"` read as
five ternaries, `"if"` in a message as an if. IBM's published WCA4Z translation of
GenApp's LGACDB01 scored complexity 21 for a method with one if/else, all but two of
it the 19 `?` placeholders in its two INSERT strings. The brace-family languages opt
`branch` into the `outside_literals` scope filter, which shields with the brace
slicer's own literal syntax; these cases go through the real extractor because the
bare regex never sees the filter.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

BRACE_LANGS = [
    "apex", "c", "cpp", "csharp", "dart", "go", "groovy", "java", "javascript", "kotlin",
    "objective-c", "php", "rust", "scala", "solidity", "swift", "typescript", "zig",
]  # fmt: skip


def _branches(lang: str, code: str) -> int:
    from gitgalaxy.core.detector import StructuralExtractor

    counts, _mit, _maps, _parents, _locations = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).coding_analysis(
        [(lang, code, 0)]
    )
    return counts["branch"]


@pytest.mark.parametrize("lang", BRACE_LANGS)
def test_brace_family_branch_declares_outside_literals(lang):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["_scope_filters"]["branch"] == "outside_literals"


# lang -> (source with literals that hold branch tokens, the real decisions in it)
LITERALS = {
    "c": (
        "int f(int x) {\n  char *s = \"if ? while\";\n  char c = '?';\n  if (x) { g(); }\n  return x ? 1 : 2;\n}\n",
        2,
    ),
    "cpp": (
        'int f(int x) {\n  auto s = R"(if ? x)";\n  const char* t = "a ? b";\n  if (x) { g(); }\n  return 0;\n}\n',
        1,
    ),
    "csharp": ('class A { void F(int x) {\n  var s = "if ? x"; var v = @"while ? y";\n  if (x > 0) { G(); }\n} }\n', 1),
    "java": (
        'class A {\n  void f(int x) {\n    String s = "INSERT INTO T values (?, ?, ?, ?, ?)";\n'
        '    String h = "(:a, :b)"; char c = \'?\';\n    String t = """\n      if ? : case\n      """;\n'
        "    if (x > 0) { g(); }\n  }\n}\n",
        1,
    ),
    "javascript": (
        "function f(x) {\n  const s = \"if ? x\"; const t = 'while ? y'; const u = `for ? z`;\n"
        "  const v = a ?? b;\n  if (x) { g(); }\n}\n",
        2,
    ),
    "typescript": (
        'function f(x: number) {\n  const s = "if ? x";\n  const v = a ?? b;\n  return x > 0 ? 1 : 2;\n}\n',
        2,
    ),
    "kotlin": ('fun f(x: Int) {\n  val s = "if ? while ${x}"\n  val v = a ?: b\n  if (x > 0) { g() }\n}\n', 2),
    "go": ('func f(x int) {\n  s := "if for ?"\n  r := `switch case`\n  if x > 0 { g() }\n}\n', 1),
    "dart": (
        "void f(int x) {\n  var s = \"if ? x\"; var t = 'for ? y';\n  var v = a ?? b;\n  if (x > 0) { g(); }\n}\n",
        2,
    ),
    "groovy": ('def f(x) {\n  def s = "if ? x"\n  if (x) { g() }\n}\n', 1),
    "objective-c": ('- (void)f:(int)x {\n  NSString *s = @"if ? x";\n  if (x) { [self g]; }\n}\n', 1),
    "php": ("<?php\nfunction f($x) {\n  $s = \"if ? while\"; $t = 'for ? x';\n  if ($x) { g(); }\n}\n", 1),
    # a lifetime is not a char literal: the `if` and the `?` operator after it both count
    "rust": ("fn f<'a>(x: &'a str) -> i32 {\n  let s = \"if ? while\";\n  if x.len() > 0 { g()?; }\n  0\n}\n", 2),
    "scala": ('def f(x: Int): Int = {\n  val s = "if while match"\n  if (x > 0) 1 else 2\n}\n', 2),
    "solidity": (
        'contract A { function f(uint x) public {\n  string memory s = "if ? while";\n  if (x > 0) { g(); }\n} }\n',
        1,
    ),
    "swift": ('func f(x: Int) {\n  let s = "if ? while"\n  let v = a ?? b\n  if x > 0 { g() }\n}\n', 2),
    "zig": ('fn f(x: u32) void {\n  const s = "if while switch";\n  if (x > 0) { g(); }\n}\n', 1),
    "apex": (
        "public class A { public void f(Integer x) {\n  String s = 'if ? while';\n  if (x > 0) { g(); }\n} }\n",
        1,
    ),
}


def test_literals_cover_every_brace_language():
    assert sorted(LITERALS) == sorted(BRACE_LANGS)


@pytest.mark.parametrize("lang", sorted(LITERALS))
def test_branch_tokens_inside_literals_do_not_count(lang):
    code, decisions = LITERALS[lang]
    assert _branches(lang, code) == decisions


def test_java_jdbc_insert_counts_its_one_decision():
    """The WCA4Z LGACDB01 shape: an if/else choosing between two parameterized INSERTs."""
    code = (
        "class A {\n  static void insertCustomer(long n, String ncs) {\n"
        '    if (ncs.equals("ON")) {\n'
        '      String sql = "INSERT INTO CUSTOMER(A, B, C, D, E, F, G, H, I, J) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";\n'
        "    } else {\n"
        '      String sql = "INSERT INTO CUSTOMER(B, C, D, E, F, G, H, I, J) values (?, ?, ?, ?, ?, ?, ?, ?, ?)";\n'
        "    }\n  }\n}\n"
    )
    assert _branches("java", code) == 2  # the if and its else arm


@pytest.mark.parametrize(
    "code,decisions",
    [
        ("int y = x > 1 ? 2 : 3;", 1),  # one ternary, one decision
        ("switch (x) {\n  case 1: g(); break;\n  default: h();\n}", 3),  # the colons add nothing
        ("outer:\nfor (int i : xs) { g(); }", 1),  # label and enhanced-for separator
        ("List<?> a; Map<?, ?> b; List<? extends Number> c; Class<? super T> d;", 0),  # wildcards are types
        ('assert x > 0 : "msg";', 0),
        ("xs.forEach(System.out::println);", 0),
        ("int y = a ? b ? 1 : 2 : 3;", 2),  # nested ternaries: two decisions
    ],
)
def test_java_colon_and_wildcard_question_marks_are_not_decisions(code, decisions):
    assert _branches("java", "class A {\n  void f() {\n" + code + "\n  }\n}\n") == decisions
