"""#5856 (register A2): the COBOL oracle's side of a batch program's PSA -> TCB -> TIOT walk.

GnuCOBOL has no PSA at address 0, and a 4-byte BINARY cannot overlay its 8-byte POINTER the way CardDemo CBSTM03A's
`TIOT-INDEX REDEFINES BUMP-TIOT POINTER` does on z/OS. `lower` rewrites the program so the walk runs on the blocks
tests/equivalence/le/ggtiot.c lays from the case's stated step (`mvs_step`), the same blocks the det runtime lays
(DetMvs.java):

* a plain POINTER (01, no VALUE) that is only ever the source of `SET ADDRESS OF rec TO ptr` is IBM's address 0 (the
  PSA): `CALL "GGPSAPTR" USING ptr` first;
* every `SET ADDRESS OF rec TO ptr` is preceded by `CALL "GGMVSCHK" USING ptr BY VALUE LENGTH OF rec` (a record longer
  than the block's remaining bytes is refused, as the Java side refuses it);
* `ptr REDEFINES view POINTER` becomes a plain POINTER (the 4-byte numeric `view` is dropped), and the only uses of
  `view` the det side models, `COMPUTE view = view +|- n`, `ADD n TO view` and `SUBTRACT n FROM view`, become
  `CALL "GGTIOTADV" / "GGTIOTSUB" USING ptr BY VALUE n`. Any other use of `view` would read bytes of an address
  (z/OS's 4-byte view of a handle is storage-layout luck): refused by name, as the translator refuses it.

Faithful or refused, never guessed: `Unsupported` is the harness's "not runnable faithfully".
"""

from __future__ import annotations

import re

ID = r"[A-Z0-9][A-Z0-9-]*"
OPERAND = rf"([+-]?\s*\d+|LENGTH\s+OF\s+{ID})"
# fixed format: columns 8-72 are code (7 is the indicator)
LAST = 72
FLAGS = re.IGNORECASE

_VIEW = re.compile(rf"^(\s*)01\s+({ID})\s+REDEFINES\s+({ID})\s+POINTER\s*\.\s*$", FLAGS)
_PLAIN = re.compile(rf"^\s*01\s+({ID})\s+POINTER\s*\.\s*$", FLAGS)
_SET = re.compile(rf"\bSET\s+ADDRESS\s+OF\s+({ID})\s+TO\s+({ID})\b", FLAGS)
# what may not follow an operand: more arithmetic, a SIZE ERROR phrase, ROUNDED, GIVING
_MORE = re.compile(r"^\s*([-+*/(]|(NOT\s+)?(ON\s+)?SIZE\b|ROUNDED\b|GIVING\b)", FLAGS)


class Unsupported(Exception):
    """The program uses the control blocks in a way the oracle does not model."""


def _code(line: str) -> str:
    return line[6:LAST] if len(line) > 6 and line[6] not in "*/" else ""


def _wrap(line: str) -> list[str]:
    """One source line as fixed-format lines of at most 72 columns, cut at blanks (a statement may continue)."""
    if len(line) <= LAST:
        return [line]
    out = []
    while len(line) > LAST:
        cut = line.rfind(" ", 12, LAST)
        out.append(line[:cut].rstrip())
        line = " " * 15 + line[cut:].lstrip()
    return [*out, line]


def _arith(code: str, binaries: dict[str, str]) -> str:
    """`code` with each modelled use of a numeric view turned into its CALL."""
    for view, ptr in binaries.items():
        v = re.escape(view)
        pats = [  # (pattern, the group holding a COMPUTE's sign or None, the operand's group, SUBTRACT)
            (rf"\bCOMPUTE\s+{v}\s*=\s*{v}\s*([+-])\s*{OPERAND}", 1, 2, False),
            (rf"\bADD\s+{OPERAND}\s+TO\s+{v}\b", None, 1, False),
            (rf"\bSUBTRACT\s+{OPERAND}\s+FROM\s+{v}\b", None, 1, True),
        ]
        for pat, sign, operand, sub in pats:
            while m := re.search(pat, code, FLAGS):
                if _MORE.match(code[m.end() :]):
                    raise Unsupported(
                        f"{view}: more than `{view} +|- n` (a SIZE ERROR phrase, ROUNDED, a longer expression)"
                    )
                minus = sub or (sign is not None and m.group(sign) == "-")
                n = re.sub(r"\s+", " ", m.group(operand))
                if n[0] in "+-":
                    n = n[0].replace("+", "") + n[1:].strip()
                call = f'CALL "{"GGTIOTSUB" if minus else "GGTIOTADV"}" USING {ptr} BY VALUE {n}'
                code = code[: m.start()] + call + code[m.end() :]
    return code


def lower(program: str, step: str | None) -> str:
    """The program the oracle compiles: unchanged when it walks no control block; `step` is the case's `mvs_step`."""
    lines = program.split("\n")
    views: dict[str, str] = {}  # pointer view -> the numeric item it REDEFINES
    plain: set[str] = set()
    pointers: set[int] = set()  # the lines declaring a plain or a view POINTER
    for i, ln in enumerate(lines):
        c = _code(ln)
        if m := _VIEW.match(c):
            views[m.group(2).upper()] = m.group(3).upper()
            pointers.add(i)
        elif m := _PLAIN.match(c):
            plain.add(m.group(1).upper())
            pointers.add(i)
    binaries = {b: ptr for ptr, b in views.items()}
    numeric = {
        i
        for i, ln in enumerate(lines)
        if (m := re.match(rf"^\s*01\s+({ID})\b", _code(ln), FLAGS)) and m.group(1).upper() in binaries
    }
    text = "\n".join(_code(ln) for i, ln in enumerate(lines) if i not in pointers)
    sets = [(m.group(1).upper(), m.group(2).upper()) for m in _SET.finditer(text)]
    # a PSA pointer is named nowhere but as the source of a SET ADDRESS OF
    null_ptrs = {
        p
        for p in plain
        if any(t == p for _, t in sets)
        and len(re.findall(rf"\b{re.escape(p)}\b", text, FLAGS)) == sum(t == p for _, t in sets)
    }
    if not views and not null_ptrs:
        return program
    if step is None:
        raise Unsupported(
            "the program walks z/OS control blocks (PSA / TCB / TIOT): no job step stated (case `mvs_step`)"
        )
    if "'" in step or "\n" in step:
        raise Unsupported("mvs_step: a quote or a newline")
    for i in numeric:
        if not _code(lines[i]).rstrip().endswith("."):
            raise Unsupported(f"{lines[i].strip()}: a numeric item a POINTER REDEFINES declared over several lines")

    def check(m: re.Match[str]) -> str:
        rec, ptr = m.group(1), m.group(2)
        pre = f'CALL "GGPSAPTR" USING {ptr} ' if ptr.upper() in null_ptrs else ""
        return f'{pre}CALL "GGMVSCHK" USING {ptr} BY VALUE LENGTH OF {rec} {m.group(0)}'

    out: list[str] = []
    for i, ln in enumerate(lines):
        c = _code(ln)
        if i in numeric:  # the numeric item is dropped: the pointer stands alone (8 bytes, as GnuCOBOL has it)
            out.append(f"{ln[:6]}* lowered (register A2): {c.strip()[:40]}")
        elif m := _VIEW.match(c):
            out.append(f"{ln[:6]}{m.group(1)}01  {m.group(2)} POINTER.")
        elif not c.strip():
            out.append(ln)
        else:
            new = _SET.sub(check, _arith(c, binaries))
            out.extend([ln] if new == c else _wrap((ln[:6] + new).rstrip()))
    left = [b for b in binaries if re.search(rf"\b{re.escape(b)}\b", "\n".join(_code(x) for x in out), FLAGS)]
    if left:
        raise Unsupported(
            f"{left[0]} (a numeric item a POINTER REDEFINES) is used other than as `+|- n`: a handle is no number"
        )
    return "\n".join(out)
