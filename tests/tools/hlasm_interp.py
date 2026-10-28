"""#5859 slice 4: an independent interpreter for the HLASM + EXEC CICS subset the zECS programs use.

It cross-checks det/hlasm.py (the lowering to COBOL). It is written from the z/Architecture Principles of Operation
(SA22-7832) and the HLASM Language Reference (SC26-4940) alone and imports nothing from the lowering: storage is one flat
byte array holding EBCDIC (cp037) data, registers are 32-bit, an address is a number, the condition code is a real
2-bit value. It is a test instrument, not a translator input, so it lives here and not under det/ (the translator
fingerprint, evidence_report.TRANSLATOR_INPUTS, reads det/).

Scope: the instructions of the lowering's subset (B BC BCR BAS L LA ST STH CH CLC CLI MVC OC SR XC BCT IC STCM TR SLL
SLDL) and the EXEC CICS commands ZECS002 and ZECSNC issue, which are recorded as events and answered from the scenario's
facts. Anything else raises `Unsupported`, so a program is interpreted whole or not at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EBCDIC = "cp037"
M32 = 0xFFFFFFFF
WS, EIB, CA, DATA, POOL, CODE = 0x1000, 0x3000, 0x4000, 0x8000, 0xF000, 0x100000
RESP = {"NORMAL": 0, "ERROR": 1, "INVREQ": 16, "LENGERR": 22, "USERIDERR": 69, "NOTAUTH": 70, "DUPREC": 14}
# the EIB fields the programs read, with this interpreter's own offsets (a program that does no arithmetic on the block
# cannot observe them): name -> (offset, length)
EIB_FIELDS = {"EIBTRNID": (0, 4), "EIBCALEN": (4, 2), "EIBRESP": (8, 4), "EIBRESP2": (12, 4), "DFHEICAP": (16, 4)}


class Unsupported(ValueError):
    pass


@dataclass
class Stmt:
    line: int
    label: str
    op: str
    operands: str


@dataclass
class Sym:
    section: str  # WS | CA | EIB | DATA | CODE | ABS
    off: int
    length: int = 1


@dataclass
class Result:
    events: list[tuple] = field(default_factory=list)
    outcome: str = ""  # RETURN | ABEND:<code>
    commarea: bytes = b""
    regs: list[int] = field(default_factory=list)
    mem: bytearray = field(default_factory=bytearray)
    steps: int = 0


def _scan_fields(text: str) -> tuple[str, str]:
    """The operand field is the text to the first blank outside quotes and parentheses."""
    depth, quoted = 0, False
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch in " \t":
            return text[:i], text[i:]
    return text, ""


def parse(text: str) -> list[Stmt]:
    """Fixed-format cards: columns 1-71 are the statement, a mark in column 72 (or a lone one drifted to 73) continues it
    on the next card from column 16."""
    out: list[Stmt] = []
    cards = text.replace("\r", "").split("\n")
    i = 0
    while i < len(cards):
        card, line = cards[i], i + 1
        i += 1
        if not card.strip() or card.startswith("*") or card.startswith(".*"):
            continue
        body = card[:71].rstrip()
        while (len(card) > 71 and card[71] != " ") or (len(card.rstrip()) == 73 and card[71] == " "):
            if i >= len(cards):
                break
            card = cards[i]
            i += 1
            body = body.rstrip() + " " + card[15:71].strip()
        label = body[:8].strip() if body[:1] != " " else ""
        rest = body[len(label) :].lstrip() if label else body.lstrip()
        label = label if label else ""
        if body[:1] != " ":
            parts = body.split(None, 1)
            label, rest = parts[0], parts[1] if len(parts) > 1 else ""
        op, _, tail = rest.partition(" ")
        if op == "EXEC":
            out.append(Stmt(line, label, "EXEC", tail.strip()))
            continue
        operands, _ = _scan_fields(tail.lstrip())
        out.append(Stmt(line, label.upper(), op.upper(), operands))
    return out


def _split_top(text: str) -> list[str]:
    parts, depth, quoted, cur = [], 0, False, ""
    for ch in text:
        if ch == "'":
            quoted = not quoted
        if not quoted and ch == "(":
            depth += 1
        if not quoted and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _const_bytes(typ: str, length: int | None, val: str) -> bytes:
    if typ == "C":
        raw = val.replace("''", "'").replace("&&", "&").encode(EBCDIC)
        n = length if length is not None else len(raw)
        return raw[:n].ljust(n, b"\x40")
    if typ == "X":
        digits = val
        n = length if length is not None else (len(digits) + 1) // 2
        digits = digits.zfill(2 * n)[-2 * n :] if length is not None else digits + ("0" * (len(digits) % 2))
        return bytes.fromhex(digits)
    if typ == "H":
        return (int(val) & 0xFFFF).to_bytes(2, "big")
    if typ == "F":
        return (int(val) & M32).to_bytes(4, "big")
    raise Unsupported(f"DC type {typ}")


_DC = re.compile(r"^(\d*)([CXHFD])(?:L(\d+))?(?:'((?:[^']|'')*)')?$", re.I)
_ALIGN = {"H": 2, "F": 4, "D": 8}
_SIZE = {"H": 2, "F": 4, "D": 8}


def _counter_name_ok(name: str) -> bool:
    """IBM (EXEC CICS DEFINE COUNTER / DCOUNTER): A-Z $ @ # first, then also 0-9 and _; no embedded or leading blanks."""
    return bool(name) and all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ$@#" or (i and c in "0123456789_") for i, c in enumerate(name)
    )


class Machine:
    def __init__(self, source: str):
        self.stmts = parse(source)
        self.mem = bytearray(0x20000)
        self.syms: dict[str, Sym] = {}
        self.equ: dict[str, int] = {}
        self.code: list[Stmt] = []
        self.labels: dict[str, int] = {}
        self.using: dict[str, int] = {}  # DSECT name -> register
        self.sect_of: dict[str, str] = {}
        self.pool_next = POOL
        self.pool: dict[tuple, int] = {}
        self._layout()

    # ---- storage layout -------------------------------------------------------------------------------------------
    def _layout(self) -> None:
        sec, loc = "", 0
        data_next = DATA
        for name, (off, ln) in EIB_FIELDS.items():
            self.syms[name] = Sym("EIB", off, ln)
        for s in self.stmts:
            if s.op == "DSECT":
                sec, loc = s.label, 0
                self.sect_of[sec] = "WS" if sec == "DFHEISTG" else "CA"
                continue
            if s.op == "DFHEIENT":
                sec = "*CSECT"
                continue
            if s.op == "EQU":
                m = re.fullmatch(r"\*-([A-Z0-9_]+)", s.operands, re.I)
                if m:
                    self.equ[s.label] = loc - self.syms[m.group(1).upper()].off
                else:
                    self.equ[s.label] = int(s.operands)
                continue
            if s.op in ("DS", "DC"):
                m = _DC.match(s.operands)
                if not m:
                    raise Unsupported(f"{s.op} {s.operands}")
                dup, typ, ln, val = m.group(1), m.group(2).upper(), m.group(3), m.group(4)
                n = int(dup) if dup else 1
                unit = (
                    int(ln)
                    if ln
                    else (_SIZE[typ] if typ in _SIZE else (len(_const_bytes(typ, None, val)) if val is not None else 1))
                )
                if typ in _ALIGN and sec != "*CSECT":
                    loc = -(-loc // _ALIGN[typ]) * _ALIGN[typ]
                if sec == "*CSECT":
                    if typ in _ALIGN:
                        data_next = -(-data_next // _ALIGN[typ]) * _ALIGN[typ]
                    if dup == "0":
                        if s.label and typ in _ALIGN:
                            self.labels[s.label] = len(self.code)  # DS 0H: a code label
                        elif s.label:
                            self.syms[s.label] = Sym("DATA", data_next - DATA, unit)  # DC 0CLn: a group header
                        continue
                    blob = (
                        _const_bytes(typ, int(ln) if ln else None, val)
                        if s.op == "DC" and val is not None
                        else b"\0" * unit
                    )
                    blob = blob * n
                    if s.label:
                        self.syms[s.label] = Sym("DATA", data_next - DATA, unit if n == 1 else len(blob))
                    self.mem[data_next : data_next + len(blob)] = blob
                    data_next += len(blob)
                    continue
                if dup == "0":
                    if s.label:
                        self.syms[s.label] = Sym(self.sect_of[sec], loc, unit)
                    continue
                if s.label:
                    self.syms[s.label] = Sym(self.sect_of[sec], loc, unit * n if typ in "CX" else unit)
                loc += unit * n
                continue
            if sec == "*CSECT" and s.op not in ("AMODE", "RMODE", "USING", "LTORG", "PRINT", "END", "CSECT"):
                if s.label:
                    self.labels[s.label] = len(self.code)
                self.code.append(s)
            elif s.op == "USING":
                d, _, r = s.operands.partition(",")
                self.using[d] = int(self.equ[r]) if r in self.equ else int(r[1:])
            elif s.label and sec == "*CSECT":
                self.labels[s.label] = len(self.code)

    # ---- operands -------------------------------------------------------------------------------------------------
    def _disp(self, text: str) -> int | tuple[str, int]:
        """A displacement or symbolic address: a number, an EQU, SYM[+/-n]; the symbol's own address is resolved by `_addr`."""
        text = text.strip()
        m = re.fullmatch(r"([A-Z_][A-Z0-9_]*)\s*([+-]\s*\d+)?", text, re.I)
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        if not m:
            raise Unsupported(f"displacement {text}")
        name = m.group(1).upper()
        add = int(m.group(2).replace(" ", "")) if m.group(2) else 0
        if name in self.equ:
            return self.equ[name] + add
        return (name, add)

    def _base_of(self, sym: Sym, regs: list[int]) -> int:
        return {"WS": WS, "EIB": EIB, "DATA": DATA}.get(sym.section) or regs[self.using["DFHCA"]]

    def _lenattr(self, text: str) -> int:
        d = self._disp(text.split("(")[0])
        if isinstance(d, tuple):
            return self.syms[d[0]].length
        raise Unsupported(f"length of {text}")

    def _ss_len(self, text: str) -> int | None:
        m = re.search(r"\((\d+)[,)]", text)  # D(L,B) or D(L): a bare number in an SS first operand is the length
        return int(m.group(1)) if m else None

    def _address(self, text: str, regs: list[int], ss_first: bool = False) -> int:
        """Resolve an address operand; a literal `=C'..'` goes to the pool."""
        text = text.strip()
        if text.startswith("="):
            return self._literal(text[1:])
        m = re.fullmatch(r"([^()]*)(?:\(([^()]*)\))?", text)
        if not m:
            raise Unsupported(f"operand {text}")
        d = self._disp(m.group(1) or "0")
        if isinstance(d, tuple):
            name, add = d
            if name not in self.syms:
                raise Unsupported(f"symbol {name}")
            sym = self.syms[name]
            total = self._base_of(sym, regs) + sym.off + add
        else:
            total = d
        parts = [p.strip() for p in (m.group(2) or "").split(",")]
        if ss_first and len(parts) == 2:
            parts = parts[1:]  # D(L,B): the first item is a length
        for r in parts:
            if r and not r.isdigit():
                n = self.equ[r.upper()]
                total += regs[n] if n else 0
        return total & 0x7FFFFFFF

    def _literal(self, text: str) -> int:
        m = re.fullmatch(r"([CXHF])(?:L(\d+))?'((?:[^']|'')*)'", text, re.I)
        if not m:
            raise Unsupported(f"literal ={text}")
        blob = _const_bytes(m.group(1).upper(), int(m.group(2)) if m.group(2) else None, m.group(3))
        key = (text,)
        if key not in self.pool:
            self.pool[key] = self.pool_next
            self.mem[self.pool_next : self.pool_next + len(blob)] = blob
            self.pool_next += len(blob) + 8
        return self.pool[key]

    def _lit_len(self, text: str) -> int:
        m = re.fullmatch(r"=([CXHF])(?:L(\d+))?'((?:[^']|'')*)'", text.strip(), re.I)
        if not m:
            raise Unsupported(f"literal {text}")
        return len(_const_bytes(m.group(1).upper(), int(m.group(2)) if m.group(2) else None, m.group(3)))

    def _imm(self, text: str) -> int:
        text = text.strip()
        m = re.fullmatch(r"([CXB])'((?:[^']|'')*)'", text, re.I)
        if m:
            t, v = m.group(1).upper(), m.group(2)
            return v.replace("''", "'").encode(EBCDIC)[0] if t == "C" else int(v, 16) if t == "X" else int(v, 2)
        d = self._disp(text)
        if isinstance(d, tuple):
            raise Unsupported(f"immediate {text}")
        return d

    def _reg(self, text: str) -> int:
        t = text.strip().upper()
        return (
            int(t[1:]) if re.fullmatch(r"R\d+", t) and t not in self.equ else self.equ[t] if t in self.equ else int(t)
        )

    # ---- execution ------------------------------------------------------------------------------------------------
    def run(self, commarea: bytes, *, facts: dict | None = None, max_steps: int = 200000) -> Result:
        facts = facts or {}
        res = Result(mem=self.mem)
        mem = self.mem
        regs = [0] * 16
        cc = 0
        mem[WS : WS + 0x1000] = (
            bytes([facts.get("fill", 0)]) * 0x1000
        )  # DFHEISTG is not initialised (design doc assumption 2)
        mem[CA : CA + len(commarea)] = commarea
        for name, v in (
            ("EIBTRNID", facts.get("transid", "ZSEC").ljust(4).encode(EBCDIC)),
            ("EIBCALEN", len(commarea).to_bytes(2, "big")),
            ("EIBRESP", bytes(4)),
            ("DFHEICAP", CA.to_bytes(4, "big")),
        ):
            off, ln = EIB_FIELDS[name]
            mem[EIB + off : EIB + off + ln] = v
        regs[10], regs[11], regs[12] = WS, EIB, CODE
        pc = 0

        def rd(a: int, n: int) -> bytes:
            return bytes(mem[a : a + n])

        def wr(a: int, b: bytes) -> None:
            mem[a : a + len(b)] = b

        def fetch_len(sym_text: str) -> int:
            return self._lenattr(sym_text)

        while True:
            if pc >= len(self.code):
                raise Unsupported("fell off the end of the program")
            res.steps += 1
            if res.steps > max_steps:
                raise Unsupported("step limit")
            s = self.code[pc]
            pc += 1
            op, ops = s.op, _split_top(s.operands) if s.op != "EXEC" else []
            if op == "EXEC":
                outcome = self._cics(s.operands, regs, facts, res, mem)
                if outcome:
                    res.outcome = outcome
                    break
                continue
            if op in ("B", "BC"):
                mask = 15 if op == "B" else self._imm(ops[0])
                target = ops[-1].strip()
                if mask & (8 >> cc):
                    pc = self.labels[target.upper()]
            elif op == "BCR":
                mask, r = self._imm(ops[0]), self._reg(ops[1])
                if mask & (8 >> cc) and r != 0:
                    pc = (regs[r] - CODE) // 8
            elif op == "BAS":
                r = self._reg(ops[0])
                regs[r] = CODE + 8 * pc
                pc = self.labels[ops[1].strip().upper()]
            elif op == "BCT":
                r = self._reg(ops[0])
                regs[r] = (regs[r] - 1) & M32
                if regs[r] != 0:
                    pc = self.labels[ops[1].strip().upper()]
            elif op == "L":
                regs[self._reg(ops[0])] = int.from_bytes(rd(self._address(ops[1], regs), 4), "big")
            elif op == "LA":
                regs[self._reg(ops[0])] = self._address(ops[1], regs)
            elif op == "ST":
                wr(self._address(ops[1], regs), regs[self._reg(ops[0])].to_bytes(4, "big"))
            elif op == "STH":
                wr(self._address(ops[1], regs), (regs[self._reg(ops[0])] & 0xFFFF).to_bytes(2, "big"))
            elif op == "CH":
                a = regs[self._reg(ops[0])]
                a = a - (1 << 32) if a & 0x80000000 else a
                b = int.from_bytes(rd(self._address(ops[1], regs), 2), "big")
                b = b - (1 << 16) if b & 0x8000 else b
                cc = 0 if a == b else 1 if a < b else 2
            elif op == "CLC":
                n = self._ss_len(ops[0]) or (self._lit_len(ops[0]) if ops[0].startswith("=") else fetch_len(ops[0]))
                a = rd(self._address(ops[0], regs, True), n)
                b = rd(self._address(ops[1], regs), n)
                cc = 0 if a == b else 1 if a < b else 2
            elif op == "CLI":
                a = rd(self._address(ops[0], regs), 1)[0]
                b = self._imm(ops[1])
                cc = 0 if a == b else 1 if a < b else 2
            elif op in ("MVC", "OC", "XC"):
                n = self._ss_len(ops[0]) or fetch_len(ops[0])
                dst = self._address(ops[0], regs, True)
                src = self._address(ops[1], regs)
                if op == "MVC":
                    for k in range(n):  # byte by byte, left to right: an overlap propagates (POPS)
                        mem[dst + k] = mem[src + k]
                else:
                    acc = 0
                    for k in range(n):
                        mem[dst + k] = (mem[dst + k] | mem[src + k]) if op == "OC" else (mem[dst + k] ^ mem[src + k])
                        acc |= mem[dst + k]
                    cc = 0 if acc == 0 else 1
            elif op == "SR":
                a, b = self._reg(ops[0]), self._reg(ops[1])
                sa = regs[a] - (1 << 32) if regs[a] & 0x80000000 else regs[a]
                sb = regs[b] - (1 << 32) if regs[b] & 0x80000000 else regs[b]
                d = sa - sb
                cc = 3 if d < -(1 << 31) or d >= (1 << 31) else 0 if d == 0 else 1 if d < 0 else 2
                regs[a] = d & M32
            elif op == "IC":
                r = self._reg(ops[0])
                regs[r] = (regs[r] & 0xFFFFFF00) | mem[self._address(ops[1], regs)]
            elif op == "STCM":
                r, mask = self._reg(ops[0]), self._imm(ops[1])
                a = self._address(ops[2], regs)
                for k in range(4):
                    if mask & (8 >> k):
                        mem[a] = (regs[r] >> (24 - 8 * k)) & 0xFF
                        a += 1
            elif op == "TR":
                n = self._ss_len(ops[0])
                if n is None:
                    raise Unsupported("TR without an explicit length")
                a = self._address(ops[0], regs, True)
                t = self._address(ops[1], regs)
                for k in range(n):
                    mem[a + k] = mem[t + mem[a + k]]
            elif op == "SLL":
                r = self._reg(ops[0])
                regs[r] = (regs[r] << (self._shift(ops[1], regs))) & M32
            elif op == "SLDL":
                r = self._reg(ops[0])
                if r % 2:
                    raise Unsupported("SLDL on an odd register")
                pair = (regs[r] << 32) | regs[r + 1]
                pair = (pair << self._shift(ops[1], regs)) & ((1 << 64) - 1)
                regs[r], regs[r + 1] = pair >> 32, pair & M32
            else:
                raise Unsupported(f"instruction {op} at line {s.line}")
        res.commarea = bytes(mem[CA : CA + len(commarea)])
        res.regs = regs
        return res

    def _shift(self, text: str, regs: list[int]) -> int:
        return self._address(text, regs) & 0x3F  # the second-operand address, low six bits (POPS)

    # ---- EXEC CICS ------------------------------------------------------------------------------------------------
    def _opts(self, text: str) -> tuple[str, dict[str, str]]:
        body = text.replace("CICS", "", 1).strip()
        head = re.match(r"([A-Z]+(?:\s+[A-Z]+)?)", body)
        cmd = head.group(1) if head else ""
        two = {"WRITEQ TD", "WRITE OPERATOR", "DEFINE DCOUNTER"}
        if cmd.split()[0] in ("WRITEQ", "WRITE", "DEFINE") and cmd in two:
            rest = body[len(cmd) :]
        else:
            cmd = cmd.split()[0]
            rest = body[len(cmd) :]
        opts: dict[str, str] = {}
        if cmd == "DEFINE DCOUNTER":  # the command's own name operand: DEFINE DCOUNTER(name)
            opts["DCOUNTER"] = ""
        for m in re.finditer(r"([A-Z0-9]+)\s*\(((?:[^()']|'[^']*')*)\)", rest):
            opts[m.group(1)] = m.group(2).strip()
        for w in re.findall(r"\b([A-Z]+)\b(?!\s*\()", re.sub(r"\([^)]*\)", "", rest)):
            opts.setdefault(w, "")
        if cmd == "DEFINE DCOUNTER":
            opts["DCOUNTER"] = re.match(r"\s*\(([^)]*)\)", rest).group(1).strip()
        return cmd, opts

    def _operand_bytes(self, arg: str, regs: list[int], mem: bytearray, length: int | None = None) -> bytes:
        a = self._address(arg, regs)
        n = length if length is not None else self._lenattr(arg)
        return bytes(mem[a : a + n])

    def _cics(self, text: str, regs: list[int], facts: dict, res: Result, mem: bytearray) -> str:
        cmd, o = self._opts(text)
        resp_off = EIB + EIB_FIELDS["EIBRESP"][0]

        def setresp(v: int) -> None:
            mem[resp_off : resp_off + 4] = v.to_bytes(4, "big")

        if cmd == "RETURN":
            res.events.append(("RETURN",))
            return "RETURN"
        if cmd == "ABEND":
            arg = o["ABCODE"]
            code = arg.strip("'") if arg.startswith("'") else self._operand_bytes(arg, regs, mem, 4).decode(EBCDIC)
            res.events.append(("ABEND", code))
            return f"ABEND:{code}"
        if cmd == "ASKTIME":
            a = self._address(o["ABSTIME"], regs)
            mem[a : a + 8] = (0).to_bytes(8, "big")
        elif cmd == "FORMATTIME":
            clock = facts.get("clock", "2026/10/01 10:30:15")
            d, t = clock.split(" ")
            a = self._address(o["YYYYMMDD"], regs)
            mem[a : a + 10] = d.encode(EBCDIC)
            a = self._address(o["TIME"], regs)
            mem[a : a + 8] = t.encode(EBCDIC)
        elif cmd == "WRITEQ TD":
            n = (
                int.from_bytes(self._operand_bytes(o["LENGTH"], regs, mem), "big")
                if not o["LENGTH"].isdigit()
                else int(o["LENGTH"])
            )
            res.events.append(("WRITEQ TD", o["QUEUE"].strip("'"), self._operand_bytes(o["FROM"], regs, mem, n)))
        elif cmd == "WRITE OPERATOR":
            n = int.from_bytes(self._operand_bytes(o["TEXTLENGTH"], regs, mem), "big")
            nroutes = int.from_bytes(self._operand_bytes(o["NUMROUTES"], regs, mem), "big")
            codes = self._operand_bytes(o["ROUTECODES"], regs, mem, nroutes)
            res.events.append(("WRITE OPERATOR", self._operand_bytes(o["TEXT"], regs, mem, n), codes, nroutes))
        elif cmd == "VERIFY":
            uid = self._operand_bytes(o["USERID"], regs, mem, 8)
            pw = self._operand_bytes(o["PASSWORD"], regs, mem, 8)
            verdict = (facts.get("verify") or {}).get(uid.hex().upper(), "NORMAL")
            res.events.append(("VERIFY", uid, pw))
            setresp(RESP[verdict])
        elif cmd == "ASSIGN":
            for k, v in (
                ("APPLID", facts.get("applid", "ZECSAPPL")),
                ("SYSID", facts.get("sysid", "ZECS")),
                ("STARTCODE", facts.get("startcode", "TD")),
            ):
                if k in o:
                    b = v.encode(EBCDIC)
                    a = self._address(o[k], regs)
                    mem[a : a + len(b)] = b
        elif cmd == "RECEIVE":
            data = facts.get("terminal", b"")
            a = self._address(o["INTO"], regs)
            n = self._lenattr(o["INTO"])
            mem[a : a + min(n, len(data))] = data[:n]  # the bytes beyond the input are left as they were
        elif cmd == "DEFINE DCOUNTER":
            name = self._operand_bytes(o["DCOUNTER"], regs, mem, 16)
            exists = name in (facts.get("counters") or ())
            bad = not _counter_name_ok(name.decode(EBCDIC).rstrip(" "))
            dw = [
                int.from_bytes(self._operand_bytes(o[k], regs, mem, 8), "big") for k in ("VALUE", "MINIMUM", "MAXIMUM")
            ]
            res.events.append(("DEFINE DCOUNTER", name, *dw, not (bad or exists)))
            if bad or exists:  # IBM: INVREQ, RESP2 404 for a name outside the rules, 202 for a counter already defined
                setresp(RESP["INVREQ"])
                mem[EIB + EIB_FIELDS["EIBRESP2"][0] :][:4] = (404 if bad else 202).to_bytes(4, "big")
            else:
                setresp(0)
        elif cmd == "START":
            res.events.append(
                (
                    "START",
                    self._operand_bytes(o["TRANSID"], regs, mem, 4),
                    self._operand_bytes(o["FROM"], regs, mem, int(o["LENGTH"])),
                )
            )
        elif cmd == "SEND":
            n = int.from_bytes(self._operand_bytes(o["LENGTH"], regs, mem), "big")
            res.events.append(("SEND", self._operand_bytes(o["FROM"], regs, mem, n)))
        else:
            raise Unsupported(f"EXEC CICS {cmd}")
        return ""


def run(source: str, commarea: bytes, **facts) -> Result:
    return Machine(source).run(commarea, facts=facts)
