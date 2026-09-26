# ==============================================================================
# GitGalaxy Tool: shared pieces of the skeleton-driven Java forges (#3657)
#
# PURPOSE:
# What the transaction (#3615), call (#3616) and repository (#3617) forges -- and
# the schema forge -- share: COBOL -> Java type and identifier mapping, the
# field-testing status text every generated artifact cites, merging the service
# extras each forge contributes, and one registry of generated class names so two
# forges can never emit the same simple name (a service importing both would not
# compile).
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TraceEntry:
    """One generated artifact (#3650): its Java file and symbol, and the facts and TODOs behind it."""

    file: str  # relative to the generated project root
    symbol: str  # `Class`, `Class#method` or `Class#field`
    kind: str
    facts: list[dict]  # each: source (file[:line]), section, ledger_field, field_testing (+ detail)
    todos: list[str] = field(default_factory=list)


class TraceLog:
    """The traceability manifest the skeleton forges fill as they plan (#3650).

    Facts name the skeleton `section` they came from; `record` fills in that section's
    ledger field and its field-testing status from ONE source (`ledger_of`, the skeleton
    exporter's section -> ledger field maps, and `confidence`, the shipped field-testing
    record), so every citation is consistent. A symbol recorded twice is kept once, and a
    class-level entry is named after its class."""

    def __init__(self, ledger_of: dict[str, str] | None = None, confidence: dict | None = None) -> None:
        self.entries: list[TraceEntry] = []
        self.ledger_of = ledger_of or {}
        self.confidence = confidence or {}
        self._seen: set[tuple] = set()

    def _fact(self, fact: dict) -> dict:
        ledger = self.ledger_of.get(fact.get("section", ""), fact.get("ledger_field"))
        rec = self.confidence.get(ledger or "", {})
        status = status_text({"field_testing": rec.get("status", "untested"),
                              "tested_on_public": rec.get("tested_on_public", 0),
                              "tested_on_private": rec.get("tested_on_private", 0)})  # fmt: skip
        return {**fact, "ledger_field": ledger, "field_testing": status}

    def record(self, file: str, symbol: str, kind: str, facts: list[dict], todos: list[str] | None = None) -> None:
        if symbol == "Class":
            symbol = file.rsplit("/", 1)[-1].removesuffix(".java")
        # the same symbol backed by other COBOL lines is another finding (#3651: a service's unchecked RESPs)
        seen = (file, symbol, kind, tuple(f.get("source", "") for f in facts))
        if seen in self._seen:
            return
        self._seen.add(seen)
        self.entries.append(TraceEntry(file, symbol, kind, [self._fact(f) for f in facts], list(todos or [])))

    def as_dict(self, generated_from: dict) -> dict:
        sorted_entries = sorted(self.entries, key=lambda e: (e.file, e.symbol))
        by_kind: dict[str, int] = {}
        for e in sorted_entries:
            by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
        return {
            "version": 1,
            "generated_from": generated_from,
            "artifacts": [
                {
                    "file": e.file,
                    "symbol": e.symbol,
                    "kind": e.kind,
                    "facts": e.facts,
                    "todos": e.todos,
                }
                for e in sorted_entries
            ],
            "summary": {
                "artifacts": len(sorted_entries),
                "facts": sum(len(e.facts) for e in sorted_entries),
                "todos": sum(len(e.todos) for e in sorted_entries),
                "by_kind": by_kind,
            },
        }


def java_path(package: str, subpackage: str, cls: str) -> str:
    parts = ["src", "main", "java"]
    if package:
        parts.extend(package.split("."))
    if subpackage:
        parts.extend(subpackage.split("."))
    parts.append(f"{cls}.java")
    return "/".join(parts)


# COBOL variable names that are protected keywords in Java (or would start with a
# digit); the field renderer sanitizes against these so the output always compiles.
_RESERVED_VARS = {
    "class",
    "static",
    "public",
    "private",
    "protected",
    "return",
    "new",
    "system",
    "default",
    "enum",
    "interface",
    "void",
    "try",
    "catch",
    "finally",
    "import",
    "package",
    "super",
    "this",
    "const",
    "goto",
    "byte",
    "int",
    "char",
    "short",
    "long",
    "float",
    "double",
    "boolean",
    "null",
    "true",
    "false",
}


def java_identifier(col_name: str) -> str:
    """The sanitized camelCase Java field name for a COBOL column.

    COBOL names use hyphens, Java keywords and leading digits freely; we normalise
    so the generated field is always a legal, non-colliding Java identifier.
    """
    # Replace hyphens with underscores before splitting to catch all legacy variations
    clean_col = col_name.lower().replace("-", "_")
    parts = clean_col.split("_")
    camel_name = parts[0] + "".join(word.title() for word in parts[1:])

    # Java variables cannot start with a number. Prefix with 'v'.
    if camel_name and camel_name[0].isdigit():
        camel_name = "v" + camel_name

    if camel_name in _RESERVED_VARS:
        camel_name += "Val"
    return camel_name


# Checked after the `(n)` repeat counts are stripped, so anything but 9 S V P is an editing symbol
# (Z , . + - * $ CR DB B / and the insertion 0): a numeric-edited PIC is display text.
_EDITED = re.compile(r"[^9SVP]")


def _digits_and_scale(pic: str) -> tuple[int, int]:
    """(digit positions, positions after V) of a numeric PIC: `S9(7)V99` -> (9, 2)."""
    expanded = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())
    whole, _, frac = expanded.partition("V")
    return whole.count("9") + frac.count("9"), frac.count("9")


def _pli_java_type(cls: str | None, pic: str, usage: str) -> str:
    """#3720: a PL/I item's Java type. A picture repeats by PREFIX (`(5)9V99`, not COBOL's
    `9(5)`); FIXED DEC(p,q) / FIXED BIN(p,q) carry their precision in the type (FIXED DEC
    defaults to (5,0), FIXED BIN to (15,0)); a BIT(1) is a flag; a POINTER / OFFSET / HANDLE
    is an address -- opaque outside the region, kept as its value."""
    if cls == "F":
        return "Double"
    if cls == "A":
        return "Long"
    if cls == "T":
        m = re.search(r"\bBIT\s*\(\s*(\d+)", usage)
        return "Boolean" if m and m.group(1) == "1" else "String"
    if cls == "9" and pic:
        expanded = re.sub(r"\((\d+)\)(.)", lambda m: m.group(2) * int(m.group(1)), pic.strip("'"))
        if re.search(r"[^9SV]", expanded):
            return "String"  # numeric-edited: a display picture
        whole, _, frac = expanded.partition("V")
        digits, scale = whole.count("9") + frac.count("9"), frac.count("9")
    elif cls in ("P", "B"):
        m = re.search(r"\b(?:FIXED|DEC(?:IMAL)?|BIN(?:ARY)?)\s*\(\s*(\d+)(?:\s*,\s*([+-]?\d+))?", usage)
        digits = int(m.group(1)) if m else (5 if cls == "P" else 15)
        scale = int(m.group(2)) if m and m.group(2) else 0
        if cls == "B":  # binary digits: 31 fit an int, 63 a long
            return "BigDecimal" if scale else "Integer" if digits <= 31 else "Long"
    else:
        return "String"
    if scale or digits > 18:
        return "BigDecimal"
    return "Integer" if digits <= 9 else "Long"


def java_type(fld: dict) -> str:
    """The Java type of one elementary item of a record layout."""
    cls, pic = fld.get("class"), (fld.get("pic") or "").upper()
    if fld.get("dialect") == "pli":
        return _pli_java_type(cls, pic, (fld.get("usage") or "").upper())
    if cls == "F":
        return "Double"
    if cls not in ("9", "P", "B") or not pic:
        return "String"
    if _EDITED.search(re.sub(r"\(\d+\)", "", pic)):
        return "String"  # numeric-edited: a display picture, not a number
    digits, scale = _digits_and_scale(pic)
    if scale or digits > 18:
        return "BigDecimal"
    return "Integer" if digits <= 9 else "Long"


def container_var(name: str) -> str:
    """A Java field for a container name, which may hold any character: `DFHEP.DATA.00001` ->
    `dfhepData00001`."""
    return java_identifier("-".join(w for w in re.split(r"[^A-Za-z0-9]+", name) if w) or "container")


def status_text(section: dict | None) -> str:
    if not section:
        return "untested"
    return (
        f"{section.get('field_testing', 'untested')} ({section.get('tested_on_public', 0)} public / "
        f"{section.get('tested_on_private', 0)} private estates)"
    )


def merge_extras(*parts: dict | None) -> dict | None:
    """One service's extras from the skeleton forges: imports (deduplicated, sorted), injected
    fields, methods, class `annotations` (deduplicated, in order) and `class_doc` lines (#3621)."""
    keys = ("imports", "fields", "methods", "annotations", "class_doc")
    present: list[dict] = [p for p in parts if p and any(p.get(k) for k in keys)]
    if not present:
        return None
    return {
        "imports": sorted({i for p in present for i in p.get("imports", [])}),
        "fields": [f for p in present for f in p.get("fields", [])],
        "methods": [m for p in present for m in p.get("methods", [])],
        "annotations": list(dict.fromkeys(a for p in present for a in p.get("annotations", []))),
        "class_doc": [line for p in present for line in p.get("class_doc", [])],
    }


class ClassNames:
    """Every simple class name the skeleton forges generate, across packages (dto.contract,
    entity.vsam, client, ...). `claim` reserves a name and says whether it was free; each
    forge keeps its own fallback naming for a taken one."""

    def __init__(self) -> None:
        self.taken: set[str] = set()

    def __contains__(self, name: str) -> bool:
        return name in self.taken

    def claim(self, name: str) -> str:
        self.taken.add(name)
        return name
