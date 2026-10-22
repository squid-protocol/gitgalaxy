# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #5736: SQL routine call sites (`call_site_data`).
#
# `calls_out_to` (#5635) is the function-level reading: every `name(` a routine body
# invokes. `call_site_data` is the program-level one, as for COBOL and PL/I: a
# `CALL name` that leaves the file. A `CALL` of a procedure the same file creates is
# a function-level edge only; one naming a routine defined elsewhere is a call site,
# resolved by invocation_resolver against the repository's SQL routines. Only the
# `CALL` verb counts: `PERFORM f()` / `SELECT f()` are expressions, not invocations.
# The code stream arrives with comments removed and string literals shielded, so a
# `-- CALL x` remark or a quoted `'CALL x'` never reads as a site.
# ==============================================================================
import bisect
import re
from typing import Any
from collections.abc import Callable

_ID = r"[\w#$@]"
_NAME = r'(?:"[^"\n]{1,128}"|' + _ID + r"{1,128})"
_CALL = re.compile(
    r"(?<![\w#$@.])CALL[ \t\r\n]+((?:" + _NAME + r"[ \t]*\.[ \t]*){0,2})(" + _NAME + r")(?![\w#$@])",
    re.I,
)
_DEFINED = re.compile(
    r"(?<![\w#$@.])CREATE[ \t\r\n]+(?:OR[ \t\r\n]+REPLACE[ \t\r\n]+)?(?:PROCEDURE|FUNCTION)[ \t\r\n]+"
    r"(?:" + _NAME + r"[ \t]*\.[ \t]*){0,2}(" + _NAME + r")(?![\w#$@])",
    re.I,
)


def _bare(name: str) -> str:
    return name.strip('"').upper()


def sql_external_calls(code_stream: str, shielded: Callable[[int], bool] | None = None) -> list[dict[str, Any]]:
    """`CALL name` sites whose routine is not created in this file (see the header)."""
    if "CALL" not in code_stream.upper():
        return []
    local = {_bare(m.group(1)) for m in _DEFINED.finditer(code_stream)}
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    rows = []
    for m in _CALL.finditer(code_stream):
        name = _bare(m.group(2))
        if name in local or (shielded is not None and shielded(m.start())):
            continue
        rows.append(
            {
                "verb": "CALL",
                "form": "literal",
                "operand": name,
                "target": name,
                "line": bisect.bisect_left(newlines, m.start()) + 1,
            }
        )
    return rows
