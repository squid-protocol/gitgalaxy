"""ARITHMETIC-OSVS: where the oracle truncates an arithmetic intermediate, and to how many decimal places (#4287).

`cobc -std=ibm` turns on GnuCOBOL's `arithmetic-osvs` (config/ibm-strict.conf). cobc then decides at compile time,
for each operation of a COMPUTE, an ADD / SUBTRACT / MULTIPLY / DIVIDE with more than one operand, or a relation with
an arithmetic side, a number of decimal places, and emits `cob_decimal_align` on the operation's result before the
next operand is loaded. This module replays that decision exactly as GnuCOBOL 3.1.2 makes it (cobc/typeck.c:
build_decimal_assign, cb_build_cond, cb_walk_cond, decimal_expand, decimal_compute, decimal_align; cobc/tree.c:
cb_build_binary_op's constant folding), so the det translator emits `Cobol.align(value, places)` at the same points.

The decision, as cobc makes it:

- dmax, "the most decimal places of any operand or receiver": the receivers' scales and cb_walk_cond over the
  expression (every numeric literal and data item, except the divisor side of a division). For a condition the walk
  covers the whole condition and is made only when nothing set dmax before -- in an IF, a folded pair of literals
  sets it while the condition is parsed; in an EVALUATE only the first WHEN is walked and the others share its dmax.
- A stack of decimal places (expr_decp): an item pushes its scale, a literal of 19 digits or more or with decimals
  pushes its scale, a FUNCTION pushes 0. A binary item of scale 0, a short integer literal, ZERO and the right operand
  of an operation when it is a numeric literal push nothing -- so the stack does not always pair an operation with its
  own operands; cobc's choice stands as it is.
- Each operation pops one entry into the one below (+ - the larger, * the sum, / the difference or dmax, whichever is
  greater, ** the difference when the exponent's entry is positive); with fewer than two entries its places are dmax.
- The places are applied (cob_decimal_align) only when the next operand is loaded or another decimal is operated
  on: an operation followed by a literal on its right, and the last operation of an expression, are not aligned
  (the receiver's own store truncates or rounds that one).
- Conditions: `A AND B` builds B before A (gcc evaluates cb_build_binary_op's arguments right to left -- measured on
  the pinned oracle), so the relations of one condition are built in reverse order, and the stack and dmax carry
  from one relation to the next (and, in an EVALUATE, from one WHEN to the next).

The runtime's `Cobol.align` is libcob's cob_decimal_align, its shift included: an intermediate with fewer decimal
places than the target loses as many low-order digits (an integer 579 aligned to 2 places is 500).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from gitgalaxy.tools.cobol_to_java.det import expr as E

MAX_NESTED_EXPR = 42
PLANNED = "planned"  # a plan's marker: the expression is generated as cobc's decimal expansion (Cobol.Dc constants)  # cobc/typeck.c: pushes past it are dropped with a warning

# a plan: id(node) -> ("ALIGN", places) for an operation whose result cobc aligns, ("FOLD", value) for a pair of
# literals cobc folds at compile time (the folded literal keeps cobc's scale)
Plan = dict


class OsvsError(Exception):
    """An expression whose cobc decision this model does not replay."""


@dataclass
class Leaf:
    """What decimal_expand does with an operand: `kind` LITERAL | ITEM | FUNC | CONST, `scale` its decimal places,
    `pushes` whether it pushes them (expr_decp)."""

    kind: str
    scale: int = 0
    pushes: bool = True


@dataclass
class Relation:
    """One relation of a condition, its operands in cobc's order (x expanded first); `decimal` when either side is
    an operation (cobc compares in decimal then, cob_decimal_cmp)."""

    x: object
    y: object
    equality: bool = False  # = or NOT = (cobc's '=' / '~'): what compare_field_literal can decide at compile time
    decimal: bool = False
    plan: Plan = field(default_factory=dict)
    constant: bool = False  # decided at compile time (cb_true / cb_false): neither walked nor built


@dataclass(frozen=True)
class Num:
    """A numeric literal as cobc holds it (struct cb_literal): its digits as written (leading zeros kept), its scale
    and its sign (-1, 0, +1). Two literals are one decimal constant when all three agree (cb_lookup_literal)."""

    sign: int
    digits: str
    scale: int

    @property
    def value(self) -> Decimal:
        v = Decimal(int(self.digits or "0")).scaleb(-self.scale)
        return -v if self.sign < 0 else v

    @property
    def unscaled(self) -> int:
        return -int(self.digits or "0") if self.sign < 0 else int(self.digits or "0")

    @property
    def key(self) -> tuple:
        return (self.sign, self.digits, self.scale)

    @staticmethod
    def written(text: str) -> Num:
        sign = -1 if text[:1] == "-" else 1 if text[:1] == "+" else 0
        body = text.lstrip("+-")
        sep = "." if "." in body else "," if "," in body else None
        scale = len(body.split(sep, 1)[1]) if sep else 0
        return Num(sign, body.replace(".", "").replace(",", ""), scale)

    @staticmethod
    def of(v: Decimal) -> Num:
        """A literal known only by its value (a folded result, LENGTH OF, a DFHRESP value): no leading zeros."""
        t = v.as_tuple()
        scale = -t.exponent if isinstance(t.exponent, int) and t.exponent < 0 else 0
        digits = "".join(map(str, t.digits))
        if isinstance(t.exponent, int) and t.exponent > 0:
            digits += "0" * t.exponent
        return Num(-1 if t.sign else 0, digits, scale)

    @staticmethod
    def folded(rslt: int, rscale: int) -> Num:
        """cb_build_numeric_literal (0, sprintf ("%lld", rslt), rscale): a minus sign becomes the literal's sign."""
        return Num(-1 if rslt < 0 else 0, str(abs(rslt)), rscale)


def is_op(e) -> bool:
    return isinstance(e, (E.Bin, E.Neg))


class Folder:
    """cb_build_binary_op's constant folding of two numeric literals (cobc/tree.c), bottom up: the folded nodes and
    the scales cb_set_dmax saw."""

    def __init__(self, length: Callable | None = None):
        self.folded: dict[int, Num] = {}
        self.length = length
        self.dmax = -1
        self.attempted = False

    def literal(self, e) -> Num | None:
        """The literal an operand is to cobc: a numeric literal, LENGTH OF an item, a folded pair; else None."""
        if isinstance(e, E.Lit) and isinstance(e.value, Decimal):
            return Num.written(e.text) if e.text else Num.of(e.value)
        if isinstance(e, E.LengthOf) and self.length is not None:
            return Num.of(Decimal(self.length(e)))
        if isinstance(e, (E.Bin, E.Neg)) and id(e) in self.folded:
            return self.folded[id(e)]
        return None

    def fold(self, e) -> None:
        if isinstance(e, E.Neg):  # 0 - x: cb_zero is no literal, nothing to fold
            self.fold(e.operand)
            return
        if not isinstance(e, E.Bin):
            return
        self.fold(e.left)
        self.fold(e.right)
        x, y = self.literal(e.left), self.literal(e.right)
        if x is None or y is None or len(x.digits) < x.scale or len(y.digits) < y.scale:
            return
        if len(x.digits) > 18 or len(y.digits) > 18:
            raise OsvsError("a folded literal of more than 18 digits")
        xs, ys = x.scale, y.scale
        self.attempted = True
        self.dmax = max(self.dmax, xs, ys)
        xv, yv = x.unscaled, y.unscaled
        op = e.op
        rscale, rslt = 0, 0
        if op in ("+", "-"):
            while xs < ys:
                xv, xs = xv * 10, xs + 1
            while xs > ys:
                yv, ys = yv * 10, ys + 1
            rscale = xs
            rslt = xv + yv if op == "+" else xv - yv
        elif op == "*":
            rscale, rslt = xs + ys, xv * yv
        elif op == "/" and yv != 0:
            while ys > 0:
                xv, ys = xv * 10, ys - 1
            rscale = xs
            if xv % yv == 0:
                rslt = _cdiv(xv, yv)
        while rscale > 0 and rslt != 0 and rslt % 10 == 0:
            rslt, rscale = _cdiv(rslt, 10), rscale - 1
        if op in ("+", "-", "*"):
            self.folded[id(e)] = Num.folded(rslt, rscale)
        elif op == "/":
            if yv == 0:
                return
            if rslt != 0:
                self.folded[id(e)] = Num.folded(rslt, rscale)
            elif x.scale == 0 and y.scale == 0 and xv % yv == 0:
                self.folded[id(e)] = Num.folded(_cdiv(xv, yv), rscale)
        elif op == "**":
            if x.scale != 0 or y.scale != 0 or yv < 0:
                return
            self.folded[id(e)] = Num.folded(1 if yv == 0 or xv == 1 else xv**yv, 0)


def _cdiv(a: int, b: int) -> int:
    """C's integer division (toward zero)."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


class Sim:
    """cobc's compile-time state for one statement or condition: dmax, the expr_decp stack, the pending align."""

    def __init__(self, leaf: Callable, length: Callable, folder: Folder):
        self.leaf = leaf  # (operand) -> Leaf, for E.Ref / E.Func
        self.length = length  # (E.LengthOf) -> int
        self.folder = folder
        self.dmax = -1
        self.stack: list[int] = []
        self.pending: tuple | None = None  # (decimal, places, node, generation)
        self.plan: Plan = {}
        self.gen = 0  # the relation being built: an align left pending by another one hits a dead decimal

    # ---- dmax: cb_walk_cond ------------------------------------------------------------------------------------
    def walk(self, e) -> None:
        v = self.folder.literal(e)
        if v is not None:
            self.dmax = max(self.dmax, v.scale)
            return
        if isinstance(e, E.Ref):
            lf = self.leaf(e)
            if lf.kind == "ITEM":
                self.dmax = max(self.dmax, lf.scale)
        elif isinstance(e, E.Bin):
            self.walk(e.left)
            if e.op != "/":
                self.walk(e.right)
        elif isinstance(e, E.Neg):
            self.walk(e.operand)

    def receiver(self, scale: int) -> None:
        self.dmax = max(self.dmax, scale)

    # ---- decimal_expand / decimal_compute / decimal_align ---------------------------------------------------------
    def flush(self) -> None:
        if self.pending is not None:
            _, places, node, gen = self.pending
            if gen == self.gen:
                self.plan[id(node)] = ("ALIGN", places)
            self.pending = None

    def push(self, places: int) -> None:
        if len(self.stack) >= MAX_NESTED_EXPR:
            raise OsvsError(f"more than {MAX_NESTED_EXPR} nested expressions")
        self.stack.append(places)

    def _leaf_of(self, e) -> Leaf:
        v = self.folder.literal(e)
        if v is not None:  # cob_decimal_set_llint for a short integer, else cob_decimal_set_field
            return Leaf("LITERAL", v.scale, len(v.digits) >= 19 or v.scale != 0)
        if isinstance(e, E.Fig) and e.kind == "ZEROS":
            return Leaf("CONST", 0, False)
        if isinstance(e, (E.Ref, E.Func)):
            return self.leaf(e)
        raise OsvsError(f"an operand {type(e).__name__} in arithmetic")

    def _right_is_literal(self, e) -> bool:
        return self.folder.literal(e) is not None

    def expand(self, d: object, e) -> None:
        if (isinstance(e, E.Bin) and id(e) not in self.folder.folded) or isinstance(e, E.Neg):
            if isinstance(e, E.Neg):  # cobc: 0 - x (cb_zero, a constant: no align, no push)
                op, right = "-", e.operand
            else:
                op, right = e.op, e.right
                self.expand(d, e.left)
            if self._right_is_literal(right):
                self.compute(op, d, e)
            else:
                t = object()
                self.expand(t, right)
                self.compute(op, d, e)
            return
        lf = self._leaf_of(e)
        if lf.kind == "CONST":
            return
        self.flush()
        if lf.pushes:
            self.push(lf.scale)

    def compute(self, op: str, d: object, node) -> None:
        if self.pending is not None and self.pending[0] is not d:
            self.flush()
        places = self.dmax
        if len(self.stack) > 1:
            top = self.stack.pop()
            below = self.stack[-1]
            if op in ("+", "-"):
                below = max(below, top)
            elif op == "*":
                below += top
            elif op == "/":
                below = max(below - top, self.dmax)
            elif op == "**" and below - top < below:
                below -= top
            self.stack[-1] = below
            places = below
        self.pending = (d, places, node, self.gen) if places >= 0 else None


def plan_compute(
    expr, receiver_scales: list[int], leaf: Callable, length: Callable, operands_first: bool = False, dmax_in: int = -1
) -> Plan:
    """The plan of a COMPUTE (or an ADD / SUBTRACT / MULTIPLY / DIVIDE ... GIVING, op 0): build_decimal_assign.
    `operands_first` for ADD / SUBTRACT ... TO / FROM (an op other than 0): each receiver is loaded after the
    operands' sum, which aligns it -- then the plan also holds the sum's places under id(expr). `dmax_in`: the dmax an
    earlier statement of the sentence left (an EVALUATE's; build_decimal_assign takes the larger)."""
    folder = Folder(length)
    folder.fold(expr)
    sim = Sim(leaf, length, folder)
    sim.dmax = max(folder.dmax, dmax_in)
    for s in receiver_scales:
        sim.receiver(s)
    sim.walk(expr)
    sim.expand(object(), expr)
    if operands_first:
        sim.flush()  # decimal_expand (t, receiver) -> decimal_align
    plan = dict(sim.plan)
    for k, v in folder.folded.items():
        plan[k] = ("FOLD", v)
    plan[PLANNED] = True
    return plan


def plan_condition(
    groups: list[list[Relation]],
    leaf: Callable,
    length: Callable,
    evaluate: bool = False,
    state_in: tuple | None = None,
    field_constant: Callable | None = None,
) -> tuple | None:
    """Fill each Relation's plan, the relations of a condition (one group) or of an EVALUATE (one group per WHEN),
    each group in emission order (left to right). cobc builds a group's relations right to left; the state carries
    over the groups in order. An IF's dmax comes from its folded literals when it has any, else from the walk; an
    EVALUATE's folds were reset at parse time (cb_end_cond), and its first WHEN's walk serves every WHEN. `state_in`
    (dmax, stack): what an earlier statement of the sentence left (None: nothing). Returns the state the build leaves
    (an EVALUATE's stays for the rest of the sentence; an IF's, PERFORM's or SEARCH's is reset, cb_end_cond).
    `field_constant(item operand, literal, equality)`: whether cobc's compare_field_literal decides a relation of a
    USAGE DISPLAY item with a literal at compile time."""
    folder = Folder(length)
    for g in groups:
        for r in g:
            folder.fold(r.x)
            folder.fold(r.y)
    sim = Sim(leaf, length, folder)
    if state_in is not None:
        sim.dmax, sim.stack = state_in[0], list(state_in[1])
    if not evaluate and folder.attempted:
        sim.dmax = max(sim.dmax, folder.dmax)
    for g in groups:
        for r in g:
            r.decimal = any(is_op(n) and id(n) not in folder.folded for n in (r.x, r.y))
            x, y = folder.literal(r.x), folder.literal(r.y)
            if x is not None and y is not None:
                # two unsigned integer literals compare at compile time (cb_build_binary_op): cb_true / cb_false
                r.constant = x.sign == y.sign == 0 and x.scale == y.scale == 0
            elif field_constant is not None and not r.decimal:
                if (x is not None or _literal_node(r.x)) and isinstance(r.y, E.Ref):
                    r.constant = field_constant(r.y, x if x is not None else r.x, r.equality)
                elif (y is not None or _literal_node(r.y)) and isinstance(r.x, E.Ref):
                    r.constant = field_constant(r.x, y if y is not None else r.y, r.equality)
    for g in groups:
        if sim.dmax == -1:
            for r in g:
                if not r.constant:
                    sim.walk(r.x)
                    sim.walk(r.y)
        for r in reversed(g):
            if not r.decimal:
                continue
            sim.plan = {}
            sim.gen += 1
            sim.expand(object(), r.x)
            sim.expand(object(), r.y)
            r.plan = dict(sim.plan)
            r.plan[PLANNED] = True
            for n in (r.x, r.y):
                _folds_of(n, folder, r.plan)
    # a pending align left on the last relation's right side is never applied to a live value
    return None if sim.dmax == -1 and not sim.stack else (sim.dmax, list(sim.stack))


def _literal_node(e) -> bool:
    """ZERO (cobc's cb_zero_lit there) or a nonnumeric literal."""
    return (isinstance(e, E.Fig) and e.kind == "ZEROS") or (isinstance(e, E.Lit) and not isinstance(e.value, Decimal))


def _folds_of(e, folder: Folder, plan: Plan) -> None:
    if isinstance(e, (E.Bin, E.Neg)):
        if id(e) in folder.folded:
            plan[id(e)] = ("FOLD", folder.folded[id(e)])
            return
        if isinstance(e, E.Bin):
            _folds_of(e.left, folder, plan)
            _folds_of(e.right, folder, plan)
        else:
            _folds_of(e.operand, folder, plan)
