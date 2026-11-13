# ==============================================================================
# GitGalaxy Core: C++ constructions the text does not write as a call (#8161, P3)
#
# PURPOSE:
# `Foo x;`, `Foo x{a, b};`, `Foo x = "lit";` and `std::make_unique<Foo>(a)` each
# run a constructor of Foo, but no `Foo(` is written: the call scan sees nothing
# (`Foo x(a)` and `Foo(a)` are written calls, contract C3, and stay `call`).
# Owner decision (#8161): such an edge is its own kind, `ctor`, never folded
# into `call`, and reported per kind (docs/calls_out_rule_contract.md, "Edge
# kinds"). This module reads them from one unit's literal-shielded body:
#   - a declaration that opens a statement (after `;`, `{`, `}`, `:` or the
#     body's start), of a named type, with no `*` / `&` declarator, ending in
#     `;` (no arguments), `{..}` (brace arguments) or `= literal;` (one: a
#     converting constructor);
#   - `make_unique<T>(..)` / `make_shared<T>(..)` (the call's arguments).
# The resolver keeps one only when the type is a repository class with a
# constructor of its own (a class with an implicit one has no unit to reach).
# Every quantifier is bounded or possessive; scans are linear.
# ==============================================================================
import re

_IDENT = r"[A-Za-z_]\w{0,127}"
_SCOPE = r"(?P<q>(?:::[ \t]*+)?(?:" + _IDENT + r"[ \t]*+(?:<[^;(){}]{0,200}?>)?[ \t]*+::[ \t]*+){0,6})"
_DECL = re.compile(
    r"(?<![\w.:>~*&])(?=[A-Za-z_:])"
    r"(?:(?:const|static|constexpr|thread_local|volatile|mutable)[ \t]++){0,4}"
    + _SCOPE
    + r"(?P<t>"
    + _IDENT
    + r")(?:[ \t]*+<[^;(){}]{0,200}?>)?[ \t\r\n]++(?P<n>"
    + _IDENT
    + r")[ \t]*+(?P<after>;|\{|=[ \t]*+(?:\"\"|'[^'\n]{0,4}'|-?[0-9][\w.']{0,40})[ \t]*+;)"
)
_MAKE = re.compile(
    r"(?<![\w.])(?:std[ \t]*+::[ \t]*+)?make_(?:unique|shared)[ \t]*+<[ \t]*+(?:const[ \t]++)?"
    + _SCOPE
    + r"(?P<t>"
    + _IDENT
    + r")[ \t]*+(?:<[^;(){}]{0,200}?>)?[ \t]*+>[ \t]*+\("
)
# words that stand where a declaration's type would but construct nothing
_NOT_TYPES = frozenset(
    {"return", "else", "new", "delete", "throw", "case", "goto", "co_return", "co_await", "co_yield",
     "sizeof", "alignof", "typedef", "using", "operator", "do", "not", "and", "or", "xor", "template",
     "namespace", "public", "private", "protected", "friend", "virtual", "explicit", "default", "if",
     "while", "for", "switch", "auto", "decltype", "static_cast", "const_cast", "reinterpret_cast",
     "dynamic_cast", "noexcept", "override", "final", "inline", "extern", "enum", "union", "void",
     "struct", "class", "typename", "try", "catch", "break", "continue", "unsigned", "signed", "short",
     "long", "int", "char", "bool", "float", "double", "wchar_t", "char8_t", "char16_t", "char32_t",
     "size_t", "concept", "requires", "export", "import", "module"}
)  # fmt: skip
_STATEMENT_OPENERS = frozenset(";{}:")


def _body_start(text: str) -> int:
    """Offset just past the unit's body `{` (the first one outside its header's parentheses), or -1."""
    depth = 0
    for k, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "{" and depth == 0:
            return k + 1
    return -1


def _opens_statement(text: str, at: int, floor: int) -> bool:
    k = at - 1
    while k >= floor and text[k] in " \t\r\n":
        k -= 1
    return k < floor or (text[k] in _STATEMENT_OPENERS and not text.startswith("::", max(k - 1, 0)))


def _args_in(text: str, open_at: int) -> int | None:
    """Argument count of the `{..}` / `(..)` list opening at `open_at`; None when it does not close nearby."""
    depth, commas, empty = 0, 0, True
    for k in range(open_at, min(len(text), open_at + 4000)):
        ch = text[k]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
            if depth == 0:
                return 0 if empty else commas + 1
        elif ch == "," and depth == 1:
            commas += 1
        elif depth >= 1 and ch not in " \t\r\n":
            empty = False
    return None


def ctor_sites(text: str) -> list[tuple[str, str, int]]:
    """(type leaf, scope qualifier, argument count) of every construction the unit's body does not write as a
    call; `text` is the whole unit, literal-shielded."""
    start = _body_start(text)
    if start < 0:
        return []
    out: list[tuple[str, str, int]] = []
    for m in _DECL.finditer(text, start):
        t, n = m.group("t"), m.group("n")
        if t in _NOT_TYPES or n in _NOT_TYPES or not _opens_statement(text, m.start(), start):
            continue
        after = m.group("after")
        if after == ";":
            arity: int | None = 0
        elif after == "{":
            arity = _args_in(text, m.end() - 1)
        else:
            arity = 1
        if arity is not None:
            out.append((t, _scope(m.group("q")), arity))
    for m in _MAKE.finditer(text, start):
        arity = _args_in(text, m.end() - 1)
        if arity is not None:
            out.append((m.group("t"), _scope(m.group("q")), arity))
    return out


def _scope(q: str | None) -> str:
    """`std :: detail ::` -> `std::detail` (template arguments dropped)."""
    if not q:
        return ""
    q = re.sub(r"<[^<>]{0,200}>", "", q)
    return "::".join(p.strip() for p in q.split("::") if p.strip())
