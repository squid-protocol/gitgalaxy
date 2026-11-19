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
CLIST strict structural-signature coverage (#8625 slice 6). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology. Every sample is invented.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

CLIST = LANGUAGE_DEFINITIONS["clist"]
CLIST_RULES = CLIST["rules"]

# (signature, a line it must match, a line it must not match)
_SIMPLE_CASES = [
    ("calls_out", "  %PAYROLL &DEPT", "WRITE 50% OFF"),
    ("branch", "  IF &RC = 0 THEN", "WRITE GIFT &NAME"),
    ("args", "PROC 1 NAME KEYWORD(ALL)", "WRITE PROC 1 NAME"),
    ("structural_boundaries", "  END", "ENDING = 1"),
    ("func_start", "LOOP: WRITE &I", "WRITE a:b"),
    ("safety", "  ERROR DO", "ERRORS = 1"),
    ("safety_bypasses", "  GOTO DONE", "GOTOX = 1"),
    ("high_risk_execution", "  EXIT CODE(8)", "EXIT: WRITE X"),
    ("io", "  READ &ANSWER", "WRITE_ALL = 1"),
    ("state_mutation", "  SET &COUNT = &COUNT + 1", "SET COUNT = 1"),
    ("dead_code", "/* SET &X = 1 */", "/* just a note */"),
    ("doc", "/* PURPOSE: list the datasets */", "/* nothing documented */"),
    ("ui_framework", "  ISPEXEC DISPLAY PANEL(MAIN)", "ISPEXEC SELECT CMD(X)"),
    ("globals", "  GLOBAL TOTAL", "GLOBALS = 1"),
    ("ownership", "/* Author: J Doe */", "/* Author:: x */"),
    ("planned_debt", "/* TODO fix the allocation */", "/* done */"),
    ("fragile_debt", "/* HACK: temp dataset name */", "/* fine */"),
    ("spec_exposure", "/* [SPEC-12] */", "/* [other] */"),
    ("telemetry", "  CONTROL MSG LIST", "CONTROL MAIN"),
    ("debug_prints", "  WRITE HELLO", "READ &X"),
    ("panics_and_aborts", "  EXIT", "EXIT: WRITE X"),
    ("cleanup", "  FREE FILE(IN)", "FREEZE = 1"),
    ("time_date_logic", "  SET &D = &SYSDATE", "&SYSUID"),
    ("ipc_rpc_bridges", "  %WORKER", "  WRITE X"),
]


@pytest.mark.parametrize(("signature", "positive", "negative"), _SIMPLE_CASES)
def test_clist_signature_positive_and_negative(signature, positive, negative):
    pattern = CLIST_RULES[signature]
    assert pattern is not None, f"clist's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"clist {signature!r} failed its positive case: {positive!r}"
    assert not pattern.search(negative), f"clist {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _SIMPLE_CASES}
    live = {k for k, v in CLIST_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


def test_clist_registration():
    assert CLIST["extensions"] == [".clist"]
    assert CLIST["lexical_family"] == "standard_block"
    assert CLIST["case_insensitive_imports"] is True
    assert "identifier_case" not in CLIST_RULES  # a helper key at rules level would be compiled as a regex
    assert set(CLIST["library_directory_suffixes"]) == {"clist", "clistlib", "sysproc"}


def test_clist_none_keys_stay_none():
    # constructs CLIST has no analogue of: a rule here would be a false signal on every member.
    for key in ("class_start", "import", "_dependency_capture", "api", "concurrency", "closures", "generics"):
        assert CLIST_RULES[key] is None, key
    # credentials come from the security lens (mainframe_secrets), never from a per-language rule.
    assert CLIST_RULES["hardcoded_secrets"] is None


def test_clist_names_are_case_blind():
    assert CLIST_RULES["branch"].search("if &rc = 0 then")
    assert CLIST_RULES["func_start"].search("loop: write &i")
    assert CLIST_RULES["calls_out"].search("syscall cleanup_dsn").group(1) == "cleanup_dsn"


def test_clist_calls_out_captures_the_callee():
    pattern = CLIST_RULES["calls_out"]
    assert pattern.search("  %PAYROLL &DEPT").group(1) == "PAYROLL"
    assert pattern.search("  SYSCALL SUBA 1").group(1) == "SUBA"
    assert pattern.search("  SET &X = &STR(100%DONE)") is None  # an `&STR(` or digit-% is not a call


def test_clist_do_group_is_not_a_branch_but_loops_are():
    pattern = CLIST_RULES["branch"]
    assert not pattern.search("DO")
    assert pattern.search("DO WHILE &I < 5")
    assert pattern.search("DO UNTIL &DONE = YES")
    assert pattern.search("DO &I = 1 TO 5")
    assert pattern.search("SELECT\nWHEN (&A = 1) SET &B = 2\nOTHERWISE")


def test_clist_goto_is_the_bypass_and_error_off_disables_the_handler():
    pattern = CLIST_RULES["safety_bypasses"]
    assert pattern.search("ERROR OFF")
    assert pattern.search("ATTN OFF")
    assert pattern.search("CONTROL NOFLUSH")
    assert not pattern.search("ERROR DO")
    assert CLIST_RULES["safety"].search("ERROR DO")


def test_clist_comments_are_shielded_from_rules():
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "/* GOTO NOWHERE */\nWRITE HELLO\nSET &X = 1\n"
    streams = prism.split_streams(sample, "clist")
    assert not CLIST_RULES["safety_bypasses"].search(streams["code_stream"])
    assert "GOTO NOWHERE" in streams["comment_stream"]
    assert CLIST_RULES["state_mutation"].search(streams["code_stream"])


_N = 5000


@pytest.mark.parametrize(
    ("signature", "payload"),
    [
        ("func_start", "A" * _N + ":"),
        ("func_start", " " * _N + "A"),
        ("calls_out", "SYSCALL" + " " * _N),
        ("calls_out", "%" + "A" * _N),
        ("args", "PROC 1" + " " * _N),
        ("branch", "DO " + " " * _N + "WHILE"),
        ("branch", "DO &" + "A" * _N),
        ("safety", "ERROR" + " " * _N + "DO"),
        ("safety_bypasses", "CONTROL " + " " * _N + "NOFLUSH"),
        ("safety_bypasses", "CONTROL " + "A " * (_N // 2)),
        ("io", " " * _N + "READ"),
        ("state_mutation", "SET" + " " * _N + "&"),
        ("dead_code", "/*" + " " * _N + "SET"),
        ("dead_code", "/* IF " + "A " * (_N // 2)),
        ("ui_framework", "ISPEXEC " + "A" * _N),
        ("globals", "&SYS" + "A" * _N),
        ("ownership", "/* Author: " + " " * _N),
        ("telemetry", "CONTROL " + "A " * (_N // 2)),
        ("ipc_rpc_bridges", "%" + "A" * _N),
        ("time_date_logic", "&SYS" + "A" * _N),
    ],
)
def test_clist_redos_immunity(signature, payload):
    assert_redos_immune(CLIST_RULES[signature], payload, timeout_sec=3.0)
