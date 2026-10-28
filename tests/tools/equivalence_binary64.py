"""#5867 (register C6): the COBOL oracle's side of EPSMPMT's binary64 payment formula.

The owner ruled (2026-10-27) that DBB EPSMPMT's `(1 + C) ** N` payment (line 125) and its dead-code
`FUNCTION ANNUITY` (line 144) are IEEE 754 binary64, on the det port (`IEEE_BINARY64_PROGRAMS` in det/gen.py) and on the
oracle. GnuCOBOL computes a COMPUTE with a float operand through decimals, so `lower` rewrites those two statements
into CALLs of tests/equivalence/faults/ggb64.c, which does the arithmetic in double. It is an owner-stated assumption,
not a z/OS calibration. EPSMPMT only: every other program is returned unchanged, and #4702 still governs its float `**`.

Faithful or refused, never guessed: in EPSMPMT, a COMPUTE holding `**` or ANNUITY that is not one of the two statements
the stub implements, or an operand whose PIC is not the one its layout assumes, is `Unsupported` (the harness's "not
runnable faithfully"). The replaced statement keeps its line count, so the coverage trace and the line numbers hold.
"""

from __future__ import annotations

import re

LAST = 72  # fixed format: columns 8-72 are code, 7 is the indicator
PROGRAMS = frozenset({"EPSMPMT"})  # the det side's IEEE_BINARY64_PROGRAMS
STUB = "ggb64.c"

FLAGS = re.IGNORECASE
_PROGRAM_ID = re.compile(r"\bPROGRAM-ID\.?\s+'?([A-Z0-9#@$-]+)", FLAGS)
_COMPUTE = re.compile(r"\bCOMPUTE\b", FLAGS)
_NEXT_VERB = re.compile(r"\s*(DISPLAY|MOVE|PERFORM|IF|ELSE|END-IF|GOBACK|COMPUTE)\b", FLAGS)
_FLOAT_OP = re.compile(r"\*\*|\bFUNCTION\s+ANNUITY\b|\bANNUITY\s*\(", FLAGS)

# line 125: the payment, as the program writes it (whitespace folded, case folded)
PAYMENT = (
    "COMPUTE EPSPDATA-RETURN-MONTH-PAYMENT = EPSPDATA-PRINCIPLE-DATA * (WS-CALC-INTEREST * "
    "(1 + WS-CALC-INTEREST) ** WS-NUMBER-OF-MONTHS) / (((1 + WS-CALC-INTEREST ) ** WS-NUMBER-OF-MONTHS) - 1)"
)
PAYMENT_CALL = (
    "CALL 'GGB64PAY' USING EPSPDATA-PRINCIPLE-DATA",
    "EPSPDATA-QUOTED-INTEREST-RATE WS-NUMBER-OF-MONTHS",
    "EPSPDATA-RETURN-MONTH-PAYMENT",
)
# line 120: the rate the stub rebuilds from the quoted rate (short HFP, as the port holds it), so it must be this
RATE = "COMPUTE WS-CALC-INTEREST = (EPSPDATA-QUOTED-INTEREST-RATE / 100) / 12"
# line 144: the dead A300-TRY2 statement; it has no period, the DISPLAY verb after it ends it
ANNUITY = "COMPUTE PAYMENT = LOAN * FUNCTION ANNUITY((INTEREST / 12) NUMBER-PERIODS)"
ANNUITY_CALL = ("CALL 'GGB64ANN' USING LOAN INTEREST", "NUMBER-PERIODS PAYMENT")
# the layouts ggb64.c reads; the copybook items (EPSPDATA) are the program's own and are checked by the stub's contract
WS_PICS = {
    "WS-NUMBER-OF-MONTHS": r"PIC\s+9\(9\)V99\s+COMP",
    "WS-CALC-INTEREST": r"COMP-1",
    "LOAN": r"PIC\s+9\(9\)V99",
    "PAYMENT": r"PIC\s+9\(9\)V99",
    "INTEREST": r"PIC\s+9\(9\)V9999",
    "NUMBER-PERIODS": r"PIC\s+999",
}


class Unsupported(Exception):
    """A statement the stub does not implement: the case is not runnable faithfully."""


def _code(line: str) -> str:
    return line[6:LAST] if len(line) > 6 and line[6] not in "*/" else ""


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().upper()


def _statements(lines: list[str]):
    """(first line, last line, folded text, ended by a period) of each COMPUTE: to its period, or to the next verb."""
    i = 0
    while i < len(lines):
        m = _COMPUTE.search(_code(lines[i]))
        if not m:
            i += 1
            continue
        parts, j, period = [], i, False
        while j < len(lines):
            c = _code(lines[j])
            if j > i and _NEXT_VERB.match(c):
                break
            parts.append(c[m.start() :] if j == i else c)
            if c.rstrip().endswith("."):
                period = True
                j += 1
                break
            j += 1
        yield i, j - 1, _fold(" ".join(parts)).rstrip(". "), period
        i = j


def _declared(text: str, name: str) -> bool:
    return bool(re.search(rf"(?<![A-Z0-9-]){re.escape(name)}\s+{WS_PICS[name]}(?![A-Z0-9-])", text, FLAGS))


def lower(program: str) -> str:
    """The program the oracle compiles: unchanged unless it is a ruled program holding the ruled statements."""
    m = _PROGRAM_ID.search(program)
    if not m or m.group(1).upper() not in PROGRAMS:
        return program
    lines = program.split("\n")
    out = list(lines)
    found = 0
    statements = list(_statements(lines))
    for first, last, text, period in statements:
        if not _FLOAT_OP.search(text):
            continue
        call = PAYMENT_CALL if text == PAYMENT else ANNUITY_CALL if text == ANNUITY else None
        if call is None:
            raise Unsupported(
                f"{m.group(1)}: a binary64 COMPUTE the stub does not implement (line {first + 1}): {text}"
            )
        if last - first + 1 < len(call):
            raise Unsupported(f"line {first + 1}: too short for the CALL that replaces it")
        for k in range(first, last + 1):
            out[k] = " " * 11 + call[k - first] if k - first < len(call) else ""
        out[first + len(call) - 1] += "." if period else ""
        found += 1
    if not found:
        raise Unsupported("no ruled binary64 statement found in a program the ruling names")
    if any(t == PAYMENT for _, _, t, _ in statements) and sum(t == RATE for _, _, t, _ in statements) != 1:
        raise Unsupported("the quoted rate is not turned into WS-CALC-INTEREST by the one COMPUTE the stub rebuilds")
    folded = _fold(" ".join(_code(ln) for ln in lines))
    for name, pic in WS_PICS.items():
        if not _declared(folded, name):
            raise Unsupported(f"{name} is not declared as ggb64.c reads it ({pic})")
    return "\n".join(out)
