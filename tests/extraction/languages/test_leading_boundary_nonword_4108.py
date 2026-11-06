"""#4108 slice 24: an alternation member that starts with a non-word char must not sit behind a leading `\\b`,
which can never match after whitespace or punctuation (assembly `.rodata`, javascript `.bind(`)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ASM = LANGUAGE_DEFINITIONS["assembly"]["rules"]["immutability_locks"]
JS = LANGUAGE_DEFINITIONS["javascript"]["rules"]["reflection_metaprogramming"]


@pytest.mark.parametrize(
    "line",
    [
        "\t.section .rodata",  # after whitespace
        "section .rodata",
        "(.rdata)",  # after punctuation
        "x.rodata",  # after a word char (matched before)
        ".rodata.str1.1",
        "FOO equ 5",
        "FOO EQU 5",
    ],
)
def test_assembly_immutability_fires(line):
    assert ASM.search(line)


@pytest.mark.parametrize("line", ["mov eax, ebx", "equal 5", "requ 5", ".rodatax", ".rdatabase"])
def test_assembly_immutability_no_fire(line):
    assert not ASM.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "f.bind(this)",  # after a word char (matched before)
        "f().call(x)",  # after a paren
        "fns[0].apply(null, args)",  # after a bracket
        "a\n  .bind(this)",  # after whitespace
        "f.call()",  # no word char after the paren
        "Object.assign(a, b)",
        "arguments.length",
        "Reflect.get(a, b)",
    ],
)
def test_javascript_reflection_fires(line):
    assert JS.search(line)


@pytest.mark.parametrize(
    "line", ["f.bound(this)", "f.callback(x)", "applyAll(x)", "rebind(x)", "xprototypes", "let r = Reflector"]
)
def test_javascript_reflection_no_fire(line):
    assert not JS.search(line)
