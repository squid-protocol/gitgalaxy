"""inline_asm opener coverage across the C family and Rust (#4108 slice 5).

GCC stacks its asm qualifiers (`asm volatile goto (`, `asm inline (`); the rules used to allow one.
Rust's `naked_asm!` and `llvm_asm!` open machine code the same way as `asm!`.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

_C_FAMILY = ("c", "cpp", "objective-c")

_C_POSITIVES = [
    'asm("nop");',
    'asm volatile ("nop");',
    'asm __volatile__ ("nop");',
    '__asm__ volatile ("nop");',
    '__asm__ __volatile__ ("nop");',
    '__asm__ __volatile ("nop");',
    'asm goto ("jmp %l0" :::: out);',
    'asm volatile goto ("jmp %l0" :::: out);',
    '__asm__ volatile goto ("jmp %l0" :::: out);',
    'asm inline ("nop");',
    'asm volatile inline ("nop");',
    '__asm__ __inline__ __volatile__ ("nop");',
    'asm\n    volatile\n    goto\n    ("nop");',
]

_C_NEGATIVES = [
    "int asm_count = 1;",
    "my_asm(x);",
    "int goto_count = 2;",
    "volatile int x = 1;",
    "goto done;",
    "inline int f(void) { return 1; }",
]


def _rule(lang, name):
    return LANGUAGE_DEFINITIONS[lang]["rules"][name]


@pytest.mark.parametrize("lang", _C_FAMILY)
@pytest.mark.parametrize("text", _C_POSITIVES)
def test_c_family_asm_qualifier_stacks_fire(lang, text):
    assert _rule(lang, "inline_asm").search(text), (lang, text)


@pytest.mark.parametrize("lang", _C_FAMILY)
@pytest.mark.parametrize("text", _C_NEGATIVES)
def test_c_family_asm_near_misses_stay_quiet(lang, text):
    assert not _rule(lang, "inline_asm").search(text), (lang, text)


@pytest.mark.parametrize("lang", ("c", "cpp"))
def test_c_cpp_msvc_asm_block_still_fires(lang):
    assert _rule(lang, "inline_asm").search("__asm { mov eax, 1 }")


@pytest.mark.parametrize("lang", _C_FAMILY)
def test_c_family_asm_qualifier_chain_is_redos_immune(lang):
    rule = _rule(lang, "inline_asm")
    assert_redos_immune(rule, "asm" + " volatile" * 20000, timeout_sec=3.0)
    assert_redos_immune(rule, "asm" + " " * 100000, timeout_sec=3.0)


_RUST_POSITIVES = [
    'asm!("nop")',
    'core::arch::asm!("nop")',
    'std::arch::asm!("nop")',
    'global_asm!(".globl f")',
    'core::arch::global_asm!(".globl f")',
    'naked_asm!("ret")',
    'core::arch::naked_asm!("ret")',
    'llvm_asm!("nop")',
    'unsafe { llvm_asm!("nop" :::: "volatile"); }',
]

_RUST_NEGATIVES = [
    "let asm = 1;",
    'my_asm!("nop")',
    'naked_asm("ret")',
    "let llvm_asm_count = 2;",
    "fn naked_asm_helper() {}",
]


@pytest.mark.parametrize("text", _RUST_POSITIVES)
def test_rust_asm_macros_fire(text):
    assert _rule("rust", "inline_asm").search(text), text


@pytest.mark.parametrize("text", _RUST_NEGATIVES)
def test_rust_asm_near_misses_stay_quiet(text):
    assert not _rule("rust", "inline_asm").search(text), text
