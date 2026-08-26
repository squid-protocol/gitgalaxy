"""
Perl extraction hardening (epic #813, issue #831). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for perl in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the old
monolithic dict files.
"""

import os
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


def test_perl_qr_brace_shield_does_not_desync_brace_slicing():
    """
    Issue #1437: a stray escaped quote inside an unrelated s/// substitution regex (not a
    real string delimiter) used to pair with the next unrelated escaped quote later in the
    file as a bogus "string", silently swallowing a `{` in between and desyncing
    _slice_by_braces for every function after it. Also covers the qr{...} case that
    motivated the issue originally -- its own internal `{`/`}` (from the {2,4}-shaped
    COMMIT marker below) must not be miscounted as real code braces either.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    code = (
        "sub check_etag {\n"
        '  $x =~ s/^\\"//g;\n'
        "  return 1;\n"
        "}\n"
        "\n"
        "sub multipart_start {\n"
        "  my $re = qr{ ^ (*COMMIT) [a-z]{2,4} };\n"
        "  return $re;\n"
        "}\n"
        "\n"
        "sub close_standby_message {\n"
        '  $y =~ s/\\"$//g;\n'
        "  return 0;\n"
        "}\n"
    )
    ext = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    safe_code = ext._build_brace_safe_stream(code, "perl")
    assert safe_code.count("{") == safe_code.count("}")


def test_perl_1517_brace_quote_op_embedded_hash_not_comment():
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    code = 'sub _line {\n  my $name = shift->name;\n  return qq{#line @{[shift]} "$name"};\n}\n'
    code_stripped, _ = prism._strip_single_line_comments(code, "perl")
    # Should not truncate the third line
    assert "return qq{" in code_stripped
    assert "};" in code_stripped


def test_perl_1517_bare_regex_embedded_hash_not_comment():
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    code = "sub FilterArgfileLine {\n  if ($arg =~ /^#/) {  # comment lines begin with '#'\n    return;\n  }\n}\n"
    code_stripped, _ = prism._strip_single_line_comments(code, "perl")
    assert "if ($arg =~ /^#/) {" in code_stripped
    assert "return;" in code_stripped


# ==============================================================================
# PERL ARGS SUMMING (Root Causes 2, 3, 4)
# ==============================================================================
def test_perl_args_summing():
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["perl"]["rules"]

    def _get_args_count(code: str) -> int:
        sat, _ = extractor._calculate_block_metrics(
            name="test_sub",
            block=code,
            loc=code.count("\n") + 1,
            start_line=1,
            end_line=code.count("\n") + 1,
            rules=rules,
            start_idx=0,
            end_idx=len(code),
            spatial_map={},
        )
        return sat.get("args_count", 0)

    # 1. Traditional prototype: skipped by signature capture, falls through to sum the body.
    # Should sum to 2 (two shifts), even though prototype is ($$).
    code_proto = """sub foo($$) {
        my $x = shift;
        my $y = shift;
    }"""
    assert _get_args_count(code_proto) == 2

    # 2. Multiple separate shift/my-unpacking statements.
    code_multiple = """sub ValidateDependencies {
        my $self = shift;
        my $pkg = shift;
        my $deps = shift;
    }"""
    assert _get_args_count(code_multiple) == 3

    # 3. Bare shift (not shifting an explicitly named array).
    # Also verify it doesn't overcount `shift @other_array`.
    code_bare_shift = """sub process {
        my $x = shift;
        shift;
        shift @other_queue;
        my $y = shift || 0;
    }"""
    assert _get_args_count(code_bare_shift) == 3

    # 4. Bare catch-all array assignment.
    code_catch_all = """sub finalize {
        my $class = shift;
        my @rest = @_;
    }"""
    assert _get_args_count(code_catch_all) == 2


def test_perl_forward_decl_does_not_grab_unrelated_brace_getascii_bug_1609():
    """
    Issue #1609: A bodyless forward declaration (e.g. `sub GetASCII($);`) should not
    accidentally grab a `{` from a later, unrelated block (e.g. `END { ... }`) that
    falls within its search window. It should be rejected as a valid function.
    Real bodied functions before/after must still be correctly extracted.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "sub real_sub_before {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "sub GetASCII($);\n"
        "\n"
        "$SIG{INT}  = 'SigInt';\n"
        "END {\n"
        "    Cleanup();\n"
        "}\n"
        "\n"
        "sub real_sub_after {\n"
        "    return 2;\n"
        "}\n"
    )

    ext = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["perl"]["rules"]

    functions, _ = ext._slice_by_braces(code, "perl", rules, 0, {})

    found_names = [f.get("name") for f in functions]
    assert "GetASCII" not in found_names
    assert "real_sub_before" in found_names
    assert "real_sub_after" in found_names
    assert len(functions) == 2


@pytest.mark.golden_crucible
def test_perl_issue_2239_pod_blocks_stripped():
    """
    Issue #2239: GitGalaxy has zero POD-block awareness for Perl. `=head1`/`=cut`-delimited
    POD documentation blocks are never stripped from the code stream before func_start runs,
    so a literal `sub name { ... }` example written as prose inside a POD block gets matched
    as a real function.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    # a. The Promise.pm repro
    crucible_path = os.environ.get("LANGUAGE_CRUCIBLE_PATH")
    assert crucible_path is not None, "LANGUAGE_CRUCIBLE_PATH not set"
    promise_pm_path = os.path.join(crucible_path, "data/perl/mojo/Promise.pm")
    with open(promise_pm_path, encoding="utf-8") as f:
        code = f.read()

    ext = StructuralExtractor("perl", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["perl"]["rules"]
    functions, _ = ext._slice_by_braces(code, "perl", rules, 0, {})
    found_names = [f.get("name") for f in functions]

    # get_p should be stripped because it's inside a POD block
    assert "get_p" not in found_names

    # b. Normal subs outside POD blocks still match correctly (e.g., 'new', 'clone')
    assert "new" in found_names
    assert "clone" in found_names

    # c. A sub whose body legitimately contains "=" as an operator
    code_with_eq = "sub real_sub_with_eq {\n  my $x = 1;\n  my $y = 2;\n  return $x = $y;\n}\n"
    functions_eq, _ = ext._slice_by_braces(code_with_eq, "perl", rules, 0, {})
    found_names_eq = [f.get("name") for f in functions_eq]
    assert "real_sub_with_eq" in found_names_eq
