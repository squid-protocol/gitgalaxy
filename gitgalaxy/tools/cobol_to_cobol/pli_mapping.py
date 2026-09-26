# ==============================================================================
# GitGalaxy: PL/I storage mapping (#3720)
#
# The width and position of every item of a PL/I structure, from the DECLARE facts
# in record_data (#3250: `usage` = the data type as written, `pic`, `occurs_max` =
# the dimension, `redefines` = DEFINED, `attributes` = the full attribute text).
#
# Elements (IBM Enterprise PL/I, defaults AND the LP(32) pointer size):
#   CHARACTER(n)             n bytes, byte-aligned; VARYING adds a 2-byte prefix
#   BIT(n)                   n BITS, bit-aligned (UNALIGNED, the default for strings);
#                            ALIGNED: ceil(n/8) bytes on a byte boundary
#   PICTURE '...'            one byte per character position (V, K and F(n) take none;
#                            CR / DB two)
#   FIXED DECIMAL(p,q)       p/2+1 bytes, byte-aligned (FIXED alone is DECIMAL(5,0))
#   FIXED BINARY(p)          p <= 7: 1 byte, <= 15: 2, <= 31: 4, else 8 (default p 15);
#                            ALIGNED (the default for arithmetic data) on its own size
#   FLOAT DECIMAL(p) / BINARY(p)  4 / 8 / 16 bytes (p <= 6 / 16 dec, 21 / 53 bin), ALIGNED
#                            on its size (doubleword at most)
#   POINTER / OFFSET / HANDLE  4 bytes, fullword-aligned
#   ENTRY / LABEL variable   8 bytes, fullword-aligned
# ALIGNED / UNALIGNED on a structure is inherited by its elements unless overridden.
# UNALIGNED data is byte-aligned, except bit strings (bit-aligned).
#
# Structures are mapped as IBM's structure-mapping rules describe: the deepest minor
# structures first, each a unit made by pairing its elements left to right. Of a pair,
# the second element goes at the first position after the first element that meets
# its alignment, and the first element is moved as far toward it as its own alignment
# allows -- so padding falls before the unit rather than inside it. A unit keeps the
# most stringent alignment of its elements and the offset of its start from that
# boundary. An array's element stride is its width rounded up to its alignment.
#
# Unknown (None) for what is not modelled: an unresolved LIKE, AREA, FILE / FORMAT data, a
# REFER extent (variable), an element with no data attributes. DEFINED items overlay
# their base and are not laid out (as COBOL's REDEFINES).
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BIT, BYTE, HALF, FULL, DOUBLE = 1, 8, 16, 32, 64  # alignment boundaries, in bits


@dataclass
class Unit:
    """A mapped item: `length` bits, alignment `align` bits, starting `residue` bits after
    such a boundary; `at` maps id(item) of every item inside to its bit offset from the
    unit's start (the unit's own item included, at 0)."""

    length: int
    align: int
    residue: int = 0
    at: dict = field(default_factory=dict)


def pic_positions(pic: str) -> int | None:
    """Storage bytes of a PL/I picture: one per character position; V, K and F(n) take none,
    CR / DB two. `(4)9` repeats."""
    p = pic.upper().strip("'")
    p = re.sub(r"F\(\s*[+-]?\d+\s*\)", "", p)  # scaling factor
    total = 0
    i = 0
    while i < len(p):
        m = re.match(r"\(\s*(\d+)\s*\)", p[i:])  # `( 4)9` repeats as `(4)9`
        rep = 1
        if m:
            rep = int(m.group(1))
            i += m.end()
            if i >= len(p):
                return None
        if p.startswith(("CR", "DB"), i):
            total += 2 * rep
            i += 2
            continue
        ch = p[i]
        i += 1
        if ch in "VK":
            continue
        if ch in "9XAZ*Y$+-S.,/B0T I R E":
            total += rep
        else:
            return None
    return total


def element(usage: str | None, pic: str | None, attributes: str, aligned: bool) -> tuple[int, int] | None:
    """(length in bits, alignment in bits) of one elementary PL/I item, or None when unknown."""
    text = f"{usage or ''} {attributes or ''}".upper()
    if pic:
        n = pic_positions(pic)
        return None if n is None else (8 * n, BYTE)
    if re.search(r"\b(?:LIKE|AREA|FILE|FORMAT|TASK|EVENT)\b", text):
        return None
    if re.search(r"\b(?:ENTRY|LABEL)\b", text):  # an entry / label VARIABLE: two addresses
        return (64, FULL if aligned else BYTE)
    if re.search(r"\b(?:POINTER|PTR|OFFSET|HANDLE)\b", text):
        return (32, FULL if aligned else BYTE)
    m = re.search(r"\bCHAR(?:ACTER)?\s*\(\s*(\d+)\s*\)", text)
    if m:
        n = int(m.group(1))
        varying = re.search(r"\bVAR(?:YING)?\b", text) is not None
        return (8 * n + (16 if varying else 0), HALF if aligned and varying else BYTE)
    m = re.search(r"\b(?:WIDECHAR|WCHAR|GRAPHIC)\s*\(\s*(\d+)\s*\)", text)
    if m:
        return (16 * int(m.group(1)), BYTE)
    m = re.search(r"\bBIT\s*\(\s*(\d+)\s*\)", text)
    if m:
        n = int(m.group(1))
        return (8 * ((n + 7) // 8), BYTE) if aligned else (n, BIT)
    fixed = re.search(r"\bFIXED\b", text) is not None
    floating = re.search(r"\bFLOAT\b", text) is not None
    binary = re.search(r"\bBIN(?:ARY)?\b", text) is not None
    decimal = re.search(r"\bDEC(?:IMAL)?\b", text) is not None
    if not (fixed or floating or binary or decimal):
        return None
    prec = re.search(r"\b(?:FIXED|FLOAT|BIN(?:ARY)?|DEC(?:IMAL)?)\s*\(\s*(\d+)", text)
    p = int(prec.group(1)) if prec else None
    # PL/I's defaults: FIXED without a base is DECIMAL; DECIMAL or BINARY without FIXED is FLOAT.
    if fixed and binary:
        p = p or 15
        size = 8 if p <= 7 else 16 if p <= 15 else 32 if p <= 31 else 64
        return (size, size if aligned else BYTE)
    if fixed:
        p = p or 5
        return (8 * (p // 2 + 1), BYTE)
    if binary:
        p = p or 21
        size = 32 if p <= 21 else 64 if p <= 53 else 128
    else:
        p = p or 6
        size = 32 if p <= 6 else 64 if p <= 16 else 128
    return (size, min(size, DOUBLE) if aligned else BYTE)


def item_class(usage: str | None, pic: str | None, attributes: str) -> str:
    """galaxy_ir's coarse storage class of a PL/I item: X string, 9 numeric picture, P fixed
    decimal, B fixed binary, F float, A locator, T bit string, N wide / graphic; `?` unknown."""
    text = f"{usage or ''} {attributes or ''}".upper()
    if pic:
        return "X" if re.search(r"[XA]", pic.upper()) else "9"
    for cls, pat in (("A", r"\b(?:POINTER|PTR|OFFSET|HANDLE)\b"), ("N", r"\b(?:WIDECHAR|WCHAR|GRAPHIC)\b"),
                     ("X", r"\bCHAR(?:ACTER)?\b"), ("T", r"\bBIT\b"), ("F", r"\bFLOAT\b")):  # fmt: skip
        if re.search(pat, text):
            return cls
    if re.search(r"\bFIXED\b", text):
        return "B" if re.search(r"\bBIN(?:ARY)?\b", text) else "P"
    if re.search(r"\bBIN(?:ARY)?\b|\bDEC(?:IMAL)?\b", text):
        return "F"
    return "?"


def _aligned(attributes: str, inherited: bool | None) -> bool | None:
    """The item's own ALIGNED / UNALIGNED, else what its structure passes down (None: neither says)."""
    a = (attributes or "").upper()
    if re.search(r"\bUNALIGNED\b|\bUNAL\b", a):
        return False
    if re.search(r"\bALIGNED\b", a):
        return True
    return inherited


def _string_or_pic(usage: str | None, pic: str | None, attributes: str) -> bool:
    text = f"{usage or ''} {attributes or ''}".upper()
    return bool(pic) or re.search(r"\b(?:CHAR(?:ACTER)?|BIT|WIDECHAR|WCHAR|GRAPHIC)\s*\(", text) is not None


def pair(first: Unit, second: Unit) -> tuple[Unit, int, int]:
    """IBM's pairing: (the combined unit, first's offset in it, second's offset in it), in bits."""
    m = max(first.align, second.align)
    best = None
    for p1 in range(first.residue, m, first.align):  # every place `first` can start within the larger boundary
        p2 = p1 + first.length
        while (p2 - second.residue) % second.align:
            p2 += 1
        # move `first` as far toward `second` as its own alignment allows
        shifted = p2 - first.length
        shifted -= (shifted - first.residue) % first.align
        pad = p2 - (shifted + first.length)
        if best is None or pad < best[0] or (pad == best[0] and shifted < best[1]):
            best = (pad, shifted, p2)
    if best is None:  # unreachable: a residue is below its alignment, so the range is never empty
        raise ValueError(f"no placement for a unit of residue {first.residue}")
    _, p1, p2 = best
    start = p1
    unit = Unit(p2 + second.length - start, m, start % m)
    for k, v in first.at.items():
        unit.at[k] = v + (p1 - start)
    for k, v in second.at.items():
        unit.at[k] = v + (p2 - start)
    return unit, p1 - start, p2 - start


def map_item(it: Any, children: dict, inherited_aligned: bool | None = None, depth: int = 0) -> Unit | None:
    """The Unit of a PL/I item and everything under it; `children` maps id(item) -> its kids
    (DEFINED ones left out by the caller). None when any width inside is unknown.
    `inherited_aligned` is the ALIGNED (True) / UNALIGNED (False) an enclosing structure
    declares, None when none does: ALIGNED on a structure aligns its strings too."""
    attrs = it.attributes or ""
    kids = children.get(id(it), [])
    times = it.occurs_max or 1
    if kids:
        aligned = _aligned(attrs, inherited_aligned)
        unit: Unit | None = None
        for kid in kids:
            ku = map_item(kid, children, aligned, depth + 1)
            if ku is None:
                return None
            unit = ku if unit is None else pair(unit, ku)[0]
        if unit is None:
            return None
        unit.at = {**unit.at, id(it): 0}
    else:
        # Strings and pictures default to UNALIGNED, arithmetic and locators to ALIGNED --
        # unless the item or an enclosing structure says otherwise.
        said = _aligned(attrs, inherited_aligned)
        aligned = said if said is not None else not _string_or_pic(it.usage, it.pic, attrs)
        el = element(it.usage, it.pic, attrs, aligned)
        if el is None:
            return None
        unit = Unit(el[0], el[1], 0, {id(it): 0})
    if times > 1:
        stride = unit.length + (-unit.length) % unit.align if unit.align > 1 else unit.length
        unit = Unit(stride * (times - 1) + unit.length, unit.align, unit.residue, unit.at)
    return unit


def layout(root: Any, children: dict) -> dict | None:
    """{id(item): (bit offset from the record's start, length in bits)} for every item of the
    PL/I record `root`, or None when a width inside is unknown."""
    unit = map_item(root, children)
    if unit is None:
        return None
    lengths: dict = {}

    def collect(it: Any, inherited: bool | None) -> None:
        kids = children.get(id(it), [])
        aligned = _aligned(it.attributes or "", inherited)
        for kid in kids:
            collect(kid, aligned)
        u = map_item(it, children, inherited)
        lengths[id(it)] = u.length if u is not None else None

    collect(root, None)
    return {k: (off, lengths.get(k)) for k, off in unit.at.items()}
