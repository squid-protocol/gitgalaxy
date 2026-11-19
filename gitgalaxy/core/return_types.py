# ==============================================================================
# GitGalaxy Core: Cross-function Return Types & Chained Receiver Extraction
#
# PURPOSE:
# `receiver_types.py` and `detector.py` type local variables within a single
# function (`x = Store()`, `x: Store`). Calls on factory results (`x = get_store()`)
# and chained calls (`get_store().save()`, `svc.store().save()`) fell back to
# the ambiguous `receiver` step or `<expr>`. This module extracts:
#   1. Declared return types on function/method headers (`return_type`), so
#      `call_resolver.py` can propagate types across function boundaries.
#   2. Call-expression receiver chains (`extract_expr_chain`) when
#      `_call_qualifier` encounters `)`, without altering `calls_out_qualifiers`.
#
# All scans are bounded/linear on literal-shielded text.
# ==============================================================================
import re

_IDENT = r"[A-Za-z_]\w{0,127}"

_PRIMITIVES = frozenset(
    {
        "none",
        "None",
        "null",
        "nil",
        "undefined",
        "void",
        "unit",
        "Unit",
        "Nothing",
        "never",
        "any",
        "Any",
        "unknown",
        "object",
        "Object",
        "auto",
        "var",
        "dynamic",
        "bool",
        "boolean",
        "Boolean",
        "int",
        "integer",
        "Integer",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "uintptr",
        "isize",
        "usize",
        "i8",
        "i16",
        "i32",
        "i64",
        "i128",
        "u8",
        "u16",
        "u32",
        "u64",
        "u128",
        "f32",
        "f64",
        "short",
        "Short",
        "long",
        "Long",
        "byte",
        "Byte",
        "sbyte",
        "char",
        "Char",
        "rune",
        "float",
        "Float",
        "double",
        "Double",
        "decimal",
        "number",
        "bigint",
        "symbol",
        "str",
        "string",
        "String",
        "bytes",
        "error",
        "size_t",
        "ssize_t",
        "ptrdiff_t",
        "NoReturn",
        "Never",
    }
)

_CONTAINERS = frozenset(
    {
        "list",
        "List",
        "MutableList",
        "ArrayList",
        "dict",
        "Dict",
        "map",
        "Map",
        "MutableMap",
        "HashMap",
        "BTreeMap",
        "set",
        "Set",
        "MutableSet",
        "HashSet",
        "frozenset",
        "tuple",
        "Tuple",
        "array",
        "Array",
        "Vec",
        "vector",
        "deque",
        "Sequence",
        "Mapping",
        "Iterable",
        "Iterator",
        "Generator",
        "Callable",
        "Coroutine",
        "Awaitable",
        "Promise",
        "Task",
        "ValueTask",
        "CompletableFuture",
        "Future",
        "IEnumerable",
        "IList",
        "ICollection",
        "IDictionary",
        "Collection",
        "Stream",
    }
)

_WRAPPERS = frozenset(
    {
        "Optional",
        "Result",
        "Option",
        "Box",
        "Arc",
        "Rc",
        "unique_ptr",
        "shared_ptr",
        "weak_ptr",
        "optional",
        "Nullable",
    }
)

_MODIFIERS = frozenset(
    {
        "public",
        "private",
        "protected",
        "internal",
        "static",
        "final",
        "abstract",
        "virtual",
        "override",
        "sealed",
        "extern",
        "inline",
        "constexpr",
        "consteval",
        "const",
        "volatile",
        "mutable",
        "async",
        "unsafe",
        "synchronized",
        "native",
        "strictfp",
        "explicit",
        "friend",
        "new",
        "partial",
        "readonly",
        "suspend",
        "infix",
        "operator",
        "tailrec",
    }
)


def _close_paren(text: str, start: int, limit: int = 3000) -> int:
    """Return index just past matching ')' for '(' at `start`, or -1."""
    if start < 0 or start >= len(text) or text[start] != "(":
        return -1
    depth = 0
    for i in range(start, min(len(text), start + limit)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _strip_outer_generics(raw: str) -> tuple[str, str | None]:
    """Return `(base, first_type_arg)` for `Base<Arg, ...>` or `Base[Arg, ...]`."""
    s = raw.strip()
    for open_ch, close_ch in (("<", ">"), ("[", "]")):
        idx = s.find(open_ch)
        if idx > 0 and s.endswith(close_ch):
            base = s[:idx].strip()
            inner = s[idx + 1 : -1].strip()
            # extract first top-level type argument
            depth = 0
            first_end = len(inner)
            for k, ch in enumerate(inner):
                if ch in "<[(":
                    depth += 1
                elif ch in ">])":
                    depth -= 1
                elif ch == "," and depth == 0:
                    first_end = k
                    break
            return base, inner[:first_end].strip()
    return s, None


def _normalize_type(raw: str, parent_class: str | None = None) -> str | None:
    """Normalize a return type annotation to a leaf class name, or None if primitive/container/ambiguous."""
    s = raw.strip()
    if not s:
        return None
    # Reject function types, slices, arrays, maps
    if s.startswith(("[]", "map[", "chan ", "func(", "(", "{")) or s.endswith("[]"):
        return None
    # Handle unions like `Foo | None` / `None | Foo` / `Foo | null | undefined`
    if "|" in s and "<" not in s and "[" not in s:
        parts = [p.strip() for p in s.split("|") if p.strip()]
        non_null = [p for p in parts if p not in ("None", "null", "undefined", "nil")]
        if len(non_null) == 1:
            s = non_null[0]
        else:
            return None
    # Strip C++/Rust/Go qualifiers & pointers/references/nullability
    s = s.rstrip("?&* \t")
    for prefix in ("const ", "mut ", "&mut ", "&", "*", "'static "):
        while s.startswith(prefix):
            s = s[len(prefix) :].strip()
    s = s.rstrip("?&* \t")
    if not s:
        return None

    base, inner = _strip_outer_generics(s)
    leaf_base = base.replace("::", ".").rsplit(".", 1)[-1].strip()
    if leaf_base in _WRAPPERS and inner:
        return _normalize_type(inner, parent_class)
    if leaf_base in _CONTAINERS or leaf_base in _PRIMITIVES:
        return None
    if leaf_base == "Self":
        return parent_class or None
    if not re.fullmatch(_IDENT, leaf_base):
        return None
    return leaf_base


_PY_HEADER = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+" + _IDENT + r"[ \t]*\(")
_TS_HEADER = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?(?:function[ \t]+\*?[ \t]*)?"
    r"(?:" + _IDENT + r"[ \t]*)?(?:<[^>()]{0,200}>)?[ \t]*\("
)
_GO_HEADER = re.compile(
    r"^[ \t]*func[ \t]*(?:\([^()]{0,300}\)[ \t]*)?" + _IDENT + r"[ \t]*(?:\[[^\]]{0,200}\])?[ \t]*\("
)
_RS_HEADER = re.compile(
    r"^[ \t]*(?:pub(?:\([^)]{0,60}\))?[ \t]+)?(?:async[ \t]+)?(?:unsafe[ \t]+)?(?:const[ \t]+)?fn[ \t]+"
    + _IDENT
    + r"[ \t]*(?:<[^()]{0,200}>)?[ \t]*\("
)
_KT_HEADER = re.compile(
    r"^[ \t]*(?:[a-z]+[ \t]+){0,6}fun[ \t]+(?:<[^()]{0,200}>[ \t]+)?(?:" + _IDENT + r"\.)?" + _IDENT + r"[ \t]*\("
)


def _extract_after_arrow(text: str, start: int, stop_chars: str) -> str | None:
    """Scan from `start` for `-> <type>` before any char in `stop_chars`."""
    tail = text[start : start + 400]
    m = re.match(r"[ \t]*->[ \t]*([^\n" + re.escape(stop_chars) + r"]{1,200})", tail)
    if not m:
        return None
    return m.group(1).strip()


def _extract_python(text: str, parent_class: str | None) -> str | None:
    m = _PY_HEADER.match(text)
    if not m:
        return None
    end = _close_paren(text, m.end() - 1)
    if end < 0:
        return None
    raw = _extract_after_arrow(text, end, ":")
    return _normalize_type(raw, parent_class) if raw else None


def _extract_ts(text: str, parent_class: str | None) -> str | None:
    m = _TS_HEADER.match(text)
    if not m:
        return None
    end = _close_paren(text, m.end() - 1)
    if end < 0:
        return None
    tail = text[end : end + 300]
    cm = re.match(r"[ \t]*:[ \t]*([^\n{;=]{1,200}?)[ \t]*(?:\{|=>|;|\n)", tail)
    if not cm:
        return None
    return _normalize_type(cm.group(1), parent_class)


def _extract_go(text: str, parent_class: str | None) -> str | None:
    m = _GO_HEADER.match(text)
    if not m:
        return None
    end = _close_paren(text, m.end() - 1)
    if end < 0:
        return None
    tail = text[end : end + 300]
    brace = tail.find("{")
    if brace < 0:
        brace = tail.find("\n")
    ret = tail[:brace].strip() if brace >= 0 else tail.strip()
    if not ret:
        return None
    if ret.startswith("(") and ret.endswith(")"):
        inner = ret[1:-1].strip()
        parts = [p.strip() for p in inner.split(",") if p.strip()]
        if len(parts) == 2 and parts[1] in ("error", "bool"):
            ret = parts[0]
        else:
            return None
    return _normalize_type(ret, parent_class)


def _extract_rust(text: str, parent_class: str | None) -> str | None:
    m = _RS_HEADER.match(text)
    if not m:
        return None
    end = _close_paren(text, m.end() - 1)
    if end < 0:
        return None
    tail = text[end : end + 400]
    rm = re.match(r"[ \t]*->[ \t]*([^\n{;]{1,200}?)(?:[ \t]+\bwhere\b|[ \t]*\{|[ \t]*;|\n)", tail)
    if not rm:
        return None
    return _normalize_type(rm.group(1), parent_class)


def _extract_kotlin(text: str, parent_class: str | None) -> str | None:
    cleaned = re.sub(r"^(?:[ \t]*@[A-Za-z_]\w*(?:\([^)]*\))?[ \t\r\n]*)+", "", text)
    m = _KT_HEADER.match(cleaned)
    if not m:
        return None
    end = _close_paren(cleaned, m.end() - 1)
    if end < 0:
        return None
    tail = cleaned[end : end + 300]
    cm = re.match(r"[ \t]*:[ \t]*([^\n{=]{1,200}?)[ \t]*(?:\{|=|\n)", tail)
    if not cm:
        return None
    return _normalize_type(cm.group(1), parent_class)


def _extract_c_like(lang: str, text: str, parent_class: str | None) -> str | None:
    """Java, C#, and C++ leading return type (plus C++ trailing `auto f(...) -> T`)."""
    paren = text.find("(")
    if paren < 0 or paren > 400:
        return None
    if lang == "cpp":
        end = _close_paren(text, paren)
        if end > 0:
            tail = text[end : end + 300]
            tm = re.search(r"->[ \t]*([^\n{;]{1,200}?)[ \t]*(?:\{|;|override|final|\n)", tail)
            if tm:
                norm = _normalize_type(tm.group(1), parent_class)
                if norm:
                    return norm
    prefix = text[:paren].strip()
    # Strip function name (possibly Class::name)
    nm = re.search(r"(?:[A-Za-z_]\w*::)?([A-Za-z_]\w*)[ \t]*\Z", prefix)
    if not nm:
        return None
    before_name = prefix[: nm.start()].strip()
    if not before_name:
        return None
    # Strip annotations/attributes like @Override or [SerializeField]
    before_name = re.sub(r"(?:@[A-Za-z_]\w*(?:\([^)]*\))?|\[[^\]]*\])[ \t\r\n]*", "", before_name).strip()
    # Strip leading modifier keywords
    tokens = before_name.split()
    while tokens and tokens[0] in _MODIFIERS:
        tokens.pop(0)
    if not tokens:
        return None
    ret = " ".join(tokens)
    return _normalize_type(ret, parent_class)


_EXTRACTORS = {
    "python": _extract_python,
    "embedded_python": _extract_python,
    "typescript": _extract_ts,
    "javascript": _extract_ts,
    "go": _extract_go,
    "rust": _extract_rust,
    "kotlin": _extract_kotlin,
    "java": lambda t, p: _extract_c_like("java", t, p),
    "csharp": lambda t, p: _extract_c_like("csharp", t, p),
    "cpp": lambda t, p: _extract_c_like("cpp", t, p),
}


_INFER_LANGS = frozenset({"python", "embedded_python", "typescript", "javascript"})
_NESTED_PY = re.compile(r"\n[ \t]+(?:async[ \t]+)?def[ \t]+")
_NESTED_JS = re.compile(r"\bfunction[ \t]+")
_RETURN_STMT = re.compile(r"\breturn[ \t]+([^\n;]{1,200})")
_RETURN_NULLS = frozenset({"None", "null", "undefined"})
_RETURN_PY_CALL = re.compile(r"^([A-Za-z_]\w{0,127}(?:\.[A-Za-z_]\w{0,127}){0,4})\([^()]{0,200}\)[ \t]*$")
_RETURN_JS_NEW = re.compile(r"^new[ \t]+([A-Za-z_]\w{0,127}(?:\.[A-Za-z_]\w{0,127}){0,4})\([^()]{0,200}\)[ \t]*$")


def _infer_body_return_type(lang: str, text: str) -> str | None:
    """Infer a return class name from `return ClassName(...)` when no return annotation is written."""
    if lang not in _INFER_LANGS:
        return None
    if lang in ("python", "embedded_python") and _NESTED_PY.search(text):
        return None
    if lang in ("typescript", "javascript") and _NESTED_JS.search(text, 1):
        return None
    call_re = _RETURN_PY_CALL if lang in ("python", "embedded_python") else _RETURN_JS_NEW
    candidate: str | None = None
    for m in _RETURN_STMT.finditer(text):
        rhs = m.group(1).strip()
        if rhs in _RETURN_NULLS:
            continue
        cm = call_re.match(rhs)
        if not cm:
            return None
        leaf = cm.group(1).rsplit(".", 1)[-1]
        if leaf in _PRIMITIVES or leaf in _CONTAINERS:
            return None
        if candidate is None:
            candidate = leaf
        elif candidate != leaf:
            return None
    return candidate


def extract_return_type(lang: str, text: str, parent_class: str | None = None) -> str | None:
    """Extract the declared (or unambiguously constructed) return class name from a function, or None."""
    fn = _EXTRACTORS.get(lang)
    if fn is None or not text:
        return None
    declared = fn(text, parent_class)
    if declared is not None:
        return declared
    return _infer_body_return_type(lang, text)


def extract_expr_chain(text: str, pos: int, separators: tuple[str, ...], max_segments: int = 4) -> str | None:
    """Extract a chained call/member receiver before `pos` when `_call_qualifier` sees `(...)`.

    For `get_store().save(` -> `"get_store()"`.
    For `self.store.get().save(` -> `"self.store.get()"`.
    Returns None if any segment is an index/literal/complex expression or has no call segment.
    """
    segments: list[str] = []
    saw_call = False
    i = pos
    for _ in range(max_segments):
        j = i
        while j > 0 and text[j - 1] in " \t\r\n" and i - j < 80:
            j -= 1
        sep = next((s for s in separators if j >= len(s) and text.startswith(s, j - len(s))), None)
        if sep is None:
            break
        k = j - len(sep)
        if sep == "." and text.startswith("...", k - 2):
            break
        while k > 0 and text[k - 1] in " \t\r\n" and j - k < 80:
            k -= 1
        is_call = False
        if k > 0 and text[k - 1] == ")":
            # Walk backwards over balanced (...) up to 400 chars
            depth = 0
            p = k - 1
            limit = max(0, k - 400)
            while p >= limit:
                ch = text[p]
                if ch == ")":
                    depth += 1
                elif ch == "(":
                    depth -= 1
                    if depth == 0:
                        break
                p -= 1
            if depth != 0:
                return None
            is_call = True
            saw_call = True
            k = p
            while k > 0 and text[k - 1] in " \t\r\n" and p - k < 40:
                k -= 1
        start = k
        while start > 0 and k - start < 128 and (text[start - 1].isalnum() or text[start - 1] in "_$"):
            start -= 1
        ident = text[start:k].lstrip("$")
        if not ident or ident[0].isdigit():
            return None
        segments.append(f"{ident}()" if is_call else ident)
        i = start
    if not saw_call or not segments:
        return None
    return ".".join(reversed(segments))


_CALL_ASSIGN_TS = re.compile(
    r"(?:^|[;\n])[ \t]*(?:(?:const|let|var)[ \t]+)?(?P<n>[A-Za-z_$]\w{0,127})[ \t]*=[ \t]*(?:await[ \t]+)?"
    r"(?!new\b)(?P<call>[A-Za-z_$]\w{0,127}(?:\.[A-Za-z_$]\w{0,127}){0,4})[ \t]*\("
)
_CALL_ASSIGN_GO = re.compile(
    r"(?:^|[;\n])[ \t]*(?P<n>[A-Za-z_]\w{0,127})(?:[ \t]*,[ \t]*(?:err|_))?[ \t]*:=[ \t]*"
    r"(?!new\b)(?P<call>[A-Za-z_]\w{0,127}(?:\.[A-Za-z_]\w{0,127}){0,4})[ \t]*\("
)
_CALL_ASSIGN_RS = re.compile(
    r"(?:^|[;\n])[ \t]*let[ \t]+(?:mut[ \t]+)?(?P<n>[A-Za-z_]\w{0,127})[ \t]*=[ \t]*"
    r"(?P<call>[A-Za-z_]\w{0,127}(?:(?:::|\.)[A-Za-z_]\w{0,127}){0,4})[ \t]*\("
)
_CALL_ASSIGN_CPP = re.compile(
    r"(?:^|[;\n])[ \t]*(?:const[ \t]+)?auto(?:[ \t]*[&*]{1,2})?[ \t]+(?P<n>[A-Za-z_]\w{0,127})[ \t]*=[ \t]*"
    r"(?P<call>[A-Za-z_]\w{0,127}(?:(?:::|\.|->)[A-Za-z_]\w{0,127}){0,4})[ \t]*\("
)
_CALL_ASSIGN_PATTERNS = {
    "typescript": _CALL_ASSIGN_TS,
    "javascript": _CALL_ASSIGN_TS,
    "go": _CALL_ASSIGN_GO,
    "rust": _CALL_ASSIGN_RS,
    "cpp": _CALL_ASSIGN_CPP,
}


def extract_call_assigns(lang: str, text: str, receivers: set[str]) -> dict[str, str]:
    """Extract `{var: call_expr}` for factory-call assignments (`const s = getStore()`, `s := NewStore()`)."""
    pat = _CALL_ASSIGN_PATTERNS.get(lang)
    if pat is None or not text or not receivers:
        return {}
    found: dict[str, str | None] = {}
    for m in pat.finditer(text):
        name = m.group("n")
        if name not in receivers:
            continue
        call = m.group("call").replace("::", ".").replace("->", ".")
        if name in found and found[name] != call:
            found[name] = None
        else:
            found.setdefault(name, call)
    return {k: v for k, v in found.items() if v}
