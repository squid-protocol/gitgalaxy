#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Cloud Schema Generator
#
# PURPOSE:
# Translates legacy COBOL byte-maps (PIC / COMP-3) into modern PostgreSQL DDL
# and JSON schemas.
#
# ARCHITECTURAL DECISION:
# Mainframe data structures are defined by absolute byte boundaries and packed
# decimal (COMP-3) storage. Cloud databases operate on dynamic types (VARCHAR,
# DECIMAL, BIGINT). This generator maps the legacy PIC clauses to their exact
# modern equivalents. By utilizing the IR state from the Deprecated Trails
# Analyzer, it actively drops abandoned memory declarations, ensuring the new
# cloud schemas are free of legacy bloat.
# ==============================================================================
import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.source_text import read_source
from gitgalaxy.core.special_names import special_names
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import parse_pic_precision


def parse_cobol_picture(
    pic_clause: str, decimal_comma: bool = False, usage: Optional[str] = None, currency_symbols: Iterable[str] = ()
) -> dict:
    """Translates a legacy COBOL PIC clause into a modern SQL/JSON data type. #3910: `currency_symbols` are the
    program's declared PICTURE SYMBOLs (`U` for 'EUR '), each a currency position like `$`."""
    if not pic_clause:
        return {"sql": "VARCHAR(255)", "json": "string"}

    pic = pic_clause.upper().strip()
    # #3816: national text -- PIC N / G, or X / A under USAGE NATIONAL / DISPLAY-1 -- is NVARCHAR (in characters);
    # a numeric PIC 9 USAGE NATIONAL stays a number below.
    wide = (usage or "").upper() in ("NATIONAL", "DISPLAY-1")
    is_national = "N" in pic or "G" in pic or (wide and ("X" in pic or "A" in pic))

    # Text / Strings: PIC X(50) or PIC A(10), national PIC N(10) / G(10)
    if "X" in pic or "A" in pic or is_national:
        match = re.search(r"[XANG]\((\d+)\)", pic)
        length = match.group(1) if match else sum(c in "XANG" for c in pic)
        return {"sql": f"NVARCHAR({length})" if is_national else f"VARCHAR({length})", "json": "string"}

    # #3827: digit positions and scale, the decimal point being `,` under DECIMAL-POINT IS COMMA
    total_p, scale = parse_pic_precision(pic, decimal_comma, currency_symbols)

    if total_p > 0 and ("V" in pic or "." in pic or "," in pic or "Z" in pic or "9" in pic):
        # Decimals/Money
        if scale > 0 or "V" in pic or "." in pic or ("," in pic and decimal_comma):
            return {"sql": f"DECIMAL({total_p}, {scale})", "json": "number"}

        # Integers
        if total_p <= 4:
            return {"sql": "SMALLINT", "json": "integer"}
        elif total_p <= 9:
            return {"sql": "INTEGER", "json": "integer"}
        else:
            return {"sql": "BIGINT", "json": "integer"}

    return {"sql": "TEXT", "json": "string"}


_LEVEL_ENTRY = re.compile(r"\s*(0?[1-9]|[1-4][0-9]|66|77|88)\s+(?:([A-Z0-9][A-Z0-9\-]*)(?=\s|$))?(.*)", re.S)
# #3820: the whole character-string to the first space or `;`, as the engine reads it -- the old
# symbol class knew only `$`, so `PIC £££9.99` (CP285's default currency sign) read as no PIC.
_PIC_CLAUSE = re.compile(r"(?<![A-Z0-9\-])PIC(?:TURE)?\s+(?:IS\s+)?([^\s;]+)")
_USAGE_CLAUSE = re.compile(r"(?<![A-Z0-9\-])(COMP(?:UTATIONAL)?(?:-[1-5])?|BINARY|PACKED-DECIMAL)(?![A-Z0-9\-])")
_CLAUSE_WORDS = frozenset({"PIC", "PICTURE", "REDEFINES", "OCCURS", "VALUE", "VALUES", "USAGE", "COMP", "BINARY"})


def _code_lines(content: str) -> list[str]:
    """Fixed-format lines as code: comment lines dropped, cols 73-80 cut, and the
    cols 1-6 sequence area blanked where column 7 is a blank indicator (so
    `000100 05 X ...` and zopeneditor's `R2     05 X ...` read as `05 X ...`).
    A line that is already a level entry in those columns (free format) is kept."""
    out = []
    for line in content.split("\n"):
        if len(line) > 6 and line[6] in "*/":
            continue
        line = line[:72]
        if re.fullmatch(r"[0-9]{1,6}", line):  # an empty line that carries only its sequence number
            line = ""
        elif (
            len(line) >= 7
            and line[6] == " "
            and re.fullmatch(r"[0-9A-Z ]{6}", line[:6])
            and not re.match(r"\s*(?:0[1-9]|[1-4][0-9]|66|77|88)\s", line[:7])
        ):
            line = " " * 6 + line[6:]
        out.append(line)
    return out


def data_entries(content: str) -> list[dict]:
    """The data description entries of upper-cased DATA DIVISION text, in order.

    #3348: read per ENTRY (a sentence), not per line, so a PIC on the next line,
    a PIC after `REDEFINES X` / `OCCURS n`, and an edited picture
    (`PIC +9(10).99`, `ZZZ,ZZ9`, `$$$9.99`) are all seen. The line reader lost
    every one of those: 385 hand-verified record fields across the three pinned
    corpora. Literal contents are blanked first, so a period inside a VALUE
    literal cannot end the entry.
    """
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import _blank_literals

    code = _blank_literals("\n".join(_code_lines(content)))
    entries = []
    groups: list[tuple[int, str | None]] = []  # #4525: (level, effective usage) of the open groups
    for raw in re.split(r"\.(?=\s|$)", code):
        m = _LEVEL_ENTRY.match(raw)
        if not m:
            continue
        level, name, rest = m.group(1).zfill(2), m.group(2), m.group(3)  # #4626: `1` / `2` read as `01` / `02`
        if name in _CLAUSE_WORDS:  # an unnamed item: the "name" is its first clause
            rest, name = f"{name} {rest}", None
        pic = _PIC_CLAUSE.search(rest)
        usage_match = _USAGE_CLAUSE.search(rest)
        usage = usage_match.group(1) if usage_match else None
        # #4525: a group's USAGE applies to every item under it without one of its own (as the engine)
        lvl = int(level)
        if lvl not in (66, 88):
            while groups and (groups[-1][0] >= lvl or lvl == 77):
                groups.pop()
            effective = usage or (groups[-1][1] if groups else None)
            groups.append((lvl, effective))
            if effective and effective.upper() != "DISPLAY":  # an inherited DISPLAY is the default anyway
                usage = effective
        entries.append(
            {
                "level": level,
                "name": name,
                "pic": pic.group(1) if pic else None,
                "usage": usage,
                "depending": "DEPENDING ON" in re.sub(r"\s+", " ", rest),
            }
        )
    return entries


def forge_schemas(
    filepath: Path, ignore_vars: Optional[set] = None, corporate_header: str = "", declared: Optional[str] = None
):
    """
    Analyzes a COBOL/Copybook file and generates modern schemas.
    Upgraded to utilize shared IR context to drop unused memory addresses.
    #3909: `declared` is the estate's code page for the file (a raw EBCDIC download); None reads it unaided.
    """
    if ignore_vars is None:
        ignore_vars = set()

    try:
        content = read_source(filepath, declared=declared).text.upper()
    except Exception:
        return None

    # #3827: SPECIAL-NAMES sits in the ENVIRONMENT DIVISION, so read it before the cut below
    names = special_names(content)
    decimal_comma = any(sn["clause"] == "DECIMAL-POINT" for sn in names)
    # #3910: the CURRENCY clauses' PICTURE SYMBOLs
    symbols = [sn["symbol"] for sn in names if sn["clause"] == "CURRENCY" and sn["symbol"]]

    # Focus only on the Data Division or raw Copybooks
    # #3533: `PROCEDURE        DIVISION.` (navikt/DSF PLUKKFR) is the same header.
    content = re.sub(r"PROCEDURE[ \t]+DIVISION", "PROCEDURE DIVISION", content)
    if "PROCEDURE DIVISION" in content:
        content = content.split("PROCEDURE DIVISION")[0]
        if "DATA DIVISION" in content:
            content = content.split("DATA DIVISION")[1]

    return render_schemas(
        data_entries(content), filepath.stem.upper(), ignore_vars, corporate_header, decimal_comma, symbols
    )


def render_schemas(
    entries: list[dict],
    table_name: str,
    ignore_vars: Optional[set] = None,
    corporate_header: str = "",
    decimal_comma: bool = False,
    currency_symbols: Iterable[str] = (),
) -> Optional[dict]:
    """The SQL DDL and JSON Schema of a program's data description entries, in source order.

    #3348: `entries` come from this forge's own reader (`data_entries`) or from the
    engine's record_data (the refractor's `engine_schemas`); both carry `level`
    (two digits), `name`, `pic`, `usage` and `depending`.
    """
    ignore_vars = ignore_vars or set()
    # #3910: a declared PICTURE SYMBOL is one character (a sign without one is its own symbol)
    symbols = sorted({sym.upper() for sym in currency_symbols if sym and len(sym) == 1})
    table_name = table_name.upper().replace("-", "_")
    columns = []
    json_properties = {}

    for entry in entries:
        level, name, pic, usage = entry["level"], entry["name"], entry["pic"], entry["usage"]

        # Skip FILLERs (empty byte spaces) and 88-level conditions (booleans)
        if name == "FILLER" or level in ("66", "88") or not name:
            continue

        # 01 levels are usually the table/record name itself
        if level == "01" and not pic:
            table_name = name.replace("-", "_")
            continue

        # Ignore group levels (levels without PICs) for the flat SQL schema
        if not pic:
            continue

        # ======================================================================
        # DEFENSIVE DESIGN (DEPRECATED TRAILS EXCLUSION):
        # Instantly drop the variable if the Deprecated Trails Analyzer proved
        # it is dead memory, preventing cloud database bloat.
        # ======================================================================
        if name in ignore_vars:
            continue

        safe_name = name.replace("-", "_")
        types = parse_cobol_picture(pic, decimal_comma, usage, symbols)

        # ======================================================================
        # ARCHITECTURAL ANOMALY (DYNAMIC MEMORY ARRAY):
        # match.group(0) grabs the full matched string from the regex
        # ======================================================================
        warning = " -- ⚠️ WARNING: OCCURS DEPENDING ON detected. Use JSONB." if entry["depending"] else ""

        # Add notes if it's a legacy packed decimal
        comment = " -- Legacy: COMP-3 (Packed Decimal)" if usage and "COMP-3" in usage else ""

        columns.append(f"    {safe_name.ljust(30)} {types['sql']}{comment}{warning}")
        json_properties[safe_name] = {
            "type": types["json"],
            "description": f"Legacy PIC: {pic}" + (" (DECIMAL-POINT IS COMMA)" if decimal_comma else ""),
        }

    if not columns:
        return None

    # Format the header for SQL
    sql_header = ""
    if corporate_header:
        lines = corporate_header.strip().split("\n")
        sql_header = "-- " + ("\n-- ".join(lines)) + "\n\n"

    # Generate PostgreSQL DDL
    sql_ddl = sql_header + f"CREATE TABLE {table_name} (\n"
    sql_ddl += ",\n".join(columns)
    sql_ddl += "\n);"

    # Generate JSON Schema
    json_schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": table_name,
        "type": "object",
        "properties": json_properties,
    }
    if decimal_comma:  # #3827: the Java forges read the edited PICTUREs by it
        json_schema["decimal_comma"] = True
    # #3910: ... and by the PICTURE SYMBOL letters (a Unicode currency sign is known without it)
    letters = [sym for sym in symbols if unicodedata.category(sym) != "Sc"]
    if letters:
        json_schema["currency_symbols"] = letters

    return {"table": table_name, "sql": sql_ddl, "json": json_schema}


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Cloud Schema Generator")

    parser = argparse.ArgumentParser(description="GitGalaxy Cloud Schema Generator")
    parser.add_argument("target", help="Path to a .cbl or .cpy file to translate")
    parser.add_argument(
        "--format",
        choices=["sql", "json", "both"],
        default="both",
        help="Output format",
    )
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)
    print(f"🔨 GitGalaxy Cloud Schema Generator processing: {target_path.name}...\n")

    # In standalone CLI mode, IR context defaults to an empty set.
    schemas = forge_schemas(target_path)

    if not schemas:
        print("⚠️ No valid data structures found to translate.")
        sys.exit(0)

    if args.format in ["sql", "both"]:
        print("==========================================================")
        print(" 🐘 POSTGRESQL DDL (CLOUD DATABASE SCHEMA)")
        print("==========================================================")
        print(schemas["sql"])
        print("\n")

    if args.format in ["json", "both"]:
        print("==========================================================")
        print(" 🌐 REST API JSON SCHEMA")
        print("==========================================================")
        print(json.dumps(schemas["json"], indent=2))
        print("\n")


if __name__ == "__main__":
    main()
