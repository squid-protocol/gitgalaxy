# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Fortran call sites for `calls_out_to` (#5638).

Fortran spells an array element and a function reference the same way, `NAME(...)`, so a
regex cannot tell them apart. A statement scan can: a `NAME(` is a function reference unless
the unit declares NAME an array (`REAL W(3,3)`, `DIMENSION`, `COMMON`, `DIMENSION(n) ::`), it
heads an assignment (`A(I) = ...` is an element store, `F(X) = ...` a statement-function
definition, never a call), it follows `%` (a component), or it is a statement keyword or an
intrinsic. `CALL NAME` records with or without an argument list. A name defined nowhere in
the scanned tree is dropped later by core/call_resolver.py (an external or an array declared
in another file), so this only has to exclude what the unit itself shows is not a call.
"""

import re

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_NAME_PAREN = re.compile(r"(?<![\w%])(" + _NAME + r")[ \t]*\(")
_CALL = re.compile(r"(?i)^call[ \t]+(" + _NAME + r")")
_LABEL = re.compile(r"^\d+[ \t]+")
# `IF (cond) stmt`, `WHERE (mask) stmt`, `FORALL (...) stmt`: the guarded statement is scanned too
_GUARD = re.compile(r"(?i)^(?:if|where|forall)[ \t]*\(")
# fixed form: a non-blank, non-zero character in column 6 continues the previous line. Only a punctuation
# mark or a lone digit counts: a free-form line indented five spaces starts with a letter or a label
_FIXED_CONTINUATION = re.compile(r"\n[ \t]{5}(?:[^\w\s]|[1-9](?=[ \t]))")
_FREE_CONTINUATION = re.compile(r"&[ \t]*\n[ \t]*&?")
_DECL = re.compile(
    r"(?i)^(?:integer|real|double[ \t]+precision|complex|logical|character|byte|type(?=[ \t]*\()|class(?=[ \t]*\()|"
    r"dimension|common|allocatable|pointer|target|save|equivalence|data|parameter|external|intrinsic|"
    r"implicit|use|format|namelist|optional|intent|volatile|value|public|private|protected|"
    r"(?:pure|elemental|recursive|impure|module)[ \t]+(?:function|subroutine)|function|subroutine|"
    r"entry|program|module|interface|end|contains)(?![A-Za-z0-9_])"
)
_TYPE_HEAD = re.compile(
    r"(?i)(?:dimension|common|equivalence|double[ \t]+precision|[a-z]+(?:[ \t]*\*[ \t]*(?:\d+|\([^)]*\)))?"
    r"(?:[ \t]*\([^)]*\))?)[ \t]*"
)
_DIMENSION_ATTR = re.compile(r"(?i)\b(?:dimension|allocatable)\b")
_KEYWORD_WORDS = (
    "if elseif while do select case where forall read write print open close inquire rewind backspace "
    "endfile return stop pause allocate deallocate nullify goto assign associate block format wait flush "
    "type class selectcase kind len"
)
_KEYWORDS = frozenset(_KEYWORD_WORDS.split())


def _statements(text: str) -> list[str]:
    text = _FIXED_CONTINUATION.sub(" ", text)
    text = _FREE_CONTINUATION.sub(" ", text)
    out: list[str] = []
    for line in text.split("\n"):
        out.extend(part.strip() for part in line.split(";") if part.strip())
    return out


def _balanced_end(s: str, open_idx: int) -> int:
    """Index just past the `)` matching the `(` at open_idx, or -1."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _split_top(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _declared_arrays(stmt: str) -> set[str]:
    """Names this declaration statement makes arrays."""
    head, sep, entities = stmt.partition("::")
    all_arrays = False
    if sep:
        all_arrays = bool(_DIMENSION_ATTR.search(head))
    else:
        m = _TYPE_HEAD.match(stmt)
        entities = stmt[m.end() :] if m else stmt
        # `COMMON /blk/ A(10), B`: drop each block name
        entities = re.sub(r"/[^/]*/", " ", entities)
        all_arrays = bool(re.match(r"(?i)dimension\b", stmt))
    names: set[str] = set()
    for part in _split_top(entities):
        m2 = re.match(r"[ \t]*(" + _NAME + r")[ \t]*(\()?", part)
        if m2 and (m2.group(2) or all_arrays):
            names.add(m2.group(1).casefold())
    return names


def _heads_assignment(stmt: str) -> bool:
    """`NAME(...)... = value` at statement level: an element store or a statement-function definition."""
    m = _NAME_PAREN.match(stmt)
    if not m:
        return False
    i = m.end() - 1
    while i != -1 and i < len(stmt) and stmt[i] == "(":
        i = _balanced_end(stmt, i)
        while 0 <= i < len(stmt) and stmt[i] in " \t":
            i += 1
    if i == -1:
        return False
    while i < len(stmt) and stmt[i] == "%":
        m3 = re.match(r"%[ \t]*" + _NAME + r"[ \t]*", stmt[i:])
        if not m3:
            return False
        i += m3.end()
        while i < len(stmt) and stmt[i] == "(":
            i = _balanced_end(stmt, i)
            if i == -1:
                return False
            while i < len(stmt) and stmt[i] in " \t":
                i += 1
    return stmt[i : i + 1] == "=" and stmt[i + 1 : i + 2] != "="


def fortran_call_names(block: str, ignore: frozenset[str]) -> list[str]:
    """Callee names of one program unit, in source order, with duplicates (the caller dedups)."""
    statements = [_LABEL.sub("", s) for s in _statements(block)]
    arrays: set[str] = set()
    for s in statements:
        if _DECL.match(s):
            arrays |= _declared_arrays(s)
    calls: list[str] = []
    for stmt in statements:
        if _DECL.match(stmt):
            continue
        while True:
            g = _GUARD.match(stmt)
            if not g:
                break
            end = _balanced_end(stmt, g.end() - 1)
            if end == -1:
                break
            # the condition is scanned like any expression; the guarded statement is what remains
            calls.extend(_references(stmt[g.end() : end - 1], arrays, ignore))
            rest = stmt[end:].strip()
            if not rest or re.match(r"(?i)then\b", rest):
                stmt = ""
                break
            stmt = rest
        if not stmt:
            continue
        m = _CALL.match(stmt)
        if m:
            calls.append(m.group(1))
            stmt = stmt[m.end() :]
        elif _heads_assignment(stmt):
            stmt = stmt[stmt.index("(") :]
            # the subscripts and the right-hand side still hold references
        calls.extend(_references(stmt, arrays, ignore))
    return calls


def _references(expr: str, arrays: set[str], ignore: frozenset[str]) -> list[str]:
    out = []
    for m in _NAME_PAREN.finditer(expr):
        key = m.group(1).casefold()
        if key in arrays or key in _KEYWORDS or key in ignore:
            continue
        out.append(m.group(1))
    return out
