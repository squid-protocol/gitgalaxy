# ==============================================================================
# GitGalaxy Core: JCICS -- Java on CICS (#3497)
#
# PURPOSE:
# A Java program on CICS reaches COBOL and CICS resources through the JCICS API
# (com.ibm.cics.server), not EXEC blocks: `Program p = new Program();
# p.setName("GETCOMPY"); p.link(data);` is an EXEC CICS LINK, `KSDS f = new
# KSDS(); f.setName("CUSTOMER"); f.read(key, holder);` an EXEC CICS READ FILE.
# None of it was extracted, so the Java side of a partly modernised estate (CBSA's
# Liberty web UI) had no CICS edges and the COBOL it LINKs looked unreached. The
# same rows the COBOL walkers emit are produced here, so Java joins the one graph:
#
#   calls           a Program's link() -> {verb LINK, form, operand, target, line}
#   cics_resources  KSDS / ESDS / RRDS reads, writes, rewrites, deletes, browses
#                   (FILE); TSQ / TDQ items (QUEUE, qualifier TS / TD);
#                   createChannel (CHANNEL); create / get / put Container
#                   (CONTAINER, qualifier the channel)
#
# A resource object's name is the argument of the last `setName(...)` on it
# before the operation: a string literal, a same-file `static final String`
# constant, or else unresolved (the operand is kept, `resolution` says which). A
# name built by concatenation keeps its literal prefix as `PREFIX*` (resolution
# `prefix`), the way #3449 keeps a STRING-built transid as a pattern.
#
# A row's line is the line of the method call (`.link(`, `.read(` ...), which a
# chained call may put below its object.
#
# SCOPE AND NON-SCOPE:
#   - Per file, flow-insensitive: the last setName before the operation's line on
#     the same variable, whatever the path. Objects passed between methods or
#     files are not followed.
#   - Only files importing com.ibm.cics.server are read.
# ==============================================================================
import re
from typing import Any, Optional

_TYPES = {"Program": "PROGRAM", "KSDS": "FILE", "ESDS": "FILE", "RRDS": "FILE", "TSQ": "QUEUE", "TDQ": "QUEUE"}
_FILE_OPS = {"read": "read", "readForUpdate": "read", "readGeneric": "read", "readGenericForUpdate": "read",
             "write": "write", "rewrite": "update", "delete": "delete", "startBrowse": "browse",
             "startGenericBrowse": "browse", "unlock": "unlock"}  # fmt: skip
_QUEUE_OPS = {"writeItem": "write", "writeItemConditional": "write", "rewriteItem": "update", "readItem": "read",
              "readNextItem": "read", "delete": "delete", "writeData": "write", "writeString": "write",
              "readData": "read"}  # fmt: skip
_IDENT = r"[A-Za-z_$][\w$]*"
_DECL = re.compile(rf"\b(Program|KSDS|ESDS|RRDS|TSQ|TDQ)\s+({_IDENT})\s*[;=,)]")
_NEW = re.compile(rf"\b({_IDENT})\s*=\s*new\s+(Program|KSDS|ESDS|RRDS|TSQ|TDQ)\s*\(")
_SET_NAME = re.compile(rf"\b({_IDENT})\s*\.\s*setName\s*\(")
_CALL = re.compile(rf"\b({_IDENT})\s*\.\s*({_IDENT})\s*\(")
_CONST = re.compile(rf"\bstatic\s+final\s+String\s+({_IDENT})\s*=\s*\"([^\"\n]*)\"\s*;")
_CHANNEL = re.compile(rf"(?:\b({_IDENT})\s*=\s*)?[\w.()\s]*?\bcreateChannel\s*\(")
_CONTAINER = re.compile(rf"\b({_IDENT})\s*\.\s*(createContainer|getContainer)\s*\(")


def _argument(text: str, start: int) -> str:
    """The first call argument starting at `start` (just past the `(`), balanced."""
    depth, i = 0, start
    while i < len(text) and i - start < 400:
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        elif ch == '"':
            i = text.find('"', i + 1)
            if i == -1:
                break
        i += 1
    return " ".join(text[start:i].split())


def _resolve(arg: str, consts: dict[str, str]) -> tuple[Optional[str], str]:
    """(name, resolution) of a setName / createContainer argument."""
    m = re.fullmatch(r'"([^"]*)"', arg)
    if m:
        return m.group(1).strip() or None, "literal"
    if arg in consts:
        return consts[arg].strip() or None, "constant"
    m = re.match(r'"([^"]+)"\s*\+', arg)
    if m:
        return m.group(1).strip() + "*", "prefix"
    return None, "unresolved"


def _blank_comments(text: str) -> str:
    """Comments blanked (offsets kept) so a commented-out call draws nothing."""

    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return re.sub(r"/\*.*?\*/|//[^\n]*", blank, text, flags=re.S)


def jcics(code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """{"calls": [...], "cics_resources": [...]} for one Java source (see the header)."""
    if not code_stream or "com.ibm.cics.server" not in code_stream:
        return {"calls": [], "cics_resources": []}
    text = _blank_comments(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        lo, hi = 0, len(newlines)
        while lo < hi:
            mid = (lo + hi) // 2
            if newlines[mid] < offset:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    consts = {m.group(1): m.group(2) for m in _CONST.finditer(text)}
    kinds: dict[str, str] = {}
    for m in _DECL.finditer(text):
        kinds[m.group(2)] = m.group(1)
    for m in _NEW.finditer(text):
        kinds[m.group(1)] = m.group(2)
    names: dict[str, list[tuple[int, str, Optional[str], str]]] = {}
    for m in _SET_NAME.finditer(text):
        if m.group(1) in kinds:
            arg = _argument(text, m.end())
            name, how = _resolve(arg, consts)
            names.setdefault(m.group(1), []).append((m.start(), arg, name, how))

    def name_at(var: str, offset: int) -> tuple[Optional[str], Optional[str], str]:
        before = [n for n in names.get(var, []) if n[0] < offset]
        if not before:
            return None, None, "unresolved"
        _, arg, name, how = before[-1]
        return arg, name, how

    calls: list[dict[str, Any]] = []
    ops: list[dict[str, Any]] = []
    for m in _CALL.finditer(text):
        var, method = m.group(1), m.group(2)
        jtype = kinds.get(var)
        if jtype is None:
            continue
        written, name, how = name_at(var, m.start())
        if jtype == "Program" and method == "link":
            calls.append({"verb": "LINK", "form": "literal" if how in ("literal", "constant") else "identifier",
                          "operand": written or var, "target": name if how in ("literal", "constant") else None,
                          "line": line_of(m.start(2))})  # fmt: skip
            continue
        table = _FILE_OPS if _TYPES[jtype] == "FILE" else _QUEUE_OPS if _TYPES[jtype] == "QUEUE" else {}
        if method not in table:
            continue
        ops.append({"verb": method, "kind": _TYPES[jtype], "access": table[method], "operand": written, "name": name,
                    "resolution": how, "candidates": None, "qualifier_operand": None,
                    "qualifier": ("TS" if jtype == "TSQ" else "TD" if jtype == "TDQ" else None),
                    "record_clause": None, "record": None, "attributes": f"JCICS {jtype}", "line": line_of(m.start(2))})  # fmt: skip
    channels: dict[str, str] = {}
    for m in _CHANNEL.finditer(text):
        arg = _argument(text, m.end())
        name, how = _resolve(arg, consts)
        if m.group(1):
            channels[m.group(1)] = name or arg
        ops.append({"verb": "createChannel", "kind": "CHANNEL", "access": "pass", "operand": arg, "name": name,
                    "resolution": how, "candidates": None, "qualifier_operand": None, "qualifier": None,
                    "record_clause": None, "record": None, "attributes": "JCICS Channel", "line": line_of(m.start())})  # fmt: skip
    for m in _CONTAINER.finditer(text):
        arg = _argument(text, m.end())
        name, how = _resolve(arg, consts)
        ops.append({"verb": m.group(2), "kind": "CONTAINER",
                    "access": "write" if m.group(2) == "createContainer" else "read", "operand": arg, "name": name,
                    "resolution": how, "candidates": None, "qualifier_operand": m.group(1),
                    "qualifier": channels.get(m.group(1)), "record_clause": None, "record": None,
                    "attributes": "JCICS Container", "line": line_of(m.start(2))})  # fmt: skip
    ops.sort(key=lambda r: r["line"])
    calls.sort(key=lambda r: r["line"])
    return {"calls": calls, "cics_resources": ops}
