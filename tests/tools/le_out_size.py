"""#5003 [c:a06ff706] (register L6): the declared size of the output item of a CEEDATE / CEEDATM call.

GnuCOBOL hands a CALLed C routine a bare pointer, so tests/equivalence/le/le_time.c cannot see how long the output item
is, and a result longer than the item would be written over the storage beside it (IBM cuts it: CEE2526 / CEE2527; the
det runtime refuses, LeTime.putVstring). `env` reads the program's DATA DIVISION and gives the harness
`GG_LE_OUT_SIZES=CEEDATE=80,CEEDATM=80`, which the model reads to refuse by name a result that does not fit.

Resolved or left alone, never guessed: an item whose size this cannot state exactly (COPY member, REDEFINES, OCCURS,
USAGE other than DISPLAY, a subscripted or reference-modified operand, a name declared twice) is left out, and the
model behaves as before for it (the census test, test_le_fmd_census_5003.py, keeps burned programs from needing one).
With several calls of one service the smallest resolved item counts: a refusal is never a loosened proof.
"""

from __future__ import annotations

import re

SERVICES = ("CEEDATE", "CEEDATM")
OUTPUT_ARG = 2  # CEEDATE lilian, picture, OUTPUT, fc; CEEDATM seconds, picture, OUTPUT, fc
LAST = 72  # fixed format: columns 8-72 are code, 7 the indicator
ID = r"[A-Z0-9][A-Z0-9-]*"
FLAGS = re.IGNORECASE

_ENTRY = re.compile(rf"^(\d{{1,2}})\s+({ID})\s*(.*)$", FLAGS | re.S)
_PIC = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", FLAGS)
_CHAR = re.compile(r"([XA9])(?:\((\d+)\))?", FLAGS)
_CALL = re.compile(rf"\bCALL\s+['\"]({'|'.join(SERVICES)})['\"]\s+USING\s+(.*)", FLAGS | re.S)
_NOT_STORAGE = re.compile(
    r"\b(REDEFINES|OCCURS|RENAMES|COMP\w*|BINARY|PACKED-DECIMAL|INDEX|POINTER|SEPARATE|JUST\w*)\b", FLAGS
)


def _statements(source: str) -> list[str]:
    lines = []
    for ln in source.splitlines():
        if len(ln) > 6 and ln[6] not in "*/":
            lines.append(ln[7:LAST])
    text = " ".join(x.strip() for x in lines)
    return [s.strip() for s in re.split(r"\.(?:\s+|$)", text) if s.strip()]


def _picture_size(pic: str) -> int | None:
    body = re.sub(r"^S", "", pic.strip().rstrip("."), flags=FLAGS)
    if not body or re.search(r"[^XA9()\d]", body, FLAGS):
        return None
    total = 0
    pos = 0
    for m in _CHAR.finditer(body):
        if m.start() != pos:
            return None
        total += int(m.group(2) or 1)
        pos = m.end()
    return total if pos == len(body) else None


def item_sizes(source: str) -> dict[str, int]:
    """Declared byte size of each uniquely-named DISPLAY item or group whose size is exactly known."""
    entries: list[tuple[int, str, int | None]] = []  # (level, name, own size; None: not a size this can state)
    for stmt in _statements(source):
        m = _ENTRY.match(stmt)
        if not m or int(m.group(1)) in (66, 88):
            continue
        level, name, rest = int(m.group(1)), m.group(2).upper(), m.group(3)
        pic = _PIC.search(rest)
        if _NOT_STORAGE.search(rest):
            entries.append((level, name, -1))  # a group or item with a clause that changes the size
        elif pic:
            entries.append((level, name, _picture_size(pic.group(1))))
        else:
            entries.append((level, name, 0 if level != 77 else None))  # a group: its children give the size
    sizes: dict[str, int | None] = {}
    seen: set[str] = set()
    stack: list[list] = []  # [level, name, total or None, is_group]

    def close(until: int) -> None:
        while stack and stack[-1][0] >= until:
            level, name, total, _ = stack.pop()
            if name in seen:
                sizes[name] = None  # declared twice: which one the call means is a scope question
            else:
                seen.add(name)
                sizes[name] = total
            if stack and stack[-1][2] is not None:
                stack[-1][2] = None if total is None else stack[-1][2] + total

    for level, name, own in entries:
        close(level if level != 77 else 1)
        if own == -1:
            stack.append([level, name, None, True])
        elif own == 0:
            stack.append([level, name, 0, True])
        else:
            stack.append([level, name, own, False])
    close(0)
    return {k: v for k, v in sizes.items() if v}


def output_sizes(source: str) -> dict[str, int]:
    """Service -> the smallest resolved output item of its calls."""
    items = item_sizes(source)
    found: dict[str, int] = {}
    for stmt in _statements(source):
        for m in _CALL.finditer(stmt):
            args = [
                a
                for a in re.split(
                    r"[\s,]+", re.sub(r"\bBY\s+(?:REFERENCE|CONTENT|VALUE)\b", " ", m.group(2), flags=FLAGS)
                )
                if a
            ]
            if len(args) <= OUTPUT_ARG:
                continue
            size = items.get(args[OUTPUT_ARG].upper())
            if size is not None:
                svc = m.group(1).upper()
                found[svc] = min(size, found.get(svc, size))
    return found


def env(source: str) -> str:
    """The shell assignment the harness puts before `./program` ("" when no output item resolves)."""
    sizes = output_sizes(source)
    return f"GG_LE_OUT_SIZES={','.join(f'{k}={v}' for k, v in sorted(sizes.items()))} " if sizes else ""
