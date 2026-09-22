# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Independent CICS transaction-map reader for the refraction differential (#3247).

The `old` (forge) side of the transaction datum: a self-contained scan of a repo's
CSD decks -- standalone `.csd` files and the DFHCSDUP SYSIN carried inline in a JCL
job -- that yields the transaction -> program map. It does NOT import the engine
(`gitgalaxy.core.mainframe_boundary`) or the answer key, so the differential
compares two independent parses of the same decks. The parse mirrors the engine's
`_csd_transactions` reading (record splitting with no continuation character,
paren-balanced attribute values, DB2TRAN exclusion, the `DEFINE PROGRAM ... TRANSID`
autoinstall pairing) so a delta is a real disagreement, not a modelling choice.

Every regex is bounded and line/record-scoped (the #3200/#3201 forge discipline).
"""

import re
from pathlib import Path
from typing import Optional

# A CSD command opens a line (tolerating a leading blank column or JCL-inline
# indentation). Only DEFINE carries a resource we keep; the rest merely terminate
# the record before them.
_CSD_COMMAND = re.compile(r"^[ \t]*(DEFINE|DELETE|ALTER|ADD|REMOVE|LIST|UPGRADE|COPY)\b", re.I)
# The head of a DEFINE record: the resource type and its name (permissive run; an
# over-long name is DFHCSDUP's diagnostic, not ours).
_CSD_DEFINE_HEAD = re.compile(r"^[ \t]*DEFINE[ \t]+([A-Z0-9]+)[ \t]*\([ \t]*([A-Z0-9@#$]+)[ \t]*\)", re.I)
# A `KEYWORD(` attribute opener; the value is read by the paren-balanced scan below.
_CSD_ATTR_KEY = re.compile(r"\b([A-Z][A-Z0-9]*)[ \t]*\(", re.I)
# Attribute-name abbreviations DFHCSDUP accepts (carddemo inline JCL); only the ones
# touching a field we keep need mapping.
_CSD_ATTR_SYNONYMS = {"DESC": "DESCRIPTION"}
# A DFHCSDUP/CEDA deck runs DFHCSDUP; a JCL that does not is not a CSD deck.
_DFHCSDUP = re.compile(r"\bPGM=DFHCSDUP\b", re.I)
_TXN_RESOURCE = "TRANSACTION"
_PGM_RESOURCE = "PROGRAM"
# DEFINE DB2TRAN/DB2ENTRY/DB2CONN carry a TRANSID(...) that is a DB2 attribute, not
# a CICS transaction definition, and must be excluded.
_EXCLUDED_RESOURCES = frozenset({"DB2TRAN", "DB2ENTRY", "DB2CONN"})


def _csd_records(text: str) -> list[tuple[int, str]]:
    """Split a CSD deck into (1-based start line, record text) DEFINE records.

    A CSD record has no continuation character: a DEFINE runs until the next
    command, a `*` comment, a JCL `//` line, a blank line, or end of deck. That
    tolerance lets one reader serve a `.csd` file, a hand-written SYSIN member and
    the inline SYSIN inside a JCL job (whose `//` control lines cleanly separate the
    DEFINE records they surround).
    """
    records: list[tuple[int, list[str]]] = []
    current: Optional[tuple[int, list[str]]] = None

    def _flush() -> None:
        nonlocal current
        if current is not None:
            records.append(current)
            current = None

    for lineno, raw in enumerate(text.split("\n"), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*") or raw.lstrip().startswith("//"):
            _flush()
            continue
        command = _CSD_COMMAND.match(raw)
        if command:
            _flush()
            if command.group(1).upper() == "DEFINE":
                current = (lineno, [raw])
            continue
        if current is not None:
            current[1].append(raw)

    _flush()
    return [(start, "\n".join(lines)) for start, lines in records]


def _csd_attributes(record: str) -> dict[str, str]:
    """Every `KEYWORD(value)` attribute in one DEFINE record, first value winning.

    Paren-balanced and quote-aware: real values carry commas (`WAITTIME(0,0,0)`),
    spaces and slashes (`DESCRIPTION('Credit/Debit')`).
    """
    attrs: dict[str, str] = {}
    for m in _CSD_ATTR_KEY.finditer(record):
        key = m.group(1).upper()
        key = _CSD_ATTR_SYNONYMS.get(key, key)
        depth = 1
        i = m.end()
        quote: Optional[str] = None
        chars: list[str] = []
        while i < len(record) and depth > 0:
            ch = record[i]
            if quote is not None:
                if ch == quote:
                    quote = None
                chars.append(ch)
            elif ch in "'\"":
                quote = ch
                chars.append(ch)
            elif ch == "(":
                depth += 1
                chars.append(ch)
            elif ch == ")":
                depth -= 1
                if depth > 0:
                    chars.append(ch)
            else:
                chars.append(ch)
            i += 1
        attrs.setdefault(key, "".join(chars).strip())
    return attrs


def _deck_transactions(text: str) -> list[tuple[str, Optional[str]]]:
    """The (transid, program) pairs in one CSD deck. `program` is None when a
    DEFINE TRANSACTION names no PROGRAM operand (a program-less transaction)."""
    out: list[tuple[str, Optional[str]]] = []
    for _line, record in _csd_records(text):
        head = _CSD_DEFINE_HEAD.match(record)
        if not head:
            continue
        resource = head.group(1).upper()
        name = head.group(2).upper()
        if resource in _EXCLUDED_RESOURCES:
            continue
        attrs = _csd_attributes(record)
        if resource == _TXN_RESOURCE:
            out.append((name, (attrs.get("PROGRAM") or "").upper() or None))
        elif resource == _PGM_RESOURCE and attrs.get("TRANSID"):
            out.append((attrs["TRANSID"].upper(), name))
    return out


def extract_transactions(repo: Path) -> dict[str, set[str]]:
    """program-id (upper) -> the set of transaction ids that entry-point into it.

    Scans every `.csd` deck and every JCL job that runs DFHCSDUP inline under
    `repo`. A transaction whose program is not a string (program-less) contributes
    to no program's entry set. This is the forge/independent view the differential
    diffs against the engine's `transaction_map`.
    """
    by_program: dict[str, set[str]] = {}

    def _add(pairs: list[tuple[str, Optional[str]]]) -> None:
        for transid, program in pairs:
            if program:
                by_program.setdefault(program, set()).add(transid)

    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        suffix = path.suffix.lower()
        if suffix == ".csd":
            _add(_deck_transactions(path.read_text(encoding="utf-8", errors="ignore")))
        elif suffix == ".jcl":
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _DFHCSDUP.search(text):
                _add(_deck_transactions(text))
    return by_program
