# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #3495: command-level EXEC CICS in HLASM.
#
# The CICS command walkers (cics_resources, cics_tasks, uow_handlers and the
# LINK/XCTL/TRANSID call-site reader) bound a command at END-EXEC (COBOL) or `;`
# (PL/I). An assembler command has neither: it is one assembler statement,
# continued by a non-blank column 72 and resuming at column 16. `cics_stream`
# rewrites a source into the COBOL shape the walkers already read, so each fact
# is extracted by the same code for every host language:
#   - comment lines (`*` / `.*` in column 1) are blanked;
#   - columns 72-80 (continuation mark + sequence field) are blanked;
#   - the last line of every `EXEC CICS` statement gets ` END-EXEC` appended.
# No line is added or removed, so every walker's line numbers are the source's.
#
# `dc_values` is the assembler's VALUE map: `NAME DC C'text'` / `CLn'text'`
# defines the constant an operand such as `ABCODE(AB_001)` names.
# ==============================================================================
import re

_EXEC_CICS = re.compile(r"^\S*[ \t]+EXEC[ \t]+CICS(?:[ \t]|$)", re.I)
_DC_CHAR = re.compile(r"^C(?:L[0-9]{1,3})?'([^']*)'", re.I)
# An HLASM symbol: a letter or @#$_ first, then up to 62 more of those or digits.
_DC_STATEMENT = re.compile(r"^([A-Z@#$_][A-Z0-9@#$_]{0,62})[ \t]+DC[ \t]+(\S.*)$", re.I)
_STATEMENT_LIMIT = 200  # lines one statement may continue over


def _is_comment(line: str) -> bool:
    return line.startswith("*") or line.startswith(".*")


def cics_stream(code_stream: str) -> str:
    """The source with comments and columns 72-80 blanked and each EXEC CICS
    statement closed by END-EXEC on its last line (line-aligned)."""
    if "CICS" not in code_stream.upper():
        return code_stream
    lines = code_stream.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or _is_comment(raw):
            out.append(" " * len(raw.rstrip("\r")) + ("\r" if raw.endswith("\r") else ""))
            i += 1
            continue
        start, text = i, raw[:71]
        # Continued while column 72 is non-blank; the next line resumes at column 16.
        while len(lines[i].rstrip("\r")) > 71 and lines[i][71] != " " and i + 1 < len(lines) and i - start < _STATEMENT_LIMIT:
            i += 1
            text += " " + lines[i][15:71]
        is_cics = _EXEC_CICS.match(text) is not None
        for j in range(start, i + 1):
            line = lines[j]
            cr = "\r" if line.endswith("\r") else ""
            # A continuation resumes at column 16, but real source drifts a column
            # (zECS ZECS002.asm puts `NOHANDLE` in column 15), so columns 1-15 are kept.
            kept = line.rstrip("\r")[:71]
            if is_cics and j == i:
                kept += " END-EXEC"
            out.append(kept + cr)
        i += 1
    return "\n".join(out)


def dc_values(code_stream: str) -> dict[str, str]:
    """`NAME DC C'text'` (or `CLn'text'`) -> {NAME: text}: the constants a CICS
    operand can name. The first definition of a name wins."""
    values: dict[str, str] = {}
    for line in code_stream.split("\n"):
        if _is_comment(line):
            continue
        m = _DC_STATEMENT.match(line.rstrip("\r")[:71])
        if not m:
            continue
        char = _DC_CHAR.match(m.group(2))
        # A CICS name is blank-padded to its field (`CL8'ZECS003 '`); the pad is not the name.
        if char and char.group(1).strip():
            values.setdefault(m.group(1).upper(), char.group(1).strip())
    return values
