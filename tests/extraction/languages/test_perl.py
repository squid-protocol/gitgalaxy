"""
Perl extraction hardening (epic #813, issue #831). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for perl in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the old
monolithic dict files.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any  # noqa: E402

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

PERL_RULES = LANGUAGE_DEFINITIONS["perl"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("sub TargetFunc {", "TargetFunc"),
        ("method TargetFunc {", "TargetFunc"),
        ("sub TargetFunc($$) {", "TargetFunc"),  # legacy prototypes
        ("sub TargetFunc ($a, $b) {", "TargetFunc"),  # modern signatures
        ("sub TargetFunc : lvalue : method {", "TargetFunc"),  # attributes
    ],
    "invalid": ["package TargetFunc", "my $TargetFunc", "goto TargetFunc"],
    "pathological": [
        ("sub \n TargetFunc \n {", "TargetFunc"),
        ("method \n TargetFunc \n ( \n $a, \n $b \n ) \n {", "TargetFunc"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_perl_func_start_valid(payload, expected_name):
    assert_valid_match(PERL_RULES["func_start"], payload, expected_name, "perl.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_perl_func_start_invalid(payload):
    assert_invalid_no_match(PERL_RULES["func_start"], payload, "perl.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_perl_func_start_pathological(payload, expected_name):
    assert_pathological_match(PERL_RULES["func_start"], payload, expected_name, "perl.func_start")
    assert_redos_immune(PERL_RULES["func_start"], payload)


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("sub foo ($a, $b) {", ""),
        ("method bar($self, $x) {", ""),
        ("my ($self, $x) = @_;", ""),
        ("my $self = shift;", ""),
    ],
    "invalid": [
        "my $a = 1;",
        "sub foo {",
    ],
    "pathological": [
        ("sub \n foo \n ( \n $a, \n $b \n ) \n {", ""),
        ("my \n ( \n $self, \n $x \n ) \n = \n @_ \n ;", ""),
    ],
}


@pytest.mark.parametrize("payload,expected", ARGS_CASES["valid"])
def test_perl_args_valid(payload, expected):
    assert_valid_match(PERL_RULES["args"], payload, expected, "perl.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_perl_args_invalid(payload):
    assert_invalid_no_match(PERL_RULES["args"], payload, "perl.args")


@pytest.mark.parametrize("payload,expected", ARGS_CASES["pathological"])
def test_perl_args_pathological(payload, expected):
    assert_pathological_match(PERL_RULES["args"], payload, expected, "perl.args")
    assert_redos_immune(PERL_RULES["args"], payload)


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("package Foo::Bar;", "Foo::Bar"),
        ("class Foo::Bar {", "Foo::Bar"),
        ("role Foo::Bar;", "Foo::Bar"),
    ],
    "invalid": [
        "my $package = 1;",
        "sub class_name {",
    ],
    "pathological": [
        ("package \n Foo::Bar \n ;", "Foo::Bar"),
        ("class \n Foo::Bar \n {", "Foo::Bar"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_perl_class_start_valid(payload, expected_name):
    assert_valid_match(PERL_RULES["class_start"], payload, expected_name, "perl.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_perl_class_start_invalid(payload):
    assert_invalid_no_match(PERL_RULES["class_start"], payload, "perl.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_perl_class_start_pathological(payload, expected_name):
    assert_pathological_match(PERL_RULES["class_start"], payload, expected_name, "perl.class_start")
    assert_redos_immune(PERL_RULES["class_start"], payload)


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("use strict;", "strict"),
        ("require Foo::Bar;", "Foo::Bar"),
        ("no warnings;", "warnings"),
    ],
    "invalid": [
        "my $use = 1;",
        "sub require_foo {",
    ],
    "pathological": [
        ("use \n Data::Dumper", "Data::Dumper"),
        ("require \n Foo::Bar \n ;", "Foo::Bar"),
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_perl_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(PERL_RULES["_dependency_capture"], payload, expected_path, "perl._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_perl_dependency_capture_invalid(payload):
    assert_invalid_no_match(PERL_RULES["_dependency_capture"], payload, "perl._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_perl_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        PERL_RULES["_dependency_capture"], payload, expected_path, "perl._dependency_capture"
    )
    assert_redos_immune(PERL_RULES["_dependency_capture"], payload)
