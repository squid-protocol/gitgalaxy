# ==============================================================================
# GitGalaxy Core: receiver typing for C++, Go, Rust and TypeScript/JavaScript (#8161, X3)
#
# PURPOSE:
# `x.m()` on a receiver the scan cannot type is at best the ambiguous `receiver`
# guess (call_resolver._visible_receiver). Python and Java already name a
# receiver's class from the calling function's own text (detector.py,
# `_python_receiver_types` / `_java_receiver_types`); this module does the same
# for four more languages, so the resolver's `typed` step can link `x.m()` to
# that class's method. The evidence, all lexical and all from one file:
#   - the function's parameters and locals with a written type
#     (`cfg: &Config`, `var y Config`, `const Config& cfg`, `let c: Config`);
#   - a local bound to a construction of a named type
#     (`T::new(..)`, `T { .. }`, `&T{..}`, `new(T)`, `new T(..)`, `T x;`,
#     `auto x = T(..)`, `std::make_unique<T>(..)`);
#   - the file's struct/class field declarations, for `self.x` / `this.x`
#     (and, in C++, a bare `x_` that no local declares: an implicit `this`).
# A name bound twice with different types, or also bound with no type the scan
# can read (`x, err := f()`, `for x in`, `auto x = f()`), maps to "": the
# resolver then neither guesses nor falls back to a field of that name. The
# answer is only a candidate: the resolver keeps it only when it names a class
# the repository defines (call_resolver._is_class), and links only when that
# class (or an ancestor) has the method. Every quantifier is bounded; the text
# is the literal-shielded unit (strings and comments blanked).
# ==============================================================================
import re
from collections.abc import Callable, Iterable

TYPED_LANGS = frozenset({"cpp", "go", "rust", "typescript", "javascript"})

_Found = dict[str, str | None]


def _note(found: _Found, name: str, cls: str | None) -> None:
    """Record `name: cls`; a second, different answer (or None) makes it None."""
    if name in found and found[name] != cls:
        found[name] = None
    else:
        found.setdefault(name, cls)


def _close(text: str, i: int, limit: int = 4000) -> int:
    """Index just past the bracket matching the opener at `text[i]`, or -1."""
    pairs = {"(": ")", "{": "}", "[": "]", "<": ">"}
    opener = text[i]
    closer = pairs[opener]
    depth = 0
    for k in range(i, min(len(text), i + limit)):
        ch = text[k]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return k + 1
    return -1


def _ends_statement(text: str, end: int, tails: re.Pattern[str]) -> bool:
    """Whether the expression ending at `end` is the whole initializer (`;`, or a language's harmless tail)."""
    return end > 0 and tails.match(text, end) is not None


def _blank_bodies(text: str, opens: re.Pattern[str]) -> str:
    """`text` with the brace body after each `opens` match blanked (newlines kept): what is left declares fields."""
    out = list(text)
    pos = 0
    while True:
        m = opens.search(text, pos)
        if m is None:
            break
        start = m.end() - 1
        end = _close(text, start, limit=1 << 22)
        if end < 0:
            break
        for k in range(start + 1, end - 1):
            if out[k] != "\n":
                out[k] = " "
        pos = end
    return "".join(out)


# ------------------------------------------------------------------------------ Rust
_RS_PATH = r"(?:(?:crate|self|super|[A-Za-z_]\w{0,63})::){0,6}"
# a written type: `&'a mut dyn path::Type<..>`; group `t` is the type's leaf, `g` its generic arguments
_RS_TYPE = (
    r"&?[ \t]*(?:'\w{1,32}[ \t]+)?(?:mut[ \t]+)?(?:(?:dyn|impl)[ \t]+)?" + _RS_PATH + r"(?P<t>[A-Z]\w{0,127})"
    r"(?P<g><[^;=(){}]{0,200}?>)?"
)
_RS_PARAM = re.compile(
    r"(?<![\w.])(?:mut[ \t]+)?(?P<n>[a-z_]\w{0,63})[ \t]*:[ \t]*" + _RS_TYPE + r"[ \t\r\n]*(?=[,)=;]|\Z)"
)
_RS_LET_TYPED = re.compile(
    r"\blet[ \t]+(?:mut[ \t]+)?(?P<n>[a-z_]\w{0,63})[ \t]*:[ \t]*" + _RS_TYPE + r"[ \t]*(?=[=;])"
)
_RS_LET = re.compile(
    r"\blet[ \t]+(?:mut[ \t]+)?(?P<n>[a-z_]\w{0,63})[ \t]*=[ \t]*&?(?:mut[ \t]+)?" + _RS_PATH + r"(?P<t>[A-Z]\w{0,127})"
    r"(?:::<[^;=(){}]{0,200}?>)?[ \t]*(?:::[ \t]*(?P<f>\w{1,64})[ \t]*(?P<call>\()|(?P<lit>[{(]))"
)
# `let x = <anything else>`: bound, with no type the scan reads
_RS_LET_ANY = re.compile(r"\blet[ \t]+(?:mut[ \t]+)?(?P<n>[a-z_]\w{0,63})[ \t]*(?:=|;)")
_RS_FOR = re.compile(r"\bfor[ \t]+(?P<p>[^{};]{1,200}?)[ \t]+in\b")
_RS_CLOSURE = re.compile(r"(?:^|[(,=]|move)[ \t]*\|(?P<p>[^|;{}]{0,200})\|")
_RS_NAME = re.compile(r"\b[a-z_]\w{0,63}\b")
# an associated function that returns its own type, by Rust convention
_RS_CTOR_FN = re.compile(r"(?:new|default|create|from|new_\w+|with_\w+|from_\w+)\Z")
_RS_TAILS = re.compile(r"[ \t\r\n]*(?:\?[ \t\r\n]*)?(?:\.(?:unwrap|expect)[ \t]*\([^;]{0,200}\)[ \t\r\n]*)?;")
# smart pointers that deref to their argument: methods of `T` are callable on them
_RS_DEREF_WRAPPERS = frozenset({"Box", "Rc", "Arc"})
_RS_STRUCT_OPEN = re.compile(r"\bstruct[ \t]+[A-Za-z_]\w{0,127}[^;{]{0,400}\{")
_RS_FN_BODY_OPEN = re.compile(r"\bfn[ \t]+\w{1,128}[^;{]{0,800}\{")
_RS_FIELD = re.compile(
    r"(?:^|[{,])[ \t\r\n]*(?:#\[[^\]]{0,200}\][ \t\r\n]*){0,4}(?:pub(?:\([^)]{0,40}\))?[ \t]+)?(?P<n>[a-z_]\w{0,63})[ \t]*:[ \t]*"
    + _RS_TYPE
    + r"[ \t\r\n]*(?=[,}])"
)


def _rs_leaf(m: re.Match[str]) -> str:
    """The type a written Rust type names: a `Box<T>` / `Rc<T>` / `Arc<T>` is `T`."""
    t, g = m.group("t"), m.group("g")
    if t in _RS_DEREF_WRAPPERS and g:
        inner = re.match(r"<[ \t]*" + _RS_PATH + r"([A-Z]\w{0,127})[ \t]*>", g)
        return inner.group(1) if inner else ""
    return t


def _rust_declared(text: str) -> _Found:
    found: _Found = {}
    for m in _RS_PARAM.finditer(text):
        if m.group("n") != "self":
            _note(found, m.group("n"), _rs_leaf(m) or None)
    for m in _RS_LET_TYPED.finditer(text):
        _note(found, m.group("n"), _rs_leaf(m) or None)
    typed_lets = set()
    for m in _RS_LET.finditer(text):
        if m.group("call") is not None:
            ok = bool(_RS_CTOR_FN.match(m.group("f"))) and _ends_statement(
                text, _close(text, m.start("call")), _RS_TAILS
            )
        else:
            ok = _ends_statement(text, _close(text, m.start("lit")), _RS_TAILS)
        _note(found, m.group("n"), m.group("t") if ok else None)
        typed_lets.add(m.start())
    for m in _RS_LET_ANY.finditer(text):
        if m.start() not in typed_lets and not _RS_LET_TYPED.match(text, m.start()):
            _note(found, m.group("n"), None)
    for m in _RS_FOR.finditer(text):
        for n in _RS_NAME.findall(m.group("p")):
            _note(found, n, None)
    for m in _RS_CLOSURE.finditer(text):
        for part in m.group("p").split(","):
            name = _RS_NAME.search(part)
            if name and ":" not in part:
                _note(found, name.group(0), None)
    return found


def _rust_fields(code: str) -> _Found:
    found: _Found = {}
    text = _blank_bodies(code, _RS_FN_BODY_OPEN)
    for m in _RS_STRUCT_OPEN.finditer(text):
        start = m.end() - 1
        end = _close(text, start, limit=1 << 20)
        if end < 0:
            continue
        body = text[start:end]
        depth_ok = _depth_one_spans(body)
        for f in _RS_FIELD.finditer(body):
            if depth_ok(f.start("n")):
                _note(found, f.group("n"), _rs_leaf(f) or None)
    return found


def _depth_one_spans(body: str) -> Callable[[int], bool]:
    """For a `{..}` body: a predicate telling whether an offset sits directly inside the outer braces."""
    depth_at = [0] * (len(body) + 1)
    depth = 0
    for k, ch in enumerate(body):
        if ch in "{([<":
            depth += 1
        elif ch in "})]>":
            depth -= 1
        depth_at[k + 1] = depth
    return lambda i: depth_at[i] == 1


# ------------------------------------------------------------------------------ Go
_GO_IDENT = r"[A-Za-z_]\w{0,127}"
# a written Go type: `*pkg.T`, `T[int]`; `q` the package qualifier, `t` the type name
_GO_TYPE = r"\*?[ \t]*(?:(?P<q>[a-z_]\w{0,63})\.)?(?P<t>" + _GO_IDENT + r")(?:\[[^\]\n]{0,120}\])?"
_GO_TYPE_RE = re.compile(r"[ \t]*" + _GO_TYPE + r"[ \t]*\Z")
_GO_FUNC_PARAMS = re.compile(
    r"\bfunc\b[ \t]*(?:\([^()]{0,300}\)[ \t]*)?(?:" + _GO_IDENT + r")?[ \t]*(?:\[[^\]]{0,200}\])?[ \t]*\("
)
_GO_VAR = re.compile(
    r"\bvar[ \t]+(?P<n>" + _GO_IDENT + r"(?:[ \t]*,[ \t]*" + _GO_IDENT + r"){0,8})[ \t]+(?P<rest>[^\n;]{1,300})"
)
_GO_SHORT = re.compile(
    r"(?P<n>" + _GO_IDENT + r"(?:[ \t]*,[ \t]*" + _GO_IDENT + r"){0,8})[ \t]*:=[ \t]*(?P<rest>[^\n;]{0,300})"
)
# the right-hand side of a binding that constructs a named type: `&T{`, `T{`, `new(T)`
_GO_CTOR = re.compile(
    r"(?:&[ \t]*)?(?:(?P<q>[a-z_]\w{0,63})\.)?(?P<t>" + _GO_IDENT + r")(?:\[[^\]\n]{0,120}\])?[ \t]*(?P<lit>\{)"
    r"|new\([ \t]*\*?(?:(?P<nq>[a-z_]\w{0,63})\.)?(?P<nt>" + _GO_IDENT + r")[ \t]*\)"
)
_GO_TAILS = re.compile(r"[ \t]*(?:$|;|\)|,|//)", re.M)
_GO_STRUCT_OPEN = re.compile(r"\btype[ \t]+" + _GO_IDENT + r"(?:\[[^\]]{0,200}\])?[ \t]+struct[ \t]*\{")
_GO_FIELD = re.compile(
    r"[ \t]*(?P<n>" + _GO_IDENT + r"(?:[ \t]*,[ \t]*" + _GO_IDENT + r"){0,8})[ \t]+(?P<t>[^`;\n\"]{1,200}?)[ \t]*"
    r"(?:`[^`\n]{0,400}`|\"[^\"\n]{0,400}\")?[ \t;]*\Z"
)
_GO_KEYWORDS = frozenset({"func", "map", "chan", "interface", "struct", "range", "go", "select"})


def _go_type_name(written: str) -> str | None:
    """`*pkg.T` -> `pkg.T`, `T` -> `T`; None for a slice, map, channel, function or interface type."""
    m = _GO_TYPE_RE.match(written)
    if m is None or m.group("t") in _GO_KEYWORDS:
        return None
    return f"{m.group('q')}.{m.group('t')}" if m.group("q") else m.group("t")


def _go_params(params: str) -> list[tuple[str, str | None]]:
    """`a, b *T, c pkg.U` -> [(a, T), (b, T), (c, pkg.U)]: a name with no type takes the next one's."""
    items: list[str] = []
    depth, cur = 0, []
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    items.append("".join(cur))
    out: list[tuple[str, str | None]] = []
    pending: list[str] = []
    for item in (i.strip() for i in items):
        if not item:
            continue
        parts = item.split(None, 1)
        if len(parts) == 1:
            pending.append(parts[0])
            continue
        typ = _go_type_name(parts[1])
        out.extend((n, typ) for n in (*pending, parts[0]))
        pending = []
    return out


def _go_declared(text: str) -> _Found:
    found: _Found = {}
    for m in _GO_FUNC_PARAMS.finditer(text):
        end = _close(text, m.end() - 1)
        if end < 0:
            continue
        for n, typ in _go_params(text[m.end() : end - 1]):
            if re.fullmatch(_GO_IDENT, n):
                _note(found, n, typ)
    for m in _GO_VAR.finditer(text):
        names = [n.strip() for n in m.group("n").split(",")]
        rest = m.group("rest")
        if "=" in rest:
            typ_part, rhs = rest.split("=", 1)
            typ = _go_type_name(typ_part) if typ_part.strip() else _go_rhs_type(rhs)
        else:
            typ = _go_type_name(rest)
        for n in names:
            _note(found, n, typ if len(names) == 1 or "=" not in rest else None)
    for m in _GO_SHORT.finditer(text):
        names = [n.strip() for n in m.group("n").split(",")]
        typ = _go_rhs_type(m.group("rest")) if len(names) == 1 else None
        for n in names:
            if n != "_":
                _note(found, n, typ)
    return found


def _go_rhs_type(rhs: str) -> str | None:
    """The type an initializer constructs (`&T{..}`, `T{}`, `new(T)`), when it is the whole initializer."""
    m = _GO_CTOR.match(rhs.lstrip())
    if m is None:
        return None
    body = rhs.lstrip()
    if m.group("lit") is not None:
        end = _close(body, m.start("lit"))
        if end < 0 or not _GO_TAILS.match(body, end):
            return None
        q, t = m.group("q"), m.group("t")
    else:
        if not _GO_TAILS.match(body, m.end()):
            return None
        q, t = m.group("nq"), m.group("nt")
    if t in _GO_KEYWORDS:
        return None
    return f"{q}.{t}" if q else t


def _go_fields(code: str) -> _Found:
    found: _Found = {}
    for m in _GO_STRUCT_OPEN.finditer(code):
        start = m.end() - 1
        end = _close(code, start, limit=1 << 20)
        if end < 0:
            continue
        for line in code[start + 1 : end - 1].split("\n"):
            f = _GO_FIELD.match(line)
            if f is None:
                continue  # blank, an embedded type, or a nested struct's line
            for n in f.group("n").split(","):
                _note(found, n.strip(), _go_type_name(f.group("t")))
    return found


# ------------------------------------------------------------------------------ TypeScript / JavaScript
_TS_IDENT = r"[A-Za-z_$][\w$]{0,127}"
# a written type: `ns.T<..>`, optionally `| undefined | null`; group `t` is the leaf
_TS_TYPE = (
    r"(?:" + _TS_IDENT + r"\.){0,4}(?P<t>[A-Z][\w$]{0,127})(?:<[^;=(){}]{0,200}?>)?"
    r"(?:[ \t]*\|[ \t]*(?:undefined|null))*"
)
_TS_PARAM = re.compile(
    r"(?:(?<=[(,])|^)[ \t\r\n]*(?:(?:private|public|protected|readonly|override)[ \t]+){0,3}"
    r"(?P<n>" + _TS_IDENT + r")[ \t]*[?!]?[ \t]*:[ \t]*" + _TS_TYPE + r"[ \t\r\n]*(?=[,)=])",
    re.M,
)
_TS_DECL_TYPED = re.compile(
    r"\b(?:let|const|var)[ \t]+(?P<n>" + _TS_IDENT + r")[ \t]*!?[ \t]*:[ \t]*" + _TS_TYPE + r"[ \t]*(?=[=;\n])"
)
_TS_NEW = re.compile(
    r"(?:\b(?:let|const|var)[ \t]+|(?P<this>\bthis\.))?(?P<n>" + _TS_IDENT + r")[ \t]*(?::[^=;\n]{1,200})?=[ \t]*"
    r"new[ \t]+(?:" + _TS_IDENT + r"\.){0,4}(?P<t>[A-Z][\w$]{0,127})[ \t]*(?:<[^;=(){}]{0,200}?>)?[ \t]*(?P<call>\()"
)
_TS_DECL_ANY = re.compile(r"\b(?:let|const|var)[ \t]+(?P<n>" + _TS_IDENT + r")[ \t]*(?=[=;\n])")
_TS_FOR = re.compile(r"\bfor[ \t]*\([ \t]*(?:let|const|var)[ \t]+(?P<p>[^;)]{1,200}?)[ \t]+(?:of|in)\b")
_TS_TAILS = re.compile(r"[ \t]*(?:;|$|\)|,)", re.M)
_TS_CLASS_OPEN = re.compile(r"\bclass[ \t]+" + _TS_IDENT + r"[^{;]{0,400}\{")
# a member's declared type at class level: `private cfg: Config;`, `cfg?: Config = ...`
_TS_FIELD = re.compile(
    r"^[ \t]*(?:(?:private|public|protected|readonly|static|declare|override|#)[ \t]*){0,4}"
    r"(?P<n>#?" + _TS_IDENT + r")[ \t]*[?!]?[ \t]*:[ \t]*" + _TS_TYPE + r"[ \t]*(?=[;=\n])",
    re.M,
)
_TS_METHOD_OPEN = re.compile(r"\)[ \t\r\n]*(?::[^{;]{0,300})?\{|=>[ \t\r\n]*\{")


def _ts_declared(text: str) -> _Found:
    found: _Found = {}
    for m in _TS_PARAM.finditer(text):
        _note(found, m.group("n"), m.group("t"))
    for m in _TS_DECL_TYPED.finditer(text):
        _note(found, m.group("n"), m.group("t"))
    newed = set()
    for m in _TS_NEW.finditer(text):
        if m.group("this"):
            continue
        ok = _ends_statement(text, _close(text, m.start("call")), _TS_TAILS)
        _note(found, m.group("n"), m.group("t") if ok else None)
        newed.add(m.start("n"))
    for m in _TS_DECL_ANY.finditer(text):
        if m.start("n") not in newed:
            _note(found, m.group("n"), None)
    for m in _TS_FOR.finditer(text):
        for n in re.findall(_TS_IDENT, m.group("p")):
            _note(found, n, None)
    return found


def _ts_fields(code: str) -> _Found:
    found: _Found = {}
    for m in _TS_CLASS_OPEN.finditer(code):
        start = m.end() - 1
        end = _close(code, start, limit=1 << 22)
        if end < 0:
            continue
        body = code[start + 1 : end - 1]
        members = _blank_bodies(body, _TS_METHOD_OPEN)
        for f in _TS_FIELD.finditer(members):
            _note(found, f.group("n"), f.group("t"))
        for f in _TS_NEW.finditer(members):
            if not f.group("this") and _ends_statement(members, _close(members, f.start("call")), _TS_TAILS):
                _note(found, f.group("n"), f.group("t"))
        # constructor parameter properties (`constructor(private readonly cfg: Config)`) and `this.x = new T(..)`
        for f in _TS_PARAM.finditer(body):
            if re.match(r"[ \t\r\n]*(?:private|public|protected|readonly)\b", body[f.start() : f.start("n")]):
                _note(found, f.group("n"), f.group("t"))
        for f in _TS_NEW.finditer(body):
            if f.group("this") and _ends_statement(body, _close(body, f.start("call")), _TS_TAILS):
                _note(found, f.group("n"), f.group("t"))
    return found


# ------------------------------------------------------------------------------ C++
_CPP_IDENT = r"[A-Za-z_]\w{0,127}"
_CPP_SCOPE = (
    r"(?:(?:"
    + _CPP_IDENT
    + r")?[ \t]*::[ \t]*(?:template[ \t]+)?(?:"
    + _CPP_IDENT
    + r"[ \t]*(?:<[^;(){}]{0,200}?>)?[ \t]*::[ \t]*){0,6})?"
)
# `const ns::T<..> *& name` followed by `;` `=` `,` `)` `(` `{`; group `t` the leaf, `g` its arguments, `n` the name
_CPP_DECL = re.compile(
    r"(?<![\w.:>])(?:(?:const|static|volatile|mutable|constexpr|thread_local|struct|class|typename)[ \t]+){0,4}"
    + _CPP_SCOPE
    + r"(?P<t>"
    + _CPP_IDENT
    + r")[ \t]*(?P<g><[^;(){}]{0,200}?>)?(?P<m>[ \t\r\n]*(?:const[ \t]+)?[*&]{1,2}[ \t\r\n]*(?:const[ \t]+)?|[ \t\r\n]+)"
    r"(?P<n>" + _CPP_IDENT + r")[ \t]*(?P<after>\[|[;=,)({]|:(?!:))"
)
_CPP_AUTO = re.compile(
    r"\bauto[ \t]*[*&]{0,2}[ \t]*(?P<n>" + _CPP_IDENT + r")[ \t]*(?:=[ \t]*(?P<rhs>[^;]{1,300})|[({])"
)
_CPP_RHS = re.compile(
    r"(?:new[ \t]+)?"
    + _CPP_SCOPE
    + r"(?:make_unique|make_shared)[ \t]*<[ \t]*"
    + _CPP_SCOPE
    + r"(?P<mt>"
    + _CPP_IDENT
    + r")[ \t]*>[ \t]*\("
    r"|(?:new[ \t]+)?" + _CPP_SCOPE + r"(?P<t>" + _CPP_IDENT + r")[ \t]*(?:<[^;(){}]{0,200}?>)?[ \t]*[({]"
)
# smart pointers whose `->` reaches their argument's methods
_CPP_POINTER_WRAPPERS = frozenset({"unique_ptr", "shared_ptr", "scoped_ptr", "intrusive_ptr", "Ref", "RefPtr"})
# words that stand where a declaration's type would but declare nothing
_CPP_NOT_TYPES = frozenset(
    {"return", "else", "new", "delete", "throw", "case", "goto", "co_return", "co_await", "co_yield",
     "sizeof", "alignof", "typedef", "using", "operator", "do", "not", "and", "or", "xor", "template",
     "namespace", "public", "private", "protected", "friend", "virtual", "explicit", "default", "if",
     "while", "for", "switch", "auto", "decltype", "static_cast", "const_cast", "reinterpret_cast",
     "dynamic_cast", "noexcept", "override", "final", "inline", "extern", "enum", "union", "void"}
)  # fmt: skip
_CPP_BODY_OPEN = re.compile(r"\)(?:[ \t\r\n]|const|noexcept|override|final|volatile|&&?|->[^{;]{0,200}){0,40}\{")
_CPP_FOR_AUTO = re.compile(
    r"\bfor[ \t]*\([ \t]*(?:const[ \t]+)?auto[ \t]*[*&]{0,2}[ \t]*(?P<n>" + _CPP_IDENT + r")[ \t]*:(?!:)"
)


def _cpp_decl_type(m: re.Match[str]) -> str | None:
    """The class a declaration's object is (or points to); None for an array."""
    if m.group("after") == "[":
        return None
    t, g = m.group("t"), m.group("g")
    if t in _CPP_POINTER_WRAPPERS and g:
        inner = re.match(r"<[ \t]*(?:const[ \t]+)?" + _CPP_SCOPE + r"(" + _CPP_IDENT + r")[ \t]*>", g)
        return inner.group(1) if inner else None
    return t


def _cpp_scan(text: str, found: _Found) -> None:
    for m in _CPP_DECL.finditer(text):
        t, n = m.group("t"), m.group("n")
        if t in _CPP_NOT_TYPES or n in _CPP_NOT_TYPES or t[0].isdigit():
            continue
        _note(found, n, _cpp_decl_type(m))


def _cpp_declared(text: str) -> _Found:
    found: _Found = {}
    _cpp_scan(text, found)
    for m in _CPP_AUTO.finditer(text):
        rhs = m.group("rhs")
        typ = None
        if rhs is not None:
            r = _CPP_RHS.match(rhs.strip())
            if r is not None:
                opener = r.end() - 1
                body = rhs.strip()
                end = _close(body, opener)
                if end > 0 and not body[end:].strip():
                    typ = r.group("mt") or r.group("t")
        _note(found, m.group("n"), typ if typ not in _CPP_NOT_TYPES else None)
    for m in _CPP_FOR_AUTO.finditer(text):
        _note(found, m.group("n"), None)
    return found


def _blank_parens(text: str) -> str:
    """`text` with every parenthesised list's contents blanked (newlines kept): a declaration's parameters."""
    out = list(text)
    depth = 0
    for k, ch in enumerate(text):
        if ch == ")":
            depth = max(0, depth - 1)
        elif depth and ch != "\n":
            out[k] = " "
        if ch == "(":
            depth += 1
    return "".join(out)


def _cpp_fields(code: str) -> _Found:
    found: _Found = {}
    _cpp_scan(_blank_parens(_blank_bodies(code, _CPP_BODY_OPEN)), found)
    return found


# ------------------------------------------------------------------------------ entry points
_DECLARED: dict[str, Callable[[str], _Found]] = {
    "rust": _rust_declared,
    "go": _go_declared,
    "typescript": _ts_declared,
    "javascript": _ts_declared,
    "cpp": _cpp_declared,
}
_FIELDS: dict[str, Callable[[str], _Found]] = {
    "rust": _rust_fields,
    "go": _go_fields,
    "typescript": _ts_fields,
    "javascript": _ts_fields,
    "cpp": _cpp_fields,
}
# the receiver prefix that names the caller's own object (`self.cfg`, `this.cfg_`; Go's receiver var is `self`)
_OWN_PREFIXES = ("self.", "this.")
# languages where a bare name no local declares is a field of the caller's own object
_IMPLICIT_THIS_LANGS = frozenset({"cpp"})


def file_field_types(lang: str, code: str) -> _Found | None:
    """Every field the file's struct/class declarations type -> its class name (None when two disagree)."""
    fn = _FIELDS.get(lang)
    return fn(code) if fn else None


def receiver_types(lang: str, text: str, receivers: Iterable[str], fields: _Found | None) -> dict[str, str]:
    """Receiver -> class name for the receivers in `receivers` (one unit's literal-shielded `text`).

    The unit's own declarations win; `self.x` / `this.x` (and a C++ bare name no local declares) is a field,
    typed by `fields` (`file_field_types`). A receiver with no single known class maps to "", which hides any
    other answer for it. Go keeps a package qualifier (`pkg.T`) for the resolver to follow.
    """
    declared = _DECLARED[lang]
    local = declared(text)
    out: dict[str, str] = {}
    for r in receivers:
        own = next((p for p in _OWN_PREFIXES if r.startswith(p)), None)
        name = r[len(own) :] if own else r
        if not name or "." in name:
            continue
        scopes: tuple[_Found, ...]
        if own:
            scopes = (fields or {},)
        elif lang in _IMPLICIT_THIS_LANGS:
            scopes = (local, fields or {})
        else:
            scopes = (local,)
        for scope in scopes:
            if name in scope:
                out[r] = scope[name] or ""
                break
    return out
