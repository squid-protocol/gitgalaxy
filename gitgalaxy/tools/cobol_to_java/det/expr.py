"""COBOL expressions and conditions from a flat token list (tree-sitter's leaves), into a small AST.

Operands: identifiers (with OF/IN qualification, subscripts and reference modification), literals, figurative
constants, FUNCTION calls, LENGTH OF. Arithmetic: + - * / ** with unary minus, parentheses. Conditions: relations
(= > < >= <= NOT, EQUAL TO, GREATER THAN ...), class (NUMERIC, ALPHABETIC...), sign (POSITIVE, NEGATIVE, ZERO),
condition-names (an 88), NOT / AND / OR, and COBOL's abbreviated combined relations (`A = 1 OR 2`,
`A NOT = 'X' AND 'Y'`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


class ExprError(Exception):
    pass


# ---- the AST -------------------------------------------------------------------------------------------------
@dataclass
class Ref:
    """A data reference: NAME [OF Q ...] [(subscripts)] [(start:length)]."""

    name: str
    qualifiers: list = field(default_factory=list)
    subscripts: list = field(default_factory=list)  # expressions
    refmod: tuple | None = None  # (start expr, length expr | None)


@dataclass
class Lit:
    """A nonnumeric literal (text) or a numeric literal (Decimal)."""

    value: str | Decimal | bytes


@dataclass
class Fig:
    """A figurative constant: SPACES ZEROS LOW HIGH QUOTES, or ALL 'x'."""

    kind: str
    all_literal: str | None = None
    hex: bool = False  # #4462: ALL X'00' (all_literal holds its bytes, one character each)


@dataclass
class Func:
    name: str
    args: list


@dataclass
class LengthOf:
    ref: Ref


@dataclass
class Bin:
    op: str  # + - * / **
    left: object
    right: object


@dataclass
class Neg:
    operand: object


@dataclass
class Rel:
    op: str  # = > < >= <= <>
    left: object
    right: object


@dataclass
class ClassCond:
    operand: object
    kind: str  # NUMERIC ALPHABETIC ALPHABETIC-UPPER ALPHABETIC-LOWER POSITIVE NEGATIVE ZERO
    negated: bool = False


@dataclass
class CondName:
    ref: Ref
    abbrev: tuple[str, object, bool] | None = (
        None  # (op, subject, negated): an abbreviated relation's object, if not a condition-name
    )


@dataclass
class Not:
    cond: object


@dataclass
class And:
    left: object
    right: object


@dataclass
class Or:
    left: object
    right: object


FIGURATIVES = {
    "SPACE": "SPACES", "SPACES": "SPACES", "ZERO": "ZEROS", "ZEROS": "ZEROS", "ZEROES": "ZEROS",
    "LOW-VALUE": "LOW", "LOW-VALUES": "LOW", "HIGH-VALUE": "HIGH", "HIGH-VALUES": "HIGH", "QUOTE": "QUOTES",
    "QUOTES": "QUOTES",
}  # fmt: skip
REL_WORDS = {"=": "=", ">": ">", "<": "<", ">=": ">=", "<=": "<=", "<>": "<>"}
CLASS_WORDS = {"NUMERIC", "ALPHABETIC", "ALPHABETIC-UPPER", "ALPHABETIC-LOWER", "POSITIVE", "NEGATIVE", "ZERO"}
RESERVED_STOP = {"AND", "OR", "NOT", "THEN", "IS", "TO", "OF", "IN", "THAN", "EQUAL", "EQUALS", "GREATER",
                 "LESS", "UNTIL", "VARYING", "FROM", "BY", "GIVING", "ROUNDED", "ON", "SIZE", "ERROR",
                 "WHEN", "ALSO", "THRU", "THROUGH", "DELIMITED", "INTO", "WITH", "POINTER", "END-IF",
                 "END-EVALUATE", "END-PERFORM", "END-COMPUTE"} | set(CLASS_WORDS)  # fmt: skip


class Parser:
    """A cursor over tokens (strings, already split: literals whole, '(' ')' ':' separate)."""

    def __init__(self, tokens: list[str]):
        self.t = tokens
        self.i = 0

    def peek(self, k: int = 0) -> str | None:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def up(self, k: int = 0) -> str | None:
        p = self.peek(k)
        return p.upper() if p is not None and p[:1] not in "'\"" else p

    def take(self) -> str:
        tok = self.peek()
        if tok is None:
            raise ExprError("unexpected end of expression")
        self.i += 1
        return tok

    def accept(self, *words: str) -> bool:
        if self.up() in words:
            self.i += 1
            return True
        return False

    def done(self) -> bool:
        return self.i >= len(self.t)

    # ---- operands ------------------------------------------------------------------------------------------
    def operand(self) -> object:
        tok = self.peek()
        if tok is None:
            raise ExprError("missing operand")
        u = self.up()
        if u is None:
            raise ExprError("missing operand")
        if tok[:1] in "'\"":
            self.i += 1
            return Lit(_unquote(tok))
        if u[:2] in ("X'", 'X"') and len(tok) > 2:
            self.i += 1
            return Lit(bytes.fromhex(tok[2:-1]))
        if u == "ALL" and self.peek(1) is not None:
            self.i += 1
            nxt = self.take()
            if nxt[:1] in "'\"":
                return Fig("ALL", _unquote(nxt))
            if nxt[:2].upper() in ("X'", 'X"') and len(nxt) > 3:  # #4462: MOVE ALL X'00' (estate-crucible KØBREG)
                return Fig("ALL", bytes.fromhex(nxt[2:-1]).decode("latin-1"), hex=True)
            if nxt.upper() in FIGURATIVES:
                return Fig(FIGURATIVES[nxt.upper()])
            raise ExprError(f"ALL {nxt}")
        if u in FIGURATIVES:
            self.i += 1
            return Fig(FIGURATIVES[u])
        if u in ("NULL", "NULLS"):  # the pointer figurative: pointers are not modelled
            raise ExprError("NULL: pointers are not modelled")
        if _is_number(tok):
            self.i += 1
            return Lit(Decimal(tok.replace(",", ".") if tok.count(",") == 1 and "." not in tok else tok))
        if u in ("+", "-") and (nxt1 := self.peek(1)) is not None and _is_number(nxt1):
            self.i += 2
            return Lit(Decimal(u + self.t[self.i - 1]))
        if u == "FUNCTION":
            self.i += 1
            name = self.take().upper()
            args = []
            # #4462: `FUNCTION CURRENT-DATE (1:4)`: a parenthesis holding a ':' is a reference modification, not
            # the arguments (a function of no arguments)
            if self.peek() == "(" and not self._refmod_group():
                self.i += 1
                while self.peek() != ")":
                    if self.peek() == ",":
                        self.i += 1
                        continue
                    args.append(self.arith())
                self.i += 1
            ref = None
            if self.peek() == "(" and self._refmod_group():
                ref = self._refmod()
            f = Func(name, args)
            return f if ref is None else Func(name, [*args, ("REFMOD", ref)])
        if u in ("LENGTH",) and self.up(1) == "OF":
            self.i += 2
            return LengthOf(self.ref())
        if u in ("ADDRESS",) and self.up(1) == "OF":
            raise ExprError("ADDRESS OF")
        r = self.ref()
        if r.name == "DFHRESP" and len(r.subscripts) == 1 and isinstance(r.subscripts[0], Ref):
            # DFHRESP(condition): the condition's RESP value (IBM CICS TS)
            from gitgalaxy.tools.cobol_to_java.det.cics import DFHRESP

            cond = r.subscripts[0].name
            if cond not in DFHRESP:
                raise ExprError(f"DFHRESP({cond}) is not a documented condition")
            return Lit(Decimal(DFHRESP[cond]))
        if r.name == "DFHVALUE" and len(r.subscripts) == 1 and isinstance(r.subscripts[0], Ref):
            # DFHVALUE(name): the CVDA's numeric value (IBM CICS TS, CVDAs and numeric values)
            from gitgalaxy.tools.cobol_to_java.det.cvda import CVDA

            name = r.subscripts[0].name
            if name not in CVDA:
                raise ExprError(f"DFHVALUE({name}) is not a documented CVDA")
            return Lit(Decimal(CVDA[name]))
        return r

    def _refmod_group(self) -> bool:
        """Whether the parenthesised group at the cursor holds a ':' of its own (a reference modification)."""
        depth = 0
        for tok in self._group():
            depth += {"(": 1, ")": -1}.get(tok, 0)
            if tok == ":" and depth == 1:
                return True
        return False

    def _group(self) -> list[str]:
        """The tokens of the parenthesised group at the cursor (not consumed)."""
        depth, out = 0, []
        for tok in self.t[self.i :]:
            out.append(tok)
            if tok == "(":
                depth += 1
            elif tok == ")":
                depth -= 1
                if depth == 0:
                    break
        return out

    def ref(self) -> Ref:
        name = self.take()
        if not _is_word(name):
            raise ExprError(f"not a data name: {name}")
        r = Ref(name.upper())
        while self.up() in ("OF", "IN"):
            self.i += 1
            r.qualifiers.append(self.take().upper())
        while self.peek() == "(":
            grp = self._group()
            if ":" in grp[1:-1] and _depth0_colon(grp):
                r.refmod = self._refmod()
            else:
                self.i += 1
                subs = []
                while self.peek() != ")":
                    subs.append(self.arith())
                    if self.peek() == ",":
                        self.i += 1
                self.i += 1
                r.subscripts = subs
        return r

    def _refmod(self) -> tuple:
        self.i += 1  # (
        start = self.arith()
        if self.take() != ":":
            raise ExprError("reference modification without ':'")
        length = None if self.peek() == ")" else self.arith()
        if self.take() != ")":
            raise ExprError("reference modification not closed")
        return (start, length)

    # ---- arithmetic -------------------------------------------------------------------------------------------
    def arith(self) -> object:
        left = self.term()
        while self.peek() in ("+", "-") and not self._sign_of_literal():
            op = self.take()
            left = Bin(op, left, self.term())
        return left

    def _sign_of_literal(self) -> bool:
        return False

    def term(self) -> object:
        left = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            left = Bin(op, left, self.power())
        return left

    def power(self) -> object:
        base = self.unary()
        if self.peek() == "**":
            self.i += 1
            return Bin("**", base, self.power())
        return base

    def unary(self) -> object:
        if self.peek() == "-":
            self.i += 1
            return Neg(self.unary())
        if self.peek() == "+":
            self.i += 1
            return self.unary()
        if self.peek() == "(":
            self.i += 1
            e = self.arith()
            if self.take() != ")":
                raise ExprError("unbalanced parenthesis")
            return e
        return self.operand()

    # ---- conditions ---------------------------------------------------------------------------------------------
    def condition(self) -> object:
        left = self._and()
        while self.accept("OR"):
            left = Or(left, self._and(previous=left))
        return left

    def _and(self, previous=None) -> object:
        left = self._not(previous)
        while self.accept("AND"):
            left = And(left, self._not(previous=left))
        return left

    def _not(self, previous=None) -> object:
        if self.up() == "NOT" and not self._rel_op_ahead(1):
            self.i += 1
            return Not(self._not(previous))
        return self._simple(previous)

    def _rel_op_ahead(self, k: int) -> bool:
        u = self.up(k)
        return u in REL_WORDS or u in ("EQUAL", "EQUALS", "GREATER", "LESS")

    def _simple(self, previous) -> object:
        if self.peek() == "(" and self._paren_is_condition():
            self.i += 1
            c = self.condition()
            if self.take() != ")":
                raise ExprError("unbalanced parenthesis in condition")
            return c
        # an abbreviated relation: `... OR 2` / `... AND NOT = 'Y'` -- the subject (and operator) of the last one
        if previous is not None and (self._rel_start() or self._looks_like_object_only()):
            last, negated = _last_rel(previous)
            if last is not None:
                if self._rel_start():
                    op, neg = self._rel_op()
                    obj = self.arith()
                    r = Rel(op, last.left, obj)
                    return Not(r) if neg else r
                # the object only: the subject and the relation (its NOT included) of the last one
                obj = self.arith()
                r = Rel(last.op, last.left, obj)
                return Not(r) if negated else r
        left = self.arith()
        if self.up() == "IS":
            self.i += 1
        neg = False
        if self.up() == "NOT" and self.up(1) in CLASS_WORDS:
            self.i += 1
            neg = True
        if self.up() in CLASS_WORDS:
            kind = self.take().upper()
            return ClassCond(left, kind, neg)
        if self._rel_start():
            op, n2 = self._rel_op()
            right = self.arith()
            r = Rel(op, left, right)
            return Not(r) if (n2 ^ neg) else r
        if isinstance(left, Ref):
            cn = CondName(left)
            last, negated = _last_rel(previous) if previous is not None else (None, False)
            if last is not None:
                # `EIBAID NOT = DFHENTER AND DFHPF7`: a data name here is the last relation's object unless it
                # is a condition-name -- which the translator, knowing the data, decides
                cn.abbrev = (last.op, last.left, negated)
            return cn
        raise ExprError(f"not a condition near {self.peek()!r}")

    def _paren_is_condition(self) -> bool:
        grp = [g.upper() for g in self._group()]
        return any(g in REL_WORDS or g in ("AND", "OR", "NOT", "EQUAL", "GREATER", "LESS") or g in CLASS_WORDS
                   for g in grp)  # fmt: skip

    def _looks_like_object_only(self) -> bool:
        """`A = 1 OR 2`: after OR / AND comes an operand with no relation of its own before the next OR / AND."""
        j = self.i
        depth = 0
        while j < len(self.t):
            tok = self.t[j].upper() if self.t[j][:1] not in "'\"" else self.t[j]
            if tok == "(":
                depth += 1
            elif tok == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and tok in ("AND", "OR"):
                break
            elif depth == 0 and (tok in REL_WORDS or tok in ("EQUAL", "GREATER", "LESS", "IS") or tok in CLASS_WORDS):
                return False
            j += 1
        # a bare data name could be a condition-name: only an operand that is a literal / figurative is an object
        first = self.t[self.i]
        return first[:1] in "'\"" or _is_number(first) or first.upper() in FIGURATIVES or first.upper() == "ALL"

    def _rel_start(self) -> bool:
        u = self.up()
        return u in REL_WORDS or u in ("EQUAL", "EQUALS", "GREATER", "LESS") or (u == "NOT" and self._rel_op_ahead(1))

    def _rel_op(self) -> tuple[str, bool]:
        neg = self.accept("NOT")
        u = self.take().upper()
        if u in REL_WORDS:
            op = REL_WORDS[u]
        elif u in ("EQUAL", "EQUALS"):
            self.accept("TO")
            op = "="
        elif u == "GREATER":
            self.accept("THAN")
            if self.accept("OR"):
                self.accept("EQUAL")
                self.accept("TO")
                op = ">="
            else:
                op = ">"
        elif u == "LESS":
            self.accept("THAN")
            if self.accept("OR"):
                self.accept("EQUAL")
                self.accept("TO")
                op = "<="
            else:
                op = "<"
        else:
            raise ExprError(f"not a relation: {u}")
        if op == "<>":
            return "=", not neg
        return op, neg


def _last_rel(c, negated: bool = False) -> tuple[Rel | None, bool]:
    """The last relation of a condition and whether a NOT applies to it: (Rel | None, negated)."""
    if isinstance(c, Rel):
        return c, negated
    if isinstance(c, Not):
        return _last_rel(c.cond, not negated)
    if isinstance(c, (And, Or)):
        return _last_rel(c.right, negated)
    if isinstance(c, CondName) and c.abbrev is not None:
        op, subject, neg = c.abbrev
        return Rel(op, subject, c.ref), negated ^ neg
    return None, False


def _unquote(tok: str) -> str:
    q = tok[0]
    return tok[1:-1].replace(q * 2, q)


def _is_number(tok: str) -> bool:
    t = tok.lstrip("+-").replace(",", "").replace(".", "", 1)
    return bool(t) and t.isdigit() and tok[:1] not in "'\"" and (tok[:1] not in "+-" or len(tok) > 1)


def _is_word(tok: str) -> bool:
    return (
        bool(tok) and tok[:1] not in "'\"()" and not _is_number(tok) and tok not in ("+", "-", "*", "/", "**", ":", ",")
    )


def _depth0_colon(grp: list[str]) -> bool:
    depth = 0
    for tok in grp:
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif tok == ":" and depth == 1:
            return True
    return False


def tokenize(text: str) -> list[str]:
    """Literals whole; ( ) : , and operators separate; a period at the end dropped."""
    import re

    toks = re.findall(r"X'[0-9A-Fa-f]*'|X\"[0-9A-Fa-f]*\"|'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|>=|<=|<>|\*\*|[()=<>:,+*/]"
                      r"|-?\d+(?:\.\d+)?(?=[\s()=<>:,+*/]|$)|[^\s()=<>:,+*/]+", text)  # fmt: skip
    if toks and toks[-1] == ".":
        toks.pop()
    # a comma (or semicolon) separates like a space in COBOL
    return [
        t.rstrip(".") if t.endswith(".") and t[:1] not in "'\"" and t != "." else t
        for t in toks
        if t not in (".", ",", ";")
    ]


def parse_condition(text: str):
    p = Parser(tokenize(text))
    c = p.condition()
    if not p.done():
        raise ExprError(f"left over in condition: {' '.join(p.t[p.i :])}")
    return c


def parse_arith(text: str):
    p = Parser(tokenize(text))
    e = p.arith()
    if not p.done():
        raise ExprError(f"left over in expression: {' '.join(p.t[p.i :])}")
    return e
