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
from gitgalaxy.core.return_types import extract_whole_call_chain

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

LANGS = frozenset({"csharp", "kotlin", "cpp"})
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
    if lang == "cpp":
        t = re.sub(r"\b(?:const|volatile|struct|class|enum|typename)\b", " ", t)
        t = re.sub(r"<[^<>]{0,400}>", "", t)
        t = re.sub(r"<[^<>]{0,400}>", "", t)
        ptr = "*" in t
        t = t.replace("*", "").replace("&", "").replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
        base = t.rsplit("::", 1)[-1]
        if not base or not re.fullmatch(r"\w+", base):
            return ""
        base = _CPP_ALIASES.get(base, base)
        return base + ("*" if ptr else "")
    t = re.sub(r"<[^<>]{0,400}>", "", t)
    if lang == "cpp":
        t = re.sub(r"\b(?:const|volatile|struct|class|enum|typename)\b", " ", t)
        t = re.sub(r"<[^<>]{0,400}>", "", t)
        t = re.sub(r"<[^<>]{0,400}>", "", t)
        ptr = "*" in t
        t = t.replace("*", "").replace("&", "").replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
        base = t.rsplit("::", 1)[-1]
        if not base or not re.fullmatch(r"\w+", base):
            return ""
        base = _CPP_ALIASES.get(base, base)
        return base + ("*" if ptr else "")
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


_KT_FOR = re.compile(r"\bfor[ \t]*\([ \t]*(?:\([^)]{0,120}\)|(?P<n>" + _IDENT + r"))[ \t]+in\b")


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
    if lang == "cpp":
        for m in _CPP_DECL.finditer(text):
            name, typ = m.group("n"), m.group("t")
            if name in _CPP_DECL_STOP or typ in _CPP_DECL_STOP:
                continue
            _note(found, name, normalize(typ + (m.group("ptr") or ""), lang) or None)
        for m in _CPP_AUTO.finditer(text):
            typ = arg_type(_initializer(text, m.end()), {}, {}, lang)
            _note(found, m.group("n"), typ if typ and typ != "nullptr" else None)
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
    for m in _KT_FOR.finditer(text):
        if m.group("n"):
            _note(found, m.group("n"), None)
    return found


_KT_PROPERTY = re.compile(r"\b(?:val|var)[ \t]++(?P<n>" + _IDENT + r")[ \t]*+:[ \t]*+" + _KT_TYPE + r"(?![\w.<])")

_CPP_ALIASES = {
    "int8_t": "char",
    "uint8_t": "unsigned",
    "int16_t": "short",
    "uint16_t": "unsigned",
    "int32_t": "int",
    "uint32_t": "unsigned",
    "int64_t": "long",
    "uint64_t": "unsigned",
    "intptr_t": "long",
    "uintptr_t": "unsigned",
    "ptrdiff_t": "long",
    "ssize_t": "long",
}
_CPP_PRIMS = frozenset({"bool", "char", "short", "int", "unsigned", "long", "size_t", "float", "double"})
_CPP_TYPE = (
    r"(?:(?:const|volatile|struct|class|typename)[ \t]+){0,3}"
    r"(?P<t>(?:[A-Za-z_]\w{0,63}::){0,8}[A-Za-z_]\w{0,127})"
    r"(?:[ \t]*<[^;=(){}]{0,200}?>)?"
    r"(?:[ \t]*\bconst\b)?"
    r"(?P<ptr>(?:[ \t]*[*&]){0,2})"
)
_CPP_DECL = re.compile(r"(?<![\w.:])" + _CPP_TYPE + r"[ \t\r\n]+(?P<n>" + _IDENT + r")[ \t\r\n]*(?=[=;,:)])")
_CPP_AUTO = re.compile(r"\b(?:const[ \t]+)?auto(?:[ \t]*[*&]){0,2}[ \t]+(?P<n>" + _IDENT + r")[ \t]*=(?!=)[ \t]*")
_CPP_DECL_STOP = frozenset(
    {"return", "new", "delete", "throw", "else", "case", "sizeof", "alignof", "decltype", "auto", "using", "typedef"}
)
_CPP_PARAM = re.compile(
    r"[ \t\r\n]*" + _CPP_TYPE + r"(?:[ \t\r\n]+(?P<n>" + _IDENT + r"))?(?:[ \t]*\[[^\]\n]{0,40}\])?[ \t\r\n]*"
)


def field_value_types(field_text: str, file_text: str, lang: str) -> dict[str, str | None]:
    """The file's field / property types: C# and C++ from member declarations (`field_text`, bodies blanked);
    Kotlin from every `val` / `var` with a declared type (a primary constructor's included), across the file."""
    if lang in ("csharp", "cpp"):
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
    if lang == "cpp":
        if a[0] == '"' or a.startswith(('u"', 'U"', 'L"', 'u8"', 'R"')):
            return "char*"
        if a[0] == "'" and len(a) >= 3 and a.endswith("'"):
            return "char"
        if a in ("true", "false"):
            return "bool"
        if a in ("nullptr", "NULL"):
            return "nullptr"
        if _CS_INT.fullmatch(a):
            return "int"
        m = _CS_SUFFIXED.fullmatch(a)
        if m:
            s = m.group("s").lower()
            return "unsigned" if "u" in s else "long"
        m = _REAL.fullmatch(a)
        if m and ("." in a or "e" in a.lower() or m.group("s")):
            return "float" if m.group("s").lower() == "f" else "double"
        return None
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


def arg_type(
    arg: str, local: dict[str, str | None], fields: dict[str, str | None], lang: str, *, allow_call_chain: bool = False
) -> str:
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
    if allow_call_chain and lang in ("kotlin", "csharp") and a.endswith(")"):
        chain = extract_whole_call_chain(a)
        if chain:
            return "@" + chain
    return ""


def site_arg_types(
    text: str, callee_end: int, local: dict[str, str | None], fields: dict[str, str | None], lang: str
) -> list[str] | None:
    """The argument types of the call whose name ends at `callee_end` ("" for an unknown one; a named argument is
    encoded as `label=Type` or `label=` when its value type is unknown); None when no argument list is read.
    A Kotlin trailing lambda is one more argument of type "" (a function value)."""
    spans = call_args(text, callee_end)
    if spans is None:
        return None
    out = []
    for lo, hi in spans:
        a = text[lo:hi].strip()
        named = (
            re.match(r"(?P<l>" + _IDENT + r")[ \t]*+=(?!=)", a)
            if lang == "kotlin"
            else (re.match(r"(?P<l>" + _IDENT + r")[ \t]*+:(?!:)", a) if lang == "csharp" else None)
        )
        if named is not None:
            rhs = a[named.end() :].strip()
            val_t = (
                ""
                if rhs.startswith("*") or rhs.startswith(("out ", "ref ", "in "))
                else arg_type(rhs, local, fields, lang, allow_call_chain=True)
            )
            out.append(f"{named.group('l')}={val_t}")
        elif a.startswith("*") or a.startswith(("out ", "ref ", "in ")):
            out.append("")
        else:
            out.append(arg_type(a, local, fields, lang, allow_call_chain=True))
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
        if lang == "cpp":
            if p.strip() == "void":
                continue
            if p.strip() == "...":
                variadic = True
                continue
            if "..." in re.sub(r"<[^<>]*>", "", p):
                is_variadic = True
                p = re.sub(r"\.\.\.(?![^<]*>)", " ", p)
            pm = _CPP_PARAM.fullmatch(p.strip())
            typ = normalize(pm.group("t") + (pm.group("ptr") or ""), lang) if pm else ""
        elif lang == "csharp":
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


def param_names(text: str, header_end: int | None, lang: str) -> list[str] | None:
    """Declared parameter names for a Kotlin or C# unit header (for named-argument overload matching)."""
    if lang not in ("kotlin", "csharp") or header_end is None or header_end > 4000:
        return None
    spans = call_args(text, header_end)
    if spans is None:
        return None
    names: list[str] = []
    for i, (lo, hi) in enumerate(spans):
        raw = text[lo:hi]
        p = _ANNOTATION.sub(" ", raw) if lang == "kotlin" else _ATTRIBUTE.sub(" ", raw)
        if i == 0 and lang == "csharp" and re.match(r"[ \t\r\n]*+this\b", p):
            continue
        p, _ = _split_default(p)
        p = (_CS_MODIFIERS if lang == "csharp" else _KT_MODIFIERS).sub(" ", p).strip()
        pm = (_CS_PARAM if lang == "csharp" else _KT_PARAM).fullmatch(p)
        if pm is None:
            return None
        names.append(pm.group("n"))
    return names


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


_CPP_STRING_TYPES = frozenset({"string", "string_view", "basic_string_view", "format_string", "basic_format_string"})


def _cpp_compat(param: str, arg: str, subtype: Subtype | None) -> bool | None:
    if not arg:
        return True if _is_type_var(param) else None
    if param == arg:
        return True
    if arg == "nullptr":
        return param.endswith("*")
    if _is_type_var(param):
        return None if _is_type_var(arg) else True
    if _is_type_var(arg):
        return None
    if arg == "char*":
        if param in _CPP_STRING_TYPES or param in ("char*", "void*", "bool"):
            return True if param != "bool" else None
        if param in _CPP_PRIMS or param.endswith("*"):
            return False
        return None
    if arg in _CPP_PRIMS:
        if param in _CPP_PRIMS:
            if param in ("double", "float") and arg in ("int", "long", "unsigned", "short", "char", "float"):
                return True
            if param in ("int", "long", "unsigned", "size_t") and arg in ("bool", "char", "short", "int"):
                return True
            return None
        if param.endswith("*") or param in _CPP_STRING_TYPES:
            return False
        return None
    if param.endswith("*") and arg.endswith("*"):
        if param == "void*":
            return True
        if subtype is not None:
            return subtype(arg[:-1], param[:-1])
        return None
    if param.endswith("*") != arg.endswith("*"):
        return False if (param in _CPP_PRIMS or arg in _CPP_PRIMS) else None
    if subtype is not None:
        return subtype(arg, param)
    return None


def _compat(param: str, arg: str, lang: str, subtype: Subtype | None) -> bool | None:
    if not param:
        return None
    if lang == "cpp":
        return _cpp_compat(param, arg, subtype)
    if not arg or arg.startswith("@"):
        return None
    return _cs_literal_compat(param, arg, subtype) if lang == "csharp" else _kt_compat(param, arg, subtype)


def _more_specific(a: list[str], b: list[str], lang: str, subtype: Subtype | None) -> bool:
    """Every parameter of `a` converts to `b`'s: `a` is at least as specific (the better function member)."""
    return all(_compat(pb, pa, lang, subtype) is True for pa, pb in zip(a, b, strict=True))


def _expand(params: list[str], n: int, variadic: bool, lang: str = "") -> list[str] | None:
    """`params` as `n` argument slots: a trailing `params T[]` / `vararg T` in its expanded form takes `T` for
    every extra argument; a C++ variadic pack (`T&&... args`) takes its element type for 0+ trailing args.
    None when it cannot take `n`."""
    if len(params) == n:
        return params
    if not variadic or not params or n < len(params) - 1:
        return None
    if lang == "cpp":
        return params[:-1] + [params[-1]] * (n - len(params) + 1)
    if not params[-1].endswith("[]"):
        return None
    return params[:-1] + [params[-1][:-2]] * (n - len(params) + 1)


def choose(
    candidates: list[tuple[list[str], bool] | None],
    args: list[str],
    lang: str,
    subtype: Subtype | None = None,
    fewest: list[int] | None = None,
    param_names: list[list[str] | None] | None = None,
) -> int | None:
    """The index of the one candidate (its parameter types, whether its last is a `params` / `vararg` array) the
    language picks for these argument types, or None when the scan cannot be certain: all arguments unknown, an
    unknown parameter list, 2+ still-possible candidates with an uncertain argument, no applicable one, or no
    single best one. Supports partial-argument elimination and Kotlin/C# named arguments (`label=Type`)."""
    if not args or any(c is None for c in candidates):
        return None
    if not any(args):
        return None

    has_named = any("=" in a for a in args)
    if has_named:
        verdicts: dict[int, list[bool | None]] = {}
        for k, c in enumerate(candidates):
            assert c is not None  # noqa: S101 -- narrowed above
            c_params, variadic = c
            lo = fewest[k] if fewest is not None else len(c_params)
            if len(args) < lo or (len(args) > len(c_params) and not variadic):
                continue
            c_names = param_names[k] if param_names is not None and k < len(param_names) else None
            if c_names is None or len(c_names) != len(c_params):
                verdicts[k] = [None]
                continue
            v_list: list[bool | None] = []
            seen_named = False
            for pos_i, a in enumerate(args):
                if "=" in a:
                    seen_named = True
                    label, val_t = a.split("=", 1)
                    if label not in c_names:
                        v_list.append(False)
                        break
                    p_idx = c_names.index(label)
                    v_list.append(True)  # parameter name matched this overload
                    if val_t:
                        v_list.append(_compat(c_params[p_idx], val_t, lang, subtype))
                elif not seen_named:
                    if pos_i < len(c_params):
                        p_t = c_params[pos_i]
                        if variadic and pos_i == len(c_params) - 1 and p_t.endswith("[]") and len(args) > len(c_params):
                            p_t = p_t[:-2]
                        v_list.append(_compat(p_t, a, lang, subtype))
                    elif variadic and c_params and c_params[-1].endswith("[]"):
                        v_list.append(_compat(c_params[-1][:-2], a, lang, subtype))
                    else:
                        v_list.append(False)
                        break
                else:
                    v_list.append(None)
            verdicts[k] = v_list
        possible = [k for k, v in verdicts.items() if False not in v]
        if len(possible) == 1:
            return possible[0] if any(x is True for x in verdicts[possible[0]]) else None
        if not possible or any(None in verdicts[k] for k in possible):
            return None
        return None

    slots: list[list[str] | None] = []
    for k, c in enumerate(candidates):
        assert c is not None  # noqa: S101 -- narrowed above
        params, variadic = c
        lo = fewest[k] if fewest is not None else len(params)
        if lo <= len(args) < len(params) and not variadic:
            slots.append(params[: len(args)])  # the rest take their defaults
        else:
            slots.append(_expand(params, len(args), variadic, lang))
    live = [k for k, s in enumerate(slots) if s is not None]
    if not live:
        return None

    def as_written(ks: list[int]) -> list[int]:
        """Equally good: the one taking the arguments as written (no default filled, no `params` expanded)."""
        if len(ks) < 2:
            return ks
        return [k for k in ks if len(candidates[k][0]) == len(args) and slots[k] == candidates[k][0]]  # type: ignore[index]

    if all(args):
        exact = as_written([k for k in live if slots[k] == args])
        if len(exact) == 1:
            return exact[0]
    verdicts = {k: [_compat(p, a, lang, subtype) for p, a in zip(slots[k], args, strict=True)] for k in live}  # type: ignore[arg-type]
    possible = [k for k, v in verdicts.items() if False not in v]
    if len(possible) == 1:
        return possible[0] if any(x is True for x in verdicts[possible[0]]) else None
    if not possible or any(None in verdicts[k] for k in possible):
        return None
    applicable = [k for k in possible if all(x is True for x in verdicts[k])]
    best = as_written(
        [k for k in applicable if all(o == k or _more_specific(slots[k], slots[o], lang, subtype) for o in applicable)]  # type: ignore[arg-type]
    )
    return best[0] if len(best) == 1 else None


# ------------------------------------------------------------------------------ receiver types (X3)
_KT_BODY_OPEN = re.compile(
    r"\b(?:fun[ \t]+(?:<[^()]{0,200}>[ \t]+)?(?:[A-Za-z_]\w{0,63}(?:<[^()]{0,200}>)?\??\.){0,4}"
    r"[A-Za-z_]\w{0,127}[ \t]*\(|constructor[ \t]*\(|init[ \t]*\{|(?:get|set)[ \t]*\()"
)
_KT_CLASS_OPEN = re.compile(
    r"\b(?:class|interface|object)[ \t]+(?:" + _IDENT + r"[ \t]*)?(?:<[^()]{0,200}>)?[^{;\n]{0,300}\{"
)
_KT_COLLECTIONS = (
    r"(?:List|MutableList|Set|MutableSet|Collection|MutableCollection|Iterable|MutableIterable|Sequence|Array)"
)
_KT_COLL_DECL = re.compile(
    r"(?<![\w.@$])(?P<n>" + _IDENT + r")[ \t]*+:[ \t]*+" + _KT_COLLECTIONS + r"[ \t]*+<[ \t]*+"
    r"(?P<e>(?:[a-z]\w{0,63}\.){0,8}[A-Z]\w{0,127}(?:\.[A-Z]\w{0,127}){0,4})\??[ \t]*+>"
)
_KT_COLL_FACTORY = re.compile(
    r"\b(?:val|var)[ \t]++(?P<n>" + _IDENT + r")[ \t]*+=[ \t]*+"
    r"(?:mutableListOf|listOf|mutableSetOf|setOf|emptyList|emptySet|arrayListOf|linkedSetOf)"
    r"[ \t]*+<[ \t]*+(?P<e>(?:[a-z]\w{0,63}\.){0,8}[A-Z]\w{0,127}(?:\.[A-Z]\w{0,127}){0,4})\??[ \t]*+>[ \t]*+\("
)
_KT_FOR_IN = re.compile(r"\bfor[ \t]*+\([ \t]*+(?P<n>" + _IDENT + r")[ \t]++in[ \t]++(?P<c>" + _IDENT + r")\b")
_KT_ELEM_HOFS = frozenset(
    {
        "map",
        "mapNotNull",
        "flatMap",
        "forEach",
        "filter",
        "filterNot",
        "any",
        "all",
        "none",
        "first",
        "firstOrNull",
        "last",
        "lastOrNull",
        "single",
        "singleOrNull",
        "find",
        "count",
        "sortedBy",
        "sortedByDescending",
        "groupBy",
        "associateBy",
        "onEach",
        "indexOfFirst",
        "indexOfLast",
        "partition",
        "takeWhile",
        "dropWhile",
    }
)
_KT_SCOPE_IT_HOFS = frozenset({"let", "also"})
_KT_HOF_CALL = re.compile(
    r"(?P<r>(?:" + _IDENT + r"\??\.)?" + _IDENT + r")[ \t]*+\??\.[ \t]*+(?P<h>" + _IDENT + r")[ \t]*+\{"
)


def _brace_closes(text: str) -> dict[int, int]:
    out: dict[int, int] = {}
    stack: list[int] = []
    for k, ch in enumerate(text):
        if ch == "{":
            stack.append(k)
        elif ch == "}" and stack:
            out[stack.pop()] = k + 1
    return out


def _close_paren(text: str, start: int, limit: int = 2000) -> int:
    if start < 0 or start >= len(text) or text[start] != "(":
        return -1
    depth = 0
    for k in range(start, min(len(text), start + limit)):
        ch = text[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return k + 1
    return -1


def _blank_kotlin_fn_bodies(file_text: str) -> str:
    """Blank Kotlin function/constructor/init/accessor bodies while preserving class bodies and primary constructors."""
    closes = _brace_closes(file_text)
    out = list(file_text)

    def _blank(lo: int, hi: int) -> None:
        for k in range(lo, hi):
            if out[k] != "\n":
                out[k] = " "

    pos = 0
    n = len(file_text)
    while True:
        m = _KT_BODY_OPEN.search(file_text, pos)
        if m is None:
            break
        if file_text[m.end() - 1] == "{":
            brace = m.end() - 1
            end = closes.get(brace, -1)
            if end > brace:
                _blank(brace + 1, end - 1)
                pos = end
                continue
            pos = m.end()
            continue
        p_end = _close_paren(file_text, m.end() - 1)
        if p_end < 0:
            pos = m.end()
            continue
        # Scan past return type / where clause / delegating ctor call up to `{` or `=`
        k = p_end
        limit = min(n, p_end + 400)
        angle = 0
        paren = 0
        found_body = False
        while k < limit:
            ch = file_text[k]
            if ch == "<":
                angle += 1
            elif ch == ">" and angle > 0:
                angle -= 1
            elif ch == "(":
                paren += 1
            elif ch == ")" and paren > 0:
                paren -= 1
            elif angle == 0 and paren == 0:
                if ch == "{":
                    end = closes.get(k, -1)
                    if end > k:
                        _blank(k + 1, end - 1)
                        pos = end
                        found_body = True
                    break
                if ch == "=":
                    # Expression body: blank to newline or through matching `{...}` on the same expression
                    j = k + 1
                    eq_limit = min(n, k + 300)
                    while j < eq_limit and file_text[j] not in "\n{;":
                        j += 1
                    if j < n and file_text[j] == "{":
                        end = closes.get(j, -1)
                        if end > j:
                            _blank(k + 1, end)
                            pos = end
                            found_body = True
                            break
                    _blank(k + 1, j)
                    pos = j
                    found_body = True
                    break
                if ch == ";":
                    break
            k += 1
        if not found_body:
            pos = p_end
    return "".join(out)


class KotlinFileIndex:
    """Precomputed blanked Kotlin file text + class/object brace spans (built once per file)."""

    __slots__ = ("_scope_cache", "blanked", "class_spans", "top_level")

    def __init__(self, file_text: str) -> None:
        self._scope_cache: dict[int, str] = {}
        self.blanked = _blank_kotlin_fn_bodies(file_text)
        closes = _brace_closes(self.blanked)
        spans: list[tuple[int, int, int]] = []
        for m in _KT_CLASS_OPEN.finditer(self.blanked):
            brace = m.end() - 1
            end = closes.get(brace, -1)
            if end > brace:
                spans.append((m.start(), brace, end))
        self.class_spans = tuple(spans)
        # Precompute top-level property text (all class bodies blanked) once
        if spans:
            out = list(self.blanked)
            for _, b, e in spans:
                for k in range(b + 1, e - 1):
                    if out[k] != "\n":
                        out[k] = " "
            self.top_level = "".join(out)
        else:
            self.top_level = self.blanked


def index_kotlin_file(file_text: str) -> KotlinFileIndex:
    """Build a `KotlinFileIndex` once per file for O(1) per-function enclosing-class property lookup."""
    return KotlinFileIndex(file_text)


def kotlin_enclosing_field_text(file_or_index: str | KotlinFileIndex, unit_start: int) -> str:
    """Return Kotlin class/top-level property text scoped to the innermost class enclosing `unit_start`.

    Function bodies and nested sibling/inner class bodies are blanked so `FunSpec` and `FunSpec.Builder`
    never leak properties into each other.
    """
    idx = file_or_index if isinstance(file_or_index, KotlinFileIndex) else KotlinFileIndex(file_or_index)
    enclosing = [s for s in idx.class_spans if s[1] <= unit_start < s[2]]
    if not enclosing:
        return idx.top_level
    # Innermost enclosing class (cached per class span)
    h_start, b_open, b_close = max(enclosing, key=lambda s: s[1])
    cached = idx._scope_cache.get(b_open)
    if cached is not None:
        return cached
    segment = list(idx.blanked[h_start:b_close])
    # Blank any nested class/object bodies inside this enclosing class
    for _, nb, ne in idx.class_spans:
        if b_open < nb and ne <= b_close:
            for k in range(nb - h_start + 1, ne - h_start - 1):
                if segment[k] != "\n":
                    segment[k] = " "
    res = "".join(segment)
    idx._scope_cache[b_open] = res
    return res


def _qual_outer_inner(raw_t: str) -> str:
    """Return `Outer.Inner` if `raw_t` ends with two uppercase-led segments, else `""`."""
    if "." not in raw_t:
        return ""
    parts = raw_t.split(".")
    if len(parts) >= 2 and parts[-2][:1].isupper() and parts[-1][:1].isupper():
        return f"{parts[-2]}.{parts[-1]}"
    return ""


def _kotlin_collection_elements(text: str) -> dict[str, str | None]:
    """Extract `{name: ElemType}` for Kotlin `List<T>` / `MutableList<T>` / `mutableListOf<T>()` declarations."""
    found: dict[str, str | None] = {}
    for pat in (_KT_COLL_DECL, _KT_COLL_FACTORY):
        for m in pat.finditer(text):
            raw_e = m.group("e")
            elem = _qual_outer_inner(raw_e) or normalize(raw_e, "kotlin")
            _note(found, m.group("n"), elem or None)
    return found


def receiver_types(
    text: str,
    receivers: set[str],
    fields: dict[str, str | None] | None,
    lang: str,
    kt_field_text: str | None = None,
) -> dict[str, str]:
    """#8161 (X3 for C# / Kotlin): receiver -> its declared class (`JsonWriter writer`, `val b: Builder`,
    `var w = new JTokenWriter()`), for the receivers in `receivers` (one unit's masked `text`).

    The unit's own declarations win; `this.x` is the field, and a bare name the unit does not declare is a field
    too (both languages have an implicit `this`). A primitive, an array, a nullable value type, or a name bound
    with no single known type maps to "", which hides any other answer for it."""
    local = declared_value_types(text, lang)
    # Preserve `Outer.Inner` nested class types (e.g. `builder: TypeSpec.Builder`) for receiver typing
    # so `call_resolver` can scope `Inner` to `Outer`'s file without disturbing overload-type normalization.
    qualified: dict[str, str] = {}
    if lang == "kotlin":
        for m in _KT_DECL.finditer(text):
            qname = _qual_outer_inner(m.group("t"))
            if qname:
                n = m.group("n")
                if n in qualified and qualified[n] != qname:
                    qualified[n] = ""
                else:
                    qualified.setdefault(n, qname)
    elif lang == "csharp":
        for m in _CS_DECL.finditer(text):
            n, raw_t = m.group("n"), m.group("t")
            if n in _CS_DECL_STOP or raw_t in _CS_DECL_STOP or m.group("dims"):
                continue
            qname = _qual_outer_inner(raw_t.replace("global::", ""))
            if qname:
                if n in qualified and qualified[n] != qname:
                    qualified[n] = ""
                else:
                    qualified.setdefault(n, qname)

    field_qualified: dict[str, str] = {}
    if lang == "kotlin":
        field_map: dict[str, str | None] = {}
        if kt_field_text:
            for m in _KT_PROPERTY.finditer(kt_field_text):
                n = m.group("n")
                _note(field_map, n, normalize(m.group("t") + (m.group("null") or ""), lang) or None)
                qname = _qual_outer_inner(m.group("t"))
                if qname:
                    if n in field_qualified and field_qualified[n] != qname:
                        field_qualified[n] = ""
                    else:
                        field_qualified.setdefault(n, qname)
            for m in _KT_VAL.finditer(kt_field_text):
                n = m.group("n")
                typ = arg_type(_initializer(kt_field_text, m.end()), {}, {}, lang)
                if typ and typ != "null":
                    _note(field_map, n, typ)
                elif n in field_map:
                    field_map[n] = None
    else:
        field_map = fields or {}

    # Kotlin `for (x in coll)` and lambda `it` element typing from declared collections
    if lang == "kotlin":
        colls: dict[str, str | None] = _kotlin_collection_elements(kt_field_text) if kt_field_text else {}
        colls.update(_kotlin_collection_elements(text))
        for m in _KT_FOR_IN.finditer(text):
            elem_name, coll_name = m.group("n"), m.group("c")
            elem_type = colls.get(coll_name)
            if elem_type and local.get(elem_name) is None:
                local[elem_name] = elem_type
                if "." in elem_type:
                    qualified[elem_name] = elem_type
        if "it" in receivers and "it" not in local:
            it_found: dict[str, str | None] = {}
            for m in _KT_HOF_CALL.finditer(text):
                hof = m.group("h")
                recv = m.group("r").replace("?.", ".")
                if hof in _KT_ELEM_HOFS:
                    base = recv.rsplit(".", 1)[-1]
                    _note(it_found, "it", colls.get(base))
                elif hof in _KT_SCOPE_IT_HOFS:
                    base = recv[5:] if recv.startswith("this.") else recv
                    if "." not in base:
                        t = qualified.get(base) or local.get(base) or field_qualified.get(base) or field_map.get(base)
                        _note(it_found, "it", t.rstrip("?") if t else None)
                    else:
                        _note(it_found, "it", None)
            if it_found.get("it"):
                it_t = it_found["it"]
                assert it_t is not None  # noqa: S101
                local["it"] = it_t
                if "." in it_t:
                    qualified["it"] = it_t

    out: dict[str, str] = {}
    scopes: tuple[dict[str, str | None], ...]
    for r in receivers:
        if r.startswith("this."):
            name, scopes = r[5:], (field_map,)
        else:
            name, scopes = r, (local, field_map)
        if not name or "." in name or not re.fullmatch(_IDENT, name):
            continue
        for scope in scopes:
            if name in scope:
                typ = (scope[name] or "").rstrip("?")
                if typ and scope is local and qualified.get(name):
                    typ = qualified[name]
                elif typ and scope is field_map and field_qualified.get(name):
                    typ = field_qualified[name]
                out[r] = "" if not typ or typ.endswith("[]") or typ in CS_PRIMITIVES else typ
                break
    return out
