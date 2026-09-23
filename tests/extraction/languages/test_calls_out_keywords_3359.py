"""
#3359: the `calls_out` contract's keyword (C2), annotation (C1) and string (C7) classes
(docs/calls_out_rule_contract.md, classes K / A / S), pinned end to end through
`StructuralExtractor.splice()` so the literal shield and the ignore sets are in the path.

Every case pairs the non-call it must drop with a real call from the same body, so a fix that
over-filters (recall loss) fails as loudly as one that under-filters.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_C_STYLE,
    CALLS_OUT_C_STYLE_NO_ANNOTATION,
)


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


# (lang, code, function, callees that must be kept, non-calls that must be dropped)
_KEYWORD_CASES = [
    (
        "go",
        "package m\nfunc Run(a int) {\n  var (\n    x = 1\n  )\n  go func() { work(a) }()\n}\n",
        "Run",
        {"work"},
        {"func", "var"},
    ),
    (
        "php",
        "<?php\nfunction run($xs) {\n  foreach ($xs as $x) { save($x); }\n"
        "  if (isset($a) && !empty($b)) { unset($a); }\n  elseif ($c) { $f = fn($y) => $y; }\n"
        "  $m = array(1);\n  $this->match($m);\n}\n",
        "run",
        {"save", "match"},
        {"foreach", "isset", "empty", "unset", "elseif", "fn", "array"},
    ),
    (
        "csharp",
        "class A {\n  void Run(int[] xs) {\n    foreach (var x in xs) { Save(x); }\n"
        "    var n = nameof(Run);\n    var (a, b) = Pair();\n    lock (this) { Go(); }\n  }\n}\n",
        "Run",
        {"Save", "Pair", "Go"},
        {"foreach", "nameof", "var", "lock"},
    ),
    (
        "rust",
        "pub(crate) fn run(v: Vec<u8>) {\n    let (a, b) = split(v);\n    match (a, b) { _ => go() }\n}\n",
        "run",
        {"split", "go"},
        {"let", "match"},
    ),
    (
        "python",
        "def run(x, xs):\n    if x in (1, 2) and not (x or y):\n        go(x)\n    elif(x):\n        stop()\n",
        "run",
        {"go", "stop"},
        {"in", "and", "not", "or", "elif"},
    ),
    (
        "lua",
        "function run(x)\n  if not (x) or (y) then\n    go(x)\n  end\nend\n",
        "run",
        {"go"},
        {"not", "or"},
    ),
    (
        "typescript",
        "function run(p: Promise<void>) {\n  const f = async () => { await go(); };\n  return p as (unknown);\n}\n",
        "run",
        {"go"},
        {"async", "as"},
    ),
    (
        "solidity",
        'contract C {\n  function run(uint a) public returns (uint) {\n    assembly ("memory-safe") { }\n'
        "    return helper(a);\n  }\n}\n",
        "run",
        {"helper"},
        {"returns", "assembly"},
    ),
    (
        "scala",
        "object O {\n  def run(xs: List[Int]): Unit = {\n    val (a, b) = xs.splitAt(1)\n"
        "    xs match { case (h) => go(h) }\n  }\n}\n",
        "run",
        {"splitAt", "go"},
        {"val", "case"},
    ),
    (
        "java",
        "class A {\n  A(int x) {\n    this(x, 0);\n    init(x);\n  }\n}\n",
        "A",
        {"init"},
        {"this"},
    ),
    (
        "perl",
        "sub run {\n  my @a = qw(a b);\n  go(@a) and (stop()) or (halt());\n  $dbh->do('x');\n}\n",
        "run",
        {"go", "stop", "halt", "do"},
        {"qw", "and", "or"},
    ),
    (
        "zig",
        "fn run(a: u8) callconv(.C) void {\n  const E = enum(u8) { x };\n  if (a == 1 and (b)) go();\n}\n",
        "run",
        {"go"},
        {"callconv", "enum", "and"},
    ),
    (
        "ada",
        "procedure Run is\nbegin\n   if not (X) then\n      Go (X);\n   end if;\nend Run;\n",
        "Run",
        {"Go"},
        {"not"},
    ),
    (
        "cpp",
        "void run(int x) {\n  static_assert(sizeof(int) == 4);\n  if constexpr (true) { go(x); }\n}\n",
        "run",
        {"go"},
        {"static_assert", "constexpr"},
    ),
    (
        "powershell",
        "function Run {\n  Write-Host 'x'\n  Return\n  break\n  exit 1\n}\n",
        "Run",
        {"Write-Host"},
        {"Return", "break", "exit"},
    ),
    (
        "livecode",
        'command doIt\n  private\n  variable tX\n  answer "x"\n  helper tX\nend doIt\n',
        "doIt",
        {"helper"},
        {"private", "variable"},
    ),
    (
        "scheme",
        "(define (run x)\n  (let* ((a (car x)))\n    (let-values (((b c) (split a)))\n      (go b))))\n",
        "run",
        {"car", "split", "go"},
        {"let*", "let-values"},
    ),
]


@pytest.mark.parametrize("lang, code, fn, keep, drop", _KEYWORD_CASES, ids=[c[0] for c in _KEYWORD_CASES])
def test_keyword_is_not_a_call(lang, code, fn, keep, drop):
    # C2: a keyword or special form followed by `(` is never a call; the real calls beside it stay.
    calls = _calls(lang, code)[fn]
    assert keep <= set(calls), calls
    assert not drop & set(calls), calls


@pytest.mark.parametrize(
    "lang, code, fn",
    [
        ("java", 'class A {\n  @SuppressWarnings("x")\n  void run(int a) {\n    go(a);\n  }\n}\n', "run"),
        ("kotlin", "class A {\n  @Throws(E::class)\n  fun run(a: Int) {\n    go(a)\n  }\n}\n", "run"),
        ("swift", "@available(iOS 13, *)\nfunc run(a: Int) {\n  go(a)\n}\n", "run"),
        ("dart", "class A {\n  @Deprecated('x')\n  void run(int a) {\n    go(a);\n  }\n}\n", "run"),
        ("groovy", "class A {\n  @Issue('x')\n  def run(a) {\n    go(a)\n  }\n}\n", "run"),
        ("scala", 'object O {\n  @deprecated("x")\n  def run(a: Int): Unit = {\n    go(a)\n  }\n}\n', "run"),
    ],
)
def test_annotation_is_not_a_call(lang, code, fn):
    # C1: a metadata annotation is a declaration, even with parentheses. The annotation may sit
    # outside the sliced body; either way it must not surface as a callee.
    found = _calls(lang, code)
    for calls in found.values():
        assert not {"SuppressWarnings", "Throws", "available", "Deprecated", "Issue", "deprecated"} & set(calls)
    assert "go" in found[fn]


def test_annotation_languages_use_the_no_annotation_pattern():
    for lang in ("java", "kotlin", "swift", "dart", "groovy", "scala"):
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE_NO_ANNOTATION
    # Python/TypeScript/JavaScript decorator factories ARE invocations (C1) -- the plain pattern.
    for lang in ("python", "typescript", "javascript"):
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE


def test_decorator_factory_is_still_a_call():
    # C1: `@retry(3)` invokes `retry`; the annotation rule must not reach python.
    code = "class A:\n    def run(self):\n        @retry(3)\n        def inner():\n            pass\n        go()\n"
    assert "retry" in _calls("python", code)["run"]


def test_no_annotation_pattern_keeps_qualifiers():
    # #3329: the qualifier rides beside calls_out_to for the annotation-free variant too.
    code = "class A {\n  void run(Store s) {\n    s.save(1);\n  }\n}\n"
    fn = next(f for f in StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")["functions"])
    assert fn["calls_out_qualifiers"].get("save") == ["s"]


def test_tcl_brace_quoted_sql_is_not_a_call():
    # C7: SQL keywords that start the lines of a brace-quoted query are string content.
    code = (
        "proc run {db} {\n  $db eval {\n    SELECT a FROM t\n    WHERE x = 1\n  }\n  lappend out x\n  cleanup $db\n}\n"
    )
    calls = _calls("tcl", code)["run"]
    assert {"lappend", "cleanup"} <= set(calls)
    assert not {"SELECT", "WHERE"} & set(calls)


@pytest.mark.parametrize(
    "lang, code, fn, callee",
    [
        # A case-sensitive language compares its ignore set exactly: the keyword never
        # swallows a real callee spelled with capitals.
        ("go", "package m\nfunc Run(v Value) {\n  t := v.Type()\n  use(t)\n}\n", "Run", "Type"),
        ("csharp", "class A {\n  void Run() {\n    var x = factory.This();\n  }\n}\n", "Run", "This"),
        ("perl", "sub run {\n  my $self = shift;\n  $self->Warn('x');\n}\n", "run", "Warn"),
    ],
)
def test_case_sensitive_ignore_keeps_capitalised_callee(lang, code, fn, callee):
    assert callee in _calls(lang, code)[fn]


def test_case_insensitive_ignore_folds():
    # powershell is `identifier_case: insensitive`: `Return`/`RETURN` are the keyword.
    calls = _calls("powershell", "function Run {\n  Write-Host 'x'\n  RETURN\n}\n")["Run"]
    assert "RETURN" not in calls and "Write-Host" in calls


def test_cobol_inline_perform_is_not_a_call():
    code = (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n           PERFORM VARYING I FROM 1 BY 1 UNTIL I > 3\n"
        "               DISPLAY I\n           END-PERFORM\n           PERFORM UNTIL X = 1\n"
        "               MOVE 1 TO X\n           END-PERFORM\n           PERFORM WORK-PARA.\n"
        "       WORK-PARA.\n           DISPLAY 'W'.\n"
    )
    calls = _calls("cobol", code)["MAIN-PARA"]
    assert "WORK-PARA" in calls
    # Inline PERFORM names no paragraph; and `END-PERFORM` ends in the verb, so the next
    # statement's first word (`PERFORM`, `MOVE`) must not be read as its target.
    assert not {"VARYING", "UNTIL", "PERFORM", "MOVE"} & set(calls)


def test_agc_tc_q_is_a_return_not_a_call():
    code = "ROUTINE\t\tTC\tHELPER\n\t\tTC\tQ\n"
    calls = [c for v in _calls("agc_assembly", code).values() for c in v]
    assert "Q" not in calls


@pytest.mark.parametrize(
    "lang, code",
    [
        ("kotlin", "fun outer(x: Int) {\n    fun inner(y: Int): Int {\n        return y\n    }\n    go(x)\n}\n"),
        (
            "java",
            "class A {\n  void outer(int x) {\n    class Local {\n      int inner(int y) {\n        return y;\n"
            "      }\n    }\n    go(x);\n  }\n}\n",
        ),
        (
            "scala",
            "object O {\n  def outer(x: Int): Unit = {\n    def inner(y: Int): Int = {\n      y\n    }\n    go(x)\n  }\n}\n",
        ),
    ],
)
def test_nested_declaration_check_covers_the_annotation_free_pattern(lang, code):
    # #3360 (C5) x #3359: the nested-declaration check runs for CALLS_OUT_C_STYLE_NO_ANNOTATION
    # too, so a nested `inner` header is not a call while the real `go(` stays.
    calls = _calls(lang, code)["outer"]
    assert "go" in calls
    assert "inner" not in calls
