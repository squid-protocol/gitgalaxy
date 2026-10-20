"""
#5639: an Objective-C++ out-of-line C++ member definition is a unit.

`bool Cls::Method() {`, a constructor `Cls::Cls()` (with or without an initializer list) and a destructor
`Cls::~Cls()` each start a unit named by the last component, so the message sends in their bodies are attributed
to them instead of to whichever unit came before. A qualified call statement and a prototype are not units.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _units(code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


@pytest.mark.parametrize(
    "header, name",
    [
        ("bool Cls::IsFullscreen()", "IsFullscreen"),
        ("static NSColor* Cls::Make(int c)", "Make"),
        ("void ns::Cls::Run(int a,\n int b)", "Run"),
        ("Cls::Cls()", "Cls"),
        ("Cls::~Cls()", "~Cls"),
        ("Cls::Cls(void*, const bool fs)\n: m_window([NSWindow alloc])\n, m_fs(fs)", "Cls"),
    ],
)
def test_member_definition_is_a_unit_with_its_sends(header, name):
    code = f"{header}\n{{\n    [m_window update];\n}}\n\nvoid Other()\n{{\n}}\n"
    units = _units(code)
    assert "update" in units[name]
    assert "update" not in units["Other"]


def test_sends_after_a_class_body_are_not_swallowed_by_the_previous_unit():
    code = "void First()\n{\n}\n\nbool Cls::Second()\n{\n    return [m_window ping];\n}\n"
    units = _units(code)
    assert "ping" not in units["First"]
    assert units["Second"] == ["ping"]


def test_qualified_call_statement_and_prototype_are_not_units():
    code = "void Run()\n{\n    Cls::Helper(1,\n  2);\n    Cls::Other();\n}\nbool Cls::Proto();\n"
    assert set(_units(code)) == {"Run"}


def test_member_definition_pattern_is_redos_immune():
    rule = LANGUAGE_DEFINITIONS["objective-c"]["rules"]["func_start"]
    assert_redos_immune(rule, "a::" * 4000)
    assert_redos_immune(rule, "a :: " * 4000 + "\n")
