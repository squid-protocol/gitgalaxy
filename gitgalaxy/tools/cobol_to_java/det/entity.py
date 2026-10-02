"""The id of a generated entity, from a record's key bytes -- so a keyed read is the repository's findById, not a scan.

The generated entity marks its key: an `@Id` field with its COBOL name, PICTURE and offset in the comment above it,
or an `@EmbeddedId` key class whose fields carry the same comments (offsets in the record). The id is decoded from
the key bytes with the runtime's own field rules; the store then checks the record found has exactly those key
bytes, so a key the decoding would read loosely (non-digits in a numeric key) finds nothing, as VSAM would."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import layout as L

_FIELD = re.compile(r"//\s*([A-Z0-9-]+):\s*PIC\s+(\S+?)(?:\s+(COMP-3|COMP-5|COMP-4|COMP|BINARY|PACKED-DECIMAL))?,"
                    r"\s*offset\s+(\d+),\s*(\d+)\s+bytes[^\n]*\n(?:\s*@[^\n]*\n)*\s*private\s+([\w.]+)\s+(\w+);")  # fmt: skip
_ID = re.compile(r"@(Id|EmbeddedId)\s*\n(?:\s*@[^\n]*\n)*\s*private\s+([\w.]+)\s+(\w+);")
_TYPES = ("String", "Long", "Integer", "Short", "BigDecimal", "java.math.BigDecimal")


@dataclass
class IdMethod:
    entity: str
    id_type: str
    code: list  # the Java method: `private static <id_type> id_<entity>(byte[] rec)`


def _item(pic: str, usage: str | None) -> L.Item:
    u = {"COMP": "BINARY", "COMP-4": "BINARY", "BINARY": "BINARY", "COMP-3": "PACKED", "PACKED-DECIMAL": "PACKED",
         "COMP-5": "COMP-5"}.get((usage or "").upper(), "DISPLAY")  # fmt: skip
    it = L.Item(5, "K", "WORKING-STORAGE", pic=pic, usage=u)
    L.layout(it)
    return it


def _sized(f: re.Match) -> L.Item | None:
    """The comment's item, when its PICTURE and USAGE give exactly the bytes the comment says (else the comment is
    not one the key bytes can be decoded by: None, and the scan stays)."""
    it = _item(f.group(2), f.group(3))
    return it if it.size == int(f.group(5)) else None


def _value(jtype: str, field: str) -> str | None:
    if jtype == "String":
        return f"Cobol.text({field}, CS)"
    conv = {"Long": ".longValue()", "Integer": ".intValue()", "Short": ".shortValue()"}.get(jtype, "")
    if jtype not in _TYPES:
        return None
    return f"Cobol.num({field}, CS){conv}"


def id_method(java_root: Path, entity: str, factory) -> IdMethod | None:
    """`factory(item, storage, offset)` is the generator's Field factory. None when the entity's id is not one the
    key bytes give (a key that is not one field, carried as a String -- the scan stays)."""
    path = next(java_root.rglob(f"entity/vsam/{entity}.java"), None)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    m = _ID.search(text)
    if m is None:
        return None
    kind, jtype, var = m.group(1), m.group(2), m.group(3)
    lines = [f"    private static {jtype} id_{entity}(byte[] rec) {{", "        Storage s = Storage.of(rec);"]
    if kind == "Id":
        f = next((x for x in _FIELD.finditer(text) if x.group(7) == var), None)
        it = _sized(f) if f is not None else None
        if f is None or it is None:
            return None
        value = _value(jtype, factory(it, "s", f.group(4)))
        if value is None:
            return None
        lines.append(f"        return {value};")
    else:
        key = next(java_root.rglob(f"entity/vsam/{jtype}.java"), None)
        if key is None:
            return None
        lines.append(f"        {jtype} k = new {jtype}();")
        fields = list(_FIELD.finditer(key.read_text(encoding="utf-8")))
        if not fields:
            return None
        for f in fields:
            it = _sized(f)
            if it is None:
                return None
            value = _value(f.group(6), factory(it, "s", f.group(4)))
            if value is None:
                return None
            name = f.group(7)
            lines.append(f"        k.set{name[0].upper()}{name[1:]}({value});")
        lines.append("        return k;")
    lines += ["    }", ""]
    return IdMethod(entity, jtype, lines)
