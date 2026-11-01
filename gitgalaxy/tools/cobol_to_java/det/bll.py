"""#5119 (register X56): OS/VS COBOL's BLL cells and SERVICE RELOAD, lowered onto the pointer lane (X47).

An OS/VS COBOL CICS program addresses storage outside WORKING-STORAGE through BLL (base locator for linkage) cells: the
first LINKAGE 01 (after DFHCOMMAREA, which must precede it) is a list of fullwords whose first, a FILLER, CICS sets to
address the list itself; each further cell addresses the next LINKAGE 01, one cell per 4096 bytes of it (CICS/MVS 2.1.2
Application Programmer's Reference, SC33-0512-1, "Base locator for linkage (BLL)", pp. 21-23). A command's SET(cell)
puts an address in a cell, and `SERVICE RELOAD record` makes the compiler address the record through its cell again
("must be used following each statement that modifies addressability ... whenever the contents of a BLL cell is changed
in any way", p. 23); a record over 4096 bytes takes its secondary cells too, each the one before plus 4096
(`ADD 4096 FRPTR GIVING FRPTR1`), reset before the SERVICE RELOAD.

IBM's own conversion to VS COBOL II (same book, "Converting to VS COBOL II", p. 29, and Figure 3, p. 26) is the model:
the cells become POINTERs, SET(cell) stays a SET(pointer), `SERVICE RELOAD record` becomes `SET ADDRESS OF record TO
cell`, the `ADD 4096` statements go, and `MOVE cell TO cell` is `SET cell TO cell`. Lowered so, a BLL program is a
pointer-lane program (GETMAIN SET, SET ADDRESS OF; DetCics / CicsTask in the port, the stub and GnuCOBOL's own SET
ADDRESS OF in the oracle), and both sides run the same lowered program. The record is addressed anew only where the
program reloads it, as IBM's compiler does; everything the lowering cannot keep exactly is refused by name, the whole
program (`Refused`, prefixed REFUSED_PREFIX): a cell used as a number, a long record reloaded before its secondary cells
were reset, SERVICE LABEL. What IBM leaves open is in the register entry.

IBM's chained storage areas (same book, "BLL and chained storage areas", p. 22: `MOVE NEXTAREA TO USERPTR. ANYNAME.`) are
kept too: a cell changed with no SERVICE RELOAD of its record later in its paragraph is re-addressed at every paragraph
name ("Insertion of a paragraph name causes the compiler to generate code to reestablish addressability"), so its record
is reloaded at the head of each paragraph (`SET ADDRESS OF` for the oracle; `CALL 'GGCBLLR'` for det, which leaves the
record as it is when the cell is null); an address moved between a cell and a fullword of data is a token both runtimes
number alike (`CALL 'GGCBLLP'` / `'GGCBLLG'`; ggcics.c, CicsTask.bllToken).
"""

from __future__ import annotations

import dataclasses
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det.source import Line, _outside_literals, expand, logical_lines

CELL_SPAN = 4096  # each BLL cell addresses this many bytes of its record (IBM, "Bll and large storage areas")
# #5119: SERVICE LABEL marks an LE recovery point (generated code after CALL 'CEE3SRP', DBB epscsmrd's EPSCSMRO), a
# program with or without BLL cells: its refusal is not a BLL one (refusal_map.json: le-recovery-point, #5106)
LE_REFUSED_PREFIX = "LE recovery point"
REFUSED_PREFIX = "OS/VS COBOL BLL addressing"  # every refusal's first words (refusal_map.json: bll-cells)

# a program the lowering must read: a SERVICE statement, or a SET / DATAPOINTER option naming an item declared as a
# fullword binary integer (a pointer-lane program's SET(pointer) names a USAGE POINTER: never read here)
_SERVICE = re.compile(r"\bSERVICE\s+(?:RELOAD|LABEL)\b", re.I)
_SET_NAME = re.compile(r"\b(?:SET|DATAPOINTER)\s*\(\s*([A-Z0-9][A-Z0-9-]*)\s*\)", re.I)
_FULLWORD = re.compile(
    r"^\s*0?2\s+([A-Z0-9][A-Z0-9-]*)\s+PIC(?:TURE)?\s+(?:IS\s+)?S9\(0?8\)\s+(?:USAGE\s+(?:IS\s+)?)?"
    r"(?:COMP|COMP-4|BINARY|COMPUTATIONAL|COMPUTATIONAL-4)\b",
    re.I,
)
_NAME = r"[A-Z0-9][A-Z0-9-]*"
_WORD = re.compile(_NAME, re.I)
_EXEC = re.compile(r"\bEXEC\s+(?:CICS|DLI|SQL)\b.*?\bEND-EXEC\b", re.I | re.S)
_RELOAD = re.compile(rf"\bSERVICE\s+RELOAD\s+({_NAME})", re.I)
_LABEL = re.compile(r"\bSERVICE\s+LABEL\b", re.I)
_MOVE = re.compile(rf"\bMOVE\s+({_NAME})\s+TO\s+({_NAME})", re.I)
_EQ = r"(?:IS\s+)?(NOT\s+)?(?:=|EQUALS?(?:\s+TO)?)"
_NIL = r"(?:ZEROS|ZEROES|ZERO|NULLS|NULL|LOW-VALUES|LOW-VALUE)(?![A-Z0-9-])"
# #5197: a cell tested for no address, in either operand order (IBM's conversion makes the cell a POINTER: `= NULL`).
# #5042: LOW-VALUE(S) is the same test: a cell is a fullword, so all-zero bytes are no address

_COMPARE = re.compile(rf"\b({_NAME})\s+{_EQ}\s+{_NIL}|\b{_NIL}\s+{_EQ}\s+({_NAME})(?![A-Z0-9-])", re.I)
# #5042: one cell compared with another (two pointers after the lowering: IBM allows = / NOT = between pointers)
_COMPARE_CELLS = re.compile(rf"\b({_NAME})\s+{_EQ}\s+({_NAME})(?![A-Z0-9-])", re.I)
_ADD = re.compile(rf"\bADD\s+4096\s*,?\s+({_NAME})\s+GIVING\s+({_NAME})", re.I)
_OPTION = re.compile(rf"\b({_NAME})\s*\(\s*({_NAME})\s*\)", re.I)
_PARAGRAPH = re.compile(rf"^ {{0,3}}({_NAME})(\s+SECTION)?\s*\.", re.I)
_PROCEDURE = re.compile(r"^\s*PROCEDURE\s+DIVISION\b", re.I)
_WS = re.compile(r"^\s*WORKING-STORAGE\s+SECTION\s*\.", re.I)
_LINKAGE = re.compile(r"^\s*LINKAGE\s+SECTION\s*\.", re.I)
_ENTRY = re.compile(rf"^\s*(01|77|66)\s+({_NAME})?|^\s*{_NAME}\s+SECTION\s*\.|^\s*PROCEDURE\s+DIVISION\b", re.I)
# options of a command that may name a cell: the pointer it sets (SET, ADDRESS's), the storage FREEMAIN releases
_CELL_OPTIONS = {"SET", "DATAPOINTER", "EIB", "COMMAREA", "CWA", "TWA", "TCTUA", "CSA", "ACEE"}
# figuratives that clear a cell (all-zero bytes: no address), and the other figuratives a cell cannot take
_CLEARS = {"ZERO", "ZEROS", "ZEROES", "LOW-VALUE", "LOW-VALUES", "NULL", "NULLS"}
_FIGURATIVE = _CLEARS | {"SPACE", "SPACES", "HIGH-VALUE", "HIGH-VALUES", "QUOTE", "QUOTES"}
# words after `MOVE a TO b` that end the statement (any other word may be a second receiving item)
_ENDS = {"ADD", "SERVICE", "MOVE", "EXEC", "IF", "ELSE", "END-IF", "GO", "PERFORM", "SET", "COMPUTE", "SUBTRACT",
         "DISPLAY", "CONTINUE", "GOBACK", "STOP", "CALL", "INITIALIZE", "EVALUATE", "WHEN", "END-EVALUATE", "NEXT",
         "EXIT", "STRING", "UNSTRING", "INSPECT", "MULTIPLY", "DIVIDE", "END-PERFORM"}  # fmt: skip


class Refused(L.LayoutError):
    """A BLL program the lowering cannot keep exactly: refused whole, by name (the message starts REFUSED_PREFIX), as
    the translator refuses any program it reads no further (a LayoutError)."""

    def __init__(self, why: str, prefix: str = REFUSED_PREFIX):
        super().__init__(f"{prefix}: {why}: not modelled")


@dataclass
class Plan:
    """What the lowering changes: line index -> its new text (a list: several lines, or none to drop it), and the
    lines inserted after the WORKING-STORAGE SECTION header."""

    edits: dict[int, list[str]] = field(default_factory=dict)
    ws_at: int | None = None
    inserted: list[str] = field(default_factory=list)


@dataclass
class Cells:
    """The program's BLL cell list: its name, the cells after the FILLER in order, each record's base cell and its
    secondary cells (one per 4096 bytes past the first), and each cell's record with its place (0 the base)."""

    name: str
    cells: list[str]
    base: dict[str, str]
    extra: dict[str, list[str]]
    of: dict[str, tuple[str, int]]


def needed(texts: list[str]) -> bool:
    """Whether the lowering must read the program at all (a cheap test of its text)."""
    if any(_SERVICE.search(t) for t in texts):
        return True
    named = {m.group(1).upper() for t in texts for m in _SET_NAME.finditer(t)}
    return bool(named) and any(m and m.group(1).upper() in named for m in map(_FULLWORD.match, texts))


def _fullword(records: list, name: str) -> bool:
    """Whether `name` is one plain fullword binary integer (no OCCURS above it): what may hold an address in data."""
    its = [it for r in records for it in r.walk() if it.name.upper() == name]
    if len(its) != 1:
        return False
    it, up = its[0], its[0]
    while up is not None:
        if up.occurs != 1:
            return False
        up = up.parent
    return (not it.children and it.category == "NUMERIC" and it.usage in ("BINARY", "COMP-5") and it.size == 4
            and it.scale == 0)  # fmt: skip


def _mask(text: str) -> str:
    return _outside_literals(text).upper()


def _cell_list(records: list) -> tuple[object | None, list]:
    """The LINKAGE 01 that can be a BLL cell list (the first, or the second after DFHCOMMAREA) and the LINKAGE 01s
    after it; (None, []) when that record is no list of fullwords led by a FILLER."""
    linkage = [r for r in records if r.section == "LINKAGE" and r.level in (1, 77)]
    at = 1 if linkage and linkage[0].name == "DFHCOMMAREA" else 0
    if len(linkage) <= at:
        return None, []
    cand = linkage[at]
    kids = cand.children
    ok = (
        cand.level == 1
        and cand.pic is None
        and not cand.redefines
        and len(kids) >= 2
        and kids[0].name == "FILLER"
        and all(
            not k.children and k.category == "NUMERIC" and k.usage in ("BINARY", "COMP-5") and k.size == 4
            and k.occurs == 1 and not k.redefines and k.scale == 0
            for k in kids
        )
    )  # fmt: skip
    return (cand, linkage[at + 1 :]) if ok else (None, [])


def _map(cand, rest: list) -> Cells:
    cells = [k.name.upper() for k in cand.children[1:]]
    base: dict[str, str] = {}
    extra: dict[str, list[str]] = {}
    of: dict[str, tuple[str, int]] = {}
    i = 0
    for r in rest:
        if r.level != 1:
            raise Refused(f"a level-{r.level} item {r.name} among the records the cells address")
        if r.name == "DFHCOMMAREA":
            raise Refused("DFHCOMMAREA after the BLL cell list (IBM: its definition must precede the list)")
        if r.redefines:
            raise Refused(f"{r.name} REDEFINES {r.redefines} among the records the cells address")
        n = max(1, math.ceil(r.size * r.occurs / CELL_SPAN))
        if i + n > len(cells):
            break  # (the records past the last cell have none: a SERVICE RELOAD of one is refused)
        base[r.name.upper()] = cells[i]
        extra[r.name.upper()] = cells[i + 1 : i + n]
        for k, c in enumerate(cells[i : i + n]):
            of[c] = (r.name.upper(), k)
        i += n
    return Cells(cand.name.upper(), cells, base, extra, of)


def plan(lines: list[Line], records: list, own: str, oracle: bool = False) -> Plan | None:
    """The lowering of a program (its logical lines, its records as det.layout parses them; `own` the program's file:
    only its own lines are changed), or None when it needs none; `oracle`: written for GnuCOBOL and the stub, not det.
    Raises Refused."""
    proc_at = next((i for i, ln in enumerate(lines) if _PROCEDURE.match(ln.text)), None)
    if proc_at is None:
        return None
    proc = list(range(proc_at, len(lines)))
    masked = {i: _mask(lines[i].text) for i in proc}
    cand, rest = _cell_list(records)
    cells = _map(cand, rest) if cand is not None else None
    text = "\n".join(masked[i] for i in proc)
    starts = []
    pos = 0
    for i in proc:
        starts.append(pos)
        pos += len(masked[i]) + 1

    def line_of(at: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= at:
                lo = mid
            else:
                hi = mid - 1
        return proc[lo]

    execs = [(m.start(), m.end()) for m in _EXEC.finditer(text)]

    def in_exec(at: int) -> bool:
        return any(a <= at < b for a, b in execs)

    if cells is not None and not (
        _RELOAD.search(text)
        or any(
            o.group(1) in ("SET", "DATAPOINTER") and o.group(2) in cells.cells
            for a, b in execs
            for o in _OPTION.finditer(text, a, b)
        )
    ):
        cells = None  # a list of fullwords and no evidence of BLL addressing: ordinary data, as in VS COBOL II
    linkage = {r.name.upper() for r in records if r.section == "LINKAGE" and r.level == 1}
    names = {it.name.upper() for r in records for it in r.walk()}
    out = Plan()
    through: set[str] = set()
    # ---- the statements: (start, end, replacement, event) in text order ----------------------------------------
    found: list[tuple[int, int, str, tuple]] = []
    for m in _LABEL.finditer(text):
        if not in_exec(m.start()):
            raise Refused(
                f"SERVICE LABEL (line {lines[line_of(m.start())].line}): the resume point after CEE3SRP, not BLL "
                "addressing",
                LE_REFUSED_PREFIX,
            )
    for m in _RELOAD.finditer(text):
        if in_exec(m.start()):
            continue
        rec = m.group(1)
        where = f"line {lines[line_of(m.start())].line}"
        if cells is not None and rec == cells.name:
            found.append((m.start(), m.end(), "CONTINUE", ("none",)))  # (the list is always addressed)
        elif cells is not None and rec in cells.base:
            found.append((m.start(), m.end(), f"SET ADDRESS OF {rec} TO {cells.base[rec]}", ("reload", rec)))
        elif rec not in linkage:
            raise Refused(f"SERVICE RELOAD {rec} ({where}): not a LINKAGE SECTION 01 record")
        elif cells is not None and rec != "DFHCOMMAREA":
            raise Refused(f"SERVICE RELOAD {rec} ({where}): no BLL cell addresses it")
        else:  # DFHCOMMAREA, or a program with no BLL cells (VS COBOL II ignores SERVICE RELOAD, IBM p. 24)
            found.append((m.start(), m.end(), "CONTINUE", ("none",)))
    if cells is not None:
        cellset = set(cells.cells)
        for m in _ADD.finditer(text):
            a, b = m.group(1), m.group(2)
            if in_exec(m.start()) or (a not in cellset and b not in cellset):
                continue
            ra, rb = cells.of.get(a), cells.of.get(b)
            if ra is None or rb is None or ra[0] != rb[0] or rb[1] != ra[1] + 1:
                raise Refused(f"ADD 4096 {a} GIVING {b} (line {lines[line_of(m.start())].line}): {b} is not the "
                              f"secondary cell after {a} of one record")  # fmt: skip
            found.append((m.start(), m.end(), "CONTINUE", ("extra", rb[0], b)))
        for m in _MOVE.finditer(text):
            a, b = m.group(1), m.group(2)
            if in_exec(m.start()) or (a not in cellset and b not in cellset):
                continue
            where = f"line {lines[line_of(m.start())].line}"
            if cells.of.get(b, ("", 0))[1] or cells.of.get(a, ("", 0))[1]:
                raise Refused(f"MOVE {a} TO {b} ({where}): a secondary cell of a long record (only ADD 4096 sets one)")
            clear = a.upper() in _CLEARS and b in cellset
            data = None if clear else b if a in cellset and b not in cellset else a if a not in cellset else None
            if data is not None and data.upper() in _FIGURATIVE:
                raise Refused(f"MOVE {a} TO {b} ({where}): only ZERO or LOW-VALUES clears a cell")
            if data is not None and (data == cells.name or not _fullword(records, data)):
                raise Refused(f"MOVE {a} TO {b} ({where}): an address moved to or from {data}, no plain fullword")
            nxt = _WORD.match(text, len(text) - len(text[m.end() :].lstrip()))
            if nxt is not None and nxt.group(0) not in _ENDS and (nxt.group(0) in names or nxt.group(0) in cellset):
                raise Refused(f"MOVE {a} TO {b} {nxt.group(0)} ({where}): an address moved to several items")
            if clear:  # (#5119: a cell cleared; IBM's conversion makes it a POINTER, NULL = all-zero bytes, X47)
                found.append((m.start(), m.end(), f"SET {b} TO NULL", ("change", b)))
            elif data is None:
                found.append((m.start(), m.end(), f"SET {b} TO {a}", ("change", b)))
            elif data == b:  # (an address into data: the token for it, IBM's chained area's "pointer to the next area")
                found.append((m.start(), m.end(), f"CALL 'GGCBLLP' USING {a} {b}", ("none",)))
            else:
                found.append((m.start(), m.end(), f"CALL 'GGCBLLG' USING {a} {b}", ("change", b)))
        for m in _COMPARE.finditer(text):
            cell, neg = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            if in_exec(m.start()) or cell.upper() not in cellset:
                continue
            if cells.of.get(cell.upper(), ("", 0))[1]:
                raise Refused(f"{cell} (line {lines[line_of(m.start())].line}): a secondary cell of a long record "
                              "compared (only its base cell holds an address)")  # fmt: skip
            found.append((m.start(), m.end(), f"{cell} {'NOT ' if neg else ''}= NULL", ("none",)))
        for m in _COMPARE_CELLS.finditer(text):
            left, neg, right = m.group(1), m.group(2), m.group(3)
            if in_exec(m.start()) or left.upper() not in cellset or right.upper() not in cellset:
                continue
            if cells.of.get(left.upper(), ("", 0))[1] or cells.of.get(right.upper(), ("", 0))[1]:
                raise Refused(f"{left} (line {lines[line_of(m.start())].line}): a secondary cell of a long record "
                              "compared (only its base cell holds an address)")  # fmt: skip
            found.append((m.start(), m.end(), f"{left} {'NOT ' if neg else ''}= {right}", ("none",)))
        for a, b in execs:
            for o in _OPTION.finditer(text, a, b):
                if o.group(2) not in cellset:
                    continue
                if o.group(1) not in _CELL_OPTIONS:
                    raise Refused(f"{o.group(1)}({o.group(2)}) (line {lines[line_of(o.start())].line}): a BLL cell "
                                  "as a command's data")  # fmt: skip
                if o.group(1) != "DATAPOINTER":
                    found.append((o.start(), o.start(), "", ("change", o.group(2))))
        # every other mention of a cell (or of the list) uses an address as a number
        spans = [(s, e) for s, e, _, ev in found if e > s] + execs
        for name in [*cellset, cells.name]:
            for m in re.finditer(rf"(?<![A-Z0-9-]){re.escape(name)}(?![A-Z0-9-])", text):
                if not any(s <= m.start() < e for s, e in spans):
                    raise Refused(f"{name} (line {lines[line_of(m.start())].line}): a BLL cell used as a number")
        through = _paragraph_rule(lines, proc, starts, found, cells, line_of)
    if not found:
        return None
    # ---- the edits --------------------------------------------------------------------------------------------
    pieces: dict[int, list[tuple[int, int, str]]] = {}
    for s, e, rep, _ev in found:
        if e == s:
            continue
        first, last = line_of(s), line_of(e - 1)
        for i in range(first, last + 1):
            if lines[i].file != own:
                raise Refused(f"a BLL statement in the COPY member {Path(lines[i].file).name}")
            k = proc.index(i)
            a = max(s, starts[k]) - starts[k]
            b = min(e, starts[k] + len(masked[i])) - starts[k]
            pieces.setdefault(i, []).append(
                (a, b, rep if i == first else " " * (b - a))
            )  # (the rest keeps its columns)
    for i, cuts in pieces.items():
        t = lines[i].text
        for a, b, rep in sorted(cuts, reverse=True):
            t = t[:a] + rep + t[b:]
        out.edits[i] = [t] if t.strip() else []
    if cells is not None:
        if through:
            _paragraph_reloads(lines, proc, starts, text, cells, through, own, oracle, out)
        _data_edits(lines, cells, own, proc_at, out)
    return out


def _heads(lines, proc) -> list[int]:
    """The places in `proc` (its indexes past the PROCEDURE DIVISION header) where a paragraph or section name starts."""
    return [k for k, i in enumerate(proc) if k and (m := _PARAGRAPH.match(lines[i].text))
            and m.group(1).upper() not in _ENDS]  # fmt: skip


def _paragraph_rule(lines, proc, starts, found, cells: Cells, line_of) -> set[str]:
    """IBM: SERVICE RELOAD must follow every statement that changes a cell, and a long record's secondary cells are
    reset before it (refused when too early). A change with no SERVICE RELOAD of its record later in the same paragraph
    is addressed again at the next paragraph name (IBM's chained storage areas): the records so changed are returned,
    to be reloaded at every paragraph name; a long record's secondary cells must be reset before that name too."""
    heads = [starts[k] for k in _heads(lines, proc)]
    events = sorted(found, key=lambda f: f[0])
    pending: dict[str, tuple[set[str], int]] = {}
    through: set[str] = set()

    def close() -> None:
        for rec, (left, at) in pending.items():
            if left:
                raise Refused(f"{cells.base[rec]} changed (line {lines[line_of(at)].line}) and a paragraph name reached "
                              f"before its secondary cells {', '.join(sorted(left))} were reset")  # fmt: skip
            through.add(rec)

    h = 0
    for s, _e, _rep, ev in events:
        while h < len(heads) and heads[h] <= s:
            close()
            pending.clear()
            h += 1
        if ev[0] == "change":
            rec, k = cells.of.get(ev[1], (None, 0))
            if rec is None:
                continue  # (a cell no record has: only its value changes)
            if k:
                raise Refused(f"{ev[1]} (line {lines[line_of(s)].line}): a secondary cell of a long record set by a "
                              "command (only ADD 4096 sets one)")  # fmt: skip
            pending[rec] = (set(cells.extra[rec]), s)
        elif ev[0] == "extra" and ev[1] in pending:
            pending[ev[1]][0].discard(ev[2])
        elif ev[0] == "reload":
            left = pending.pop(ev[1], (set(), s))[0]
            if left:
                raise Refused(f"SERVICE RELOAD {ev[1]} (line {lines[line_of(s)].line}) before its secondary cells "
                              f"{', '.join(sorted(left))} were reset")  # fmt: skip
    close()
    return through


def _paragraph_reloads(lines, proc, starts, text, cells: Cells, through: set[str], own: str, oracle: bool,
                       out: Plan) -> None:  # fmt: skip
    """Each record in `through` reloaded from its base cell at the head of every paragraph and section (IBM's compiler
    re-addresses at each procedure name, however it is reached: falling into it, GO TO, PERFORM, a HANDLE exit). A
    paragraph that is only EXIT reads no record, so it is left alone."""
    recs = [r for r in cells.base if r in through]  # (in the cells' order: the same text every time)
    stmts = [f"    SET ADDRESS OF {r} TO {cells.base[r]}." if oracle else f"    CALL 'GGCBLLR' USING {r} {cells.base[r]}."
             for r in recs]  # fmt: skip
    heads = _heads(lines, proc)
    if re.search(r"(?<![A-Z0-9-])DECLARATIVES\s*\.", text):
        raise Refused("DECLARATIVES in a program whose records are addressed again at paragraph names")
    for n, k in enumerate(heads):
        i = proc[k]
        m = _PARAGRAPH.match(lines[i].text)
        if m is None:  # (_heads matched it)
            continue
        end = starts[heads[n + 1]] if n + 1 < len(heads) else len(text)
        if text[starts[k] + m.end() : end].strip() == "EXIT.":
            continue
        if lines[i].file != own:
            raise Refused(f"a paragraph name in the COPY member {Path(lines[i].file).name}")
        base = (out.edits.get(i) or [lines[i].text])[0]
        rest = base[m.end() :]
        out.edits[i] = [base[: m.end()], *stmts, *([rest] if rest.strip() else [])]


def _data_edits(lines: list[Line], cells: Cells, own: str, proc_at: int, out: Plan) -> None:
    """The cell list leaves LINKAGE and is written in WORKING-STORAGE as POINTERs (a record's base cells; secondary
    cells and the FILLER are dropped: the pointer addresses the whole record)."""
    link = next((i for i in range(proc_at) if _LINKAGE.match(lines[i].text)), None)
    at = next((i for i in range(link or 0, proc_at)
               if link is not None and re.match(rf"^\s*01\s+{re.escape(cells.name)}\s*\.", lines[i].text, re.I)), None)  # fmt: skip
    ws = next((i for i in range(proc_at) if _WS.match(lines[i].text)), None)
    if at is None or ws is None:
        raise Refused("the BLL cell list or the WORKING-STORAGE SECTION is not in the program's own text")
    end = next((i for i in range(at + 1, proc_at + 1) if i == proc_at or _ENTRY.match(lines[i].text)), proc_at)
    for i in [at, *range(at + 1, end), ws]:
        if lines[i].file != own:
            raise Refused(f"the BLL cell list in the COPY member {Path(lines[i].file).name}")
    for i in range(at, end):
        out.edits[i] = []
    secondary = {c for v in cells.extra.values() for c in v}
    out.ws_at = ws
    out.inserted = [f"01  {cells.name}."] + [f"    05  {c} USAGE POINTER." for c in cells.cells if c not in secondary]


def _records(lines: list[Line]) -> list:
    return L.parse(lines)


def lower(lines: list[Line], own: str | None = None) -> list[Line]:
    """The det translator's lowering of its logical lines (COPY members expanded): unchanged when the program needs none.
    Raises Refused."""
    if not lines or not needed([ln.text for ln in lines]):
        return lines
    own = own or lines[0].file
    p = plan(lines, _records(lines), own)
    if p is None:
        return lines
    out: list[Line] = []
    for i, ln in enumerate(lines):
        if i in p.edits:
            out += [
                dataclasses.replace(ln, text=t, cut="", lost="", lost_after="", lost_joined=False) for t in p.edits[i]
            ]
        else:
            out.append(ln)
        if i == p.ws_at:
            out += [Line(t, ln.file, ln.line) for t in p.inserted]
    return out


def _fixed(text: str) -> list[str]:
    """Columns 8-72 of one line of fixed form, wrapped at a space outside literals when longer than 65."""
    rows = []
    while len(text) > 65:
        bare = _outside_literals(text)
        cut = bare.rfind(" ", 5, 65)
        if cut <= 4:
            raise Refused("a lowered statement too long for fixed form")
        rows.append(text[:cut].rstrip())
        text = "    " + text[cut:].lstrip()
    rows.append(text)
    return rows


def lower_text(source: str, dirs: list[Path]) -> str:
    """The equivalence oracle's lowering of a fixed-form program's text (COPY members found in `dirs`), so GnuCOBOL runs
    the program the det port was translated from: unchanged when it needs none. Raises Refused."""
    raw = source.splitlines()
    if not needed([r[7:72] if len(r) > 6 and r[6] not in "*/" else "" for r in raw]):
        return source
    own = "<program>"
    lines = expand(logical_lines(raw, own), list(dirs))
    p = plan(lines, _records(lines), own, oracle=True)
    if p is None:
        return source
    edits: dict[int, list[str]] = {}
    for i, texts in p.edits.items():
        n = lines[i].line - 1
        edits[n] = [r for t in texts for r in _fixed(t)]
        k = n + 1
        while k < len(raw) and len(raw[k]) > 6 and raw[k][6] == "-":  # (a continuation of the line: part of it)
            edits[k] = []
            k += 1
    out: list[str] = []
    for n, row in enumerate(raw):
        if n in edits:
            texts = edits[n]
            out += [row[:6].ljust(6) + " " + texts[0]] + ["       " + t for t in texts[1:]] if texts else [
                row[:6].ljust(6) + "*"]  # fmt: skip
        else:
            out.append(row)
        if p.ws_at is not None and n == lines[p.ws_at].line - 1:
            out += ["       " + t for t in p.inserted]
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")
