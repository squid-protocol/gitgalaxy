"""A JCL SORT (DFSORT) step as a COBOL program (#4268): the control statements a step's SYSIN holds, with the
SYMNAMES it names, parsed into a model and lowered onto the COBOL SORT / MERGE statement, which the det port already
translates (cobolrt/Sort) and GnuCOBOL runs. The oracle runs the lowered program; the port is its det translation.

    parse(sysin, symnames) -> Control
    cobol_program(control, reclen, inputs) -> COBOL source (fixed format)

The model (IBM z/OS DFSORT Application Programming Guide, SC23-6878; "SORT / MERGE control statements", "INCLUDE /
OMIT control statements", "OPTION control statement", "Using symbols for fields and constants"):

* SORT FIELDS=(p,m,f,o,...) or FIELDS=(p,m,o,...),FORMAT=f, SORT FIELDS=COPY, MERGE FIELDS=(...). Formats: CH and BI
  (unsigned: byte order), ZD and PD (signed, by value). p is the 1-based byte position.
* EQUALS (OPTION EQUALS, or the EQUALS operand of SORT / MERGE): records with equal keys keep their input order --
  WITH DUPLICATES IN ORDER. Without it (the shipped installation default is EQUALS=NO) their order is undefined: no
  DUPLICATES phrase, so cobolrt/Sort stops the run by name on two such records whose bytes differ. A MERGE without
  EQUALS is refused (COBOL's MERGE always takes the USING order, an order DFSORT does not promise).
* INCLUDE / OMIT COND=(...) [,FORMAT=f]: a field compared (EQ NE GT GE LT LE) with a field of the same format, or with
  a constant -- C'...' (cut or blank-padded to the field), X'...' (cut or X'00'-padded), or a decimal number against a
  ZD / PD field -- joined by AND / OR (& / |) and parentheses, AND binding tighter. Applied to each input record
  before the sort (an INPUT PROCEDURE), or to each merged record (an OUTPUT PROCEDURE).
* SYMNAMES: `name,p,m[,f]` fields and `name,constant` constants; anything after a blank is a remark.
* Several inputs of a SORT are SORTIN's concatenation, in order; a MERGE's are SORTIN01, SORTIN02, ...

* OUTREC FIELDS=(...) (or BUILD=): the output record rebuilt from, in order, input fields (p,m or a SYMNAMES field; CH or
  BI), nX blanks, nZ binary zeros and C'...' / X'...' constants, optionally each after its own `o:` output position,
  which must be the next free byte (a gap or an overlap is refused). Applied after the sort / merge, to the record the
  INCLUDE / OMIT kept; the output record is as long as the items. Sort keys and conditions name INPUT positions.

Everything else is refused by name (Refused): INREC / OUTFIL / SUM / RECORD / ALTSEQ and the other
statements, the other formats (FI, AQ, AC, ...), OPTION operands other than EQUALS / NOEQUALS, a ZD key over 18 digits,
a field outside the record, and comparisons DFSORT pads or converts across formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FORMATS = ("CH", "BI", "ZD", "PD")
OPS = {"EQ": "=", "NE": "NOT =", "GT": ">", "GE": ">=", "LT": "<", "LE": "<="}
# columns 2-71 hold a control statement; column 1 is a label or blank (DFSORT: "Control statement format")
LAST = 71


class Refused(ValueError):
    """A control statement, operand or field the model does not cover, by name."""


@dataclass(frozen=True)
class Field:
    pos: int  # 1-based
    length: int
    fmt: str


@dataclass(frozen=True)
class Key:
    field: Field
    descending: bool


@dataclass(frozen=True)
class Const:
    kind: str  # C, X or N (decimal)
    text: str  # C: the characters; X: the hex digits; N: the signed number


@dataclass(frozen=True)
class Fill:
    length: int
    zero: bool  # nZ binary zeros, else nX blanks


@dataclass(frozen=True)
class Cmp:
    left: Field
    op: str
    right: Field | Const


@dataclass(frozen=True)
class Logic:
    op: str  # AND / OR
    left: Cmp | Logic
    right: Cmp | Logic


@dataclass(frozen=True)
class Control:
    verb: str  # SORT, MERGE or COPY
    keys: tuple[Key, ...]
    cond: Cmp | Logic | None  # the records kept
    omit: bool  # cond names the records dropped (OMIT), not those kept (INCLUDE)
    equals: bool
    outrec: tuple[Field | Const | Fill, ...] = ()  # the output record's items; empty: the record as it is


def _split_top(text: str) -> list[str]:
    """`text` cut at the commas outside quotes and parentheses."""
    out, depth, cur, quote = [], 0, "", False
    for ch in text:
        if ch == "'":
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quote:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return [*out, cur]


def _first_word(text: str) -> tuple[str, str]:
    """The text up to the first blank outside quotes, and the rest (a remark, or the next operand group)."""
    quote = False
    for i, ch in enumerate(text):
        if ch == "'":
            quote = not quote
        elif ch == " " and not quote:
            return text[:i], text[i:]
    return text, ""


def _statements(sysin: str) -> list[tuple[str, str]]:
    """(name, operands) per control statement: a statement whose operands end in a comma continues on the next line."""
    out: list[tuple[str, str]] = []
    pending = False
    for raw in sysin.splitlines():
        line = raw[:LAST].rstrip()
        if not line.strip() or line.startswith("*") or line.startswith("/*"):
            continue
        if pending:
            more, _ = _first_word(line.strip())
            name, ops = out[-1]
            out[-1] = (name, ops + more)
            pending = more.endswith(",")
            continue
        if line[0] != " ":
            raise Refused(f"a control statement label ({line.split()[0]})")
        parts = line.strip().split(None, 1)
        name = parts[0].upper()
        ops, _ = _first_word(parts[1].strip()) if len(parts) > 1 else ("", "")
        out.append((name, ops))
        pending = ops.endswith(",")
    return out


def _const(text: str) -> Const | None:
    m = re.fullmatch(r"C'((?:[^']|'')*)'", text)
    if m:
        return Const("C", m.group(1).replace("''", "'"))
    m = re.fullmatch(r"X'([0-9A-Fa-f]*)'", text)
    if m:
        if len(m.group(1)) % 2:
            raise Refused(f"a hexadecimal constant of an odd number of digits ({text})")
        return Const("X", m.group(1).upper())
    if re.fullmatch(r"[+-]?\d+", text):
        return Const("N", text)
    return None


def parse_symnames(symnames: str) -> dict[str, Field | Const]:
    """SYMNAMES records: `name,p,m[,f]` (a field) or `name,constant`; `*` in column 1 a comment."""
    syms: dict[str, Field | Const] = {}
    for raw in symnames.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("*"):
            continue
        text, _ = _first_word(line.strip())
        parts = _split_top(text)
        name = parts[0].upper()
        if len(parts) == 2:
            c = _const(parts[1])
            if c is None:
                raise Refused(f"SYMNAMES {name}: a symbol of {parts[1]} (only fields and constants)")
            syms[name] = c
        elif len(parts) in (3, 4) and parts[1].isdigit() and parts[2].isdigit():
            fmt = parts[3].upper() if len(parts) == 4 else ""
            syms[name] = Field(int(parts[1]), int(parts[2]), fmt)
        else:
            raise Refused(f"SYMNAMES {name}: {text} (only p,m[,f] fields and constants)")
    return syms


def _check_fmt(fmt: str, where: str) -> None:
    if fmt not in FORMATS:
        raise Refused(f"{where}: format {fmt or '(none)'} (modelled: {', '.join(FORMATS)})")


def _field(
    tokens: list[str], i: int, syms: dict[str, Field | Const], fmt_default: str, with_fmt: bool
) -> tuple[Field, int]:
    """The field at tokens[i] (a symbol or p,m[,f]) and the index after it."""
    sym = syms.get(tokens[i].upper())
    if isinstance(sym, Field):
        fmt = sym.fmt
        i += 1
        if not fmt and with_fmt and i < len(tokens) and tokens[i].upper() in FORMATS:
            fmt, i = tokens[i].upper(), i + 1
        return Field(sym.pos, sym.length, fmt or fmt_default), i
    if not (tokens[i].isdigit() and i + 1 < len(tokens) and tokens[i + 1].isdigit()):
        raise Refused(f"a field of {tokens[i]} (a symbol or p,m)")
    pos, length, i = int(tokens[i]), int(tokens[i + 1]), i + 2
    fmt = fmt_default
    if with_fmt and i < len(tokens) and tokens[i].upper() not in ("A", "D") and tokens[i].upper() not in OPS:
        fmt, i = tokens[i].upper(), i + 1
    return Field(pos, length, fmt), i


def _keys(operand: str, fmt_default: str, syms: dict[str, Field | Const], verb: str) -> tuple[Key, ...]:
    tokens = [t.strip() for t in _split_top(operand.strip()[1:-1])]
    keys, i = [], 0
    while i < len(tokens):
        f, i = _field(tokens, i, syms, fmt_default, True)
        if i >= len(tokens) or tokens[i].upper() not in ("A", "D"):
            raise Refused(f"{verb} FIELDS: a key without A or D ({operand})")
        _check_fmt(f.fmt, f"{verb} FIELDS")
        keys.append(Key(f, tokens[i].upper() == "D"))
        i += 1
    return tuple(keys)


def _cond(operand: str, fmt_default: str, syms: dict[str, Field | Const]) -> Cmp | Logic:
    """COND=(...): relations joined by AND / OR, AND binding tighter; a parenthesised group is a relation."""
    items = [t.strip() for t in _split_top(operand.strip()[1:-1])]
    rels: list[Cmp | Logic] = []
    joins: list[str] = []
    i = 0
    while i < len(items):
        if items[i].startswith("("):
            rels.append(_cond(items[i], fmt_default, syms))
            i += 1
        else:
            left, i = _field(items, i, syms, fmt_default, True)
            if i >= len(items) or items[i].upper() not in OPS:
                raise Refused(f"COND: a relation without EQ / NE / GT / GE / LT / LE ({operand})")
            op = items[i].upper()
            i += 1
            # p,m[,f] is a field: a decimal constant stands alone before AND / OR or the end
            field_next = i + 1 < len(items) and items[i].isdigit() and items[i + 1].isdigit()
            right: Field | Const | None = _const(items[i]) if i < len(items) and not field_next else None
            if right is None and i < len(items) and isinstance(syms.get(items[i].upper()), Const):
                right, i = syms[items[i].upper()], i + 1  # type: ignore[assignment]
            elif right is not None:
                i += 1
            else:
                right, i = _field(items, i, syms, fmt_default, True)
            rels.append(_relation(left, op, right))
        if i < len(items):
            j = {"&": "AND", "|": "OR"}.get(items[i].upper(), items[i].upper())
            if j not in ("AND", "OR"):
                raise Refused(f"COND: {items[i]} between relations (AND / OR)")
            joins.append(j)
            i += 1
            if i == len(items):
                raise Refused(f"COND: ends with {j}")
    # AND first, then OR, each left to right
    terms: list[Cmp | Logic] = [rels[0]]
    for j, r in zip(joins, rels[1:], strict=True):
        if j == "AND":
            terms[-1] = Logic("AND", terms[-1], r)
        else:
            terms.append(r)
    out = terms[0]
    for t in terms[1:]:
        out = Logic("OR", out, t)
    return out


def _relation(left: Field, op: str, right: Field | Const) -> Cmp:
    _check_fmt(left.fmt, "COND")
    if isinstance(right, Field):
        _check_fmt(right.fmt, "COND")
        numeric = {left.fmt, right.fmt} <= {"ZD", "PD"}
        if not numeric and (left.fmt != right.fmt or left.length != right.length):
            raise Refused(f"COND: {left.fmt} {left.length} bytes against {right.fmt} {right.length} bytes "
                          "(fields of one format and length, or two numeric ones)")  # fmt: skip
    elif right.kind == "N" and left.fmt not in ("ZD", "PD"):
        raise Refused(f"COND: a {left.fmt} field against a decimal constant")
    elif right.kind != "N" and left.fmt not in ("CH", "BI"):
        raise Refused(f"COND: a {left.fmt} field against a {right.kind} constant")
    return Cmp(left, op, right)


def _outrec(operand: str, syms: dict[str, Field | Const]) -> tuple[Field | Const | Fill, ...]:
    """OUTREC FIELDS=(...): input fields, nX / nZ fills and constants, laid end to end."""
    if not (operand.startswith("(") and operand.endswith(")")):
        raise Refused(f"OUTREC FIELDS={operand}")
    tokens = [t.strip() for t in _split_top(operand[1:-1])]
    items: list[Field | Const | Fill] = []
    nxt, i = 1, 0  # the next free output byte
    while i < len(tokens):
        t = tokens[i]
        at = re.match(r"(\d+):(.*)", t)
        if at:
            if int(at.group(1)) != nxt:
                raise Refused(f"OUTREC position {at.group(1)}: with the next free byte at {nxt} (gaps and overlaps)")
            t = tokens[i] = at.group(2).strip()
        fill = re.fullmatch(r"(\d+)([XZ])", t.upper())
        sym = syms.get(t.upper())
        lit = sym if isinstance(sym, Const) else (None if t.isdigit() or sym else _const(t))
        item: Field | Const | Fill
        if fill:
            if int(fill.group(1)) < 1:
                raise Refused(f"OUTREC {t}")
            item = Fill(int(fill.group(1)), fill.group(2) == "Z")
            i += 1
        elif lit is not None:
            if lit.kind == "N" or not lit.text:
                raise Refused(f"OUTREC constant {t} (only non-empty C'...' and X'...')")
            item = lit
            i += 1
        else:
            f, i = _field(tokens, i, syms, "CH", False)
            if i < len(tokens) and tokens[i].upper() in FORMATS:  # p,m,f: a conversion unless CH / BI
                if tokens[i].upper() not in ("CH", "BI"):
                    raise Refused(f"OUTREC a {tokens[i].upper()} field (a format conversion)")
                i += 1
            if f.fmt not in ("CH", "BI"):
                raise Refused(f"OUTREC a {f.fmt} field (a format conversion)")
            item = Field(f.pos, f.length, "CH")
        items.append(item)
        nxt += _out_len(item)
    if not items:
        raise Refused("OUTREC without fields")
    return tuple(items)


def _out_len(item: Field | Const | Fill) -> int:
    if isinstance(item, Field):
        return item.length
    if isinstance(item, Fill):
        return item.length
    return len(item.text) if item.kind == "C" else len(item.text) // 2


def parse(sysin: str, symnames: str = "") -> Control:
    """The step's control statements as a model, or Refused naming what is not modelled."""
    syms = parse_symnames(symnames)
    verb: str | None = None
    keys: tuple[Key, ...] = ()
    cond: Cmp | Logic | None = None
    omit = False
    equals: bool | None = None
    outrec: tuple[Field | Const | Fill, ...] = ()
    for name, operands in _statements(sysin):
        ops = {}
        for op in _split_top(operands):
            k, eq, v = op.partition("=")
            ops[k.strip().upper()] = v.strip() if eq else ""
        if name in ("SORT", "MERGE"):
            if verb is not None:
                raise Refused("a second SORT / MERGE statement")
            unknown = set(ops) - {"FIELDS", "FORMAT", "EQUALS", "NOEQUALS"}
            if unknown:
                raise Refused(f"{name} operands {', '.join(sorted(unknown))}")
            if "EQUALS" in ops or "NOEQUALS" in ops:
                equals = "EQUALS" in ops
            fields = ops.get("FIELDS", "")
            if fields.upper() == "COPY":
                verb = "COPY"
            elif fields.startswith("(") and fields.endswith(")"):
                verb = name
                keys = _keys(fields, ops.get("FORMAT", "").upper(), syms, name)
            else:
                raise Refused(f"{name} FIELDS={fields}")
        elif name in ("INCLUDE", "OMIT"):
            if cond is not None:
                raise Refused("a second INCLUDE / OMIT statement")
            unknown = set(ops) - {"COND", "FORMAT"}
            if unknown or not ops.get("COND", "").startswith("("):
                raise Refused(f"{name} operands {', '.join(sorted(unknown)) or ops.get('COND')}")
            cond, omit = _cond(ops["COND"], ops.get("FORMAT", "").upper(), syms), name == "OMIT"
        elif name == "OUTREC":
            if outrec:
                raise Refused("a second OUTREC statement")
            unknown = set(ops) - {"FIELDS", "BUILD"}
            if unknown or len({"FIELDS", "BUILD"} & set(ops)) != 1:
                raise Refused(f"OUTREC operands {', '.join(sorted(unknown)) or 'without FIELDS'}")
            outrec = _outrec(ops.get("FIELDS") or ops["BUILD"], syms)
        elif name == "OPTION":
            unknown = set(ops) - {"EQUALS", "NOEQUALS"}
            if unknown:
                raise Refused(f"OPTION {', '.join(sorted(unknown))}")
            if ops:
                equals = "EQUALS" in ops
        elif name == "END":
            break
        else:
            raise Refused(f"the {name} statement")
    if verb is None:
        raise Refused("no SORT or MERGE statement")
    return Control(verb, keys, cond, omit, bool(equals), outrec)


# ----- lowering --------------------------------------------------------------------------------------------------


def _pic(f: Field) -> str:
    if f.fmt in ("CH", "BI"):
        return f"PIC X({f.length})"
    if f.fmt == "ZD":
        if f.length > 18:
            raise Refused(f"a ZD field of {f.length} digits (at most 18)")
        return f"PIC S9({f.length})"
    digits = 2 * f.length - 1
    if digits > 18:
        raise Refused(f"a PD field of {f.length} bytes ({digits} digits; at most 18)")
    return f"PIC S9({digits}) COMP-3"


def _overlay(name: str, f: Field, reclen: int, redefines: str | None) -> list[str]:
    """An 01 laying `f` at its position in a record of `reclen` bytes (a REDEFINES of `redefines`, or an SD record)."""
    if f.pos < 1 or f.pos + f.length - 1 > reclen:
        raise Refused(f"a field at {f.pos} of {f.length} bytes, outside the {reclen}-byte record")
    head = f"01  {name}-R" + (f" REDEFINES {redefines}" if redefines else "") + "."
    out = [head]
    if f.pos > 1:
        out.append(f"    05 FILLER PIC X({f.pos - 1}).")
    out.append(f"    05 {name} {_pic(f)}.")
    rest = reclen - (f.pos + f.length - 1)
    if rest and not redefines:  # every record of an SD is the record's length
        out.append(f"    05 FILLER PIC X({rest}).")
    return out


def _literal(c: Const, f: Field) -> str:
    if c.kind == "N":
        return c.text
    if c.kind == "C":
        text = c.text[: f.length].ljust(f.length)
        return "'" + text.replace("'", "''") + "'"
    return "X'" + c.text[: 2 * f.length].ljust(2 * f.length, "0") + "'"


def cobol_program(ctl: Control, reclen: int, inputs: list[str], output: str = "SORTOUT",
                  program_id: str = "DFSORTST") -> str:  # fmt: skip
    """The step as a COBOL program: `inputs` are the input DD names (SORTIN's concatenation for a SORT or COPY; the
    SORTINnn files of a MERGE), each and the output fixed-length records of `reclen` bytes."""
    if not inputs:
        raise Refused("a step without input")
    if ctl.verb == "MERGE" and not ctl.equals:
        raise Refused("MERGE without EQUALS (DFSORT leaves the order of equal keys open; COBOL's MERGE does not)")
    # The oracle's SORT rewrites a signed DISPLAY key's sign in the records it sorts (an unsigned '1' comes out
    # the overpunch 'A' under -fsign=EBCDIC); DFSORT orders by the value and never changes a byte. A numeric key
    # is therefore sorted as a copy carried ahead of the record, and only the record is written.
    carried = any(k.field.fmt in ("ZD", "PD") for k in ctl.keys)
    if carried and ctl.verb == "MERGE":
        raise Refused("MERGE on a ZD or PD key (the oracle rewrites the key's sign in the merged records)")
    ins = [f"I{n}" for n in range(1, len(inputs) + 1)]
    selects = [f"SELECT {i}-FILE ASSIGN TO {dd}." for i, dd in zip(ins, inputs, strict=True)]
    selects += [f"SELECT O-FILE ASSIGN TO {output}.", "SELECT S-FILE ASSIGN TO SORTWK01."]
    outlen = sum(_out_len(x) for x in ctl.outrec) if ctl.outrec else reclen
    files = [x for i in ins for x in (f"FD  {i}-FILE.", f"01  {i}-REC PIC X({reclen}).")]
    files += ["FD  O-FILE.", f"01  O-REC PIC X({outlen}).", "SD  S-FILE."]
    keys, carry = [], []
    if carried:
        files.append("01  S-REC.")
        for n, k in enumerate(ctl.keys, 1):
            _overlay(f"K{n}", k.field, reclen, None)  # the field's bounds and picture
            files += [f"    05 K{n}-X PIC X({k.field.length}).", f"    05 K{n} REDEFINES K{n}-X {_pic(k.field)}."]
            carry.append(f"MOVE W-REC({k.field.pos}:{k.field.length}) TO K{n}-X")
        files.append(f"    05 S-DATA PIC X({reclen}).")
    else:
        files.append(f"01  S-REC PIC X({reclen}).")
        for n, k in enumerate(ctl.keys, 1):
            files += _overlay(f"K{n}", k.field, reclen, None)
    keys = [f"ON {'DESCENDING' if k.descending else 'ASCENDING'} KEY K{n}" for n, k in enumerate(ctl.keys, 1)]
    data = ["01  W-EOF PIC X.", f"01  W-REC PIC X({reclen})."]
    names: dict[Field, str] = {}

    def operand(f: Field) -> str:
        if f not in names:
            names[f] = f"C{len(names) + 1}"
            data.extend(_overlay(names[f], f, reclen, "W-REC"))
        return names[f]

    def text(c: Cmp | Logic) -> str:
        if isinstance(c, Logic):
            return f"({text(c.left)} {c.op} {text(c.right)})"
        right = operand(c.right) if isinstance(c.right, Field) else _literal(c.right, c.left)
        return f"({operand(c.left)} {OPS[c.op]} {right})"

    keep = None
    if ctl.cond is not None:
        keep = text(ctl.cond)
        keep = f"NOT {keep}" if ctl.omit else keep
    if ctl.outrec:  # after the comparison overlays, which REDEFINES W-REC and must follow it
        data.append(f"01  W-OUT PIC X({outlen}).")
    build = ["PERFORM BUILD-OUT"] if ctl.outrec else []
    shown = "W-OUT" if ctl.outrec else "W-REC"
    proc = ["MAIN-PARA."]
    dup = " WITH DUPLICATES IN ORDER" if ctl.equals else ""
    using = f"        USING {' '.join(f'{i}-FILE' for i in ins)}"
    if ctl.verb == "COPY":
        proc += ["    OPEN OUTPUT O-FILE", "    PERFORM READ-ALL", "    CLOSE O-FILE", "    GOBACK."]
    elif ctl.verb == "SORT":
        proc += [f"    SORT S-FILE {keys[0]}", *[f"        {k}" for k in keys[1:]]]
        proc[-1] += dup
        proc.append(using if keep is None and not carried else "        INPUT PROCEDURE READ-ALL")
        write_all = carried or bool(ctl.outrec)
        proc += ["        OUTPUT PROCEDURE WRITE-ALL" if write_all else "        GIVING O-FILE", "    GOBACK."]
    else:
        proc += [f"    MERGE S-FILE {keys[0]}", *[f"        {k}" for k in keys[1:]], using]
        proc += ["        GIVING O-FILE" if keep is None and not ctl.outrec else "        OUTPUT PROCEDURE WRITE-ALL",
                 "    GOBACK."]  # fmt: skip
    if carried or ctl.outrec or (ctl.verb == "MERGE" and keep is not None):
        into = "" if carried else " INTO W-REC"
        pre = ["MOVE S-DATA TO W-REC"] if carried and ctl.outrec else []
        write = f"WRITE O-REC FROM {shown if ctl.outrec else 'S-DATA' if carried else 'W-REC'}"
        body = [*pre, *build, write]
        if carried or keep is None:
            step = ["NOT AT END", *[f"    {x}" for x in body]]
        else:
            step = [f"NOT AT END IF {keep}", *[f"    {x}" for x in body], "END-IF"]
        proc += ["WRITE-ALL.", "    OPEN OUTPUT O-FILE", "    MOVE 'N' TO W-EOF", "    PERFORM UNTIL W-EOF = 'Y'",
                 f"        RETURN S-FILE{into}", "            AT END MOVE 'Y' TO W-EOF",
                 *[f"            {x}" for x in step], "        END-RETURN", "    END-PERFORM", "    CLOSE O-FILE."]  # fmt: skip
    if ctl.verb == "COPY" or (ctl.verb == "SORT" and (keep is not None or carried)):
        put: list[str]
        if ctl.verb == "COPY":
            put = [*build, f"WRITE O-REC FROM {shown}"]
        elif carried:
            put = ["MOVE W-REC TO S-DATA", *carry, "RELEASE S-REC"]
        else:
            put = ["RELEASE S-REC FROM W-REC"]
        proc += ["READ-ALL."]
        for i in ins:
            proc += [f"    OPEN INPUT {i}-FILE", "    MOVE 'N' TO W-EOF", "    PERFORM UNTIL W-EOF = 'Y'",
                     f"        READ {i}-FILE INTO W-REC", "            AT END MOVE 'Y' TO W-EOF"]  # fmt: skip
            if keep:
                proc += [
                    f"            NOT AT END IF {keep}",
                    *[f"                {x}" for x in put],
                    "            END-IF",
                ]
            else:
                proc += ["            NOT AT END", *[f"                {x}" for x in put]]
            proc += ["        END-READ", "    END-PERFORM", f"    CLOSE {i}-FILE"]
        proc[-1] += "."
    if ctl.outrec:
        proc += ["BUILD-OUT."]
        at = 1
        for item in ctl.outrec:
            n = _out_len(item)
            if isinstance(item, Field):
                proc.append(f"    MOVE W-REC({item.pos}:{item.length}) TO W-OUT({at}:{n})")
            elif isinstance(item, Fill):
                proc.append(f"    MOVE {'LOW-VALUES' if item.zero else 'SPACES'} TO W-OUT({at}:{n})")
            else:
                lit = "'" + item.text.replace("'", "''") + "'" if item.kind == "C" else "X'" + item.text + "'"
                proc.append(f"    MOVE {lit} TO W-OUT({at}:{n})")
            at += n
        proc[-1] += "."
    lines = ["IDENTIFICATION DIVISION.", f"PROGRAM-ID. {program_id}.", "ENVIRONMENT DIVISION.",
             "INPUT-OUTPUT SECTION.", "FILE-CONTROL.", *[f"    {s}" for s in selects], "DATA DIVISION.",
             "FILE SECTION.", *files, "WORKING-STORAGE SECTION.", *data, "PROCEDURE DIVISION.", *proc]  # fmt: skip
    return "\n".join(_fixed(x) for x in lines) + "\n"


def _fixed(line: str) -> str:
    """A line in fixed format: area A from column 8, cut at blanks to end by column 72 (a statement continues)."""
    out, line = [], "       " + line
    while len(line) > 72:
        cut = line.rfind(" ", 12, 72)
        if cut < 0 or line[:cut].count("'") % 2:
            raise Refused("a constant too long for one source line")
        out.append(line[:cut].rstrip())
        line = " " * 15 + line[cut:].lstrip()
    return "\n".join([*out, line])
