"""
Tcl extraction hardening (epic #848). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for tcl in one file: func_start,
args, class_start, _dependency_capture.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

TCL_RULES = LANGUAGE_DEFINITIONS["tcl"]["rules"]

FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("proc TargetFunc {", "TargetFunc"),
        ("proc TargetFunc {a b} {", "TargetFunc"),
        ("proc ::namespace::TargetFunc {args} {", "TargetFunc"),
    ],
    "invalid": [
        "set TargetFunc",
        "if {$TargetFunc}",
        "TargetFunc a b",
        "if {$a == $b} {",
        "set proc TargetFunc",
        'puts "proc TargetFunc {"',
    ],
    "pathological": [
        ("proc \t TargetFunc \t {", "TargetFunc"),
        ("proc   TargetFunc {", "TargetFunc"),
        ("proc \n ::namespace::TargetFunc \n { \n a \n b \n } \n {", "TargetFunc"),
    ],
}

ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("proc TargetFunc {a b} {", "a b"),
        ("proc ::namespace::TargetFunc {args} {", "args"),
        ("proc TargetFunc {{a 1} b} {", "{a 1} b"),
        ("proc faultsim_integrity_check {{db db}} {", "{db db}"),
        ("proc TargetFunc {a {b 2} {c {nested list}}} {", "a {b 2} {c {nested list}}"),
    ],
    "invalid": [
        "TargetFunc a b",
        "if {$a == $b} {",
    ],
    "pathological": [
        ("proc \n ::namespace::TargetFunc \n { \n a \n b \n } \n {", " \n a \n b \n "),
        ("proc TargetFunc \n { \n {a 1} \n {b 2} \n } \n {", " \n {a 1} \n {b 2} \n "),
        ("proc   TargetFunc   {   a   b   }   {", "   a   b   "),
    ],
}

CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("oo::class create TargetClass {", "TargetClass"),
        ("snit::type TargetClass {", "TargetClass"),
        ("itcl::class TargetClass {", "TargetClass"),
    ],
    "invalid": ["set TargetClass", "if {$TargetClass}", "TargetClass create foo"],
    "pathological": [
        ("oo::class \t create \t TargetClass \t {", "TargetClass"),
        ("oo::class \n create \n TargetClass \n {", "TargetClass"),
        ("snit::type \n TargetClass \n {", "TargetClass"),
    ],
}

DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("package require TargetPkg", "TargetPkg"),
        ("source TargetPkg.tcl", "TargetPkg.tcl"),
        ("load TargetPkg.so", "TargetPkg.so"),
        ("package require -exact TargetPkg 1.0", "TargetPkg"),
        ('source "TargetPkg.tcl"', "TargetPkg.tcl"),
    ],
    "invalid": [
        "puts TargetPkg",
        "set package TargetPkg",
        'puts "package require TargetPkg"',
    ],
    "pathological": [
        ("package   require   TargetPkg", "TargetPkg"),
        ("source   TargetPkg.tcl", "TargetPkg.tcl"),
        ("package \t require \t TargetPkg", "TargetPkg"),
    ],
}


class TestTclExtraction:
    # -------------------------------------------------------------------------
    # func_start
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize("payload,expected", FUNCTION_CASES["valid"])
    def test_func_start_valid(self, payload, expected):
        assert_valid_match(TCL_RULES["func_start"], payload, expected, "tcl")

    @pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
    def test_func_start_invalid(self, payload):
        assert_invalid_no_match(TCL_RULES["func_start"], payload, "tcl")

    @pytest.mark.parametrize("payload,expected", FUNCTION_CASES["pathological"])
    def test_func_start_pathological(self, payload, expected):
        assert_pathological_match(TCL_RULES["func_start"], payload, expected, "tcl")

    # -------------------------------------------------------------------------
    # args
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize("payload,expected", ARGS_CASES["valid"])
    def test_args_valid(self, payload, expected):
        assert_valid_match(TCL_RULES["args"], payload, expected, "tcl")

    @pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
    def test_args_invalid(self, payload):
        assert_invalid_no_match(TCL_RULES["args"], payload, "tcl")

    @pytest.mark.parametrize("payload,expected", ARGS_CASES["pathological"])
    def test_args_pathological(self, payload, expected):
        assert_pathological_match(TCL_RULES["args"], payload, expected, "tcl")

    # -------------------------------------------------------------------------
    # class_start
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize("payload,expected", CLASS_CASES["valid"])
    def test_class_start_valid(self, payload, expected):
        assert_valid_match(TCL_RULES["class_start"], payload, expected, "tcl")

    @pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
    def test_class_start_invalid(self, payload):
        assert_invalid_no_match(TCL_RULES["class_start"], payload, "tcl")

    @pytest.mark.parametrize("payload,expected", CLASS_CASES["pathological"])
    def test_class_start_pathological(self, payload, expected):
        assert_pathological_match(TCL_RULES["class_start"], payload, expected, "tcl")

    # -------------------------------------------------------------------------
    # _dependency_capture
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize("payload,expected", DEPENDENCY_CASES["valid"])
    def test_dependency_valid(self, payload, expected):
        assert_valid_dependency_match(TCL_RULES["_dependency_capture"], payload, expected, "tcl")

    @pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
    def test_dependency_invalid(self, payload):
        assert_invalid_no_match(TCL_RULES["_dependency_capture"], payload, "tcl")

    @pytest.mark.parametrize("payload,expected", DEPENDENCY_CASES["pathological"])
    def test_dependency_pathological(self, payload, expected):
        assert_pathological_dependency_match(TCL_RULES["_dependency_capture"], payload, expected, "tcl")

    def test_brace_safe_stream_single_quotes(self):
        from gitgalaxy.core.detector import StructuralExtractor
        from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

        extractor = StructuralExtractor("tcl", LANGUAGE_DEFINITIONS)

        # (a) The confirmed repro
        code_a = 'string map {\' \'\'} $contents\nproc drop_all_tables {{db db}} {\n    puts "dropped"\n}\nproc drop_all_indexes {{db db}} {\n    puts "dropped"\n}'
        safe_a = extractor._build_brace_safe_stream(code_a, "tcl")

        # It shouldn't swallow the braces
        assert "{" in safe_a
        assert "}" in safe_a

        # A safer test is to run the extractor full pass if possible, or just check the shielded output
        # In the buggy version, the `'` would swallow everything between `{' ''}` and the next `'` (which might not even exist, or if we added another, it would swallow it).

        code_bug = "string map {' ''} $contents\nproc drop_all_tables {{db db}} {\n    puts 'dropped'\n}"
        safe_bug = extractor._build_brace_safe_stream(code_bug, "tcl")
        # In the bug, everything between the 3rd ' and the 4th ' is blanked out!
        assert "proc drop_all_tables" in safe_bug

        # (b) legitimate uses of '
        code_b = "set a \"this has an ' in it\"\n# comment with '\nproc normal_proc {} {\n    puts 'hello'\n}"
        safe_b = extractor._build_brace_safe_stream(code_b, "tcl")
        assert "proc normal_proc" in safe_b
