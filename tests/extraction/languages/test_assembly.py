"""
Assembly extraction hardening (epic #813, issue #856). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for assembly in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

ASSEMBLY_RULES = LANGUAGE_DEFINITIONS["assembly"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("main:", "main"),
        ("_start:", "_start"),
        ("my_func:", "my_func"),
        ("  indented_func:", "indented_func"),
        ("func_name.1:", "func_name.1"),
        ("func$name:", "func$name"),
        ("?MyFunc@@:", "?MyFunc@@"),
        ("@MyFunc:", "@MyFunc"),
        (".global_function:", ".global_function"),
        ("_:", "_"),
        ("@:", "@"),
        ("?:", "?"),
        ("a:", "a"),
        ("\t\tmy_func\t\t:", "my_func"),
        ("Long_Function_Name_With_Many_Parts_123$@?:", "Long_Function_Name_With_Many_Parts_123$@?"),
        ("func_with_trailing_spaces  :", "func_with_trailing_spaces"),
    ],
    "invalid": [
        "  mov eax, 1",
        ".L1:",
        ".LBB0_1:",
        "1:",
        "999:",
        "0:",
        ".text:",
        ".data:",
        ".bss:",
        "; main:",
        "# _start:",
        "// func:",
        "func_name",
        "func-name:",
        "func name:",
        "123func:",
        ".Lfunc:",
        ".LC123:",
        ".text_section:",
    ],
    "pathological": [
        ("very_long_function_name_with_lots_of_parts:", "very_long_function_name_with_lots_of_parts"),
        ("func \t\t  :", "func"),
        ("?mang@led$name.123_@:", "?mang@led$name.123_@"),
        ("\t\t .global_but_weird_name$@?:", ".global_but_weird_name$@?"),
        ("  @fastcall_func@123:", "@fastcall_func@123"),
        (" \t\t_Z3fooii:", "_Z3fooii"),  # C++ mangled name
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_assembly_func_start_valid(payload, expected_name):
    assert_valid_match(ASSEMBLY_RULES["func_start"], payload, expected_name, "assembly.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_assembly_func_start_invalid(payload):
    assert_invalid_no_match(ASSEMBLY_RULES["func_start"], payload, "assembly.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_assembly_func_start_pathological(payload, expected_name):
    assert_pathological_match(ASSEMBLY_RULES["func_start"], payload, expected_name, "assembly.func_start")


def test_assembly_func_start_redos_immunity():
    assert_redos_immune(ASSEMBLY_RULES["func_start"], "A" * 100000 + ":", timeout_sec=1.0)


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("mov rdi, 1", "rdi"),
        ("push rsi", "rsi"),
        ("add rdx, rax", "rdx"),
        ("sub rcx, 1", "rcx"),
        ("mov r8, 2", "r8"),
        ("xor r9, r9", "r9"),
        ("ldr x0, [sp]", "x0"),
        ("str w7, [x1]", "w7"),
        ("mov v3.16b, v3.16b", "v3"),
        ("mov xmm0, xmm0", "xmm0"),
        ("mov r0, #1", "r0"),
        ("push {r0, r1, r2, r3}", "r0"),
        ("add x7, x7, #1", "x7"),
        ("mov edi, 1", "edi"),
        ("mov esi, 2", "esi"),
        ("mov edx, 3", "edx"),
        ("mov ecx, 4", "ecx"),
        ("mov r8d, 5", "r8d"),
        ("mov r9d, 6", "r9d"),
        ("mov r8w, 5", "r8w"),
        ("mov r9b, 6", "r9b"),
        ("xor ax, ax", "ax"),
        ("mov al, 1", "al"),
        ("mov ah, 2", "ah"),
        ("mov bl, 3", "bl"),
        ("mov bh, 4", "bh"),
        ("mov cl, 5", "cl"),
        ("mov ch, 6", "ch"),
        ("mov dl, 7", "dl"),
        ("mov dh, 8", "dh"),
        ("mov si, boot", "si"),
        ("mov di, osbase", "di"),
    ],
    "invalid": [
        "mov rax, 1",
        "mov rbx, 2",
        "mov r10, 3",
        "mov r15, 3",
        "ldr x8, [sp]",
        "str w10, [x10]",
        "mov v15.16b, v15.16b",
        "mov xmm15, xmm15",
        "mov r12, 5",
        "ldr x30, [sp]",
        "str w8, [x8]",
        "mov ymm0, ymm0",  # Not supported by current args
        "mov zmm0, zmm0",  # Not supported by current args
        "mov e8, 5",  # (#856 follow-up) fictional register, not a real x86 form
        "mov e9, 6",  # (#856 follow-up) fictional register, not a real x86 form
        "mov sp, 1",
        "mov bp, 1",
        "mov lr, 1",
    ],
    "pathological": [
        ("mov\trdi,\t1", "rdi"),
        ("push\t\t\t rsi", "rsi"),
        ("add  rdx ,  rdx", "rdx"),
        ("sub \t rcx \t , \t 1", "rcx"),
        ("ldr\t\t\t x0\t\t\t,\t\t\t[sp]", "x0"),
        ("\tmov\tr8,2\t", "r8"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_assembly_args_valid(payload, expected_name):
    assert_valid_match(ASSEMBLY_RULES["args"], payload, expected_name, "assembly.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_assembly_args_invalid(payload):
    assert_invalid_no_match(ASSEMBLY_RULES["args"], payload, "assembly.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_assembly_args_pathological(payload, expected_name):
    assert_pathological_match(ASSEMBLY_RULES["args"], payload, expected_name, "assembly.args")


def test_assembly_args_redos_immunity():
    assert_redos_immune(ASSEMBLY_RULES["args"], "mov" + " \t" * 50000 + "rdi", timeout_sec=1.0)


def test_assembly_args_phantom_register_vs_real_r8_r9_suffixes():
    """(#856 follow-up) `[er][89]` matched the nonexistent registers "e8"/"e9"
    (no such x86 registers exist) while failing to match the real r8d/r9d/
    r8w/r9w/r8b/r9b sub-register forms, because the trailing `\\b` never
    fires between two word characters (the digit and the size suffix).
    Verified against the real assembly corpus (language-crucible/data/assembly)
    through the actual Prism comment-stripping pipeline (not raw file text):
    matches went from 84 to 305 (+263%), with the biggest gains in bootos's
    16-bit real-mode bootloader code, which the old pattern missed entirely
    (0 matches) since it had no legacy 8/16-bit register support at all.
    """
    match = ASSEMBLY_RULES["args"].search("mov e8, 5")
    assert match is None, "Fictional register 'e8' must not match"

    for real_form in ("r8d", "r9d", "r8w", "r9w", "r8b", "r9b"):
        match = ASSEMBLY_RULES["args"].search(f"mov {real_form}, 1")
        assert match is not None, f"Real register form '{real_form}' must match"
        assert match.group(1).lower() == real_form


def test_assembly_args_legacy_8_16_bit_registers_regression():
    """(#856 follow-up) assembly's own `_meta.target_version` states
    "Backwards Compatible", and real corpus code (bootos's 16-bit real-mode
    BIOS bootloader) uses the legacy 8/16-bit register set (ax/al/ah, etc.)
    as its de facto argument-coupling convention. The original pattern had
    zero support for these forms.
    """
    for reg in ("ax", "bx", "cx", "dx", "al", "ah", "bl", "bh", "cl", "ch", "dl", "dh", "si", "di"):
        match = ASSEMBLY_RULES["args"].search(f"mov {reg}, 1")
        assert match is not None, f"Legacy register '{reg}' must match"
        assert match.group(1).lower() == reg

    # Real ABI/architecture registers must still be excluded even though they
    # share characters with the new legacy-register alternatives.
    for excluded in ("sp", "bp", "lr", "rax", "rbx", "r12", "r15"):
        match = ASSEMBLY_RULES["args"].search(f"mov {excluded}, 1")
        assert match is None, f"'{excluded}' must remain excluded (not an argument register)"


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("struc my_struct", "struc"),
        ("STRUCT my_struct", "STRUCT"),
        (".struct my_struct", ".struct"),
        ("my_struct STRUCT", "my_struct STRUCT"),
        ("  struc   foo", "struc"),
        ("\t.struct\tbar", ".struct"),
        ("My_Long_Struct_Name STRUCT", "My_Long_Struct_Name STRUCT"),
        ("struc ?foo@", "struc"),
        ("my_struct struc", "my_struct struc"),
        ("my_struct .struct", "my_struct .struct"),
    ],
    "invalid": [
        "my_struct: struc",
        "struc",
        "STRUCT",
        ".struct",
        "struc 123foo",
        "123foo STRUCT",
    ],
    "pathological": [
        ("struc \t\t  foo_bar_baz", "struc"),
        ("foo_bar_baz \t\t  STRUCT", "foo_bar_baz \t\t  STRUCT"),
        ("\t\t  .struct \t\t  _foo", ".struct"),
        ("?mang@led$name_@ \t STRUCT", "?mang@led$name_@ \t STRUCT"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_assembly_class_start_valid(payload, expected_name):
    assert_valid_match(ASSEMBLY_RULES["class_start"], payload, expected_name, "assembly.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_assembly_class_start_invalid(payload):
    assert_invalid_no_match(ASSEMBLY_RULES["class_start"], payload, "assembly.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_assembly_class_start_pathological(payload, expected_name):
    assert_pathological_match(ASSEMBLY_RULES["class_start"], payload, expected_name, "assembly.class_start")


def test_assembly_class_start_redos_immunity():
    assert_redos_immune(ASSEMBLY_RULES["class_start"], "struc" + " \t" * 50000 + "A", timeout_sec=1.0)


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ('%include "macros.inc"', "macros.inc"),
        ('.include "defs.s"', "defs.s"),
        ('.incbin "data.bin"', "data.bin"),
        ("INCLUDE macros.inc", "macros.inc"),
        ("INCLUDELIB kernel32.lib", "kernel32.lib"),
        ("%include 'single_quotes.inc'", "single_quotes.inc"),
        (".include 'single.s'", "single.s"),
        (".incbin 'data.bin'", "data.bin"),
        ('  %include "indented.inc"', "indented.inc"),
        ('\t.include\t"tabbed.s"', "tabbed.s"),
        ("include macros.inc", "macros.inc"),
        ("includelib kernel32.lib", "kernel32.lib"),
    ],
    "invalid": [
        "include_flag db 1",
        "%include",
        ".include",
        "INCLUDE",
        "INCLUDELIB",
        ".incbin",
        "#include <stdio.h>",
        'import "foo.s"',
    ],
    "pathological": [
        ('%include \t\t  "macros.inc"', "macros.inc"),
        (".include\t\t\t'defs.s'", "defs.s"),
        ("INCLUDE \t\t macros.inc", "macros.inc"),
        ("INCLUDELIB \t\t kernel32.lib", "kernel32.lib"),
        ('\t\t%include\t\t"macros.inc"\t\t', "macros.inc"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["valid"])
def test_assembly_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(ASSEMBLY_RULES["_dependency_capture"], payload, expected_name, "assembly.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_assembly_dependency_invalid(payload):
    assert_invalid_no_match(ASSEMBLY_RULES["_dependency_capture"], payload, "assembly.dependency")


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["pathological"])
def test_assembly_dependency_pathological(payload, expected_name):
    assert_pathological_dependency_match(
        ASSEMBLY_RULES["_dependency_capture"], payload, expected_name, "assembly.dependency"
    )


def test_assembly_dependency_redos_immunity():
    assert_redos_immune(ASSEMBLY_RULES["_dependency_capture"], "%include" + " \t" * 50000 + '"A"', timeout_sec=1.0)
