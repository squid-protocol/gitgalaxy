"""
#4001: what BMS sends for a SEND MAP, and what a RECEIVE MAP delivers -- the harness's own model,
read from the BMS source (DFHMSD / DFHMDI / DFHMDF), for both sides of the CICS crucible.

A program hands BMS its symbolic map: per named field a length (`<f>L`), an attribute byte
(`<f>A`), extended colour and highlight bytes (`<f>C` / `<f>H`, when the mapset has DSATTS)
and data (`<f>O`). The stub runtime records those bytes, CicsTask records the same values, and
`send_map` resolves either into the 3270 fields BMS writes (the crucible's SPEC 6.3):

  attribute  the program's byte, unless MAPONLY, or the byte is X'00', X'80', X'02' or X'82'
             (the null and the input flags a RECEIVE MAP leaves); else, without DATAONLY, the
             DFHMDF ATTRB's byte (ASKIP,NORM when omitted); else none.
  data       the program's, when its first byte is not null (and not MAPONLY); else, without
             DATAONLY, the map's INITIAL; else none.
  colour /   the program's byte when it is not X'00'; else, without DATAONLY, the field's
  highlight  COLOR / HILIGHT, then the map's, then the mapset's; else none.
  omission   under DATAONLY a field BMS sends nothing for is not sent at all.
  cursor     CURSOR(n): offset n; CURSOR alone: the first field whose length is -1 (symbolic
             cursor positioning); otherwise, without DATAONLY, the map's IC field.

Attribute, colour and highlight bytes are compared as the EBCDIC bytes they are: the stub's
DFHBMSCA stand-in holds each constant as its EBCDIC byte, so a program's hex literal, its
DFHBMSCA name and its bit arithmetic all yield the byte a mainframe would hold.

Sources: IBM CICS TS, "BMS macros" (DFHMSD, DFHMDI, DFHMDF: ATTRB, INITIAL, COLOR, HILIGHT,
JUSTIFY, IC, DSATTS); "SEND MAP" (MAPONLY, DATAONLY, CURSOR); "Building the output screen"
(where each value comes from); 3270 Data Stream Programmer's Reference GA23-0059 ("Field
attribute", the attribute byte's graphic encodings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.source_text import read_source

EBCDIC = "cp037"

# GA23-0059: bits 2-7 of an attribute byte -> the graphic EBCDIC byte BMS writes for it.
_GRAPHIC = bytes.fromhex(
    "40C1C2C3C4C5C6C7C8C94A4B4C4D4E4F"
    "50D1D2D3D4D5D6D7D8D95A5B5C5D5E5F"
    "6061E2E3E4E5E6E7E8E96A6B6C6D6E6F"
    "F0F1F2F3F4F5F6F7F8F97A7B7C7D7E7F"
)
# DFHMDF COLOR / HILIGHT -> the extended attribute value (DFHBMSCA: DFHBLUE ... DFHNEUTR, DFHBLINK ...)
COLORS = {"BLUE": 0xF1, "RED": 0xF2, "PINK": 0xF3, "GREEN": 0xF4, "TURQUOISE": 0xF5, "YELLOW": 0xF6,
          "NEUTRAL": 0xF7}  # fmt: skip
HILIGHTS = {"BLINK": 0xF1, "REVERSE": 0xF2, "UNDERLINE": 0xF4}
# Not attributes: the null, and the input flags RECEIVE MAP leaves (DFHBMEOF, DFHBMCUR, DFHBMEC)
NO_ATTRIBUTE = frozenset({0x00, 0x80, 0x02, 0x82})


def attr_byte(attrb: Optional[list[str]]) -> int:
    """The 3270 attribute byte a DFHMDF ATTRB produces. Omitted: (ASKIP,NORM); given without
    ASKIP / PROT / UNPROT: unprotected."""
    words = {a.upper() for a in (attrb if attrb is not None else ["ASKIP", "NORM"])}
    bits = 0
    if "ASKIP" in words:
        bits |= 0x30
    elif "PROT" in words:
        bits |= 0x20
    if "NUM" in words:
        bits |= 0x10
    if "BRT" in words:
        bits |= 0x08
    elif "DRK" in words:
        bits |= 0x0C
    elif "DET" in words:
        bits |= 0x04
    if "FSET" in words:
        bits |= 0x01
    return _GRAPHIC[bits & 0x3F]


# ---- the BMS source ---------------------------------------------------------------------------
@dataclass
class BmsField:
    name: Optional[str]  # None: an unnamed field (a label)
    length: int
    attrb: Optional[list[str]]
    initial: Optional[str]
    color: Optional[str]
    hilight: Optional[str]
    justify: list[str]
    ic: bool

    @property
    def numeric(self) -> bool:
        return "NUM" in {a.upper() for a in self.attrb or []}


@dataclass
class BmsMap:
    name: str
    mapset: str
    color: Optional[str] = None
    hilight: Optional[str] = None
    mapset_color: Optional[str] = None
    mapset_hilight: Optional[str] = None
    dsatts: frozenset[str] = frozenset()
    fields: list[BmsField] = field(default_factory=list)

    def named(self) -> list[BmsField]:
        return [f for f in self.fields if f.name]


def _statements(text: str) -> list[tuple[str, str, str]]:
    """(label, operation, operands) per assembler statement: `*` lines are comments, a non-blank
    column 72 continues the statement on the next line from column 16."""
    out: list[tuple[str, str, str]] = []
    buf: Optional[str] = None
    for raw in text.splitlines():
        if buf is None and (raw.startswith("*") or not raw.strip()):
            continue
        body, cont = raw[:71], len(raw) > 71 and raw[71] != " "
        buf = body.rstrip() if buf is None else buf + body[15:].strip()
        if cont:
            continue
        label = (
            buf[: buf.index(" ")] if not buf.startswith(" ") and " " in buf else ("" if buf.startswith(" ") else buf)
        )
        rest = buf[len(label) :].strip()
        op, _, operands = rest.partition(" ")
        out.append((label.strip(), op.upper(), _operand_field(operands.strip())))
        buf = None
    return out


def _operand_field(text: str) -> str:
    """The operand field alone: it ends at the first blank outside quotes and parentheses."""
    depth, quoted = 0, False
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == " ":
            return text[:i]
    return text


def _operands(text: str) -> dict[str, str]:
    """KEY=value pairs, split at the commas outside quotes and parentheses."""
    parts, depth, quoted, start = [], 0, False, 0
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == ",":
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    out = {}
    for p in parts:
        key, eq, value = p.partition("=")
        if eq:
            out[key.strip().upper()] = value.strip()
    return out


def _list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [v.strip().upper() for v in value.strip().strip("()").split(",") if v.strip()]


def _first(value: Optional[str]) -> Optional[str]:
    return next(iter(_list(value)), None)


def _quoted(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'").replace("&&", "&")
    return v


def parse_bms(text: str) -> dict[str, BmsMap]:
    """Every map of a BMS source, by map name."""
    maps: dict[str, BmsMap] = {}
    mapset, ms_ops = "", {}
    current: Optional[BmsMap] = None
    for label, op, operands in _statements(text):
        ops = _operands(operands)
        if op == "DFHMSD":
            if ops.get("TYPE", "").upper() != "FINAL":
                mapset, ms_ops = label.upper(), ops
            continue
        if op == "DFHMDI":
            current = BmsMap(label.upper(), mapset, color=_first(ops.get("COLOR")), hilight=_first(ops.get("HILIGHT")),
                             mapset_color=_first(ms_ops.get("COLOR")), mapset_hilight=_first(ms_ops.get("HILIGHT")),
                             dsatts=frozenset(_list(ms_ops.get("DSATTS"))))  # fmt: skip
            maps[current.name] = current
            continue
        if op == "DFHMDF" and current is not None:
            attrb = _list(ops.get("ATTRB")) if "ATTRB" in ops else None
            initial = _quoted(ops.get("INITIAL"))
            length = int(ops["LENGTH"]) if ops.get("LENGTH", "").isdigit() else len(initial or "")
            current.fields.append(BmsField(
                name=label.upper() or None, length=length, attrb=attrb, initial=initial,
                color=_first(ops.get("COLOR")), hilight=_first(ops.get("HILIGHT")),
                justify=_list(ops.get("JUSTIFY")), ic="IC" in (attrb or [])))  # fmt: skip
    return maps


def load_maps(paths: list[Path]) -> dict[str, BmsMap]:
    out: dict[str, BmsMap] = {}
    for p in paths:
        out.update(parse_bms(read_source(p).text))
    return out


# ---- SEND MAP -----------------------------------------------------------------------------------
@dataclass
class ProgramField:
    """What the program left in one field of its symbolic map. Bytes are EBCDIC; None = X'00'."""

    length: Optional[int] = None  # <f>L: -1 asks for the cursor (symbolic cursor positioning)
    attr: Optional[int] = None
    color: Optional[int] = None
    hilight: Optional[int] = None
    data: Optional[bytes] = None  # <f>O


def ebcdic(text: str) -> bytes:
    """Text as the EBCDIC bytes a 3270 field holds; a character CCSID 037 cannot hold becomes
    X'3F' (SUB), as a code-page conversion writes it -- never dropped."""
    return b"".join(ch.encode(EBCDIC) if ord(ch) < 256 else b"\x3f" for ch in text)


def _hex(b: Optional[int]) -> Optional[str]:
    return None if b is None else f"{b:02X}"


def _extended(kind: str, prog: Optional[int], f: BmsField, m: BmsMap, dataonly: bool) -> tuple[Optional[str], str]:
    table = COLORS if kind == "color" else HILIGHTS
    if prog not in (None, 0x00):
        return _hex(prog), "program"
    if dataonly:
        return None, "none"
    for name in (getattr(f, kind), getattr(m, kind), getattr(m, f"mapset_{kind}")):
        if name:
            return _hex(table.get(name)), "map" if table.get(name) is not None else "none"
    return None, "none"


def send_map(m: BmsMap, program: Optional[dict[str, ProgramField]], options: list[str],
             cursor: Any = None) -> tuple[dict[str, dict[str, Any]], Any]:  # fmt: skip
    """The fields BMS sends for one SEND MAP (SPEC 6.3), and where it puts the cursor (a field
    name, {"offset": n}, or None). `program` is None under MAPONLY (no FROM area); `cursor` is
    CURSOR's value, or None when the option has none."""
    opts = {o.upper() for o in options}
    maponly, dataonly = "MAPONLY" in opts or program is None, "DATAONLY" in opts
    ext = {"COLOR", "HILIGHT"} & set(m.dsatts)
    out: dict[str, dict[str, Any]] = {}
    for f in m.named():
        p = (program or {}).get(f.name or "") or ProgramField()
        if not maponly and p.attr is not None and p.attr not in NO_ATTRIBUTE:
            attr, attr_from = _hex(p.attr), "program"
        elif not dataonly:
            attr, attr_from = _hex(attr_byte(f.attrb)), "map"
        else:
            attr, attr_from = None, "none"
        if not maponly and p.data and p.data[0] != 0x00:
            data, data_from = p.data, "program"
        elif not dataonly and f.initial is not None:
            data, data_from = f.initial.encode(EBCDIC), "map"
        else:
            data, data_from = None, "none"
        fo: dict[str, Any] = {"attr": attr, "attr_from": attr_from, "data": data, "data_from": data_from}
        for kind in ("color", "hilight"):
            if kind.upper() in ext:
                fo[kind], fo[f"{kind}_from"] = _extended(kind, None if maponly else getattr(p, kind), f, m, dataonly)
        sent = any(fo[k] is not None for k in ("attr", "data", "color", "hilight") if k in fo)
        if dataonly and not sent:
            continue  # BMS sends nothing for it: the field is not in the data stream at all
        out[f.name or ""] = fo
    where: Any = None
    if "CURSOR" in opts and cursor is not None:
        where = {"offset": int(cursor)}
    elif "CURSOR" in opts and not maponly:
        where = next((f.name for f in m.named() if ((program or {}).get(f.name or "") or ProgramField()).length == -1),
                     None)  # fmt: skip
    if where is None and not dataonly:
        where = next((f.name for f in m.fields if f.ic and f.name), None)
    return out, where


# ---- RECEIVE MAP --------------------------------------------------------------------------------
def received_value(f: BmsField, typed: str) -> str:
    """A transmitted field as RECEIVE MAP puts it in `<f>I` (DFHMDF JUSTIFY): left-justified and
    blank-padded, or -- JUSTIFY=RIGHT, or a NUM field -- right-justified and zero-filled."""
    text = typed[: f.length]
    right = "RIGHT" in f.justify or (f.numeric and "LEFT" not in f.justify)
    pad = "0" if ("ZERO" in f.justify or (right and "BLANK" not in f.justify)) else " "
    return text.rjust(f.length, pad) if right else text.ljust(f.length, pad)
