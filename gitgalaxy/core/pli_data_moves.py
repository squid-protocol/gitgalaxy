# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #3491 part 3: PL/I data moves -- the assignment statement as data_moves rows.
#
# The same row shape as core/data_moves.py (COBOL), verb ASSIGN:
#
#   `t1, t2 = expr;`   one row per data item in expr, for each target (COBOL's
#                      COMPUTE rule), items in order of appearance, each once;
#   `t = 'lit';`       an expression with no data item: one `literal` row when it
#                      is a single (signed) literal, one `function` row (the name)
#                      when it is a single built-in call (`X = DATE();`), else none;
#   `A = B, BY NAME;`  structure to structure by matching names: `corresponding`;
#   `X += e;`          compound assignment (Enterprise PL/I): X is a source too.
#
# A source is a data name as written with its qualification (`A.B.C`, `P->X` reads
# as X); an array subscript is dropped and is no source (COBOL's rule). A built-in
# function (SUBSTR, LENGTH, INDEX, ...) is no source, but every data item in its
# arguments is. DFHRESP(x) / DFHVALUE(x) are CICS constants (`cics_constant`). A
# pseudo-variable target -- `SUBSTR(A, 1, 3) = ...`, `UNSPEC(A) = ...` -- assigns A
# in part: target A with `target_refmod`. A source is never marked refmod: an
# argument of SUBSTR(...) is an item like any other.
#
# PL/I reserves no words, so a statement beginning IF / DO / CALL / ... is only an
# assignment when `=` follows that first word directly (`IF = 1;` is legal). A
# statement is scanned after its labels and after THEN / ELSE / OTHERWISE / WHEN(...) /
# an ON condition (an on-unit's single statement is a data move when it fires);
# `DO I = 1 TO N` is loop control, not a data move; a `%` preprocessor statement
# (`%X = ...;`) runs at compile time and moves no data. Sequence fields (columns 73-80)
# are blanked by shape (core/pli_calls.py).
# ==============================================================================
import bisect
import re
from typing import Any, Optional

from gitgalaxy.core.pli_calls import blank_sequence_fields

_TOKEN = re.compile(
    r"(?P<string>'(?:[^']|'')*'(?:B[14]?|X|GX|G)?(?![\w@#$]))"
    r"|(?P<number>[0-9]+(?:\.[0-9]*)?(?:E[+-]?[0-9]+)?[BI]?(?![\w@#$]))"
    r"|(?P<word>[\w@#$]+)"
    r"|(?P<arrow>->)"
    r"|(?P<op><=|>=|\^=|¬=|<>|\|\||\*\*|[-+*/|&=<>^¬(),.;:%])",
    re.I,
)
_KEYWORDS = frozenset(
    (
        "IF",
        "DO",
        "DCL",
        "DECLARE",
        "CALL",
        "RETURN",
        "GO",
        "GOTO",
        "END",
        "SELECT",
        "WHEN",
        "OTHERWISE",
        "ON",
        "REVERT",
        "SIGNAL",
        "OPEN",
        "CLOSE",
        "READ",
        "WRITE",
        "REWRITE",
        "DELETE",
        "LOCATE",
        "GET",
        "PUT",
        "ALLOCATE",
        "ALLOC",
        "FREE",
        "LEAVE",
        "ITERATE",
        "STOP",
        "EXIT",
        "EXEC",
        "DISPLAY",
        "FETCH",
        "RELEASE",
        "WAIT",
        "FORMAT",
        "PROC",
        "PROCEDURE",
        "BEGIN",
        "ENTRY",
        "DEFINE",
        "PACKAGE",
        "ELSE",
        "THEN",
    )
)
# The PL/I built-in functions and pseudo-variables a data move can name (Language
# Reference, "Built-in functions, pseudovariables, and subroutines"), the common set.
BUILTINS = frozenset(
    (
        "ABS",
        "ACOS",
        "ADD",
        "ADDR",
        "ADDRDATA",
        "ALL",
        "ALLOCATION",
        "ALLOCN",
        "ANY",
        "ASIN",
        "ATAN",
        "ATAND",
        "ATANH",
        "BIN",
        "BINARY",
        "BIT",
        "BOOL",
        "CEIL",
        "CENTER",
        "CENTRE",
        "CHAR",
        "CHARACTER",
        "COLLATE",
        "COMPLEX",
        "COPY",
        "COS",
        "COSD",
        "COSH",
        "COUNT",
        "CURRENTSTORAGE",
        "CSTG",
        "DATAFIELD",
        "DATE",
        "DATETIME",
        "DAYS",
        "DAYSTODATE",
        "DEC",
        "DECIMAL",
        "DIM",
        "DIVIDE",
        "EMPTY",
        "ERF",
        "EXP",
        "FIXED",
        "FLOAT",
        "FLOOR",
        "HBOUND",
        "HEX",
        "HIGH",
        "IMAG",
        "INDEX",
        "LBOUND",
        "LEFT",
        "LENGTH",
        "LINENO",
        "LOG",
        "LOG10",
        "LOG2",
        "LOW",
        "LOWERCASE",
        "LOWER2",
        "MAX",
        "MIN",
        "MOD",
        "MULTIPLY",
        "NULL",
        "OFFSET",
        "ONCHAR",
        "ONCODE",
        "ONCOUNT",
        "ONFILE",
        "ONKEY",
        "ONLOC",
        "ONSOURCE",
        "PLIRETV",
        "POINTER",
        "PTR",
        "POLY",
        "PRECISION",
        "PREC",
        "PROD",
        "REAL",
        "REM",
        "REPEAT",
        "REVERSE",
        "RIGHT",
        "ROUND",
        "SEARCH",
        "SIGN",
        "SIN",
        "SIND",
        "SINH",
        "SIZE",
        "SQRT",
        "STATUS",
        "STORAGE",
        "STG",
        "STRING",
        "SUBSTR",
        "SUBTRACT",
        "SUM",
        "SYSNULL",
        "TALLY",
        "TAN",
        "TAND",
        "TANH",
        "TIME",
        "TRANSLATE",
        "TRIM",
        "TRUNC",
        "UNSPEC",
        "UPPERCASE",
        "VALID",
        "VERIFY",
        "WHIGH",
        "WLOW",
    )
)
_PSEUDO_TARGETS = frozenset({"SUBSTR", "UNSPEC", "STRING", "REAL", "IMAG", "ONCHAR", "ONSOURCE", "ENTRYADDR"})
_CICS_CONSTANTS = frozenset({"DFHRESP", "DFHVALUE"})
_STATEMENT_LIMIT = 4000  # tokens one statement may run over


def _tokens(text: str) -> list[tuple[str, str, int]]:
    """(kind, TEXT, offset): comments already gone from the code stream, words upper-cased."""
    out = []
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup or "op"
        out.append((kind, m.group(0) if kind == "string" else m.group(0).upper(), m.start()))
    return out


def _group_end(toks: list, i: int) -> int:
    """Index just past the `)` matching the `(` at toks[i]."""
    depth = 0
    for j in range(i, len(toks)):
        if toks[j][1] == "(":
            depth += 1
        elif toks[j][1] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(toks)


def _reference(toks: list, i: int) -> tuple[Optional[str], int]:
    """A data reference at toks[i]: `A`, `A.B(I).C`, `P->X` (qualified name without
    subscripts), and the index after it; (None, i) when toks[i] is no word."""
    if i >= len(toks) or toks[i][0] != "word":
        return None, i
    parts = [toks[i][1]]
    j = i + 1
    while j < len(toks):
        if toks[j][1] == "(":
            j = _group_end(toks, j)
        elif toks[j][1] == "." and j + 1 < len(toks) and toks[j + 1][0] == "word":
            parts.append(toks[j + 1][1])
            j += 2
        elif toks[j][0] == "arrow" and j + 1 < len(toks) and toks[j + 1][0] == "word":
            parts = [toks[j + 1][1]]  # a locator qualifier: the based item is the reference
            j += 2
        else:
            break
    return ".".join(parts), j


def _sources(toks: list) -> list[tuple[str, str]]:
    """(text, kind) of every data item of an expression, in order, each once."""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(toks):
        kind, text, _ = toks[i]
        if kind == "word":
            nxt = toks[i + 1][1] if i + 1 < len(toks) else ""
            if nxt == "(" and text in _CICS_CONSTANTS:
                end = _group_end(toks, i + 1)
                item = (text + "(" + "".join(t[1] for t in toks[i + 2 : end - 1]) + ")", "cics_constant")
                i = end
            elif nxt == "(" and text in BUILTINS:
                i += 1  # the built-in is no source; its arguments are scanned next
                continue
            else:
                name, i = _reference(toks, i)
                item = (name or text, "item")
            if item not in out:
                out.append(item)
            continue
        i += 1
    return out


def _single_value(toks: list) -> Optional[tuple[str, str]]:
    """An item-free expression's one row: a (signed) literal, or a lone built-in call."""
    body = toks[1:] if toks and toks[0][1] in ("-", "+") else toks
    if len(body) == 1 and body[0][0] in ("string", "number"):
        return "".join(t[1] for t in toks), "literal"
    lone_call = len(body) == 1 or (len(body) > 1 and body[1][1] == "(" and _group_end(body, 1) == len(body))
    if body and body[0][0] == "word" and body[0][1] in BUILTINS and lone_call:
        return body[0][1], "function"
    return None


def _clause_start(stmt: list) -> int:
    """Index where the statement's own action begins: after labels and after an
    IF ... THEN / ELSE / OTHERWISE / WHEN(...) prefix."""
    i = 0
    while True:
        # Labels (`LABEL:`), and the sequence fields a removed comment left behind --
        # no statement starts with a number -- in any order.
        while i < len(stmt) and (
            stmt[i][0] == "number" or (i + 1 < len(stmt) and stmt[i][0] == "word" and stmt[i + 1][1] == ":")
        ):
            i += 1 if stmt[i][0] == "number" else 2
        word = stmt[i][1] if i < len(stmt) else ""
        after = stmt[i + 1][1] if i + 1 < len(stmt) else ""
        if word == "IF" and after != "=":
            j, depth = i + 1, 0
            while j < len(stmt) and not (depth == 0 and stmt[j][1] == "THEN"):
                depth += {"(": 1, ")": -1}.get(stmt[j][1], 0)
                j += 1
            i = j + 1
        elif word in ("ELSE", "OTHERWISE") and after != "=":
            i += 1
        elif word == "WHEN" and after == "(":
            i = _group_end(stmt, i + 1)
        elif word == "ON" and after != "=" and i + 1 < len(stmt) and stmt[i + 1][0] == "word":
            # An ON unit's single statement (`ON ENDFILE(F) EOF = '1'B;`) runs when the
            # condition fires: skip the condition, its reference and SNAP.
            i += 2
            if i < len(stmt) and stmt[i][1] == "(":
                i = _group_end(stmt, i)
            if i < len(stmt) and stmt[i][1] == "SNAP":
                i += 1
        else:
            return i


def pli_data_moves(code_stream: str) -> list[dict[str, Any]]:
    """Every PL/I assignment's data-move rows (see the header)."""
    if "=" not in code_stream:
        return []
    text = blank_sequence_fields(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    toks = _tokens(text)
    rows: list[dict[str, Any]] = []
    stmt: list = []
    for tok in [*toks, ("op", ";", len(text))]:
        if tok[1] != ";" and len(stmt) < _STATEMENT_LIMIT:
            stmt.append(tok)
            continue
        rows.extend(_assignment_rows(stmt[_clause_start(stmt) :], newlines))
        stmt = []
    return rows


def _assignment_rows(stmt: list, newlines: list[int]) -> list[dict[str, Any]]:
    if not stmt or stmt[0][0] != "word":
        return []
    if stmt[0][1] in _KEYWORDS and not (len(stmt) > 1 and stmt[1][1] == "="):
        return []
    # The targets: references separated by commas, up to the first `=` at depth 0.
    targets: list[tuple[str, bool]] = []
    i = 0
    while True:
        word = stmt[i][1] if i < len(stmt) else ""
        if word in _PSEUDO_TARGETS and i + 1 < len(stmt) and stmt[i + 1][1] == "(":
            name, _ = _reference(stmt, i + 2)
            if name is None:
                return []
            targets.append((name, True))
            i = _group_end(stmt, i + 1)
        else:
            name, i = _reference(stmt, i)
            if name is None:
                return []
            targets.append((name, False))
        if i < len(stmt) and stmt[i][1] == ",":
            i += 1
            continue
        break
    compound = i + 1 < len(stmt) and stmt[i][1] in ("+", "-", "*", "/", "|", "||", "**") and stmt[i + 1][1] == "="
    if compound:
        i += 1
    if i >= len(stmt) or stmt[i][1] != "=":
        return []
    expr = stmt[i + 1 :]
    by_name = False
    for j in range(len(expr) - 2):
        if expr[j][1] == "," and expr[j + 1][1] == "BY" and expr[j + 2][1] == "NAME":
            expr, by_name = expr[:j], True
            break
    line = bisect.bisect_left(newlines, stmt[0][2]) + 1
    sources = _sources(expr)
    rows = []
    for target, partial in targets:
        srcs = ([(target, "item")] if compound else []) + [s for s in sources if not (compound and s[0] == target)]
        if not srcs:
            single = _single_value(expr)
            srcs = [single] if single else []
        for src, kind in srcs:
            rows.append({"verb": "ASSIGN", "source": src, "source_kind": kind, "target": target,
                         "corresponding": by_name, "source_refmod": False, "target_refmod": partial,
                         "line": line})  # fmt: skip
    return rows
