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
    ]

    invalid = [
        ("on TargetFunc", None),
        ("command TargetFunc\n", None),
        ("script TargetScript pArg", None),
        ("on TargetFunc -- comment", None),
        ("on TargetFunc // comment", None),
        ("on TargetFunc # comment", None),
    ]

    pathological = [
        ("on TargetFunc \t pArg1,   pArg2", "pArg1,   pArg2"),
        ("command TargetFunc pArg1, pArg2 -- comment", "pArg1, pArg2"),
        ("function TargetFunc pArg1 // comment", "pArg1"),
        ("setprop TargetFunc pArg # comment", "pArg"),
        ("on TargetFunc pArg /* comment */", "pArg"),
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
