# ==============================================================================
# GitGalaxy: a small, strict YAML reader for configuration files (#3613)
#
# PURPOSE:
# GitGalaxy's own configs (the COBOL -> Java target first) are read without
# PyYAML, so they work in zero-dependency installs. This is NOT a general YAML
# implementation: it reads the subset configuration files use, and REJECTS
# everything else with an error naming the line, rather than guessing.
#
# Read:
#   - block mappings nested by indentation (spaces only); `key: value`, `key:`
#   - block sequences (`- item`, including `- key: value` mapping items)
#   - flow sequences of scalars: `[a, 'b', 3]`
#   - scalars, YAML 1.2 core schema: null (`null`, `~`, empty), booleans
#     (`true` / `false`, any case), integers, floats, and strings -- plain,
#     'single-quoted' (`''` is one quote) or "double-quoted" (\\" \\\\ \\n \\t \\/)
#   - comments: `#` at the start of a line or after whitespace, outside quotes
#   - a single leading `---`
# Rejected: anchors / aliases (&, *), tags (!), block scalars (| >), flow
# mappings ({...}), nested flow sequences, complex keys (?), multiple documents,
# tab indentation, duplicate keys.
#
# Note the 1.2 core schema: `yes` / `no` / `on` / `off` are strings, not booleans.
# ==============================================================================
from __future__ import annotations

import re
from typing import Any

_INT = re.compile(r"[-+]?[0-9]+")  # 1.2 core: `017` is 17 (not octal)
_FLOAT = re.compile(r"[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[-+]?[0-9]+[eE][-+]?[0-9]+")
_KEY = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s#'"\[\]{},:][^:#]*?)\s*:(?:\s+|$)""")
_UNSUPPORTED_START = {"&": "anchors", "*": "aliases", "!": "tags", "|": "block scalars", ">": "block scalars",
                      "{": "flow mappings", "?": "complex keys", "%": "directives", "@": "reserved indicators",
                      "`": "reserved indicators"}  # fmt: skip


class YamlError(ValueError):
    """A document outside the supported subset, or malformed; the message names the line."""


def _strip_comment(text: str) -> str:
    """The line without its comment: a `#` at the start or after whitespace, outside quotes."""
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                if quote == "'" and text[i + 1 : i + 2] == "'":
                    i += 2
                    continue
                quote = None
        elif ch in "'\"" and (i == 0 or text[i - 1] in " \t[,:-"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
        i += 1
    return text.rstrip()


def _unquote(token: str, line: int) -> str:
    if token[0] == "'":
        if len(token) < 2 or token[-1] != "'":
            raise YamlError(f"line {line}: unterminated single-quoted string")
        return token[1:-1].replace("''", "'")
    if len(token) < 2 or token[-1] != '"':
        raise YamlError(f"line {line}: unterminated double-quoted string")
    out, i, body = [], 0, token[1:-1]
    escapes = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "/": "/", "r": "\r", "0": "\0"}
    while i < len(body):
        if body[i] == "\\":
            nxt = body[i + 1 : i + 2]
            if nxt not in escapes:
                raise YamlError(f"line {line}: unsupported escape \\{nxt} in a double-quoted string")
            out.append(escapes[nxt])
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def _scalar(text: str, line: int) -> Any:
    """One scalar under the YAML 1.2 core schema."""
    text = text.strip()
    if text == "" or text in ("null", "Null", "NULL", "~"):
        return None
    if text[0] in "'\"":
        return _unquote(text, line)
    if text[0] in _UNSUPPORTED_START:
        raise YamlError(f"line {line}: {_UNSUPPORTED_START[text[0]]} are not supported in GitGalaxy configs")
    if text[0] == "[":
        return _flow_sequence(text, line)
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if _INT.fullmatch(text):
        return int(text)
    if _FLOAT.fullmatch(text):
        return float(text)
    if re.search(r":(?:\s|$)", text) or " #" in text:
        raise YamlError(f"line {line}: a plain value may not contain ': ' -- quote it")
    return text


def _flow_sequence(text: str, line: int) -> list:
    if not text.endswith("]"):
        raise YamlError(f"line {line}: unterminated flow sequence")
    body = text[1:-1].strip()
    if not body:
        return []
    items, buf, quote = [], [], None
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in "[]{}":
            raise YamlError(f"line {line}: nested flow collections are not supported")
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if quote:
        raise YamlError(f"line {line}: unterminated string in a flow sequence")
    items.append("".join(buf))
    if items and not items[-1].strip():
        items.pop()  # a trailing comma
    return [_scalar(item, line) for item in items]


def load_yaml(text: str) -> Any:
    """The data one YAML document holds (see the module header for the subset)."""
    lines: list[tuple[int, int, str]] = []  # (line number, indent, content)
    seen_content = False
    for no, raw in enumerate(text.splitlines(), 1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        stripped = body.lstrip(" ")
        if stripped.startswith("\t") or "\t" in body[: len(body) - len(stripped) + 1]:
            raise YamlError(f"line {no}: tabs are not allowed for indentation")
        if stripped in ("---", "..."):
            if stripped == "---" and not seen_content:
                continue
            raise YamlError(f"line {no}: multiple documents are not supported")
        seen_content = True
        lines.append((no, len(body) - len(stripped), stripped))
    if not lines:
        return None
    value, pos = _block(lines, 0, lines[0][1])
    if pos != len(lines):
        no = lines[pos][0]
        raise YamlError(f"line {no}: unexpected indentation")
    return value


def _block(lines: list[tuple[int, int, str]], pos: int, indent: int) -> tuple[Any, int]:
    """The mapping or sequence whose entries sit at `indent`, from `pos`."""
    if lines[pos][2] == "-" or lines[pos][2].startswith("- "):
        return _sequence(lines, pos, indent)
    return _mapping(lines, pos, indent)


def _nested(lines: list[tuple[int, int, str]], pos: int, parent_indent: int) -> tuple[Any, int]:
    """The value of a `key:` / `-` with nothing after it: a deeper block, else null."""
    if pos < len(lines) and lines[pos][1] > parent_indent:
        return _block(lines, pos, lines[pos][1])
    return None, pos


def _mapping(lines: list[tuple[int, int, str]], pos: int, indent: int) -> tuple[dict, int]:
    out: dict[Any, Any] = {}
    while pos < len(lines) and lines[pos][1] == indent:
        no, _, content = lines[pos]
        if content == "-" or content.startswith("- "):
            raise YamlError(f"line {no}: a sequence item where a mapping key was expected")
        m = _KEY.match(content)
        if not m:
            if content[0] in _UNSUPPORTED_START:
                raise YamlError(f"line {no}: {_UNSUPPORTED_START[content[0]]} are not supported in GitGalaxy configs")
            raise YamlError(f"line {no}: expected `key: value`")
        key_text = m.group(1).strip()
        key = _unquote(key_text, no) if key_text[0] in "'\"" else key_text
        if key in out:
            raise YamlError(f"line {no}: duplicate key {key!r}")
        rest = content[m.end() :]
        pos += 1
        if rest.strip():
            out[key] = _scalar(rest, no)
        else:
            out[key], pos = _nested(lines, pos, indent)
    if pos < len(lines) and lines[pos][1] > indent:
        raise YamlError(f"line {lines[pos][0]}: unexpected indentation")
    return out, pos


def _sequence(lines: list[tuple[int, int, str]], pos: int, indent: int) -> tuple[list, int]:
    out: list[Any] = []
    while pos < len(lines) and lines[pos][1] == indent:
        no, _, content = lines[pos]
        if not (content == "-" or content.startswith("- ")):
            raise YamlError(f"line {no}: expected a `- ` sequence item")
        item = content[1:].lstrip(" ")
        pos += 1
        if not item:
            value, pos = _nested(lines, pos, indent)
        elif item == "-" or item.startswith("- "):
            # `- - x`: a sequence item that is itself a sequence, continued at the inner dash's column.
            inner = indent + (len(content) - len(item))
            value, k = _sequence([(no, inner, item), *lines[pos:]], 0, inner)
            pos += k - 1
        elif _KEY.match(item):
            # `- key: value`: a mapping item whose first entry shares the dash's line; the
            # rest of its entries sit at the column that first key starts in.
            inner = indent + (len(content) - len(item))
            value, k = _mapping([(no, inner, item), *lines[pos:]], 0, inner)
            pos += k - 1  # index k of [first line, *lines[pos:]] is lines[pos + k - 1]
        else:
            value = _scalar(item, no)
        out.append(value)
    return out, pos
