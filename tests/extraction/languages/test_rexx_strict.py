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
REXX strict structural-signature coverage (#2504). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology.
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

REXX = LANGUAGE_DEFINITIONS["rexx"]
REXX_RULES = REXX["rules"]

_REXX_SIMPLE_CASES = [
    ("branch", "  IF RC ~= 0 THEN", "  end   /* closer, #2822 C2 */"),
    ("branch", "  SELECT;", "  SELECT = 1"),
    ("branch", "  DO WHILE I < MAX", "  DO_WHILE = 1"),
    ("branch", "  DO I = 1 TO 10", "  DO_I = 1"),
    ("args", "  PARSE UPPER ARG DSN MEM", "  ARG(1)"),
    ("args", "  USE STRICT ARG DSN", "  SAY ARG"),
    ("structural_boundaries", "  RETURN", "  RETURNING = 1"),
    ("structural_boundaries", "  CALL SUBRTN", "  CALL ON ERROR"),
    ("func_start", "PROBE_IO:", "  PROBE_IO = 1"),
    ("func_start", "::ROUTINE HANDLER", "  ::CLASS HANDLER"),
    ("class_start", "::CLASS ACCTPGM", "  ::ROUTINE ACCTPGM"),
    ("safety", "  SIGNAL ON SYNTAX", "  SIGNAL MYLABEL"),
    ("safety", "  IF RC ~= 0 THEN", "  RC = 0"),
    ("safety_bypasses", "  SIGNAL OFF HALT", "  SIGNAL ON HALT"),
    ("safety_bypasses", "  SIGNAL DONE", "  SIGNAL ON SYNTAX"),
    ("safety_bypasses", "  SIGNAL VALUE EXPR", "  SIGNAL ON SYNTAX"),
    ("high_risk_execution", "  INTERPRET CMD", "  interpreter = 'REGINA'"),
    ("high_risk_execution", "  EXIT 0", "  EXIT:"),
    ("io", "  EXECIO 1 DISKR INDD", "  x = 'DISKR INDD'"),
    ("io", "  LINEIN(1)", "  X = LINEIN"),
    ("io", "  PARSE PULL DATA", "  PARSE ARG DATA"),
    ("io", "  QUEUE 'LINE'", "  QUEUE = 1"),
    ("api", "::ROUTINE MYRTN PUBLIC", "::ROUTINE MYRTN PRIVATE"),
    ("state_mutation", "  RC = 0", "  IF RC = 0 THEN"),
    ("state_mutation", "  REC.1 = 'DATA'", "  REC.1 == 'DATA'"),
    ("state_mutation", "  PARSE VAR DATA A B", "  PARSE ARG DATA"),
    ("dead_code", "/* IF RC ~= 0 THEN */", "/* THE RC FROM THE COMMAND */"),
    ("dead_code", "-- RC = 0", "-- THE RC WAS ZERO"),
    ("doc", "/** refresh the cache\n   before posting */", "/** BANNER **/"),
    ("doc", "/* PURPOSE: MAIN PROGRAM */", "/* TEST PROGRAM */"),
    ("ui_framework", "  ADDRESS ISPEXEC 'DISPLAY PANEL(P1)'", "  ADDRESS TSO"),
    ("globals", "  PROCEDURE EXPOSE RC", "  PROCEDURE"),
    ("globals", "  SYSVAR('SYSUID')", "  X = SYSVAR"),
    ("globals", "  .ENVIRONMENT", "  A.ENVIRONMENT"),
    ("scientific", "  RANDOM(1)", "  X = RANDOM"),
    ("reflection_metaprogramming", "  VALUE('X')", "  X = VALUE"),
    ("import", "::REQUIRES 'SUBRTN.REXX'", "::CLASS SUBRTN"),
    ("_dependency_capture", "::REQUIRES 'SUBRTN.REXX'", "::REQUIRES"),
    ("ownership", "/* @author: MAINFRAME TEAM */", "/* THE AUTHOR IS UNKNOWN */"),
    ("planned_debt", "/* TODO: FIX RC CHECK */", "/* FIX RC CHECK */"),
    ("fragile_debt", "/* HACK: BYPASS SECURITY */", "/* BYPASS SECURITY */"),
    ("spec_exposure", "/* [SPEC-123] */", "/* SPECIFICATION 123 */"),
    ("pointers", "  STORAGE(100)", "  X = STORAGE"),
    ("telemetry", "  TRACE I", "  TRACE(I)"),
    ("debug_prints", "  SAY 'JOB COMPLETE'", "  sayings = 1"),
    ("explicit_casts", "  C2D(1)", "  X = C2D"),
    ("panics_and_aborts", "  EXIT 0", "  EXIT:"),
    ("panics_and_aborts", "  RAISE ERROR", "  RAISE = 1"),
    ("thread_sleeps", "  SYSSLEEP(1)", "  X = SYSSLEEP"),
    ("bitwise_ops", "  BITAND(1)", "  X = BITAND"),
    ("immutability_locks", "::CONSTANT 1", "::CLASS 1"),
    ("cleanup", "  DROP WORKAREA", "  WORKAREA = DROP"),
    ("cleanup", "  FREE FI(INDD)", "  X = FREE"),
    ("encapsulation", "::ROUTINE SUBRTN PRIVATE", "::ROUTINE SUBRTN PUBLIC"),
    ("time_date_logic", "  TIME()", "  X = TIME"),
    ("ipc_rpc_bridges", "  ADDRESS TSO", "  ADDRESS()"),
]


@pytest.mark.parametrize(("signature", "positive", "negative"), _REXX_SIMPLE_CASES)
def test_rexx_signature_positive_and_negative(signature, positive, negative):
    pattern = REXX_RULES[signature]
    assert pattern is not None, f"rexx's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"rexx {signature!r} failed its documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"rexx {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _REXX_SIMPLE_CASES}
    live = {k for k, v in REXX_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


_BASELINE_KEYS = [
    "branch",
    "args",
    "structural_boundaries",
    "func_start",
    "class_start",
    "safety",
    "safety_bypasses",
    "high_risk_execution",
    "io",
    "api",
    "state_mutation",
    "dead_code",
    "doc",
    "test",
    "concurrency",
    "ui_framework",
    "closures",
    "globals",
    "decorators",
    "generics",
    "comprehensions",
    "scientific",
    "reflection_metaprogramming",
    "import",
    "_dependency_capture",
    "ownership",
    "planned_debt",
    "fragile_debt",
    "hardcoded_secrets",
    "spec_exposure",
    "ssr_boundaries",
    "events",
    "dependency_injection",
    "macros",
    "pointers",
    "memory_alloc",
    "inline_asm",
    "telemetry",
    "debug_prints",
    "explicit_casts",
    "panics_and_aborts",
    "thread_sleeps",
    "bitwise_ops",
    "sync_locks",
    "immutability_locks",
    "cleanup",
    "encapsulation",
    "listeners",
    "test_skip",
    "serialization_parsing",
    "regex_execution",
    "time_date_logic",
    "ipc_rpc_bridges",
    "auth_middleware",
]

_EXPECTED_NONE_KEYS = {
    "test",
    "concurrency",
    "closures",
    "decorators",
    "generics",
    "comprehensions",
    "memory_alloc",
    "inline_asm",
    "macros",
    "dependency_injection",
    "ssr_boundaries",
    "events",
    "listeners",
    "sync_locks",
    "test_skip",
    "serialization_parsing",
    "regex_execution",
    "hardcoded_secrets",
    "auth_middleware",
}


def test_rexx_schema_completeness():
    baseline = set(_BASELINE_KEYS)
    missing = baseline - set(REXX_RULES)
    assert not missing, f"rexx rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(REXX_RULES) - baseline - {"_visibility_export_list"}
    assert extra == set(), f"unexpected non-baseline keys: {extra}"


def test_rexx_none_keys_are_the_intended_set():
    actual_none = {k for k, v in REXX_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


def test_rexx_registration():
    assert set(REXX["extensions"]) == {".rexx", ".exec", ".cmd"}
    assert REXX["lexical_family"] == "recursive_block_rexx"
    assert REXX["case_insensitive_imports"] is True
    assert "invocation_model" not in REXX
    assert "invocation_model" not in REXX_RULES
    assert ".cmd" in LENS_CONFIG["COLLISION_FREQUENCIES"]
    assert ".cmd" in LANGUAGE_DEFINITIONS["batch"]["extensions"]
    assert REXX.get("internal_discriminator") is not None
    assert LANGUAGE_DEFINITIONS["batch"].get("internal_discriminator") is not None


def test_cmd_collision_resolves_correctly():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})

    # real REXX content named .cmd resolves rexx
    lang, _, _ = detector.focus("src/build.cmd", "/* REXX */\nSAY 'HELLO'")
    assert lang == "rexx"

    # batch content named .cmd resolves batch
    lang, _, _ = detector.focus("src/run.cmd", "@echo off\nsetlocal\ngoto :label")
    assert lang == "batch"

    # .rexx and .exec resolve rexx directly
    lang, _, _ = detector.focus("src/test.rexx", "SAY 'HELLO'")
    assert lang == "rexx"
    lang, _, _ = detector.focus("src/test.exec", "SAY 'HELLO'")
    assert lang == "rexx"

    # x = 'rem = a // 7' style REXX with rem-variable lines must NOT flip to batch
    lang, _, _ = detector.focus("src/rem.cmd", "/* REXX */\nx = 'rem = a // 7'\nrem = 1\n")
    assert lang == "rexx"


def test_rexx_nested_comment_shielding():
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = (
        "/* outer /* inner */ still comment */ x = a // b\n"
        "-- ooRexx line comment\n"
        "say 'not /* a comment'\n"
        "say 'don''t'\n"
        'say "-- inside string"\n'
    )
    streams = prism.split_streams(sample, "rexx")
    code = streams["code_stream"]
    assert "still comment */" not in code
    assert "x = a // b" in code
    assert "-- ooRexx line comment" not in code
    assert "say 'not /* a comment'" in code
    assert "say 'don''t'" in code
    assert 'say "-- inside string"' in code


def test_rexx_address_is_ipc_rpc_bridges():
    assert REXX_RULES["ipc_rpc_bridges"].search("  ADDRESS TSO")
    assert not REXX_RULES["io"].search("  ADDRESS TSO")
    assert not REXX_RULES["ipc_rpc_bridges"].search("  ADDRESS()")


def test_rexx_signal_ownership():
    assert REXX_RULES["safety"].search("  SIGNAL ON SYNTAX")
    assert not REXX_RULES["safety_bypasses"].search("  SIGNAL ON SYNTAX")

    assert REXX_RULES["safety_bypasses"].search("  SIGNAL OFF HALT")
    assert not REXX_RULES["safety"].search("  SIGNAL OFF HALT")

    assert REXX_RULES["safety_bypasses"].search("  SIGNAL DONE")
    assert not REXX_RULES["safety"].search("  SIGNAL DONE")

    assert REXX_RULES["safety_bypasses"].search("  SIGNAL VALUE EXPR")
    assert not REXX_RULES["safety"].search("  SIGNAL VALUE EXPR")


def test_rexx_exit_dual():
    assert REXX_RULES["high_risk_execution"].search("  EXIT 0")
    assert REXX_RULES["panics_and_aborts"].search("  EXIT 0")

    assert not REXX_RULES["high_risk_execution"].search("  SIGNAL EXIT")
    assert not REXX_RULES["panics_and_aborts"].search("  SIGNAL EXIT")

    assert not REXX_RULES["high_risk_execution"].search("  CALL EXIT")
    assert not REXX_RULES["panics_and_aborts"].search("  CALL EXIT")

    assert not REXX_RULES["high_risk_execution"].search("EXIT:")
    assert not REXX_RULES["panics_and_aborts"].search("EXIT:")


def test_rexx_parse_one_owner_per_form():
    assert REXX_RULES["args"].search("  PARSE ARG X")
    assert not REXX_RULES["io"].search("  PARSE ARG X")
    assert not REXX_RULES["state_mutation"].search("  PARSE ARG X")

    assert REXX_RULES["io"].search("  PARSE PULL LINE")
    assert not REXX_RULES["args"].search("  PARSE PULL LINE")
    assert not REXX_RULES["state_mutation"].search("  PARSE PULL LINE")

    assert REXX_RULES["state_mutation"].search("  PARSE VAR A B")
    assert not REXX_RULES["args"].search("  PARSE VAR A B")
    assert not REXX_RULES["io"].search("  PARSE VAR A B")

    assert REXX_RULES["state_mutation"].search("  PARSE VALUE T WITH D")
    assert not REXX_RULES["args"].search("  PARSE VALUE T WITH D")
    assert not REXX_RULES["io"].search("  PARSE VALUE T WITH D")


def test_rexx_state_mutation_anchoring():
    assert REXX_RULES["state_mutation"].search("x = 1")
    assert REXX_RULES["state_mutation"].search("IF A THEN x = 1")

    assert not REXX_RULES["state_mutation"].search("IF x = 1 THEN")
    assert not REXX_RULES["state_mutation"].search("DO i = 1 TO 5")
    assert not REXX_RULES["state_mutation"].search("WHEN n = 0 THEN")

    assert REXX_RULES["state_mutation"].search("rec.1 = 1")
    assert REXX_RULES["state_mutation"].search("stem. = 1")
    assert not REXX_RULES["state_mutation"].search("x == y")


def test_rexx_statement_vs_function():
    assert REXX_RULES["telemetry"].search("  TRACE I")
    assert not REXX_RULES["telemetry"].search("  TRACE(I)")

    assert REXX_RULES["args"].search("  ARG A")
    assert not REXX_RULES["args"].search("  ARG(1)")

    assert REXX_RULES["io"].search("  QUEUE 'A'")
    assert not REXX_RULES["io"].search("  queue = 5")

    assert REXX_RULES["io"].search("  PULL A")
    assert not REXX_RULES["io"].search("  pull = 5")

    assert REXX_RULES["io"].search("  PUSH A")
    assert not REXX_RULES["io"].search("  push = 5")


def test_rexx_caret_anchored_rules_all_set_multiline_flag():
    for key, pattern in REXX_RULES.items():
        if pattern is None or not isinstance(pattern, re.Pattern):
            continue
        if "^" in pattern.pattern.replace("[^", ""):
            assert pattern.flags & re.M, f"rexx {key!r} uses '^' without re.M"
    disc = REXX["internal_discriminator"]
    assert disc.flags & re.M, "internal_discriminator uses '^' without re.M"


def test_rexx_sections_slice_through_mode_a_as_named_units():
    from gitgalaxy.core.detector import StructuralExtractor

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = (
        "dispatch:\n"
        "  SAY 'DISPATCH'\n"
        "  RETURN\n"
        "probe_a:\n"
        "  SAY 'PROBE_A'\n"
        "  RETURN\n"
        "probe_b:\n"
        "  SAY 'PROBE_B'\n"
        "  RETURN\n"
    )
    streams = prism.split_streams(sample, "rexx")
    functions = StructuralExtractor("rexx", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"]
    )["functions"]
    names = {f["name"] for f in functions}
    assert names == {"dispatch", "probe_a", "probe_b"}


def test_rexx_is_in_the_mode_a_dispatch_and_named_class_allowlist():
    from gitgalaxy.core import detector

    assert "rexx" in detector._CLASS_START_NAMED_EXTRACTION_LANGS


def test_rexx_class_start_extracts_named_class():
    m = REXX_RULES["class_start"].search("::CLASS Account")
    assert m and m.group(1) == "Account"


def test_rexx_strings_reach_rules():
    assert REXX_RULES["io"].search('"EXECIO 1 DISKR INDD"')
    assert REXX_RULES["high_risk_execution"].search("'plain interpret decoy text'")


_N = 32000


@pytest.mark.parametrize(
    ("signature", "payload"),
    [
        ("func_start", "A" * _N + ":"),
        ("state_mutation", " " * _N + "X="),
        ("dead_code", "/*" + "A" * _N),
        ("_dependency_capture", "::REQUIRES '" + "A" * _N),
        ("ownership", "/* Author: " + " " * _N),
        ("api", "::ROUTINE A " + "B " * (_N // 2) + "PUBLIC"),
        ("encapsulation", "::ROUTINE A " + "B " * (_N // 2) + "PRIVATE"),
        ("safety_bypasses", "SIGNAL " + " " * _N + "VALUE"),
        ("io", "PARSE " + " " * _N + "PULL"),
        ("branch", "DO " + " " * _N + "WHILE"),
        ("branch", "DO " + "A" * _N),
        ("ui_framework", "ISPEXEC " + "A" * _N),
        ("cleanup", "DROP  " + "A" * _N),
        ("args", "PARSE" + " " * _N + "ARG"),
        ("telemetry", " " * _N + "TRACE"),
        ("ipc_rpc_bridges", " " * _N + "ADDRESS"),
        ("high_risk_execution", "CALL EXIT " * (_N // 10)),
        ("import", "::" + " " * _N + "REQUIRES"),
        ("state_mutation", "x" + "." * _N + "="),
        ("func_start", "::ROUTINE " + "A" * _N),
        ("safety", "SIGNAL ON USER " + "A" * _N),
        ("_dependency_capture", "::REQUIRES " + "A" * _N),
    ],
)
def test_rexx_redos_immunity(signature, payload):
    pattern = REXX_RULES[signature]
    assert_redos_immune(pattern, payload, timeout_sec=3.0)


def test_rexx_double_dash_arithmetic_is_the_documented_trade():
    """recursive_block_rexx treats `--` as a line comment (ooRexx/Regina).
    Classic-REXX adjacent double-negation (`5--3`) is therefore truncated at
    the `--` -- the trade languages/rexx.py's lexical_family comment records
    as accepted (vanishingly rare in real source vs. ubiquitous ooRexx `--`
    comments). This test PINS the trade so a future change is deliberate."""
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    code = prism.split_streams("x = 5--3\n", "rexx")["code_stream"]
    assert "x = 5" in code
    assert "3" not in code


def test_rexx_when_rc_branch_safety_dual_is_deliberate():
    """`when rc = 8 then` is branch's WHEN arm AND safety's response test --
    the pli IF/IF-SQLCODE precedent (#2869), both rules counting the same
    token on purpose."""
    stmt = "  when rc = 8 then nop"
    assert REXX_RULES["branch"].search(stmt)
    assert REXX_RULES["safety"].search(stmt)
