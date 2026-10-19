"""acs strict structural-signature coverage (#5465): routing, positive/negative rule tables, ReDoS sweep."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

ACS = LANGUAGE_DEFINITIONS["acs"]
RULES = ACS["rules"]

SAMPLE = '#include "zcommon.acs"\n\nscript 1 (int tag) NET\n{\n  Delay(35);\n  terminate;\n}\n'


def test_acs_routes_to_acs():
    lang, _, _ = LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus("wadsrc/strifehelp.acs", SAMPLE)
    assert lang == "acs"


def test_identity():
    assert ACS["extensions"] == [".acs"]
    assert ACS["lexical_family"] == "standard_block"


@pytest.mark.parametrize(
    ("rule", "text", "first"),
    [
        ("func_start", "script 1 (void)\n{\n", "1"),
        ("func_start", "script 7 ENTER\n{\n", "7"),
        ("func_start", 'script "Open Door" (int tag) CLIENTSIDE\n{\n', '"Open Door"'),
        ("func_start", "script Boom (void)\n{\n", "Boom"),
        ("func_start", "script << 0 >> (int type, int tag)\n{\n", "<< 0 >>"),
        ("func_start", "SCRIPT 2 OPEN\n{\n", "2"),
        ("func_start", "function int Add(int a, int b)\n{\n", "Add"),
        ("func_start", "function void Spawn(void)\n{\n", "Spawn"),
        ("args", "script 1 (int a, int b)\n{\n", "(int a, int b)"),
        ("args", "function int Add(int a, int b)\n{\n", "(int a, int b)"),
        ("api", "script 4 (void)\n", "4"),
        ("_dependency_capture", '#include "zcommon.acs"\n', "zcommon.acs"),
        ("_dependency_capture", '#import "lib.acs"\n', "lib.acs"),
    ],
)
def test_rule_positive(rule, text, first):
    m = RULES[rule].search(text)
    assert m is not None, f"{rule} missed {text!r}"
    assert first in m.groups() or first == m.group(0)


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("func_start", '  Print(s:"script 1");\n'),  # string content, not a header
        ("func_start", "  Add(1, 2);\n"),  # call statement
        ("func_start", "// script 1\n"),
        ("func_start", "  functional = 1;\n"),
        ("_dependency_capture", "#include <not_quoted>\n"),
        ("listeners", 'script "Open Door" (int tag)\n'),  # OPEN inside the quoted name is not a script type
        ("events", 'script "Net Door" (void)\n'),
        ("cleanup", "  Thing_Spawn(1);\n"),
    ],
)
def test_rule_negative(rule, text):
    assert RULES[rule].search(text) is None


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("branch", "if (a && b) {}"),
        ("structural_boundaries", "terminate;"),
        ("io", 'SetCVar("x", 1);'),
        ("debug_prints", 'Print(s:"hi");'),
        ("panics_and_aborts", "terminate;"),
        ("bitwise_ops", "a = b << 2;"),
        ("cleanup", "Thing_Remove(5);"),
        ("listeners", "script 7 ENTER\n{"),
        ("listeners", "script 9 (void) DEATH\n{"),
        ("events", "script 1 (void) NET\n{"),
        ("concurrency", "Delay(35);"),
        ("thread_sleeps", "Delay(35);"),
        ("macros", "#define VDOORSPEED 16"),
        ("globals", "global int 3:Score;"),
        ("time_date_logic", "x = Timer();"),
        ("ipc_rpc_bridges", 'ACS_NamedExecute("x", 0);'),
        ("system_config_mutation", "SetGravity(0.5);"),
        ("ui_framework", 'HudMessage(s:"x"; HUDMSG_PLAIN, 0, CR_RED, 1.5, 1.5, 3.0);'),
    ],
)
def test_rule_fires(rule, text):
    assert RULES[rule].search(text) is not None


@pytest.mark.parametrize(
    "rule",
    [
        "class_start",
        "safety_bypasses",
        "high_risk_execution",
        "doc",
        "test",
        "closures",
        "generics",
        "decorators",
        "pointers",
        "memory_alloc",
        "inline_asm",
        "telemetry",
        "sync_locks",
    ],
)
def test_absent_signals_are_explicit_none(rule):
    assert rule in RULES and RULES[rule] is None


def test_redos_sweep():
    payloads = {
        "func_start": "script " * 50000 + '"',
        "args": "script 1 (" + "(" * 20000,
        "api": "script " * 50000,
        "listeners": "script 1 " + "(" * 50000,
        "events": "script 1 (" + "a" * 50000,
    }
    for rule, payload in payloads.items():
        assert_redos_immune(RULES[rule], payload, timeout_sec=3.0)
    assert_redos_immune(RULES["func_start"], "function " + "a " * 50000, timeout_sec=3.0)
