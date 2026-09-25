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


def java_type(fld: dict) -> str:
    """The Java type of one elementary item of a record layout."""
    cls, pic = fld.get("class"), (fld.get("pic") or "").upper()
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
    """One service's extras from the transaction and call forges."""
    present: list[dict] = [p for p in parts if p and (p.get("imports") or p.get("fields") or p.get("methods"))]
    if not present:
        return None
    imports = sorted({i for p in present for i in p.get("imports", [])})
    fields = [f for p in present for f in p.get("fields", [])]
    methods = [m for p in present for m in p.get("methods", [])]
    return {"imports": imports, "fields": fields, "methods": methods}


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
