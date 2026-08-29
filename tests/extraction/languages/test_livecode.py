import sys
from pathlib import Path

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

import pytest  # noqa: E402
from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

LIVECODE_RULES = LANGUAGE_DEFINITIONS["livecode"]["rules"]


def test_livecode_func_start():
    valid = [
        ("on TargetFunc", "TargetFunc"),
        ("command TargetFunc", "TargetFunc"),
        ("function TargetFunc", "TargetFunc"),
        ("getprop TargetFunc", "TargetFunc"),
        ("setprop TargetFunc", "TargetFunc"),
        ("private function TargetFunc", "TargetFunc"),
        ("public command TargetFunc", "TargetFunc"),
        ("private on TargetFunc", "TargetFunc"),
        ("public on TargetFunc", "TargetFunc"),
        ("private getprop TargetFunc", "TargetFunc"),
        # #2409: LiveCode Builder (.lcb) `handler` syntax -- parenthesized,
        # typed param list, so the name is followed by `(` (rejected for the
        # LiveCode Script forms above) or a `\` line continuation.
        ("handler BoxValue(in pValue as any) returns Array", "BoxValue"),
        ("public handler MCAssertExpectPrecondition(in pCondition as Boolean)", "MCAssertExpectPrecondition"),
        ("private handler _helper()", "_helper"),
        ("public handler MCAssertExpectPreconditionWithReason \\", "MCAssertExpectPreconditionWithReason"),
    ]

    invalid = [
        ("script TargetFunc", None),
        ("put TargetFunc into x", None),
        ("repeat with TargetFunc", None),
        ("function_not_start = 1", None),
        ("command_name", None),
        ('put "on TargetFunc" into x', None),
        ("on", None),
        ("function TargetFunc()", None),
        # #2409: `foreign handler` / `public foreign handler` are FFI *binding
        # declarations* (C-prototype shaped, `binds to "<builtin>"`, no body) --
        # excluded by construction, parallel to a C header prototype.
        ('public foreign handler MCArrayEvalKeysOf(in T as Array) returns nothing binds to "<builtin>"', None),
        ("foreign handler MCFoo(in x as Integer)", None),
        # `handler type <Name>(...)` declares a handler *type* (function-pointer
        # typedef), not a callable definition.
        ("handler type Thunk()", None),
        # LCB `handler` with no `(` at all is not a real handler header.
        ("handler NotAHandler", None),
    ]

    pathological = [
        ("private \t command \t TargetFunc \t ", "TargetFunc"),
        ("public \t function \t TargetFunc", "TargetFunc"),
        ("public \t function \t TargetFunc", "TargetFunc"),
        ("on \tTargetFunc\t", "TargetFunc"),
        ("private\t\tcommand\t\tTargetFunc", "TargetFunc"),
        ("on TargetFunc--comment", "TargetFunc"),
        ("command TargetFunc//comment", "TargetFunc"),
        ("function TargetFunc#comment", "TargetFunc"),
        ("getprop TargetFunc/*comment*/", "TargetFunc"),
        ("\t public \t handler \t MixedCase (in a as X)", "MixedCase"),
        ("HANDLER ShoutingCase(in a as X)", "ShoutingCase"),
    ]

    for payload, expected in valid:
        assert_valid_match(LIVECODE_RULES["func_start"], payload, expected, "livecode.func_start")

    for payload, _ in invalid:
        assert_invalid_no_match(LIVECODE_RULES["func_start"], payload, "livecode.func_start")

    for payload, expected in pathological:
        assert_pathological_match(LIVECODE_RULES["func_start"], payload, expected, "livecode.func_start")


def test_livecode_class_start():
    valid = [
        ("script TargetScript", "TargetScript"),
        ("behavior TargetBehavior", "TargetBehavior"),
        ("widget TargetWidget", "TargetWidget"),
        ("module com.livecode.library", "com.livecode.library"),
        ("library TargetLibrary", "TargetLibrary"),
    ]

    invalid = [
        ("on script", None),
        ("put behavior into x", None),
        ("widget_not_start = 1", None),
        ('put "script TargetScript" into x', None),
        ("module ", None),
        ("script TargetScript pArg", None),
    ]

    pathological = [
        ("script \t TargetScript", "TargetScript"),
        ("module \t com.livecode.library", "com.livecode.library"),
        ("widget \t TargetWidget \t ", "TargetWidget"),
        ("behavior\t\tTargetBehavior", "TargetBehavior"),
        ("script TargetScript--comment", "TargetScript"),
        ("widget TargetWidget//comment", "TargetWidget"),
    ]

    for payload, expected in valid:
        assert_valid_match(LIVECODE_RULES["class_start"], payload, expected, "livecode.class_start")

    for payload, _ in invalid:
        assert_invalid_no_match(LIVECODE_RULES["class_start"], payload, "livecode.class_start")

    for payload, expected in pathological:
        assert_pathological_match(LIVECODE_RULES["class_start"], payload, expected, "livecode.class_start")


def test_livecode_args():
    valid = [
        ("on TargetFunc pArg1", "pArg1"),
        ("command TargetFunc pArg1, pArg2", "pArg1, pArg2"),
        ("function TargetFunc pArg1, pArg2, pArg3", "pArg1, pArg2, pArg3"),
        ("setprop TargetFunc pArg1", "pArg1"),
        ("on TargetFunc @pArray", "@pArray"),
        # #2409: LiveCode Builder parenthesized, typed param list.
        ("handler Foo(in x as String, out y as Integer)", "in x as String, out y as Integer"),
        ("public handler MCAssert(in pCondition as Boolean)", "in pCondition as Boolean"),
    ]

    invalid = [
        ("on TargetFunc", None),
        ("command TargetFunc\n", None),
        ("script TargetScript pArg", None),
        ("on TargetFunc -- comment", None),
        ("on TargetFunc // comment", None),
        ("on TargetFunc # comment", None),
        ("handler Foo()", None),
        ("handler type Thunk(in x as any)", None),
    ]

    pathological = [
        ("on TargetFunc \t pArg1,   pArg2", "pArg1,   pArg2"),
        ("command TargetFunc pArg1, pArg2 -- comment", "pArg1, pArg2"),
        ("function TargetFunc pArg1 // comment", "pArg1"),
        ("setprop TargetFunc pArg # comment", "pArg"),
        ("on TargetFunc pArg /* comment */", "pArg"),
        ("public handler Bar( inout z as List )", "inout z as List"),
    ]

    for payload, expected in valid:
        assert_valid_match(LIVECODE_RULES["args"], payload, expected, "livecode.args")

    for payload, _ in invalid:
        assert_invalid_no_match(LIVECODE_RULES["args"], payload, "livecode.args")

    for payload, expected in pathological:
        assert_pathological_match(LIVECODE_RULES["args"], payload, expected, "livecode.args")


def test_livecode_dependency_capture():
    valid = [
        ('start using stack "lib"', "lib"),
        ('require "database"', "database"),
        ('include "my_lib"', "my_lib"),
        ('module "com.livecode.math"', "com.livecode.math"),
        ("start using behavior my_behavior", "my_behavior"),
        ('start using "stack_name"', "stack_name"),
        ("start using stack my_stack", "my_stack"),
    ]

    invalid = [
        ("put empty into requirePath", None),
        ("require_login", None),
    ]

    xfail_invalid = [
        ('/*\nstart using stack "fake"\n*/', None),
        ('put "\nstart using stack \\"fake\\"\n" into x', None),
    ]

    pathological = [
        ('start \t using \t behavior \t "btnBehavior"', "btnBehavior"),
        ('start \t using \t stack \t "lib"', "lib"),
        ('require \t "database"', "database"),
        ('module \t "com.livecode.math"', "com.livecode.math"),
    ]

    for payload, expected in valid:
        assert_valid_dependency_match(
            LIVECODE_RULES["_dependency_capture"], payload, expected, "livecode._dependency_capture"
        )

    for payload, _ in invalid:
        assert_invalid_no_match(LIVECODE_RULES["_dependency_capture"], payload, "livecode._dependency_capture")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))

    for payload, expected in pathological:
        assert_pathological_dependency_match(
            LIVECODE_RULES["_dependency_capture"], payload, expected, "livecode._dependency_capture"
        )
