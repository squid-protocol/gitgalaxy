"""
#6454 (calls_out contract C3, docs/calls_out_rule_contract.md): Dart calls with a type-argument
list between the callee and its `(`: `findAncestorStateOfType<T>()`, `NotificationListener<T>(...)`,
`EnumProperty<Foo>(...)`, `a!.push<T>(x)`. Dart used the plain `name(` pattern, which skipped the
`<...>`; it now uses `CALLS_OUT_DART` (the #4124 JVM pattern with the
`@Name(` annotation guard, plus nullable type arguments).

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_DART

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _callees(code: str) -> set[str]:
    funcs = StructuralExtractor("dart", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    out: set[str] = set()
    for f in funcs:
        out.update(f["calls_out_to"])
    return out


def _wrap(body: str) -> str:
    return "class W {\n  void run() {\n" + body + "\n  }\n}\n"


def test_dart_uses_the_generic_pattern():
    assert LANGUAGE_DEFINITIONS["dart"]["rules"]["calls_out"] is CALLS_OUT_DART


@pytest.mark.parametrize(
    "stmt, callee",
    [
        ("    ctx.findAncestorStateOfType<ScrollableState>();", "findAncestorStateOfType"),
        ("    return NotificationListener<ScrollNotification>(child: c);", "NotificationListener"),
        ("    final p = EnumProperty<TextAlign>('a', v);", "EnumProperty"),
        ("    final m = Map<String, List<int>>();", "Map"),  # one nesting level
        ("    nav!.push<T>(route);", "push"),  # the bang form
        ("    xs.fold<int>(0, (a, b) => a + b);", "fold"),
        ("    final n = ValueNotifier<String?>(null);", "ValueNotifier"),  # nullable argument
        ("    final c = Completer<Map<String, T?>?>();", "Completer"),
        ("    plain(x);", "plain"),
    ],
)
def test_generic_call_is_captured(stmt, callee):
    assert callee in _callees(_wrap(stmt))


@pytest.mark.parametrize(
    "stmt, name",
    [
        ("    @Deprecated('x') var y = 1;", "Deprecated"),  # C1: an annotation is a declaration
        ("    final b = a < b > (c);", "a"),  # a comparison with blanks never opens a list
        ("    final b = x<y || z>(w);", "x"),  # `|` never inside a type-argument list
        ("    final b = a<b ? c : d>(e);", "a"),  # a ternary: `:` never inside a list
    ],
)
def test_annotation_and_comparison_shapes_are_not_calls(stmt, name):
    assert name not in _callees(_wrap(stmt))


def test_generic_type_without_call_is_not_a_call():
    assert "List" not in _callees(_wrap("    final List<int> xs = [];"))


def test_pattern_is_redos_immune():
    for payload in ("a<" + "b<" * 300, "a<" + "b, " * 400):
        assert_redos_immune(CALLS_OUT_DART, payload)
