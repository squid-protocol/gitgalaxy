# ==============================================================================
# GitGalaxy Core: Java overload choice by argument type (#8161, J1)
#
# PURPOSE:
# Java overloads of one arity (`indexOf(int[], int)` / `indexOf(long[], long)`)
# were an ambiguous `overload` row, never an edge (#3835 chooses by argument
# count only). The detector now records, per call site, a coarse type for each
# argument, and per method its declared parameter types; the call resolver
# picks the overload Java's own rules pick (JLS 15.12.2: strict and loose
# invocation, then the most specific method) -- but only when the answer is
# certain:
#   - every argument has a known type (a literal, a typed local / parameter /
#     field, `new T(..)`, a cast of a plain operand, `xs.length`);
#   - every candidate's parameter types were read;
#   - no candidate is "maybe" applicable (two reference types whose subtyping
#     the scan cannot see). Anything else leaves the row as it was.
# Types are leaf names with generics dropped (`java.util.List<String>` ->
# `List`), arrays as a `[]` suffix per dimension, varargs as an array.
# The text is the unit's own source with every literal blanked to the same
# length, quotes kept (`mask_literals`): the engine's literal shield shortens a
# literal to `""`, which loses `'c'` (char) against `"c"` (String).
# Every scan is linear: bounded or possessive quantifiers only.
# ==============================================================================
import re
from collections.abc import Callable, Iterator

PRIMITIVES = frozenset({"byte", "short", "char", "int", "long", "float", "double", "boolean"})
_BOXES = {
    "Byte": "byte",
    "Short": "short",
    "Character": "char",
    "Integer": "int",
    "Long": "long",
    "Float": "float",
    "Double": "double",
    "Boolean": "boolean",
}
_UNBOX = {v: k for k, v in _BOXES.items()}
# JLS 5.1.2 widening primitive conversions
_WIDENS = {
    "byte": {"short", "int", "long", "float", "double"},
    "short": {"int", "long", "float", "double"},
    "char": {"int", "long", "float", "double"},
    "int": {"long", "float", "double"},
    "long": {"float", "double"},
    "float": {"double"},
    "double": set(),
    "boolean": set(),
}
_NUMBER_SUPERS = frozenset({"Number", "Comparable", "Serializable", "Object", "Constable", "ConstantDesc"})
# Every supertype of a few final JDK classes: none of them has a subclass, so a parameter not listed is
# definitely not applicable to an argument of that class.
_FINAL_SUPERS: dict[str, frozenset[str]] = {
    "String": frozenset({"CharSequence", "Comparable", "Serializable", "Object", "Constable", "ConstantDesc"}),
    "StringBuilder": frozenset({"CharSequence", "Appendable", "Serializable", "Object", "Comparable"}),
    "StringBuffer": frozenset({"CharSequence", "Appendable", "Serializable", "Object", "Comparable"}),
    "Boolean": frozenset({"Comparable", "Serializable", "Object", "Constable"}),
    "Character": frozenset({"Comparable", "Serializable", "Object", "Constable"}),
    **dict.fromkeys(("Byte", "Short", "Integer", "Long", "Float", "Double"), _NUMBER_SUPERS),
}
_ARRAY_SUPERS = frozenset({"Object", "Cloneable", "Serializable"})
# A type variable by convention (`T`, `E`, `K2`): its bound is not read, so it accepts nothing for certain.
_TYPE_VAR = re.compile(r"[A-Z][0-9]?\Z")

Subtype = Callable[[str, str], bool | None]


# ------------------------------------------------------------------------------ masking
_LEXEME = re.compile(r"[/\"']")


def mask_literals(text: str) -> str:
    """`text` with every comment and literal's contents blanked, same length, newlines and quotes kept."""
    out = list(text)
    n = len(text)
    i = 0

    def blank(lo: int, hi: int) -> None:
        for k in range(lo, hi):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        hit = _LEXEME.search(text, i)
        if hit is None:
            break
        i = hit.start()
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            blank(i + 3, max(i + 3, j - 3))
            i = j
        elif ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j, n)
            blank(i + 1, j)
            i = j + 1
        else:
            i += 1  # a lone `/`
    return "".join(out)


# ------------------------------------------------------------------------------ declared types
_IDENT = r"[A-Za-z_$][\w$]{0,127}"
_PRIM_ALT = "|".join(sorted(PRIMITIVES))
# a written type: a primitive, or an upper-case class (`java.util.Map.Entry` allowed), optionally generic,
# then array dimensions or varargs
_TYPE = (
    r"(?P<t>(?:" + _PRIM_ALT + r")(?![\w$])|(?:[a-z][\w$]{0,63}\.){0,8}[A-Z][\w$]{0,127}(?:\.[A-Z][\w$]{0,127}){0,4})"
    r"(?:[ \t]*+<[^;=(){}]{0,200}?>)?"
    r"(?P<dims>(?:[ \t]*+\[[ \t]*+\])*+|[ \t]*+\.\.\.)"
)
_DECL = re.compile(r"(?<![\w$.])(?=[A-Za-z_$])" + _TYPE + r"[ \t\r\n]*+(?P<n>" + _IDENT + r")[ \t\r\n]*+(?=[=;,:)])")
_VAR = re.compile(r"\bvar[ \t]++(?P<n>" + _IDENT + r")[ \t]*+(?P<eq>=[ \t]*+)?")
_NEW = re.compile(
    r"new[ \t]++(?P<t>(?:[a-z][\w$]{0,63}\.){0,8}[A-Z][\w$]{0,127}(?:\.[A-Z][\w$]{0,127}){0,4})[ \t]*+[<(]"
)
_LAMBDA_ONE = re.compile(r"(?<![\w$.])(?P<n>" + _IDENT + r")[ \t]*+->")
_LAMBDA_LIST = re.compile(r"\((?P<p>[^()]{0,300})\)[ \t]*+->")
_NAME = re.compile(_IDENT)
_DECL_STOP = frozenset({"extends", "implements", "super", "instanceof", "throws", "default", "new", "return"})


def normalize(written: str) -> str:
    """`final java.util.List<String> ...` -> `List[]`-style leaf form."""
    t = re.sub(r"<[^<>]{0,400}>", "", written)
    t = re.sub(r"<[^<>]{0,400}>", "", t)  # one level of nesting
    t = t.replace("...", "[]").replace(" ", "").replace("\t", "")
    dims = t.count("[]")
    base = t.replace("[]", "")
    return base.rsplit(".", 1)[-1] + "[]" * dims


def _note(found: dict[str, str | None], name: str, typ: str | None) -> None:
    if name in found and found[name] != typ:
        found[name] = None
    else:
        found.setdefault(name, typ)


def declared_value_types(text: str) -> dict[str, str | None]:
    """Every variable `text` declares -> its type (primitives and arrays included); None when the name is bound
    twice with different types, or with no type the scan reads (`var x = f()`, a lambda parameter, a
    multi-catch)."""
    found: dict[str, str | None] = {}
    for m in _DECL.finditer(text):
        name = m.group("n")
        if name in _DECL_STOP or m.group("t") in _DECL_STOP:
            continue
        j = m.start() - 1
        while j >= 0 and text[j] in " \t\r\n":
            j -= 1
        if j >= 0 and text[j] == "|":  # `catch (A | B e)`: e is either
            _note(found, name, None)
            continue
        _note(found, name, normalize(m.group("t") + m.group("dims")))
    for m in _VAR.finditer(text):
        typ = None
        if m.group("eq"):
            nm = _NEW.match(text, m.end())
            if nm is not None:
                typ = normalize(nm.group("t"))
        _note(found, m.group("n"), typ)
    for m in _LAMBDA_ONE.finditer(text):
        _note(found, m.group("n"), None)
    for m in _LAMBDA_LIST.finditer(text):
        for part in m.group("p").split(","):
            words = part.split()
            if len(words) == 1 and _NAME.fullmatch(words[0]):
                _note(found, words[0], None)
    return found


# ------------------------------------------------------------------------------ call sites and arguments
_OPEN = {"(": ")", "[": "]", "{": "}"}
_MAX_SCAN = 4000


def call_args(text: str, pos: int) -> list[tuple[int, int]] | None:
    """The (start, end) spans of the arguments of the call whose callee name ends at `pos`; None when no
    argument list follows or it does not close within a bound. Commas count at depth zero of `()`, `[]`, `{}`
    and outside a `<..>` generic argument list (an `<` after an identifier whose `>` closes before the call's
    own `)`), like detector._call_arity."""
    n = len(text)
    i = pos
    while i < n and text[i] in " \t\r\n":
        i += 1
    if i < n and text[i] == "<":
        depth, j = 0, i
        while j < n and j - i < 400:
            depth += {"<": 1, ">": -1}.get(text[j], 0)
            j += 1
            if depth == 0:
                break
        if depth:
            return None
        i = j
        while i < n and text[i] in " \t\r\n":
            i += 1
    if i >= n or text[i] != "(":
        return None
    end = min(n, i + _MAX_SCAN)
    close = -1
    stack: list[str] = []
    commas: list[int] = []
    j = i + 1
    while j < end:
        ch = text[j]
        if ch in _OPEN:
            stack.append(_OPEN[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch == ")" and not stack:
            close = j
            break
        elif ch == "," and not stack:
            commas.append(j)
        elif ch == "<" and not stack and j > 0 and (text[j - 1].isalnum() or text[j - 1] in "_$"):
            k, depth = j, 0
            while k < end and k - j < 400:
                c2 = text[k]
                if c2 == "<":
                    depth += 1
                elif c2 == ">":
                    depth -= 1
                    if depth == 0:
                        break
                elif c2 in ";{}()":
                    break
                k += 1
            if depth == 0 and k < end and text[k] == ">":
                j = k
        j += 1
    if close < 0:
        return None
    if not text[i + 1 : close].strip():
        return []
    bounds = [i, *commas, close]
    return [(bounds[k] + 1, bounds[k + 1]) for k in range(len(bounds) - 1)]


_INT = re.compile(r"-?(?:0[xX][0-9a-fA-F_]{1,40}|0[bB][01_]{1,80}|[0-9][0-9_]{0,40})")
_LONG = re.compile(r"-?(?:0[xX][0-9a-fA-F_]{1,40}|0[bB][01_]{1,80}|[0-9][0-9_]{0,40})[lL]")
_FLOAT = re.compile(r"-?(?:[0-9][0-9_]{0,40}(?:\.[0-9_]{0,40})?|\.[0-9][0-9_]{0,40})(?:[eE][+-]?[0-9]{1,4})?[fF]")
_DOUBLE = re.compile(
    r"-?(?:[0-9][0-9_]{0,40}\.[0-9_]{0,40}(?:[eE][+-]?[0-9]{1,4})?|\.[0-9][0-9_]{0,40}(?:[eE][+-]?[0-9]{1,4})?"
    r"|[0-9][0-9_]{0,40}[eE][+-]?[0-9]{1,4}|(?:[0-9][0-9_]{0,40}(?:\.[0-9_]{0,40})?|\.[0-9]{1,40})[dD])"
)
_NEW_ARG = re.compile(
    r"new[ \t\r\n]++(?P<t>(?:[a-z][\w$]{0,63}\.){0,8}(?:[A-Z][\w$]{0,127}(?:\.[A-Z][\w$]{0,127}){0,4}|"
    + _PRIM_ALT
    + r"))[ \t\r\n]*+(?P<g><[^;=(){}]{0,200}?>)?[ \t\r\n]*+(?P<open>[(\[])"
)
_CAST = re.compile(
    r"\([ \t\r\n]*+(?P<t>(?:" + _PRIM_ALT + r")(?![\w$])|(?:[a-z][\w$]{0,63}\.){0,8}[A-Z][\w$]{0,127})"
    r"(?P<dims>(?:[ \t]*+\[[ \t]*+\])*+)[ \t\r\n]*+\)[ \t\r\n]*+(?P<rest>[A-Za-z_$][\w$.]{0,200}|[0-9][\w.]{0,60})\Z"
)
_NAME_FULL = re.compile(r"(?P<this>this\.)?(?P<n>" + _IDENT + r")\Z")
_LENGTH = re.compile(r"(?P<n>" + _IDENT + r")\.length\Z")


def _closes_at_end(text: str, open_at: int) -> bool:
    """Whether the bracket at `open_at` closes exactly at the end of `text` (nothing follows the expression)."""
    opener = text[open_at]
    closer = _OPEN[opener]
    depth = 0
    for k in range(open_at, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                rest = text[k + 1 :].strip()
                if opener == "[":  # `new int[3][4]`, `new String[] { .. }`
                    return rest == "" or rest[0] in "[{"
                return rest == ""
    return False


def arg_type(arg: str, local: dict[str, str | None], fields: dict[str, str | None]) -> str:
    """The type of one argument expression (masked text), or "" when it is not certain."""
    a = arg.strip()
    if not a:
        return ""
    if a[0] == '"':
        return "String" if len(a) >= 2 and a.endswith('"') and '"' not in a[1:-1] else ""
    if a[0] == "'":
        return "char" if len(a) >= 2 and a.endswith("'") and "'" not in a[1:-1] else ""
    if a in ("true", "false"):
        return "boolean"
    if a == "null":
        return "null"
    if _LONG.fullmatch(a):
        return "long"
    if _INT.fullmatch(a):
        return "int"
    if _FLOAT.fullmatch(a):
        return "float"
    if _DOUBLE.fullmatch(a):
        return "double"
    m = _NEW_ARG.match(a)
    if m is not None and m.start() == 0 and _closes_at_end(a, m.start("open")):
        base = normalize(m.group("t"))
        if m.group("open") == "(":
            return base if base not in PRIMITIVES else ""
        dims = re.findall(r"\[", a[m.start("open") :].split("{", 1)[0])
        return base + "[]" * len(dims)
    m = _CAST.fullmatch(a)
    if m is not None:
        rest = m.group("rest")
        if rest.endswith(".") or ".." in rest:
            return ""
        return normalize(m.group("t") + m.group("dims"))
    m = _NAME_FULL.fullmatch(a)
    if m is not None:
        scope = fields if m.group("this") else (local if m.group("n") in local else fields)
        return scope.get(m.group("n")) or ""
    m = _LENGTH.fullmatch(a)
    if m is not None:
        n = m.group("n")
        typ = local.get(n) if n in local else fields.get(n)
        return "int" if typ and typ.endswith("[]") else ""
    return ""


def site_arg_types(
    text: str, callee_end: int, local: dict[str, str | None], fields: dict[str, str | None]
) -> list[str] | None:
    """The argument types of the call whose name ends at `callee_end` ("" for an unknown one); None when no
    argument list is read."""
    spans = call_args(text, callee_end)
    if spans is None:
        return None
    return [arg_type(text[lo:hi], local, fields) for lo, hi in spans]


_CALL_NAME = re.compile(r"(?<![\w$])[A-Za-z_$][\w$]{0,127}(?![\w$])(?=[ \t\r\n]*+[<(])")


def call_sites(text: str, callee: str) -> Iterator[int]:
    """The end offsets of every `callee` written as a call name (`callee(` or `callee<..>(`)."""
    yield from name_sites(text).get(callee, ())


def name_sites(text: str) -> dict[str, list[int]]:
    """Every name written before `(` or `<` -> the end offsets where it is, in one pass."""
    out: dict[str, list[int]] = {}
    for m in _CALL_NAME.finditer(text):
        out.setdefault(m.group(), []).append(m.end())
    return out


# ------------------------------------------------------------------------------ parameter types
_PARAM = re.compile(r"(?P<t>.{1,300}?)[ \t\r\n]++(?P<n>" + _IDENT + r")(?P<cdims>(?:[ \t]*+\[[ \t]*+\])*+)", re.S)
_ANNOTATION = re.compile(r"@[\w$.]{1,128}(?:[ \t\r\n]*+\([^()]{0,300}\))?")
_FINAL = re.compile(r"\bfinal\b")


def param_types(text: str, header_end: int | None) -> list[str] | None:
    """The declared parameter types of the unit whose header name ends at `header_end` in `text` (masked);
    None when unread."""
    if header_end is None or header_end > 4000:
        return None
    spans = call_args(text, header_end)
    if spans is None:
        return None
    out: list[str] = []
    for lo, hi in spans:
        p = _FINAL.sub(" ", _ANNOTATION.sub(" ", text[lo:hi])).strip()
        pm = _PARAM.fullmatch(p)
        if pm is None:
            return None
        out.append(normalize(pm.group("t")) + "[]" * pm.group("cdims").count("["))
    return out


# ------------------------------------------------------------------------------ applicability (JLS 15.12.2)
def _is_type_var(t: str) -> bool:
    return bool(_TYPE_VAR.match(t.replace("[]", "")))


def _compat(param: str, arg: str, loose: bool, subtype: Subtype | None) -> bool | None:
    """Is an argument of type `arg` applicable to `param`? True / False / None (cannot tell).

    `loose` adds boxing and unboxing (JLS 5.3 loose invocation); strict allows identity and widening only.
    """
    if param == arg:
        return True
    if arg == "null":
        return param not in PRIMITIVES
    if _is_type_var(param) or _is_type_var(arg):
        if arg in PRIMITIVES:
            return None if loose else False
        return None
    p_arr, a_arr = param.endswith("[]"), arg.endswith("[]")
    if arg in PRIMITIVES:
        if param in PRIMITIVES:
            return param in _WIDENS[arg]
        if not loose:
            return False
        box = _UNBOX[arg]
        return param == box or param in _FINAL_SUPERS[box]
    if param in PRIMITIVES:
        if not loose or arg not in _BOXES:
            return False  # only a box unboxes
        prim = _BOXES[arg]
        return param == prim or param in _WIDENS[prim]
    if a_arr:
        if not p_arr:
            return param in _ARRAY_SUPERS
        pe, ae = param[:-2], arg[:-2]
        if pe in PRIMITIVES or ae in PRIMITIVES:
            return pe == ae
        return _compat(pe, ae, False, subtype)
    if p_arr:
        return False
    if param == "Object":
        return True
    if param in _FINAL_SUPERS:  # nothing subclasses a final class
        return False
    if arg in _FINAL_SUPERS:
        return param in _FINAL_SUPERS[arg]
    if subtype is not None:
        return subtype(arg, param)
    return None


def _more_specific(a: list[str], b: list[str], subtype: Subtype | None) -> bool:
    """Every parameter of `a` is applicable to `b`'s by strict invocation (JLS 15.12.2.5)."""
    return all(_compat(pb, pa, False, subtype) is True for pa, pb in zip(a, b, strict=True))


def choose(candidates: list[list[str] | None], args: list[str], subtype: Subtype | None = None) -> int | None:
    """The index of the one overload (same arity as `args`) Java picks for these argument types, or None
    when the scan cannot be certain: an unknown argument or parameter list, a maybe-applicable candidate,
    no applicable one, or no single most specific one."""
    if not args or any(not a for a in args) or any(c is None or len(c) != len(args) for c in candidates):
        return None
    params = [c for c in candidates if c is not None]
    exact = [k for k, c in enumerate(params) if c == args]
    if len(exact) == 1:
        return exact[0]
    for loose in (False, True):
        verdicts = [[_compat(p, a, loose, subtype) for p, a in zip(c, args, strict=True)] for c in params]
        if any(None in v and False not in v for v in verdicts):
            return None
        applicable = [k for k, v in enumerate(verdicts) if all(x is True for x in v)]
        if not applicable:
            continue
        best = [
            k
            for k in applicable
            if all(o == k or _more_specific(params[k], params[o], subtype) for o in applicable)
            and not any(o != k and _more_specific(params[o], params[k], subtype) for o in applicable)
        ]
        return best[0] if len(best) == 1 else None
    return None
