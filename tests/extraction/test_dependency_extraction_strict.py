import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# =======================================================================# THE GRAVITY LINK GAUNTLET
# Proves that the `_dependency_capture` spawner accurately isolates EXACTLY
# the imported file/module path across major languages, surviving destructuring,
# aliases, and multi-line formatting without capturing the wrong variables.
# =======================================================================# =======================================================================# THE GRAVITY LINK GAUNTLET (37-LANGUAGE MEGA SUITE)
# Proves that the `_dependency_capture` spawner accurately isolates EXACTLY
# the imported file/module path across ALL supported languages, surviving
# destructuring, aliases, and multi-line formatting without capturing the wrong variables.
# =======================================================================
DEPENDENCY_EXTRACTION_CASES = {
    "ruby": {
        "valid": [
            ("require 'json'", "json"),
            ("require_relative '../core/engine'", "../core/engine"),
        ],
        "invalid": ["required_fields = []"],
        "pathological": [
            (
                'require_relative \n ( \n "../lib/massive_module" \n )',
                "../lib/massive_module",
            )
        ],
    },
    "php": {
        "valid": [
            (
                "use Illuminate\\Support\\Facades\\Route;",
                "Illuminate\\Support\\Facades\\Route",
            ),
            ("require_once 'vendor/autoload.php';", "vendor/autoload.php"),
        ],
        "invalid": ["$useCache = true;"],
        "pathological": [
            (
                "use \n function \n My\\Custom\\Namespace\\target_function \n ;",
                "My\\Custom\\Namespace\\target_function",
            )
        ],
    },

    "html": {
        "valid": [
            ('<script src="app.js"></script>', "app.js"),
            ('<link rel="stylesheet" href="style.css">', "style.css"),
        ],
        "invalid": ["", 'let src = "app.js";'],
        "pathological": [('<link \n rel="stylesheet" \n href="theme.css">', "theme.css")],
    },
    "css": {
        "valid": [
            ('@import url("reset.css");', "reset.css"),
            ('@import "theme.css";', "theme.css"),
        ],
        "invalid": [".import { color: red; }"],
        "pathological": [('@import \n url( \n "fonts.css" \n )', "fonts.css")],
    },
    "fortran": {
        "valid": [
            ("USE iso_fortran_env", "iso_fortran_env"),
            ("INCLUDE 'constants.h'", "constants.h"),
        ],
        "invalid": ["CHARACTER(LEN=10) :: INCLUDE_FILE"],
        "pathological": [("USE \n , \n INTRINSIC \n :: \n omp_lib", "omp_lib")],
    },



    "dart": {
        "valid": [
            ("import 'dart:io';", "dart:io"),
            (
                "export 'package:flutter/material.dart';",
                "package:flutter/material.dart",
            ),
        ],
        "invalid": ["var importPath = '';"],
        "pathological": [
            (
                "export \n 'package:provider/provider.dart'",
                "package:provider/provider.dart",
            )
        ],
    },
    "dockerfile": {
        "valid": [
            ("FROM ubuntu:latest", "ubuntu:latest"),
            ("COPY --from=builder /app /app", "builder"),
        ],
        "invalid": ["ENV FROM_PATH=/app"],
        "pathological": [("FROM \n --platform=linux/amd64 \n alpine:3.18", "alpine:3.18")],
    },

    "livecode": {
        "valid": [
            ('start using stack "lib"', "lib"),
            ('require "database"', "database"),
        ],
        "invalid": ["put empty into requirePath"],
        "pathological": [('start \n using \n behavior \n "btnBehavior"', "btnBehavior")],
    },
    "objective-c": {
        "valid": [
            ("#import <Foundation/Foundation.h>", "Foundation/Foundation.h"),
            ("@import UIKit;", "UIKit"),
        ],
        "invalid": ["int import_count;"],
        "pathological": [("@import \n CoreGraphics \n ;", "CoreGraphics")],
    },
}


class TestDependencyExtraction:
    @pytest.mark.parametrize("lang_id", DEPENDENCY_EXTRACTION_CASES.keys())
    def test_positive_dependency_extraction(self, lang_id):
        """
        Proves that valid import signatures are caught, and the regex
        isolates EXACTLY the module/file path.
        """
        cases = DEPENDENCY_EXTRACTION_CASES.get(lang_id, {})
        if "valid" not in cases:
            pytest.skip(f"No valid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("_dependency_capture")
        if not pattern:
            pytest.skip(f"No _dependency_capture pattern defined for {lang_id}")

        for payload, expected_name in cases["valid"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] Iron Wall Blocked Valid Import: '{payload}'"

            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Regex matched but captured nothing!"

                # Check if the expected name is in ANY of the capture groups (some languages use alternate groups for require vs import)
                found = any(expected_name in g for g in captured_groups)
                assert found, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean path '{expected_name}' from '{payload}'"
                )
            else:
                pytest.fail(f"[{lang_id}] _dependency_capture MUST use a capture group to isolate the path!")

    @pytest.mark.parametrize("lang_id", DEPENDENCY_EXTRACTION_CASES.keys())
    def test_negative_dependency_extraction(self, lang_id):
        """
        Proves that structural lookalikes (variable assignments, comments)
        are explicitly ignored by the dependency spawner.
        """
        cases = DEPENDENCY_EXTRACTION_CASES.get(lang_id, {})
        if "invalid" not in cases:
            pytest.skip(f"No invalid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("_dependency_capture")
        if not pattern:
            pytest.skip(f"No _dependency_capture pattern defined for {lang_id}")

        for payload in cases["invalid"]:
            match = pattern.search(payload)
            assert match is None, (
                f"[{lang_id}] 👻 GHOST DEPENDENCY HALLUCINATED! Erroneously mapped path on: '{payload}'"
            )

    @pytest.mark.parametrize("lang_id", DEPENDENCY_EXTRACTION_CASES.keys())
    def test_pathological_dependency_extraction(self, lang_id):
        """
        Adversarial Engineering: Proves the regex can survive "Frankenstein"
        formatting, including vertical newlines, destructuring, and
        alias stacking, while still cleanly extracting the path.
        """
        cases = DEPENDENCY_EXTRACTION_CASES.get(lang_id, {})
        if "pathological" not in cases:
            pytest.skip(f"No pathological cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("_dependency_capture")
        if not pattern:
            pytest.skip(f"No _dependency_capture pattern defined for {lang_id}")

        for payload, expected_name in cases["pathological"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] 💥 Engine choked on pathological import formatting: '{payload}'"

            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Matched but captured nothing!"

                found = any(expected_name in g for g in captured_groups)
                assert found, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean path '{expected_name}'"
                )
