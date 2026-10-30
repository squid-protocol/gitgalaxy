# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re

# #4975: Common HLASM opcodes that could follow an HLASM label named FILE, JOB,
# PRINT, REPORT, PROC, or SORT in column 1. Guarding these ensures an HLASM
# statement like `FILE DC CL80' '` or `JOB CSECT` is never mistaken for Easytrieve.
_HLASM_OPS = (
    r"DC|DS|EQU|USING|DROP|CSECT|DSECT|ORG|LTORG|AMODE|RMODE|MVC|CLC|MVI|CLI|"
    r"ST|LA|LR|AR|SR|BR|BAL|BALR|BC|BCR|J|NOP"
)
_HLASM_PRINT_OPS = r"NOGEN|GEN|ON|OFF|DATA|NODATA|MCALL|NOMCALL|MSUMMARY|NOMSUMMARY|UHEAD|NOUHEAD|" + _HLASM_OPS

# #7064: NASM / C-preprocessor `%` directives share the Easytrieve `%name` macro-call shape; a `.mac` holding them is NASM.
_NASM_COND = r"n?(?:def|ctx|idni?|macro|num|str|id|token|env|using)"
_NASM_DIRECTIVES = (
    rf"macro|imacro|unmacro|endmacro|exitmacro|define|xdefine|idefine|undef|assign|iassign|defstr|deftok|include|"
    rf"if(?:{_NASM_COND})?|elif(?:{_NASM_COND})?|else|endif|rep|endrep|exitrep|push|pop|rotate|line|error|"
    r"warning|pragma|strlen|substr|local|arg|stacksize|use|depend|pathsearch|clear"
)

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Easytrieve Plus / FOCUS",
        "last_updated": "2026-10-13",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    "extensions": [".ezt", ".mac", ".ezp"],
    "exact_matches": [],
    "discriminators": [".ezt", ".mac", ".ezp"],
    "shebangs": [],
    # #4975: Collision resolution for `.mac` (claimed by both hlasm and easytrieve).
    # Easytrieve claims `.mac` on Easytrieve evidence -- FILE, JOB, PRINT, REPORT,
    # PROC, SORT, macro definitions/calls, and hyphenated control boundaries.
    "internal_discriminator": re.compile(
        r"^[ \t]*(?:"
        rf"FILE[ \t]+(?!(?:{_HLASM_OPS})\b)[A-Za-z0-9&_-]+|"
        rf"JOB[ \t]+(?:INPUT\b|(?!(?:{_HLASM_OPS})\b)[A-Za-z0-9_-]+)|"
        rf"PRINT(?:[ \t]*$|[ \t]+(?!(?:{_HLASM_PRINT_OPS})\b)[A-Za-z0-9_-]+)|"
        rf"(?:REPORT|PROC|SORT)[ \t]+(?!(?:{_HLASM_OPS})\b)[A-Za-z0-9_-]+|"
        r"MACRO[ \t]+(?:&|[0-9]+\b|[A-Za-z0-9_-]+)|"
        r"(?:END-PROC|END-MACRO|END-JOB|END-REPORT|END-IF|END-DO|END-CASE)\b|"
        rf"%(?![0-9]|(?:{_NASM_DIRECTIVES})\b)[A-Za-z0-9_-]+"
        r")",
        re.M | re.I,
    ),
    "lexical_family": "line_exclusive",
    "identifier_case": "insensitive",
    "identifier_extra_chars": "-",
    "rules": {
        "calls_out": re.compile(r"\b(?:PERFORM|CALL|EXEC|EXECUTE)\b[ \t]+([A-Za-z0-9_-]+)", re.I),
        "branch": re.compile(r"\b(?:IF|ELSE|END-IF|DO|WHILE|UNTIL|CASE|WHEN|END-CASE)\b", re.I),
        "args": None,
        "structural_boundaries": re.compile(r"\b(?:END-PROC|END-MACRO|END-JOB|RETURN|GOTO|GO[ \t]+TO)\b", re.I),
        "func_start": re.compile(r"^[ \t]*(?:JOB|PROC|MACRO)[ \t]+([A-Za-z0-9_-]+)", re.I | re.M),
        "class_start": None,
        "safety": None,
        "safety_bypasses": None,
        "high_risk_execution": re.compile(r"\b(?:STOP|EXIT)\b", re.I),
        "io": re.compile(r"\b(?:GET|PUT|READ|WRITE|PRINT|DISPLAY)\b", re.I),
        "api": None,
        "state_mutation": re.compile(
            r"^[ \t]*([A-Za-z0-9_-]+)[ \t]*=|\bMOVE\b[ \t]+[A-Za-z0-9_'-]+[ \t]+\bTO\b", re.I | re.M
        ),
        "dead_code": re.compile(r"^[ \t]*\*[ \t]*(?:IF|PERFORM|GET|PUT|JOB|MACRO)\b", re.I | re.M),
        "doc": None,
        "test": None,
        "concurrency": None,
        "ui_framework": None,
        "events": None,
        "sync_locks": None,
        "explicit_casts": None,
        "memory_management": None,
        "panics_and_aborts": re.compile(r"\b(?:STOP|EXIT)\b", re.I),
        "cleanup": None,
        "immutability_locks": None,
        "globals": None,
        "pointers": None,
        "closures": None,
        "comprehensions": None,
        "generics": None,
        "ssr_boundaries": None,
        "hardcoded_secrets": re.compile(
            r"\b(?:PASSWORD|PASSWD|PWD|SECRET|KEY|TOKEN)\b[ \t]*=[ \t]*['\"][^'\"]{3,64}['\"]", re.I
        ),
        "dependency_injection": None,
        "test_skip": None,
        "macros": re.compile(r"^[ \t]*MACRO\b", re.I | re.M),
        "encapsulation": None,
        "bitwise_ops": None,
        "regex_execution": None,
        "crypto_algorithms": None,
        "crypto_entropy": None,
        "crypto_obfuscation": None,
        "planned_debt": re.compile(r"^[ \t]*\*[ \t]*(?:TODO|FIXME|HACK|XXX)\b", re.I | re.M),
    },
}
