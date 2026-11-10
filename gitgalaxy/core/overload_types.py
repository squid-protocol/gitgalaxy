# ==============================================================================
# GitGalaxy Core: C# and Kotlin overload choice by argument type (#8161, PR 5)
#
# PURPOSE:
# The C# and Kotlin port of J1 (java_arg_types.py). Same-named overloads in one
# class or file (`WriteValue(int)` / `WriteValue(decimal?)`, `addModifiers(vararg
# KModifier)` / `addModifiers(Iterable<KModifier>)`) were linked to an arbitrary one:
# 577 of C#'s 623 and 88 of Kotlin's 98 wrong confident links on the LAWS survey
# repos. The detector records each call site's argument types and each unit's
# declared parameter types (and the counts it accepts: defaults, `params`,
# `vararg`); the call resolver picks the overload the language picks, and only
# when certain (every argument typed, every candidate's parameters read, no
# candidate only maybe applicable). Anything else keeps the `overload` row.
#
# Types are leaf names with generics dropped (`System.Collections.Generic.List<int>`
# -> `List`), arrays as a `[]` suffix per dimension. C# keeps `?` only on a value
# type (`decimal?` is Nullable<decimal>; `string?` is an annotation) and spells
# the System aliases as keywords (`Int32` -> `int`); Kotlin keeps every `?`.
#
# The language rules the choice uses (and the ones it refuses to guess):
#   C#      identity, the implicit numeric conversions (C# spec 10.2.3), a value
#           type to its nullable, boxing to `object`; a reference argument to a
#           class it may convert to (a user-defined implicit operator, a repo
#           subtype the scan cannot see) is "maybe". An int literal to a narrower
#           integral parameter (a constant conversion) is "maybe" too.
#   Kotlin  no implicit numeric conversion: identity, `T` to `T?`, `null` only to
#           a nullable, anything to `Any` / `Any?`; an integer literal to `Long`,
#           `Short` or `Byte` (an integer literal takes the expected type) is "maybe".
# Every scan is linear: bounded or possessive quantifiers only.
# ==============================================================================
import re
from collections.abc import Callable

from gitgalaxy.core.java_arg_types import call_args, mask_literals, name_sites

__all__ = [
    "LANGS",
    "arg_type",
    "call_args",
    "choose",
    "declared_value_types",
    "field_value_types",
    "mask_literals",
    "name_sites",
    "param_types",
    "site_arg_types",
]

LANGS = frozenset({"csharp", "kotlin"})
Subtype = Callable[[str, str], bool | None]
_IDENT = r"[A-Za-z_][\w]{0,127}"

# ------------------------------------------------------------------------------ C# types
CS_PRIMITIVES = frozenset(
    {"bool", "byte", "sbyte", "char", "decimal", "double", "float", "int", "uint", "long", "ulong", "short", "ushort"}
    | {"nint", "nuint"}
)
_CS_ALIASES = {
    "Boolean": "bool",
    "Byte": "byte",
    "SByte": "sbyte",
    "Char": "char",
    "Decimal": "decimal",
    "Double": "double",
    "Single": "float",
    "Int32": "int",
    "UInt32": "uint",
    "Int64": "long",
    "UInt64": "ulong",
    "Int16": "short",
    "UInt16": "ushort",
    "IntPtr": "nint",
    "UIntPtr": "nuint",
    "String": "string",
    "Object": "object",
}
# value types whose `T?` is Nullable<T> (a struct of the repo is not known here: its `?` is dropped)
_CS_VALUE = CS_PRIMITIVES | {"DateTime", "DateTimeOffset", "TimeSpan", "Guid", "BigInteger", "Half", "Int128"}
# C# spec 10.2.3, implicit numeric conversions
_CS_WIDENS = {
    "sbyte": {"short", "int", "long", "float", "double", "decimal", "nint"},
    "byte": {"short", "ushort", "int", "uint", "long", "ulong", "float", "double", "decimal", "nint", "nuint"},
    "short": {"int", "long", "float", "double", "decimal", "nint"},
    "ushort": {"int", "uint", "long", "ulong", "float", "double", "decimal", "nint", "nuint"},
    "int": {"long", "float", "double", "decimal", "nint"},
    "uint": {"long", "ulong", "float", "double", "decimal", "nuint"},
    "long": {"float", "double", "decimal"},
    "ulong": {"float", "double", "decimal"},
    "char": {"ushort", "int", "uint", "long", "ulong", "float", "double", "decimal", "nint", "nuint"},
    "float": {"double"},
    "double": set(),
    "decimal": set(),
    "bool": set(),
    "nint": {"long", "float", "double", "decimal"},
    "nuint": {"ulong", "float", "double", "decimal"},
}
# what a primitive or a string converts to besides the above: boxing, and the interfaces they implement
_CS_PRIM_SUPERS = frozenset(
    {"object", "ValueType", "IComparable", "IConvertible", "IFormattable", "IEquatable", "ISpanFormattable"}
)
_CS_STRING_SUPERS = frozenset({"object", "IComparable", "IConvertible", "IEnumerable", "ICloneable", "IEquatable"})
_CS_NARROW_INTEGRALS = frozenset({"sbyte", "byte", "short", "ushort", "uint", "ulong", "char", "nuint"})

# ------------------------------------------------------------------------------ Kotlin types
KT_NUMBERS = frozenset({"Int", "Long", "Short", "Byte", "Double", "Float", "UInt", "ULong", "UShort", "UByte"})
_KT_FINAL = KT_NUMBERS | {"String", "Char", "Boolean", "Unit"}
_KT_SUPERS: dict[str, frozenset[str]] = {
    **dict.fromkeys(KT_NUMBERS, frozenset({"Any", "Number", "Comparable", "Serializable"})),
    "String": frozenset({"Any", "CharSequence", "Comparable", "Serializable"}),
    "Char": frozenset({"Any", "Comparable", "Serializable"}),
    "Boolean": frozenset({"Any", "Comparable", "Serializable"}),
    "Unit": frozenset({"Any"}),
}
_KT_LITERAL_TARGETS = frozenset({"Long", "Short", "Byte", "UInt", "ULong", "UShort", "UByte"})

# A type variable by convention (`T`, `E`, `K2`): its bound is not read, so it accepts nothing for certain.
_TYPE_VAR = re.compile(r"[A-Z][0-9]?\Z")


def normalize(written: str, lang: str) -> str:
    """A written type -> the leaf form (`global::System.Int32?` -> `int?`, `List<KModifier>` -> `List`); "" for a
    form this scan does not type (a Kotlin function type, a C# tuple)."""
    t = written.strip()
    if not t or t[0] == "(" or "->" in t:
        return ""
    t = re.sub(r"<[^<>]{0,400}>", "", t)
    t = re.sub(r"<[^<>]{0,400}>", "", t)  # one level of nesting
    t = t.replace("global::", "").replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
    nullable = t.endswith("?")
    t = t.rstrip("?")
    dims = len(re.findall(r"\[[,]*\]", t))
    base = re.sub(r"\[[,]*\]", "", t).rstrip("?")
    base = base.rsplit(".", 1)[-1]
    if not base or not re.fullmatch(r"\w+", base):
        return ""
    if lang == "csharp":
        base = _CS_ALIASES.get(base, base)
        keep = nullable and not dims and base in _CS_VALUE
    else:
        keep = nullable
    return base + "[]" * dims + ("?" if keep else "")


# ------------------------------------------------------------------------------ declared types
_CS_PRIM_ALT = "|".join(sorted(CS_PRIMITIVES | {"string", "object"}))
_CS_TYPE = (
    r"(?P<t>(?:" + _CS_PRIM_ALT + r")(?!\w)|(?:global::)?(?:[A-Za-z_]\w{0,63}\.){0,8}[A-Z]\w{0,127})"
    r"(?:[ \t]*+<[^;=(){}]{0,200}?>)?"
    r"(?P<null>[ \t]*+\?)?"
    r"(?P<dims>(?:[ \t]*+\[[ \t,]*+\])*+)"
)
_CS_DECL = re.compile(r"(?<![\w.])" + _CS_TYPE + r"[ \t\r\n]++(?P<n>" + _IDENT + r")[ \t\r\n]*+(?=[=;,:)]|in\b)")
_CS_VAR = re.compile(r"\bvar[ \t]++(?P<n>" + _IDENT + r")[ \t]*+(?P<eq>=(?!=)[ \t]*+)?")
_CS_LAMBDA_ONE = re.compile(r"(?<![\w.])(?P<n>" + _IDENT + r")[ \t]*+=>")
_CS_DECL_STOP = frozenset(
    {"return", "new", "is", "as", "in", "out", "ref", "case", "else", "await", "yield", "throw", "using", "goto"}
)
_KT_TYPE = (
    r"(?P<t>(?:[a-z]\w{0,63}\.){0,8}[A-Z]\w{0,127}(?:\.[A-Z]\w{0,127}){0,4})"
    r"(?:[ \t]*+<[^;=(){}]{0,200}?>)?"
    r"(?P<null>[ \t]*+\?)?"
)
_KT_DECL = re.compile(r"(?<![\w.@$])(?P<n>" + _IDENT + r")[ \t]*+:[ \t]*+" + _KT_TYPE + r"(?![\w.<])")
_KT_VAL = re.compile(r"\b(?:val|var)[ \t]++(?P<n>" + _IDENT + r")[ \t]*+=(?!=)[ \t]*+")
_KT_VARARG = re.compile(r"\bvararg[ \t]++(?P<n>" + _IDENT + r")")
_KT_LAMBDA = re.compile(r"\{[ \t\r\n]*+(?P<p>[\w, \t]{1,200})->")


def _note(found: dict[str, str | None], name: str, typ: str | None) -> None:
    if name in found and found[name] != typ:
        found[name] = None
    else:
        found.setdefault(name, typ)


def _initializer(text: str, start: int) -> str:
    """The expression after `=` at `start`, to the end of its statement (`;`, a newline at depth zero, `}`)."""
    depth, k, end = 0, start, min(len(text), start + 400)
    while k < end:
        ch = text[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and ch in ";\n":
            break
        k += 1
    return text[start:k]


def declared_value_types(text: str, lang: str) -> dict[str, str | None]:
    """Every variable `text` declares -> its type; None when the name is bound twice with different types, or
    with no type the scan reads (a lambda parameter, `var x = f()`, a Kotlin `vararg` parameter -- an array)."""
    found: dict[str, str | None] = {}
    if lang == "csharp":
        for m in _CS_DECL.finditer(text):
            name, typ = m.group("n"), m.group("t")
            if name in _CS_DECL_STOP or typ in _CS_DECL_STOP:
                continue
            _note(found, name, normalize(typ + (m.group("null") or "") + m.group("dims"), lang) or None)
        for m in _CS_VAR.finditer(text):
            typ = arg_type(_initializer(text, m.end()), {}, {}, lang) if m.group("eq") else ""
            _note(found, m.group("n"), typ if typ and typ != "null" else None)
        for m in _CS_LAMBDA_ONE.finditer(text):
            _note(found, m.group("n"), None)
        return found
    for m in _KT_DECL.finditer(text):
        _note(found, m.group("n"), normalize(m.group("t") + (m.group("null") or ""), lang) or None)
    for m in _KT_VAL.finditer(text):
        if m.group("n") in found:
            continue  # `val x: T = ..` is typed by its declaration
        typ = arg_type(_initializer(text, m.end()), {}, {}, lang)
        _note(found, m.group("n"), typ if typ and typ != "null" else None)
    for m in _KT_VARARG.finditer(text):
        found[m.group("n")] = None
    for m in _KT_LAMBDA.finditer(text):
        for part in m.group("p").split(","):
            if re.fullmatch(_IDENT, part.strip()):
                _note(found, part.strip(), None)
    return found


_KT_PROPERTY = re.compile(r"\b(?:val|var)[ \t]++(?P<n>" + _IDENT + r")[ \t]*+:[ \t]*+" + _KT_TYPE + r"(?![\w.<])")


def field_value_types(field_text: str, file_text: str, lang: str) -> dict[str, str | None]:
    """The file's field / property types: C# from its member declarations (`field_text`, bodies blanked); Kotlin
    from every `val` / `var` with a declared type (a primary constructor's included), across the file."""
    if lang == "csharp":
        return declared_value_types(field_text, lang)
    found: dict[str, str | None] = {}
    for m in _KT_PROPERTY.finditer(file_text):
        _note(found, m.group("n"), normalize(m.group("t") + (m.group("null") or ""), lang) or None)
    return found


# ------------------------------------------------------------------------------ argument types
_CS_INT = re.compile(r"-?(?:0[xX][0-9a-fA-F_]{1,40}|0[bB][01_]{1,80}|[0-9][0-9_]{0,40})")
_CS_SUFFIXED = re.compile(
    r"-?(?:0[xX][0-9a-fA-F_]{1,40}|0[bB][01_]{1,80}|[0-9][0-9_]{0,40})(?P<s>[uU][lL]|[lL][uU]|[lL]|[uU])"
)
_REAL = re.compile(
    r"-?(?:[0-9][0-9_]{0,40}(?:\.[0-9][0-9_]{0,40})?(?:[eE][+-]?[0-9]{1,4})?|\.[0-9][0-9_]{0,40}(?:[eE][+-]?[0-9]{1,4})?)"
    r"(?P<s>[fFdDmM]?)"
)
_KT_INT = re.compile(r"-?(?:0[xX][0-9a-fA-F_]{1,40}|0[bB][01_]{1,80}|[0-9][0-9_]{0,40})(?P<s>[uU]?[lL]?)")
_CS_NEW = re.compile(
    r"new[ \t\r\n]++(?P<t>(?:global::)?(?:[A-Za-z_]\w{0,63}\.){0,8}(?:[A-Z]\w{0,127}|" + _CS_PRIM_ALT + r"))"
    r"[ \t\r\n]*+(?P<g><[^;=(){}]{0,200}?>)?[ \t\r\n]*+(?P<open>[(\[{])"
)
_CS_CAST = re.compile(
    r"\([ \t\r\n]*+(?P<t>(?:" + _CS_PRIM_ALT + r")(?!\w)|(?:[A-Za-z_]\w{0,63}\.){0,8}[A-Z]\w{0,127})"
    r"(?P<null>\??)(?P<dims>(?:[ \t]*+\[[ \t]*+\])*+)[ \t\r\n]*+\)[ \t\r\n]*+(?P<rest>[A-Za-z_][\w.]{0,200}|[0-9][\w.]{0,60})\Z"
)
_KT_CTOR = re.compile(r"(?P<t>(?:[a-z]\w{0,63}\.){0,8}[A-Z]\w{0,127})[ \t]*+(?:<[^;=(){}]{0,200}?>)?[ \t]*+\(")
_KT_AS = re.compile(r"(?P<e>.{1,300}?)[ \t]++as[ \t]++" + _KT_TYPE + r"\Z", re.S)
_KT_CLASS_REF = re.compile(r"(?P<t>[A-Z]\w{0,127})(?:<[^;=(){}]{0,100}>)?::class(?P<java>\.java)?\Z")
_NAME_FULL = re.compile(r"(?P<this>this\.)?(?P<n>" + _IDENT + r")\Z")
_OPEN = {"(": ")", "[": "]", "{": "}"}


def _closes_at_end(text: str, open_at: int) -> bool:
    opener = text[open_at]
    closer = _OPEN[opener]
    depth = 0
    for k in range(open_at, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                return text[k + 1 :].strip() == "" or (opener == "[" and text[k + 1 :].strip()[:1] in "[{")
    return False


def _literal(a: str, lang: str) -> str | None:
    """The type of a literal, "" for one this scan does not type, None when `a` is no literal."""
    if a[0] == '"' or a.startswith(('@"', '$"', '$@"', '@$"')):
        q = a.index('"')
        return "string" if lang == "csharp" else ("String" if a.endswith('"') and len(a) > q + 1 else "")
    if a[0] == "'":
        return ("char" if lang == "csharp" else "Char") if len(a) >= 3 and a.endswith("'") else ""
    if a in ("true", "false"):
        return "bool" if lang == "csharp" else "Boolean"
    if a == "null":
        return "null"
    if lang == "csharp":
        if _CS_INT.fullmatch(a):
            return "int"
        m = _CS_SUFFIXED.fullmatch(a)
        if m:
            s = m.group("s").lower()
            return {"l": "long", "u": "uint"}.get(s, "ulong")
        m = _REAL.fullmatch(a)
        if m and ("." in a or "e" in a.lower() or m.group("s")):
            return {"f": "float", "m": "decimal"}.get(m.group("s").lower(), "double")
        return None
    m = _KT_INT.fullmatch(a)
    if m:
        s = m.group("s").lower()
        return {"": "Int", "l": "Long", "u": "UInt", "ul": "ULong"}.get(s, "")
    m = _REAL.fullmatch(a)
    if m and m.group("s").lower() in ("", "f", "d") and ("." in a or "e" in a.lower() or m.group("s")):
        return "Float" if m.group("s").lower() == "f" else ("Double" if m.group("s").lower() != "d" else "")
    return None


def arg_type(arg: str, local: dict[str, str | None], fields: dict[str, str | None], lang: str) -> str:
    """The type of one argument expression (masked text), or "" when it is not certain."""
    a = arg.strip()
    if not a:
        return ""
    lit = _literal(a, lang)
    if lit is not None:
        return lit
    if lang == "csharp":
        m = _CS_NEW.match(a)
        if m is not None and _closes_at_end(a, m.start("open")):
            base = normalize(m.group("t"), lang)
            if m.group("open") == "(" or m.group("open") == "{":
                return base if base not in CS_PRIMITIVES else ""
            return base + "[]" * a[m.start("open") :].split("{", 1)[0].count("[")
        m = _CS_CAST.fullmatch(a)
        if m is not None:
            rest = m.group("rest")
            if rest.endswith(".") or ".." in rest:
                return ""
            return normalize(m.group("t") + m.group("null") + m.group("dims"), lang)
        if a.startswith("nameof(") and a.endswith(")"):
            return "string"
        if a.startswith("typeof(") and a.endswith(")") and _closes_at_end(a, 6):
            return "Type"
    else:
        m = _KT_CLASS_REF.fullmatch(a)
        if m is not None:
            return "Class" if m.group("java") else "KClass"
        m = _KT_CTOR.match(a)
        if m is not None and _closes_at_end(a, m.end() - 1):
            return normalize(m.group("t"), lang)
        m = _KT_AS.fullmatch(a)
        if m is not None:
            return normalize(m.group("t") + (m.group("null") or ""), lang)
    m = _NAME_FULL.fullmatch(a)
    if m is not None:
        scope = fields if m.group("this") else (local if m.group("n") in local else fields)
        return scope.get(m.group("n")) or ""
    return ""


def site_arg_types(
    text: str, callee_end: int, local: dict[str, str | None], fields: dict[str, str | None], lang: str
) -> list[str] | None:
    """The argument types of the call whose name ends at `callee_end` ("" for an unknown one; a named or spread
    argument is unknown); None when no argument list is read. A Kotlin trailing lambda is one more argument
    of type "" (a function value)."""
    spans = call_args(text, callee_end)
    if spans is None:
        return None
    out = []
    for lo, hi in spans:
        a = text[lo:hi].strip()
        named = lang == "kotlin" and re.match(_IDENT + r"[ \t]*+=(?!=)", a)
        named = named or (lang == "csharp" and re.match(_IDENT + r"[ \t]*+:(?!:)", a))
        if named or a.startswith("*") or a.startswith(("out ", "ref ", "in ")):
            out.append("")
        else:
            out.append(arg_type(a, local, fields, lang))
    if lang == "kotlin" and _trailing_lambda(text, callee_end):
        out.append("")
    return out


def _trailing_lambda(text: str, callee_end: int) -> bool:
    """`f(a) { .. }`: the call's `)` is followed by a lambda argument."""
    i = text.find("(", callee_end)
    if i < 0:
        return False
    depth = 0
    for k in range(i, min(len(text), i + 4000)):
        ch = text[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                rest = text[k + 1 : k + 200].lstrip(" \t")
                return rest.startswith("{")
    return False


# ------------------------------------------------------------------------------ parameter types
_ATTRIBUTE = re.compile(r"\[(?=[ \t]*+[A-Za-z_])[^\[\]]{0,300}\]")  # `[NotNull]`, never an array's `[]` / `[,]`
_ANNOTATION = re.compile(r"@[\w.:]{1,128}(?:[ \t\r\n]*+\([^()]{0,300}\))?")
_CS_MODIFIERS = re.compile(r"\b(?:this|ref|out|in|params|scoped|readonly)\b")
_KT_MODIFIERS = re.compile(r"\b(?:vararg|val|var|noinline|crossinline|override|private|public|internal|protected)\b")
_CS_PARAM = re.compile(r"(?P<t>.{1,300}?)[ \t\r\n]++(?P<n>" + _IDENT + r")", re.S)
_KT_PARAM = re.compile(r"(?P<n>" + _IDENT + r")[ \t\r\n]*+:[ \t\r\n]*+(?P<t>.{1,300})", re.S)


def _split_default(p: str) -> tuple[str, bool]:
    """`int x = 0` -> (`int x`, True): a parameter with a default value."""
    depth = 0
    for k, ch in enumerate(p):
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == "=" and depth <= 0 and p[k + 1 : k + 2] not in ("=", ">") and p[k - 1 : k] not in "!<>=":
            return p[:k], True
    return p, False


def param_types(text: str, header_end: int | None, lang: str) -> tuple[list[str], tuple[int, int | None, int]] | None:
    """(declared parameter types, (fewest arguments, most -- None for `params` / `vararg` --, the count)) of the
    unit whose header name ends at `header_end` in `text` (masked); None when unread. A `params` array or a
    Kotlin `vararg` parameter is typed as its element array (`object[]`, `KModifier[]`). A C# extension method's
    `this` receiver is not counted: it is called as `receiver.M(the others)`."""
    if header_end is None or header_end > 4000:
        return None
    spans = call_args(text, header_end)
    if spans is None:
        return None
    out: list[str] = []
    fewest, variadic = 0, False
    for i, (lo, hi) in enumerate(spans):
        raw = text[lo:hi]
        p = _ANNOTATION.sub(" ", raw) if lang == "kotlin" else _ATTRIBUTE.sub(" ", raw)
        if i == 0 and lang == "csharp" and re.match(r"[ \t\r\n]*+this\b", p):
            continue  # an extension method's receiver: `s.FormatWith(a, b)` passes the others only
        p, has_default = _split_default(p)
        is_variadic = bool(re.search(r"\bparams\b" if lang == "csharp" else r"\bvararg\b", p))
        p = (_CS_MODIFIERS if lang == "csharp" else _KT_MODIFIERS).sub(" ", p).strip()
        if lang == "csharp":
            pm = _CS_PARAM.fullmatch(p)
            typ = normalize(pm.group("t"), lang) if pm else ""
        else:
            pm = _KT_PARAM.fullmatch(p)
            typ = normalize(pm.group("t"), lang) if pm else ""
            if typ and is_variadic:
                typ += "[]"
        if pm is None:
            return None
        out.append(typ)
        variadic = variadic or is_variadic
        if not has_default and not is_variadic:
            fewest = len(out)
    count = len(out)
    return out, (fewest, None if variadic else count, count)


# ------------------------------------------------------------------------------ applicability
def _is_type_var(t: str) -> bool:
    return bool(_TYPE_VAR.match(t.rstrip("?").replace("[]", "")))


def _cs_compat(param: str, arg: str, subtype: Subtype | None) -> bool | None:
    if param == arg:
        return True
    if arg == "null":
        return param not in CS_PRIMITIVES  # a nullable or a reference type takes null
    if _is_type_var(param) or _is_type_var(arg):
        return None
    p_null, a_null = param.endswith("?"), arg.endswith("?")
    p, a = param.rstrip("?"), arg.rstrip("?")
    if a_null and not p_null:
        # Nullable<T> boxes to object; it never converts to a non-nullable value type
        if p in ("object", "ValueType"):
            return True
        return False if p in _CS_VALUE else None
    if a in CS_PRIMITIVES:
        if p in CS_PRIMITIVES:
            return p == a or p in _CS_WIDENS[a]
        if p in _CS_PRIM_SUPERS:
            return not p_null or p == "object"
        if p == "string":
            return False
        return None  # a user-defined implicit operator (JToken's from int) may apply
    if a == "string":
        if p in CS_PRIMITIVES:
            return False
        if p in _CS_STRING_SUPERS:
            return True
        return None
    if a.endswith("[]"):
        if p.endswith("[]"):
            pe, ae = p[:-2], a[:-2]
            if pe in CS_PRIMITIVES or ae in CS_PRIMITIVES:
                return pe == ae
            return _cs_compat(pe, ae, subtype)
        return True if p in ("object", "Array") else None
    if p in CS_PRIMITIVES or p == "string":
        return None  # a repo class's implicit operator to it
    if p == "object":
        return True
    if subtype is not None:
        return subtype(a, p)
    return None


def _cs_literal_compat(param: str, arg: str, subtype: Subtype | None) -> bool | None:
    """An int literal converts to a narrower integral parameter when its value fits (a constant conversion)."""
    verdict = _cs_compat(param, arg, subtype)
    if verdict is False and arg == "int" and param.rstrip("?") in _CS_NARROW_INTEGRALS:
        return None
    return verdict


def _kt_compat(param: str, arg: str, subtype: Subtype | None) -> bool | None:
    if param == arg:
        return True
    if param in ("Any?",):
        return True
    if arg == "null":
        return param.endswith("?")
    if _is_type_var(param) or _is_type_var(arg):
        return None
    p_null, a_null = param.endswith("?"), arg.endswith("?")
    if a_null and not p_null:
        return False  # a nullable never passes where a non-null type is declared
    p, a = param.rstrip("?"), arg.rstrip("?")
    if p == a or p == "Any":
        return True
    if a == "Int" and p in _KT_LITERAL_TARGETS:
        return None  # an integer literal takes the expected type
    if a in _KT_FINAL:
        return p in _KT_SUPERS.get(a, frozenset())
    if p in _KT_FINAL:
        return False  # nothing subclasses a final class
    if a.endswith("[]") or p.endswith("[]"):
        return None
    if subtype is not None:
        return subtype(a, p)
    return None


def _compat(param: str, arg: str, lang: str, subtype: Subtype | None) -> bool | None:
    if not param:
        return None
    return _cs_literal_compat(param, arg, subtype) if lang == "csharp" else _kt_compat(param, arg, subtype)


def _more_specific(a: list[str], b: list[str], lang: str, subtype: Subtype | None) -> bool:
    """Every parameter of `a` converts to `b`'s: `a` is at least as specific (the better function member)."""
    return all(_compat(pb, pa, lang, subtype) is True for pa, pb in zip(a, b, strict=True))


def _expand(params: list[str], n: int, variadic: bool) -> list[str] | None:
    """`params` as `n` argument slots: a trailing `params T[]` / `vararg T` in its expanded form takes `T` for
    every extra argument. None when it cannot take `n`."""
    if len(params) == n:
        return params
    if not variadic or not params or not params[-1].endswith("[]") or n < len(params) - 1:
        return None
    return params[:-1] + [params[-1][:-2]] * (n - len(params) + 1)


def choose(
    candidates: list[tuple[list[str], bool] | None],
    args: list[str],
    lang: str,
    subtype: Subtype | None = None,
    fewest: list[int] | None = None,
) -> int | None:
    """The index of the one candidate (its parameter types, whether its last is a `params` / `vararg` array) the
    language picks for these argument types, or None when the scan cannot be certain: an unknown argument or
    parameter list, a maybe-applicable candidate, no applicable one, or no single best one. A candidate whose
    defaults fill the parameters after `args` (`fewest[k] <= len(args)`) is matched on its first parameters."""
    if not args or any(not a for a in args) or any(c is None for c in candidates):
        return None
    slots: list[list[str] | None] = []
    for k, c in enumerate(candidates):
        assert c is not None  # noqa: S101 -- narrowed above
        params, variadic = c
        lo = fewest[k] if fewest is not None else len(params)
        if lo <= len(args) < len(params) and not variadic:
            slots.append(params[: len(args)])  # the rest take their defaults
        else:
            slots.append(_expand(params, len(args), variadic))
    live = [k for k, s in enumerate(slots) if s is not None]
    if not live:
        return None

    def as_written(ks: list[int]) -> list[int]:
        """Equally good: the one taking the arguments as written (no default filled, no `params` expanded)."""
        if len(ks) < 2:
            return ks
        return [k for k in ks if len(candidates[k][0]) == len(args) and slots[k] == candidates[k][0]]  # type: ignore[index]

    exact = as_written([k for k in live if slots[k] == args])
    if len(exact) == 1:
        return exact[0]
    verdicts = {k: [_compat(p, a, lang, subtype) for p, a in zip(slots[k], args, strict=True)] for k in live}  # type: ignore[arg-type]
    if any(None in v and False not in v for v in verdicts.values()):
        return None
    applicable = [k for k, v in verdicts.items() if all(x is True for x in v)]
    best = as_written(
        [k for k in applicable if all(o == k or _more_specific(slots[k], slots[o], lang, subtype) for o in applicable)]  # type: ignore[arg-type]
    )
    return best[0] if len(best) == 1 else None


# ------------------------------------------------------------------------------ receiver types (X3)
def receiver_types(text: str, receivers: set[str], fields: dict[str, str | None] | None, lang: str) -> dict[str, str]:
    """#8161 (X3 for C# / Kotlin): receiver -> its declared class (`JsonWriter writer`, `val b: Builder`,
    `var w = new JTokenWriter()`), for the receivers in `receivers` (one unit's masked `text`).

    The unit's own declarations win; `this.x` is the field, and a bare name the unit does not declare is a field
    too (both languages have an implicit `this`). A primitive, an array, a nullable value type, or a name bound
    with no single known type maps to "", which hides any other answer for it."""
    local = declared_value_types(text, lang)
    out: dict[str, str] = {}
    scopes: tuple[dict[str, str | None], ...]
    for r in receivers:
        if r.startswith("this."):
            name, scopes = r[5:], (fields or {},)
        else:
            name, scopes = r, (local, fields or {})
        if not name or "." in name or not re.fullmatch(_IDENT, name):
            continue
        for scope in scopes:
            if name in scope:
                typ = (scope[name] or "").rstrip("?")
                out[r] = "" if not typ or typ.endswith("[]") or typ in CS_PRIMITIVES else typ
                break
    return out
