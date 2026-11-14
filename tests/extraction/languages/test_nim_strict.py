"""
Nim (#6572): `.nim` / `.nims` / `.nimble` are mapped, a `proc` / `func` / `method` / `iterator` / `template` /
`macro` / `converter` definition is a func_start sliced by indentation, an `object` / `enum` / `tuple` / `concept` /
`distinct` type is a class_start, and `import` / `from` / `include` name their module in `_dependency_capture`
(no import is read from a `#` comment, a `#[ ]#` block or a string). Every snippet is real Nim.
"""

import re
import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

NIM = LANGUAGE_DEFINITIONS["nim"]
RULES = NIM["rules"]

SRC = (
    "# import hidden\n"
    "import std/os, strutils\n"
    "\n"
    "proc area*(r: float, s: float): float =\n"
    "  let k = 3.14\n"
    "  result = k * r * s\n"
    "\n"
    "func twice(x: int): int = x * 2\n"
    "\n"
    "iterator items(n: int): int =\n"
    "  for i in 0 ..< n:\n"
    "    yield i\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("nim", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _starts(content: str) -> list[str]:
    return [m.group(1) for m in RULES["func_start"].finditer(content)]


def test_nim_extensions_route_to_nim():
    for name in ("src/a.nim", "tasks.nims", "pkg.nimble"):
        assert _route(name, SRC) == "nim", name


def test_routines_are_units_with_indentation_spans():
    assert _starts(SRC) == ["area", "twice", "items"]
    assert [m.group(1) for m in RULES["args"].finditer(SRC)] == ["r: float, s: float", "x: int", "n: int"]
    spans = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"]}
    assert spans["area"][0] == 4 and spans["area"][1] >= 6
    assert spans["items"][0] == 10


def test_func_start_forms():
    src = (
        "proc a() = discard\n"
        "proc b*[T](x: T): T = x\n"
        "func `+`*(a, b: V): V = a\n"
        "method m(self: Base) {.base.} =\n  discard\n"
        "template t(body: untyped) =\n  body\n"
        "macro mm(x: untyped): untyped =\n  x\n"
        "converter toS(x: int): string = $x\n"
        "proc forward(x: int): int\n"
        "  proc nested(y: int) =\n    discard\n"
        "proc `[]=`*(s: var S, i: int, v: int) = discard\n"
    )
    assert _starts(src) == ["a", "b", "`+`", "m", "t", "mm", "toS", "forward", "nested", "`[]=`"]


def test_proc_types_and_non_definitions_are_not_units():
    src = (
        "type Cb = proc (x: int): int\n"
        "var f: proc(x: int)\n"
        "let g = proc (x: int): int = x\n"
        "# proc commented() = discard\n"
        "const proc_name = 1\n"
        'echo "proc fake() ="\n'
    )
    assert _starts(src) == []


def test_classes_are_found():
    src = (
        "type\n"
        "  Point* = object\n"
        "    x, y: int\n"
        "  Color = enum red, green\n"
        "  Pair[T] = tuple[a, b: T]\n"
        "  Node = ref object of RootObj\n"
        "  Id = distinct int\n"
        "  Alias = int\n"
        "  Sized {.packed.} = object\n"
        "type Solo* = ptr object\n"
        "  Showable = concept x\n"
        "var notAType = object\n"
    )
    assert [m.group(1) for m in RULES["class_start"].finditer(src)] == [
        "Point",
        "Color",
        "Pair",
        "Node",
        "Id",
        "Sized",
        "Solo",
        "Showable",
    ]


def test_dependencies_capture_the_target():
    src = (
        "import std/os, strutils\n"
        "import std/[tables, sets]\n"
        "from strutils import split\n"
        "include ../common/defs\n"
        "import mypkg\n"
        "  import indented\n"
        "importantThing = 1\n"
    )
    got = [m.group(1) for m in RULES["_dependency_capture"].finditer(src)]
    assert got == ["std/os", "std", "strutils", "../common/defs", "mypkg", "indented"]


def test_import_capture_blank_hides_comments_and_strings():
    src = (
        "# import Hidden1\n"
        "#[ block\n   import Hidden2\n]#\n"
        '"""\nimport Hidden3\n"""\n'
        'let s = "import Hidden4"\n'
        "import real\n"
    )
    blank = re.compile(NIM["import_capture_blank"])
    kept = blank.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), src)
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(kept)] == ["real"]


def test_safety_bypasses_and_high_risk():
    src = 'cast[int](p)\nunsafeAddr x\n{.push checks: off.}\n{.emit: "x".}\n{.warning[UnusedImport]: off.}\n'
    assert _hits("safety_bypasses", src) == [
        "cast[",
        "unsafeAddr",
        "{.push checks: off",
        "{.emit",
        "{.warning[UnusedImport]: off",
    ]
    assert _hits("high_risk_execution", "execCmd(c)\nexecProcess(c)\nstaticExec(c)\n") == [
        "execCmd",
        "execProcess",
        "staticExec",
    ]


def test_branches_and_case_arms():
    src = (
        "if a:\n  discard\nelif b:\n  discard\ncase x\nof 1: discard\ntype D = object of RootObj\nfor i in s: discard\n"
    )
    assert _hits("branch", src) == ["if", "elif", "case", "of", "for"]


def test_state_mutation_and_concurrency():
    assert _hits("state_mutation", "x += 1\ninc n\ns.add(1)\nif a <= b: discard\nif a == b: discard\n") == [
        "+=",
        "inc",
        ".add(",
    ]
    assert _hits("concurrency", "let t = spawn work()\nawait fetch()\nwithLock l:\n  discard\n") == [
        "spawn",
        "await",
        "withLock",
    ]


def test_doc_pragmas_and_generics():
    assert _hits("doc", "## documented\n### banner\n# plain\n") == ["##"]
    assert _hits("decorators", "proc f() {.inline.} = discard\nproc g() {.raises: [].} = discard\n") == [
        "{.inline",
        "{.raises",
    ]
    assert len(_hits("generics", "proc f[T](x: T) = discard\nvar s: seq[int]\ntype B[T] = object\n")) == 2


def test_every_rule_survives_pathological_input():
    payloads = [
        "proc " + "a" * 20000 + "\n",
        "proc f" + "[" * 5000 + "\n",
        "proc f(" + "a, " * 5000 + "\n",
        "proc `" + "a" * 20000 + "\n",
        "type " + "A" * 20000 + " = \n",
        "type A[" + "T, " * 5000 + "\n",
        "import " + "a/" * 5000 + "\n",
        "#[" + "import " * 5000 + "\n",
        '"' + "a" * 30000 + "\n",
        "proc f " + "*" * 5000 + "\n",
        "  " * 5000 + "proc f\n",
        "{." + "a" * 20000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
    assert re.compile(NIM["import_capture_blank"]).sub("", "#[" + "a" * 30000) is not None
