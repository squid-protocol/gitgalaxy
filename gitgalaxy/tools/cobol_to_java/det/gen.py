"""Java for one COBOL program over byte storage (docs/language_status/det_port_design.md).

`translate(...)` returns the service's source and the statement counts: every statement either translated or a
`throw new Hole(...)` naming its line. This first version covers batch programs (runBatch); a CICS program's
EXEC CICS commands are holes until the CICS boundary is written."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det import osvs as O
from gitgalaxy.tools.cobol_to_java.det import stmt as S
from gitgalaxy.tools.cobol_to_java.det.source import WIDE

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det.cics import Cics
    from gitgalaxy.tools.cobol_to_java.det.source import EngineCopies


class Untranslatable(Exception):
    pass


def _reads(method):
    """The operands a method names are only read (gen.reading)."""

    def wrapper(self, *args, **kwargs):
        with self.reading():
            return method(self, *args, **kwargs)

    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


class LiftViolation(Exception):
    """Lifted items (det-port B3: typed Java fields instead of byte storage) used where only their bytes will do:
    the caller lifts them no more and translates again."""

    def __init__(self, names):
        super().__init__(", ".join(sorted(names)))
        self.names = set(names)


# Library routines the runtime models (each the twin of the harness's COBOL-side model): program -> (Java, args)
LIBRARY = {
    "CEEDAYS": ("__PACKAGE__.cobolrt.le.Ceedays.call", 4),
    "COBDATFT": ("__PACKAGE__.cobolrt.le.Cobdatft.call", 1),
}


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
    varying: dict | None = None  # RECORD VARYING ... DEPENDING ON: {min, max, depending} (program.fd_entries)
    sort: bool = False  # an SD (sort-merge) file: SORT / MERGE / RELEASE / RETURN only
    sort_length: int | None = None  # its records' length (None: records of different lengths)


@dataclass
class Program:
    name: str
    service: str
    package: str
    records: list
    proc: S.Procedure
    files: dict = field(default_factory=dict)  # FD / SELECT name -> FileDef


class Gen:
    def __init__(self, prog: Program, structured: bool = False):
        self.write_only_pointers: set[str] = set()  # program.write_only_pointers
        self.p = prog
        # structured: a program with no GO TO / HANDLE -- paragraphs are void methods called in order, no dispatcher
        self.structured = structured
        self.lines: list[str] = []
        self.stats: dict[str, Any] = {"statements": 0, "translated": 0, "holes": []}
        self.sentence: str | None = None  # the label of the NEXT SENTENCE block being generated
        # ARITHMETIC-OSVS (#4287, det/osvs.py): the plan of the expression being generated (id(node) -> ALIGN / FOLD)
        # and, inside a condition, the plans of its relations still to generate, in order
        self.osvs: dict = {}
        self.rel_plans: list | None = None
        # inside an intrinsic function's arguments (cob_intr_binop: a zero divisor gives 0, never NaN, #4655)
        self.intr = 0
        # what the last decimal build of the sentence left: (dmax, expr_decp stack), None when nothing (an EVALUATE's
        # condition leaves its state to the next statements of the sentence; a period, a COMPUTE or an IF resets it)
        self.leak: tuple | None = None
        self.items: dict[str, list[L.Item]] = {}
        self.ids: dict[int, str] = {}
        self.storage_of: dict[int, str] = {}
        n = 0
        taken: set[str] = set()
        for rec in prog.records:
            for it in rec.walk():
                self.items.setdefault(it.name, []).append(it)
                n += 1  # FILLER too: an 88 may be on one
                if structured:
                    # the COBOL name in camelCase (acctId); a second item of the name: acctId2, ...
                    base = camel(it.name) if it.name != "FILLER" else f"filler{n}"
                    name, k = base, 1
                    while name in taken or name in JAVA_RESERVED:
                        k += 1
                        name = f"{base}{k}"
                    taken.add(name)
                    self.ids[id(it)] = name
                else:
                    self.ids[id(it)] = f"f{n}_{jname(it.name)}"
        self.taken_names = set(self.ids.values())
        # #4271 COMP-1 / COMP-2 (det.hfp, cobolrt/Hfp): a float is read and written only as a number. field_expr
        # serves a float item only to value_field; any other use -- its bytes, or those of an item that overlaps
        # it (a group holding it, a REDEFINES) -- is refused by name: HFP on z/OS, IEEE on the oracle (register C6)
        self._value_use = 0  # > 0 while value_field asks
        self._init_bytes = 0  # > 0 inside INITIALIZE: a group is walked to its elementary items, never copied
        self.fmode: str | None = None  # "LONG" / "SHORT" while num() generates a floating-point expression
        self.float_extents: dict[int, list] = {}  # storage root id -> [(item, first extent, full extent, tables)]
        self.root_of: dict[int, int] = {}  # id(record) -> id(its storage root)
        # condition-name methods: id(88 item) -> (Java method name, the test's body); in order of first use
        self.cond_methods: dict[int, tuple[str, str, L.Item]] = {}
        self.conds: dict[str, list[L.Item]] = {}
        for rec in prog.records:
            for it in rec.walk():
                for c in it.conditions:
                    self.conds.setdefault(c.name, []).append(c)
        self.para_index = {p.name: i for i, p in enumerate(prog.proc.paragraphs)}
        self.consts: dict[str, str] = {}
        self.dcs: dict[
            tuple, tuple
        ] = {}  # ARITHMETIC-OSVS: libcob's decimal constants (Cobol.Dc): key -> (name, value)
        self.tmp = 0
        self.cur = 0
        self.cics: Cics | None = None
        self.copy_dirs: list = []
        self.engine: EngineCopies | None = None  # #4528: the estate's declared code pages
        self.lifted: dict[int, str] = {}  # id(item) -> "X" (a String of its length) | "BIN" (a long) -- B3
        self.violations: set[str] = set()  # lifted items used through their bytes: this translation is discarded
        # typed groups: a group holding lifted items keeps its bytes for whole-group uses -- packed from the typed
        # fields before one, unpacked into them after a write (gen.statement) -- instead of being a violation
        self.sync_groups = False
        self.synced: dict[int, L.Item] = {}  # every group so used: its pack_ / unpack_ methods are emitted
        self.touched: dict[int, bool] = {}  # this statement's synced groups -> written (else only read)
        self._reading = 0  # > 0 while an operand is only read
        self.java_root: Path | None = None  # the generated project's src/main/java
        self.id_methods: dict = {}  # entity -> its id_<entity> method lines (det.entity)  # where the program's copybooks are (a DTO field's declaration is read there)  # det.cics.Cics for a CICS program
        self.sql: Any = None  # det.sql.Sql for a program with EXEC SQL
        self.clock = "clock.currentDate()"  # FUNCTION CURRENT-DATE outside CICS
        self.uses_random = False  # FUNCTION RANDOM: the program keeps a run unit's sequence (Funcs.Random)
        self.callees: dict[str, str] = {}  # CALLed program -> the ObjectProvider field of its service
        # CALLed program -> its handleCall parameter types (CobolRef<String>, or a contract DTO for a group item)
        self.callee_types: dict[str, list[str]] = {}
        # the COMMAREA codec (det.cics.Cics) a DTO crosses storage with: the CICS one, or made on first use for a batch
        # program
        self.dto_codecs: Cics | None = None
        self.dto_codecs_factory: Callable[[], Cics] | None = None
        self.entities: set = set()
        # SPECIAL-NAMES alphabets (name -> the definition's tokens, program.alphabets) and PROGRAM COLLATING
        # SEQUENCE: a SORT / MERGE's collating sequence
        self.alphabets: dict[str, list[str]] = {}
        self.program_collating: str | None = None
        # the PROGRAM COLLATING SEQUENCE's Sort.Collating once a relation condition compares under it (#4539): the
        # service's COLLATING constant
        self.pcs_used: str | None = None

    # ---- references ---------------------------------------------------------------------------------------------
    def resolve(self, ref: E.Ref) -> L.Item:
        if ref.name == "RETURN-CODE" and not self.items.get(ref.name):
            ref = E.Ref("GG-RETURN-CODE")
        if ref.name == "SORT-RETURN" and not self.items.get(ref.name):
            ref = E.Ref("GG-SORT-RETURN")
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
        if it.category == "FLOAT":  # #4271: a float's value only (value_field), never its bytes (register C6)
            if not self._value_use or ref.refmod is not None:
                raise Untranslatable(f"{ref.name}: the bytes of a {it.usage} item ({FLOAT_BYTES})")
        elif not self._init_bytes:
            over = self.overlaps_float(it)
            if over is not None:
                raise Untranslatable(f"{ref.name}: its bytes hold {over.name} {over.usage} ({FLOAT_BYTES})")
        packed = self.check_lift(it)
        base = self.ids.get(id(it))
        if base is None:
            raise Untranslatable(f"{ref.name}: FILLER")
        out = f"\x00PACK:{base}\x00" if packed else base  # resolved by after_statement
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

    def value_field(self, ref: E.Ref) -> str:
        """field_expr for a use of the item's value (a number read, stored, compared or displayed): the one way a
        COMP-1 / COMP-2 item is named (#4271)."""
        self._value_use += 1
        try:
            return self.field_expr(ref)
        finally:
            self._value_use -= 1

    def overlaps_float(self, it: L.Item) -> L.Item | None:
        """The float item whose bytes `it` (not a float) covers -- as a group holding it, or a REDEFINES over it -- or
        None. Items in the same table compare one occurrence; otherwise whole tables."""
        if not self.float_extents or it.record is None:
            return None
        floats = self.float_extents.get(self.root_of.get(id(it.record), id(it.record)), [])
        if not floats:
            return None
        first, full, tables = _extents(it)
        for f, ffirst, ffull, ftables in floats:
            a, b = (first, ffirst) if set(tables) & set(ftables) else (full, ffull)
            if a[0] < b[1] and b[0] < a[1]:
                return f
        return None

    def float_item(self, e) -> L.Item | None:
        """The COMP-1 / COMP-2 item `e` names as a number (a reference modification names bytes: None)."""
        if isinstance(e, E.Ref) and e.refmod is None:
            try:
                it = self.resolve(e)
            except Untranslatable:
                return None
            return it if it.category == "FLOAT" else None
        return None

    def has_float(self, e) -> bool:
        if isinstance(e, E.Ref):
            return self.float_item(e) is not None
        if isinstance(e, E.Bin):
            return self.has_float(e.left) or self.has_float(e.right)
        if isinstance(e, E.Neg):
            return self.has_float(e.operand)
        return False

    def float_mode(self, exprs: list, receivers: list, multiply: bool = False) -> str | None:
        """IBM's evaluation mode of an arithmetic statement (6.4 Programming Guide, SC27-8714-03, Appendix A,
        "Floating-point data and intermediate results"): None (fixed point) unless a receiver or operand is COMP-1 /
        COMP-2; then "SHORT" if every receiver and operand is COMP-1 and there is no multiplication or
        exponentiation, else "LONG" (ARITH(COMPAT))."""
        refs: list = list(receivers)
        other = False  # an operand that is no data item (a literal, a function, a figurative)

        def walk(e) -> None:
            nonlocal other, multiply
            if isinstance(e, E.Ref):
                refs.append(e)
            elif isinstance(e, E.Bin):
                multiply = multiply or e.op in ("*", "**")
                walk(e.left)
                walk(e.right)
            elif isinstance(e, E.Neg):
                walk(e.operand)
            else:
                other = True

        for e in exprs:
            walk(e)
        items = [self.float_item(r) for r in refs]
        if not any(items):
            return None
        return (
            "SHORT"
            if not other and not multiply and all(x is not None and x.usage == "COMP-1" for x in items)
            else "LONG"
        )

    # ---- ARITHMETIC-OSVS (#4287) ------------------------------------------------------------------------------
    def osvs_leaf(self, e) -> O.Leaf:
        """What cobc's decimal_expand does with a data item or a FUNCTION (det/osvs.py)."""
        if isinstance(e, E.Func):
            return O.Leaf("FUNC", 0, True)
        it = self.resolve(e)
        if it.level == 88:
            return O.Leaf("COND", 0, False)
        scale = it.scale if it.category in ("NUMERIC", "NUMERIC-EDITED") else 0
        # a binary item of scale 0 is loaded as an integer (cob_decimal_set_llint): no places pushed
        binary = it.usage in ("BINARY", "COMP-5", "INDEX") and scale == 0 and e.refmod is None
        return O.Leaf("ITEM", scale, not binary)

    def osvs_length(self, e: E.LengthOf) -> int:
        it = self.resolve(e.ref)
        return it.size * it.occurs

    @contextlib.contextmanager
    def osvs_plan(self, plan: dict):
        outer, self.osvs = self.osvs, plan
        try:
            yield
        finally:
            self.osvs = outer

    def plan_arith(self, expr, receivers: list, operands_first: bool = False) -> dict:
        """The plan of an arithmetic statement's expression, its receivers' places counted (build_decimal_assign)."""
        scales = []
        for t in receivers:
            it = self.resolve(t) if isinstance(t, E.Ref) else None
            if it is not None and it.category in ("NUMERIC", "NUMERIC-EDITED"):
                scales.append(it.scale)
            elif it is not None:
                scales.append(0)
        dmax_in = self.leak[0] if self.leak is not None else -1
        self.leak = None
        try:
            return O.plan_compute(expr, scales, self.osvs_leaf, self.osvs_length, operands_first, dmax_in)
        except O.OsvsError as e:
            raise Untranslatable(f"ARITHMETIC-OSVS: {e} (#4287)") from e

    def cond_relations(self, c, out: list) -> None:
        """The relations of a condition in the order cond() generates them, each with its operands in cobc's order."""
        if isinstance(c, (E.And, E.Or)):
            self.cond_relations(c.left, out)
            self.cond_relations(c.right, out)
        elif isinstance(c, E.Not):
            self.cond_relations(c.cond, out)
        elif isinstance(c, E.CondName):
            if c.abbrev is not None and self.resolve_cond(c.ref) is None:
                out.append(self._relation(c.abbrev[1], c.ref, c.abbrev[0] == "="))
        elif isinstance(c, E.ClassCond):
            if c.kind in ("POSITIVE", "NEGATIVE", "ZERO"):
                out.append(self._relation(c.operand, E.Fig("ZEROS")))  # cobc: x > ZERO, a constant
        elif isinstance(c, E.Rel):
            out.append(self._relation(c.left, c.right, c.op == "="))

    @staticmethod
    def _relation(x, y, equality: bool = False) -> O.Relation:
        return O.Relation(x, y, equality)

    def field_constant(self, ref: E.Ref, lit, equality: bool) -> bool:
        """Whether cobc decides a relation of a USAGE DISPLAY item with a literal at compile time (cobc/tree.c
        compare_field_literal): a literal longer than an alphanumeric item, or with more decimals or more integer
        digits than a numeric one, makes = / NOT = constant -- and, for more integer digits, < > <= >= on a numeric
        item too. Such a relation is neither walked nor built (#4287)."""
        try:
            it = self.resolve(ref)
        except Untranslatable:
            return False
        if it.usage != "DISPLAY" or it.level == 88:
            return False
        if isinstance(lit, O.Num):
            data, lscale = lit.digits, lit.scale
        elif isinstance(lit, E.Fig):  # ZERO: cb_zero_lit
            data, lscale = "0", 0
        elif isinstance(lit, E.Lit) and isinstance(lit.value, str):
            data, lscale = lit.value, 0
        else:
            return False
        refmod_length = 0
        if ref.refmod is not None:
            start, length = ref.refmod
            if length is not None and isinstance(length, E.Lit) and isinstance(length.value, Decimal):
                refmod_length = int(length.value)
            elif isinstance(start, E.Lit) and isinstance(start.value, Decimal) and length is None:
                refmod_length = it.size - int(start.value) + 1
            else:
                return False
        lit_length = len(data.rstrip(" "))
        numeric = it.category in ("NUMERIC", "NUMERIC-EDITED")
        if not numeric or refmod_length:
            return equality and lit_length > (refmod_length or it.size)
        fscale = it.scale
        if fscale < 0 or not data.isdigit():
            return False
        if set(data) == {"0"}:
            i, scale = 0, 0
        else:
            lit_start = len(data) - len(data.lstrip("0"))
            lit_length -= lit_start
            scale, i, j = lscale, lit_length, len(data)
            while scale > 0 and j > 0 and data[j - 1] == "0":
                scale, i, j = scale - 1, i - 1, j - 1
        if scale > 0 and fscale < scale:
            return equality
        if i - scale > 0 and it.size - fscale >= 0 and i - scale > it.size - fscale:
            return equality or it.category == "NUMERIC"
        return False

    def plan_relations(self, groups: list[list[O.Relation]], evaluate: bool = False) -> list[dict]:
        state_in, self.leak = (None if evaluate else self.leak), None
        try:
            out = O.plan_condition(groups, self.osvs_leaf, self.osvs_length, evaluate, state_in, self.field_constant)
        except O.OsvsError as e:
            raise Untranslatable(f"ARITHMETIC-OSVS: {e} (#4287)") from e
        self.leak = out if evaluate else None
        return [r.plan for g in groups for r in g]

    @contextlib.contextmanager
    def relations_planned(self, plans: list[dict]):
        outer, self.rel_plans = self.rel_plans, list(plans)
        try:
            yield
            if self.rel_plans:
                raise Untranslatable("ARITHMETIC-OSVS: a condition's relations out of step with their plan (#4287)")
        finally:
            self.rel_plans = outer

    @contextlib.contextmanager
    def relation(self):
        """One relation being generated: its plan, the next of the condition's (none outside a planned one)."""
        if self.rel_plans is None:
            plan: dict = {}
        elif not self.rel_plans:
            raise Untranslatable("ARITHMETIC-OSVS: a condition's relations out of step with their plan (#4287)")
        else:
            plan = self.rel_plans.pop(0)
        with self.osvs_plan(plan):
            yield

    def cond_top(self, c) -> str:
        """A condition as cobc builds one (cb_build_cond then cb_end_cond: IF, PERFORM UNTIL, SEARCH WHEN)."""
        if isinstance(c, tuple):
            self.leak = None
            return self.cond(c)
        rels: list = []
        self.cond_relations(c, rels)
        with self.relations_planned(self.plan_relations([rels])):
            return self.cond(c)

    @contextlib.contextmanager
    def floating(self, mode: str | None):
        outer, self.fmode = self.fmode, mode
        try:
            yield
        finally:
            self.fmode = outer

    def fnum(self, e) -> str:
        """A floating-point expression (self.fmode): HFP values as exact BigDecimals (cobolrt/Hfp) -- a float item
        as it is, any other operand converted to long, each operation HFP's own (truncating, one guard digit)."""
        lng = _b(self.fmode == "LONG")
        if isinstance(e, E.Lit) and isinstance(e.value, Decimal):
            return f"Hfp.of({self.const(e.value)})"
        if isinstance(e, E.Fig) and e.kind == "ZEROS":
            return "BigDecimal.ZERO"
        if isinstance(e, E.Ref):
            if self.float_item(e) is not None:
                return f"Cobol.num({self.value_field(e)}, CS)"
            with self.floating(None):
                return f"Hfp.of({self.num(e)})"
        if isinstance(e, E.Neg):
            return f"{self.fnum(e.operand)}.negate()"
        if isinstance(e, E.Bin):
            if e.op == "**":
                raise Untranslatable(
                    "exponentiation in a floating-point expression (IBM's run-time routine is not documented bit for "
                    "bit; oracle_assumptions.md C6)"
                )
            fn = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}[e.op]
            return f"Hfp.{fn}({self.fnum(e.left)}, {self.fnum(e.right)}, {lng})"
        if isinstance(e, E.LengthOf):
            with self.floating(None):
                return f"Hfp.of({self.num(e)})"
        if isinstance(e, E.Func):
            raise Untranslatable(f"FUNCTION {e.name} in a floating-point expression (oracle_assumptions.md C6)")
        raise Untranslatable(f"floating-point expression {type(e).__name__}")

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

    def find_by_id(self, entity: str, repo: str) -> str:
        """`.withFindById(...)` for a store of the entity's primary key, or "" when its id is not the key's."""
        if self.java_root is None:
            return ""
        from gitgalaxy.tools.cobol_to_java.det.entity import id_method

        if entity not in self.id_methods:
            m = id_method(self.java_root, entity, self.factory)
            self.id_methods[entity] = m.code if m else None
        if self.id_methods[entity] is None:
            return ""
        return f".withFindById(rec -> {repo}.findById(id_{entity}(rec)))"

    def method(self, i: int) -> str:
        """The Java method of paragraph i: p{i} (dispatcher), else the paragraph's name in camelCase."""
        if not self.structured:
            return f"p{i}"
        if not hasattr(self, "_methods"):
            self._methods: list[str] = []
            taken: set[str] = set()
            for p in self.p.proc.paragraphs:
                base = camel(p.name)
                base = base if base[:1].isalpha() else "p" + base[:1].upper() + base[1:]
                name, k = base, 1
                while name in taken or name in JAVA_RESERVED or name in METHODS_TAKEN:
                    k += 1
                    name = f"{base}{k}"
                taken.add(name)
                self._methods.append(name)
        return self._methods[i]

    def perform_call(self, a: int, b: int, ind: str) -> list[str]:
        """PERFORM a THRU b: the dispatcher, or (structured) each paragraph of the range called in order."""
        if not self.structured:
            return [f"{ind}perform({a}, {b});"]
        return [f"{ind}{self.method(i)}();" for i in range(a, b + 1)]

    def jump(self, target: str) -> str:
        """A transfer to a paragraph (a HANDLE exit): the dispatcher's GOTO; a structured program has no HANDLE."""
        if not self.structured:
            return f"return GOTO | {target};"
        return 'throw new IllegalStateException("a HANDLE exit in a program without HANDLE");'

    # ---- B3: lifted (typed) items -------------------------------------------------------------------------------
    def check_lift(self, it: L.Item) -> bool:
        """An item used through its bytes: a lifted item is a violation. A group holding lifted items is one too,
        unless groups are synced: then True -- its expression packs them into its bytes first, and the statement
        unpacks them after a write."""
        if not self.lifted:
            return False
        if id(it) in self.lifted:
            self.violate(it)
            return False
        inside = [x for x in it.walk() if id(x) in self.lifted]
        if not inside:
            return False
        if not self.sync_groups:
            for x in inside:
                self.violate(x)
            return False
        self.synced[id(it)] = it
        self.touched[id(it)] = self.touched.get(id(it), False) or self._reading == 0
        return True

    @contextlib.contextmanager
    def reading(self):
        """Operands named inside are only read (a group so named needs no unpack after the statement)."""
        self._reading += 1
        try:
            yield
        finally:
            self._reading -= 1

    COMPOUND = frozenset({"IF", "EVALUATE", "PERFORM", "SEARCH"})

    def after_statement(self, s: S.Stmt, lines: list[str], ind: str) -> list[str]:
        """A synced group's bytes around this statement's own uses of it (nested statements did theirs):
        - a simple statement: its typed fields packed into them ONCE, before it -- a second pack inside it would
          overwrite what it had just written (INITIALIZE's elements) -- and unpacked after it when it may write;
        - a condition (IF, EVALUATE, PERFORM UNTIL, SEARCH): packed where it is evaluated, every time (a loop body
          may change the typed fields between evaluations); a condition only reads.
        A written group's typed numbers cannot be unpacked exactly (the bytes may be no number: MOVE SPACES), and a
        write that can transfer control before the unpack leaves the typed fields stale: both are violations --
        those items stay byte storage."""
        if not self.touched:
            return lines
        compound = s.kind in self.COMPOUND
        out, before = [], []
        for ln in lines:
            for g in self.touched:
                fid = self.ids[g]
                token = f"\x00PACK:{fid}\x00"
                if token in ln:
                    ln = ln.replace(token, f"pack_{fid}()" if compound else fid)
                    if not compound and fid not in before:
                        before.append(fid)
            out.append(ln)
        at = 1 if out and out[0].lstrip().startswith("//") else 0  # after the statement's own COBOL comment
        out[at:at] = [f"{ind}pack_{fid}();" for fid in before]
        written = [self.synced[t] for t, w in self.touched.items() if w and not compound]
        if not written:
            return out
        code = [ln for ln in lines if not ln.lstrip().startswith("//")]  # (the COBOL comments say RETURN)
        transfers = any(re.search(r"\b(?:return|throw)\b|\bjump\(", ln) for ln in code)
        # A statement with phrases of its own (READ ... INVALID KEY / AT END, ON SIZE ERROR, ON OVERFLOW ...) runs
        # them before its end -- before the unpack: they would read stale typed fields, and the unpack would undo
        # their own typed writes. Its written groups keep byte storage.
        nested = bool(s.body or s.orelse or any(s.phrases.values()))
        for grp in written:
            for x in grp.walk():
                if id(x) in self.lifted and (transfers or nested or self.lifted[id(x)] == "NUM"):
                    self.violate(x)
            out.append(f"{ind}unpack_{self.ids[id(grp)]}();")
        return out

    def violate(self, it: L.Item) -> str:
        """Record a lifted item used through its bytes (the translation is repeated without lifting it)."""
        self.violations.add(it.name)
        return "/* lift violation */"

    def lift(self, e):
        """(kind, Java name, item) of a lifted item named plainly (no subscript, no reference modification)."""
        if isinstance(e, E.Ref) and not e.subscripts and e.refmod is None:
            try:
                it = self.resolve(e)
            except Untranslatable:
                return None
            k = self.lifted.get(id(it))
            if k:
                return k, self.ids[id(it)], it
        return None

    def lift_text(self, e, n: int) -> str | None:
        """A literal / figurative as the n bytes an alphanumeric MOVE leaves (computed now), as a Java literal."""
        if isinstance(e, E.Lit) and isinstance(e.value, str):
            return jstr(e.value[:n].ljust(n))
        if isinstance(e, E.Lit) and isinstance(e.value, bytes):
            return jstr(e.value.decode("latin-1")[:n].ljust(n))
        if isinstance(e, E.Fig):
            if e.kind == "ALL":
                pat = e.all_literal or " "
                return jstr((pat * (n // len(pat) + 1))[:n])
            return jstr(str(self.fig_char(e.kind)) * n)
        return None

    def bin_value(self, it: L.Item, v: Decimal) -> int:
        """A numeric literal stored in a binary item and read back (TRUNC(BIN), as the runtime: the integer part,
        the sign dropped for an unsigned item, wrapped to the item's 2 / 4 / 8 bytes)."""
        n = int(v)  # toward zero
        if not it.signed:
            n = abs(n)
        bits = 8 * it.size
        n &= (1 << bits) - 1
        if it.signed and n >= 1 << (bits - 1):
            n -= 1 << bits
        return n

    def move_lifted(self, src, lt) -> str:
        kind, name, it = lt
        if kind == "X":
            t = self.lift_text(src, it.size)
            if t is not None:
                return f"{name} = {t};"
            ls = self.lift(src)
            if ls and ls[0] == "X":
                return f"{name} = {ls[1]};" if ls[2].size == it.size else f"{name} = Cobol.fit({ls[1]}, {it.size});"
            if isinstance(src, E.Ref):
                with self.reading():
                    return f"{name} = Cobol.moveText({self.field_expr(src)}, {it.size}, CS);"
            return self.violate(it)
        if kind == "NUM":  # a numeric sender's value, stored as the item stores it; any other sender: its bytes
            if isinstance(src, E.Fig) and src.kind == "ZEROS":
                return f"{name} = BigDecimal.ZERO;"
            # A MOVE keeps the sending sign through truncation, so a signed item can receive negative zero --
            # -0.05 or -1000 into S9(3) is 00} -- which a BigDecimal cannot hold (an arithmetic store gives +0:
            # NEGZERO in test_det_programs). Typed only when no negative zero can arrive: a literal that does not
            # truncate to one, a typed sender whose digits all fit (it is never -0 itself); never an item's bytes.
            if it.signed and not self.fits_without_negative_zero(src, it):
                return self.violate(it)
            if self.is_numeric(src) and not (isinstance(src, E.Ref) and self.resolve(src).category != "NUMERIC"):
                return self.store_into(E.Ref(it.name), self.num(src), False)
            return self.violate(it)
        if isinstance(src, E.Lit) and isinstance(src.value, Decimal):
            return f"{name} = {self.bin_value(it, src.value)}L;"
        if isinstance(src, E.Fig) and src.kind == "ZEROS":
            return f"{name} = 0L;"
        ls = self.lift(src)
        if ls and ls[0] == "BIN" and ls[2].size == it.size and ls[2].signed == it.signed:
            return f"{name} = {ls[1]};"
        return self.violate(it)

    def literal_moved(self, v: Decimal, target: E.Ref) -> Decimal:
        """The literal a MOVE stores. GnuCOBOL (-std=ibm) folds an integer literal MOVEd to a zoned item of scale 0
        at compile time: truncated to zero, it is +0 (MOVE -1000 TO S9(3) is 00{), where every other MOVE keeps
        the sign (-1000.0, -0.05, a scaled or COMP-3 target, a field sender: 00}). The probe:
        test_det_programs.py NEGZERO; a declared difference -- IBM's behaviour is not measured."""
        exponent = v.as_tuple().exponent
        if not v.is_signed() or not isinstance(exponent, int) or exponent < 0:
            return v
        try:
            it = self.resolve(target)
        except Untranslatable:
            return v
        if target.refmod is not None or it.category != "NUMERIC" or it.usage != "DISPLAY" or it.scale != 0:
            return v
        if it.sign_separate:
            return v
        return v if abs(v) % (Decimal(10) ** it.digits) else Decimal(0)

    def fits_without_negative_zero(self, src, it: L.Item) -> bool:
        """Whether a MOVE of `src` into the signed numeric item `it` cannot leave negative zero there."""
        whole, scale = it.digits - it.scale, it.scale
        if isinstance(src, E.Lit) and isinstance(src.value, Decimal):
            v = src.value
            kept = abs(v) % (Decimal(10) ** whole)  # high-order digits beyond the PICTURE go
            kept = kept.quantize(Decimal(1).scaleb(-scale), rounding="ROUND_DOWN")  # so do low-order ones
            return not (v.is_signed() and kept == 0)
        ls = self.lift(src)
        if ls is None:
            return False  # an item's bytes may be negative zero, or truncate to it
        _kind, _name, s = ls
        if ls[0] == "BIN":  # a long holds what its bytes hold, past its PICTURE's digits
            return {2: 5, 4: 10, 8: 19}[s.size] <= whole and scale >= 0
        return s.digits - s.scale <= whole and s.scale <= scale

    def rel_lifted(self, jop: str, a, b) -> str | None:
        """A relation with a lifted item on either side, or None (not one)."""
        la, lb = self.lift(a), self.lift(b)
        if not la and not lb:
            return None
        if not la:
            flipped = {"==": "==", ">": "<", "<": ">", ">=": "<=", "<=": ">="}[jop]
            return self.rel_lifted(flipped, b, a)
        kind, name, it = la
        if kind == "NUM":
            if isinstance(b, E.Fig) and b.kind == "ZEROS":
                return f"{name}.signum() {jop} 0"
            if self.is_numeric(b):
                return f"{name}.compareTo({self.num(b)}) {jop} 0"
            return self.violate(it)
        if kind == "BIN":
            if isinstance(b, E.Lit) and isinstance(b.value, Decimal):
                if b.value == b.value.to_integral_value():
                    return f"{name} {jop} {int(b.value)}L"
                return f"BigDecimal.valueOf({name}).compareTo({self.const(b.value)}) {jop} 0"
            if isinstance(b, E.Fig) and b.kind == "ZEROS":
                return f"{name} {jop} 0L"
            if lb and lb[0] == "BIN":
                return f"{name} {jop} {lb[1]}"
            if self.is_numeric(b):
                return f"BigDecimal.valueOf({name}).compareTo({self.num(b)}) {jop} 0"
            return self.violate(it)
        # an alphanumeric item: COBOL's comparison of nonnumeric operands
        c = self.coll(jop, b)
        t = self.lift_text(b, it.size) if not (isinstance(b, E.Lit) and isinstance(b.value, Decimal)) else None
        if (
            t is not None
            and isinstance(b, (E.Lit, E.Fig))
            and (not isinstance(b, E.Lit) or len(str(b.value)) <= it.size)
        ):
            if jop == "==" and not c:
                return f"{name}.equals({t})"
            return f"Cobol.compareText({name}, {t}, CS{c}) {jop} 0"
        if lb and lb[0] == "X":
            return f"Cobol.compareText({name}, {lb[1]}, CS{c}) {jop} 0"
        if isinstance(b, E.Ref):
            flipped = {"==": "==", ">": "<", "<": ">", ">=": "<=", "<=": ">="}[jop]
            return f"Cobol.compare({self.field_expr(b)}, {name}, CS{c}) {flipped} 0"
        if isinstance(b, E.Lit) and isinstance(b.value, str):  # a literal longer than the item
            return f"Cobol.compareText({name}, {jstr(b.value)}, CS{c}) {jop} 0"
        if isinstance(b, E.Func):
            return f"Cobol.compareText({name}, {self.text(b)}, CS{c}) {jop} 0"
        return self.violate(it)

    def eib(self, name: str) -> str:
        return self.field_expr(E.Ref(name, ["DFHEIBLK"]))

    # ---- values -----------------------------------------------------------------------------------------------------
    def const(self, v: Decimal) -> str:
        key = str(v)
        if key not in self.consts:
            # named by its value: D16, D0_05 (0.05), DM1 (-1); the literal's scale is kept (16 and 16.0 differ)
            name = "D" + re.sub(r"[^A-Za-z0-9]", "_", key.replace("-", "M"))
            while name in self.consts.values():
                name += "_"
            self.consts[key] = name
        return self.consts[key]

    @_reads
    def num(self, e) -> str:
        """A Java BigDecimal expression for an arithmetic expression."""
        if self.fmode is not None:
            return self.fnum(e)
        if self.has_float(e):  # an expression with a float operand outside a statement's own mode: a comparand
            with self.floating("LONG"):
                return self.fnum(e)
        if isinstance(e, E.Lit):
            if isinstance(e.value, Decimal):
                return self.const(e.value)
            raise Untranslatable("a nonnumeric literal in arithmetic")
        lo = self.lift(e)
        if lo and lo[0] == "BIN":
            return f"BigDecimal.valueOf({lo[1]})"
        if lo and lo[0] == "NUM":
            return lo[1]
        if isinstance(e, E.Ref):
            it = self.resolve(e)
            if it.category not in ("NUMERIC", "NUMERIC-EDITED"):
                # an alphanumeric used as a number (e.g. a PIC X subscript): its digits
                return f"Cobol.num({self.field_expr(e)}, CS)"
            return f"Cobol.num({self.field_expr(e)}, CS)"
        if isinstance(e, E.Fig) and e.kind == "ZEROS":
            return "BigDecimal.ZERO"
        if isinstance(e, (E.Bin, E.Neg)):
            p = self.osvs.get(id(e))
            if p is not None and p[0] == "FOLD":  # cobc folded the two literals at compile time (det/osvs.py)
                return self.const(p[1].value)
            v = self.num_op(e)
            # ARITHMETIC-OSVS: cobc truncates this intermediate (cob_decimal_align, det/osvs.py)
            return f"Cobol.align({v}, {p[1]})" if p is not None else v
        if isinstance(e, E.LengthOf):
            it = self.resolve(e.ref)
            return f"BigDecimal.valueOf({it.size * it.occurs})"
        if isinstance(e, E.Func):
            return self.func(e)
        raise Untranslatable(f"expression {type(e).__name__}")

    def dc(self, n: O.Num) -> str:
        """libcob's decimal constant of a literal (Cobol.Dc): one per literal as cobc keys it (its digits as written,
        scale and sign), its scale changed by use."""
        if n.key not in self.dcs:
            name = "DC_" + re.sub(r"[^A-Za-z0-9]", "_", str(n.value).replace("-", "M"))
            while name in (x for x, _ in self.dcs.values()):
                name += "_"
            self.dcs[n.key] = (name, str(n.value))
        return self.dcs[n.key][0]

    def dc_literal(self, e) -> O.Num | None:
        """The literal on the right of an operation that cobc makes a decimal constant (planned expressions only)."""
        if O.PLANNED not in self.osvs:
            return None
        p = self.osvs.get(id(e))
        if p is not None and p[0] == "FOLD":
            return p[1]
        if isinstance(e, E.Lit) and isinstance(e.value, Decimal):
            return O.Num.written(e.text) if e.text else O.Num.of(e.value)
        if isinstance(e, E.LengthOf):
            return O.Num.of(Decimal(self.osvs_length(e)))
        return None

    def num_op(self, e) -> str:
        # an operand that may be libcob's NaN (a zero divisor, #4655): the operation through Cobol, NaN in, NaN out
        nan = not self.intr and self.fmode is None
        if isinstance(e, E.Neg):
            nan = nan and _may_nan(e.operand)
            if O.PLANNED in self.osvs:  # cobc: 0 - x (its scale: x's, at least 0; a literal x a decimal constant)
                lit = self.dc_literal(e.operand)
                if lit is not None:
                    return f"Cobol.subtract(BigDecimal.ZERO, {self.dc(lit)})"
                if nan:
                    return f"Cobol.subtract(BigDecimal.ZERO, {self.num(e.operand)})"
                return f"BigDecimal.ZERO.subtract({self.num(e.operand)})"
            if nan:
                return f"Cobol.negate({self.num(e.operand)})"
            return f"{self.num(e.operand)}.negate()"
        nan = nan and (_may_nan(e.left) or _may_nan(e.right))
        lit = self.dc_literal(e.right)
        if lit is not None:
            a = self.num(e.left)
            if e.op == "**" and lit.sign < 0:
                raise Untranslatable(
                    "ARITHMETIC-OSVS: a negative literal exponent (libcob overwrites the constant, #4287)"
                )
            fn = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "**": "power"}[e.op]
            return f"Cobol.{fn}({a}, {self.dc(lit)})"
        a, b = self.num(e.left), self.num(e.right)
        if nan and e.op in ("+", "-", "*"):
            return f"Cobol.{ {'+': 'add', '-': 'subtract', '*': 'multiply'}[e.op] }({a}, {b})"
        if e.op == "+":
            return f"{a}.add({b})"
        if e.op == "-":
            return f"{a}.subtract({b})"
        if e.op == "*":
            return f"{a}.multiply({b})"
        if e.op == "/":
            return f"Cobol.divideIntr({a}, {b})" if self.intr else f"Cobol.divide({a}, {b})"
        if e.op == "**":
            return f"Cobol.power({a}, {b})"
        raise Untranslatable(f"operator {e.op}")

    def func(self, f: E.Func) -> str:
        refmod = next((a[1] for a in f.args if isinstance(a, tuple) and a[0] == "REFMOD"), None)
        if refmod is None:
            return self.intr_func(f)
        # #4462: FUNCTION CURRENT-DATE (1:4): the characters of the function's text (an alphanumeric function only)
        if f.name not in ("UPPER-CASE", "LOWER-CASE", "TRIM", "REVERSE", "CURRENT-DATE"):
            raise Untranslatable(f"FUNCTION {f.name} with a reference modification")
        start, length = refmod
        at = f"{self.int_expr(start)} - 1"
        end = f", {at} + {self.int_expr(length)}" if length is not None else ""
        return f"{self.intr_func(f)}.substring({at}{end})"

    def intr_func(self, f: E.Func) -> str:
        self.intr += 1
        try:
            return self._func(f)
        finally:
            self.intr -= 1

    def _func(self, f: E.Func) -> str:
        name = f.name
        args = [a for a in f.args if not (isinstance(a, tuple) and a[0] == "REFMOD")]
        if name == "TRIM" and len(args) == 2 and isinstance(args[1], E.Ref) and args[1].name in ("LEADING", "TRAILING"):
            return f"Funcs.trim{args[1].name.title()}({self.text(args[0])})"
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
        if name == "RANDOM" and len(args) <= 1:
            # the run unit's sequence (Funcs.Random): the oracle's generator, not z/OS's (oracle_assumptions C12)
            self.uses_random = True
            return f"funcRandom.next({self.num(args[0])})" if args else "funcRandom.next()"
        raise Untranslatable(f"FUNCTION {name}")

    @_reads
    def text(self, e) -> str:
        """A Java String for an operand's text."""
        if isinstance(e, E.Lit):
            if isinstance(e.value, Decimal):
                return jstr(str(e.value))
            if isinstance(e.value, bytes):
                return jstr(e.value.decode("latin-1"))
            return jstr(e.value)
        lo = self.lift(e)
        if lo and lo[0] == "X":
            return lo[1]
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
                return self.resolve(e).category in ("NUMERIC", "FLOAT")
            except Untranslatable:
                return False
        if isinstance(e, (E.Bin, E.Neg, E.LengthOf)):
            return True
        if isinstance(e, E.Func):
            return e.name in ("NUMVAL", "NUMVAL-C", "TEST-NUMVAL", "TEST-NUMVAL-C", "INTEGER-OF-DATE", "DATE-OF-INTEGER", "INTEGER", "MOD",
                              "REM", "ABS", "LENGTH", "MIN", "MAX", "INTEGER-PART", "RANDOM")  # fmt: skip
        return False

    # ---- conditions ---------------------------------------------------------------------------------------------
    @_reads
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
                with self.relation():
                    t = self.rel(op, subject, c.ref)
                return f"!({t})" if negated else t
            if cn is None:
                raise Untranslatable(f"condition-name {c.ref.name}")
            return self.cond_test(cn, c.ref.subscripts)
        if isinstance(c, E.ClassCond):
            if c.kind in ("POSITIVE", "NEGATIVE", "ZERO"):
                sig = {"POSITIVE": "> 0", "NEGATIVE": "< 0", "ZERO": "== 0"}[c.kind]
                with self.relation():
                    t = f"{self.num(c.operand)}.signum() {sig}"
            else:
                if not isinstance(c.operand, E.Ref):
                    raise Untranslatable("class condition on an expression")
                fn = {"NUMERIC": "isNumeric", "ALPHABETIC": "isAlphabetic", "ALPHABETIC-UPPER": "isAlphabeticUpper",
                      "ALPHABETIC-LOWER": "isAlphabeticLower"}[c.kind]  # fmt: skip
                t = f"Cobol.{fn}({self.field_expr(c.operand)}, CS)"
            return f"!({t})" if c.negated else t
        if isinstance(c, E.Rel):
            with self.relation():
                return self.rel(c.op, c.left, c.right)
        raise Untranslatable(f"condition {type(c).__name__}")

    def rel(self, op: str, a, b) -> str:
        jop = {"=": "==", ">": ">", "<": "<", ">=": ">=", "<=": "<="}[op]
        if self.has_float(a) or self.has_float(b):
            return self.rel_float(jop, a, b)
        lifted = self.rel_lifted(jop, a, b)
        if lifted is not None:
            return lifted
        # numeric comparison when both sides are numeric (or one is ZERO against a number)
        if (self.is_numeric(a) and self.is_numeric(b)) or (
            self.is_numeric(a) and isinstance(b, E.Fig) and b.kind == "ZEROS") or (
            self.is_numeric(b) and isinstance(a, E.Fig) and a.kind == "ZEROS"):  # fmt: skip
            return f"{self.num(a)}.compareTo({self.num(b)}) {jop} 0"
        if isinstance(a, E.Ref):
            return f"{self.cmp(a, b, jop)} {jop} 0"
        if isinstance(b, E.Ref):
            flipped = {"==": "==", ">": "<", "<": ">", ">=": "<=", "<=": ">="}[jop]
            return f"{self.cmp(b, a, jop)} {flipped} 0"
        if isinstance(a, E.Func) or isinstance(b, E.Func):
            c = self.coll(jop)
            if c:
                return f"Cobol.compareText({self.text(a)}, {self.text(b)}, CS{c}) {jop} 0"
            return f"Cobol.compareText({self.text(a)}, {self.text(b)}) {jop} 0"
        raise Untranslatable("comparison of two non-data operands")

    def rel_float(self, jop: str, a, b) -> str:
        """A comparison with a COMP-1 / COMP-2 comparand, in floating point (IBM: "if either comparand is a
        floating-point value"): long, unless both are COMP-1 items -- a fixed-point comparand converted to long."""
        for x in (a, b):
            if (isinstance(x, E.Fig) and x.kind != "ZEROS") or not (self.is_numeric(x) or isinstance(x, E.Fig)):
                raise Untranslatable(f"a COMP-1 / COMP-2 item compared with a nonnumeric operand ({FLOAT_BYTES})")
        fa, fb = self.float_item(a), self.float_item(b)
        mode = "SHORT" if fa is not None and fb is not None and fa.usage == fb.usage == "COMP-1" else "LONG"
        with self.floating(mode):
            return f"{self.num(a)}.compareTo({self.num(b)}) {jop} 0"

    def cmp(self, a: E.Ref, b, jop: str = "<") -> str:
        """A comparison of `a` with `b` as an int (<0, 0, >0); `jop` the relation it is for: an alphanumeric one is
        made under the PROGRAM COLLATING SEQUENCE where that can change its result (self.coll)."""
        fa = self.field_expr(a)
        numeric = self.is_numeric(a) and (
            self.is_numeric(b) or (isinstance(b, E.Fig) and b.kind == "ZEROS") or isinstance(b, (E.Bin, E.Neg))
        )
        c = "" if numeric else self.coll(jop, a, b)
        if isinstance(b, E.Ref):
            return f"Cobol.compare({fa}, {self.field_expr(b)}, CS{c})"
        if isinstance(b, E.Lit):
            if isinstance(b.value, Decimal):
                return f"Cobol.compare({fa}, {self.const(b.value)}, CS{c})"
            return f"Cobol.compare({fa}, {self.text(b)}, CS{c})"
        if isinstance(b, E.Fig):
            if b.kind == "ALL":  # the literal repeated to the item's length (#4557)
                return f"Cobol.compareAll({fa}, {jstr(b.all_literal or '')}, CS{c})"
            return f"Cobol.compareFigurative({fa}, Figurative.{self.fig(b.kind)}, CS{c})"
        if isinstance(b, E.Func):
            if c:
                return f"Cobol.compareText(Cobol.text({fa}, CS), {self.text(b)}, CS{c})"
            return f"Cobol.compareText(Cobol.text({fa}, CS), {self.text(b)})"
        if isinstance(b, (E.Bin, E.Neg)):
            return f"Cobol.num({fa}, CS).compareTo({self.num(b)})"
        raise Untranslatable(f"comparison with {type(b).__name__}")

    # ---- PROGRAM COLLATING SEQUENCE (#4539) -------------------------------------------------------------------
    def coll(self, jop: str, *operands) -> str:
        """The argument suffix ', COLLATING' when a nonnumeric relation `jop` compares under the PROGRAM COLLATING
        SEQUENCE, else ''.

        IBM (Enterprise COBOL 6.4 Language Reference, OBJECT-COMPUTER paragraph; "Comparison of alphanumeric
        operands"): the program collating sequence orders the nonnumeric comparisons of relation conditions
        (condition-names, EVALUATE, PERFORM UNTIL and SEARCH conditions are relation conditions), never a numeric one
        (by value) nor a national one (the translator refuses national data). NATIVE, STANDARD-1 and STANDARD-2 are
        the data's byte order (register D1; Gen.collating). Under an EBCDIC or a literal alphabet an ordering relation
        (<, >, <=, >=, a THRU range) is made in the alphabet (Sort.Collating: IBM's order, refused by name where
        GnuCOBOL's differs); an equality only when the alphabet has ALSO -- without it each character has a position
        of its own, so equal positions are equal bytes. Each item operand must hold characters only (an alphabet
        orders characters; a packed or binary byte is no character)."""
        name = self.program_collating
        if name is None or (jop == "==" and "ALSO" not in self.alphabets.get(name, [])):
            return ""
        expr = self.collating("relation condition: PROGRAM", name)
        if expr is None:
            return ""
        for e in operands:
            if isinstance(e, E.Ref):
                it = self.resolve(e)
                if not (_text_item(it) or _unsigned_zoned(it)):
                    raise Untranslatable(f"{e.name} compared under PROGRAM COLLATING SEQUENCE {name}: holds "
                                         f"numeric or national items: not modelled")  # fmt: skip
        self.pcs_used = expr
        return ", COLLATING"

    def fig(self, kind: str) -> str:
        """The runtime's Figurative constant, refused by name where the PROGRAM COLLATING SEQUENCE defines it."""
        self.fig_char(kind)
        return _fig(kind)

    def fig_char(self, kind: str) -> str | None:
        """A figurative's character (None for ALL). HIGH-VALUE and LOW-VALUE are the characters of the highest and
        the lowest position in the program collating sequence (IBM: Language Reference, "Figurative constant
        values"; GnuCOBOL likewise: LOW-VALUE is a literal alphabet's first character). Under a literal alphabet
        they are not X'FF' / X'00': refused by name. Under EBCDIC they are the native ones on both sides."""
        name = self.program_collating
        if kind in ("HIGH", "LOW") and name is not None:
            defn = self.alphabets.get(name) or ["?"]
            if defn[0] not in ("NATIVE", "STANDARD-1", "STANDARD-2", "EBCDIC"):
                raise Untranslatable(f"{kind}-VALUE under PROGRAM COLLATING SEQUENCE {name} (the character of its "
                                     f"{'highest' if kind == 'HIGH' else 'lowest'} position): not modelled")  # fmt: skip
        return FIG_CHAR.get(kind)

    def cond_field(self, cn: L.Item, subscripts=()) -> str:
        """The item an 88 tests, its subscripts applied (the 88's own, as written on the condition-name)."""
        parent = cn.parent
        if parent is None:
            raise Untranslatable(f"88 {cn.name}: no parent item")
        self.check_lift(parent)  # an 88 on a group holding a lifted item
        if parent.category != "FLOAT" and self.overlaps_float(parent):
            raise Untranslatable(f"88 {cn.name}: its item's bytes hold a COMP-1 / COMP-2 item ({FLOAT_BYTES})")
        f = self.ids.get(id(parent))
        if f is None:
            raise Untranslatable(f"88 {cn.name}: no item")
        levels = _occurs_chain(parent)
        if len(levels) != len(subscripts):
            raise Untranslatable(f"88 {cn.name}: {len(subscripts)} subscripts for {len(levels)} OCCURS levels")
        for lvl, sub in zip(levels, subscripts):
            f += f".at({self.int_expr(sub)}, {lvl.size})"
        return f

    @staticmethod
    def value_node(v):
        """An 88 / VALUE entry as an expression node."""
        kind = v[0]
        if kind == "num":
            return E.Lit(v[1])
        if kind == "lit":
            return E.Lit(v[1])
        if kind == "hex":
            return E.Lit(v[1])
        if kind == "fig":
            return E.Fig(v[1])
        raise Untranslatable(f"88 value {kind}")

    def cond_test(self, cn: L.Item, subscripts=()) -> str:
        """An 88's test. Without subscripts it is a named method of the service (isAcctActive() for 88
        ACCT-ACTIVE), emitted once and called at each use: the same test, so behaviour does not change."""
        if subscripts:
            return self._cond_body(cn, subscripts)
        known = self.cond_methods.get(id(cn))
        if known is None:
            body = self._cond_body(cn, subscripts)
            base = "is" + "".join(w[:1].upper() + w[1:] for w in [camel(cn.name)])
            name, k = base, 1
            paras = {self.method(i) for i in range(len(self.p.proc.paragraphs))} if self.structured else set()
            while name in self.taken_names or name in JAVA_RESERVED or name in METHODS_TAKEN or name in paras:
                k += 1
                name = f"{base}{k}"
            self.taken_names.add(name)
            known = self.cond_methods[id(cn)] = (name, body, cn)
        return f"{known[0]}()"

    def cond_method_lines(self) -> list[str]:
        """The condition-name methods, in order of first use: each traces to its 88 and the item it tests."""
        out = []
        for name, body, cn in self.cond_methods.values():
            parent = cn.parent.name if cn.parent is not None else "?"
            out += [f"    /** 88 {cn.name} of {parent}. */", f"    private boolean {name}() {{ return {body}; }}", ""]
        return out

    def _cond_body(self, cn: L.Item, subscripts=()) -> str:
        if cn.parent is not None and id(cn.parent) in self.lifted and not subscripts:
            item = E.Ref(cn.parent.name)
            tests = []
            for v in cn.values:
                if v[0] == "range":
                    tests.append(f"({self.rel('>=', item, self.value_node(v[1]))} && "
                                 f"{self.rel('<=', item, self.value_node(v[2]))})")  # fmt: skip
                else:
                    tests.append(self.rel("=", item, self.value_node(v)))
            return "(" + " || ".join(tests) + ")" if len(tests) > 1 else tests[0]
        f = self.cond_field(cn, subscripts)
        if cn.parent is not None and cn.parent.category == "FLOAT":  # Cobol.compare: in floating point (long)
            for v in cn.values:
                for x in v[1:] if v[0] == "range" else [v]:
                    if not (x[0] == "num" or x == ("fig", "ZEROS")):
                        raise Untranslatable(f"88 {cn.name}: a nonnumeric value of a {cn.parent.usage} item")
        tests = []
        for v in cn.values:
            if v[0] == "range":
                lo, hi = v[1], v[2]
                tests.append(f"({self.vcmp(f, lo, cn, '<')} >= 0 && {self.vcmp(f, hi, cn, '<')} <= 0)")
            else:
                tests.append(f"{self.vcmp(f, v, cn, '==')} == 0")
        return "(" + " || ".join(tests) + ")" if len(tests) > 1 else tests[0]

    def vcmp(self, f: str, v, cn: L.Item | None = None, jop: str = "==") -> str:
        """An 88 value against its item as an int; a nonnumeric one under the PROGRAM COLLATING SEQUENCE where that
        can change the result (a THRU range: `jop` "<"; a value: "==")."""
        kind = v[0]
        parent = cn.parent if cn is not None else None
        numeric = (
            parent is not None and parent.category == "NUMERIC" and (kind == "num" or tuple(v) == ("fig", "ZEROS"))
        )
        c = ""
        if cn is not None and parent is not None and not numeric:
            c = self.coll(jop)
            if c and not (_text_item(parent) or _unsigned_zoned(parent)):
                raise Untranslatable(f"88 {cn.name} under PROGRAM COLLATING SEQUENCE {self.program_collating}: "
                                     f"{parent.name} holds numeric or national items: not modelled")  # fmt: skip
        if kind == "num":
            return f"Cobol.compare({f}, {self.const(v[1])}, CS{c})"
        if kind == "lit":
            return f"Cobol.compare({f}, {jstr(v[1])}, CS{c})"
        if kind == "fig":
            return f"Cobol.compareFigurative({f}, Figurative.{self.fig(v[1])}, CS{c})"
        if kind == "hex":
            return f"Cobol.compare({f}, {jstr(v[1].decode('latin-1'))}, CS{c})"
        raise Untranslatable(f"88 value {kind}")

    # ---- moves --------------------------------------------------------------------------------------------------
    def move(self, src, target: E.Ref) -> str:
        if self.float_item(target) is not None or self.float_item(src) is not None:
            return self.move_float(src, target)
        lt = self.lift(target)
        if lt:
            return self.move_lifted(src, lt)
        ls = self.lift(src)
        if ls and ls[0] == "X":  # a String sender: as an alphanumeric item of its length
            return f"Cobol.move({ls[1]}, {self.field_expr(target)}, CS);"
        if ls and self.resolve(target).category in ("NUMERIC", "NUMERIC-EDITED"):  # a number into a numeric item
            return f"Cobol.move({self.num(src)}, {self.field_expr(target)}, CS);"
        return self._move(src, target)

    def move_float(self, src, target: E.Ref) -> str:
        """A MOVE with a COMP-1 / COMP-2 sender or receiver (#4271): numbers only -- into a float, a numeric
        literal, ZERO or a numeric item (converted to its precision); out of one, into a numeric or numeric-edited
        item (rounded, IBM "Conversions and precision"). Its bytes never move (register C6)."""
        tf, sf = self.float_item(target), self.float_item(src)
        if tf is not None:
            ft = self.value_field(target)
            if isinstance(src, E.Lit) and isinstance(src.value, Decimal):
                return f"Cobol.move({self.const(src.value)}, {ft}, CS);"
            if isinstance(src, E.Fig) and src.kind == "ZEROS":
                return f"Cobol.moveFigurative(Figurative.ZEROS, {ft}, CS);"
            if isinstance(src, E.Ref) and (sf is not None or self.resolve(src).category == "NUMERIC"):
                if self.lift(src):
                    return f"Cobol.move({self.num(src)}, {ft}, CS);"
                with self.reading():
                    return f"Cobol.move({self.value_field(src)}, {ft}, CS);"
            raise Untranslatable(f"MOVE of a nonnumeric operand to {tf.name} {tf.usage} ({FLOAT_BYTES})")
        if sf is None:
            raise Untranslatable("MOVE: no floating-point operand")
        tcat = self.resolve(target).category
        if tcat not in ("NUMERIC", "NUMERIC-EDITED"):
            raise Untranslatable(f"MOVE {sf.name} {sf.usage} to a {tcat.lower()} item ({FLOAT_BYTES})")
        lt = self.lift(target)
        if lt:
            return self.violate(lt[2])  # a typed target takes no rounded float: it stays byte storage
        ft = self.field_expr(target)
        with self.reading():
            return f"Cobol.move({self.value_field(src)}, {ft}, CS);"

    def _move(self, src, target: E.Ref) -> str:
        ft = self.field_expr(target)
        with self.reading():
            return self._move_from(src, ft, target)

    def _move_from(self, src, ft: str, target: E.Ref) -> str:
        if isinstance(src, E.Ref):
            return f"Cobol.move({self.field_expr(src)}, {ft}, CS);"
        if isinstance(src, E.Lit):
            if isinstance(src.value, Decimal):
                return f"Cobol.move({self.const(self.literal_moved(src.value, target))}, {ft}, CS);"
            return f"Cobol.move({self.text(src)}, {ft}, CS);"
        if isinstance(src, E.Fig):
            if src.kind == "ALL":
                return f"Cobol.moveAll({jstr(src.all_literal or '')}, {ft}, CS);"
            return f"Cobol.moveFigurative(Figurative.{self.fig(src.kind)}, {ft}, CS);"
        if isinstance(src, E.Func):
            if self.is_numeric(src):
                return f"Cobol.move({self.num(src)}, {ft}, CS);"
            return f"Cobol.move({self.text(src)}, {ft}, CS);"
        if isinstance(src, E.LengthOf):
            return f"Cobol.move({self.num(src)}, {ft}, CS);"
        raise Untranslatable(f"MOVE from {type(src).__name__}")

    def initialize(self, ref: E.Ref) -> list[str]:
        """INITIALIZE: every elementary item of the group (not FILLER, not under a REDEFINES) to spaces or zero."""
        lo = self.lift(ref)
        if lo:
            return [self.move(E.Fig("SPACES" if lo[0] == "X" else "ZEROS"), ref)]
        it = self.resolve(ref)
        self._init_bytes += 1  # walked to its elementary items below: a float among them is set to zero
        try:
            base = self.value_field(ref)
        finally:
            self._init_bytes -= 1
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
            if x.usage == "POINTER":  # INITIALIZE sets a pointer NULL (GnuCOBOL, measured; oracle_assumptions.md C9):
                # all zero bytes. A port's pointer only ever holds NULL (an address is not modelled), so this is also
                # "unchanged"; a write-only pointer is skipped as before
                if x.name.upper() not in self.write_only_pointers:
                    rel = x.offset - it.offset
                    out.append(f"Cobol.moveFigurative(Figurative.LOW_VALUES, Field.group({base}.storage(), "
                               f"{base}.offset() + {rel}, {x.size}), CS);")  # fmt: skip
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
        fig = "ZEROS" if x.category in ("NUMERIC", "NUMERIC-EDITED", "FLOAT") else "SPACES"
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
        if cat == "FLOAT":  # #4271: IBM hexadecimal floating point, 4 (COMP-1) or 8 (COMP-2) bytes
            return f"Field.hfp({storage}, {offset}, {_b(it.usage == 'COMP-2')})"
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
        ends = [e for e in p.sentence_ends if e > 0] + [len(p.body)]
        if not any(s.kind == "NEXT-SENTENCE" for s in S.walk(p.body)):
            out, start = [], 0
            for end in ends:  # a period resets cobc's arithmetic state (cb_end_statement, #4287)
                self.leak = None
                out += self.block(p.body[start:end], ind)
                start = max(start, end)
            self.leak = None
            return out
        out, start = [], 0
        for k, end in enumerate(ends):
            if end <= start:
                continue
            self.sentence = f"sentence{k}"
            self.leak = None
            out += [f"{ind}{self.sentence}: {{", *self.block(p.body[start:end], ind + "    "), f"{ind}}}"]
            start = end
        self.sentence = None
        self.leak = None
        return out

    def block(self, stmts: list, ind: str) -> list[str]:
        out = []
        for s in stmts:
            out += self.statement(s, ind)
        return out

    def statement(self, s: S.Stmt, ind: str) -> list[str]:
        self.stats["statements"] += 1
        outer, self.touched = self.touched, {}
        try:
            code = self.after_statement(s, self._statement(s, ind), ind)
            self.stats["translated"] += 1
            return code
        except Untranslatable as e:
            why = f"line {s.line}: {s.kind} {e}"
            self.stats["holes"].append(why)
            return [f"{ind}// {_comment(s.text)}", f"{ind}if (true) throw new Hole({jstr(why)});"]
        finally:
            self.touched = outer

    def _statement(self, s: S.Stmt, ind: str) -> list[str]:
        k = s.kind
        c = f"{ind}// {_comment(s.text)}"
        if k == "HOLE":
            raise Untranslatable(s.data.get("why", "not parsed"))
        if _holds_wide(s):  # #4272: never translated with the stand-in byte (source.narrowed)
            raise Untranslatable(WIDE_WHY)
        if self.sets_sort_return(s):
            # IBM (SORT-RETURN special register): moving 16 to it in an input / output procedure ends the sort at
            # the next RELEASE or RETURN; GnuCOBOL's behaviour is not measured
            raise Untranslatable("SORT-RETURN set by the program (ends a sort early): not modelled")
        if k in ("SORT", "MERGE"):
            return [c, *self.sort(s, ind)]
        if k in ("RELEASE", "RETURN"):
            return [c, *self.release_return(s, ind)]
        if k == "MOVE":
            return [c] + [ind + self.move(s.data["from"], t) for t in s.data["to"]]
        if k == "IF":
            out = [c, f"{ind}if ({self.cond_top(s.data['cond'])}) {{", *self.block(s.body, ind + "    ")]
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
        if k == "ENTRY":  # #4462 (stmt._entry): the program's first statement is its entry, else not modelled
            if s.data.get("first"):
                return [c]
            raise Untranslatable(f"ENTRY {s.data['name']}: an alternate entry point is not modelled")
        if k in ("EXIT", "CONTINUE"):
            what = s.data.get("what") or []
            if k == "EXIT" and what[:1] == ["PROGRAM"]:
                return [c, f"{ind}if (true) throw new Goback();"]
            if k == "EXIT" and what[:1] == ["PARAGRAPH"]:
                return [c, f"{ind}if (true) return{'' if self.structured else ' ' + str(self.cur + 1)};"]
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
        if k == "SEARCH":
            return [c, *self.search(s, ind)]
        if k == "EXHIBIT":  # #4462 (stmt._exhibit): EXHIBIT NAMED, one DISPLAY line of `name = value` / literal
            parts: list[str] = []
            for written, o in s.data["operands"]:
                if parts:
                    parts.append(jstr(" "))
                if isinstance(o, E.Ref) and not o.qualifiers and not o.subscripts and o.refmod is None:
                    parts += [jstr(f"{written} = "), self.display_operand(o)]
                elif isinstance(o, E.Lit) and isinstance(o.value, str):
                    parts.append(self.display_operand(o))
                else:  # a qualified / subscripted name: IBM shows it as written, GnuCOBOL respells it ("A in R")
                    raise Untranslatable(f"EXHIBIT NAMED of {written}: only plain names and nonnumeric literals")
            return [c, f"{ind}Sysout.display({', '.join(parts)});"]
        if k == "COMPUTE":
            mode = self.float_mode([s.data["expr"]], [t for t, _ in s.data["targets"]])
            if mode is not None:
                self.float_statement(s, s.data["targets"])
            plan = self.plan_arith(s.data["expr"], [t for t, _ in s.data["targets"]])
            plan = {} if mode is not None else plan
            with self.floating(mode), self.osvs_plan(plan):
                value = self.num(s.data["expr"])
            return [c, *self.store_all(s, s.data["targets"], value, ind, s.data["expr"] if mode is None else None)]
        if k == "ARITH":
            d = s.data
            receivers = [t for t, _ in d.get("targets") or []] + [t for t, _ in d.get("giving") or []]
            receivers += [d["remainder"]] if d.get("remainder") is not None else []
            mode = self.float_mode(d["operands"], receivers, d["op"] in ("*", "*="))
            if mode is not None:
                self.float_statement(s, list(d.get("targets") or []) + list(d.get("giving") or []))
                if d.get("remainder") is not None:
                    raise Untranslatable(f"DIVIDE REMAINDER in floating point ({FLOAT_BYTES})")
                with self.floating(mode):
                    return [c, *self.arith_float(s, ind)]
            return [c, *self.arith(s, ind)]
        if k == "SET-POINTER":
            if s.data["target"] not in self.write_only_pointers:
                raise Untranslatable("SET ADDRESS OF (pointers)")
            return [c, f"{ind}// the pointer is never read (write_only_pointers): no effect any output can show"]
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
                if cn.parent is not None and id(cn.parent) in self.lifted and not r.subscripts:
                    out.append(ind + self.move(self.value_node(v), E.Ref(cn.parent.name)))
                    continue
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
            if len(words) > 1 and words[1].upper() == "SQL" and self.sql is not None:
                try:  # (the translator's own error class, by its instance: no import of det.sql here)
                    return [c, *self.sql.command(s.text, s.line, ind)]
                except (self.sql.Error, E.ExprError, KeyError) as e:
                    raise Untranslatable(f"EXEC SQL: {e}") from e
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
            return f"Cobol.moveFigurative(Figurative.{self.fig(v[1])}, {f}, CS);"
        if kind == "hex":
            return f"Cobol.move({jstr(v[1].decode('latin-1'))}, {f}, CS);"
        raise Untranslatable(f"value {kind}")

    @_reads
    # ---- SEARCH / SEARCH ALL (#4462) --------------------------------------------------------------------------
    def search(self, s: S.Stmt, ind: str) -> list[str]:
        """SEARCH table [VARYING index] [AT END ...] WHEN c ... and SEARCH ALL table [AT END ...] WHEN keys ...: the
        table's first INDEXED BY index (or the VARYING one of its own) walks it (IBM Enterprise COBOL 6.4 Language Reference, SEARCH statement;
        GnuCOBOL's code, the harness's oracle, the same loops). The table's size is its OCCURS, or the DEPENDING ON
        item's value."""
        d = s.data
        if d.get("error") or d["table"] is None:
            raise Untranslatable(f"SEARCH: {d.get('error')}")
        table = self.resolve(d["table"])
        if not (table.occurs > 1 or table.depending):
            raise Untranslatable(f"SEARCH {table.name}: no OCCURS")
        if not table.indexed_by:
            raise Untranslatable(f"SEARCH {table.name}: no INDEXED BY")
        if not s.whens:
            raise Untranslatable("SEARCH with no WHEN")
        dep = table.depending
        size = self.int_expr(E.Parser(E.tokenize(dep)).ref()) if dep else str(table.occurs)
        idx = E.Ref(table.indexed_by[0])
        varying = d.get("varying")
        if varying is not None and varying.name in table.indexed_by:
            idx, varying = varying, None  # VARYING one of the table's own indexes: it walks the table
        elif varying is not None:  # IBM steps it with the index; GnuCOBOL (the oracle) sets it to the index's value
            raise Untranslatable(f"SEARCH VARYING {varying.name}: IBM and GnuCOBOL step it differently")
        fi = self.field_expr(idx)
        loop = self.tmpname("search")
        at_end = self.block(s.phrases.get("AT-END", []), ind + "        ")
        if d["all"]:
            return self.search_all(s, table, idx, fi, size, loop, at_end, ind)
        out = [f"{ind}{loop}: while (true) {{",
               f"{ind}    if ({self.int_expr(idx)} > {size}) {{", *at_end, f"{ind}        break {loop};",
               f"{ind}    }}"]  # fmt: skip
        for i, (cond, body) in enumerate(s.whens):
            out += [f"{ind}    {'} else ' if i else ''}if ({self.cond_top(cond)}) {{", *self.block(body, ind + "        "),
                    f"{ind}        break {loop};"]  # fmt: skip
        out.append(f"{ind}    }}")
        out.append(f"{ind}    Cobol.store({fi}, Cobol.num({fi}, CS).add(BigDecimal.ONE), false, CS);")
        return [*out, f"{ind}}}"]

    def search_all(self, s: S.Stmt, table: L.Item, idx: E.Ref, fi: str, size: str, loop: str, at_end: list[str],
                   ind: str) -> list[str]:  # fmt: skip
        """SEARCH ALL: a binary search of the occurrences 1..size. Its WHEN is `key = value` (or a key's
        condition-name) for the leading keys of the table's KEY phrase, each key subscripted by the index, joined by
        AND -- anything else is refused. Each step sets the index to (head + tail) / 2; the WHEN true runs its body;
        else the first key, in KEY order, not equal to its value moves head up (an ASCENDING key below its value, a
        DESCENDING one above) or tail down. head >= tail - 1: AT END. A table out of key order, or keys equal in
        several occurrences, leave IBM's result undefined; this is GnuCOBOL's walk."""
        cond, body = s.whens[0]
        keys = {name: asc for asc, name in table.keys}
        if not keys:
            raise Untranslatable(f"SEARCH ALL {table.name}: no ASCENDING / DESCENDING KEY")
        terms: list = []

        def conj(c):
            if isinstance(c, E.And):
                conj(c.left)
                conj(c.right)
            else:
                terms.append(c)

        conj(cond)
        named: dict[str, tuple[E.Ref, object]] = {}
        for t in terms:
            key = value = None
            if isinstance(t, E.Rel) and t.op == "=":
                for a, b in ((t.left, t.right), (t.right, t.left)):
                    if isinstance(a, E.Ref) and a.name in keys:
                        key, value = a, b
                        break
            elif isinstance(t, E.CondName) and t.abbrev is None:
                cn = self.resolve_cond(t.ref)
                if cn is not None and cn.parent is not None and cn.parent.name in keys and len(cn.values) == 1 \
                        and cn.values[0][0] != "range":  # fmt: skip
                    key, value = E.Ref(cn.parent.name, list(t.ref.qualifiers), list(t.ref.subscripts)), \
                        self.value_node(cn.values[0])  # fmt: skip
            if key is None or not key.subscripts or key.subscripts[-1] != idx or key.refmod is not None:
                raise Untranslatable(f"SEARCH ALL {table.name}: WHEN must be KEY = value AND ... (on {idx.name})")
            if key.name in named:
                raise Untranslatable(f"SEARCH ALL {table.name}: key {key.name} named twice")
            named[key.name] = (key, value)
        order = [name for _, name in table.keys]
        if set(named) != set(order[: len(named)]):
            raise Untranslatable(f"SEARCH ALL {table.name}: WHEN names keys {sorted(named)}, not the leading keys")
        head, tail, mid = self.tmpname("head"), self.tmpname("tail"), self.tmpname("mid")
        out = [f"{ind}int {head} = 0, {tail} = {size} + 1;",
               f"{ind}{loop}: while (true) {{",
               f"{ind}    if ({head} >= {tail} - 1) {{", *at_end, f"{ind}        break {loop};", f"{ind}    }}",
               f"{ind}    int {mid} = ({head} + {tail}) / 2;",
               f"{ind}    Cobol.store({fi}, BigDecimal.valueOf({mid}), false, CS);",
               f"{ind}    if ({self.cond(cond)}) {{", *self.block(body, ind + "        "),
               f"{ind}        break {loop};", f"{ind}    }}"]  # fmt: skip
        for i, name in enumerate(order[: len(named)]):
            key, value = named[name]
            low = self.rel("<" if keys[name] else ">", key, value)
            out += [f"{ind}    {'} else ' if i else ''}if (!({self.rel('=', key, value)})) {{",
                    f"{ind}        if ({low}) {head} = {mid}; else {tail} = {mid};"]  # fmt: skip
        # (every key equal and the WHEN false cannot be: the WHEN is those equalities)
        out += [f"{ind}    }} else {{", f"{ind}        break {loop};", f"{ind}    }}", f"{ind}}}"]
        return [f"{ind}{{", *[("    " + x) for x in out], f"{ind}}}"]

    def display_operand(self, o) -> str:
        lo = self.lift(o)
        if lo and lo[0] == "X":
            return lo[1]
        if isinstance(o, E.Ref):
            if self.float_item(o) is not None:  # IBM: as external floating point -.9(8)E-99 / -.9(17)E-99
                return f"Cobol.displayText({self.value_field(o)}, CS)"
            return f"Cobol.displayText({self.field_expr(o)}, CS)"
        if isinstance(o, E.Lit):
            if isinstance(o.value, Decimal):
                return jstr(str(o.value))
            return self.text(o)
        if isinstance(o, E.Fig):
            ch = self.fig_char(o.kind)
            if ch is None:
                raise Untranslatable("DISPLAY ALL")
            return jstr(ch)
        if isinstance(o, E.Func):
            if self.is_numeric(o):  # #4557: no runtime formatter; GnuCOBOL shows each result in its own picture
                raise Untranslatable(f"DISPLAY of numeric FUNCTION {o.name}: its display picture is not modelled")
            return self.text(o)
        raise Untranslatable(f"DISPLAY of {type(o).__name__}")

    def float_statement(self, s: S.Stmt, targets: list) -> None:
        """What a floating-point statement does not model: ON SIZE ERROR (HFP exponent overflow and underflow are
        refused by name in the runtime) and ROUNDED into a float (its precision is the rounding)."""
        if "SIZE-ERROR" in s.phrases or "NOT-SIZE-ERROR" in s.phrases:
            raise Untranslatable(f"ON SIZE ERROR in a floating-point statement ({FLOAT_BYTES})")
        for t, rounded in targets:
            if rounded and self.float_item(t) is not None:
                raise Untranslatable(f"ROUNDED into {t.name}, a floating-point item ({FLOAT_BYTES})")

    def arith_float(self, s: S.Stmt, ind: str) -> list[str]:
        """ADD / SUBTRACT / MULTIPLY / DIVIDE in floating point (self.fmode): as arith, each operation HFP's."""
        d = s.data
        if d.get("giving") is not None or len(d["operands"]) > 1:
            self.leak = None  # cobc's build_decimal_assign (#4287)
        op, ops = d["op"], d["operands"]
        lng = _b(self.fmode == "LONG")
        if d.get("giving") is not None:
            if op in ("+", "-"):
                val = self.fnum(ops[0])
                for o in ops[1:]:
                    val = f"Hfp.{'add' if op == '+' else 'subtract'}({val}, {self.fnum(o)}, {lng})"
            else:
                fn = "multiply" if op == "*" else "divide"
                val = f"Hfp.{fn}({self.fnum(ops[0])}, {self.fnum(ops[1])}, {lng})"
            return self.store_all(s, d["giving"], val, ind)
        total = self.fnum(ops[0]) if ops else "BigDecimal.ZERO"
        for o in ops[1:]:
            total = f"Hfp.add({total}, {self.fnum(o)}, {lng})"
        tsum = self.tmpname("t")
        out = [f"{ind}BigDecimal {tsum} = {total};"]
        for tgt, rounded in d["targets"]:
            if not isinstance(tgt, E.Ref):
                raise Untranslatable("arithmetic target is not a data item")
            cur = self.fnum(tgt)
            val = {"+=": f"Hfp.add({cur}, {tsum}, {lng})", "-=": f"Hfp.subtract({cur}, {tsum}, {lng})",
                   "*=": f"Hfp.multiply({tsum}, {cur}, {lng})", "/=": f"Hfp.divide({cur}, {tsum}, {lng})"}[op]  # fmt: skip
            out.append(ind + self.store_into(tgt, val, rounded))
        return out

    def store_all(self, s: S.Stmt, targets: list, value: str, ind: str, expr=None, after=None) -> list[str]:
        """The value of a decimal expression `expr` (None: a floating-point value) stored in each target, then
        `after(v)`'s lines, then the SIZE ERROR phrases. libcob's NaN (a zero divisor, #4655) changes no target: a
        lifted one is guarded; one with a division or an exponent also raises the statement's size error, which a
        statement with ON SIZE ERROR clears first and reads after (the receivers may still change: an aligned NaN
        is 0, 0 ** 0 is 1)."""
        out = []
        checked = "SIZE-ERROR" in s.phrases or "NOT-SIZE-ERROR" in s.phrases
        if not checked:
            v = self.tmpname("v")
            out.append(f"{ind}BigDecimal {v} = {value};")
            nan = expr is not None and _may_nan(expr)
            for t, rounded in targets:
                guard = f"if (!Cobol.isNan({v})) " if nan and self.lift(t) else ""
                out.append(ind + guard + self.store_into(t, v, rounded))
            return out + (after(v) if after else [])
        v, err = self.tmpname("v"), self.tmpname("sizeError")
        sized = expr is not None and _raises_size(expr)
        if sized:
            out.append(f"{ind}Cobol.sizeClear();")
        out.append(f"{ind}BigDecimal {v} = {value};")
        out.append(f"{ind}boolean {err} = {'Cobol.sizeRaised()' if sized else 'false'};")
        for t, rounded in targets:
            out.append(f"{ind}{err} |= Cobol.storeChecked({self.field_expr(t)}, {v}, {_b(rounded)}, CS);")
        out += after(v) if after else []
        if "SIZE-ERROR" in s.phrases:
            out += [f"{ind}if ({err}) {{", *self.block(s.phrases["SIZE-ERROR"], ind + "    "), f"{ind}}}"]
        if "NOT-SIZE-ERROR" in s.phrases:
            out += [f"{ind}if (!{err}) {{", *self.block(s.phrases["NOT-SIZE-ERROR"], ind + "    "), f"{ind}}}"]
        return out

    def store_into(self, t: E.Ref, value: str, rounded: bool) -> str:
        """An arithmetic result (no ON SIZE ERROR) stored in a target: a lifted binary item through Cobol.binary."""
        lt = self.lift(t)
        if lt and lt[0] == "BIN":
            it = lt[2]
            comp5 = ", true" if it.usage == "COMP-5" else ""  # no TRUNC truncates a COMP-5 item (#4684)
            return f"{lt[1]} = Cobol.binary({value}, {it.digits}, {_b(it.signed)}, {_b(rounded)}{comp5}, CS);"
        if lt and lt[0] == "NUM":
            it = lt[2]
            fn = "packed" if it.usage == "PACKED" else "zoned"
            return f"{lt[1]} = Cobol.{fn}({value}, {it.digits}, {it.scale}, {_b(it.signed)}, {_b(rounded)}, CS);"
        return f"Cobol.store({self.value_field(t)}, {value}, {_b(rounded)}, CS);"

    def arith(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        op = d["op"]
        ops = d["operands"]
        if d.get("giving") is not None:
            # cobc: one expression, as COMPUTE (cb_build_binary_list): ((A + B) + C), ((C - A) - B), A * B, A / B
            expr = ops[0]
            for o in ops[1:] if op in ("+", "-") else ops[1:2]:
                expr = E.Bin(op, expr, o)
            plan = {} if d.get("remainder") is not None else self.plan_arith(expr, [t for t, _ in d["giving"]])
            with self.osvs_plan(plan):
                val = self.num(expr)
            after = None
            if d.get("remainder") is not None:
                # cob_div_remainder: from the quotient truncated to the first receiver's places (not its PICTURE's
                # high-order digits); a zero divisor leaves the remainder unchanged (#4655)
                q = self.resolve(d["giving"][0][0])

                def after(v, q=q):
                    rem = f"Cobol.remainder({self.num(ops[0])}, {v}, {self.num(ops[1])}, {q.scale})"
                    return [f"{ind}Cobol.store({self.field_expr(d['remainder'])}, {rem}, false, CS);"]

            return self.store_all(s, d["giving"], val, ind, expr, after)
        if len(ops) > 1:
            # cobc: the operands' sum is one expression, aligned when the first receiver is loaded (#4287)
            expr = ops[0]
            for o in ops[1:]:
                expr = E.Bin("+", expr, o)
            with self.osvs_plan(self.plan_arith(expr, [t for t, _ in d["targets"]], operands_first=True)):
                total = self.num(expr)
        else:
            total = self.num(ops[0]) if ops else "BigDecimal.ZERO"
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
            lt = self.lift(tgt)
            if self.native_add(s, op, ops, tgt, rounded):  # cobc's native integer ADD / SUBTRACT (#4684)
                it = self.resolve(tgt)
                sign = "add" if op == "+=" else "subtract"
                if lt and lt[0] == "BIN":
                    val = f"BigDecimal.valueOf({lt[1]}).{sign}({tsum})"
                    out.append(f"{ind}{lt[1]} = Cobol.binaryNative({val}, {it.digits}, false, "
                               f"{_b(it.usage == 'COMP-5')}, CS);")  # fmt: skip
                else:
                    f = self.field_expr(tgt)
                    out.append(f"{ind}Cobol.storeNative({f}, Cobol.num({f}, CS).{sign}({tsum}), CS);")
                continue
            if lt and lt[0] in ("BIN", "NUM") and not checked:  # a lifted target: its value, the store as above
                cur = f"BigDecimal.valueOf({lt[1]})" if lt[0] == "BIN" else lt[1]
                if op == "/=":  # a zero divisor: libcob's NaN, the target unchanged (#4655)
                    qv = self.tmpname("q")
                    out.append(f"{ind}BigDecimal {qv} = Cobol.divide({cur}, {tsum});")
                    out.append(f"{ind}if (!Cobol.isNan({qv})) {self.store_into(tgt, qv, rounded)}")
                    continue
                val = {"+=": f"{cur}.add({tsum})", "-=": f"{cur}.subtract({tsum})",
                       "*=": f"{tsum}.multiply({cur})"}[op]  # fmt: skip
                out.append(ind + self.store_into(tgt, val, rounded))
                continue
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

    def native_add(self, s: S.Stmt, op: str, ops: list, tgt: E.Ref, rounded: bool) -> bool:
        """Whether cobc 3.1.2 compiles this ADD / SUBTRACT ... TO / FROM target to native integer arithmetic
        (cb_build_add / cb_build_sub -> cb_build_optim_add / _sub, #4684): no ROUNDED and no store option -- no ON
        SIZE ERROR (for COMP-5 a NOT ON SIZE ERROR alone keeps it native: build_store_option checks only the ON
        phrase), no NOT ON SIZE ERROR for COMP / COMP-4 / BINARY (TRUNC(STD) adds one at run time:
        Cobol.storeNative checks it) --, an unsigned binary target of no decimal places, and one operand that fits a C
        int (cb_fits_int; cobc folds a list of literals into one). Only an unsigned target can differ: a signed one
        wraps the same way through libcob's decimal store. ON SIZE ERROR keeps cobc's decimal store."""
        if op not in ("+=", "-=") or rounded or "SIZE-ERROR" in s.phrases or tgt.refmod is not None:
            return False
        try:
            it = self.resolve(tgt)
        except Untranslatable:
            return False
        if it.category != "NUMERIC" or it.usage not in ("BINARY", "COMP-5") or it.signed or it.scale != 0:
            return False
        if "NOT-SIZE-ERROR" in s.phrases and it.usage != "COMP-5":
            return False
        if ops and all(isinstance(o, E.Lit) and isinstance(o.value, Decimal) for o in ops):
            return _fits_int_literal(sum((o.value for o in ops), Decimal(0)))
        return len(ops) == 1 and self.fits_int(ops[0])

    def fits_int(self, e) -> bool:
        """cobc's cb_fits_int: an integer literal within a C int, or an item of no decimal places whose values a C int
        holds by its layout (binary of at most 4 bytes, zoned of at most 9 bytes, packed of at most 9 digits)."""
        if isinstance(e, E.Lit):
            return isinstance(e.value, Decimal) and _fits_int_literal(e.value)
        if not isinstance(e, E.Ref) or e.refmod is not None:
            return False
        try:
            it = self.resolve(e)
        except Untranslatable:
            return False
        if it.children:
            return False
        if it.usage == "INDEX":
            return True
        if it.category != "NUMERIC" or it.scale > 0:
            return False
        if it.usage in ("BINARY", "COMP-5"):
            return it.size <= 4
        if it.usage == "DISPLAY":
            return it.size < 10
        if it.usage == "PACKED":
            return it.digits < 10
        return False

    def evaluate(self, s: S.Stmt, ind: str) -> list[str]:
        # ARITHMETIC-OSVS (#4287): cobc builds each WHEN's condition in turn at END-EVALUATE, the state carried over
        groups = []
        for conds, _ in s.whens:
            g: list = []
            for objs in conds or []:
                for subj, obj in zip(s.data["subjects"], objs, strict=False):
                    self.when_relations(subj, obj, g)
            groups.append(g)
        plans = self.plan_relations(groups, evaluate=True)
        leak_out = self.leak
        with self.relations_planned(plans):
            out = self.evaluate_planned(s, ind)
        if self.leak is not None and any(plans):
            # cobc builds the WHEN conditions after the last WHEN's statements, from the state they leave
            raise Untranslatable("ARITHMETIC-OSVS: an EVALUATE whose last WHEN leaves cobc's arithmetic state to its "
                                 "conditions (#4287)")  # fmt: skip
        self.leak = leak_out
        return out

    def when_relations(self, subject, obj, out: list) -> None:
        """The relations of one WHEN test in the order when_test generates them (cobc's evaluate_test)."""
        kind = obj[0]
        if kind in ("ANY", "UNPARSED") or (isinstance(subject, tuple) and subject[0] == "UNPARSED"):
            return
        if subject in ("TRUE", "FALSE"):
            if kind == "COND":
                self.cond_relations(obj[1], out)
            return
        if kind == "VALUE":
            out.append(self._relation(subject, obj[1], True))
        elif kind == "RANGE":  # cobc: low <= subject AND subject <= high
            out += [self._relation(obj[1], subject), self._relation(subject, obj[2])]

    def evaluate_planned(self, s: S.Stmt, ind: str) -> list[str]:
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
            if conds is not None:  # cb_end_cond after the WHEN's objects: its statements start clean
                self.leak = None
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
            with self.relation():
                t = self.rel("=", subject, obj[1])
            return f"!({t})" if obj[3] else t
        if kind == "RANGE":
            with self.relation():
                lo = self.rel(">=", subject, obj[1])
            with self.relation():
                hi = self.rel("<=", subject, obj[2])
            t = f"({lo} && {hi})"
            return f"!{t}" if obj[3] else t
        if kind == "COND":
            raise Untranslatable("a condition as WHEN object of a value subject")
        raise Untranslatable(f"WHEN {kind}")

    def perform(self, s: S.Stmt, ind: str) -> list[str]:
        d = s.data
        # cobc builds an UNTIL condition before the inline statements (#4287): it sees the state before them, and
        # they start from the clean one it leaves
        leak_before = self.leak
        if d["until"] is not None or d["varying"] is not None:
            self.leak = None
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
                body = self.perform_call(sec[0], sec[-1], ind + "    ")
            else:
                body = self.perform_call(self.para_index[t], self.para_index[thru], ind + "    ")
        if d["times"] is not None:
            i = self.tmpname("i")
            return [
                f"{ind}for (int {i} = 0, n_{i} = {self.int_expr(d['times'])}; {i} < n_{i}; {i}++) {{",
                *body,
                f"{ind}}}",
            ]
        leak_after = self.leak
        if d["until"] is not None:
            self.leak = leak_before
            cond = self.cond_top(d["until"])
            self.leak = leak_after
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
            self.leak = leak_before
            until_code = self.cond_top(until)
            self.leak = leak_after
            return [f"{ind}{init}", f"{ind}while (!({until_code})) {{", *body, f"{ind}    {step}", f"{ind}}}"]
        self.leak = leak_after
        if d["inline"]:
            return [f"{ind}{{", *body, f"{ind}}}"]
        return [x[4:] if x.startswith(ind + "    ") else x for x in body]

    def codec_for(self, cls: str) -> str:
        """The in_ / out_ / fill_ codec of contract DTO `cls` (det.cics.Cics.codec), made on first use."""
        if self.dto_codecs is None and self.dto_codecs_factory is not None:
            self.dto_codecs = self.dto_codecs_factory()
        if self.dto_codecs is None:
            raise Untranslatable(f"no generated project to carry {cls} across a CALL")
        try:
            return self.dto_codecs.codec(cls)
        except Exception as e:  # det.cics.CicsError: a DTO property the port cannot convert
            raise Untranslatable(f"{cls}: {e}") from e

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
            refs, out, back = [], [], []
            types = self.callee_types.get(prog, [])
            for k, (_, a) in enumerate(args):
                v = self.tmpname("arg")
                refs.append(v)
                f = self.field_expr(a)
                typ = types[k] if k < len(types) else "CobolRef<String>"
                if typ == "CobolRef<String>":
                    out.append(f"{ind}CobolRef<String> {v} = CobolRef.of(Cobol.text({f}, CS));")
                    back.append(f"{ind}Cobol.move({v}.get(), {f}, CS);")
                    continue
                # a group USING item the callee takes as its contract DTO: built from the item's bytes, and the
                # object the callee filled written back (BY REFERENCE) -- the codec a LINKed COMMAREA crosses with
                cls = self.codec_for(typ)
                out.append(f"{ind}{typ} {v} = out_{cls}({f}.storage(), {f}.offset());")
                back.append(f"{ind}in_{cls}({v}, {f}.storage(), {f}.offset());")
            rc = self.tmpname("rc")
            out.append(f"{ind}int {rc} = {callee}.getObject().handleCall({', '.join(refs)});")
            out += back
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
                a_field = isinstance(src, E.Ref)  # a data item is a Field; a literal / function, its text
                if delim is None:
                    parts.append(f"Cobol.StringPart.size({a})" if a_field else f"Cobol.StringPart.size({a}, CS)")
                else:
                    b = self.str_arg(delim)
                    tail = "" if a_field and isinstance(delim, E.Ref) else ", CS"
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
            delims.append(f"Cobol.Delim.of({a}, {_b(every)})" if isinstance(operand, E.Ref)
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
            ch = self.fig_char(e.kind)
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
                ch = str(self.fig_char(e.kind))
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
            if fd.varying is not None:
                raise Untranslatable(f"READ of the variable-length file {fd.select}")
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
            if fd.varying is not None:  # the record's length is the DEPENDING ON item's value when it is written
                if k == "REWRITE":
                    raise Untranslatable(f"REWRITE of the variable-length file {fd.select}")
                length = self.int_expr(E.Ref(fd.varying["depending"]))
                out.append(f"{ind}String {st} = {v}.write({length});")
            else:
                out.append(f"{ind}String {st} = {v}.{k.lower()}({rec_item.size});")
            out += self.status(fd, st, ind)
            out += self.io_phrases(s, st, ind, at_end=None, invalid=("21", "22", "23", "24"))
            return out
        if k == "START":
            raise Untranslatable("START")
        raise Untranslatable(k)

    # ---- SORT / MERGE / RELEASE / RETURN (IBM Enterprise COBOL for z/OS 6.4 Language Reference) ----------------
    def sets_sort_return(self, s: S.Stmt) -> bool:
        """Whether the statement stores into the SORT-RETURN special register."""
        if self.items.get("SORT-RETURN"):
            return False  # the program's own item of that name
        d, targets = s.data, []
        if s.kind == "MOVE":
            targets = d["to"]
        elif s.kind == "SET-TO":
            targets = d["targets"]
        elif s.kind == "INITIALIZE":
            targets = d["refs"]
        elif s.kind in ("COMPUTE", "ARITH"):
            targets = [t[0] if isinstance(t, tuple) else t for t in (d.get("targets") or []) + (d.get("giving") or [])]
        return any(isinstance(t, E.Ref) and t.name == "SORT-RETURN" for t in targets)

    def sort_file(self, name: str) -> FileDef:
        fd = next((f for f in self.p.files.values() if f.sort and name in (f.select, f.fd)), None)
        if fd is None:
            raise Untranslatable(f"{name}: no SD file")
        if fd.record is None or fd.sort_length is None:
            raise Untranslatable(f"{name}: an SD with no record, or records of different lengths")
        return fd

    def procedure_range(self, rng: tuple, ind: str) -> list[str]:
        """An INPUT / OUTPUT PROCEDURE: run as PERFORM name [THRU name] runs it (a section: its paragraphs)."""
        t, thru = rng
        if t not in self.para_index or (thru is not None and thru not in self.para_index):
            raise Untranslatable(f"PROCEDURE {t}{' THRU ' + thru if thru else ''}: no such paragraph")
        if thru is None and self.p.proc.paragraphs[self.para_index[t]].section == t:
            sec = [i for i, p in enumerate(self.p.proc.paragraphs) if p.section == t]
            return self.perform_call(sec[0], sec[-1], ind)
        return self.perform_call(self.para_index[t], self.para_index[thru or t], ind)

    def sort(self, s: S.Stmt, ind: str) -> list[str]:
        """SORT / MERGE: a Sort over the SD's records, filled from the USING files or the INPUT PROCEDURE's RELEASEs,
        ordered, then emptied into the GIVING files or by the OUTPUT PROCEDURE's RETURNs; SORT-RETURN 0."""
        d, verb = s.data, s.kind
        sd = self.sort_file(d["file"])
        var = f"sort_{jname(sd.select)}"
        coll = self.collating(verb, d["collating"] or self.program_collating)
        keys = []
        for ref, asc in d["keys"]:
            it = self.resolve(ref)
            top = it
            while top.parent is not None:
                top = top.parent
            if it.section != "FILE" or top.fd != sd.fd:
                raise Untranslatable(f"{verb} KEY {ref.name}: not in a record of {sd.fd}")
            if _occurs_chain(it) or it.depending:
                raise Untranslatable(f"{verb} KEY {ref.name}: under an OCCURS")
            if coll and it.category != "NUMERIC" and not _text_item(it):
                # the alphabet orders characters: a packed, binary or zoned byte is no character of the data's
                # code page (on z/OS its byte is the same in ASCII and EBCDIC; a character's is not)
                raise Untranslatable(f"{verb} KEY {ref.name}: holds numeric or national items, under COLLATING "
                                     f"SEQUENCE {d['collating'] or self.program_collating}: not modelled")  # fmt: skip
            keys.append(f"new Sort.Key(r -> {self.factory(it, 'r', str(it.offset))}, {_b(asc)})")
        out = [
            f"{ind}{var} = new Sort({jstr(sd.fd or sd.select)}, {sd.sort_length}, {_b(d['duplicates'])}, CS,"
            + (f" {coll}," if coll else "")
        ]
        out += [f"{ind}        {k}{',' if n < len(keys) - 1 else ');'}" for n, k in enumerate(keys)]
        if d["input"] is not None:
            out += self.procedure_range(d["input"], ind)
        for n, name in enumerate(d["using"]):
            if n and verb == "MERGE":
                out.append(f"{ind}{var}.nextInput();")
            out += self.using_file(verb, var, sd, name, ind)
        out.append(f"{ind}{var}.{'sort' if verb == 'SORT' else 'merge'}();")
        if d["output"] is not None:
            out += self.procedure_range(d["output"], ind)
        for name in d["giving"]:
            out += self.giving_file(verb, var, sd, name, ind)
        out.append(f"{ind}{var} = null;")
        out.append(f"{ind}Cobol.store({self.field_expr(E.Ref('SORT-RETURN'))}, BigDecimal.ZERO, false, CS);")
        return out

    def collating(self, verb: str, name: str | None) -> str | None:
        """The SORT / MERGE's COLLATING SEQUENCE (or PROGRAM COLLATING SEQUENCE) alphabet as a Sort.Collating, or None
        for the data's byte order: NATIVE (register D1), STANDARD-1 / STANDARD-2 (ASCII / ISO 646, which the
        harness's ISO-8859-1 data is in byte order). EBCDIC and a literal alphabet (literals, THRU, ALSO, SPACE /
        ZERO / QUOTE) are modelled; an ordinal (a numeric literal names a code of the native set: EBCDIC on z/OS),
        HIGH-VALUE / LOW-VALUE and anything else are refused by name."""
        if name is None:
            return None
        defn = self.alphabets.get(name) or []
        kind = defn[0] if defn else "no ALPHABET"
        what = f"{verb} COLLATING SEQUENCE {name}"
        if kind in ("NATIVE", "STANDARD-1", "STANDARD-2"):
            return None
        if kind == "EBCDIC":
            return f"Sort.Collating.ebcdic({jstr(name)}, CS)"
        if not (kind[0] in "'\"" or kind in ("SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "QUOTE", "QUOTES")):
            raise Untranslatable(f"{what} ({kind}): not modelled")
        figurative = {"SPACE": " ", "SPACES": " ", "ZERO": "0", "ZEROS": "0", "ZEROES": "0", "QUOTE": '"',
                      "QUOTES": '"'}  # fmt: skip

        def chars(t: str) -> str:
            if t[0] in "'\"":
                return t[1:-1].replace(t[0] * 2, t[0])
            if t in figurative:
                return figurative[t]
            raise Untranslatable(f"{what}: {t} in the alphabet (an ordinal names a code of the native set, EBCDIC on "
                                 f"z/OS; HIGH-VALUE / LOW-VALUE): not modelled")  # fmt: skip

        entries, i = [], 0
        while i < len(defn):
            first = chars(defn[i])
            if not first:
                raise Untranslatable(f"{what}: an empty literal")
            i += 1
            if i < len(defn) and defn[i] in ("THRU", "THROUGH"):
                last = chars(defn[i + 1]) if i + 1 < len(defn) else ""
                if len(first) != 1 or len(last) != 1:
                    raise Untranslatable(f"{what}: THRU between literals of one character only")
                entries.append("T" + first + last)
                i += 2
                continue
            group = first
            while i < len(defn) and defn[i] == "ALSO":
                also = chars(defn[i + 1]) if i + 1 < len(defn) else ""
                if len(first) != 1 or len(also) != 1:
                    raise Untranslatable(f"{what}: ALSO between literals of one character only")
                group += also
                i += 2
            entries += ["A" + group] if len(group) == 1 or len(first) == 1 else ["A" + c for c in group]
        if not entries:
            raise Untranslatable(f"{what}: an empty alphabet")
        return f"Sort.Collating.alphabet({jstr(name)}, CS, {', '.join(jstr(e) for e in entries)})"

    def _sort_io_file(self, verb: str, sd: FileDef, name: str) -> tuple[FileDef, L.Item]:
        """A USING / GIVING file and its record (checked present, so callers get it as a non-optional Item)."""
        fd = self.p.files.get(name)
        if fd is None or fd.sort:
            raise Untranslatable(f"{verb} USING / GIVING {name}: no such file")
        if fd.handle is None:
            raise Untranslatable(f"{name}: {fd.why}")
        if fd.varying is not None or fd.record is None or fd.record.size != sd.sort_length:
            raise Untranslatable(f"{verb} USING / GIVING {name}: records not the sort file's length: not modelled")
        return fd, fd.record

    def using_file(self, verb: str, var: str, sd: FileDef, name: str, ind: str) -> list[str]:
        """USING: the file opened, every record read into the sort, closed. Its FILE STATUS item is left as it was:
        GnuCOBOL's implicit I/O does not set it (and IBM's depends on FASTSRT: register F4)."""
        fd, record = self._sort_io_file(verb, sd, name)
        v, rec, st, what = jname(fd.select), self.ids[id(record)], self.tmpname("st"), f"{verb} USING {name}"
        return [f'{ind}String {st} = {v}.open("INPUT");',
                f'{ind}Sort.expect({st}, {jstr(what + ": OPEN")}, "00");',
                f"{ind}while (true) {{", f"{ind}    {st} = {v}.readNext();",
                f'{ind}    if ({st}.equals("10")) {{', f"{ind}        break;", f"{ind}    }}",
                f'{ind}    Sort.expect({st}, {jstr(what + ": READ")}, "00");', f"{ind}    {var}.add({rec});", f"{ind}}}",
                f"{ind}{st} = {v}.close();",
                f'{ind}Sort.expect({st}, {jstr(what + ": CLOSE")}, "00");']  # fmt: skip

    def giving_file(self, verb: str, var: str, sd: FileDef, name: str, ind: str) -> list[str]:
        """GIVING: the file opened OUTPUT, every record in order written from its record area, closed (its FILE
        STATUS left as it was, as USING)."""
        fd, record = self._sort_io_file(verb, sd, name)
        v, rec, st, what = jname(fd.select), self.ids[id(record)], self.tmpname("st"), f"{verb} GIVING {name}"
        r = self.tmpname("r")
        return [f"{ind}{var}.rewind();", f'{ind}String {st} = {v}.open("OUTPUT");',
                f'{ind}Sort.expect({st}, {jstr(what + ": OPEN")}, "00");',
                f"{ind}for (byte[] {r} = {var}.next(); {r} != null; {r} = {var}.next()) {{",
                f"{ind}    {rec}.putRaw({r});", f"{ind}    {st} = {v}.write({record.size});",
                f'{ind}    Sort.expect({st}, {jstr(what + ": WRITE")}, "00");',
                f"{ind}}}", f"{ind}{st} = {v}.close();",
                f'{ind}Sort.expect({st}, {jstr(what + ": CLOSE")}, "00");']  # fmt: skip

    def release_return(self, s: S.Stmt, ind: str) -> list[str]:
        """RELEASE record [FROM x]: (MOVE x TO record) the record into the active sort. RETURN file [INTO x]: the
        next record into the SD record area ([MOVE it TO x]); AT END when none is left."""
        if s.kind == "RELEASE":
            it = self.resolve(s.data["record"])
            sd = self.sort_file(it.fd or "")
            if it.size != sd.sort_length:
                raise Untranslatable(f"RELEASE {it.name}: not the sort file's record length")
            var = f"sort_{jname(sd.select)}"
            out = [ind + self.move(s.data["from"], s.data["record"])] if s.data["from"] is not None else []
            what = jstr(f"RELEASE {it.name} outside an input procedure")
            return [*out, f"{ind}Sort.active({var}, {what}).release({self.field_expr(s.data['record'])});"]
        sd = self.sort_file(s.data["file"])
        var, rec, st = f"sort_{jname(sd.select)}", self.ids[id(sd.record)], self.tmpname("st")
        what = jstr(f"RETURN {s.data['file']} outside an output procedure")
        out = [f'{ind}String {st} = Sort.active({var}, {what}).returnInto({rec}) ? "00" : "10";']
        if s.data["into"] is not None:
            out += [f'{ind}if ({st}.equals("00")) {{', f"{ind}    Cobol.move({rec}, {self.field_expr(s.data['into'])}, CS);",
                    f"{ind}}}"]  # fmt: skip
        return out + self.io_phrases(s, st, ind, at_end="10", invalid=())

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


JAVA_RESERVED = {"abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
                 "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float", "for",
                 "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native", "new",
                 "package", "private", "protected", "public", "return", "short", "static", "strictfp", "super",
                 "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile", "while",
                 "true", "false", "null", "var", "record", "yield"}  # fmt: skip
# the service's own members a paragraph method must not shadow
METHODS_TAKEN = {"initialState", "perform", "run", "runTask", "runBatch", "runProgram", "handleCall", "handleTransaction", "handleLink",
                 "store", "condition", "paragraph", "dd", "cx", "task", "files", "datasets", "clock", "handlers",
                 "stores", "heldKey", "caBack", "fields0", "fields1", "fields2", "fields3"}  # fmt: skip


FLOAT_BYTES = "IBM hexadecimal floating point on z/OS, IEEE on the oracle: oracle_assumptions.md C6"


def _extents(it: L.Item) -> tuple[tuple[int, int], tuple[int, int], list[int]]:
    """An item's bytes within its record: its first occurrence, the whole of its outermost table, and the ids of
    the OCCURS items it lies in."""
    first = (it.offset, it.offset + it.size * it.occurs)
    full, tables = first, []
    a: L.Item | None = it
    while a is not None:
        if a.occurs > 1:
            tables.append(id(a))
            full = (a.offset, a.offset + a.size * a.occurs)
        a = a.parent
    return first, full, tables


def camel(cobol: str) -> str:
    """ACCT-CURR-BAL -> acctCurrBal; 1000-CARDFILE-GET-NEXT -> 1000CardfileGetNext (callers prefix a digit)."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", cobol) if p]
    if not parts:
        return "x"
    return parts[0].lower() + "".join(p[:1].upper() + p[1:].lower() for p in parts[1:])


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


def _text_item(it: L.Item) -> bool:
    """Every elementary item of `it` (itself, or a group's) holds characters: alphanumeric, alphabetic or edited,
    USAGE DISPLAY, not national / DBCS."""
    if it.children:
        return all(_text_item(c) for c in it.children)
    return (it.usage == "DISPLAY" and not set(it.picture()) & set("NG")
            and it.category in ("ALPHANUMERIC", "ALPHABETIC", "NUMERIC-EDITED", "ALPHANUMERIC-EDITED"))  # fmt: skip


def _unsigned_zoned(it: L.Item) -> bool:
    """An unsigned zoned decimal item (USAGE DISPLAY): its bytes are digit characters, as an alphanumeric item's."""
    return not it.children and it.category == "NUMERIC" and it.usage == "DISPLAY" and "S" not in it.picture()


def _may_nan(e) -> bool:
    """An expression whose value can be libcob's NaN at run time (#4655): a division (a zero divisor), an exponent
    (no finite result), or an operation on one. A function's value never is (cob_intr_binop gives 0)."""
    if isinstance(e, E.Bin):
        return e.op in ("/", "**") or _may_nan(e.left) or _may_nan(e.right)
    if isinstance(e, E.Neg):
        return _may_nan(e.operand)
    return False


def _raises_size(e) -> bool:
    """An expression that can raise libcob's size error (#4655): a division or an exponent anywhere, a function's
    arguments included (FUNCTION MOD / REM by zero give 0 and raise nothing)."""
    if isinstance(e, E.Bin):
        return e.op in ("/", "**") or _raises_size(e.left) or _raises_size(e.right)
    if isinstance(e, E.Neg):
        return _raises_size(e.operand)
    if isinstance(e, E.Func):
        return any(_raises_size(a) for a in e.args if not isinstance(a, tuple))
    return False


def _fits_int_literal(v: Decimal) -> bool:
    """cb_fits_int of a numeric literal: no decimal places as written (3.0 has one), within a C int."""
    exponent = v.as_tuple().exponent
    return isinstance(exponent, int) and exponent >= 0 and -(2**31) <= v <= 2**31 - 1


def _b(v: bool) -> str:
    return "true" if v else "false"


def _camel(name: str) -> str:
    parts = name.lower().split("-")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _comment(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(WIDE, "?")).strip()[:150].replace("*/", "* /")


# #4272 (docs/language_status/oracle_assumptions.md D4): no single-byte code page holds the character, so the literal's
# bytes and length are what the source's transfer to the compiler made of it, not what COBOL says
WIDE_WHY = ("an alphanumeric literal holds a character beyond the single-byte code page (national / DBCS text in the "
            "source): its bytes and length depend on how the source reached the compiler")  # fmt: skip


def _holds_wide(s: S.Stmt) -> bool:
    """Whether the statement's own text or parts (not the statements nested in it: each is its own hole) hold a
    PROCEDURE DIVISION literal's wide character (source.WIDE). An EVALUATE's WHEN conditions are its own."""
    return _wide_in((s.text, s.data, [cond for cond, _ in s.whens]))


def _wide_in(x: Any) -> bool:
    if isinstance(x, str):
        return WIDE in x
    if isinstance(x, S.Stmt):  # a nested statement is translated (or refused) on its own
        return False
    if isinstance(x, dict):
        return any(_wide_in(k) or _wide_in(v) for k, v in x.items())
    if isinstance(x, (list, tuple, set, frozenset)):
        return any(_wide_in(v) for v in x)
    if hasattr(x, "__dataclass_fields__"):
        return any(_wide_in(getattr(x, f)) for f in x.__dataclass_fields__)
    return False
