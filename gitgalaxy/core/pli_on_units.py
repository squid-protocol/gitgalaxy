# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #3491 part 2: PL/I condition handling as unit-of-work / handler rows.
#
# PL/I's error handling is the ON statement, not CICS HANDLE: `ON cond on-unit`
# installs a handler for a condition until a REVERT (or the block ends). Each
# becomes a `uow_handler_data` row in the shape core/uow_handlers.py documents:
#
#   kind      source  verb    condition (as written)   target      target_kind
#   ON_UNIT   PLI     ON      ERROR | ENDFILE(F) | ... -           SYSTEM  `ON c SYSTEM;`
#                                                       -           NULL    `ON c;` (swallows it)
#                                                       -           BLOCK   `ON c BEGIN; ... END;`
#                                                       the name    PROCEDURE `ON c CALL x;`
#                                                       the label   LABEL   `ON c GO TO x;`
#                                                       -           STATEMENT any other statement
#   REVERT    PLI     REVERT  the condition            -           -
#   SIGNAL    PLI     SIGNAL  the condition            -           -
#   attributes: `SNAP` when the ON statement codes it.
#
# The condition vocabulary is the pli standard's own (_ON_BARE / _ON_FILE): a file
# condition or CONDITION(name) needs its parenthesised reference, so prose such as
# `ON WEDNESDAY` or a data name `ON_KEY` never reads as a handler. An ON / REVERT /
# SIGNAL counts only where a statement can begin -- after `;`, a label's `:`,
# THEN / ELSE / OTHERWISE, or at the start of the stream.
# ==============================================================================
import bisect
import re
from typing import Any

from gitgalaxy.core.pli_calls import blank_sequence_fields
from gitgalaxy.standards.language_standards.languages.pli import _ON_BARE, _ON_FILE

_ID = r"[\w@#$]+"
_CONDITION = r"(" + _ON_BARE + r"(?![\w@#$])|" + _ON_FILE + r")"
_ON = re.compile(r"(?<![\w@#$%.])ON[ \t\r\n]+" + _CONDITION + r"[ \t\r\n]*(SNAP(?![\w@#$]))?[ \t\r\n]*", re.I)
_REVERT_SIGNAL = re.compile(r"(?<![\w@#$%.])(REVERT|SIGNAL)[ \t\r\n]+" + _CONDITION, re.I)
_UNIT_HEAD = re.compile(
    r"(SYSTEM)[ \t\r\n]*;|(;)|(BEGIN)(?![\w@#$])|CALL[ \t\r\n]+(" + _ID + r")|GO[ \t]*TO[ \t\r\n]+(" + _ID + r")",
    re.I,
)
# What may sit between a statement boundary and the ON: blanks, and sequence fields
# that end their line -- a comment the code stream removed can leave its line's
# `00000390` alone there (DSF GML/R0019955.pli opens with a comment block).
_GAP = r"(?:[ \t\r\n]|[A-Z@#$]{0,6}[0-9]{2,8}(?=[ \t]*\r?\n))*"
_STATEMENT_START = re.compile(r"(?:^|[;:]|(?<![\w@#$])(?:THEN|ELSE|OTHERWISE))" + _GAP + r"$", re.I)


def _starts_statement(text: str, offset: int) -> bool:
    return _STATEMENT_START.search(text[max(0, offset - 120) : offset]) is not None


def _condition(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


def pli_on_units(code_stream: str) -> list[dict[str, Any]]:
    """Every ON / REVERT / SIGNAL statement of one PL/I code stream (see the header)."""
    upper = code_stream.upper()
    if "ON" not in upper and "REVERT" not in upper and "SIGNAL" not in upper:
        return []
    text = blank_sequence_fields(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def row(kind: str, verb: str, offset: int, **extra: Any) -> dict[str, Any]:
        out = {"kind": kind, "source": "PLI", "verb": verb, "condition": None, "target": None,
               "target_kind": None, "resp_var": None, "attributes": None,
               "line": bisect.bisect_left(newlines, offset) + 1}  # fmt: skip
        out.update(extra)
        return out

    rows = []
    for m in _ON.finditer(text):
        if not _starts_statement(text, m.start()):
            continue
        head = _UNIT_HEAD.match(text, m.end())
        target, target_kind = None, "STATEMENT"
        if head:
            if head.group(1):
                target_kind = "SYSTEM"
            elif head.group(2):
                target_kind = "NULL"
            elif head.group(3):
                target_kind = "BLOCK"
            elif head.group(4):
                target, target_kind = head.group(4).upper(), "PROCEDURE"
            else:
                target, target_kind = head.group(5).upper(), "LABEL"
        rows.append(row("ON_UNIT", "ON", m.start(), condition=_condition(m.group(1)), target=target,
                        target_kind=target_kind, attributes="SNAP" if m.group(2) else None))  # fmt: skip
    for m in _REVERT_SIGNAL.finditer(text):
        if _starts_statement(text, m.start()):
            verb = m.group(1).upper()
            rows.append(row(verb, verb, m.start(), condition=_condition(m.group(2))))
    rows.sort(key=lambda r: r["line"])
    return rows
