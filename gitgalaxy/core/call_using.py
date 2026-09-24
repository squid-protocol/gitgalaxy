# ==============================================================================
# GitGalaxy Core: batch CALL USING contracts (#3454)
#
# PURPOSE:
# #3355 matched a CICS LINK / XCTL COMMAREA to the callee's DFHCOMMAREA. A batch
# `CALL 'X' USING A B C` passes its data positionally to the callee's
# `PROCEDURE DIVISION USING P Q R` (or an `ENTRY 'X' USING ...`), and neither
# side was recorded, so an arity or length mismatch between them was invisible.
# Two readings, both per file:
#
#   call_using_args(stream, offset)  the USING list of the CALL whose target ends
#                                    at `offset` -> call_site_data.using_args
#   entry_points(stream)             each PROCEDURE DIVISION USING / ENTRY 'X'
#                                    USING -> entry_point_data
#
# An argument list is comma-joined, one item per position:
#   NAME            BY REFERENCE (the default), qualifiers kept: `A OF B`
#   CONTENT:NAME    BY CONTENT;  VALUE:NAME  BY VALUE (the mode carries on to the
#                   following items until another BY)
#   ADDRESS OF X / LENGTH OF X / OMITTED / a quoted literal, as written
# Subscripts and reference modifiers are dropped (`X(I)` is X).
#
# SCOPE AND NON-SCOPE:
#   - Extraction only. Pairing a CALL with its callee's entry point, and each
#     argument with the parameter in its position (arity, byte length through
#     record_layout), is the reader's (GalaxyIR.call_contracts).
#   - The list ends at RETURNING, ON / NOT ON EXCEPTION / OVERFLOW, END-CALL, a
#     period, or the next statement's verb; it is capped at `_MAX_TOKENS`.
#   - Sequence fields are blanked first, so a numbered line's cols 73-80 tag is
#     never read as an argument.
# ==============================================================================
import bisect
import re
from typing import Any, Optional

from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_TOKEN = re.compile(r"'[^'\n]{0,160}'|\"[^\"\n]{0,160}\"|[A-Z0-9][A-Z0-9-]{0,62}|[(),.]", re.I)
_MAX_TOKENS = 400
_STOP = frozenset({"RETURNING", "ON", "NOT", "END-CALL", "EXCEPTION", "OVERFLOW", "GIVING"})
# A statement verb ends an unterminated USING list (`CALL 'X' USING A` + `MOVE ...`).
_VERBS = frozenset(
    {
        "ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY",
        "DIVIDE", "ELSE", "END-EVALUATE", "END-IF", "END-PERFORM", "END-READ", "END-SEARCH", "END-STRING",
        "EVALUATE", "EXEC", "EXIT", "GO", "GOBACK", "IF", "INITIALIZE", "INSPECT", "MERGE", "MOVE",
        "MULTIPLY", "OPEN", "PERFORM", "READ", "RELEASE", "RETURN", "REWRITE", "SEARCH", "SET", "SORT",
        "START", "STOP", "STRING", "SUBTRACT", "UNSTRING", "WHEN", "WRITE", "COPY",
    }
)  # fmt: skip
_MODES = {"REFERENCE": "", "CONTENT": "CONTENT:", "VALUE": "VALUE:"}
_PROC_USING = re.compile(r"(?<![A-Z0-9-])PROCEDURE[ \t\n]{1,200}DIVISION(?![A-Z0-9-])", re.I)
_ENTRY = re.compile(r"(?<![A-Z0-9-])ENTRY[ \t\n]{1,200}(?:'([^'\n]{1,30})'|\"([^\"\n]{1,30})\")", re.I)
_WINDOW = 6000


def _args(text: str, start: int) -> Optional[str]:
    """The USING list starting at `start` (just past the callee / DIVISION / ENTRY
    name), or None when no USING follows."""
    toks = [m.group(0) for m in _TOKEN.finditer(text, start, min(len(text), start + _WINDOW))][:_MAX_TOKENS]
    if not toks or toks[0].upper() != "USING":
        return None
    out: list[str] = []
    mode = ""
    i = 1
    while i < len(toks):
        t = toks[i]
        up = t.upper()
        if t == ".":
            break
        if t == ",":
            i += 1
            continue
        if up in _STOP or up in _VERBS:
            break
        if up == "BY" and i + 1 < len(toks) and toks[i + 1].upper() in _MODES:
            mode = _MODES[toks[i + 1].upper()]
            i += 2
            continue
        if up in _MODES:
            mode = _MODES[up]
            i += 1
            continue
        if up in ("ADDRESS", "LENGTH") and i + 2 < len(toks) and toks[i + 1].upper() == "OF":
            out.append(f"{mode}{up} OF {toks[i + 2].upper()}")
            i += 3
            continue
        if up == "OMITTED" or t[0] in "'\"":
            out.append(f"{mode}{up if up == 'OMITTED' else t}")
            i += 1
            continue
        if not re.match(r"[A-Z]", up) and not re.match(r"[0-9]", up):
            i += 1
            continue
        name = up
        i += 1
        while i + 1 < len(toks) and toks[i].upper() in ("OF", "IN"):
            name += f" OF {toks[i + 1].upper()}"
            i += 2
        if i < len(toks) and toks[i] == "(":
            depth = 0
            while i < len(toks):
                if toks[i] == "(":
                    depth += 1
                elif toks[i] == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
        out.append(f"{mode}{name}")
    return ",".join(out) if out else None


def call_using_args(blanked_stream: str, offset: int) -> Optional[str]:
    """The USING list of the CALL whose callee operand ends at `offset`, read from a
    stream whose sequence fields are already blanked (`blank_stream`, once per
    file: blanking a slice would measure columns from the slice, not the line)."""
    return _args(blanked_stream, offset)


def blank_stream(code_stream: str) -> str:
    """The code stream with fixed-format sequence fields blanked, offsets unchanged."""
    return _blank_sequence_fields(code_stream, "cobol")


def entry_points(code_stream: str) -> list[dict[str, Any]]:
    """Every PROCEDURE DIVISION [USING ...] and ENTRY 'X' [USING ...] of one file."""
    if not code_stream or "DIVISION" not in code_stream.upper():
        return []
    text = _blank_sequence_fields(code_stream, "cobol")
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    rows: list[dict[str, Any]] = [
        {
            "kind": "PROCEDURE",
            "entry_name": None,
            "params": _args(text, m.end()),
            "line": bisect.bisect_left(newlines, m.start()) + 1,
        }
        for m in _PROC_USING.finditer(text)
    ]
    rows.extend(
        {
            "kind": "ENTRY",
            "entry_name": (m.group(1) or m.group(2) or "").strip().upper() or None,
            "params": _args(text, m.end()),
            "line": bisect.bisect_left(newlines, m.start()) + 1,
        }
        for m in _ENTRY.finditer(text)
    )
    rows.sort(key=lambda r: r["line"])
    return rows
