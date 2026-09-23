# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

DEFINITION: dict[str, Any] = {
    "_meta": {"target_version": "Windows CMD/Batch", "status": "production"},
    "extensions": [".bat", ".cmd"],
    "exact_matches": [],
    "discriminators": [],
    "shebangs": [],
    "lexical_family": "line_exclusive",
    # #3338: labels are case-insensitive (`call :BUILD` reaches `:build`), and a
    # label name may carry `-` and `.` (the func_start/calls_out name class), so
    # the unreferenced_by_name census reads a batch name the way CMD does (#3198).
    "identifier_case": "insensitive",
    "identifier_extra_chars": "-.",
    # Collision resolution for `.cmd` (#2504: rexx claims it too, and batch's
    # empty rules dict scores 0 in the Tier 3 lexical scan, so without a
    # Tier 2 anchor every real batch file would lose the scan to any language
    # with rules). These are batch-only line shapes REXX cannot carry:
    # `@echo off/on`, SETLOCAL/ENDLOCAL, `goto :label`, the `%~dp0`/`%%~x`
    # argument modifiers and `%ERRORLEVEL%`/`errorlevel N` tests. Bare `rem`
    # and `set X=1` are deliberately left out -- `rem = n // 7` and
    # `set = 1` are legal REXX assignments (registry order checks batch's
    # discriminator FIRST, so a false batch hit on real REXX would lock the
    # wrong language, the costlier direction).
    "internal_discriminator": re.compile(
        r"^[ \t]*@?ECHO[ \t]+(?:OFF|ON)\b"
        r"|^[ \t]*(?:SETLOCAL|ENDLOCAL)\b"
        r"|^[ \t]*GOTO[ \t]+:?[A-Za-z_]"
        r"|^[ \t]*@?SET[ \t]+\"?[A-Za-z_][\w]{0,63}="
        r"|^[ \t]*IF[ \t]+(?:NOT[ \t]+)?(?:EXIST|DEFINED)\b"
        r"|%%?~[A-Za-z]{0,10}[0-9]"
        r"|%ERRORLEVEL%"
        r"|\bERRORLEVEL[ \t]+[0-9]",
        re.M | re.I,
    ),
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        "calls_out": re.compile(r"^[ \t]*call[ \t]+:?([A-Za-z_][\w.-]*)", re.I | re.M),
        # #3338 func_start: a `:label` opens a unit only when it is a SUBROUTINE --
        # the target of a `call :label` somewhere in the same file, CMD's one
        # invoke-by-name form. A label is also a `goto` target, and the syntax
        # does not tell the two apart, so the regex matches every label and the
        # `batch_call_target` scope filter (detector.py) keeps the called ones.
        # Measured on language-crucible v1.4.0: of the 7 labels in batch/, only
        # buildrelease.bat's `:build` (3 `call :build` sites, ends `exit /B 0`)
        # is a subroutine; `:CheckOpts` is an option-parsing loop head,
        # `:builddoc`/`:skipdoc` are fall-through sections and `:Help` is a
        # goto-reached exit. `::` (the comment idiom) never matches: `:` is not
        # in the name class. Name bounded to 64 chars (ReDoS-flat).
        "func_start": re.compile(r"^[ \t]*:([A-Za-z_][\w.-]{0,63})", re.M),
        "_scope_filters": {"func_start": "batch_call_target"},
    },
}
