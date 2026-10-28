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
from collections.abc import Callable
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


SUBSET = frozenset({
    "B", "BC", "BCR", "BAS", "L", "LA", "ST", "STH", "CH", "CLC", "CLI", "MVC", "OC", "SR", "XC", "BCT",
    "IC", "STCM", "TR", "SLL", "SLDL",
})  # fmt: skip
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
_DYN = re.compile(r"([^()]*)\(([^(),]*)(?:,([^(),]*))?\)")  # d(b), d(,b), d(l,b), SYM(x)
_ASRA = "EXEC CICS ABEND ABCODE('ASRA') NODUMP END-EXEC"  # (a program check: the address names no storage of ours)
_SPAN = 65536  # an address is region * _SPAN + offset: the region is a top-level storage unit (docs, "Address model")
# The scratch cells of the address model, each emitted only when a lowering uses it: name -> PICTURE
_CELLS = {
    "RG": "S9(9) COMP-5 VALUE 0", "OF": "S9(9) COMP-5 VALUE 0", "B": "X", "BUF": "X(4)", "OUT": "X(4)",
    "T": "S9(18) COMP-5 VALUE 0", "U": "S9(18) COMP-5 VALUE 0", "X": "S9(18) COMP-5 VALUE 0",
    "Y": "S9(18) COMP-5 VALUE 0",
}  # fmt: skip
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
class Region:
    """A storage unit a register-held address can name: its id (the address divided by _SPAN), COBOL name, length."""

    id: int
    cobol: str
    length: int
    writable: bool


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
            # HLASM resumes a continuation at column 16 and wants columns 1-15 blank. zECS's ZECS002 starts `NOHANDLE` in
            # column 15; the CICS translator, which reads an EXEC CICS before the assembler does, takes the line's text
            # wherever it starts, so that is the rule for EXEC CICS. Any other statement is refused, never a letter dropped.
            if lines[i][:15].strip():
                if " ".join(body.split()[:3]).find("EXEC CICS") < 0:
                    raise Refused(f"line {i + 1}: continuation text before column 16")
                body += " " + lines[i][:71].strip()
            else:
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


def _args(text: str) -> list[str]:
    """The operands of an instruction: split at the commas outside parentheses and quotes."""
    out: list[str] = []
    cur, depth, quoted = "", 0, False
    for ch in text:
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch in "()":
            depth += 1 if ch == "(" else -1
        if ch == "," and depth == 0 and not quoted:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return [*out, cur]


# GnuCOBOL / IBM COBOL reserved words an assembler symbol can be spelled like (a DSECT field `PASSWORD`, a label `DATE`):
# cobc stops at one with "syntax error, unexpected PASSWORD" (#5859). The lowering gives such a name a suffix.
_RESERVED_WORDS = frozenset(
    re.findall(
        r"[A-Z0-9-]+",
        "ACCEPT ACCESS ADD ADDRESS ALL ALPHABET ALTER AND ARE AREA AREAS AT AUTHOR BEFORE BLANK BLOCK BY CALL CANCEL CD CF CH"
        " CHARACTER CLASS CLOSE CODE COLLATING COLUMN COMMA COMMON COMPUTE CONFIGURATION CONTAINS CONTENT CONTINUE CONTROL"
        " CONVERTING COPY CORR COUNT CURRENCY DATA DATE DAY DE DEBUGGING DECIMAL-POINT DELETE DELIMITED DELIMITER DEPENDING"
        " DESCENDING DESTINATION DETAIL DISABLE DISPLAY DIVIDE DIVISION DOWN DUPLICATES DYNAMIC EGI ELSE EMI ENABLE END ENTER"
        " ENVIRONMENT EOP EQUAL ERROR ESI EVALUATE EVERY EXCEPTION EXIT EXTEND EXTERNAL FALSE FD FILE FILLER FINAL FIRST FOOTING"
        " FOR FROM FUNCTION GENERATE GIVING GLOBAL GO GOBACK GROUP HEADING I-O ID IDENTIFICATION IF IN INDEX INDEXED INDICATE"
        " INITIAL INITIALIZE INITIATE INPUT INSPECT INSTALLATION INTO INVALID IS JUST JUSTIFIED KEY LABEL LAST LEADING LEFT"
        " LENGTH LIMIT LIMITS LINAGE LINE LINES LINKAGE LOCK MEMORY MERGE MESSAGE MODE MODULES MOVE MULTIPLE NATIVE NEGATIVE"
        " NEXT NO NOT NULL NUMBER NUMERIC OBJECT OCCURS OF OFF OMITTED ON OPEN OPTIONAL OR ORDER ORGANIZATION OTHER OUTPUT"
        " OVERFLOW PACKED-DECIMAL PADDING PAGE PASSWORD PERFORM PIC PICTURE PLUS POINTER POSITION POSITIVE PRINTING PROCEDURE"
        " PROCEED PROGRAM PROGRAM-ID PURGE QUEUE QUOTE QUOTES RANDOM RD READ RECEIVE RECORD RECORDS REDEFINES REEL REFERENCE"
        " REFERENCES RELATIVE RELEASE REMAINDER REMOVAL RENAMES REPLACE REPLACING REPORT REPORTS RERUN RESERVE RESET RETURN"
        " RETURNING REVERSED REWIND REWRITE RF RH RIGHT ROUNDED RUN SAME SD SEARCH SECTION SECURITY SEGMENT SELECT SEND SENTENCE"
        " SEPARATE SEQUENCE SEQUENTIAL SET SIGN SIZE SORT SORT-MERGE SOURCE SOURCES SPACE SPACES SPECIAL-NAMES STANDARD START"
        " STATUS STOP STRING SUB-QUEUE-1 SUBTRACT SUM SUPPRESS SYMBOLIC SYNC SYNCHRONIZED TABLE TALLYING TAPE TERMINAL TERMINATE"
        " TEST TEXT THAN THEN THROUGH THRU TIME TIMES TO TOP TRAILING TRUE TYPE UNIT UNSTRING UNTIL UP UPON USAGE USE USING"
        " VALUE VALUES VARYING WHEN WITH WORDS WORKING-STORAGE WRITE ZERO ZEROES ZEROS",
    )
)
_RESERVED_SUFFIX = "-HL"


def _cobol(name: str) -> str:
    out = name.upper().replace("_", "-")
    return out + _RESERVED_SUFFIX if out in _RESERVED_WORDS else out


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
        self.regions: dict[str, Region] = {}  # the units an `LA Rn,SYM` can put in a register
        self.cells: set[str] = set()  # the scratch cells (_CELLS, "N") the lowering uses
        self.unit: dict[int, Item] = {}  # id(item) -> the top-level item holding it

    def refuse(self, s: Stmt | None, what: str) -> Refused:
        return Refused(f"{what} at line {s.line}" if s else what)

    # ---- pass 1: storage ---------------------------------------------------------------------------------------
    def layout(self) -> None:
        section: str | None = None
        loc = 0
        groups: list[Item] = []  # open 0CLn groups
        entry: list[tuple[Stmt, str]] = []
        ext: Item | None = None  # the named X constant the next unnamed X rows of its width continue (a table)
        row = 0
        for s in self.stmts:
            if s.op in ("DSECT", "DFHEIENT"):
                ext = None
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
            dup = str(int(dup)) if dup else ""
            if dup == "1":
                dup = ""
            if (
                (dup not in ("", "0") and typ not in ("C", "X"))  # H / F / D copies need alignment and an array
                or (ln and typ in _SIZE)
                or (s.op == "DC" and val is None and dup != "0")
            ):
                raise self.refuse(s, f"{s.op} {s.operands}")
            length = int(ln) if ln else _SIZE.get(typ, 1) if typ != "C" or val is None else len(val.replace("''", "'"))
            if not ln and typ == "X" and val is not None:
                length = (len(val) + 1) // 2
            copies = int(dup) if dup not in ("", "0") else 1
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
                # the next row of a table: `T DC XL16'..'` then `DC XL16'..'`
                if (
                    ext is not None
                    and typ == "X"
                    and val is not None
                    and dup == ""
                    and length == row
                    and loc == ext.off + ext.length
                ):
                    ext.value = (ext.value or "") + (self._value(s, typ, length, val) or "")
                    ext.length += length
                    loc += length
                    continue
                ext = None
                continue  # an unnamed constant (the eyecatcher a `B` jumps around): nothing names or reads it
            if s.op == "DS" and section == "*CSECT":
                raise self.refuse(s, "DS storage in the program CSECT")
            value = self._value(s, typ, length, val)
            row = length
            if copies > 1:  # `n C/X` copies of one element: one field of n elements
                length *= copies
                value = value * copies if value is not None else None
            item = Item(s.label.upper() if s.label else "", section, loc, length, typ, value)
            self._place(s, item, groups)
            ext = item if item.name and typ == "X" and section == "*CSECT" and not groups and copies == 1 else None
            loc += length
            while groups and loc >= groups[-1].off + groups[-1].length:
                g = groups.pop()
                if loc != g.off + g.length:
                    raise self.refuse(s, f"{g.name} 0CL{g.length} not covered exactly by its fields")
        if not self.program:
            raise self.refuse(None, "no DFHEIENT entry")
        for s, r in entry:  # (the register EQUs follow the code)
            self.entry_regs.add(self._reg(s, r))
        for tops in self.sections.values():
            for top in tops:
                todo = [top]
                while todo:
                    it = todo.pop()
                    self.unit[id(it)] = top
                    todo += it.children

    def _place(self, s: Stmt, item: Item, groups: list[Item]) -> None:
        if item.name:
            if not _SYMBOL.match(item.name) or item.name in self.items:
                raise self.refuse(s, f"symbol {item.name}")
            if _cobol(item.name).endswith(_RESERVED_SUFFIX) and _cobol(item.name) in {_cobol(n) for n in self.items}:
                raise self.refuse(s, f"symbol {item.name} collides with its reserved-word rename")
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
        for s in code:  # the units an `LA Rn,SYM` puts in a register, before any code dereferences one
            arg = _args(s.operands)[-1].strip() if s.op == "LA" else ""
            m = re.fullmatch(r"([A-Z][A-Z0-9_]*)(?:\+\d+)?", arg, re.I)
            if m and self._number(arg) is None and m.group(1).upper() in self.items:
                self.region(s, self.items[m.group(1).upper()])
        proc = self._procedure(code)
        lines = self._data() + proc
        for line in lines:  # fixed format ends at column 72: a longer line would lose its tail silently
            if len(line) > 72:
                raise Refused(f"generated line past column 72: {line.strip()[:40]}")
        return "\n".join(lines) + "\n"

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
            ops = _args(s.operands) if s.op != "EXEC" else []
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
            v = ops[1].strip() if len(ops) == 2 else ""
            n = self._number(v)
            if n is not None:
                if not 0 <= n <= 4095:
                    raise self.refuse(s, f"LA of an address ({s.operands})")
                return [f"           MOVE {n} TO {reg}"]
            dyn = self.operand(s, v)
            if dyn is not None:  # LA Rn,d(,Rm): the address plus d, in 31 bits (POPS, LOAD ADDRESS)
                if dyn[0] != "dyn" or dyn[3] is not None:
                    raise self.refuse(s, f"LA {s.operands} (an index register)")
                plus = f" + {dyn[2]}" if dyn[2] else ""
                return [f"           COMPUTE {reg} =", f"               FUNCTION MOD({dyn[1]}{plus}, 2147483648)"]
            item, disp, _ = self.storage(s, v)
            region, off = self.region(s, item)
            return [f"           MOVE {region.id * _SPAN + off + disp} TO {reg}"]
        if op == "IC":
            if len(ops) != 2:
                raise self.refuse(s, f"IC {s.operands}")
            reg = self.work_reg(s, ops[0])
            self.cells.add("N")
            return [  # POPS: the byte replaces bits 24-31 of the register, its other bits stay
                *self._fetch(s, ops[1]),
                "           MOVE HL-B TO HL-LO",
                f"           COMPUTE {reg} = {reg} - FUNCTION MOD({reg}, 256) + HL-N",
            ]
        if op in ("SLL", "SLDL"):
            return self._shift(s, ops)
        if op == "STCM":
            return self._stcm(s, ops)
        if op == "TR":
            return self._tr(s, ops)
        if op == "SR":
            if len(ops) != 2 or self._reg(s, ops[0]) != self._reg(s, ops[1]):
                raise self.refuse(s, f"SR {s.operands} (only SR Rn,Rn, a register clear)")
            return [f"           MOVE 0 TO {self.work_reg(s, ops[0])}"]
        if op == "XC":
            if len(ops) != 2:
                raise self.refuse(s, f"XC {s.operands}")
            item, disp, length = self.storage(s, ops[0])
            other, odisp, olen = self.storage(s, ops[1])
            if (other, odisp) != (item, disp) or olen < length:  # `XC X(n),X` is the same field, as for OC X,X
                raise self.refuse(s, f"XC {s.operands} (only XC X,X, a field clear)")
            if item.typ in ("H", "F", "D") or item.doubleword:
                raise self.refuse(s, "XC on binary fields")
            self._writable(s, item)
            return [f"           MOVE LOW-VALUES TO {self.ref(item, disp, length)}"]
        if op == "BCT":
            if len(ops) != 2:
                raise self.refuse(s, f"BCT {s.operands}")
            reg, tgt = self.work_reg(s, ops[0]), self.target(s, ops[1])
            return [  # POPS: subtract 1 from the fullword (wrapping), branch while the result is not zero; CC unchanged
                f"           COMPUTE {reg} =",
                f"               FUNCTION MOD({reg} - 1 + 2147483648, 4294967296)",
                "               - 2147483648",
                f"           IF {reg} NOT = 0",
                f"               GO TO {tgt}",
                "           END-IF",
            ]
        if op == "MVC":
            dst_op = self.operand(s, ops[0], True)
            if dst_op is not None or (len(ops) == 2 and self.operand(s, ops[1], True) is not None):
                n = self.storage(s, ops[0])[2] if dst_op is None else (dst_op[3] or 1) if dst_op[0] == "dyn" else 0
                if n != 1:  # (a longer copy through a register may overlap itself, byte by byte: not modelled)
                    raise self.refuse(s, f"MVC {s.operands} (only one byte through a register)")
                return [*self._fetch(s, ops[1], True), *self._store(s, ops[0], 1, "HL-B")]
            lit = re.fullmatch(r"=C'((?:[^'&]|'')*)'", ops[1].strip(), re.I) if len(ops) == 2 else None
            if lit:  # a literal-pool constant: the destination must be exactly its length
                text = lit.group(1).replace("''", "'")
                dst, dd, dl = self.storage(s, ops[0])
                if dl != len(text) or dst.typ in ("H", "F", "D") or dst.doubleword:
                    raise self.refuse(s, f"MVC {s.operands}")
                self._writable(s, dst)
                return [f"           MOVE {_quote(text)}", f"             TO {self.ref(dst, dd, dl)}"]
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
        if op == "CLI" and self.operand(s, ops[0]) is not None:
            return self._fetch(s, ops[0])  # the byte is compared by the BC that follows (_compare_operands)
        if op in ("CLC", "CLI", "OC"):
            return []  # set the condition code only (OC X,X leaves X as it is): read by the next BC
        raise self.refuse(s, f"instruction {op}")

    # ---- the address model (slice 3b) ----------------------------------------------------------------------------
    def _number(self, text: str) -> int | None:
        t = text.strip().upper()
        return int(t) if t.isdigit() else self.equ.get(t)

    def operand(self, s: Stmt, text: str, ss: bool = False) -> tuple | None:
        """`d(b)`, `d(,b)`, `d(l,b)` (ss: an SS-format operand, where the first field is a length) ->
        ("dyn", base cell, d, length | None); `SYM(x)`, a symbol indexed by a register -> ("idx", item, d, cell);
        None for a plain symbol (storage())."""
        m = _DYN.fullmatch(text.strip())
        if not m:
            return None
        d, x, b = m.group(1).strip(), m.group(2).strip(), m.group(3)
        disp = 0 if not d else self._number(d)
        if disp is not None:
            if not 0 <= disp <= 4095:
                raise self.refuse(s, f"displacement {text}")
            if b is None:
                return ("dyn", self.work_reg(s, x), disp, None)
            length = self._number(x) if x else None
            if x and (length is None or not ss):
                raise self.refuse(s, f"index register in {text}")
            return ("dyn", self.work_reg(s, b), disp, length)
        if b is None and x and not x.isdigit():
            item, sdisp, _ = self.storage(s, d)
            return ("idx", item, sdisp, self.work_reg(s, x))
        return None

    def _unit(self, s: Stmt, item: Item) -> tuple[str, str, int, int, bool]:
        """(key, COBOL name, offset of `item` in the unit, unit length, writable) of the storage an address into `item`
        reaches: the top-level 01 of DFHEISTG or the program CSECT, or the whole COMMAREA."""
        if item.section == "*EIB":
            raise self.refuse(s, f"address of the EIB field {item.name}")
        if item.section in ("DFHEISTG", "*CSECT"):
            top = self.unit[id(item)]
            if not top.name:
                raise self.refuse(s, f"address into unnamed storage ({item.name or 'FILLER'})")
            tops, key, cob, base, length = [top], top.name, _cobol(top.name), top.off, top.length
        else:
            tops = self.sections[item.section]
            key, cob, base = item.section, "DFHCOMMAREA", 0
            length = max(t.off + t.length for t in tops)
        todo = list(tops)
        while todo:
            it = todo.pop()
            if it.typ in ("H", "F", "D") or it.doubleword:  # (the bytes of a binary field differ: little endian here)
                raise self.refuse(s, f"address into {cob}, which holds the binary field {it.name or 'FILLER'}")
            if it.typ == "C" and it.value is not None:  # (a C constant is ASCII here and EBCDIC on z/OS)
                raise self.refuse(s, f"address into {cob}, which holds the character constant {it.name or 'FILLER'}")
            todo += it.children
        return key, cob, item.off - base, length, item.section != "*CSECT"

    def region(self, s: Stmt, item: Item) -> tuple[Region, int]:
        """The Region an address of `item` lies in (registered on first use) and the offset of `item` in it."""
        key, cob, off, length, writable = self._unit(s, item)
        region = self.regions.get(key)
        if region is None:
            region = self.regions[key] = Region(len(self.regions) + 1, cob, length, writable)
        return region, off

    def _locate(self, cell: str, disp: int) -> list[str]:
        """HL-RG, HL-OF := the region and offset of the address in `cell`, plus `disp`."""
        self.cells |= {"RG", "OF"}
        out = [f"           DIVIDE {cell} BY {_SPAN} GIVING HL-RG REMAINDER HL-OF"]
        return [*out, f"           ADD {disp} TO HL-OF"] if disp else out

    def _switch(self, n: int, write: bool, action: Callable[[str], list[str]]) -> list[str]:
        """`action(region name)` for the `n` bytes at HL-OF of the region HL-RG names; an address outside every region
        that can hold one (or past its end, or a store into a constant) is a program check: ASRA."""
        out = ["           EVALUATE HL-RG"]
        for r in self.regions.values():
            if r.length < n or (write and not r.writable):
                continue
            out += [
                f"               WHEN {r.id}",
                f"                   IF HL-OF < 0 OR HL-OF > {r.length - n}",
                f"                       {_ASRA}",
                "                   ELSE",
                *(f"                       {line}" for line in action(r.cobol)),
                "                   END-IF",
            ]
        return [*out, "               WHEN OTHER", f"                   {_ASRA}", "           END-EVALUATE"]

    def _plain(self, s: Stmt, item: Item) -> None:
        if item.typ in ("H", "F", "D") or item.doubleword or (item.typ == "C" and item.value is not None):
            raise self.refuse(s, f"byte of {item.name} ({item.typ})")

    def _fetch(self, s: Stmt, text: str, ss: bool = False) -> list[str]:
        """Lines leaving the first byte of the operand in HL-B."""
        self.cells.add("B")
        op = self.operand(s, text, ss)
        if op is None:
            item, disp, _ = self.storage(s, text)
            self._plain(s, item)
            return [f"           MOVE {self.ref(item, disp, 1)} TO HL-B"]
        if op[0] == "idx":  # IC R5,TABLE(R5): the register is the byte offset into the table
            _, item, disp, cell = op
            _, cob, off, length, _w = self._unit(s, item)
            self.cells.add("OF")
            return [
                f"           COMPUTE HL-OF = {off + disp} + {cell}",
                f"           IF HL-OF < 0 OR HL-OF > {length - 1}",
                f"               {_ASRA}",
                "           ELSE",
                f"               MOVE {cob}(HL-OF + 1:1) TO HL-B",
                "           END-IF",
            ]
        return [*self._locate(op[1], op[2]), *self._switch(1, False, lambda r: [f"MOVE {r}(HL-OF + 1:1) TO HL-B"])]

    def _store(self, s: Stmt, text: str, n: int, src: str) -> list[str]:
        """Lines storing the `n` bytes `src` (a COBOL operand) at the operand."""
        op = self.operand(s, text, True)
        if op is None:
            item, disp, length = self.storage(s, text)
            if length < n:
                raise self.refuse(s, f"store of {n} bytes into {text}")
            self._plain(s, item)
            self._writable(s, item)
            return [f"           MOVE {src}", f"             TO {self.ref(item, disp, n)}"]
        if op[0] == "idx" or (op[3] is not None and op[3] != n):
            raise self.refuse(s, f"store through {text}")
        return [
            *self._locate(op[1], op[2]),
            *self._switch(n, True, lambda r: [f"MOVE {src}", f"  TO {r}(HL-OF + 1:{n})"]),
        ]

    def _byte_literal(self, s: Stmt, text: str) -> str:
        """The byte of `C'x'` (EBCDIC cp037, as z/OS compares it) or `X'hh'`, as a COBOL hex literal."""
        lit = re.fullmatch(r"([CX])'([^']*)'", text.strip(), re.I)
        if not lit:
            raise self.refuse(s, f"CLI {s.operands}")
        if lit.group(1).upper() == "X":
            if not re.fullmatch(r"[0-9A-F]{2}", lit.group(2), re.I):
                raise self.refuse(s, f"CLI {s.operands}")
            return f"X'{lit.group(2).upper()}'"
        if len(lit.group(2)) != 1:
            raise self.refuse(s, f"CLI {s.operands}")
        return f"X'{lit.group(2).encode('cp037').hex().upper()}'"

    def _shift(self, s: Stmt, ops: list[str]) -> list[str]:
        """SLL Rn,k (a 32-bit logical left shift) and SLDL Rn,k (the even/odd pair as one 64-bit value): POPS, chapter 7.
        k is an immediate here; no condition code is set."""
        k = self._number(ops[1]) if len(ops) == 2 else None
        if k is None or not 0 <= k <= 63:
            raise self.refuse(s, f"{s.op} {s.operands} (a shift count that is not an immediate)")
        reg = self.work_reg(s, ops[0])

        def wrap(dst: str, src: str) -> list[str]:  # (to a signed 32-bit value)
            return [
                f"           COMPUTE {dst} =",
                f"               FUNCTION MOD({src} + 2147483648, 4294967296)",
                "               - 2147483648",
            ]

        if s.op == "SLL":
            if k == 0:
                return []
            if k >= 32:
                return [f"           MOVE 0 TO {reg}"]
            self.cells.add("T")
            return [
                f"           COMPUTE HL-T = FUNCTION MOD({reg}, {2 ** (32 - k)}) * {2**k}",
                *wrap(reg, "HL-T"),
            ]
        n = self._reg(s, ops[0])
        if n % 2 or n + 1 in self.entry_regs:
            raise self.refuse(s, f"SLDL on {ops[0]}: not an even register with a free odd partner")
        odd = self.work_reg(s, str(n + 1))
        if not 0 < k < 32:
            raise self.refuse(s, f"SLDL by {k} (only 1 to 31)")
        self.cells |= {"T", "U", "X", "Y"}
        m, f = 2 ** (32 - k), 2**k
        return [  # even' = (even mod 2^(32-k)) * 2^k + (odd div 2^(32-k)), odd' = (odd mod 2^(32-k)) * 2^k, unsigned
            f"           COMPUTE HL-U = FUNCTION MOD({reg}, 4294967296)",
            f"           COMPUTE HL-T = FUNCTION MOD({odd}, 4294967296)",
            f"           DIVIDE HL-T BY {m} GIVING HL-X REMAINDER HL-Y",
            f"           COMPUTE HL-U = FUNCTION MOD(HL-U, {m}) * {f} + HL-X",
            f"           COMPUTE HL-T = HL-Y * {f}",
            *wrap(reg, "HL-U"),
            *wrap(odd, "HL-T"),
        ]

    def _stcm(self, s: Stmt, ops: list[str]) -> list[str]:
        """STCM Rn,mask,d(b): the bytes of the register the mask picks (bit 8 the high byte), stored side by side."""
        if len(ops) != 3:
            raise self.refuse(s, f"STCM {s.operands}")
        reg, mask = self.work_reg(s, ops[0]), self._mask(ops[1])
        if mask is None or mask == 0:
            raise self.refuse(s, f"STCM mask {ops[1]}")
        picked = [i for i in range(4) if mask & (8 >> i)]
        self.cells |= {"T", "U", "X", "BUF", "OUT", "N"}
        lines = [f"           COMPUTE HL-T = FUNCTION MOD({reg}, 4294967296)"]
        for pos, (src, dst) in zip((4, 3, 2), (("T", "U"), ("U", "T"), ("T", "U")), strict=True):
            lines += [
                f"           DIVIDE HL-{src} BY 256 GIVING HL-{dst} REMAINDER HL-X",
                "           MOVE HL-X TO HL-N",
                f"           MOVE HL-LO TO HL-BUF({pos}:1)",
            ]
        lines += ["           MOVE HL-U TO HL-N", "           MOVE HL-LO TO HL-BUF(1:1)"]
        lines += [f"           MOVE HL-BUF({i + 1}:1) TO HL-OUT({j + 1}:1)" for j, i in enumerate(picked)]
        return [*lines, *self._store(s, ops[2], len(picked), f"HL-OUT(1:{len(picked)})")]

    def _mask(self, text: str) -> int | None:
        return _mask(text) if _mask(text) is not None else self._number(text)

    def _tr(self, s: Stmt, ops: list[str]) -> list[str]:
        """TR d(l,b),TABLE: each of the l bytes is replaced by the table byte its value indexes (POPS: TRANSLATE)."""
        if len(ops) != 2:
            raise self.refuse(s, f"TR {s.operands}")
        table, tdisp, _ = self.storage(s, ops[1])
        _, tcob, toff, tlen, _w = self._unit(s, table)
        if tlen < toff + tdisp + 256:
            raise self.refuse(s, f"TR table {table.name} shorter than 256 bytes")
        dst = self.operand(s, ops[0], True)
        self.cells |= {"N"}
        pick = f"MOVE {tcob}(HL-N + {toff + tdisp + 1}:1)"
        if dst is None:
            item, disp, n = self.storage(s, ops[0])
            self._plain(s, item)
            self._writable(s, item)
            if self._unit(s, item)[1] == tcob:
                raise self.refuse(s, "TR over its own table")
            if n > 16:
                raise self.refuse(s, f"TR of {n} bytes (only up to 16)")
            out: list[str] = []
            for i in range(n):
                at = self.ref(item, disp + i, 1)
                out += [f"           MOVE {at} TO HL-LO", f"           {pick}", f"             TO {at}"]
            return out
        if dst[0] == "idx" or not 1 <= (dst[3] or 1) <= 16:
            raise self.refuse(s, f"TR {s.operands}")
        n = dst[3] or 1

        def action(r: str) -> list[str]:
            out = []
            for i in range(1, n + 1):
                at = f"{r}(HL-OF + {i}:1)"
                out += [f"MOVE {at} TO HL-LO", pick, f"  TO {at}"]
            return out

        return [*self._locate(dst[1], dst[2]), *self._switch(n, True, action)]

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
        ops = [o.strip() for o in _args(setter.operands)]
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
        if s.op == "CLI" and self.operand(s, ops[0]) is not None:
            return "HL-B", self._byte_literal(s, ops[1])
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
        if self.cells:
            out.append("       01  HL-WORK.")
            out += [f"           05  HL-{n} PIC {pic}." for n, pic in _CELLS.items() if n in self.cells]
        if "N" in self.cells:  # a byte as a number and back: the low byte of a 2-byte binary (big endian)
            out += [
                "       01  HL-W2.",
                "           05  HL-HI PIC X VALUE LOW-VALUE.",
                "           05  HL-LO PIC X VALUE LOW-VALUE.",
                "       01  HL-N REDEFINES HL-W2 PIC 9(4) COMP.",
            ]
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
        if it.typ == "X" and len(it.value) <= 40:
            return [f"{ind}{lvl}  {name} PIC X({it.length})", f"{ind}        VALUE X'{it.value}'."]
        if it.typ == "X":  # a table: one FILLER per 16 bytes, as a long C value is split
            out = [f"{ind}{lvl}  {name}."]
            sub = f"{level + 5 if level > 1 else 5:02d}"
            for i in range(0, len(it.value), 32):
                part = it.value[i : i + 32]
                out += [f"{ind}    {sub}  FILLER PIC X({len(part) // 2})", f"{ind}        VALUE X'{part}'."]
            return out
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
