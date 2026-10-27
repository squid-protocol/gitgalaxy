# ==============================================================================
# GitGalaxy Core: relation conditions -- which COBOL comparisons are alphanumeric (#4035)
#
# PURPOSE:
# COBOL compares two alphanumeric operands by the program's collating sequence
# (EBCDIC on the mainframe: lower case before upper, letters before digits) and
# pads the shorter operand with spaces. A Java port that writes String.compareTo
# disagrees on exactly those inputs (#3986 added util/CobolCompare). The porting
# agent still had to find the alphanumeric comparisons itself; this reads them off.
# One row per relation condition (relation_facts):
#
#   line         where the condition starts
#   context      IF | EVALUATE WHEN | PERFORM UNTIL | SEARCH WHEN
#   left, right  the two operands as written
#   op           = | <> | > | >= | < | <=   (NOT folded in: NOT > is <=)
#   left_class, right_class
#                alphanumeric | numeric | edited | group | figurative | zero | function | unknown
#   kind         alphanumeric (compared by collating sequence) | numeric | unknown
#   abbreviated  the subject and/or operator was carried forward (`A > 'X' AND < 'Y'`)
#   ordering     the operator orders (anything but = and <>), so the collating sequence decides it
#   java         the exact CobolCompare call for an alphanumeric row
#
# Operand classes come from the data items of the program and the copybooks it is
# given (PIC X / A: alphanumeric; PIC 9 or a numeric USAGE: numeric; no PIC with
# subordinate items: group). A name that cannot be resolved (or is defined twice
# with different classes) is `unknown`, never guessed numeric.
#
# Also here: condition_ranges (a level-88 `VALUE 'A' THRU 'Z'` over a non-numeric
# item depends on the collating sequence too) and collating_sequence (the
# PROGRAM COLLATING SEQUENCE / ALPHABET clauses a program declares).
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per program, from its source text; EXEC blocks are skipped.
#   - Not comparisons, so skipped: class conditions (IS [NOT] NUMERIC / ALPHABETIC...,
#     a SPECIAL-NAMES CLASS name), sign conditions (POSITIVE / NEGATIVE / ZERO), and a
#     bare condition-name (a level-88).
#   - COPY ... REPLACING is not applied: a copybook's own names are used as written.
#   - Bounded: linear scans, no nested quantifiers; a statement is capped.
# ==============================================================================
import bisect
import copy
import hashlib
import re
from typing import Any

from gitgalaxy.core.data_moves import (
    _END_WORDS,
    _FIGURATIVE,
    _STATEMENT_TOKENS,
    _TOKEN,
    _VERBS,
    _WORD,
    _is_literal,
    _procedure_text,
)
from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_PROCEDURE = re.compile(r"(?<![A-Z0-9-])PROCEDURE[ \t\n]{1,200}DIVISION(?![A-Z0-9-])", re.I)
_LEVEL_NAME = re.compile(rf"\s{{0,200}}(\d{{1,2}})(?:\s{{1,200}}({_WORD}))?(?=\s|$)", re.I)
_PIC = re.compile(r"(?<![A-Z0-9-])PIC(?:TURE)?(?:\s{1,200}IS)?\s{1,200}(\S{1,200})", re.I)
_NUMERIC_USAGE = re.compile(
    r"(?<![A-Z0-9-])(?:COMP(?:UTATIONAL)?(?:-[0-5X])?|BINARY|PACKED-DECIMAL|INDEX|POINTER)(?![A-Z0-9-])", re.I
)
_PIC_COUNT = re.compile(r"\([0-9]{1,6}\)")
_VALUE = re.compile(r"(?<![A-Z0-9-])VALUES?(?:\s{1,200}(?:IS|ARE))?\s{1,200}", re.I)
_QUALIFIERS = frozenset({"OF", "IN"})
_ALNUM_FUNCTIONS = frozenset({"UPPER-CASE", "LOWER-CASE", "REVERSE", "TRIM", "CONCATENATE", "SUBSTITUTE", "CHAR"})
_NUMERIC_FUNCTIONS = frozenset(
    {"LENGTH", "NUMVAL", "NUMVAL-C", "ORD", "INTEGER", "MOD", "ABS", "INTEGER-OF-DATE", "CURRENT-DATE-INT"}
)
_ARITH = frozenset({"+", "-", "*", "/", "**"})
_CLASS_WORDS = frozenset(
    {"NUMERIC", "ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER", "POSITIVE", "NEGATIVE", "ZERO"}
)
_JAVA = {"=": "eq", ">": "gt", ">=": "ge", "<": "lt", "<=": "le"}
_NOT_OP = {"=": "<>", "<>": "=", ">": "<=", "<=": ">", "<": ">=", ">=": "<"}
_ITEM_LIMIT = 100000
_COND_TOKENS = _STATEMENT_TOKENS


# ---- data items ---------------------------------------------------------------------------


_ENTRY_MARK = re.compile("['\"]" + r"|\.(?=[ \t\r\n]|\Z)")


def _entries(text: str) -> list[tuple[str, int]]:
    """The period-terminated entries of `text` (quote-aware, linear): (entry text, start offset)."""
    out: list[tuple[str, int]] = []
    start, quote = 0, ""
    for m in _ENTRY_MARK.finditer(text):
        ch = m.group(0)
        if quote:
            if ch == quote:
                quote = ""
        elif ch != ".":
            quote = ch
        else:
            out.append((text[start : m.start()], start))
            start = m.end()
            if len(out) > _ITEM_LIMIT:
                break
    return out


def _pic_class(pic: str, usage_numeric: bool) -> str:
    body = _PIC_COUNT.sub("", pic.upper()).rstrip(".")
    if not body:
        return "unknown"
    if set(body) <= set("9SVP"):
        return "numeric"
    if "N" in body:
        return "unknown"  # national: its own collation
    if "X" in body or "A" in body:
        return "alphanumeric"
    if usage_numeric:
        return "numeric"
    return "edited"


_ITEM_CACHE: dict[bytes, list[dict[str, Any]]] = {}
_ITEM_CACHE_MAX = 2048


def _data_items(texts: list[str]) -> list[dict[str, Any]]:
    """Level-numbered data items of the data divisions in `texts`: name, level, parent, class, 88 values.
    Memoised on the texts' digest (#5142): the porting tickets read each program's items twice per run and the
    Java matrix generates the same programs once per config, so the parse is the bulk of a ticket pass. A caller
    gets its own copy, so mutating the result never reaches the cache."""
    h = hashlib.blake2b(digest_size=16)
    for t in texts:
        h.update(len(t).to_bytes(8, "little"))
        h.update(t.encode("utf-8", "surrogatepass"))
    key = h.digest()
    items = _ITEM_CACHE.get(key)
    if items is None:
        if len(_ITEM_CACHE) >= _ITEM_CACHE_MAX:
            _ITEM_CACHE.clear()
        items = _ITEM_CACHE[key] = _parse_data_items(texts)
    return copy.deepcopy(items)


def _parse_data_items(texts: list[str]) -> list[dict[str, Any]]:
    """The uncached parse behind `_data_items`."""
    items: list[dict[str, Any]] = []
    for raw in texts:
        text = _blank_sequence_fields(raw, "cobol")
        text = "\n".join("" if len(ln) > 6 and ln[6] in "*/Dd" else ln for ln in text.split("\n"))
        m = _PROCEDURE.search(text)
        if m:
            text = text[: m.start()]
        stack: list[dict[str, Any]] = []
        for entry, start in _entries(text):
            head = _LEVEL_NAME.match(entry)
            if not head:
                continue
            level = int(head.group(1))
            if not (1 <= level <= 49 or level in (66, 77, 88)):
                continue
            name = (head.group(2) or "FILLER").upper()
            rest = entry[head.end() :]
            if level == 88:
                parent = stack[-1] if stack else None
                v = _VALUE.search(rest)
                items.append({"level": 88, "name": name, "parent": parent["name"] if parent else None,
                              "values": _value_ranges(rest[v.end() :]) if v else [],
                              "line": text.count("\n", 0, start + head.start(1)) + 1, "cls": "condition"})  # fmt: skip
                continue
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            pic = _PIC.search(rest)
            numeric_usage = bool(_NUMERIC_USAGE.search(rest))
            item = {"level": level, "name": name, "parents": [s["name"] for s in stack],
                    "parent": stack[-1]["name"] if stack else None, "children": 0,
                    "cls": _pic_class(pic.group(1), numeric_usage) if pic else ("numeric" if numeric_usage else None)}  # fmt: skip
            if stack:
                stack[-1]["children"] += 1
            if level in (66, 77) or level == 1:
                stack = []
            stack.append(item)
            items.append(item)
    for it in items:
        if it["level"] != 88 and it["cls"] is None:
            it["cls"] = "group" if it["children"] else "unknown"
    return items


def _value_ranges(text: str) -> list[dict[str, str | None]]:
    """The VALUE list of a level-88: [{lo, hi}], hi None for a single value."""
    toks = [m.group(0) for m in _TOKEN.finditer(text)]
    out: list[dict[str, str | None]] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.upper() in ("THRU", "THROUGH") and out and i + 1 < len(toks):
            out[-1]["hi"] = toks[i + 1]
            i += 2
            continue
        if t.upper() not in ("IS", "ARE", "ALL") and t != ",":
            out.append({"lo": t, "hi": None})
        i += 1
    return out


class _Items:
    def __init__(self, items: list[dict[str, Any]]):
        self.by_name: dict[str, list[dict[str, Any]]] = {}
        for it in items:
            self.by_name.setdefault(it["name"], []).append(it)

    def klass(self, name: str, qualifiers: list[str]) -> str:
        found = self.by_name.get(name.upper(), [])
        if qualifiers:
            q = {x.upper() for x in qualifiers}
            narrowed = [it for it in found if q <= set(it.get("parents", []))]
            found = narrowed or found
        classes = {it["cls"] for it in found}
        return classes.pop() if len(classes) == 1 else "unknown"

    def is_condition_name(self, name: str) -> bool:
        return any(it["level"] == 88 for it in self.by_name.get(name.upper(), []))


# ---- operands -----------------------------------------------------------------------------


def _word(token: str) -> str:
    """The leading COBOL word of a token (a folded `NAME(1:2)` is `NAME`), "" for none."""
    m = re.match(_WORD, token, re.I)
    return m.group(0) if m else ""


def _operand(toks: list[tuple[str, int]], items: _Items) -> tuple[str, str]:
    """(operand as written, its class) for the tokens of one operand."""
    if not toks:
        return "", "unknown"
    written = " ".join(t for t, _ in toks)
    first = toks[0][0]
    up = first.upper()
    if any(t in _ARITH for t, _ in toks[1:]) or (len(toks) > 1 and toks[0][0] in ("+", "-")):
        return written, "numeric"
    if _is_literal(first):
        return written, "unknown" if up[0] == "N" else "alphanumeric"
    if re.fullmatch(r"[+-]?[0-9]*\.?[0-9]+", first):
        return written, "numeric"
    if up == "ALL" and len(toks) > 1:
        return written, "figurative"
    if up in _FIGURATIVE:
        return written, "zero" if up in ("ZERO", "ZEROS", "ZEROES") else "figurative"
    if up == "FUNCTION" and len(toks) > 1:
        fn = _word(toks[1][0]).upper()
        return written, "alphanumeric" if fn in _ALNUM_FUNCTIONS else (
            "numeric" if fn in _NUMERIC_FUNCTIONS else "function"
        )
    if up == "LENGTH" or (up in ("ADDRESS",) and len(toks) > 1):
        return written, "numeric" if up == "LENGTH" else "unknown"
    base = re.match(_WORD, first, re.I)
    if base:
        qualifiers = [t for k, (t, _) in enumerate(toks[1:], 1) if toks[k - 1][0].upper() in _QUALIFIERS]
        if ":" in first:  # a reference modification is an alphanumeric item
            return written, "alphanumeric"
        return written, items.klass(base.group(0), [_word(q) for q in qualifiers if _word(q)])
    return written, "unknown"


def _collapse(toks: list[tuple[str, int]], text: str) -> list[tuple[str, int]]:
    """A subscript or reference modification `(I)` / `(1:5)` after a name is part of the operand: fold the name
    and its parenthesis into one token spelled as in the source (whitespace collapsed)."""
    out: list[tuple[str, int]] = []
    i = 0
    while i < len(toks):
        t, s = toks[i]
        i += 1
        if re.fullmatch(_WORD, t, re.I) and i < len(toks) and toks[i][0] == "(" and toks[i][1] <= s + len(t) + 1:
            depth, j = 0, i
            while j < len(toks):
                depth += toks[j][0] == "("
                depth -= toks[j][0] == ")"
                j += 1
                if depth == 0:
                    break
            last = toks[j - 1]
            t = re.sub(r"\s+", "", text[s : last[1] + len(last[0])])
            i = j
        out.append((t, s))
    return out


# ---- conditions ---------------------------------------------------------------------------


def _split_logical(toks: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    """Cut a condition at AND / OR (not the OR of `GREATER THAN OR EQUAL TO`)."""
    segs: list[list[tuple[str, int]]] = [[]]
    for k, (t, s) in enumerate(toks):
        u = t.upper()
        if u in ("AND", "OR") and not (u == "OR" and k + 1 < len(toks) and toks[k + 1][0].upper() == "EQUAL"):
            segs.append([])
        else:
            segs[-1].append((t, s))
    return [g for g in segs if g]


def _find_operator(seg: list[tuple[str, int]]) -> tuple[int, int, str | None]:
    """(first index of the operator phrase, one past its last, normalized operator) in a segment."""
    n = len(seg)
    i = 0
    while i < n:
        u = seg[i][0].upper()
        j, neg, op = i, False, None
        if u == "IS":
            j += 1
        if j < n and seg[j][0].upper() == "NOT":
            neg, j = True, j + 1
        if j < n:
            w = seg[j][0].upper()
            if w in ("=", ">", "<"):
                op = w
                j += 1
                if j < n and seg[j][0] == "=" and w in (">", "<"):
                    op, j = w + "=", j + 1
                elif j < n and seg[j][0] == ">" and w == "<":
                    op, j = "<>", j + 1
            elif w == "EQUAL":
                op, j = "=", j + 1 + (j + 1 < n and seg[j + 1][0].upper() == "TO")
            elif w in ("GREATER", "LESS"):
                op, j = (">" if w == "GREATER" else "<"), j + 1 + (j + 1 < n and seg[j + 1][0].upper() == "THAN")
                if j + 1 < n and seg[j][0].upper() == "OR" and seg[j + 1][0].upper() == "EQUAL":
                    op += "="
                    j += 2 + (j + 2 < n and seg[j + 2][0].upper() == "TO")
        if op:
            return i, j, _NOT_OP[op] if neg else op
        i += 1
    return -1, -1, None


class _Rows:
    def __init__(self, text: str, items: _Items, newlines: list[int]):
        self.text, self.items, self.newlines = text, items, newlines
        self.rows: list[dict[str, Any]] = []

    def line(self, offset: int) -> int:
        return bisect.bisect_left(self.newlines, offset) + 1

    def add(self, context: str, start: int, left: list, op: str, right: list, abbreviated: bool) -> None:
        lw, lc = _operand(left, self.items)
        rw, rc = _operand(right, self.items)
        numericish = {"numeric", "edited", "zero"}
        if lc in numericish and rc in numericish:
            kind = "numeric"
        elif "unknown" in (lc, rc) or "function" in (lc, rc):
            kind = "unknown"
        else:
            kind = "alphanumeric"
        row: dict[str, Any] = {"line": self.line(start), "context": context, "left": lw, "op": op, "right": rw,
                               "left_class": lc, "right_class": rc, "kind": kind, "abbreviated": abbreviated,
                               "ordering": op not in ("=", "<>")}  # fmt: skip
        if kind == "alphanumeric":
            call = f"CobolCompare.{_JAVA[_NOT_OP[op] if op in ('<>',) else op]}({lw}, {rw})"
            row["java"] = f"!{call}" if op == "<>" else call
        self.rows.append(row)

    def condition(self, context: str, toks: list[tuple[str, int]]) -> None:
        toks = _collapse(toks, self.text)
        subject: list | None = None
        op: str | None = None
        for seg in _split_logical(toks):
            while seg and seg[0][0] == "(":
                seg = seg[1:]
            while seg and seg[-1][0] == ")":
                seg = seg[:-1]
            if not seg:
                continue
            a, b, found = _find_operator(seg)
            if found is None:
                words = [t.upper() for t, _ in seg]
                if any(w in _CLASS_WORDS for w in words):
                    continue  # a class or sign condition
                if "IS" in words and len(seg) >= 2:
                    continue  # IS [NOT] <class-name>
                first = seg[1 if seg[0][0].upper() == "NOT" and len(seg) > 1 else 0][0]
                if subject is not None and op and (_is_literal(first) or first.upper() in _FIGURATIVE
                                                   or re.fullmatch(r"[+-]?[0-9]*\.?[0-9]+", first)
                                                   or (re.fullmatch(_WORD, first, re.I) and not self.items.is_condition_name(first)
                                                       and self.items.klass(first, []) != "unknown")):  # fmt: skip
                    negated = seg[0][0].upper() == "NOT"  # `OR NOT 'Z'` repeats the operator, negated
                    self.add(context, seg[0][1], subject, _NOT_OP[op] if negated else op, seg[negated:], True)
                continue
            left, right = seg[:a], seg[b:]
            if not right:
                continue
            if not left:
                if subject is None:
                    continue
                self.add(context, seg[0][1], subject, found, right, True)
                op = found
                continue
            subject, op = left, found
            self.add(context, seg[0][1], left, found, right, False)


def _is_term(t: str) -> bool:
    return t == "." or t in _END_WORDS or t in _VERBS


def relation_facts(code_stream: str, copybooks: list[str] | None = None) -> list[dict[str, Any]]:
    """#4035: every relation condition of the program's procedure division, in source order. `copybooks`
    are the texts of the member files whose data items the program COPYs."""
    upper = code_stream.upper() if code_stream else ""
    if not upper or not any(w in upper for w in ("IF", "WHEN", "UNTIL")):
        return []
    text = _procedure_text(code_stream)
    items = _Items(_data_items([code_stream, *(copybooks or [])]))
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    toks = [(m.group(0), m.start()) for m in _TOKEN.finditer(text)]
    rows = _Rows(text, items, newlines)
    scopes: list[tuple[str, list]] = []  # open EVALUATE / SEARCH, with an EVALUATE's subjects
    i, n = 0, len(toks)
    while i < n:
        u = toks[i][0].upper()
        if u == "EXEC":
            while i < n and toks[i][0].upper() != "END-EXEC":
                i += 1
            i += 1
            continue
        if u == ".":
            scopes.clear()
        elif u in ("END-EVALUATE", "END-SEARCH") and scopes:
            scopes.pop()
        elif u == "IF" or (u == "UNTIL" and i > 0):
            context = "IF" if u == "IF" else "PERFORM UNTIL"
            j = i + 1
            while j < min(n, i + _COND_TOKENS) and not _is_term(toks[j][0].upper()) and toks[j][0].upper() != "AFTER":
                j += 1
            rows.condition(context, toks[i + 1 : j])
            i = j
            continue
        elif u == "SEARCH":
            scopes.append(("SEARCH", []))
        elif u == "EVALUATE":
            j = i + 1
            while j < min(n, i + _COND_TOKENS) and toks[j][0].upper() != "WHEN" and toks[j][0] != ".":
                j += 1
            subjects: list[list] = [[]]
            for t in toks[i + 1 : j]:
                if t[0].upper() == "ALSO":
                    subjects.append([])
                else:
                    subjects[-1].append(t)
            scopes.append(("EVALUATE", subjects))
            i = j
            continue
        elif u == "WHEN" and scopes:
            kind, subjects = scopes[-1]
            j = i + 1
            while (
                j < min(n, i + _COND_TOKENS)
                and toks[j][0].upper() != "WHEN"
                and not (_is_term(toks[j][0].upper()) and toks[j][0].upper() not in ("NEXT",))
            ):
                j += 1
            body = toks[i + 1 : j]
            if kind == "SEARCH":
                rows.condition("SEARCH WHEN", body)
            elif body and body[0][0].upper() != "OTHER":
                _evaluate_when(rows, subjects, body)
            i = j
            continue
        i += 1
    return rows.rows


def _evaluate_when(rows: _Rows, subjects: list[list], body: list[tuple[str, int]]) -> None:
    objects: list[list] = [[]]
    for t in body:
        if t[0].upper() == "ALSO":
            objects.append([])
        else:
            objects[-1].append(t)
    for k, obj in enumerate(objects):
        subj = subjects[k] if k < len(subjects) else []
        words = [t.upper() for t, _ in subj]
        if not obj or obj[0][0].upper() in ("ANY",) or not subj:
            continue
        if words in (["TRUE"], ["FALSE"]):
            if obj[0][0].upper() not in ("TRUE", "FALSE"):
                rows.condition("EVALUATE WHEN", obj)
            continue
        neg = obj[0][0].upper() == "NOT"
        obj = obj[1:] if neg else obj
        if obj and obj[0][0].upper() in ("TRUE", "FALSE"):
            continue
        thru = [x for x, (t, _) in enumerate(obj) if t.upper() in ("THRU", "THROUGH")]
        subj = _collapse(subj, rows.text)
        if thru:
            lo, hi = _collapse(obj[: thru[0]], rows.text), _collapse(obj[thru[0] + 1 :], rows.text)
            rows.add("EVALUATE WHEN", obj[0][1], subj, "<" if neg else ">=", lo, False)
            rows.add("EVALUATE WHEN", obj[0][1], subj, ">" if neg else "<=", hi, False)  # NOT lo..hi: < lo OR > hi
        else:
            rows.add(
                "EVALUATE WHEN", obj[0][1] if obj else 0, subj, "<>" if neg else "=", _collapse(obj, rows.text), False
            )


def condition_ranges(code_stream: str, copybooks: list[str] | None = None) -> list[dict[str, Any]]:
    """#4035: level-88 conditions whose VALUE has a THRU range over a non-numeric item: membership depends on
    the collating sequence ({name, parent, parent_class, ranges: [{lo, hi}], line})."""
    all_items = _data_items([code_stream or "", *(copybooks or [])])
    items = _Items(all_items)
    out: list[dict[str, Any]] = []
    for it in all_items:
        if it["level"] != 88 or not it["parent"] or not any(r["hi"] for r in it["values"]):
            continue
        pc = items.klass(it["parent"], [])
        if pc in ("numeric", "zero"):
            continue
        out.append({"name": it["name"], "parent": it["parent"], "parent_class": pc,
                    "ranges": [r for r in it["values"] if r["hi"]], "line": it["line"]})  # fmt: skip
    return out


# ---- collating sequence ------------------------------------------------------------------

_PROGRAM_SEQ = re.compile(
    r"(?<![A-Z0-9-])PROGRAM[ \t\n]{1,50}COLLATING[ \t\n]{1,50}SEQUENCE(?:[ \t\n]{1,50}IS)?[ \t\n]{1,50}(" + _WORD + ")",
    re.I,
)
_ALPHABET = re.compile(
    r"(?<![A-Z0-9-])ALPHABET[ \t\n]{1,50}(" + _WORD + r")[ \t\n]{1,50}IS[ \t\n]{1,50}"
    r"((?:(?![ \t\n]ALPHABET(?![A-Z0-9-]))[^.]){1,400})",
    re.I,
)
_NATIVE = frozenset({"NATIVE", "EBCDIC"})


def collating_sequence(code_stream: str) -> list[dict[str, Any]]:
    """#4035: the program's collating-sequence declarations: {line, clause, name, definition, custom}.
    `PROGRAM COLLATING SEQUENCE IS a` names the alphabet `a` for every alphanumeric comparison; an ALPHABET
    is `custom` unless it is NATIVE or EBCDIC (the mainframe's own order, which CobolCompare follows)."""
    if not code_stream or ("COLLATING" not in code_stream.upper() and "ALPHABET" not in code_stream.upper()):
        return []
    text = _blank_sequence_fields(code_stream, "cobol")
    text = "\n".join("" if len(ln) > 6 and ln[6] in "*/Dd" else ln for ln in text.split("\n"))
    alphabets = {m.group(1).upper(): (m.group(2).strip(), m.start()) for m in _ALPHABET.finditer(text)}
    out: list[dict[str, Any]] = []
    for m in _PROGRAM_SEQ.finditer(text):
        name = m.group(1).upper()
        definition = alphabets.get(name, (None, 0))[0]
        first = (definition or "").split()[0].upper() if definition else ""
        out.append({"line": text.count("\n", 0, m.start()) + 1, "clause": "PROGRAM COLLATING SEQUENCE", "name": name,
                    "definition": " ".join(definition.split()) if definition else None,
                    "custom": first not in _NATIVE})  # fmt: skip
    for name, (definition, pos) in alphabets.items():
        out.append({"line": text.count("\n", 0, pos) + 1, "clause": "ALPHABET", "name": name,
                    "definition": " ".join(definition.split()), "custom": definition.split()[0].upper() not in _NATIVE})  # fmt: skip
    return sorted(out, key=lambda r: (r["line"], r["clause"]))
