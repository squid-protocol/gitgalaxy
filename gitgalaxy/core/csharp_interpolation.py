"""C# interpolated-string holes, made visible to the call scan (#6266).

`$"Total: {counts.Total()}"` runs `Total` at run time, but the literal shield blanks the whole string, so the
`calls_out` scan never sees the hole. `expose_holes` rewrites each interpolated string in a unit's text as an empty
literal followed by its hole expressions (`"" +(counts.Total())`): the shield then blanks what is still a literal
(strings nested inside a hole) and the call pattern finds the calls. Comments, plain strings and char literals are copied
through untouched for the shield to strip. Stdlib only; offsets are not preserved (the shield does not preserve them either).
"""

_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = frozenset(_OPEN.values())


def _prefix(text: str, i: int) -> tuple[int, int, bool] | None:
    """`(string_start, dollars, verbatim)` when a string literal's `$` / `@` prefix begins at `i`, else None."""
    j, dollars, verbatim = i, 0, False
    while j < len(text) and text[j] in "$@":
        dollars += text[j] == "$"
        verbatim = verbatim or text[j] == "@"
        j += 1
    if j < len(text) and text[j] == '"' and (j > i or dollars == 0):
        return j, dollars, verbatim
    return None


def _skip_plain_string(text: str, q: int, verbatim: bool) -> int:
    """Index after the plain (non-interpolated) string whose opening quote is at `q`."""
    if text.startswith('"""', q):
        n = len(text[q:]) - len(text[q:].lstrip('"'))
        end = text.find('"' * n, q + n)
        return len(text) if end < 0 else end + n
    i = q + 1
    while i < len(text):
        ch = text[i]
        if verbatim and ch == '"':
            if text.startswith('""', i):
                i += 2
                continue
            return i + 1
        if not verbatim and ch == "\\":
            i += 2
            continue
        if not verbatim and ch == '"':
            return i + 1
        if not verbatim and ch == "\n":
            return i
        i += 1
    return i


def _hole_end(text: str, i: int) -> tuple[int, int]:
    """`(expression_end, hole_end)` for a hole whose expression starts at `i`: ends at a top-level `:` or `,` (format /
    alignment) or the closing `}`; `hole_end` is just past that `}`."""
    depth, expr_end = 0, -1
    while i < len(text):
        ch = text[i]
        if ch in ('"', "$", "@"):
            pre = _prefix(text, i) if ch != '"' else (i, 0, False)
            if pre:
                i = _string_end(text, *pre)
                continue
        if ch == "'":
            i = _skip_char(text, i)
            continue
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            if depth == 0:
                return (i if expr_end < 0 else expr_end), i + 1
            depth -= 1
        elif ch in ":," and depth == 0 and expr_end < 0 and not text.startswith("::", i):
            expr_end = i
        i += 1
    return (len(text) if expr_end < 0 else expr_end), len(text)


def _skip_char(text: str, i: int) -> int:
    j = i + 1
    while j < len(text) and text[j] != "'" and text[j] != "\n":
        j += 2 if text[j] == "\\" else 1
    return j + 1


def _string_end(text: str, q: int, dollars: int, verbatim: bool) -> int:
    """Index after the string whose opening quote is at `q` (holes included)."""
    return _interpolated(text, q, dollars, verbatim, [])[0] if dollars else _skip_plain_string(text, q, verbatim)


def _interpolated(text: str, q: int, dollars: int, verbatim: bool, holes: list[str]) -> tuple[int, int]:
    """Walk an interpolated string whose opening quote is at `q`; append each hole's expression to `holes`.
    Returns `(end_index, newline_count)`."""
    raw = text.startswith('"""', q)
    quotes = len(text) - q - len(text[q:].lstrip('"')) if raw else 1
    opener = "{" * (dollars if raw else 1)
    i, newlines = q + quotes, 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            newlines += 1
        if raw:
            if text.startswith('"' * quotes, i):
                return i + quotes, newlines
        elif verbatim and ch == '"':
            if text.startswith('""', i):
                i += 2
                continue
            return i + 1, newlines
        elif not verbatim and ch == "\\":
            i += 2
            continue
        elif ch == '"':
            return i + 1, newlines
        elif ch == "\n" and not verbatim:
            return i, newlines
        if text.startswith(opener, i):
            if not raw and text.startswith("{{", i):
                i += 2
                continue
            start = i + len(opener)
            expr_end, end = _hole_end(text, start)
            holes.append(text[start:expr_end])
            newlines += text.count("\n", start, end)
            i = end
            continue
        i += 1
    return i, newlines


def expose_holes(text: str) -> str:
    """`text` with every interpolated string replaced by `""` plus its hole expressions, as `+(expr)` terms."""
    if "$" not in text:
        return text
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(text[i:end])
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append(text[i:end])
            i = end
        elif ch == "'":
            end = _skip_char(text, i)
            out.append(text[i:end])
            i = end
        elif ch in ('"', "$", "@") and (pre := (_prefix(text, i) if ch != '"' else (i, 0, False))):
            q, dollars, verbatim = pre
            if not dollars:
                end = _skip_plain_string(text, q, verbatim)
                out.append(text[i:end])
            else:
                holes: list[str] = []
                end, newlines = _interpolated(text, q, dollars, verbatim, holes)
                out.append('""' + "\n" * newlines + "".join(f"+({expose_holes(h)})" for h in holes))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def blank_interpolated(text: str) -> str:
    """`text` with every interpolated string (holes included) blanked to spaces, newlines kept, so offsets and line
    numbers are unchanged. The brace shield's plain string pattern mis-pairs a `\\"` nested in a hole (#6266)."""
    if "$" not in text:
        return text
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(text[i:end])
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append(text[i:end])
            i = end
        elif ch == "'":
            end = _skip_char(text, i)
            out.append(text[i:end])
            i = end
        elif ch in ('"', "$", "@") and (pre := (_prefix(text, i) if ch != '"' else (i, 0, False))):
            q, dollars, verbatim = pre
            end = _string_end(text, q, dollars, verbatim)
            if not dollars:
                out.append(text[i:end])
            else:
                out.append("".join(c if c == "\n" else " " for c in text[i:end]))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)
