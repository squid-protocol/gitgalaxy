# ==============================================================================
# GitGalaxy Core: BMS Screen-Field Layout Extraction (#3347, roadmap #3249)
#
# PURPOSE:
# A BMS map source defines a CICS 3270 screen with three HLASM macros: DFHMSD
# (the mapset), DFHMDI (a map inside it) and DFHMDF (a field on that map). The
# counted rules say THAT a file builds a screen (`ui_framework`, the named DFHMDF
# `args`). This channel says WHAT: every field's name, position `POS=(line,col)`,
# `LENGTH`, `ATTRB`, `PICIN`/`PICOUT`, `INITIAL` and `OCCURS`, under the map and
# mapset that own it. It is the source of the symbolic-map copybook a COBOL
# program `COPY`s (`<map>I`/`<map>O` with `<field>L/F/A/I/O` per named field),
# which is all the refraction differential could see of a map before.
#
# SHAPE:
# A flat, source-ordered list of dicts, one per macro statement, with `kind`
# 'mapset' | 'map' | 'field' and the tree carried as `ordinal`/`parent_ordinal`
# (a map's parent is its mapset, a field's parent is its map), the same flat
# discipline as the record channel. An unnamed DFHMDF is a screen literal (a
# label): it is a real field of the screen layout -- it occupies a position --
# and is emitted with `name` None; only a NAMED field reaches the symbolic map.
# Operands with a column of their own are parsed into it; every other operand
# (COLOR, HILIGHT, JUSTIFY, GRPNAME, a scalar POS=n, and a map's SIZE/LINE/
# COLUMN or a mapset's TYPE/MODE/LANG ...) is kept as written in `attributes`.
#
# WHY A STATEMENT JOINER AND NOT ONE REGEX:
# An HLASM statement continues onto the next line when column 72 is non-blank,
# and the continuation resumes in column 16. Operands end at the first blank
# outside a quoted string (the rest of the line is positional remarks), and a
# quoted INITIAL literal may itself be split mid-word across lines (CBSA:
# `INITIAL='Please provide ... and pr*` / `ess Enter.'`). So the statement is
# assembled column-wise first, and every pattern then runs on one bounded
# operand string. Columns 73-80 (sequence numbers) are never read.
#
# SCOPE AND NON-SCOPE:
#   - Reads the PRISM code stream (`*` and `.*` comment lines already blanked),
#     never the raw file, so a commented-out field produces no fact.
#   - Same-file only. A `COPY`ed member carries its own fields when scanned.
#   - No assembly: conditional assembly (AIF/AGO) is not evaluated, and the
#     symbolic-map byte layout (the L/F/A/I/O suffixed items) is not generated;
#     that is a consumer's derivation from these rows.
# ==============================================================================
import re
from typing import Any, Optional

# Column 72 (index 71) is the continuation indicator; a continued line resumes
# in column 16 (index 15). Columns 73-80 are sequence numbers and never read.
_CONTINUATION_COLUMN = 71
_RESUME_COLUMN = 15
# A statement longer than this many continuation lines is malformed; stop there
# rather than walk the rest of the file as one statement.
_MAX_CONTINUATIONS = 200

_NAME = re.compile(r"[A-Za-z@#$][A-Za-z0-9@#$_]{0,62}")
_OPERATION = re.compile(r"[ \t]+([A-Za-z]{1,8})(?![A-Za-z0-9@#$_])")
_MACROS = {"DFHMSD": "mapset", "DFHMDI": "map", "DFHMDF": "field"}
_KEYWORD = re.compile(r"([A-Za-z]{1,10})=(.*)", re.S)
_POS_PAIR = re.compile(r"\(\s*(\d{1,4})\s*,\s*(\d{1,4})\s*\)")
_INTEGER = re.compile(r"\d{1,6}")
# Operands with a column of their own on a DFHMDF.
_FIELD_COLUMNS = ("POS", "LENGTH", "ATTRB", "PICIN", "PICOUT", "INITIAL", "OCCURS")


def _is_continued(line: str) -> bool:
    return len(line) > _CONTINUATION_COLUMN and line[_CONTINUATION_COLUMN] not in " \t"


def _scan_operands(segment: str, text: list[str], state: dict[str, Any]) -> bool:
    """Append `segment`'s operand characters to `text`. Returns True when the
    operand field ended on this line at a blank outside quotes (the rest is
    remarks). `state["quote"]` carries an open literal across lines."""
    i = 0
    while i < len(segment):
        ch = segment[i]
        if state["quote"]:
            text.append(ch)
            if ch == "'":
                if i + 1 < len(segment) and segment[i + 1] == "'":
                    text.append("'")
                    i += 2
                    continue
                state["quote"] = False
        elif ch in " \t":
            return True
        else:
            text.append(ch)
            if ch == "'":
                state["quote"] = True
        i += 1
    return False


def _statements(code_stream: str) -> list[tuple[int, Optional[str], str, str]]:
    """(line, name, OPERATION, operands) for every DFHMSD/DFHMDI/DFHMDF statement.

    `operands` is the statement's operand field joined across its continuation
    lines, remarks dropped. Every other statement (TITLE, PRINT, COPY, END,
    conditional assembly) is consumed with its continuations and skipped."""
    lines = code_stream.split("\n")
    out: list[tuple[int, Optional[str], str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        start = i
        i += 1
        body = line[:_CONTINUATION_COLUMN]
        if not body.strip():
            continue
        name_match = _NAME.match(body)
        name = name_match.group(0) if name_match else None
        after_name = name_match.end() if name_match else 0
        # Column 1 holding something that is not a name (a sequence symbol, a
        # macro-parameter reference) is not a BMS macro statement.
        column_one_ok = name_match is not None or body[0] in " \t"
        op_match = _OPERATION.match(body, after_name) if column_one_ok else None
        operation = op_match.group(1).upper() if op_match else ""
        continued = _is_continued(line)
        if op_match is None or operation not in _MACROS:
            # Skip this statement's continuation lines too.
            hops = 0
            while continued and i < len(lines) and hops < _MAX_CONTINUATIONS:
                continued = _is_continued(lines[i])
                i += 1
                hops += 1
            continue
        segment = body[op_match.end() :].lstrip(" \t")
        text: list[str] = []
        state: dict[str, Any] = {"quote": False}
        ended = _scan_operands(segment, text, state)
        hops = 0
        while continued and i < len(lines) and hops < _MAX_CONTINUATIONS:
            nxt = lines[i]
            i += 1
            hops += 1
            continued = _is_continued(nxt)
            # Operands carry on only inside an open literal or after a trailing
            # comma; otherwise a continuation line is more remarks.
            if state["quote"]:
                ended = _scan_operands(nxt[_RESUME_COLUMN:_CONTINUATION_COLUMN], text, state)
            elif not ended or (text and text[-1] == ","):
                ended = _scan_operands(nxt[_RESUME_COLUMN:_CONTINUATION_COLUMN].lstrip(" \t"), text, state)
        out.append((start + 1, name, operation, "".join(text)))
    return out


def _split_operands(operands: str) -> list[str]:
    """Top-level comma split, outside quotes and parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote = False
    for ch in operands:
        if quote:
            current.append(ch)
            if ch == "'":
                quote = False  # a doubled '' re-opens on the next character
            continue
        if ch == "'":
            quote = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current))
    return [p for p in parts if p]


def _unquote(value: str) -> str:
    """A BMS literal's content: outer quotes dropped, `''` -> `'`, `&&` -> `&`."""
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        value = value[1:-1]
    return value.replace("''", "'").replace("&&", "&")


def _unparen(value: str) -> str:
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    return value.replace(" ", "").upper()


def _as_int(value: str) -> Optional[int]:
    value = value.strip()
    return int(value) if _INTEGER.fullmatch(value) else None


def _statement_fields(kind: str, operands: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "pos_line": None,
        "pos_column": None,
        "length": None,
        "attrb": None,
        "picin": None,
        "picout": None,
        "initial": None,
        "occurs": None,
    }
    rest: list[str] = []
    for operand in _split_operands(operands):
        m = _KEYWORD.fullmatch(operand)
        key = m.group(1).upper() if m else None
        if kind != "field" or key not in _FIELD_COLUMNS or m is None:
            rest.append(operand)
            continue
        value = m.group(2)
        if key == "POS":
            pair = _POS_PAIR.fullmatch(value.strip())
            if pair:
                fields["pos_line"], fields["pos_column"] = int(pair.group(1)), int(pair.group(2))
            else:
                rest.append(operand)  # POS=n, a buffer offset
        elif key == "LENGTH":
            fields["length"] = _as_int(value)
        elif key == "OCCURS":
            fields["occurs"] = _as_int(value)
        elif key == "ATTRB":
            fields["attrb"] = _unparen(value)
        else:  # PICIN / PICOUT / INITIAL
            fields[key.lower()] = _unquote(value)
    fields["attributes"] = ",".join(rest) or None
    return fields


def bms_screen_fields(code_stream: str) -> list[dict[str, Any]]:
    """The mapset -> map -> field tree of one BMS map source, flat and in source order.

    The closing `DFHMSD TYPE=FINAL` is a bracket, not a mapset, and yields no row.
    A map outside any mapset, or a field before any map, is a root/partial tree
    rather than an error: the rows still describe what the file declares."""
    rows: list[dict[str, Any]] = []
    mapset_ordinal: Optional[int] = None
    map_ordinal: Optional[int] = None
    for line, name, operation, operands in _statements(code_stream):
        kind = _MACROS[operation]
        if kind == "mapset" and re.search(r"(?<![A-Za-z0-9])TYPE=FINAL(?![A-Za-z0-9])", operands, re.I):
            mapset_ordinal = map_ordinal = None
            continue
        ordinal = len(rows)
        if kind == "mapset":
            parent = None
            mapset_ordinal, map_ordinal = ordinal, None
        elif kind == "map":
            parent = mapset_ordinal
            map_ordinal = ordinal
        else:
            parent = map_ordinal if map_ordinal is not None else mapset_ordinal
        rows.append(
            {
                "kind": kind,
                "ordinal": ordinal,
                "parent_ordinal": parent,
                "name": name,
                **_statement_fields(kind, operands),
                "line": line,
            }
        )
    return rows
