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
    },
}
