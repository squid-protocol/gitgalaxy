"""zscript strict structural-signature coverage (#5465): routing, positive/negative rule tables, ReDoS sweep."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

ZS = LANGUAGE_DEFINITIONS["zscript"]
RULES = ZS["rules"]

SAMPLE = '#include "zscript/base.zs"\nclass Imp : Actor\n{\n  void Tick()\n  {\n    Super.Tick();\n  }\n}\n'


def test_zs_routes_to_zscript():
    lang, _, _ = LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus("zscript/imp.zs", SAMPLE)
    assert lang == "zscript"


def test_identity():
    assert ZS["extensions"] == [".zs"]
    assert ZS["identifier_case"] == "insensitive"
    assert ZS["lexical_family"] == "standard_block"


@pytest.mark.parametrize(
    ("rule", "text", "first"),
    [
        ("func_start", "  override void Tick()\n  {\n", "Tick"),
        ("func_start", "  virtual ui void Draw(int x, bool y)\n  {\n", "Draw"),
        ("func_start", "  static Class<Actor> Pick(Name n) const\n  {\n", "Pick"),
        ("func_start", "  int, bool Check()\n  {\n", "Check"),
        ("func_start", '  deprecated("3.8", "Use X() instead") void Old()\n  {\n', "Old"),
        ("func_start", "  Array<Array<int> > Grid()\n  {\n", "Grid"),
        ("args", "  void Fire(int a, Array<int> b)\n  {\n", "Fire"),
        ("class_start", "class Imp : Actor\n{", "Imp"),
        ("class_start", "class Service abstract\n{", "Service"),
        ("class_start", "struct Wads // comment\n{", "Wads"),
        ("class_start", "extend class Actor\n{", "Actor"),
        ("class_start", "enum EFlags\n{", "EFlags"),
        ("class_start", 'class Old deprecated("3.8", "x") : Actor\n{', "Old"),
        ("_dependency_capture", '#include "zscript/base.zs"\n', "zscript/base.zs"),
    ],
)
def test_rule_positive(rule, text, first):
    m = RULES[rule].search(text)
    assert m is not None, f"{rule} missed {text!r}"
    assert first in m.groups() or first == m.group(0)


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("func_start", "  native void Tick();\n"),  # bodiless declaration
        ("func_start", "  abstract void Think();\n"),
        ("func_start", "  A_Log(x);\n"),  # call statement
        ("func_start", "  return Foo(x);\n"),
        ("func_start", "  else if (x) {\n"),
        ("class_start", "// class Foo\n"),
        ("class_start", "  x = classify(y);\n"),
        ("_dependency_capture", "#include <not_quoted>\n"),
        ("bitwise_ops", "Array<Array<int>> a;"),  # closing generics are not a shift
        ("cleanup", "  void Destroy()\n"),  # declaration, not a call site
    ],
)
def test_rule_negative(rule, text):
    assert RULES[rule].search(text) is None


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("branch", "if (a && b) {}"),
        ("structural_boundaries", "return 1;"),
        ("safety_bypasses", "clearscope int Get()"),
        ("io", "CVar.GetCVar('x')"),
        ("debug_prints", 'A_Log("hi");'),
        ("panics_and_aborts", 'ThrowAbortException("x");'),
        ("memory_alloc", "new('Actor')"),
        ("explicit_casts", "Class<Actor>(x)"),
        ("bitwise_ops", "a = b << 2;"),
        ("immutability_locks", "const X = 1;"),
        ("encapsulation", "private int x;"),
        ("cleanup", "Destroy();"),
        ("listeners", "  override void WorldTick()"),
        ("listeners", "  virtual ui void RenderOverlay(RenderEvent e)"),
        ("events", 'EventHandler.SendNetworkEvent("x");'),
        ("time_date_logic", "Level.time"),
        ("ipc_rpc_bridges", 'CallACS("x");'),
        ("system_config_mutation", "cv.SetInt(3);"),
    ],
)
def test_rule_fires(rule, text):
    assert RULES[rule].search(text) is not None


@pytest.mark.parametrize(
    "rule",
    ["high_risk_execution", "doc", "test", "concurrency", "closures", "macros", "pointers", "inline_asm", "telemetry"],
)
def test_absent_signals_are_explicit_none(rule):
    assert rule in RULES and RULES[rule] is None


def test_redos_sweep():
    payloads = {
        "func_start": "  " + "override " * 50000 + "void f(",
        "args": "  void f(" + "(" * 20000,
        "class_start": "extend " * 50000 + "class",
        "api": "  " + "static " * 50000 + "void f",
    }
    for rule, payload in payloads.items():
        assert_redos_immune(RULES[rule], payload, timeout_sec=3.0)
    assert_redos_immune(RULES["func_start"], '  deprecated("' + "a" * 50000, timeout_sec=3.0)
    assert_redos_immune(RULES["func_start"], "  Array<" * 20000, timeout_sec=3.0)
