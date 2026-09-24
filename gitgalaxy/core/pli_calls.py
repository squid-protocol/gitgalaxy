# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #3491: PL/I program call sites.
#
# Two readings join the COBOL call-site channel (`call_site_data`):
#   - `pli_cics_stream` closes every `EXEC CICS ... ;` with END-EXEC (inserted
#     before its `;`, so no line moves) -- the COBOL LINK / XCTL / RETURN|START|RUN
#     TRANSID reader then reads PL/I unchanged, operands resolving through the
#     DCL ... INIT values of `_pli_value_map`.
#   - `pli_external_calls`: `CALL name` / `CALL name(args)` whose name is NOT a
#     procedure or ENTRY label of the same file. A call to an internal procedure
#     is a function-level edge (`fcall_data`, via calls_out); only a call leaving
#     the compilation unit -- an external entry, another load module, PLITDLI --
#     is a program call site. PL/I names the entry itself, so its target is the
#     name as written (form `literal`, like COBOL's `CALL 'X'`).
# Names are PL/I identifiers: letters (national letters included -- navikt/DSF's
# `ÅPNE_DATABASE`, #3520), digits, `_ @ # $`, case-insensitive (upper-cased).
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

_ID = r"[\w@#$]"
_EXEC_CICS = re.compile(r"(?<![\w@#$])EXEC[ \t\r\n]+CICS(?![\w@#$])", re.I)
# `label:` then PROC / PROCEDURE / ENTRY, with further labels, blanks, line breaks
# and 8-digit sequence fields (columns 73-80) allowed between.
_LABELLED_UNIT = re.compile(
    r"(?<![\w@#$%])(" + _ID + r"{1,64})[ \t]*:(?:[\s0-9]{0,200}?" + _ID + r"{1,64}[ \t]*:)*"
    r"[\s0-9]{0,200}?(?:PROC(?:EDURE)?|ENTRY)(?![\w@#$])",
    re.I,
)
# The name may sit on the next line, past the 8-digit sequence field (columns
# 73-80) that ends the CALL's own line; an identifier never starts with a digit.
_CALL = re.compile(
    r"(?<![\w@#$%.])CALL(?:[ \t]*[0-9]{8})?[ \t\r\n]+((?![0-9])" + _ID + r"{1,64})(?![\w@#$])", re.I
)
_BLOCK_LIMIT = 2000  # characters one EXEC CICS statement may run over


def _statement_end(code: str, start: int) -> int:
    """Offset of the `;` ending the statement that starts at `start` (outside '...'),
    or -1 when none follows within _BLOCK_LIMIT."""
    quoted = False
    for i in range(start, min(len(code), start + _BLOCK_LIMIT)):
        ch = code[i]
        if ch == "'":
            quoted = not quoted
        elif ch == ";" and not quoted:
            return i
    return -1


# A columns 73-80 sequence field, recognised by SHAPE, not column: the code stream
# has comments removed (a leading `/*YS*/` shifts the rest of its line left), and a
# national letter took two bytes of an EBCDIC column. So: the last token of a line,
# after two or more blanks, of up to 6 letters then 2-8 digits (`00001740`, DSF's
# `R0015160`). A statement's own trailing number is preceded by one blank at most.
_SEQUENCE_FIELD = re.compile(r"(?m)(?<=[ \t]{2})([A-Z@#$]{0,6}[0-9]{2,8})[ \t]*(?=\r?$)", re.I)


def blank_sequence_fields(code_stream: str) -> str:
    """Columns 73-80 sequence fields replaced by blanks (offsets unchanged)."""
    return _SEQUENCE_FIELD.sub(lambda m: " " * len(m.group(0)), code_stream)


def pli_cics_stream(code_stream: str) -> str:
    """The code stream with ` END-EXEC` inserted before each EXEC CICS's `;`, and
    every columns 73-80 sequence field blanked -- navikt/DSF writes `EXEC CICS LINK
    PROGRAM` with its `('R0015501')` on the next line, and the sequence number that
    ends the first line sat between the keyword and its operand."""
    if "CICS" not in code_stream.upper():
        return code_stream
    code_stream = blank_sequence_fields(code_stream)
    out, pos = [], 0
    for m in _EXEC_CICS.finditer(code_stream):
        if m.start() < pos:
            continue  # inside the previous command
        end = _statement_end(code_stream, m.end())
        if end == -1:
            continue
        out.append(code_stream[pos:end])
        out.append(" END-EXEC")
        pos = end
    out.append(code_stream[pos:])
    return "".join(out)


def internal_names(code_stream: str) -> set[str]:
    """Every procedure / ENTRY label of the file, upper-cased."""
    return {m.group(1).upper() for m in _LABELLED_UNIT.finditer(code_stream)}


def pli_external_calls(code_stream: str, shielded: Optional[Callable[[int], bool]] = None) -> list[dict[str, Any]]:
    """`CALL name` sites whose name is not defined in this file (see the header)."""
    if "CALL" not in code_stream.upper():
        return []
    code_stream = blank_sequence_fields(code_stream)  # DSF: `SKRIV_FEILLISTE:  R0015160` / `PROC;`
    local = internal_names(code_stream)
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    rows = []
    for m in _CALL.finditer(code_stream):
        name = m.group(1).upper()
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
