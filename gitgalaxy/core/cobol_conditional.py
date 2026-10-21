# ==============================================================================
# GitGalaxy Core: COBOL conditional compilation, >>DEFINE / >>IF / >>ELSE / >>END-IF (#5648)
#
# PURPOSE:
# Enterprise COBOL 6 reads compiler-directing statements before it reads any
# COBOL: a `>>IF` branch that is not taken is not source, so a COPY, a data item
# or a paragraph inside it does not exist. Nothing here read them: the translator
# took every branch. `Conditional` is the one reader (the options come from
# core.compiler_options): feed it each source line in order; `feed` says whether
# the line is COBOL text to keep (True) or a directive / an inactive line (False).
#
#   >>DEFINE name AS literal [OVERRIDE]   a numeric or alphanumeric literal; a DEFINE(name=...) compiler option does
#                                         not change it (IBM: an option without a matching AS PARAMETER is ignored)
#   >>DEFINE name AS PARAMETER            the value of the DEFINE(name=literal) compiler option; with no such option
#                                         the name is not defined (IBM), which `IS DEFINED` can test
#   >>IF condition / >>ELSE / >>END-IF    nest; condition: `name IS [NOT] DEFINED`, a relation of names and literals
#                                         (=, <>, <, >, <=, >=, NOT, EQUAL TO, GREATER / LESS THAN [OR EQUAL TO];
#                                         only = / <> on alphanumeric operands, IBM), NOT, AND, OR, parentheses
#   IBM reference (Enterprise COBOL for z/OS 6.4 Language Reference): "DEFINE directive" (rldirdef), "Constant
#   conditional expressions" (rldircons), "Conditional compilation" (rldircon); the DEFINE compiler option page.
#
# SCOPE AND NON-SCOPE:
#   - A directive in an inactive branch is ignored, except the IF / ELSE / END-IF that keep the nesting.
#   - Refused by name (ConditionalCompilation), never guessed: an unknown form of >>DEFINE (OFF, TRUE / FALSE), a
#     relation on a name nothing defines, a numeric against an alphanumeric operand, `>>ELSE` or `>>END-IF` with no
#     `>>IF`, an `>>IF` left open at the end (`finish`), `>>EVALUATE`, a second `>>DEFINE` of a name to another
#     value without OVERRIDE (IBM: it "must" have the same value), an ordering relation on alphanumerics, any of these in a COPY member (`refuse`): the
#     compilation variables a member sees are the program's at the COPY, which a reader of the member alone lacks.
#   - Options given outside the source (the compile step's PARM) are not read here: `defines` carries them when a
#     caller has them. Directives other than these (`>>SOURCE FORMAT`, `>>D`) are left to the reader that owns them.
#   - No burned-estate program uses a conditional-compilation directive, so no port depends on this reader.
# ==============================================================================
from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from gitgalaxy.core.cobol_preprocessor import drop_comment

Value = Decimal | str

_TOKEN = re.compile(
    r"""\s*(?:(?P<str>'(?:[^']|'')*'|"(?:[^"]|"")*")|(?P<num>[+-]?\d+(?:\.\d+)?)|(?P<op><>|<=|>=|=|<|>|\(|\))"""
    r"""|(?P<word>[A-Z][A-Z0-9_-]*))""",
    re.I,
)
_DIRECTIVE = re.compile(r"\s*>>\s*(IF|ELSE|END-IF|DEFINE|EVALUATE|WHEN)\b(.*)", re.I | re.S)


class ConditionalCompilation(ValueError):
    """A conditional-compilation directive this reader refuses by name (see the module header)."""


def _tokens(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ConditionalCompilation(f"cannot read {text[pos:].strip()!r}")
        kind = m.lastgroup or ""
        out.append((kind, m.group(kind).upper() if kind == "word" else m.group(kind)))
        pos = m.end()
    return out


def _literal(kind: str, text: str) -> Value | None:
    if kind == "num":
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    if kind == "str":
        return text[1:-1].replace(text[0] * 2, text[0])
    return None


def options_defines(rows: Iterable[dict[str, Any]]) -> dict[str, Value]:
    """{name: value} of the `DEFINE(name=literal)` rows of core.compiler_options.compiler_options (later wins)."""
    out: dict[str, Value] = {}
    for r in rows:
        if r.get("option") != "DEFINE":
            continue
        name, _, raw = str(r.get("value") or "").partition("=")
        toks = _tokens(raw) if raw.strip() else []
        value = _literal(*toks[0]) if len(toks) == 1 else None
        if not name.strip() or value is None:
            raise ConditionalCompilation(
                f"compiler option DEFINE({r.get('value')}): only name=literal (numeric or quoted) is read"
            )
        out[name.strip().upper()] = value
    return out


class Conditional:
    """The state of `>>IF` nesting over one source, line by line."""

    def __init__(self, defines: dict[str, Value] | None = None, refuse: str = "") -> None:
        self.option: dict[str, Value] = dict(defines or {})
        self.refuse = refuse  # set: every directive is refused with this reason (a COPY member, see logical_lines)
        # a name's value; None: declared by AS PARAMETER with no option, so not defined. An option alone defines
        # nothing: IBM ignores a DEFINE option that no `>>DEFINE name AS PARAMETER` asks for.
        self.declared: dict[str, Value | None] = {}
        # one entry per open >>IF: [branch taken, parent active, in the >>ELSE part]
        self._stack: list[list[bool]] = []
        self.where = ""
        self._toks: list[tuple[str, str]] = []
        self._pos = 0

    @property
    def active(self) -> bool:
        return all(f[0] != f[2] and f[1] for f in self._stack) if self._stack else True

    def _fail(self, why: str) -> ConditionalCompilation:
        return ConditionalCompilation(f"{self.where + ': ' if self.where else ''}{why}")

    def feed(self, code: str, where: str = "") -> bool:
        """True when `code` (one source line, columns 8-72 or free text) is COBOL to keep; False for a directive
        this reader consumes and for any line inside an inactive branch."""
        self.where = where
        m = _DIRECTIVE.match(drop_comment(code))
        if not m:
            return self.active
        word, rest = m.group(1).upper(), m.group(2)
        if self.refuse:
            raise self._fail(f">>{word}: {self.refuse}")
        if word in ("EVALUATE", "WHEN"):
            raise self._fail(f">>{word}: not read (refused by name)")
        if word == "IF":
            parent = self.active
            taken = self._condition(rest) if parent else False
            self._stack.append([taken, parent, False])
        elif word == "ELSE":
            if not self._stack:
                raise self._fail(">>ELSE with no open >>IF")
            if self._stack[-1][2]:
                raise self._fail("second >>ELSE in one >>IF")
            self._stack[-1][2] = True
        elif word == "END-IF":
            if not self._stack:
                raise self._fail(">>END-IF with no open >>IF")
            self._stack.pop()
        elif self.active:
            self._define(rest)
        return False

    def finish(self, where: str = "") -> None:
        if self._stack:
            self.where = where
            raise self._fail(f"{len(self._stack)} >>IF still open at the end of the source (no >>END-IF)")

    # ---- >>DEFINE ----
    def _define(self, rest: str) -> None:
        toks = _tokens(drop_comment(rest))
        words = [t[1] for t in toks]
        if len(toks) < 3 or toks[0][0] != "word" or words[1] != "AS":
            raise self._fail(
                f">>DEFINE{rest.rstrip()}: only `name AS literal [OVERRIDE]` / `name AS PARAMETER` is read"
            )
        name = words[0]
        override = len(toks) == 4 and words[3] == "OVERRIDE"
        if words[2] == "PARAMETER" and toks[2][0] == "word":
            value = self.option.get(name)
        else:
            value = _literal(*toks[2])
            if value is None:
                raise self._fail(
                    f">>DEFINE{rest.rstrip()}: only `name AS literal [OVERRIDE]` / `name AS PARAMETER` is read"
                )
        if not (len(toks) == 3 or override):
            raise self._fail(
                f">>DEFINE{rest.rstrip()}: only `name AS literal [OVERRIDE]` / `name AS PARAMETER` is read"
            )
        if not override and name in self.declared and self.declared[name] != value:
            raise self._fail(f">>DEFINE {name}: declared again with another value and no OVERRIDE (refused)")
        self.declared[name] = value

    # ---- >>IF condition ----
    def _condition(self, rest: str) -> bool:
        toks = _tokens(drop_comment(rest))
        self._toks, self._pos = toks, 0
        result = self._or()
        if self._pos != len(toks):
            raise self._fail(f">>IF: cannot read the condition at {toks[self._pos][1]!r}")
        return result

    def _peek(self, *words: str) -> bool:
        return self._pos < len(self._toks) and self._toks[self._pos][1] in words

    def _take(self, *words: str) -> bool:
        if self._peek(*words):
            self._pos += 1
            return True
        return False

    def _or(self) -> bool:
        left = self._and()
        while self._take("OR"):
            right = self._and()
            left = left or right
        return left

    def _and(self) -> bool:
        left = self._not()
        while self._take("AND"):
            right = self._not()
            left = left and right
        return left

    def _not(self) -> bool:
        if self._take("NOT"):
            return not self._not()
        if self._take("("):
            inner = self._or()
            if not self._take(")"):
                raise self._fail(">>IF: missing )")
            return inner
        return self._relation()

    def _operand(self) -> tuple[Value | None, str | None]:
        """(value, name): a literal has no name; an undefined name has no value."""
        if self._pos >= len(self._toks):
            raise self._fail(">>IF: the condition ends where an operand is expected")
        kind, text = self._toks[self._pos]
        self._pos += 1
        if kind == "word":
            return self.declared.get(text), text
        value = _literal(kind, text)
        if value is None:
            raise self._fail(f">>IF: {text!r} is not an operand")
        return value, None

    def _relation(self) -> bool:
        left, name = self._operand()
        self._take("IS")
        negate = self._take("NOT")
        if self._take("DEFINED"):
            if name is None:
                raise self._fail(">>IF: DEFINED needs a name")
            return (left is None) == negate
        order = self._order()
        right, rname = self._operand()
        for value, n in ((left, name), (right, rname)):
            if value is None:
                raise self._fail(f">>IF: {n} is not defined (a relation on an undefined name is refused)")
        if isinstance(left, Decimal) != isinstance(right, Decimal):
            raise self._fail(">>IF: a numeric operand is compared with an alphanumeric one (refused)")
        if isinstance(left, str) and isinstance(right, str):  # a shorter operand is padded with spaces
            if order(-1) != order(1):  # (not = / <>)
                raise self._fail(">>IF: only = or <> compares alphanumeric operands (refused)")
            width = max(len(left), len(right))
            left, right = left.ljust(width), right.ljust(width)
        c = (left > right) - (left < right)  # type: ignore[operator, unused-ignore]
        return order(c) != negate

    def _order(self):
        """The comparison as a function of cmp(left, right) in {-1, 0, 1}."""
        if self._pos >= len(self._toks):
            raise self._fail(">>IF: the condition ends where a relational operator is expected")
        if self._take("<>"):
            return lambda c: c != 0
        for sym, fn in (("<=", lambda c: c <= 0), (">=", lambda c: c >= 0), ("=", lambda c: c == 0),
                        ("<", lambda c: c < 0), (">", lambda c: c > 0)):  # fmt: skip
            if self._take(sym):
                return fn
        for words, base in ((("EQUAL",), 0), (("GREATER",), 1), (("LESS",), -1)):
            if self._take(*words):
                self._take("TO", "THAN")
                if base and self._take("OR"):
                    if not self._take("EQUAL"):
                        raise self._fail(">>IF: OR must be followed by EQUAL")
                    self._take("TO")
                    return (lambda c: c >= 0) if base > 0 else (lambda c: c <= 0)
                return (lambda c: c == 0) if base == 0 else ((lambda c: c > 0) if base > 0 else (lambda c: c < 0))
        raise self._fail(f">>IF: {self._toks[self._pos][1]!r} is not a relational operator")
