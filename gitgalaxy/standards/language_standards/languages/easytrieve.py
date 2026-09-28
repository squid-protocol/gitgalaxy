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

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Easytrieve Plus / FOCUS",
        "last_updated": "2026-09-28",
        "blueprint_version": "v6.3",
        "status": "production"
    },
    "extensions": [".ezt", ".mac", ".ezp"],
    "exact_matches": [],
    "discriminators": [],
    "shebangs": [],
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
        "state_mutation": re.compile(r"^[ \t]*([A-Za-z0-9_-]+)[ \t]*=|\bMOVE\b[ \t]+[A-Za-z0-9_'-]+[ \t]+\bTO\b", re.I | re.M),
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
        "hardcoded_secrets": re.compile(r"\b(?:PASSWORD|PASSWD|PWD|SECRET|KEY|TOKEN)\b[ \t]*=[ \t]*['\"][^'\"]{3,64}['\"]", re.I),
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
    }
}
