"""Java for one COBOL program over byte storage (docs/language_status/det_port_design.md).

`translate(...)` returns the service's source and the statement counts: every statement either translated or a
`throw new Hole(...)` naming its line. This first version covers batch programs (runBatch); a CICS program's
EXEC CICS commands are holes until the CICS boundary is written."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det import stmt as S

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det.cics import Cics


class Untranslatable(Exception):
    pass


# Library routines the runtime models (each the twin of the harness's COBOL-side model): program -> (Java, args)
LIBRARY = {"CEEDAYS": ("__PACKAGE__.cobolrt.le.Ceedays.call", 4)}


def jstr(s: str) -> str:
    """A Java string literal; every non-ASCII or control character escaped."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append(f"\\u{o:04x}")
    return '"' + "".join(out) + '"'


def jname(cobol: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", cobol)


@dataclass
class FileDef:
    select: str
    dd: str
    organization: str
    access: str
    status: list | None  # the FILE STATUS item: [name, qualifiers...]
    record_key: str | None
    fd: str | None = None  # the FD name
    record: L.Item | None = None  # the FD's (first) record
    key_item: L.Item | None = None  # the RECORD KEY's item
    entity: str | None = None  # indexed: the generated entity class (simple name)
    repository: str | None = None  # its repository field
    handle: str | None = None  # the Java expression creating the DetFile; None: a hole
    why: str = ""


@dataclass
class Program:
    name: str
    service: str
    package: str
    records: list
    proc: S.Procedure
    files: dict = field(default_factory=dict)  # FD / SELECT name -> FileDef


class Gen:
    def __init__(self, prog: Program):
        self.p = prog
        self.lines: list[str] = []
        self.stats: dict[str, Any] = {"statements": 0, "translated": 0, "holes": []}
        self.sentence: str | None = None  # the label of the NEXT SENTENCE block being generated
        self.items: dict[str, list[L.Item]] = {}
        self.ids: dict[int, str] = {}
        self.storage_of: dict[int, str] = {}
        n = 0
        for rec in prog.records:
            for it in rec.walk():
                self.items.setdefault(it.name, []).append(it)
                n += 1  # FILLER too: an 88 may be on one
                self.ids[id(it)] = f"f{n}_{jname(it.name)}"
        self.conds: dict[str, list[L.Item]] = {}
        for rec in prog.records:
            for it in rec.walk():
                for c in it.conditions:
                    self.conds.setdefault(c.name, []).append(c)
        self.para_index = {p.name: i for i, p in enumerate(prog.proc.paragraphs)}
        self.consts: dict[str, str] = {}
        self.tmp = 0
        self.cur = 0
        self.cics: Cics | None = None
        self.copy_dirs: list = []  # where the program's copybooks are (a DTO field's declaration is read there)  # det.cics.Cics for a CICS program
        self.clock = "clock.currentDate()"  # FUNCTION CURRENT-DATE outside CICS
        self.callees: dict[str, str] = {}  # CALLed program -> the ObjectProvider field of its service
        self.entities: set = set()

    # ---- references ---------------------------------------------------------------------------------------------
    def resolve(self, ref: E.Ref) -> L.Item:
        if ref.name == "RETURN-CODE" and not self.items.get(ref.name):
            ref = E.Ref("GG-RETURN-CODE")
        cands = self.items.get(ref.name, [])
        if ref.qualifiers:

            def ok(it: L.Item) -> bool:
                names = []
                a = it.parent
                while a is not None:
                    names.append(a.name)
                    a = a.parent
                if it.section == "FILE" and it.fd:
                    names.append(it.fd)
                return all(q in names for q in ref.qualifiers)

            cands = [c for c in cands if ok(c)]
        if len(cands) != 1:
            raise Untranslatable(f"{ref.name}: {'no such item' if not cands else 'ambiguous'}")
        return cands[0]

    def resolve_cond(self, ref: E.Ref) -> L.Item | None:
        cands = self.conds.get(ref.name, [])
        if ref.qualifiers:
            cands = [c for c in cands if c.parent and (c.parent.name in ref.qualifiers or any(
                q in _ancestors(c.parent) for q in ref.qualifiers))]  # fmt: skip
        return cands[0] if len(cands) == 1 else None

    def field_expr(self, ref: E.Ref) -> str:
        it = self.resolve(ref)
        base = self.ids.get(id(it))
        if base is None:
            raise Untranslatable(f"{ref.name}: FILLER")
        out = base
        if ref.subscripts:
            levels = list(_occurs_chain(it))
            if len(levels) != len(ref.subscripts):
                raise Untranslatable(f"{ref.name}: {len(ref.subscripts)} subscripts for {len(levels)} OCCURS levels")
            for lvl, sub in zip(levels, ref.subscripts):
                out += f".at({self.int_expr(sub)}, {lvl.size})"
        elif _occurs_chain(it):
            pass  # an unsubscripted table reference: the first occurrence (a group / whole-table move uses the group)
        if ref.refmod is not None:
            start, length = ref.refmod
            out += f".ref({self.int_expr(start)}, {('Integer.valueOf(' + self.int_expr(length) + ')') if length is not None else 'null'})"
        return out

    def int_expr(self, e) -> str:
        if isinstance(e, E.Lit) and isinstance(e.value, Decimal):
            return str(int(e.value))
        return f"{self.num(e)}.intValue()"

    def never_written(self, it: L.Item) -> bool:
        """Whether no statement can change the item: none names it, or a group holding it, as a receiver."""
        if not hasattr(self, "_written"):
            self._written = set()
            for p in self.p.proc.paragraphs:
                for s in S.walk(p.body):
                    d = s.data
                    refs = list(d.get("to") or []) + list(d.get("refs") or []) + list(d.get("targets") or [])
                    refs += list(d.get("giving") or []) + [d.get(k) for k in ("into", "target", "remainder")]
                    for r in refs:
                        r = r[0] if isinstance(r, tuple) else r
                        if isinstance(r, E.Ref):
                            self._written.add(r.name)
                    if s.kind == "EXEC" and re.match(r"(?is)\s*EXEC\s+CICS\b", s.text):
                        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, parse_exec

                        try:
                            _, opts = parse_exec(s.text)
                        except CicsError:
                            opts = {"?": s.text}
                        # what CICS only reads: names, the data sent; any other option may be set by the command
                        read_only = {"MAP", "MAPSET", "FROM", "DATASET", "FILE", "PROGRAM", "TRANSID", "QUEUE",
                                     "ABCODE", "KEYLENGTH", "LABEL", "DATESEP", "TIMESEP", "CURSOR"}  # fmt: skip
                        for k, v in opts.items():
                            if v and k not in read_only:
                                self._written.update(w.upper() for w in re.findall(r"[A-Za-z0-9-]+", v))
                    elif s.kind in ("EXEC", "HOLE", "CALL"):
                        self._written.update(w.upper() for w in re.findall(r"[A-Za-z0-9-]+", s.text))
        a: L.Item | None = it
        while a is not None:
            if a.name in self._written:
                return False
            a = a.parent
        return True

    def eib(self, name: str) -> str:
        return self.field_expr(E.Ref(name, ["DFHEIBLK"]))

    # ---- values -----------------------------------------------------------------------------------------------------
    def const(self, v: Decimal) -> str:
        key = str(v)
        if key not in self.consts:
            self.consts[key] = f"N{len(self.consts)}"
        return self.consts[key]

    def num(self, e) -> str:
        """A Java BigDecimal expression for an arithmetic expression."""
        if isinstance(e, E.Lit):
            if isinstance(e.value, Decimal):
                return self.const(e.value)
            raise Untranslatable("a nonnumeric literal in arithmetic")
        if isinstance(e, E.Ref):
            it = self.resolve(e)
            if it.category not in ("NUMERIC", "NUMERIC-EDITED"):
                # an alphanumeric used as a number (e.g. a PIC X subscript): its digits
                return f"Cobol.num({self.field_expr(e)}, CS)"
            return f"Cobol.num({self.field_expr(e)}, CS)"
        if isinstance(e, E.Fig) and e.kind == "ZEROS":
            return "BigDecimal.ZERO"
        if isinstance(e, E.Neg):
            return f"{self.num(e.operand)}.negate()"
        if isinstance(e, E.Bin):
            a, b = self.num(e.left), self.num(e.right)
            if e.op == "+":
                return f"{a}.add({b})"
            if e.op == "-":
                return f"{a}.subtract({b})"
            if e.op == "*":
                return f"{a}.multiply({b})"
            if e.op == "/":
                return f"Cobol.divide({a}, {b})"
            if e.op == "**":
                return f"Cobol.power({a}, {b})"
        if isinstance(e, E.LengthOf):
            it = self.resolve(e.ref)
            return f"BigDecimal.valueOf({it.size * it.occurs})"
        if isinstance(e, E.Func):
            return self.func(e)
        raise Untranslatable(f"expression {type(e).__name__}")

    def func(self, f: E.Func) -> str:
        name = f.name
        args = [a for a in f.args if not (isinstance(a, tuple) and a[0] == "REFMOD")]
        if name in ("UPPER-CASE", "LOWER-CASE", "TRIM", "REVERSE") and len(args) == 1:
            return f"Funcs.{_camel(name)}({self.text(args[0])})"
        if name == "CURRENT-DATE":
            return "DetCics.currentDate(task.now())" if self.cics is not None else self.clock
        if name in ("NUMVAL", "NUMVAL-C", "TEST-NUMVAL", "TEST-NUMVAL-C") and len(args) == 1:
            return f"Funcs.{_camel(name)}({self.text(args[0])})"
        if name in ("INTEGER-OF-DATE", "DATE-OF-INTEGER", "INTEGER", "INTEGER-PART", "ABS") and len(args) == 1:
            return f"Funcs.{_camel(name)}({self.num(args[0])})"
        if name in ("MOD", "REM", "MIN", "MAX") and len(args) >= 2:
            return f"Funcs.{_camel(name)}({', '.join(self.num(a) for a in args)})"
        if name == "LENGTH" and len(args) == 1:
            return f"BigDecimal.valueOf({self.text(args[0])}.length())"
        raise Untranslatable(f"FUNCTION {name}")

    def text(self, e) -> str:
        """A Java String for an operand's text."""
        if isinstance(e, E.Lit):
            if isinstance(e.value, Decimal):
                return jstr(str(e.value))
            if isinstance(e.value, bytes):
                return jstr(e.value.decode("latin-1"))
            return jstr(e.value)
        if isinstance(e, E.Ref):
            return f"Cobol.text({self.field_expr(e)}, CS)"
        if isinstance(e, E.Func):
            return self.func(e)
        raise Untranslatable(f"text of {type(e).__name__}")

    def is_numeric(self, e) -> bool:
        if isinstance(e, E.Lit):
            return isinstance(e.value, Decimal)
        if isinstance(e, E.Ref):
            try:
                return self.resolve(e).category in ("NUMERIC",)
            except Untranslatable:
                return False
        if isinstance(e, (E.Bin, E.Neg, E.LengthOf)):
            return True
        if isinstance(e, E.Func):
            return e.name in ("NUMVAL", "NUMVAL-C", "TEST-NUMVAL", "TEST-NUMVAL-C", "INTEGER-OF-DATE", "DATE-OF-INTEGER", "INTEGER", "MOD",
                              "REM", "ABS", "LENGTH", "MIN", "MAX", "INTEGER-PART")  # fmt: skip
        return False

    # ---- conditions ---------------------------------------------------------------------------------------------
    def cond(self, c) -> str:
        if isinstance(c, tuple) and c and c[0] == "UNPARSED":
            raise Untranslatable(f"condition: {c[2]}")
        if isinstance(c, E.And):
            return f"({self.cond(c.left)} && {self.cond(c.right)})"
        if isinstance(c, E.Or):
            return f"({self.cond(c.left)} || {self.cond(c.right)})"
        if isinstance(c, E.Not):
            return f"!({self.cond(c.cond)})"
        if isinstance(c, E.CondName):
            cn = self.resolve_cond(c.ref)
            if cn is None and c.abbrev is not None:
                op, subject, negated = c.abbrev  # an abbreviated relation's object
                t = self.rel(op, subject, c.ref)
                return f"!({t})" if negated else t
            if cn is None:
                raise Untranslatable(f"condition-name {c.ref.name}")
            return self.cond_test(cn, c.ref.subscripts)
        if isinstance(c, E.ClassCond):
            if c.kind in ("POSITIVE", "NEGATIVE", "ZERO"):
                sig = {"POSITIVE": "> 0", "NEGATIVE": "< 0", "ZERO": "== 0"}[c.kind]
                t = f"{self.num(c.operand)}.signum() {sig}"
            else:
                if not isinstance(c.operand, E.Ref):
                    raise Untranslatable("class condition on an expression")
                fn = {"NUMERIC": "isNumeric", "ALPHABETIC": "isAlphabetic", "ALPHABETIC-UPPER": "isAlphabeticUpper",
                      "ALPHABETIC-LOWER": "isAlphabeticLower"}[c.kind]  # fmt: skip
                t = f"Cobol.{fn}({self.field_expr(c.operand)}, CS)"
            return f"!({t})" if c.negated else t
        if isinstance(c, E.Rel):
            return self.rel(c.op, c.left, c.right)
        raise Untranslatable(f"condition {type(c).__name__}")

    def rel(self, op: str, a, b) -> str:
        jop = {"=": "==", ">": ">", "<": "<", ">=": ">=", "<=": "<="}[op]
        # numeric comparison when both sides are numeric (or one is ZERO against a number)
        if (self.is_numeric(a) and self.is_numeric(b)) or (
            self.is_numeric(a) and isinstance(b, E.Fig) and b.kind == "ZEROS") or (
            self.is_numeric(b) and isinstance(a, E.Fig) and a.kind == "ZEROS"):  # fmt: skip
            return f"{self.num(a)}.compareTo({self.num(b)}) {jop} 0"
        if isinstance(a, E.Ref):
            return f"{self.cmp(a, b)} {jop} 0"
        if isinstance(b, E.Ref):
            flipped = {"==": "==", ">": "<", "<": ">", ">=": "<=", "<=": ">="}[jop]
            return f"{self.cmp(b, a)} {flipped} 0"
        if isinstance(a, E.Func) or isinstance(b, E.Func):
            return f"Cobol.compareText({self.text(a)}, {self.text(b)}) {jop} 0"
        raise Untranslatable("comparison of two non-data operands")

    def cmp(self, a: E.Ref, b) -> str:
        fa = self.field_expr(a)
        if isinstance(b, E.Ref):
            return f"Cobol.compare({fa}, {self.field_expr(b)}, CS)"
        if isinstance(b, E.Lit):
            if isinstance(b.value, Decimal):
                return f"Cobol.compare({fa}, {self.const(b.value)}, CS)"
            return f"Cobol.compare({fa}, {self.text(b)}, CS)"
        if isinstance(b, E.Fig):
            if b.kind == "ALL":
                return f"Cobol.compareAll({fa}, {jstr(b.all_literal or '')}, CS)"
            return f"Cobol.compareFigurative({fa}, Figurative.{_fig(b.kind)}, CS)"
        if isinstance(b, E.Func):
            return f"Cobol.compareText(Cobol.text({fa}, CS), {self.text(b)})"
        if isinstance(b, (E.Bin, E.Neg)):
            return f"Cobol.num({fa}, CS).compareTo({self.num(b)})"
        raise Untranslatable(f"comparison with {type(b).__name__}")

    def cond_field(self, cn: L.Item, subscripts=()) -> str:
        """The item an 88 tests, its subscripts applied (the 88's own, as written on the condition-name)."""
        parent = cn.parent
        if parent is None:
            raise Untranslatable(f"88 {cn.name}: no parent item")
        f = self.ids.get(id(parent))
        if f is None:
            raise Untranslatable(f"88 {cn.name}: no item")
        levels = _occurs_chain(parent)
        if len(levels) != len(subscripts):
            raise Untranslatable(f"88 {cn.name}: {len(subscripts)} subscripts for {len(levels)} OCCURS levels")
        for lvl, sub in zip(levels, subscripts):
            f += f".at({self.int_expr(sub)}, {lvl.size})"
        return f

    def cond_test(self, cn: L.Item, subscripts=()) -> str:
        f = self.cond_field(cn, subscripts)
        tests = []
        for v in cn.values:
            if v[0] == "range":
                lo, hi = v[1], v[2]
                tests.append(f"({self.vcmp(f, lo)} >= 0 && {self.vcmp(f, hi)} <= 0)")
            else:
                tests.append(f"{self.vcmp(f, v)} == 0")
        return "(" + " || ".join(tests) + ")" if len(tests) > 1 else tests[0]

    def vcmp(self, f: str, v) -> str:
        kind = v[0]
        if kind == "num":
            return f"Cobol.compare({f}, {self.const(v[1])}, CS)"
        if kind == "lit":
            return f"Cobol.compare({f}, {jstr(v[1])}, CS)"
        if kind == "fig":
            return f"Cobol.compareFigurative({f}, Figurative.{_fig(v[1])}, CS)"
        if kind == "hex":
            return f"Cobol.compare({f}, {jstr(v[1].decode('latin-1'))}, CS)"
        raise Untranslatable(f"88 value {kind}")

    # ---- moves --------------------------------------------------------------------------------------------------
    def move(self, src, target: E.Ref) -> str:
        ft = self.field_expr(target)
        if isinstance(src, E.Ref):
            return f"Cobol.move({self.field_expr(src)}, {ft}, CS);"
        if isinstance(src, E.Lit):
            if isinstance(src.value, Decimal):
                return f"Cobol.move({self.const(src.value)}, {ft}, CS);"
            return f"Cobol.move({self.text(src)}, {ft}, CS);"
        if isinstance(src, E.Fig):
            if src.kind == "ALL":
                return f"Cobol.moveAll({jstr(src.all_literal or '')}, {ft}, CS);"
            return f"Cobol.moveFigurative(Figurative.{_fig(src.kind)}, {ft}, CS);"
        if isinstance(src, E.Func):
            if self.is_numeric(src):
                return f"Cobol.move({self.num(src)}, {ft}, CS);"
            return f"Cobol.move({self.text(src)}, {ft}, CS);"
        if isinstance(src, E.LengthOf):
            return f"Cobol.move({self.num(src)}, {ft}, CS);"
        raise Untranslatable(f"MOVE from {type(src).__name__}")

    def initialize(self, ref: E.Ref) -> list[str]:
        """INITIALIZE: every elementary item of the group (not FILLER, not under a REDEFINES) to spaces or zero."""
        it = self.resolve(ref)
        base = self.field_expr(ref)
        out = []

        def walk(x: L.Item, redef: bool, shift: str) -> None:
            redef = redef or (bool(x.redefines) and x is not it)
            if redef:
                return
            if x.children and x.pic is None:
                for c in x.children:
                    if c.occurs > 1:
                        for k in range(c.occurs):
                            walk_occ(c, k)
                    else:
                        walk(c, redef, shift)
                return
            if x.name == "FILLER" and x is not it:
                return
            out.append(self._init_one(x, base, it))

        def walk_occ(c: L.Item, k: int) -> None:
            # a table element: its own offset plus k strides, relative to the INITIALIZE target
            for leaf in c.walk():
                if leaf.children or leaf.name == "FILLER" or leaf.redefines:
                    continue
                out.append(self._init_one(leaf, base, it, extra=k * c.size))

        walk(it, False, "")
        return out

    def _init_one(self, x: L.Item, base: str, top: L.Item, extra: int = 0) -> str:
        fig = "ZEROS" if x.category in ("NUMERIC", "NUMERIC-EDITED") else "SPACES"
        rel = x.offset - top.offset + extra
        return f"Cobol.moveFigurative(Figurative.{_fig(fig)}, {self.factory(x, f'{base}.storage()', f'{base}.offset() + {rel}')}, CS);"

    # ---- fields -------------------------------------------------------------------------------------------------
    def factory(self, it: L.Item, storage: str, offset: str) -> str:
        cat = it.category
        if cat == "GROUP":
            return f"Field.group({storage}, {offset}, {it.size})"
        if cat in ("ALPHANUMERIC",):
            return f"Field.alphanumeric({storage}, {offset}, {it.size}, {_b(it.justified)})"
        if cat == "ALPHABETIC":
            return f"Field.alphabetic({storage}, {offset}, {it.size}, {_b(it.justified)})"
        if cat == "NUMERIC":
            if it.usage == "PACKED":
                return f"Field.packed({storage}, {offset}, {it.digits}, {it.scale}, {_b(it.signed)})"
            if it.usage in ("BINARY", "COMP-5"):
                return f"Field.binary({storage}, {offset}, {it.digits}, {it.scale}, {_b(it.signed)}, {_b(it.usage == 'COMP-5')})"
            return (f"Field.zoned({storage}, {offset}, {it.digits}, {it.scale}, {_b(it.signed)}, "
                    f"{_b(it.sign_leading)}, {_b(it.sign_separate)})")  # fmt: skip
        if cat == "NUMERIC-EDITED":
            return (
                f"Field.numericEdited({storage}, {offset}, {it.size}, {jstr(it.picture())}, {_b(it.blank_when_zero)})"
            )
        if cat == "ALPHANUMERIC-EDITED":
            return f"Field.alphanumericEdited({storage}, {offset}, {it.size}, {jstr(it.picture())})"
        raise Untranslatable(f"{it.name}: {cat}")

    # ---- statements ---------------------------------------------------------------------------------------------
    def paragraph(self, p: S.Paragraph, ind: str) -> list[str]:
        """A paragraph's statements; with NEXT SENTENCE in it, each sentence is a labelled block NEXT SENTENCE
        breaks out of (out of an inline PERFORM too, as COBOL's does)."""
        if not any(s.kind == "NEXT-SENTENCE" for s in S.walk(p.body)):
            return self.block(p.body, ind)
        out, start = [], 0
        ends = [e for e in p.sentence_ends if e > 0] + [len(p.body)]
        for k, end in enumerate(ends):
            if end <= start:
                continue
            self.sentence = f"sentence{k}"
            out += [f"{ind}{self.sentence}: {{", *self.block(p.body[start:end], ind + "    "), f"{ind}}}"]
            start = end
        self.sentence = None
        return out

    def block(self, stmts: list, ind: str) -> list[str]:
        out = []
        for s in stmts:
            out += self.statement(s, ind)
        return out

    def statement(self, s: S.Stmt, ind: str) -> list[str]:
        self.stats["statements"] += 1
        try:
            code = self._statement(s, ind)
            self.stats["translated"] += 1
            return code
        except Untranslatable as e:
            why = f"line {s.line}: {s.kind} {e}"
            self.stats["holes"].append(why)
            return [f"{ind}// {_comment(s.text)}", f"{ind}if (true) throw new Hole({jstr(why)});"]

    def _statement(self, s: S.Stmt, ind: str) -> list[str]:
        k = s.kind
        c = f"{ind}// {_comment(s.text)}"
        if k == "HOLE":
            raise Untranslatable(s.data.get("why", "not parsed"))
        if k == "MOVE":
            return [c] + [ind + self.move(s.data["from"], t) for t in s.data["to"]]
        if k == "IF":
            out = [c, f"{ind}if ({self.cond(s.data['cond'])}) {{", *self.block(s.body, ind + "    ")]
            if s.orelse:
                out += [f"{ind}}} else {{", *self.block(s.orelse, ind + "    ")]
            return [*out, f"{ind}}}"]
        if k == "EVALUATE":
            return [c, *self.evaluate(s, ind)]
        if k == "PERFORM":
            return [c, *self.perform(s, ind)]
        if k == "GOTO":
            t = s.data["targets"]
            if s.data["depending"] is None:
                if len(t) != 1 or t[0] not in self.para_index:
                    raise Untranslatable(f"GO TO {t}")
                return [c, f"{ind}if (true) return GOTO | {self.para_index[t[0]]};"]
            sw = [c, f"{ind}switch ({self.int_expr(s.data['depending'])}) {{"]
            for i, name in enumerate(t, 1):
                if name not in self.para_index:
                    raise Untranslatable(f"GO TO {name}: no such paragraph")
                sw.append(f"{ind}    case {i}: return GOTO | {self.para_index[name]};")
            return [*sw, f"{ind}    default: break;", f"{ind}}}"]
        if k in ("EXIT", "CONTINUE"):
            what = s.data.get("what") or []
            if k == "EXIT" and what[:1] == ["PROGRAM"]:
                return [c, f"{ind}if (true) throw new Goback();"]
            if k == "EXIT" and what[:1] == ["PARAGRAPH"]:
                return [c, f"{ind}if (true) return {self.cur + 1};"]
            return [c]
        if k == "NEXT-SENTENCE":
            if not getattr(self, "sentence", None):
                raise Untranslatable("NEXT SENTENCE outside a sentence")
            return [c, f"{ind}if (true) break {self.sentence};"]
        if k in ("GOBACK", "STOP"):
            return [c, f"{ind}if (true) throw new Goback();"]
        if k == "DISPLAY":
            if s.data["upon"] not in (None, "SYSOUT", "CONSOLE", "SYSERR"):
                raise Untranslatable(f"DISPLAY UPON {s.data['upon']}")
            ops = [self.display_operand(o) for o in s.data["operands"]]
            fn = "displayNoAdvancing" if s.data["no_advancing"] else "display"
            return [c, f"{ind}Sysout.{fn}({', '.join(ops)});"]
        if k == "COMPUTE":
            return [c, *self.store_all(s, s.data["targets"], self.num(s.data["expr"]), ind)]
        if k == "ARITH":
            return [c, *self.arith(s, ind)]
        if k == "INITIALIZE":
            out = [c]
            for r in s.data["refs"]:
                out += [ind + x for x in self.initialize(r)]
            return out
        if k == "SET-TRUE":
            out = [c]
            for r in s.data["conds"]:
                cn = self.resolve_cond(r)
                if cn is None or not cn.values:
                    raise Untranslatable(f"SET {r.name} TO TRUE")
                v = cn.values[0]
                if v[0] == "range":
                    v = v[1]
                f = self.cond_field(cn, r.subscripts)
                out.append(ind + self._move_value(v, f))
            return out
        if k == "SET-TO":
            return [c] + [ind + self.move(s.data["value"], t) for t in s.data["targets"]]
        if k == "SET-BY":
            out = [c]
            for t in s.data["targets"]:
                f = self.field_expr(t)
                op = "add" if s.data["up"] else "subtract"
                out.append(f"{ind}Cobol.store({f}, Cobol.num({f}, CS).{op}({self.num(s.data['by'])}), false, CS);")
            return out
        if k == "CALL":
            return [c, *self.call(s, ind)]
        if k == "ACCEPT":
            frm = s.data["from"]
            src = {"DATE": "Funcs.acceptDate(clock())", "DATE YYYYMMDD": "Funcs.acceptDate8(clock())",
                   "TIME": "Funcs.acceptTime(clock())", "DAY": "Funcs.acceptDay(clock())",
                   "DAY YYYYDDD": "Funcs.acceptDay7(clock())"}.get(frm)  # fmt: skip
            if src is None:
                raise Untranslatable(f"ACCEPT FROM {frm}")
            return [c, f"{ind}Cobol.move({src}, {self.field_expr(s.data['target'])}, CS);"]
        if k == "STRING":
            return [c, *self.string(s, ind)]
        if k == "UNSTRING":
            return [c, *self.unstring(s, ind)]
        if k == "INSPECT":
            return [c, *self.inspect(s, ind)]
        if k in ("OPEN", "CLOSE", "READ", "WRITE", "REWRITE", "START"):
            return [c, *self.io(s, ind)]
        if k == "EXEC":
            words = s.text.split()
            if self.cics is None or len(words) < 2 or words[1].upper() != "CICS":
                raise Untranslatable("EXEC " + (words[1] if len(words) > 1 else ""))
            from gitgalaxy.tools.cobol_to_java.det.cics import CicsError

            try:
                return [c, *self.cics.command(s.text, ind)]
            except (CicsError, E.ExprError, KeyError) as e:
                raise Untranslatable(f"EXEC CICS: {e}") from e
        raise Untranslatable(f"{k} not translated")

    def _move_value(self, v, f: str) -> str:
        kind = v[0]
        if kind == "num":
            return f"Cobol.move({self.const(v[1])}, {f}, CS);"
        if kind == "lit":
            return f"Cobol.move({jstr(v[1])}, {f}, CS);"
        if kind == "fig":
            return f"Cobol.moveFigurative(Figurative.{_fig(v[1])}, {f}, CS);"
        if kind == "hex":
            return f"Cobol.move({jstr(v[1].decode('latin-1'))}, {f}, CS);"
        raise Untranslatable(f"value {kind}")

    def display_operand(self, o) -> str:
        if isinstance(o, E.Ref):
            return f"Cobol.displayText({self.field_expr(o)}, CS)"
        if isinstance(o, E.Lit):
            if isinstance(o.value, Decimal):
                return jstr(str(o.value))
            return self.text(o)
        if isinstance(o, E.Fig):
            ch = {"SPACES": " ", "ZEROS": "0", "QUOTES": '"', "LOW": "\x00", "HIGH": "\xff"}.get(o.kind)
            if ch is None:
                raise Untranslatable("DISPLAY ALL")
            return jstr(ch)
        if isinstance(o, E.Func):
            return self.text(o) if not self.is_numeric(o) else f"Cobol.displayNumber({self.num(o)})"
        raise Untranslatable(f"DISPLAY of {type(o).__name__}")

    def store_all(self, s: S.Stmt, targets: list, value: str, ind: str) -> list[str]:
        out = []
        checked = "SIZE-ERROR" in s.phrases or "NOT-SIZE-ERROR" in s.phrases
        if not checked:
            v = self.tmpname("v")
            out.append(f"{ind}BigDecimal {v} = {value};")
            for t, rounded in targets:
                out.append(f"{ind}Cobol.store({self.field_expr(t)}, {v}, {_b(rounded)}, CS);")
            return out
        v, err = self.tmpname("v"), self.tmpname("sizeError")
        out.append(f"{ind}BigDecimal {v} = {value};")
        out.append(f"{ind}boolean {err} = false;")
        for t, rounded in targets:
            out.append(f"{ind}{err} |= Cobol.storeChecked({self.field_expr(t)}, {v}, {_b(rounded)}, CS);")
        if "SIZE-ERROR" in s.phrases:
            out += [f"{ind}if ({err}) {{", *self.block(s.phrases["SIZE-ERROR"], ind + "    "), f"{ind}}}"]
        if "NOT-SIZE-ERROR" in s.phrases:
            out += [f"{ind}if (!{err}) {{", *self.block(s.phrases["NOT-SIZE-ERROR"], ind + "    "), f"{ind}}}"]
        return out

    def arith(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        op = d["op"]
        ops = d["operands"]
        if d.get("giving") is not None:
            if op == "+":
                val = " ".join([self.num(ops[0])] + [f".add({self.num(o)})" for o in ops[1:]]).replace(" .", ".")
            elif op == "-":
                val = self.num(ops[0]) + "".join(f".subtract({self.num(o)})" for o in ops[1:])
            elif op == "*":
                val = f"{self.num(ops[0])}.multiply({self.num(ops[1])})"
            else:
                val = f"Cobol.divide({self.num(ops[0])}, {self.num(ops[1])})"
            out = self.store_all(s, d["giving"], val, ind)
            if d.get("remainder") is not None:
                q = self.field_expr(d["giving"][0][0])
                out.append(f"{ind}Cobol.store({self.field_expr(d['remainder'])}, {self.num(ops[0])}.subtract("
                           f"Cobol.num({q}, CS).multiply({self.num(ops[1])})), false, CS);")  # fmt: skip
            return out
        total = self.num(ops[0]) + "".join(f".add({self.num(o)})" for o in ops[1:]) if ops else "BigDecimal.ZERO"
        out = []
        tsum = self.tmpname("t")
        out.append(f"{ind}BigDecimal {tsum} = {total};")
        checked = "SIZE-ERROR" in s.phrases or "NOT-SIZE-ERROR" in s.phrases
        err = self.tmpname("sizeError")
        if checked:
            out.append(f"{ind}boolean {err} = false;")
        for tgt, rounded in d["targets"]:
            if not isinstance(tgt, E.Ref):
                raise Untranslatable("arithmetic target is not a data item")
            f = self.field_expr(tgt)
            cur = f"Cobol.num({f}, CS)"
            val = {"+=": f"{cur}.add({tsum})", "-=": f"{cur}.subtract({tsum})", "*=": f"{tsum}.multiply({cur})",
                   "/=": f"Cobol.divide({cur}, {tsum})"}[op]  # fmt: skip
            if checked:
                out.append(f"{ind}{err} |= Cobol.storeChecked({f}, {val}, {_b(rounded)}, CS);")
            else:
                out.append(f"{ind}Cobol.store({f}, {val}, {_b(rounded)}, CS);")
        if checked:
            if "SIZE-ERROR" in s.phrases:
                out += [f"{ind}if ({err}) {{", *self.block(s.phrases["SIZE-ERROR"], ind + "    "), f"{ind}}}"]
            if "NOT-SIZE-ERROR" in s.phrases:
                out += [f"{ind}if (!{err}) {{", *self.block(s.phrases["NOT-SIZE-ERROR"], ind + "    "), f"{ind}}}"]
        return out

    def evaluate(self, s: S.Stmt, ind: str) -> list[str]:
        subjects = s.data["subjects"]
        out = []
        first = True
        for conds, body in s.whens:
            if conds is None:
                test = "true"
            else:
                alts = []
                for objs in conds:
                    if len(objs) != len(subjects):
                        raise Untranslatable("WHEN with a different number of ALSO objects")
                    alts.append(" && ".join(self.when_test(subj, obj) for subj, obj in zip(subjects, objs)))
                test = " || ".join(f"({a})" for a in alts)
            kw = "if" if first else "} else if"
            out += [f"{ind}{kw} ({test}) {{", *self.block(body, ind + "    ")]
            first = False
        if not first:
            out.append(f"{ind}}}")
        return out

    def when_test(self, subject, obj) -> str:
        kind = obj[0]
        if kind == "ANY":
            return "true"
        if kind == "UNPARSED":
            raise Untranslatable(f"WHEN {obj[1]}")
        if isinstance(subject, tuple) and subject[0] == "UNPARSED":
            raise Untranslatable(f"EVALUATE {subject[1]}")
        if subject in ("TRUE", "FALSE"):
            if kind == "COND":
                t = self.cond(obj[1])
            elif kind == "VALUE" and isinstance(obj[1], E.Ref):
                cn = self.resolve_cond(obj[1])
                if cn is None:
                    raise Untranslatable(f"WHEN {obj[1].name}: not a condition")
                t = self.cond_test(cn, obj[1].subscripts)
            elif kind in ("TRUE", "FALSE"):
                t = "true" if kind == "TRUE" else "false"
            else:
                raise Untranslatable("WHEN object for EVALUATE TRUE")
            t = f"!({t})" if (obj[-1] is True and kind in ("COND", "VALUE")) else t
            return t if subject == "TRUE" else f"!({t})"
        if kind == "VALUE":
            t = self.rel("=", subject, obj[1])
            return f"!({t})" if obj[2] else t
        if kind == "RANGE":
            t = f"({self.rel('>=', subject, obj[1])} && {self.rel('<=', subject, obj[2])})"
            return f"!{t}" if obj[3] else t
        if kind == "COND":
            raise Untranslatable("a condition as WHEN object of a value subject")
        raise Untranslatable(f"WHEN {kind}")

    def perform(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        if d["inline"] or d["target"] is None:
            body = self.block(s.body, ind + "    ")
        else:
            t = d["target"]
            if t not in self.para_index:
                raise Untranslatable(f"PERFORM {t}: no such paragraph")
            thru = d["thru"] or t
            if thru not in self.para_index:
                raise Untranslatable(f"PERFORM THRU {thru}: no such paragraph")
            if self.p.proc.paragraphs[self.para_index[t]].section == t and d["thru"] is None:
                # PERFORM section: its paragraphs
                sec = [i for i, p in enumerate(self.p.proc.paragraphs) if p.section == t]
                body = [f"{ind}    perform({sec[0]}, {sec[-1]});"]
            else:
                body = [f"{ind}    perform({self.para_index[t]}, {self.para_index[thru]});"]
        if d["times"] is not None:
            i = self.tmpname("i")
            return [
                f"{ind}for (int {i} = 0, n_{i} = {self.int_expr(d['times'])}; {i} < n_{i}; {i}++) {{",
                *body,
                f"{ind}}}",
            ]
        if d["until"] is not None:
            cond = self.cond(d["until"])
            if d["test_after"]:
                return [f"{ind}do {{", *body, f"{ind}}} while (!({cond}));"]
            return [f"{ind}while (!({cond})) {{", *body, f"{ind}}}"]
        if d["varying"] is not None:
            var, frm, by, until = d["varying"]
            f = self.field_expr(var)
            init = (
                self.move(frm, var)
                if not isinstance(frm, (E.Bin, E.Neg))
                else f"Cobol.store({f}, {self.num(frm)}, false, CS);"
            )
            step = f"Cobol.store({f}, Cobol.num({f}, CS).add({self.num(by)}), false, CS);"
            return [f"{ind}{init}", f"{ind}while (!({self.cond(until)})) {{", *body, f"{ind}    {step}", f"{ind}}}"]
        if d["inline"]:
            return [f"{ind}{{", *body, f"{ind}}}"]
        return [x[4:] if x.startswith(ind + "    ") else x for x in body]

    def call(self, s: S.Stmt, ind: str) -> list[str]:
        prog = s.data["program"]
        args = s.data["args"]
        if prog == "CEE3ABD":
            code = args[0][1] if args else None
            if code is None:
                return [f'{ind}if (true) throw CobolAbend.user(0, "CEE3ABD");']
            return [f'{ind}if (true) throw CobolAbend.user({self.int_expr(code)}, "CEE3ABD");']
        callee = self.callees.get(prog)
        if callee is not None:
            if any(m != "REFERENCE" or not isinstance(a, E.Ref) for m, a in args):
                raise Untranslatable(f"CALL {prog}: items BY REFERENCE expected")
            refs, out = [], []
            for _, a in args:
                v = self.tmpname("arg")
                refs.append(v)
                out.append(f"{ind}CobolRef<String> {v} = CobolRef.of(Cobol.text({self.field_expr(a)}, CS));")
            rc = self.tmpname("rc")
            out.append(f"{ind}int {rc} = {callee}.getObject().handleCall({', '.join(refs)});")
            for v, (_, a) in zip(refs, args):
                out.append(f"{ind}Cobol.move({v}.get(), {self.field_expr(a)}, CS);")
            out.append(
                f"{ind}Cobol.store({self.field_expr(E.Ref('RETURN-CODE'))}, BigDecimal.valueOf({rc}), false, CS);"
            )
            return out
        lib = LIBRARY.get(prog)
        if lib is not None:
            if len(args) != lib[1] or any(m != "REFERENCE" or not isinstance(a, E.Ref) for m, a in args):
                raise Untranslatable(f"CALL {prog}: {lib[1]} items BY REFERENCE expected")
            return [f"{ind}{lib[0]}({', '.join(self.field_expr(a) for _, a in args)});"]
        raise Untranslatable(f"CALL {prog}")

    def string(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        parts = []
        for sources, delim in d["parts"]:
            for src in sources:
                a = self.str_arg(src)
                if delim is None:
                    parts.append(
                        f"Cobol.StringPart.size({a})" if a.startswith("f") else f"Cobol.StringPart.size({a}, CS)"
                    )
                else:
                    b = self.str_arg(delim)
                    tail = "" if a.startswith("f") and b.startswith("f") else ", CS"
                    parts.append(f"Cobol.StringPart.delimited({a}, {b}{tail})")
        pointer = self.field_expr(d["pointer"]) if d.get("pointer") is not None else "null"
        call = f"Cobol.string({self.field_expr(d['into'])}, {pointer}, CS, {', '.join(parts)})"
        return self.overflow(s, call, ind)

    def overflow(self, s: S.Stmt, call: str, ind: str) -> list[str]:
        """A STRING / UNSTRING call (true: OVERFLOW) and its ON OVERFLOW / NOT ON OVERFLOW phrases."""
        if not ("OVERFLOW" in s.phrases or "NOT-OVERFLOW" in s.phrases):
            return [f"{ind}{call};"]
        v = self.tmpname("overflow")
        out = [f"{ind}boolean {v} = {call};"]
        if "OVERFLOW" in s.phrases:
            out += [f"{ind}if ({v}) {{", *self.block(s.phrases["OVERFLOW"], ind + "    "), f"{ind}}}"]
        if "NOT-OVERFLOW" in s.phrases:
            out += [f"{ind}if (!{v}) {{", *self.block(s.phrases["NOT-OVERFLOW"], ind + "    "), f"{ind}}}"]
        return out

    def unstring(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        delims = []
        for operand, every in d["delims"]:
            a = self.str_arg(operand)
            delims.append(f"Cobol.Delim.of({a}, {_b(every)})" if a.startswith("f")
                          else f"Cobol.Delim.of({a}, {_b(every)}, CS)")  # fmt: skip
        intos = []
        for target, dl, cnt in d["intos"]:
            x = f"Cobol.Into.of({self.field_expr(target)})"
            if dl is not None:
                x += f".delimiterIn({self.field_expr(dl)})"
            if cnt is not None:
                x += f".countIn({self.field_expr(cnt)})"
            intos.append(x)
        ptr = self.field_expr(d["pointer"]) if d.get("pointer") is not None else "null"
        tal = self.field_expr(d["tallying"]) if d.get("tallying") is not None else "null"
        call = (f"Cobol.unstring({self.field_expr(d['src'])}, {ptr}, {tal}, java.util.List.of({', '.join(delims)}), "
                f"CS, {', '.join(intos)})")  # fmt: skip
        return self.overflow(s, call, ind)

    def str_arg(self, e) -> str:
        """A STRING / INSPECT operand: a Field (an expression starting `f`) or a Java String."""
        if isinstance(e, E.Ref):
            return self.field_expr(e)
        return self.text_or_field(e)

    def text_or_field(self, e) -> str:
        if isinstance(e, E.Fig):
            ch = {"SPACES": " ", "ZEROS": "0", "QUOTES": '"', "LOW": "\x00", "HIGH": "\xff"}.get(e.kind)
            if ch is None:
                raise Untranslatable("STRING ALL")
            return jstr(ch)
        return self.text(e)

    def inspect(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        f = self.field_expr(d["target"])

        def txt(e, like=None) -> str:
            """An INSPECT operand as text; a figurative as long as the operand it stands against."""
            if isinstance(e, E.Fig) and e.kind != "ALL":
                ch = FIG_CHAR[e.kind]
                n = len(like.value) if isinstance(like, E.Lit) and isinstance(like.value, str) else 1
                return jstr(ch * n)
            if isinstance(e, E.Fig):
                return jstr(e.all_literal or "")
            return self.text(e)

        clauses = []
        for c in d["clauses"]:
            if c[0] == "tally":
                _, counter, mode, pat, bounds = c
                expr = (f"Cobol.Clause.tally({self.field_expr(counter)}, Cobol.Mode.{mode}, "
                        f"{'null' if pat is None else txt(pat)}, CS)")  # fmt: skip
            elif c[0] == "replace":
                _, mode, pat, by, bounds = c
                expr = (f"Cobol.Clause.replace(Cobol.Mode.{mode}, {'null' if pat is None else txt(pat)}, "
                        f"{txt(by, pat)}, CS)")  # fmt: skip
            else:
                _, a, b, bounds = c
                expr = f"Cobol.Clause.converting({txt(a)}, {txt(b, a)}, CS)"
            for which, x in bounds:
                expr += f".{which.lower()}({txt(x)}, CS)"
            clauses.append(expr)
        return [f"{ind}Cobol.inspect({f}, CS, {', '.join(clauses)});"]

    # ---- files --------------------------------------------------------------------------------------------------
    def io(self, s: S.Stmt, ind: str) -> list[str]:
        k = s.kind
        out = []
        if k in ("OPEN", "CLOSE"):
            for entry in s.data["files"]:
                mode, name = entry if k == "OPEN" else (None, entry)
                fd = self.p.files.get(name)
                if fd is None:
                    raise Untranslatable(f"{k} {name}: no SELECT")
                v = jname(fd.select)
                st = self.tmpname("st")
                if fd.handle is None:
                    raise Untranslatable(f"{name}: {fd.why}")
                call = f"{v}.open({jstr(mode or 'INPUT')})" if k == "OPEN" else f"{v}.close()"
                out.append(f"{ind}String {st} = {call};")
                out += self.status(fd, st, ind)
            return out
        if k == "READ":
            fd = self.p.files.get(s.data["file"])
            if fd is None:
                raise Untranslatable(f"READ {s.data['file']}: no SELECT")
            if fd.handle is None:
                raise Untranslatable(f"{fd.select}: {fd.why}")
            v = jname(fd.select)
            seq = s.data["next"] or fd.access == "SEQUENTIAL" or fd.organization == "SEQUENTIAL"
            st = self.tmpname("st")
            if seq and s.data["key"] is None:
                out.append(f"{ind}String {st} = {v}.readNext();")
            else:
                key = self.resolve(s.data["key"]) if s.data["key"] is not None else fd.key_item
                if key is None or key.record is not fd.record:
                    raise Untranslatable(f"READ {fd.select}: its key is not in its record")
                out.append(f"{ind}String {st} = {v}.readKey({key.offset}, {key.size});")
            out += self.status(fd, st, ind)
            if s.data["into"] is not None:
                rec = self.ids[id(fd.record)]
                out.append(f'{ind}if ({st}.startsWith("0")) {{')
                out.append(f"{ind}    Cobol.move({rec}, {self.field_expr(s.data['into'])}, CS);")
                out.append(f"{ind}}}")
            out += self.io_phrases(s, st, ind, at_end="10", invalid=("21", "22", "23", "24"))
            return out
        if k in ("WRITE", "REWRITE"):
            rec_item = self.resolve(s.data["record"])
            fd = next((f for f in self.p.files.values() if f.record is not None and rec_item.fd == f.fd), None)
            if fd is None:
                raise Untranslatable(f"{k} {s.data['record'].name}: no file")
            if fd.handle is None:
                raise Untranslatable(f"{fd.select}: {fd.why}")
            v = jname(fd.select)
            if s.data["from"] is not None:
                out.append(ind + self.move(s.data["from"], s.data["record"]))
            st = self.tmpname("st")
            out.append(f"{ind}String {st} = {v}.{k.lower()}({rec_item.size});")
            out += self.status(fd, st, ind)
            out += self.io_phrases(s, st, ind, at_end=None, invalid=("21", "22", "23", "24"))
            return out
        if k == "START":
            raise Untranslatable("START")
        raise Untranslatable(k)

    def status(self, fd: FileDef, st: str, ind: str) -> list[str]:
        if fd.status is None:
            return []
        return [ind + self.move_text(st, E.Ref(fd.status[0], fd.status[1:]))]

    def move_text(self, java: str, target: E.Ref) -> str:
        return f"Cobol.move({java}, {self.field_expr(target)}, CS);"

    def io_phrases(self, s: S.Stmt, st: str, ind: str, at_end, invalid) -> list[str]:
        out = []
        if at_end and "AT-END" in s.phrases:
            out += [
                f"{ind}if ({st}.equals({jstr(at_end)})) {{",
                *self.block(s.phrases["AT-END"], ind + "    "),
                f"{ind}}}",
            ]
        if at_end and "NOT-AT-END" in s.phrases:
            out += [
                f'{ind}if ({st}.startsWith("0")) {{',
                *self.block(s.phrases["NOT-AT-END"], ind + "    "),
                f"{ind}}}",
            ]
        if "INVALID-KEY" in s.phrases:
            test = " || ".join(f"{st}.equals({jstr(c)})" for c in invalid)
            out += [f"{ind}if ({test}) {{", *self.block(s.phrases["INVALID-KEY"], ind + "    "), f"{ind}}}"]
        if "NOT-INVALID-KEY" in s.phrases:
            out += [
                f'{ind}if ({st}.startsWith("0")) {{',
                *self.block(s.phrases["NOT-INVALID-KEY"], ind + "    "),
                f"{ind}}}",
            ]
        return out

    def tmpname(self, base: str) -> str:
        self.tmp += 1
        return f"{base}{self.tmp}"


FIG_CHAR = {"SPACES": " ", "ZEROS": "0", "QUOTES": '"', "LOW": "\x00", "HIGH": "\xff"}


def _fig(kind: str) -> str:
    """The runtime's Figurative constant for a figurative of the AST."""
    return {"LOW": "LOW_VALUES", "HIGH": "HIGH_VALUES"}.get(kind, kind)


def _ancestors(it: L.Item) -> list[str]:
    out = []
    a = it.parent
    while a is not None:
        out.append(a.name)
        a = a.parent
    return out


def _occurs_chain(it: L.Item) -> list[L.Item]:
    """The OCCURS items from the outermost to `it` (itself included when it OCCURS)."""
    chain = []
    a: L.Item | None = it
    while a is not None:
        if a.occurs > 1 or a.depending:
            chain.append(a)
        a = a.parent
    return list(reversed(chain))


def _b(v: bool) -> str:
    return "true" if v else "false"


def _camel(name: str) -> str:
    parts = name.lower().split("-")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _comment(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:150].replace("*/", "* /")
