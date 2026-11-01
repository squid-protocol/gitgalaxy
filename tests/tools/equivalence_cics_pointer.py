"""#6839 slice 3 (register X47): the CICS oracle's side of a POINTER's numeric view.

GnuCOBOL's POINTER is 8 bytes little-endian; ZECS001's `CACHE-ADDRESS-X REDEFINES CACHE-ADDRESS PIC S9(08) COMP` is a
4-byte big-endian view of it, so `ADD ZF-LENGTH TO CACHE-ADDRESS-X` writes a number into the wrong half of the address
and the next `SET ADDRESS OF` or WEB CONVERSE FROM(...) reads an unmapped one (SIGSEGV). IBM's pointer is 4 bytes and
the add is plain address arithmetic. `lower` rewrites the program so the oracle does the address arithmetic on the
pointer itself, the two idioms the det translator models (`det/program.pointer_view_of`, `Gen.pointer_view_statement`):

* `ADD n TO view` / `SUBTRACT n FROM view` -> `CALL "GGCPTRADV" USING ptr BY VALUE n` (negated for SUBTRACT); n is an
  integer literal or a BINARY item of at most 9 digits; ggcics.c refuses a result outside the pointer's block;
* `MOVE view1 TO view2` -> `SET ptr2 TO ptr1`;
* the view's declaration is dropped.

Any other use of a view (COMPUTE, IF, a MOVE to or from a number, ADD GIVING, several targets, a statement over several
lines) is `Unsupported`, refused by name as the translator refuses it. A program with no view comes back unchanged.
(The batch twin for z/OS control blocks is equivalence_mvs.py.)
"""

from __future__ import annotations

import re

from equivalence_mvs import FLAGS, ID, _code, _wrap


class Unsupported(Exception):
    """A numeric view of a POINTER used in a way the oracle does not model."""


_PTR = re.compile(rf"\b\d\d\s+({ID})\s+(?:USAGE\s+(?:IS\s+)?)?POINTER\b", FLAGS)
_VIEW = re.compile(
    rf"\b\d\d\s+({ID})\s+REDEFINES\s+({ID})\s+(?:PIC(?:TURE)?\s+(?:IS\s+)?S?9(?:\(\d+\)|9*)\s+"
    r"(?:USAGE\s+(?:IS\s+)?)?(?:COMP|COMPUTATIONAL|BINARY)|(?:USAGE\s+(?:IS\s+)?)?(?:COMP|COMPUTATIONAL|BINARY)\s+"
    r"PIC(?:TURE)?\s+(?:IS\s+)?S?9(?:\(\d+\)|9*))\s*\.",
    FLAGS,
)
# what may follow a modelled statement on its line: nothing, the period, or the next clause of the enclosing sentence
_TAIL = re.compile(r"^\s*(\.|$|(ELSE|END-IF|END-PERFORM|END-EVALUATE|WHEN)\b)", FLAGS)
_BINARY = re.compile(r"\b(COMP|COMPUTATIONAL|BINARY)\b", FLAGS)
_DIGITS = re.compile(r"\bS?9(?:\((\d+)\)|(9*))", FLAGS)


def _word(name: str) -> str:
    """`name` as a whole COBOL word: a hyphen continues a name, so `\\b` would find `A-B` inside `A-B-C`."""
    return rf"(?<![\w-]){re.escape(name)}(?![\w-])"


def _binary_operand(text: str, name: str) -> bool:
    """`name` is declared as an integer BINARY item of at most 9 digits (an int, which a BY VALUE argument is)."""
    m = re.search(rf"\b\d\d\s+{re.escape(name)}\b([^.]*)\.", text, FLAGS)
    if not m or not _BINARY.search(m.group(1)):
        return False
    pic = _DIGITS.search(m.group(1))
    if pic is None or re.search(r"\bV\b|9V|V9", m.group(1), FLAGS):
        return False
    digits = int(pic.group(1)) if pic.group(1) else 1 + len(pic.group(2))
    return digits <= 9


def _views(lines: list[str]) -> tuple[dict[str, str], set[int]]:
    """({view: pointer}, the line numbers of the views' declarations)."""
    text, starts = "", []
    for ln in lines:
        starts.append(len(text))
        text += _code(ln) + "\n"
    pointers = {m.group(1).upper() for m in _PTR.finditer(text)}
    views: dict[str, str] = {}
    drop: set[int] = set()
    for m in _VIEW.finditer(text):
        if m.group(2).upper() not in pointers:
            continue
        views[m.group(1).upper()] = m.group(2).upper()
        first = max(i for i, s in enumerate(starts) if s <= m.start())
        last = max(i for i, s in enumerate(starts) if s <= m.end() - 1)
        drop.update(range(first, last + 1))
    return views, drop


def _statement(code: str, views: dict[str, str], text: str) -> str:
    """`code` with each modelled use of a view turned into its CALL / SET."""
    for view, ptr in views.items():
        v = _word(view)
        operand = r"([+-]?\s*\d+|" + ID + r")"
        for pat, sub in (
            (rf"\bADD\s+{operand}\s+TO\s+{v}", False),
            (rf"\bSUBTRACT\s+{operand}\s+FROM\s+{v}", True),
        ):
            while m := re.search(pat, code, FLAGS):
                n = re.sub(r"\s+", "", m.group(1))
                if not _TAIL.match(code[m.end() :]):
                    raise Unsupported(
                        f"{view}: more than one `ADD|SUBTRACT n TO|FROM {view}` (GIVING, ROUNDED, SIZE ERROR, other targets)"
                    )
                if n.upper() in views:
                    raise Unsupported(f"{view}: the operand {n} is a numeric view of a pointer")
                if not re.fullmatch(r"[+-]?\d+", n) and not _binary_operand(text, n):
                    raise Unsupported(
                        f"{view}: the operand {n} is no integer literal or BINARY item of at most 9 digits"
                    )
                if sub:
                    if not re.fullmatch(
                        r"[+-]?\d+", n
                    ):  # `BY VALUE -item` is no COBOL, and the stub has no subtract entry
                        raise Unsupported(f"{view}: SUBTRACT {n} FROM {view} (only an integer literal can be negated)")
                    n = n[1:] if n[0] == "-" else "-" + n.lstrip("+")
                code = code[: m.start()] + f'CALL "GGCPTRADV" USING {ptr} BY VALUE {n}' + code[m.end() :]
    for view, ptr in views.items():
        for other, optr in views.items():
            pat = rf"\bMOVE\s+{_word(view)}\s+TO\s+{_word(other)}"
            while m := re.search(pat, code, FLAGS):
                if not _TAIL.match(code[m.end() :]):
                    raise Unsupported(f"{other}: `MOVE {view} TO {other}` with other targets")
                code = code[: m.start()] + f"SET {optr} TO {ptr}" + code[m.end() :]
    return code


def lower(program: str) -> str:
    """The program the oracle compiles: unchanged when no POINTER has a numeric view."""
    lines = program.split("\n")
    views, drop = _views(lines)
    if not views:
        return program
    text = "\n".join(_code(ln) for ln in lines)
    out: list[str] = []
    for i, ln in enumerate(lines):
        c = _code(ln)
        if i in drop:
            out.append(f"{ln[:6]}* lowered (register X47): {c.strip()[:40]}")
            continue
        new = _statement(c, views, text) if c.strip() else c
        out.extend([ln] if new == c else _wrap((ln[:6] + new).rstrip()))
    body = "\n".join(_code(x) for x in out)
    for view in views:
        if re.search(_word(view), body, FLAGS):
            raise Unsupported(
                f"{view} (a numeric view of the POINTER {views[view]}) is used other than as "
                f"`ADD|SUBTRACT n TO|FROM view` or `MOVE view TO view`: an address is no number"
            )
    return "\n".join(out)
