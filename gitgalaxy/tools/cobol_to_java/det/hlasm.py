# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#5859: the HLASM + EXEC CICS front end, slice 1 (docs/language_status/hlasm_cics_design.md).

`lower_text` lowers a command-level CICS assembler program to a fixed-format COBOL program, which the det translator
(and, from slice 2, the GnuCOBOL oracle) then reads like any other: the BLL precedent (X56, `bll.lower_text`).

Storage (HLASM Language Reference SC26-4940, "DS / DC instructions"): each DSECT is laid out with the assembler's
boundary alignment (H 2, F 4, D 8) and every symbol keeps its offset and length attribute; a `0CLn` symbol is a group
over the fields it covers. DFHEISTG -> WORKING-STORAGE; the DSECT a `USING` binds to the register loaded from DFHEICAP
-> LINKAGE DFHCOMMAREA; the EIB fields are DFHEIBLK's. Registers are fullword binary cells (HL-Rn). Code addresses are
opaque return ids: BAS stores one, BCR dispatches on it.

The condition code (z/Architecture Principles of Operation SA22-7832, chapter 7) is resolved statically: a
conditional BC must follow its CC-setting instruction directly, and a logical compare (CLC, CLI) whose high / low
outcome the mask separates is refused (GnuCOBOL collates ASCII, z/OS EBCDIC); equal / not equal is exact.

Everything outside the subset is refused by name (`Refused`), so a program is translated whole or not at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# The statement rules of gitgalaxy/core/hlasm_cics.py, mirrored as cics_macro_level does: the translator fingerprint
# (tests/tools/evidence_report.TRANSLATOR_INPUTS) reads det/, not that scanner module.
def _is_comment(line: str) -> bool:
    return line.startswith("*") or line.startswith(".*")


def _continues(line: str) -> bool:
    """Column 72 is non-blank, or a lone mark drifted into column 73 (zECS's `EXEC CICS WRITEQ TD ... X` lines)."""
    body = line.rstrip("\r")
    if len(body) > 71 and body[71] != " ":
        return True
    return len(body.rstrip()) == 73 and body[71] == " "


SUBSET = frozenset({"B", "BC", "BCR", "BAS", "L", "LA", "ST", "STH", "CH", "CLC", "CLI", "MVC", "OC"})
_IGNORED = frozenset({"AMODE", "RMODE", "PRINT", "LTORG", "END", "EJECT", "SPACE", "TITLE"})
_RESERVED_REGS = {13}  # the save area, never a work register here
_ALIGN = {"H": 2, "F": 4, "D": 8}
_SIZE = {"H": 2, "F": 4, "D": 8}
_PIC = {"H": "S9(4) COMP-5", "F": "S9(9) COMP-5", "D": "S9(15) COMP-3"}
# DFHEIBLK (CICS Application Programming Reference, "EIB fields"): the ones the subset reads, with their HLASM type
_EIB = {
    "EIBTRNID": ("C", 4), "EIBTRMID": ("C", 4), "EIBCALEN": ("H", 2), "EIBRESP": ("F", 4), "EIBRESP2": ("F", 4),
    "EIBAID": ("C", 1), "EIBCPOSN": ("H", 2), "EIBDS": ("C", 8), "EIBRSRCE": ("C", 8), "EIBREQID": ("C", 8),
}  # fmt: skip
# DCOUNTER options CICS reads or writes as an unsigned doubleword: an XL8 operand there is a number, not bytes
_DOUBLEWORD_OPTIONS = {"VALUE", "MINIMUM", "MAXIMUM", "INCREMENT", "COMPAREMIN", "COMPAREMAX"}
_SYMBOL = re.compile(r"[A-Z][A-Z0-9_]{0,29}$", re.I)
_DC_ITEM = re.compile(r"^(\d*)([CXHFD])(?:L(\d+))?(?:'((?:[^']|'')*)')?$", re.I)


class Refused(ValueError):
    """The program uses something outside the slice-1 subset: named, never translated."""


@dataclass
class Stmt:
    line: int
    label: str
    op: str
    operands: str


@dataclass
class Item:
    """One storage symbol (or an unnamed FILLER) of a section: offset, length attribute, type, group members."""

    name: str
    section: str
    off: int
    length: int
    typ: str  # C X H F D, or G for a 0CLn group
    value: str | None = None
    children: list[Item] = field(default_factory=list)
    doubleword: bool = False


def _split_operands(text: str) -> str:
    """The operand field: up to the first blank outside quotes (the remarks follow it)."""
    quoted = False
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif ch in " \t" and not quoted:
            return text[:i]
    return text


def statements(text: str) -> list[Stmt]:
    """Comment-free statements, each continuation (column 72) joined at column 16."""
    lines = text.replace("\r", "").split("\n")
    out: list[Stmt] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or _is_comment(raw):
            i += 1
            continue
        start, body = i, raw[:71]
        while _continues(lines[i]) and i + 1 < len(lines):
            i += 1
            body += " " + lines[i][15:71].strip()
        i += 1
        label = "" if body[:1] in (" ", "\t") else body.split()[0]
        rest = body[len(label) :].strip()
        if not rest:
            continue
        op, _, operands = rest.partition(" ")
        op, operands = op.upper(), operands.strip()
        if op == "EXEC":
            out.append(Stmt(start + 1, label, op, operands))
        else:
            out.append(Stmt(start + 1, label, op, _split_operands(operands)))
    return out


def _cobol(name: str) -> str:
    return name.upper().replace("_", "-")


class _Lowering:
    def __init__(self, text: str, file: str):
        self.file = file
        self.stmts = statements(text)
        self.items: dict[str, Item] = {}
        self.sections: dict[str, list[Item]] = {}
        self.equ: dict[str, int] = {}
        self.program = ""
        self.entry_regs: set[int] = set(_RESERVED_REGS)
        self.commarea: str | None = None
        self.labels: list[str] = []
        self.used_regs: set[int] = set()
        self.returns: list[str] = []

    def refuse(self, s: Stmt | None, what: str) -> Refused:
        return Refused(f"{what} at line {s.line}" if s else what)

    # ---- pass 1: storage ---------------------------------------------------------------------------------------
    def layout(self) -> None:
        section: str | None = None
        loc = 0
        groups: list[Item] = []  # open 0CLn groups
        entry: list[tuple[Stmt, str]] = []
        for s in self.stmts:
            if s.op == "DSECT":
                section, loc, groups = s.label.upper(), 0, []
                self.sections[section] = []
                continue
            if s.op == "DFHEIENT":
                section, loc, groups = "*CSECT", 0, []
                self.sections[section] = []
                self.program = s.label.upper()
                for reg in re.findall(r"(?:CODEREG|DATAREG|EIBREG)=(\([^)]*\)|[^,]+)", s.operands, re.I):
                    entry += [(s, r) for r in reg.strip("()").split(",")]
                continue
            if s.op == "EQU":
                m = re.fullmatch(r"\*-([A-Z0-9_]+)", s.operands, re.I)
                if re.fullmatch(r"\d+", s.operands):
                    self.equ[s.label.upper()] = int(s.operands)
                elif m and m.group(1).upper() in self.items and self.items[m.group(1).upper()].section == section:
                    self.equ[s.label.upper()] = loc - self.items[m.group(1).upper()].off
                else:
                    raise self.refuse(s, f"EQU {s.operands}")
                continue
            if s.op not in ("DS", "DC") or section is None:
                continue
            m = _DC_ITEM.match(s.operands)
            if not m:
                raise self.refuse(s, f"{s.op} {s.operands}")
            dup, typ, ln, val = m.group(1), m.group(2).upper(), m.group(3), m.group(4)
            if dup not in ("", "0") or (ln and typ in _SIZE) or (s.op == "DC" and val is None and dup != "0"):
                raise self.refuse(s, f"{s.op} {s.operands}")
            length = int(ln) if ln else _SIZE.get(typ, 1) if typ != "C" or val is None else len(val.replace("''", "'"))
            if not ln and typ == "X" and val is not None:
                length = (len(val) + 1) // 2
            if typ in _ALIGN:
                aligned = -(-loc // _ALIGN[typ]) * _ALIGN[typ]
                if aligned > loc:  # the boundary's skipped bytes keep every later offset in a group or the COMMAREA
                    self._place(s, Item("", section, loc, aligned - loc, "C"), groups)
                loc = aligned
            if dup == "0":
                if typ in _ALIGN and not s.label:
                    continue  # DS 0F / 0H: alignment only
                if typ in _ALIGN:  # `LABEL DS 0H`: a code label
                    if section == "*CSECT":
                        continue
                    raise self.refuse(s, f"{s.op} {s.operands}")
                item = Item(s.label.upper(), section, loc, length, "G")
                self._place(s, item, groups)
                groups.append(item)
                continue
            if s.op == "DC" and section != "*CSECT":
                raise self.refuse(s, "DC in a DSECT")
            if section == "*CSECT" and not s.label and not groups:
                continue  # an unnamed constant (the eyecatcher a `B` jumps around): nothing names or reads it
            if s.op == "DS" and section == "*CSECT":
                raise self.refuse(s, "DS storage in the program CSECT")
            item = Item(s.label.upper() if s.label else "", section, loc, length, typ, self._value(s, typ, length, val))
            self._place(s, item, groups)
            loc += length
            while groups and loc >= groups[-1].off + groups[-1].length:
                g = groups.pop()
                if loc != g.off + g.length:
                    raise self.refuse(s, f"{g.name} 0CL{g.length} not covered exactly by its fields")
        if not self.program:
            raise self.refuse(None, "no DFHEIENT entry")
        for s, r in entry:  # (the register EQUs follow the code)
            self.entry_regs.add(self._reg(s, r))

    def _place(self, s: Stmt, item: Item, groups: list[Item]) -> None:
        if item.name:
            if not _SYMBOL.match(item.name) or item.name in self.items:
                raise self.refuse(s, f"symbol {item.name}")
            self.items[item.name] = item
        (groups[-1].children if groups else self.sections[item.section]).append(item)

    def _value(self, s: Stmt, typ: str, length: int, val: str | None) -> str | None:
        if val is None:
            return None
        if typ == "C":
            text = val.replace("''", "'")
            if "&" in text.replace("&&", ""):
                raise self.refuse(s, f"variable symbol in {s.operands}")
            return text.replace("&&", "&")[:length].ljust(length)
        if typ == "X":
            if not re.fullmatch(r"[0-9A-F]+", val, re.I):
                raise self.refuse(s, f"{s.op} {s.operands}")
            return val.upper().rjust(2 * length, "0")[-2 * length :]
        if typ in ("H", "F") and re.fullmatch(r"[+-]?\d+", val):
            return str(int(val))
        raise self.refuse(s, f"{s.op} {s.operands}")

    def _reg(self, s: Stmt, text: str) -> int:
        t = text.strip().upper()
        n = int(t) if t.isdigit() else self.equ.get(t)
        if n is None or not 0 <= n <= 15:
            raise self.refuse(s, f"register {text}")
        return n

    # ---- operands ----------------------------------------------------------------------------------------------
    def storage(self, s: Stmt, text: str) -> tuple[Item, int, int]:
        """`SYM`, `SYM+n`, `SYM+n(len)` -> (item, displacement, length)."""
        m = re.fullmatch(r"([A-Z][A-Z0-9_]*)(?:\+(\d+))?(?:\((\d+)\))?", text.strip(), re.I)
        if not m:
            raise self.refuse(s, f"operand {text}")
        name = m.group(1).upper()
        if name in _EIB:
            item = Item(name, "*EIB", 0, _EIB[name][1], _EIB[name][0])
        elif name in self.items:
            item = self.items[name]
        else:
            raise self.refuse(s, f"operand {text}")
        if item.section not in ("DFHEISTG", "*CSECT", "*EIB") and item.section != self.commarea:
            raise self.refuse(s, f"operand {text}: DSECT {item.section} not addressed")
        disp = int(m.group(2) or 0)
        length = int(m.group(3)) if m.group(3) else item.length - disp
        if disp + length > item.length or length <= 0:
            raise self.refuse(s, f"operand {text} past its symbol")
        return item, disp, length

    @staticmethod
    def ref(item: Item, disp: int, length: int) -> str:
        if disp == 0 and length == item.length:
            return _cobol(item.name)
        return f"{_cobol(item.name)}({disp + 1}:{length})"

    def work_reg(self, s: Stmt, text: str) -> str:
        n = self._reg(s, text)
        if n in self.entry_regs:
            raise self.refuse(s, f"{s.op} on reserved register {n}")
        self.used_regs.add(n)
        return f"HL-R{n}"

    def target(self, s: Stmt, text: str) -> str:
        name = text.strip().upper()
        if name not in self.labels:
            raise self.refuse(s, f"branch target {text}")
        return _cobol(name)

    # ---- pass 2: code ------------------------------------------------------------------------------------------
    def lower(self) -> str:
        self.layout()
        code = self._code_stmts()
        self.labels = [s.label.upper() for s in code if s.label]
        cics = [s for s in code if s.op == "EXEC"]
        for s in cics:  # an XL8 a DCOUNTER option names is an unsigned doubleword number
            if re.search(r"\bDCOUNTER\b", s.operands, re.I):
                for opt, arg in re.findall(r"([A-Z]+)\s*\(([^()]*)\)", s.operands, re.I):
                    it = self.items.get(arg.strip().upper())
                    if opt.upper() in _DOUBLEWORD_OPTIONS and it and it.typ == "X" and it.length == 8:
                        it.doubleword = True
        proc = self._procedure(code)
        return "\n".join(self._data() + proc) + "\n"

    def _code_stmts(self) -> list[Stmt]:
        """The executable statements of the CSECT: from DFHEIENT to LTORG / END, unnamed branch-around DCs dropped."""
        out: list[Stmt] = []
        inside = False
        for s in self.stmts:
            if s.op == "DFHEIENT":
                inside = True
                continue
            if not inside:
                if s.op in ("DSECT", "DS", "DC", "EQU", "PRINT"):
                    continue
                raise self.refuse(s, f"{s.op} before DFHEIENT")
            if s.op in ("LTORG", "END"):
                break
            if s.op in ("AMODE", "RMODE", "PRINT", "EQU") or (s.op == "DC" and not s.label):
                if s.op == "DC" and not self._after_unconditional(out):
                    raise self.refuse(s, "constant reached by fall-through")
                continue
            if s.op == "DS" and s.label and re.fullmatch(r"0H", s.operands, re.I):
                out.append(Stmt(s.line, s.label, "", ""))
                continue
            if s.op == "USING" or s.op == "EXEC" or s.op in SUBSET:
                out.append(s)
                continue
            raise self.refuse(s, f"instruction {s.op}")
        return out

    @staticmethod
    def _after_unconditional(out: list[Stmt]) -> bool:
        last = next((s for s in reversed(out) if s.op), None)
        return last is not None and (last.op == "B" or (last.op == "BC" and _mask(last.operands) == 15))

    def _procedure(self, code: list[Stmt]) -> list[str]:
        body: list[str] = []
        prev: Stmt | None = None
        k = 0
        loaded: dict[int, int] = {}  # register -> line of `L Rn,DFHEICAP`
        for s in code:
            if s.label:
                _close(body)
                body.append(f"       {_cobol(s.label)}.")
            if not s.op:
                prev = None
                continue
            body.append(f"      *    {self.file.rsplit('/', 1)[-1]}:{s.line}: {s.op} {s.operands}"[:72].rstrip())
            ops = s.operands.split(",") if s.op != "EXEC" else []
            if s.op == "USING":
                dsect, reg = (o.strip().upper() for o in ops) if len(ops) == 2 else ("", "")
                if dsect not in self.sections or self._reg(s, reg) not in loaded or self.commarea:
                    raise self.refuse(s, f"USING {s.operands}")
                self.commarea = dsect
            elif s.op == "L" and len(ops) == 2 and ops[1].strip().upper() == "DFHEICAP":
                n = self._reg(s, ops[0])
                loaded[n] = s.line
                self.entry_regs.add(n)  # the COMMAREA base: no work register from here on
            elif s.op == "EXEC":
                body += self._exec(s)
            elif s.op in ("B", "BC"):
                mask, tgt = (15, ops[0]) if s.op == "B" else (_mask(ops[0]), ops[1] if len(ops) == 2 else "")
                if mask is None:
                    raise self.refuse(s, f"BC mask {ops[0]}")
                if mask == 0:
                    body.append("           CONTINUE")
                elif mask == 15:
                    body.append(f"           GO TO {self.target(s, tgt)}")
                else:
                    cond = self._condition(s, prev, mask)
                    body += [
                        f"           IF {cond}",
                        f"               GO TO {self.target(s, tgt)}",
                        "           END-IF",
                    ]
            elif s.op == "BAS":
                reg, tgt = self.work_reg(s, ops[0]), self.target(s, ops[1])
                k += 1
                self.returns.append(f"HL-RET-{k}")
                body += [f"           MOVE {k} TO {reg}", f"           GO TO {tgt}"]
                _close(body)
                body.append(f"       HL-RET-{k}.")
            elif s.op == "BCR":
                mask = _mask(ops[0])
                if mask == 0:
                    body.append("           CONTINUE")
                elif mask != 15:
                    raise self.refuse(s, "conditional BCR")
                else:
                    body += self._dispatch(s, self.work_reg(s, ops[1]))
            else:
                body += self._simple(s, ops)
            prev = s
        _close(body)
        return [
            "       PROCEDURE DIVISION.",
            *body,
        ]

    def _dispatch(self, s: Stmt, reg: str) -> list[str]:
        if not self.returns:
            raise self.refuse(s, "BCR with no BAS return point")
        out = (
            ["           GO TO"]
            + [f"               {r}" for r in self.returns]
            + [f"               DEPENDING ON {reg}"]
        )
        # A return id no BAS stored: a branch to an address the program never took, a program check (ASRA)
        return [*out, "           EXEC CICS ABEND ABCODE('ASRA') NODUMP END-EXEC"]

    def _simple(self, s: Stmt, ops: list[str]) -> list[str]:
        op = s.op
        if op in ("L", "ST", "STH", "CH"):
            if len(ops) != 2:
                raise self.refuse(s, f"{op} {s.operands}")
            reg = self.work_reg(s, ops[0])
            item, disp, length = self.storage(s, ops[1])
            want = "H" if op in ("STH", "CH") else "F"
            if item.typ != want or disp or length != item.length:
                raise self.refuse(s, f"{op} on {item.name} ({item.typ})")
            name = _cobol(item.name)
            if op in ("ST", "STH"):
                self._writable(s, item)
            if op == "L":
                return [f"           MOVE {name} TO {reg}"]
            if op == "ST":
                return [f"           MOVE {reg} TO {name}"]
            if op == "STH":  # the low halfword, as a signed halfword (POPS: STH stores bits 48-63)
                return [f"           COMPUTE {name} =", f"               FUNCTION MOD({reg} + 32768, 65536) - 32768"]
            return []  # CH: only sets the condition code, read by the next BC
        if op == "LA":
            reg = self.work_reg(s, ops[0])
            v = ops[1].strip().upper() if len(ops) == 2 else ""
            n = int(v) if v.isdigit() else self.equ.get(v)
            if n is None or not 0 <= n <= 4095:
                raise self.refuse(s, f"LA of an address ({s.operands})")
            return [f"           MOVE {n} TO {reg}"]
        if op == "MVC":
            dst, dd, dl = self.storage(s, ops[0])
            m = re.fullmatch(r"([A-Z][A-Z0-9_]*(?:\+\d+)?)", ops[1].strip(), re.I) if len(ops) == 2 else None
            if not m:
                raise self.refuse(s, f"MVC {s.operands}")
            src, sd, sl = self.storage(s, ops[1])
            if sl < dl:
                raise self.refuse(s, "MVC reading past its source symbol")
            if dst.typ in ("H", "F", "D") or src.typ in ("H", "F", "D") or dst.doubleword or src.doubleword:
                raise self.refuse(s, "MVC on binary fields")
            self._writable(s, dst)
            if self._overlap(dst, dd, src, sd, dl):
                raise self.refuse(s, "overlapping MVC")
            return [f"           MOVE {self.ref(src, sd, dl)}", f"             TO {self.ref(dst, dd, dl)}"]
        if op in ("CLC", "CLI", "OC"):
            return []  # set the condition code only (OC X,X leaves X as it is): read by the next BC
        raise self.refuse(s, f"instruction {op}")

    def _writable(self, s: Stmt, item: Item) -> None:
        if item.section in ("*CSECT", "*EIB"):
            raise self.refuse(s, f"store into {item.name} (program constant or EIB)")

    def _overlap(self, a: Item, ad: int, b: Item, bd: int, n: int) -> bool:
        if a.section != b.section:
            return False
        lo, hi = a.off + ad, b.off + bd
        return lo < hi + n and hi < lo + n

    def _condition(self, s: Stmt, setter: Stmt | None, mask: int) -> str:
        """The branch condition of `BC mask` after `setter` (POPS: CC 0 equal / zero, 1 low / nonzero, 2 high)."""
        if setter is None or s.label or setter.op not in ("CLC", "CLI", "CH", "OC"):
            raise self.refuse(s, "conditional BC not directly after its CC-setting instruction")
        taken = {cc for cc, bit in enumerate((8, 4, 2, 1)) if mask & bit}
        ops = [o.strip() for o in setter.operands.split(",")]
        if setter.op == "OC":
            if len(ops) != 2 or ops[0].upper() != ops[1].upper():
                raise self.refuse(setter, "OC other than OC X,X")
            item, disp, length = self.storage(setter, ops[0])
            if item.typ not in ("H", "F") or disp or length != item.length:
                raise self.refuse(setter, f"OC on {item.name} ({item.typ})")
            rel = {frozenset({0}): "=", frozenset({1}): "NOT ="}.get(frozenset(taken & {0, 1}))
            if rel is None:
                raise self.refuse(s, f"BC {mask} after OC")
            return f"{_cobol(item.name)} {rel} 0"
        if setter.op == "CH":
            reg = self.work_reg(setter, ops[0])
            item, disp, length = self.storage(setter, ops[1])
            if item.typ != "H" or disp or length != item.length:
                raise self.refuse(setter, f"CH on {item.name}")
            rel = {
                frozenset({0}): "=", frozenset({1}): "<", frozenset({2}): ">",
                frozenset({0, 1}): "<=", frozenset({0, 2}): ">=", frozenset({1, 2}): "NOT =",
            }.get(frozenset(taken & {0, 1, 2}))  # fmt: skip
            if rel is None:
                raise self.refuse(s, f"BC {mask} after CH")
            return f"{reg} {rel} {_cobol(item.name)}"
        rel = {frozenset({0}): "=", frozenset({1, 2}): "NOT ="}.get(frozenset(taken & {0, 1, 2}))
        if rel is None:
            raise self.refuse(s, f"BC {mask} after {setter.op}: a high / low outcome (EBCDIC collating)")
        left, right = self._compare_operands(setter, ops)
        return f"{left} {rel} {right}"

    def _compare_operands(self, s: Stmt, ops: list[str]) -> tuple[str, str]:
        if len(ops) != 2:
            raise self.refuse(s, f"{s.op} {s.operands}")
        item, disp, length = self.storage(s, ops[0])
        lit = re.fullmatch(r"(=)?([CXHF])'([^']*)'", ops[1], re.I)
        if s.op == "CLI":
            if not lit or lit.group(1) or lit.group(2).upper() not in "CX" or item.typ in ("H", "F", "D"):
                raise self.refuse(s, f"CLI {s.operands}")
            byte = f"'{lit.group(3)}'" if lit.group(2).upper() == "C" else f"X'{lit.group(3).upper()}'"
            if len(lit.group(3)) != (1 if lit.group(2).upper() == "C" else 2):
                raise self.refuse(s, f"CLI {s.operands}")
            return self.ref(item, disp, 1), byte
        if lit:
            typ = lit.group(2).upper()
            if not lit.group(1) or typ not in ("H", "F") or item.typ != typ or disp or length != item.length:
                raise self.refuse(s, f"CLC {s.operands}")
            return _cobol(item.name), str(int(lit.group(3)))
        other, od, ol = self.storage(s, ops[1])
        binary = {"H", "F", "D"}
        if ol < length or ((item.typ in binary) != (other.typ in binary)) or item.typ == "D" or other.typ == "D":
            raise self.refuse(s, f"CLC {s.operands}")
        if item.typ in binary and (item.typ != other.typ or disp or od):
            raise self.refuse(s, f"CLC {s.operands}")
        return self.ref(item, disp, length), self.ref(other, od, length)

    def _exec(self, s: Stmt) -> list[str]:
        text = re.sub(r"\s+\(", "(", s.operands.strip())
        if not re.match(r"CICS\b", text, re.I):
            raise self.refuse(s, f"EXEC {text.split()[0] if text else ''}")
        tok = re.compile(r"([A-Z0-9]+)(?:\(((?:'[^']*'|[^()'])*)\))?", re.I)
        rest = text[4:]
        words = [
            f"{m.group(1).upper()}({self._cics_arg(s, m.group(2).strip())})"
            if m.group(2) is not None
            else m.group(1).upper()
            for m in tok.finditer(rest)
        ]
        if tok.sub("", rest).strip():
            raise self.refuse(s, f"EXEC CICS operand syntax {text}")
        out = ["           EXEC CICS", *(f"               {w}" for w in words)]
        out[-1] += " END-EXEC"
        return out

    def _cics_arg(self, s: Stmt, arg: str) -> str:
        if re.fullmatch(r"'[^']*'", arg) or re.fullmatch(r"\d+", arg):
            return arg
        name = arg.upper()
        if name in _EIB or name in self.items:
            self.storage(s, arg)  # addressed?
            return _cobol(name)
        raise self.refuse(s, f"EXEC CICS operand {arg}")

    # ---- data division ------------------------------------------------------------------------------------------
    def _data(self) -> list[str]:
        out = [
            "       IDENTIFICATION DIVISION.",
            f"       PROGRAM-ID. {self.program}.",
            f"      * Lowered from {self.file.rsplit('/', 1)[-1]} by det/hlasm.py (#5859).",
            "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.",
        ]
        if self.used_regs:
            out.append("       01  HL-REGISTERS.")
            out += [f"           05  HL-R{n} PIC S9(9) COMP-5 VALUE 0." for n in sorted(self.used_regs)]
        for sec in ("DFHEISTG", "*CSECT"):
            for it in self.sections.get(sec, []):
                out += self._item(it, 1)
        for sec in self.sections:
            if sec not in ("DFHEISTG", "*CSECT") and sec != self.commarea:
                raise Refused(f"DSECT {sec}, which no USING addresses")
        if self.commarea:
            out += ["       LINKAGE SECTION.", "       01  DFHCOMMAREA."]
            for it in self.sections[self.commarea]:
                out += self._item(it, 5)
        return out

    def _item(self, it: Item, level: int) -> list[str]:
        name = _cobol(it.name) if it.name else "FILLER"
        lvl = f"{level:02d}"
        ind = "       " if level == 1 else "           " + "   " * ((level - 5) // 5)
        if it.typ == "G":
            if not it.name and level == 1:
                raise Refused("an unnamed 0CL group")
            out = [f"{ind}{lvl}  {name}."]
            for c in it.children:
                out += self._item(c, level + 5 if level > 1 else 5)
            return out
        if not it.name and level == 1 and it.value is None:
            return []  # unnamed top-level storage: nothing names it
        if it.typ in ("H", "F", "D"):
            pic = _PIC[it.typ]
            value = f" VALUE {it.value}" if it.value is not None else ""
            return [f"{ind}{lvl}  {name} PIC {pic}{value}."]
        if it.doubleword:
            v = int(it.value, 16) if it.value is not None else None
            if v is not None and v >= 10**18:
                raise Refused(f"{it.name} past PIC 9(18)")
            return [f"{ind}{lvl}  {name} PIC 9(18) COMP-5" + (f" VALUE {v}." if v is not None else ".")]
        if it.value is None:
            return [f"{ind}{lvl}  {name} PIC X({it.length})."]
        if it.typ == "X":
            return [f"{ind}{lvl}  {name} PIC X({it.length})", f"{ind}        VALUE X'{it.value}'."]
        chunks = [it.value[i : i + 40] for i in range(0, len(it.value), 40)]
        if len(chunks) == 1:
            return [f"{ind}{lvl}  {name} PIC X({it.length})", f"{ind}        VALUE {_quote(it.value)}."]
        out = [f"{ind}{lvl}  {name}."]
        sub = f"{level + 5 if level > 1 else 5:02d}"
        for chunk in chunks:
            out += [f"{ind}    {sub}  FILLER PIC X({len(chunk)})", f"{ind}        VALUE {_quote(chunk)}."]
        return out


def _close(body: list[str]) -> None:
    """Ends the sentence before a paragraph header: each paragraph is one sentence, closed by a period."""
    last = next((i for i in range(len(body) - 1, -1, -1) if not body[i].startswith("      *")), None)
    if last is not None and not body[last].endswith("."):
        body[last] += "."


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _mask(text: str) -> int | None:
    t = text.strip().upper()
    m = re.fullmatch(r"B'([01]{4})'", t)
    if m:
        return int(m.group(1), 2)
    return int(t) if t.isdigit() and int(t) < 16 else None


def lower_text(text: str, file: str) -> str:
    """The fixed-format COBOL program `text` (an HLASM CICS program) lowers to. Raises Refused, naming what is outside
    the subset."""
    return _Lowering(text, file).lower()


def service_stub(program: str, package: str) -> str:
    """The generated service an HLASM CICS program has none of (the forge reads COBOL only): `<Name>Service` with the
    region facade the forge gives a CICS program (handleTransaction, the COMMAREA untyped) and the runTask the port
    fills -- as det makes the stub of a sibling unit the forge never saw (#5106)."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

    cls = java_class_base(program) + "Service"
    return "\n".join([
        f"package {package}.service;",
        "",
        f"import {package}.cics.CicsTask;",
        "",
        f"public class {cls} {{",
        "    public Object handleTransaction(String transid, Object request) {",
        "        CicsTask.Region region = CicsTask.region();",
        "        CicsTask task = region.transaction(transid, request);",
        f'        region.run(task, "{program.upper()}", this::runTask);',
        "        return task.returned(Object.class);",
        "    }",
        "",
        "    public void runTask(CicsTask task) {",
        "    }",
        "}",
        "",
    ])  # fmt: skip
