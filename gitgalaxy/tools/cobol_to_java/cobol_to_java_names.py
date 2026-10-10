#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Clean-Room Key -> Java Name
#
# PURPOSE:
# One place to turn a clean-room output key into the Java identifiers generated
# from it, so every forge names the same program the same way.
#
# ARCHITECTURAL DECISION (#3221):
# The clean room keys its outputs per path: the program's stem when that stem is
# unique in the repository, else the path under the target flattened with `__`
# (`multiroot__sam__SAM2`) -- see `_output_keys` in cobol_refractor_controller.py
# (#3218). The Java forges used to re-derive their class names from the IR's
# `metadata.file_name` (or a schema's `title`) instead, which throws that
# disambiguation away: two programs named SAM2.cbl both produced Sam2Service.java
# and the later one in filename order silently overwrote the earlier.
#
# Deriving the name from the key -- and only from the key -- restores the
# clean room's one-output-file-per-input-file invariant on the Java side. A key
# that is just a unique stem produces exactly the name the old code produced, so
# only a genuinely colliding program is renamed.
# ==============================================================================
import re
import unicodedata
from pathlib import Path

# `COBOL__SAM2` -> ["COBOL", "SAM2"]; `WS-CUST_REC` -> ["WS", "CUST", "REC"].
_SEPARATORS = re.compile(r"[^A-Za-z0-9]+")
# #3815: the same split for names, but a non-ASCII character is part of a word, not a break: `[^A-Za-z0-9]`
# made `ØKONOMI` the class `Konomi` (and `KONOMI` its twin). Over pure ASCII both splits are identical.
_WORD_BREAKS = re.compile(r"[^A-Za-z0-9\u0080-\U0010FFFF]+")

# #3815: the Unicode categories Java's Character.isJavaIdentifierStart / isJavaIdentifierPart accept (letters,
# letter numbers, currency symbols, connector punctuation; a part adds digits and combining marks). The ignorable
# format controls Java also lets through are invisible, so they are replaced like any other illegal character.
_JAVA_START = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nl", "Sc", "Pc"})
_JAVA_PART = _JAVA_START | {"Nd", "Mn", "Mc"}


def java_start_ok(ch: str) -> bool:
    """Whether `ch` may start a Java identifier."""
    return unicodedata.category(ch) in _JAVA_START


def java_legal_chars(name: str) -> str:
    """#3815: every non-ASCII character Java does not allow in an identifier (CP273 shows `@` as `§`) becomes
    `_` -- replaced, never dropped, so `KUNDE§NR` cannot collapse onto `KUNDENR`. ASCII is left alone: the
    ASCII sanitising each caller already does is what the refraction snapshots pin."""
    return "".join(ch if ch.isascii() or unicodedata.category(ch) in _JAVA_PART else "_" for ch in name)


# #3815: str.lower/title/capitalize map some letters to several (`ß`.title() is `Ss`, `İ`.lower() is `i̇`), which
# changes a name's length and can fold two names into one (`STRASSE-ß` and `STRASSE-SS`). These per-character
# forms keep such a letter as it is; for every other character they give exactly what the str methods give.
def _lower1(ch: str) -> str:
    low = ch.lower()
    return low if len(low) == 1 else ch


def _title1(ch: str) -> str:
    title = ch.title()
    return title if len(title) == 1 else ch


def _cased(ch: str) -> bool:
    return ch.islower() or ch.isupper() or ch.istitle()


def lower_name(text: str) -> str:
    """`text.lower()`, one character per character (#3815)."""
    return "".join(_lower1(ch) for ch in text)


def title_name(word: str) -> str:
    """`word.title()`, one character per character (#3815): a character after a cased one is lowered, any
    other is title-cased, as CPython's str.title does."""
    out = []
    prev_cased = False
    for ch in word:
        out.append(_lower1(ch) if prev_cased else _title1(ch))
        prev_cased = _cased(ch)
    return "".join(out)


def capitalize_name(word: str) -> str:
    """`word.capitalize()`, one character per character (#3815)."""
    return _title1(word[0]) + lower_name(word[1:]) if word else word


# A Java class name that would shadow something every generated file imports.
RESERVED_CLASSES = frozenset(
    {
        "Entity",
        "Class",
        "System",
        "Object",
        "String",
        "Enum",
        "Record",
        "Thread",
    }
)


def output_key(path: Path, suffix: str) -> str:
    """The clean-room key a generated artifact was written under.

    `suffix` is the artifact's trailing tag, e.g. `_ir` for `COBOL__SAM2_ir.json`
    or `_slice` for `COBOL__SAM2_slice.json`. Splitting on `_` does not work: a
    flattened key contains `__`, so `name.split("_")[0]` returns `COBOL`.
    """
    stem = path.stem
    return stem[: -len(suffix)] if suffix and stem.endswith(suffix) else stem


def java_class_base(key: str, prefix: str = "Legacy") -> str:
    """`COBOL__SAM2` -> `CobolSam2`; `SAM1LIB` -> `Sam1lib`; `BNK1CAC` -> `Bnk1cac`.

    A key that is a plain stem yields exactly what `"".join(w.capitalize() ...)`
    over the old program id yielded, which is why non-colliding programs keep
    their current class names.
    """
    # #3815: NFC first, so a name that arrived decomposed (a macOS path) is the same class, and file, as its
    # composed form; national letters stay, and a character Java rejects becomes `_`.
    key = unicodedata.normalize("NFC", key)
    name = java_legal_chars("".join(capitalize_name(word) for word in _WORD_BREAKS.split(key) if word))
    if not name or name[0].isdigit() or not java_start_ok(name[0]) or name in RESERVED_CLASSES:
        # An empty, digit-leading or shadowing name is not a legal or safe class
        # name; `prefix` is what the entity forge already used for the last case.
        name = prefix + name
    # #3815: a prefix before a leading combining mark composes with it (`Legacy` + U+0308 -> `Legacÿ`)
    return unicodedata.normalize("NFC", name)


def java_url_segment(key: str) -> str:
    """The `@RequestMapping` path for a program: `COBOL__SAM2` -> `cobol-sam2`.

    Two programs that share a stem must not share a URL either -- Spring refuses
    to start on an ambiguous mapping.
    """
    return "-".join(word.lower() for word in _SEPARATORS.split(key) if word) or "legacy"


def program_key_from_ir(ir_state: dict, explicit: str | None = None) -> str:
    """`explicit` (the caller's clean-room key) when given, else the IR's own file
    name. The fallback keeps the single-file CLIs and older callers working."""
    if explicit:
        return explicit
    raw = ir_state.get("metadata", {}).get("file_name", "") or ""
    return raw.split(".")[0]


# #4037: SQL names. A COBOL item or record named CURRENT-DATE, USER, ORDER, KEY or YEAR becomes a column or
# table of that name, and the database refuses the DDL ("expected identifier": the table is never created).
# These are the words reserved -- or keywords an identifier may not be -- in the databases the generator
# targets: the SQL standard's core, H2 2.x's keyword list (KEY, VALUE, YEAR, MONTH, DAY among them),
# PostgreSQL's reserved words, and DB2 / MySQL / Oracle ones a COBOL data name plausibly takes.
SQL_RESERVED = frozenset(
    {
        "ACCESS",
        "ADD",
        "ALL",
        "ALTER",
        "ANALYSE",
        "ANALYZE",
        "AND",
        "ANY",
        "ARRAY",
        "AS",
        "ASC",
        "ASYMMETRIC",
        "AUDIT",
        "AUTHORIZATION",
        "BETWEEN",
        "BINARY",
        "BOTH",
        "BY",
        "CALL",
        "CASE",
        "CAST",
        "CHECK",
        "COLLATE",
        "COLLATION",
        "COLUMN",
        "COMMENT",
        "CONCURRENTLY",
        "CONDITION",
        "CONNECT",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT",
        "CURRENT_CATALOG",
        "CURRENT_DATE",
        "CURRENT_PATH",
        "CURRENT_ROLE",
        "CURRENT_SCHEMA",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "CURRENT_USER",
        "CURSOR",
        "DATABASE",
        "DATE",
        "DAY",
        "DEFAULT",
        "DEFERRABLE",
        "DELETE",
        "DESC",
        "DESCRIBE",
        "DISTINCT",
        "DO",
        "DROP",
        "ELSE",
        "ELSEIF",
        "END",
        "EXCEPT",
        "EXEC",
        "EXISTS",
        "FALSE",
        "FETCH",
        "FILE",
        "FOR",
        "FOREIGN",
        "FREEZE",
        "FROM",
        "FULL",
        "FUNCTION",
        "GRANT",
        "GROUP",
        "GROUPS",
        "HAVING",
        "HOUR",
        "IDENTIFIED",
        "IF",
        "ILIKE",
        "IN",
        "INDEX",
        "INITIALLY",
        "INNER",
        "INSERT",
        "INTERSECT",
        "INTERVAL",
        "INTO",
        "IS",
        "ISNULL",
        "JOIN",
        "KEY",
        "KEYS",
        "LATERAL",
        "LEADING",
        "LEFT",
        "LEVEL",
        "LIKE",
        "LIMIT",
        "LOCALTIME",
        "LOCALTIMESTAMP",
        "LOCK",
        "MINUS",
        "MINUTE",
        "MODE",
        "MONTH",
        "NATURAL",
        "NOT",
        "NOTNULL",
        "NULL",
        "NUMBER",
        "OF",
        "OFFSET",
        "ON",
        "ONLY",
        "OPTION",
        "OR",
        "ORDER",
        "OUTER",
        "OVER",
        "OVERLAPS",
        "PARTITION",
        "PLACING",
        "PRIMARY",
        "PROCEDURE",
        "QUALIFY",
        "RANGE",
        "READ",
        "REFERENCES",
        "REGEXP",
        "RETURN",
        "RETURNING",
        "REVOKE",
        "RIGHT",
        "ROW",
        "ROWID",
        "ROWNUM",
        "ROWS",
        "SCHEMA",
        "SECOND",
        "SELECT",
        "SESSION",
        "SESSION_USER",
        "SET",
        "SIMILAR",
        "SIZE",
        "SOME",
        "START",
        "SYMMETRIC",
        "SYSTEM_USER",
        "TABLE",
        "TABLESAMPLE",
        "THEN",
        "TIME",
        "TIMESTAMP",
        "TO",
        "TOP",
        "TRAILING",
        "TRIGGER",
        "TRUE",
        "UESCAPE",
        "UID",
        "UNION",
        "UNIQUE",
        "UNKNOWN",
        "UPDATE",
        "USER",
        "USING",
        "VALUE",
        "VALUES",
        "VARIADIC",
        "VERBOSE",
        "VIEW",
        "WHEN",
        "WHERE",
        "WINDOW",
        "WITH",
        "WRITE",
        "YEAR",
    }
)


def sql_name(name: str) -> str:
    """#4037: a table or column name as it goes inside a JPA annotation's Java string: a reserved word
    quoted (`\\"CURRENT_DATE\\"` -- the database then takes it as a plain identifier, and Hibernate uses the
    quoted name in every statement), anything else unchanged."""
    return f'\\"{name}\\"' if name.upper() in SQL_RESERVED else name
