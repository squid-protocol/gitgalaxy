"""IBM hexadecimal floating point (HFP) for COMP-1 / COMP-2 (#4271, register C6): the translator's model.

The same rules as the runtime's `cobolrt/Hfp.java`, written independently over exact `Fraction`s: the translator
encodes a float item's VALUE with it, and tests/cobol_mainframe/test_det_hfp.py checks the runtime against it.

Format (z/Architecture Principles of Operation, SA22-7832, "Hexadecimal-Floating-Point Number Representation"): a sign
bit, a 7-bit characteristic (the exponent of 16, excess 64) and a fraction of 6 (short, COMP-1) or 14 (long, COMP-2)
hexadecimal digits, big-endian; the value is +/- 0.fraction x 16 ** (characteristic - 64). Zero is all zero bytes.

- ADD / SUBTRACT NORMALIZED: one hexadecimal guard digit in the alignment, then normalized and truncated. MULTIPLY
  and DIVIDE: the exact result truncated. LOAD ROUNDED (long to short): a one added at the first discarded bit.
- Fixed point to float: the exact value truncated to long, then rounded to short for COMP-1 (ASSUMED: IBM does not
  document the conversion it generates).
- Float to fixed point: rounded in the receiver's low-order position, at most 9 (COMP-1) / 18 (COMP-2) significant
  digits (Enterprise COBOL 6.4 Programming Guide, SC27-8714-03, "Conversions and precision").
- DISPLAY: as external floating point -.9(8)E-99 (COMP-1) / -.9(17)E-99 (COMP-2) (6.4 Language Reference, DISPLAY).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from fractions import Fraction

SHORT, LONG = 6, 14
_EXACT = Context(prec=400)  # every HFP value's decimal expansion fits (16 ** -79 has 316 digits)


class HfpRange(ArithmeticError):
    """An exponent overflow or underflow: refused by name (z/OS's result depends on the program mask)."""


def _chop(v: Fraction, digits: int) -> tuple[bool, int, int] | None:
    """(neg, e, f): |v| truncated to `digits` hex digits, f x 16 ** (e - digits); None for zero."""
    if v == 0:
        return None
    a = abs(v)
    e = 0
    while a >= Fraction(16) ** e:
        e += 1
    while a < Fraction(16) ** (e - 1):
        e -= 1
    f = int(a * Fraction(16) ** (digits - e))  # floor: a > 0
    if e > 63 or e < -64:
        raise HfpRange(f"HFP exponent {'overflow' if e > 63 else 'underflow'}")
    return v < 0, e, f


def _val(neg: bool, e: int, f: int, digits: int) -> Fraction:
    v = f * Fraction(16) ** (e - digits)
    return -v if neg else v


def chop(v: Fraction, digits: int) -> Fraction:
    h = _chop(Fraction(v), digits)
    return Fraction(0) if h is None else _val(*h, digits)


def of(v) -> Fraction:
    """A fixed-point value converted to long HFP (truncated)."""
    return chop(Fraction(v), LONG)


def to_short(v: Fraction) -> Fraction:
    """LOAD ROUNDED: long to short, half away from zero at the first discarded bit."""
    h = _chop(Fraction(v), LONG)
    if h is None:
        return Fraction(0)
    neg, e, f = h
    f = (f + (1 << (4 * (LONG - SHORT) - 1))) >> (4 * (LONG - SHORT))
    if f == 16**SHORT:
        f, e = 16 ** (SHORT - 1), e + 1
    if e > 63:
        raise HfpRange("HFP exponent overflow")
    return _val(neg, e, f, SHORT)


def for_item(v, short: bool) -> Fraction:
    return to_short(of(v)) if short else of(v)


def _parts(v: Fraction, digits: int) -> tuple[bool, int, int] | None:
    h = _chop(v, digits)
    if h is not None and _val(*h, digits) != v:
        raise ValueError(f"not an HFP value of {digits} digits: {v}")
    return h


def add(a: Fraction, b: Fraction, long: bool) -> Fraction:
    d = LONG if long else SHORT
    x, y = _parts(Fraction(a), d), _parts(Fraction(b), d)
    if x is None or y is None:
        return Fraction(b) if x is None else Fraction(a)
    if x[1] < y[1]:
        x, y = y, x
    fx = x[2] * 16
    fy = (y[2] * 16) >> (4 * (x[1] - y[1]))  # one guard digit: the digits shifted past it are lost
    s = (-fx if x[0] else fx) + (-fy if y[0] else fy)
    if s == 0:
        return Fraction(0)
    neg, s, e = s < 0, abs(s), x[1]
    if s >= 16 ** (d + 1):
        s, e = s >> 4, e + 1
    while s < 16**d:
        s, e = s << 4, e - 1
    if e > 63 or e < -64:
        raise HfpRange("HFP exponent out of range")
    return _val(neg, e, s >> 4, d)


def sub(a: Fraction, b: Fraction, long: bool) -> Fraction:
    return add(a, -Fraction(b), long)


def mul(a: Fraction, b: Fraction, long: bool) -> Fraction:
    d = LONG if long else SHORT
    _parts(Fraction(a), d), _parts(Fraction(b), d)
    return chop(Fraction(a) * Fraction(b), d)


def div(a: Fraction, b: Fraction, long: bool) -> Fraction:
    d = LONG if long else SHORT
    _parts(Fraction(a), d), _parts(Fraction(b), d)
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return chop(Fraction(a) / Fraction(b), d)


def _dec(v: Fraction) -> Decimal:
    return _EXACT.divide(Decimal(v.numerator), Decimal(v.denominator))  # exact: the denominator is a power of 2


def to_fixed(v: Fraction, scale: int, significant: int) -> Decimal:
    """Rounded half away from zero at `scale`, at most `significant` significant digits."""
    d = _dec(Fraction(v))
    q = Decimal(1).scaleb(-scale)
    with localcontext(_EXACT):
        r = d.quantize(q, rounding=ROUND_HALF_UP)
        if r != 0 and len(str(abs(int(r.scaleb(scale))))) > significant:
            s = Context(prec=significant, rounding=ROUND_HALF_UP).plus(d)
            r = s.quantize(q, rounding=ROUND_HALF_UP)
    return r


def display(v: Fraction, long: bool) -> str:
    n = 17 if long else 8
    if v == 0:
        return " ." + "0" * n + "E 00"
    a = _dec(abs(Fraction(v)))
    k = a.adjusted() + 1  # a = 0.ddd x 10 ** k
    with localcontext(_EXACT):
        m = a.scaleb(-k).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP)
        if m >= 1:
            m, k = (m / 10).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP), k + 1
        digits = str(int(m.scaleb(n))).rjust(n, "0")
    return ("-" if v < 0 else " ") + "." + digits + "E" + ("-" if k < 0 else " ") + f"{abs(k):02d}"


def encode(v: Fraction, short: bool) -> bytes:
    """The item's bytes for a value of its precision (already for_item)."""
    d = SHORT if short else LONG
    h = _parts(Fraction(v), d)
    if h is None:
        return bytes(4 if short else 8)
    neg, e, f = h
    return bytes([(0x80 if neg else 0) | (e + 64)]) + f.to_bytes(d // 2, "big")


def decode(b: bytes) -> Fraction:
    d = SHORT if len(b) == 4 else LONG
    f = int.from_bytes(b[1:], "big")
    if f == 0:
        return Fraction(0)
    return _val(bool(b[0] & 0x80), (b[0] & 0x7F) - 64, f, d)
