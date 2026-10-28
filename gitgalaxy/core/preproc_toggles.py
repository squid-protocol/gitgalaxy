"""C-family preprocessor toggles no file of the scan ever defines (#6770).

`#if 0` is dead by its own text; `#if defined(I_NET_ENABLED)` is dead only if nothing defines `I_NET_ENABLED`.
A scan can know that for a repo-owned feature toggle: the name is never `#define`d / `#undef`d in any C-family
file, never named by a build file, and never read as a token in code (only in conditionals and comments). The
last test keeps system macros out (`PATH_MAX`, `SIGPIPE`: a system header defines them, but the repo's code
uses them). Underscore-led names (compiler and platform predefines) and a few well-known externally set
names are never decided. Everything else stays unknown: both sides of the branch are kept, as before.

Stdlib only; linear regexes over bounded lines.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Never decided: set by the compiler, the platform or the user's command line, not by the repo's files.
_EXTERNAL_NAMES = frozenset(
    {"unix", "linux", "i386", "WIN32", "WIN64", "NDEBUG", "DEBUG", "EMSCRIPTEN", "ANDROID", "MSDOS", "DJGPP"}
)
_DEFINE_RE = re.compile(r"^[ \t]*#[ \t]*(?:define|undef)[ \t]+([A-Za-z_]\w*)", re.M)
_COND_RE = re.compile(r"^[ \t]*#[ \t]*(?:if|ifdef|ifndef|elif|elifdef|elifndef)\b([^\n]*)", re.M)
# A directive other than `#define` (whose body is code) and a whole-line `//` comment: not code.
_NOT_CODE_RE = re.compile(r"^[ \t]*(?:#[ \t]*(?!define\b)|//)[^\n]*$", re.M)
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_COMMAND_LINE_DEFINE_RE = re.compile(r"[-/]D[ \t]*([A-Za-z_]\w*)")  # `-DX`, `/DX`: the token pass reads it as `DX`
# More C-family text than this and the scan decides nothing: the token pass is not worth its time.
MAX_TEXT_BYTES = 64_000_000


def unset_toggles(c_texts: Iterable[str], build_texts: Iterable[str]) -> frozenset[str]:
    """The names tested by a conditional that nothing in the scan defines, names or uses as code."""
    candidates: set[str] = set()
    blocked: set[str] = set()
    total = 0
    for text in c_texts:
        total += len(text)
        if total > MAX_TEXT_BYTES:
            return frozenset()
        if "#" not in text:
            blocked.update(_IDENT_RE.findall(text))
            continue
        blocked.update(_DEFINE_RE.findall(text))
        for cond in _COND_RE.findall(text):
            candidates.update(_IDENT_RE.findall(cond))
        blocked.update(_IDENT_RE.findall(_NOT_CODE_RE.sub("", text)))
    for text in build_texts:
        blocked.update(_IDENT_RE.findall(text))
        blocked.update(_COMMAND_LINE_DEFINE_RE.findall(text))
    candidates.discard("defined")
    return frozenset(n for n in candidates if n not in blocked and not n.startswith("_") and n not in _EXTERNAL_NAMES)


_TOKEN_RE = re.compile(
    r"\s*(?:(\|\||&&)|(!)(?!=)|([()])|(defined)\b|([A-Za-z_]\w*)|(0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]{0,3}|(\S))"
)


def toggle_condition_value(text: str, unset: frozenset[str]) -> bool | None:
    """Three-valued value of a `#if` / `#elif` condition over `defined(X)`, `!`, `&&`, `||`, parens, integer
    literals and bare names; None (unknown) for anything else. A name in `unset` is not defined and reads 0."""
    tokens: list[tuple[str, str]] = []
    for m in _TOKEN_RE.finditer(text):
        kind = m.lastindex
        if kind is None:
            return None
        if kind == 7:  # any other punctuation: a comparison, arithmetic, `?:`
            return None
        tokens.append((str(kind), m.group(kind)))
    if not tokens or len(tokens) > 200:
        return None
    pos = 0

    def peek() -> tuple[str, str] | None:
        return tokens[pos] if pos < len(tokens) else None

    class _Unknown(Exception):
        pass

    def atom() -> bool | None:
        nonlocal pos
        tok = peek()
        if tok is None:
            raise _Unknown
        pos += 1
        kind, val = tok
        if kind == "3" and val == "(":
            inner = parse_or()
            close = peek()
            if close != ("3", ")"):
                raise _Unknown
            pos += 1
            return inner
        if kind == "4":  # defined X / defined(X)
            nxt = peek()
            paren = nxt == ("3", "(")
            if paren:
                pos += 1
            name = peek()
            if name is None or name[0] != "5":
                raise _Unknown
            pos += 1
            if paren:
                if peek() != ("3", ")"):
                    raise _Unknown
                pos += 1
            return False if name[1] in unset else None
        if kind == "5":
            if val in ("true", "false"):
                return val == "true"
            if val in unset:
                # a function-like use `X(1)` is not a plain name
                if peek() == ("3", "("):
                    raise _Unknown
                return False
            raise _Unknown
        if kind == "6":
            digits = val[2:] if val[:2] in ("0x", "0X") else val
            return digits.strip("0") != ""
        raise _Unknown

    def parse_not() -> bool | None:
        nonlocal pos
        if peek() == ("2", "!"):
            pos += 1
            v = parse_not()
            return None if v is None else not v
        return atom()

    def parse_and() -> bool | None:
        nonlocal pos
        vals = [parse_not()]
        while peek() == ("1", "&&"):
            pos += 1
            vals.append(parse_not())
        if False in vals:
            return False
        return None if None in vals else True

    def parse_or() -> bool | None:
        nonlocal pos
        vals = [parse_and()]
        while peek() == ("1", "||"):
            pos += 1
            vals.append(parse_and())
        if True in vals:
            return True
        return None if None in vals else False

    try:
        value = parse_or()
    except _Unknown:
        return None
    return value if pos == len(tokens) else None
