"""The DATA DIVISION as storage: every item's offset, length, category and initial bytes.

Parsed with tree-sitter's COBOL grammar from the expanded source (det.source), laid out by the IBM Enterprise COBOL
storage rules, and the initial image computed from the VALUE clauses the way GnuCOBOL (-std=ibm -fsign=EBCDIC, the
equivalence harness's oracle) initialises storage. tests/cobol_mainframe/test_det_layout.py checks the image of every
WORKING-STORAGE record against GnuCOBOL's own bytes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det.source import Line, as_fixed

POSITIVE = "{ABCDEFGHI"  # overpunched +0..+9 (-fsign=EBCDIC, ASCII data)
NEGATIVE = "}JKLMNOPQR"


class LayoutError(Exception):
    pass


@dataclass
class Item:
    level: int
    name: str
    section: str  # FILE | WORKING-STORAGE | LOCAL-STORAGE | LINKAGE
    fd: str | None = None
    pic: str | None = None
    usage: str = "DISPLAY"  # DISPLAY | BINARY | PACKED | COMP-5 | COMP-1 | COMP-2 | POINTER | INDEX
    occurs: int = 1
    occurs_min: int | None = None
    depending: str | None = None
    redefines: str | None = None
    values: list = field(default_factory=list)  # literal values (88: several, ranges as (lo, hi))
    sign_leading: bool = False
    sign_separate: bool = False
    justified: bool = False
    blank_when_zero: bool = False
    children: list = field(default_factory=list)
    conditions: list = field(default_factory=list)  # its 88s
    parent: Item | None = None
    line: int = 0
    # computed
    offset: int = 0  # within its 01 record
    size: int = 0  # one occurrence
    record: Item | None = None  # its 01 / 77

    # ---- the PICTURE ------------------------------------------------------------------------------------------
    def picture(self) -> str:
        """The PICTURE with repetitions expanded: S9(3)V99 -> S999V99."""
        return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), (self.pic or "").upper())

    @property
    def category(self) -> str:
        if self.usage in ("COMP-1", "COMP-2"):
            return "FLOAT"
        if self.usage in ("POINTER", "INDEX"):
            return self.usage
        if self.pic is None:
            return "GROUP"
        p = self.picture()
        if set(p) <= set("9SVP"):
            return "NUMERIC"
        if set(p) <= set("A"):
            return "ALPHABETIC"
        if set(p) <= set("XA9"):
            return "ALPHANUMERIC"
        if set(p) & set("Z*+-CRDB.,$") or ("9" in p and set(p) & set("B0/")):
            return "NUMERIC-EDITED" if not set(p) & set("XA") else "ALPHANUMERIC-EDITED"
        return "ALPHANUMERIC-EDITED"

    @property
    def digits(self) -> int:
        return sum(1 for c in self.picture() if c in "9P") if self.category in ("NUMERIC", "NUMERIC-EDITED") else 0

    @property
    def scale(self) -> int:
        p = self.picture()
        if self.category == "NUMERIC":
            return len(p.split("V", 1)[1]) if "V" in p else -sum(1 for c in p if c == "P")
        if self.category == "NUMERIC-EDITED":
            dp = p.find(".") if "." in p else p.find("V")
            return sum(1 for c in p[dp + 1 :] if c in "9Z*") if dp >= 0 else 0
        return 0

    @property
    def signed(self) -> bool:
        return self.category == "NUMERIC" and "S" in self.picture()

    def elementary_size(self) -> int:
        cat, p = self.category, self.picture()
        if cat == "FLOAT":
            return 4 if self.usage == "COMP-1" else 8
        if cat == "POINTER":
            return 8
        if cat == "INDEX":
            return 4
        if cat == "NUMERIC":
            d = self.digits - sum(1 for c in p if c == "P")
            if self.usage == "PACKED":
                return d // 2 + 1
            if self.usage in ("BINARY", "COMP-5"):
                return 2 if d <= 4 else 4 if d <= 9 else 8
            return d + (1 if self.sign_separate and self.signed else 0)
        # edited / alphanumeric: every position except V counts; CR / DB are two
        return len(p.replace("V", ""))

    @property
    def stride(self) -> int:
        return self.size

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


# ---- parsing -----------------------------------------------------------------------------------------------------
def _parser():
    from tree_sitter_language_pack import get_parser

    return get_parser("cobol")


def _txt(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("latin-1")


_SECTIONS = {"file_section": "FILE", "working_storage_section": "WORKING-STORAGE",
             "local_storage_section": "LOCAL-STORAGE", "linkage_section": "LINKAGE"}  # fmt: skip
_USAGE = {"COMP": "BINARY", "COMP_4": "BINARY", "BINARY": "BINARY", "COMPUTATIONAL": "BINARY",
          "COMPUTATIONAL_4": "BINARY", "COMP_3": "PACKED", "COMPUTATIONAL_3": "PACKED", "PACKED_DECIMAL": "PACKED",
          "COMP_5": "COMP-5", "COMPUTATIONAL_5": "COMP-5", "COMP_1": "COMP-1", "COMPUTATIONAL_1": "COMP-1",
          "COMP_2": "COMP-2", "COMPUTATIONAL_2": "COMP-2", "POINTER": "POINTER", "INDEX": "INDEX",
          "DISPLAY": "DISPLAY"}  # fmt: skip


def _data_only(lines: list[Line]) -> list[Line]:
    """The lines the record parser needs, others blanked (kept, so each item keeps its line): the IDENTIFICATION
    DIVISION's paragraphs after PROGRAM-ID (REMARKS, DATE-COMPILED ... -- obsolete, free text), EXEC SQL blocks
    left in the DATA DIVISION (DECLARE CURSOR / TABLE: no storage; an INCLUDE was expanded as a COPY), and a
    section header with nothing under it (an empty LINKAGE SECTION)."""
    out = [Line(ln.text, ln.file, ln.line) for ln in lines]
    in_id = False
    want_name = False  # PROGRAM-ID. with its name on a later line
    for ln in out:
        t = ln.text.strip().upper()
        if re.match(r"(IDENTIFICATION|ID)\s+DIVISION\b", t):
            in_id = True
            continue
        if re.match(r"(ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", t):
            in_id = False
        if re.match(r"PROCEDURE\s+DIVISION\b", t):
            break
        if in_id and re.match(r"PROGRAM-ID\b", t):
            want_name = not re.sub(r"^PROGRAM-ID\.?", "", t).strip()
            continue
        if in_id and want_name and t:
            want_name = False
            continue
        if in_id:
            ln.text = ""
    k = 0
    while k < len(out):
        t = out[k].text.strip().upper()
        if re.match(r"PROCEDURE\s+DIVISION\b", t):
            break
        if re.match(r"EXEC\s+SQL\b", t):
            while k < len(out):
                done = re.search(r"\bEND-EXEC\b", out[k].text, re.I)
                out[k].text = ""
                k += 1
                if done:
                    break
            continue
        if re.match(r"[A-Z0-9-]+\s+SECTION\s*\.$", t):
            nxt = next((x.text.strip().upper() for x in out[k + 1 :] if x.text.strip()), "")
            if re.match(r"([A-Z0-9-]+\s+SECTION|[A-Z]+\s+DIVISION)\b", nxt):
                out[k].text = ""
        k += 1
    return out


def parse(lines: list[Line]) -> list[Item]:
    """The 01 / 77 records of the DATA DIVISION, each a tree of Items."""
    text = as_fixed(_data_only(lines))
    # the PROCEDURE DIVISION is not needed (and EXEC blocks there are not this grammar's): stop before it
    m = re.search(r"^ {7}\s*PROCEDURE\s+DIVISION\b", text, re.I | re.M)
    head = text[: m.start()] if m else text
    src = (head + "       PROCEDURE DIVISION.\n           GOBACK.\n").encode("latin-1")
    tree = _parser().parse(src)
    records: list[Item] = []
    errors = []

    def visit(node, section: str | None, fd: str | None):
        if node.type == "ERROR":
            errors.append(node.start_point[0] + 1)
            return
        if node.type in _SECTIONS:
            section = _SECTIONS[node.type]
        if node.type == "file_description":
            entry = next((c for c in node.children if c.type == "file_description_entry"), None)
            fd = _txt(entry, src).split()[0].upper().rstrip(".") if entry else None
        if node.type == "data_description":
            if node.has_error:  # #4411: an ERROR / MISSING inside an entry: its clauses are not what was read
                errors.append(node.start_point[0] + 1)
                return
            records_append(node, section, fd)
            return
        for c in node.children:
            visit(c, section, fd)

    stack: list[Item] = []

    def records_append(node, section, fd):
        it = _item(node, src, section or "?", fd)
        it.line = node.start_point[0] + 1
        if it.level == 88:
            if stack:
                stack[-1].conditions.append(it)
                it.parent = stack[-1]
            return
        if it.level == 66:
            return  # RENAMES: not laid out (none in the corpora this runs on)
        if it.level in (1, 77):
            stack.clear()
            records.append(it)
            stack.append(it)
            return
        while stack and stack[-1].level >= it.level:
            stack.pop()
        if not stack:
            raise LayoutError(f"line {it.line}: level {it.level} {it.name} has no 01 above it")
        it.parent = stack[-1]
        stack[-1].children.append(it)
        stack.append(it)

    visit(tree.root_node, None, None)
    if errors:
        raise LayoutError(f"DATA DIVISION does not parse near expanded line(s) {errors[:5]}")
    for r in records:
        _inherit_usage(r, None)
        layout(r)
    # an 01 REDEFINES another 01 of its section shares that record's storage
    by_name: dict[tuple[str, str], Item] = {}
    for r in records:
        if r.redefines and r.level == 1:
            target = by_name.get((r.section, r.redefines))
            if target is None:
                raise LayoutError(f"line {r.line}: 01 {r.name} REDEFINES {r.redefines}, no 01 of that name before it")
            r.record = target.record or target
        by_name[(r.section, r.name)] = r
    return records


def _item(node, src: bytes, section: str, fd: str | None) -> Item:
    level = name = None
    it = Item(level=0, name="", section=section, fd=fd)
    for c in node.children:
        t = c.type
        if t == "level_number":
            level = int(_txt(c, src))
        elif t == "entry_name":
            name = _txt(c, src).upper()
        elif t == "picture_clause":
            pic = next((g for g in c.children if g.type.startswith("picture")), c)
            it.pic = _txt(pic, src).upper().rstrip(".")
        elif t == "usage_clause":
            kinds = [g.type for g in c.children if g.type.upper() in _USAGE]
            if kinds:
                it.usage = _USAGE[kinds[0].upper()]
        elif t == "occurs_clause":
            ints = [int(_txt(g, src)) for g in c.children if g.type == "integer"]
            it.occurs = ints[-1] if ints else 1
            it.occurs_min = ints[0] if len(ints) > 1 else None
            dep = next((g for g in c.children if g.type == "qualified_word"), None)
            it.depending = _txt(dep, src).upper() if dep else None
        elif t == "redefines_clause":
            it.redefines = _txt(c.children[-1], src).upper()
        elif t == "value_clause":
            it.values = [_value(v, src) for v in c.children if v.type == "value_item"]
        elif t == "sign_clause":
            words = {g.type for g in c.children}
            it.sign_leading = "LEADING" in words
            it.sign_separate = "SEPARATE" in words
        elif t == "justified_clause":
            it.justified = True
        elif t == "blank_clause":
            it.blank_when_zero = True
    it.level, it.name = level or 0, name or "FILLER"
    return it


def _value(node, src: bytes):
    """A VALUE item: ('lit', text) | ('num', Decimal) | ('fig', SPACES|ZEROS|LOW|HIGH|QUOTES) | ('all', text) |
    ('hex', bytes) | ('range', lo, hi)."""
    parts = list(node.children)
    if any(c.type == "THRU" or c.type == "THROUGH" for c in parts):
        vals = [c for c in parts if c.type not in ("THRU", "THROUGH")]
        return ("range", _one(vals[0], src), _one(vals[-1], src))
    if parts and parts[0].type == "ALL":
        return ("all", _one(parts[1], src))
    return _one(parts[0], src) if parts else ("lit", _txt(node, src))


def _one(node, src: bytes):
    t, text = node.type, _txt(node, src)
    if text[:1] not in "'\"":
        text = text.rstrip(",;")  # `VALUES 0, 1`: the grammar hands the separator over with the value
    up = text.upper()
    if t in ("string",):
        q = text[0]
        return ("lit", text[1:-1].replace(q * 2, q))
    if t == "x_string":
        return ("hex", bytes.fromhex(re.sub(r"^X['\"]|['\"]$", "", text, flags=re.I)))
    if t == "number":
        return ("num", Decimal(text))
    if up.startswith(("SPACE",)):
        return ("fig", "SPACES")
    if up.startswith(("ZERO",)):
        return ("fig", "ZEROS")
    if up.startswith("LOW-VALUE"):
        return ("fig", "LOW")
    if up.startswith("HIGH-VALUE"):
        return ("fig", "HIGH")
    if up.startswith("QUOTE"):
        return ("fig", "QUOTES")
    if t == "string" or text[:1] in "'\"":
        return ("lit", text[1:-1])
    try:
        return ("num", Decimal(text))
    except ArithmeticError as e:  # #4411: an unquoted word is no literal (VALUE NULL ...): refused, never its text
        raise LayoutError(f"line {node.start_point[0] + 1}: VALUE {text} not modelled") from e


def _inherit_usage(it: Item, usage: str | None) -> None:
    if it.usage == "DISPLAY" and usage and usage != "DISPLAY":
        it.usage = usage
    for c in it.children:
        _inherit_usage(c, it.usage if it.pic is None else None)


def layout(rec: Item) -> None:
    """Offsets and sizes within the record, REDEFINES sharing their target's offset."""

    def size_of(it: Item, at: int) -> int:
        it.offset = at
        it.record = rec
        if it.pic is not None or it.usage in ("COMP-1", "COMP-2", "POINTER", "INDEX") or not it.children:
            it.size = it.elementary_size() if (it.pic or it.usage != "DISPLAY") else 0
            return it.size * it.occurs
        cur = at
        by_name: dict[str, Item] = {}
        for c in it.children:
            if c.redefines:
                target = by_name.get(c.redefines)
                if target is None:
                    raise LayoutError(f"line {c.line}: {c.name} REDEFINES {c.redefines}, not a sibling before it")
                size_of(c, target.offset)
            else:
                cur += size_of(c, cur)
            by_name[c.name] = c
        it.size = max([cur - at] + [c.offset - at + c.size * c.occurs for c in it.children])
        return it.size * it.occurs

    size_of(rec, 0)


# ---- the initial image -----------------------------------------------------------------------------------------
def image(rec: Item) -> bytes:
    if rec.level == 1 and rec.redefines and rec.record is not None and rec.record is not rec:
        return image(rec.record)[: rec.size * rec.occurs].ljust(rec.size * rec.occurs, b" ")
    return _image(rec)


def _image(rec: Item) -> bytes:
    """The record's bytes before the PROCEDURE DIVISION runs (GnuCOBOL's initialisation): VALUE clauses applied,
    the rest initialised by category (alphanumeric spaces, numeric zero), REDEFINES leaving their target's bytes."""
    # GnuCOBOL starts a record from zero bytes and initialises each item that is not a REDEFINES by its category:
    # a byte no such item covers (a REDEFINES longer than what it redefines) stays x'00'
    buf = bytearray(b"\x00" * (rec.size * rec.occurs))
    _fill(rec, buf, 0, False)
    return bytes(buf)


def _fill(it: Item, buf: bytearray, shift: int, under_redefines: bool) -> None:
    for k in range(it.occurs):
        base = it.offset + shift + k * it.size
        here_redef = under_redefines or bool(it.redefines)
        if it.children and it.pic is None:
            if it.values and not here_redef:
                _put_value(it, buf, base, it.values[0], group=True)
                continue
            for c in it.children:
                _fill(c, buf, shift + k * it.size, here_redef)
            continue
        if here_redef and it is not it.record:
            continue  # a REDEFINES leaves the bytes of what it redefines
        if it.values:
            _put_value(it, buf, base, it.values[0], group=False)
        else:
            _put_default(it, buf, base)


def _put_default(it: Item, buf: bytearray, at: int) -> None:
    cat = it.category
    n = it.size
    if cat == "NUMERIC-EDITED":
        buf[at : at + n] = b" " * n  # set at run time: MOVE ZERO through the runtime's editing (runtime_init)
    elif cat == "NUMERIC" and it.usage == "DISPLAY":
        # GnuCOBOL initialises a DISPLAY numeric item without VALUE to zero digits, the sign not overpunched (a
        # separate sign is '+')
        digits = b"0" * (n - (1 if it.sign_separate and it.signed else 0))
        if it.sign_separate and it.signed:
            digits = b"+" + digits if it.sign_leading else digits + b"+"
        buf[at : at + n] = digits
    elif cat == "NUMERIC":
        buf[at : at + n] = encode_number(it, Decimal(0))
    elif cat in ("FLOAT", "POINTER", "INDEX"):
        buf[at : at + n] = b"\x00" * n
    else:
        buf[at : at + n] = b" " * n


def _put_value(it: Item, buf: bytearray, at: int, v, group: bool) -> None:
    n = it.size
    kind = v[0]
    if group or it.category not in ("NUMERIC",):
        if kind == "lit":
            data = v[1].encode("latin-1")
        elif kind == "hex":
            data = v[1]
        elif kind == "all":
            lit = v[1][1].encode("latin-1") if isinstance(v[1], tuple) else b" "
            data = (lit * (n // max(1, len(lit)) + 1))[:n]
        elif kind == "fig":
            data = {"SPACES": b" ", "ZEROS": b"0", "LOW": b"\x00", "HIGH": b"\xff", "QUOTES": b'"'}[v[1]] * n
        elif kind == "num":
            data = str(v[1]).encode("latin-1")
        else:
            data = b""
        data = data[:n]
        if it.justified and not group:
            buf[at : at + n] = data.rjust(n, b" ")
        else:
            buf[at : at + n] = data.ljust(n, b" ")
        return
    if kind == "fig" and v[1] == "ZEROS":
        # GnuCOBOL: VALUE ZERO (the figurative) is written as the default zero, the sign not overpunched -- while
        # VALUE 0 (a numeric literal) is a positive zero, overpunched (CBTRN03C's WS-PAGE-TOTAL vs COTRN02C's
        # WS-TRAN-AMT-N, both checked against GnuCOBOL's bytes)
        _put_default(it, buf, at)
    elif kind == "num":
        buf[at : at + n] = encode_number(it, v[1])
    elif kind == "fig":
        buf[at : at + n] = {"SPACES": b" ", "LOW": b"\x00", "HIGH": b"\xff", "QUOTES": b'"'}[v[1]] * n
    elif kind == "lit":
        buf[at : at + n] = v[1].encode("latin-1")[:n].ljust(n, b" ")
    elif kind == "hex":
        buf[at : at + n] = v[1][:n].ljust(n, b"\x00")


def encode_number(it: Item, value: Decimal) -> bytes:
    """A numeric item's bytes for `value` (truncated to its PICTURE)."""
    digits, scale, signed = it.digits, it.scale, it.signed
    unscaled = int((value.copy_abs() * (Decimal(10) ** scale)).to_integral_value(rounding="ROUND_DOWN"))
    negative = signed and value < 0 and unscaled != 0
    s = str(unscaled)[-digits:].rjust(digits, "0") if digits else ""
    if it.usage == "PACKED":
        nib = s.rjust(it.size * 2 - 1, "0") + ("D" if negative else ("C" if signed else "F"))
        return bytes.fromhex(nib)
    if it.usage in ("BINARY", "COMP-5"):
        v = -int(s) if negative else int(s)
        return v.to_bytes(it.size, "big", signed=signed or v < 0)
    if not signed:
        return s.encode("latin-1")
    if it.sign_separate:
        sign = b"-" if negative else b"+"
        return sign + s.encode("latin-1") if it.sign_leading else s.encode("latin-1") + sign
    over = NEGATIVE if negative else POSITIVE
    if it.sign_leading:
        return (over[int(s[0])] + s[1:]).encode("latin-1")
    return (s[:-1] + over[int(s[-1])]).encode("latin-1")


def decode_number(it: Item, data: bytes) -> Decimal | None:
    """A zoned (sign overpunched, not separate) or packed item's value from its bytes; None when they are not a
    valid number of the item (VALUE SPACES on a numeric item, low-values)."""
    scale = Decimal(10) ** it.scale
    if it.usage == "PACKED":
        h = data.hex().upper()
        digits, sign = h[:-1], h[-1:]
        if not digits.isdigit() or sign not in "CDF":
            return None
        v = Decimal(int(digits)) / scale
        return -v if sign == "D" else v
    if it.usage != "DISPLAY" or it.sign_separate:
        return None
    s = data.decode("latin-1")
    if not s:
        return None
    negative = False
    at = 0 if it.sign_leading else len(s) - 1
    ch = s[at]
    if it.signed and not ch.isdigit():
        if ch in POSITIVE:
            s = s[:at] + str(POSITIVE.index(ch)) + s[at + 1 :]
        elif ch in NEGATIVE:
            s = s[:at] + str(NEGATIVE.index(ch)) + s[at + 1 :]
            negative = True
        else:
            return None
    if not s.isdigit():
        return None
    v = Decimal(int(s)) / scale
    return -v if negative else v


def records(program: Path, dirs: list[Path]) -> list[Item]:
    from gitgalaxy.tools.cobol_to_java.det.source import program_lines

    return parse(program_lines(program, dirs))


def runtime_init(rec: Item) -> list[Item]:
    """The items the image cannot hold: numeric-edited items without a VALUE, which GnuCOBOL initialises as MOVE ZERO
    (edited). The generated storage applies that move when it is created."""
    out = []

    def walk(it: Item, redef: bool) -> None:
        redef = redef or bool(it.redefines)
        if it.children and it.pic is None:
            if not it.values:
                for c in it.children:
                    walk(c, redef)
            return
        if not redef and not it.values and it.category == "NUMERIC-EDITED":
            out.append(it)

    walk(rec, False)
    return out
