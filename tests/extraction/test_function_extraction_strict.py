import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# ==============================================================================
# THE UNIVERSAL EXTRACTION GAUNTLET
# Proves that the `func_start` spawner accurately isolates EXACTLY the function
# name ("TargetFunc") across 32 distinct programming languages and architectures.
#
# FORMAT:
# "lang": {
#     "valid": [ ("Payload String", "Expected Extracted Name") ],
#     "invalid": [ "Strings that look like functions but MUST NOT match" ]
# }
# ==============================================================================
# ==============================================================================
# THE UNIVERSAL EXTRACTION GAUNTLET
# Proves that the `func_start` spawner accurately isolates EXACTLY the function
# name ("TargetFunc") across 32 distinct programming languages and architectures.
#
# FORMAT:
# "lang": {
#     "valid": [ ("Payload String", "Expected Extracted Name") ],
#     "invalid": [ "Strings that look like functions but MUST NOT match" ],
#     "pathological": [ "Frankenstein formatting designed to break the regex" ]
# }
# ==============================================================================
EXTRACTION_CASES = {
    "php": {
        "valid": [
            ("function TargetFunc()", "TargetFunc"),
            ("public static function TargetFunc(", "TargetFunc"),
            ("final protected function TargetFunc()", "TargetFunc"),
        ],
        "invalid": ["class TargetFunc", "$var = TargetFunc()", "new TargetFunc()"],
        "pathological": [
            # PHP 8 attributes and erratic reference ampersands
            (
                "#[\\ReturnTypeWillChange]\nfinal \n public \n static \n function \n & \n TargetFunc \n (",
                "TargetFunc",
            )
        ],
    },
    "ruby": {
        "valid": [
            ("def TargetFunc", "TargetFunc"),
            ("def self.TargetFunc", "TargetFunc"),
            ("define_method :TargetFunc do", "TargetFunc"),
        ],
        "invalid": ["class TargetFunc", "TargetFunc = 5", "module TargetFunc"],
        "pathological": [
            # Vertical class-method declaration
            ("def \n self. \n TargetFunc \n (", "TargetFunc")
        ],
    },
    "shell": {
        "valid": [
            ("function TargetFunc {", "TargetFunc"),
            ("TargetFunc() {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc=", "if TargetFunc; then", "alias TargetFunc="],
        "pathological": [
            # Extreme spacing on standard definitions
            ("function \t \n TargetFunc \n {", "TargetFunc")
        ],
    },
    "cobol": {
        "valid": [
            ("       TargetFunc SECTION.", "TargetFunc"),
            ("       TargetFunc.", "TargetFunc"),
        ],
        "invalid": [
            "       01 TargetFunc.",
            "           PERFORM TargetFunc.",
            "       END-TargetFunc.",
        ],
        "pathological": [
            # Margin hugging and separated section headers
            ("TargetFunc \n           SECTION.", "TargetFunc")
        ],
    },
    "apex": {
        "valid": [
            ("public static void TargetFunc()", "TargetFunc"),
            ("trigger TargetFunc on Account", "TargetFunc"),
        ],
        "invalid": ["public class TargetFunc", "delete TargetFunc"],
        "pathological": [
            # Future callouts and erratic spacing
            (
                "@future(callout=true)\npublic \n static \n void \n TargetFunc \n (",
                "TargetFunc",
            )
        ],
    },
    "dart": {
        "valid": [
            ("void TargetFunc()", "TargetFunc"),
            ("Future<int> TargetFunc()", "TargetFunc"),
            ("int get TargetFunc(", "TargetFunc"),
        ],
        "invalid": ["class TargetFunc", "var TargetFunc =", "if (TargetFunc)"],
        "pathological": [
            # Extreme modifier stacking
            (
                "@override\nexternal \n static \n final \n Future<List<Map<String, dynamic>>> \n TargetFunc \n (",
                "TargetFunc",
            )
        ],
    },
    "fortran": {
        "valid": [
            ("SUBROUTINE TargetFunc()", "TargetFunc"),
            ("REAL FUNCTION TargetFunc()", "TargetFunc"),
            ("PURE RECURSIVE FUNCTION TargetFunc()", "TargetFunc"),
        ],
        "invalid": ["END SUBROUTINE TargetFunc", "CALL TargetFunc", "TYPE TargetFunc"],
        "pathological": [
            # Excessive prefix stacking
            (
                "PURE \n RECURSIVE \n DOUBLE \n PRECISION \n FUNCTION \n TargetFunc \n (",
                "TargetFunc",
            )
        ],
    },
    "matlab": {
        "valid": [
            ("function [out] = TargetFunc(in)", "TargetFunc"),
            ("function TargetFunc()", "TargetFunc"),
        ],
        "invalid": ["if TargetFunc()", "classdef TargetFunc", "TargetFunc = 5"],
        "pathological": [
            # Splitting output arrays across newlines
            (
                "function \n [ \n out1 \n , \n out2 \n ] \n = \n TargetFunc \n (",
                "TargetFunc",
            )
        ],
    },
    "livecode": {
        "valid": [
            ("on TargetFunc", "TargetFunc"),
            ("command TargetFunc", "TargetFunc"),
            ("private function TargetFunc", "TargetFunc"),
        ],
        "invalid": ["script TargetFunc", "put TargetFunc", "repeat with TargetFunc"],
        "pathological": [("private \n command \n TargetFunc \n ", "TargetFunc")],
    },
    "objective-c": {
        "valid": [
            ("- (void)TargetFunc:", "TargetFunc"),
            ("+ (int)TargetFunc", "TargetFunc"),
            ("static void TargetFunc()", "TargetFunc"),
        ],
        "invalid": ["@interface TargetFunc", "TargetFunc()", "TargetFunc ="],
        "pathological": [
            # Fragmented return types
            (
                "- \n ( \n NSDictionary<NSString *, NSArray<NSNumber *> *> * \n ) \n TargetFunc \n :",
                "TargetFunc",
            )
        ],
    },
    "sqlite": {
        "valid": [
            ("CREATE TRIGGER TargetFunc", "TargetFunc"),
            ("CREATE VIEW TargetFunc", "TargetFunc"),
            ("CREATE UNIQUE INDEX TargetFunc", "TargetFunc"),
        ],
        "invalid": ["CREATE TABLE TargetFunc", "DROP VIEW TargetFunc"],
        "pathological": [
            (
                "CREATE \n TEMPORARY \n TRIGGER \n IF \n NOT \n EXISTS \n TargetFunc \n ",
                "TargetFunc",
            )
        ],
    },
    "abap": {
        "valid": [
            ("METHOD TargetFunc.", "TargetFunc"),
            ("FORM TargetFunc.", "TargetFunc"),
            ("FUNCTION TargetFunc.", "TargetFunc"),
        ],
        "invalid": ["CLASS TargetFunc", "DATA TargetFunc", "CALL FUNCTION TargetFunc"],
        "pathological": [("METHOD \n TargetFunc \n .", "TargetFunc")],
    },
    "perl": {
        "valid": [
            ("sub TargetFunc {", "TargetFunc"),
            ("method TargetFunc {", "TargetFunc"),
        ],
        "invalid": ["package TargetFunc", "my $TargetFunc", "goto TargetFunc"],
        "pathological": [("sub \n TargetFunc \n {", "TargetFunc")],
    },
    "haskell": {
        "valid": [
            ("TargetFunc :: Int -> Int", "TargetFunc"),
            ("TargetFunc :: Maybe String", "TargetFunc"),
        ],
        "invalid": ["data TargetFunc", "class TargetFunc", "newtype TargetFunc"],
        "pathological": [("TargetFunc \n :: \n Maybe \n ( \n Int \n -> \n Int \n )", "TargetFunc")],
    },
    "lua": {
        "valid": [
            ("function TargetFunc()", "TargetFunc"),
            ("local function TargetFunc(", "TargetFunc"),
        ],
        "invalid": ["TargetFunc = function()", "if TargetFunc() then"],
        "pathological": [("local \n function \n TargetFunc \n (", "TargetFunc")],
    },
    "scheme": {
        "valid": [
            ("(define (TargetFunc x y)", "TargetFunc"),
            ("(define (TargetFunc)", "TargetFunc"),
        ],
        "invalid": [
            "(define-record-type TargetFunc",
            "(if TargetFunc",
            "(let ((TargetFunc 1))",
        ],
        "pathological": [("( \n define \n ( \n TargetFunc \n x \n )", "TargetFunc")],
    },
    "makefile": {
        "valid": [("TargetFunc:", "TargetFunc"), ("TargetFunc::", "TargetFunc")],
        "invalid": [".PHONY: TargetFunc", "TargetFunc =", "ifeq TargetFunc"],
        "pathological": [("TargetFunc \t :", "TargetFunc")],
    },
    "assembly": {
        "valid": [("TargetFunc:", "TargetFunc"), ("_TargetFunc:", "_TargetFunc")],
        "invalid": ["jmp TargetFunc", "call TargetFunc", ".data:"],
        "pathological": [("_TargetFunc \t :", "_TargetFunc")],
    },
    "dockerfile": {
        "valid": [
            ("RUN apt-get update", "RUN"),
            ('CMD ["python"]', "CMD"),
            ('ENTRYPOINT ["sh"]', "ENTRYPOINT"),
        ],
        "invalid": ["FROM ubuntu", "ENV TargetFunc=1", "COPY . ."],
        "pathological": [("RUN \t apt-get \t update", "RUN")],
    },
    "typescript": {
        "valid": [
            ("function TargetFunc()", "TargetFunc"),
            ("export const TargetFunc = async () =>", "TargetFunc"),
            ("public get TargetFunc()", "TargetFunc")
        ],
        "invalid": ["class TargetFunc", "type TargetFunc", "interface TargetFunc"],
        "pathological": [("public \n async \n get \n TargetFunc \n (", "TargetFunc")]
    },
    "zig": {
        "valid": [("fn TargetFunc()", "TargetFunc"), ("pub fn TargetFunc()", "TargetFunc")],
        "invalid": ["const TargetFunc = struct", "var TargetFunc"],
        "pathological": [("pub \n export \n fn \n TargetFunc \n (", "TargetFunc")]
    },
    "solidity": {
        "valid": [("function TargetFunc()", "TargetFunc"), ("modifier TargetFunc()", "TargetFunc")],
        "invalid": ["contract TargetFunc", "struct TargetFunc"],
        "pathological": [("function \n TargetFunc \n (", "TargetFunc")]
    },
    "groovy": {
        "valid": [("def TargetFunc()", "TargetFunc"), ("public void TargetFunc()", "TargetFunc")],
        "invalid": ["class TargetFunc", "if (TargetFunc)"],
        "pathological": [("public \t static \t def \t TargetFunc \t (", "TargetFunc")]
    },
    "jcl": {
        "valid": [("//TargetFunc EXEC PGM=PROG", "TargetFunc")],
        "invalid": ["//TargetFunc DD DSN=", "//* TargetFunc EXEC"],
        "pathological": [("//TargetFunc \t EXEC ", "TargetFunc")]
    },
    "agc_assembly": {
        "valid": [("TargetFunc TC", "TargetFunc"), ("TargetFunc CA", "TargetFunc")],
        "invalid": ["TargetFunc EQUALS", "TargetFunc DEC"],
        "pathological": [("TargetFunc \t TC", "TargetFunc")]
    },
    "m4": {
        "valid": [("m4_define(`TargetFunc',", "m4_define"), ("AC_DEFUN([TargetFunc],", "AC_DEFUN")],
        "invalid": ["TargetFunc()", "define TargetFunc"],
        "pathological": [("m4_define \n (`TargetFunc',", "m4_define")]
    },
    "yacc": {
        "valid": [("TargetFunc:", "TargetFunc")],
        "invalid": ["%token TargetFunc", "case TargetFunc:"],
        "pathological": [("TargetFunc \t :", "TargetFunc")]
    },
    "css": {
        "valid": [("@media (max-width: 600px) {", "@media"), ("@keyframes TargetFunc {", "@keyframes")],
        "invalid": [".TargetFunc {", "#TargetFunc {"],
        "pathological": [("@media \n (max-width) \n {", "@media")]
    },
    "html": {
        "valid": [("<script>", "script"), ("<style>", "style")],
        "invalid": ["<div id='script'>", "<span class='style'>"],
        "pathological": [("<script \n >", "script")]
    },
    "tcl": {
        "valid": [("proc TargetFunc {", "TargetFunc")],
        "invalid": ["set TargetFunc", "if {$TargetFunc}"],
        "pathological": [("proc \t TargetFunc \t {", "TargetFunc")]
    },
    "embedded_python": {
        "valid": [("def TargetFunc()", "TargetFunc")],
        "invalid": ["class TargetFunc:", "TargetFunc = 1"],
        "pathological": [("@dec\nasync \t def \n TargetFunc \n (", "TargetFunc")]
    },
}


class TestFunctionExtraction:
    @pytest.mark.parametrize("lang_id", EXTRACTION_CASES.keys())
    def test_positive_function_extraction(self, lang_id):
        """
        Proves that valid function signatures are caught, and the regex
        isolates EXACTLY the function name, stripping away all modifiers/return types.
        Adapts dynamically to languages that use strict Capture Groups vs Full String matches.
        """
        cases = EXTRACTION_CASES.get(lang_id, {})
        if "valid" not in cases:
            pytest.skip(f"No valid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("func_start")
        if not pattern:
            pytest.skip(f"No func_start pattern defined for {lang_id}")

        for payload, expected_name in cases["valid"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] Iron Wall Blocked Valid Function: '{payload}'"

            # If the regex uses capture groups (like C#, C++, Rust, Swift), verify the exact group.
            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Regex matched but captured nothing!"
                assert expected_name in captured_groups, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean name '{expected_name}' from '{payload}'"
                )

            # If the regex relies on positive lookaheads without groups (like Python, JS, TS),
            # verify the matched substring safely contains the name.
            else:
                assert expected_name in match.group(0), (
                    f"[{lang_id}] Matched string {match.group(0)} failed to contain target '{expected_name}'"
                )

    @pytest.mark.parametrize("lang_id", EXTRACTION_CASES.keys())
    def test_negative_function_extraction(self, lang_id):
        """
        Proves that structural lookalikes (classes, if-statements, macros, invocations, interfaces)
        are explicitly ignored by the function spawner across all languages.
        """
        cases = EXTRACTION_CASES.get(lang_id, {})
        if "invalid" not in cases:
            pytest.skip(f"No invalid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("func_start")
        if not pattern:
            pytest.skip(f"No func_start pattern defined for {lang_id}")

        for payload in cases["invalid"]:
            match = pattern.search(payload)
            assert match is None, (
                f"[{lang_id}] 👻 GHOST SATELLITE HALLUCINATED! Erroneously spawned a function from: '{payload}'"
            )

    @pytest.mark.parametrize("lang_id", EXTRACTION_CASES.keys())
    def test_pathological_function_extraction(self, lang_id):
        """
        Adversarial Engineering: Proves the regex can survive "Frankenstein"
        formatting, including vertical newlines, massive generic blobs, and
        decorator stacking, while still cleanly extracting the function name.
        """
        cases = EXTRACTION_CASES.get(lang_id, {})
        if "pathological" not in cases:
            pytest.skip(f"No pathological cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("func_start")
        if not pattern:
            pytest.skip(f"No func_start pattern defined for {lang_id}")

        for payload, expected_name in cases["pathological"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] 💥 Engine choked on pathological formatting: '{payload}'"

            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Matched but captured nothing!"
                assert expected_name in captured_groups, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean name '{expected_name}'"
                )
            else:
                assert expected_name in match.group(0), (
                    f"[{lang_id}] Matched string failed to contain target '{expected_name}'"
                )
