"""JS/TS template-literal holes and Python f-string holes, made visible to the call scan (#8161, X6).

`` `Total: ${counts.total()}` `` and `f"Total: {counts.total()}"` run `total` at run time, but the literal shield
blanks the whole literal, so the `calls_out` scan never sees the hole. Like `csharp_interpolation.expose_holes`
(#6266), each function here rewrites every such literal in a unit's text as an empty literal followed by its hole
expressions (`"" +(counts.total())`): the shield then blanks what is still a literal (strings nested inside a hole) and
the call pattern finds the calls. Comments, plain strings and (JS) regex literals are copied through untouched for the
shield to strip. Newlines are kept, so line numbers hold; other offsets are not preserved (the shield does not preserve
them either). Stdlib only, one forward pass, no regex: the cost is linear in the text.
"""

_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = frozenset(_OPEN.values())

# A `/` opens a JS regex literal only where a value is expected: after one of these characters, or one of these
# keywords, or `=>` (the same value-position rule as the literal shield's regex branch). Elsewhere it is division.
_JS_REGEX_PRECEDERS = frozenset("(,=:[!&|?{};~")
_JS_REGEX_KEYWORDS = frozenset(
    {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "yield", "await", "else", "do"}
)


def _holes_term(holes: list[str], newlines: int, expose) -> str:
    return '""' + "\n" * newlines + "".join(f"+({expose(h)})" for h in holes)


# ----------------------------------------------------------------------------- JS / TS


def _js_skip_quoted(text: str, i: int) -> int:
    """Index after the '...' / "..." string whose quote is at `i` (one line, `\\` escapes)."""
    q, j = text[i], i + 1
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == q:
            return j + 1
        if ch == "\n":
            return j
        j += 1
    return j


def _js_regex_end(text: str, i: int) -> int | None:
    """Index after a regex literal whose `/` is at `i`, or None when the `/` is division (or a comment)."""
    if i + 1 >= len(text) or text[i + 1] in "/*= \t\n":
        return None
    k = i
    while k > 0 and text[k - 1] in " \t":
        k -= 1
    if k > 0 and text[k - 1] != "\n" and text[k - 1] not in _JS_REGEX_PRECEDERS and text[k - 2 : k] != "=>":
        start = k
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_$"):
            start -= 1
        if text[start:k] not in _JS_REGEX_KEYWORDS:
            return None
    j, in_class = i + 1, False
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "\n":
            return None
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            j += 1
            while j < len(text) and text[j].isalpha():
                j += 1
            return j
        j += 1
    return None


def _js_hole_end(text: str, i: int) -> int:
    """Index of the `}` closing a `${` hole whose expression starts at `i` (nested strings, templates and braces)."""
    depth = 0
    while i < len(text):
        ch = text[i]
        if ch in "'\"":
            i = _js_skip_quoted(text, i)
            continue
        if ch == "`":
            i = _js_template(text, i, [])[0]
            continue
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return len(text)


def _js_template(text: str, i: int, holes: list[str]) -> tuple[int, int]:
    """Walk the template literal whose backtick is at `i`; append each `${...}` expression to `holes`.
    Returns `(end_index, newline_count)`."""
    j, newlines = i + 1, 0
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "\n":
            newlines += 1
        elif ch == "`":
            return j + 1, newlines
        elif ch == "$" and text.startswith("${", j):
            start = j + 2
            end = _js_hole_end(text, start)
            holes.append(text[start:end])
            newlines += text.count("\n", start, end)
            j = end + 1
            continue
        j += 1
    return j, newlines


def expose_js_holes(text: str) -> str:
    """`text` with every template literal holding a `${` hole replaced by `""` plus its hole expressions."""
    if "${" not in text:
        return text
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
        elif ch in "'\"":
            end = _js_skip_quoted(text, i)
        elif ch == "/" and (rx := _js_regex_end(text, i)) is not None:
            end = rx
        elif ch == "`":
            holes: list[str] = []
            end, newlines = _js_template(text, i, holes)
            out.append(_holes_term(holes, newlines, expose_js_holes) if holes else text[i:end])
            i = end
            continue
        else:
            out.append(ch)
            i += 1
            continue
        out.append(text[i:end])
        i = end
    return "".join(out)


# ----------------------------------------------------------------------------- Python


def _py_prefix(text: str, i: int) -> tuple[int, bool] | None:
    """`(quote_index, is_fstring)` when a string literal (with an optional r/b/f/u prefix) starts at `i`."""
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        return None
    j = i
    while j < len(text) and j - i < 2 and text[j] in "rRbBfFuU":
        j += 1
    if j < len(text) and text[j] in "'\"":
        return j, "f" in text[i:j].lower()
    return None


def _py_quote(text: str, q: int) -> str:
    ch = text[q]
    return ch * 3 if text.startswith(ch * 3, q) else ch


def _py_plain_end(text: str, q: int) -> int:
    """Index after the plain string whose opening quote is at `q`."""
    quote = _py_quote(text, q)
    j = q + len(quote)
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text.startswith(quote, j):
            return j + len(quote)
        if text[j] == "\n" and len(quote) == 1:
            return j
        j += 1
    return j


def _py_expression_ends(text: str, i: int) -> bool:
    """Whether a top-level `!` conversion, `:` format spec or `=` debug marker at `i` ends a hole's expression."""
    ch = text[i]
    if ch == "!":
        return not text.startswith("!=", i)
    if ch == "=":
        return not text.startswith("==", i) and text[i - 1] not in "=!<>"
    return ch == ":"


def _py_hole_end(text: str, i: int, quote: str) -> tuple[int, int]:
    """`(expression_end, hole_end)` for an f-string hole whose expression starts at `i`: the expression ends at a
    top-level `!` conversion, `:` format spec or `=` debug marker; `hole_end` is just past the closing `}`."""
    depth, expr_end = 0, -1
    while i < len(text):
        ch = text[i]
        if text.startswith(quote, i):
            return (i if expr_end < 0 else expr_end), i  # unterminated hole: the literal ends here
        if ch in "'\"rRbBfFuU" and (pre := _py_prefix(text, i)):
            i = _py_string_end(text, *pre)
            continue
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            if depth == 0:
                return (i if expr_end < 0 else expr_end), i + 1
            depth -= 1
        elif depth == 0 and expr_end < 0 and _py_expression_ends(text, i):
            expr_end = i
        i += 1
    return (len(text) if expr_end < 0 else expr_end), len(text)


def _py_fstring(text: str, q: int, holes: list[str]) -> tuple[int, int]:
    """Walk the f-string whose opening quote is at `q`; append each hole's expression to `holes`.
    Returns `(end_index, newline_count)`."""
    quote = _py_quote(text, q)
    j, newlines = q + len(quote), 0
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if text.startswith(quote, j):
            return j + len(quote), newlines
        if ch == "\n":
            if len(quote) == 1:
                return j, newlines
            newlines += 1
        elif ch == "{":
            if text.startswith("{{", j):
                j += 2
                continue
            start = j + 1
            expr_end, end = _py_hole_end(text, start, quote)
            holes.append(text[start:expr_end])
            newlines += text.count("\n", start, end)
            # a format spec may hold nested holes (`{x:{width}}`); they name values, not calls worth a scan
            j = end
            continue
        j += 1
    return j, newlines


def _py_string_end(text: str, q: int, fstring: bool) -> int:
    return _py_fstring(text, q, [])[0] if fstring else _py_plain_end(text, q)


def expose_python_holes(text: str) -> str:
    """`text` with every f-string replaced by `""` plus its hole expressions, as `+(expr)` terms."""
    if "{" not in text:
        return text
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "#":
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(text[i:end])
            i = end
            continue
        pre = _py_prefix(text, i) if ch in "'\"rRbBfFuU" else None
        if pre is None:
            out.append(ch)
            i += 1
            continue
        q, fstring = pre
        if fstring:
            holes: list[str] = []
            end, newlines = _py_fstring(text, q, holes)
            out.append(_holes_term(holes, newlines, expose_python_holes))
        else:
            end = _py_plain_end(text, q)
            out.append(text[i:end])
        i = end
    return "".join(out)
