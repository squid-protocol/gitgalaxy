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
from pathlib import Path
from typing import Optional


def parse_cobol_picture(pic_clause: str) -> dict:
    """Translates a legacy COBOL PIC clause into a modern SQL/JSON data type."""
    if not pic_clause:
        return {"sql": "VARCHAR(255)", "json": "string"}

    pic = pic_clause.upper().strip()

    # Text / Strings: PIC X(50) or PIC A(10)
    if "X" in pic or "A" in pic:
        match = re.search(r"[XA]\((\d+)\)", pic)
        length = match.group(1) if match else sum(c in "XA" for c in pic)
        return {"sql": f"VARCHAR({length})", "json": "string"}

    # Decimals/Money: PIC S9(7)V99
    if "V" in pic or "." in pic:
        parts = pic.split("V") if "V" in pic else pic.split(".")
        left, right = parts[0], parts[1] if len(parts) > 1 else ""

        def count_nines(s):
            m = re.search(r"9\((\d+)\)", s)
            return int(m.group(1)) if m else s.count("9")

        p_left = count_nines(left)
        p_right = count_nines(right)
        total_p = p_left + p_right
        return {"sql": f"DECIMAL({total_p}, {p_right})", "json": "number"}

    # Integers: PIC 9(4)
    if "9" in pic:
        match = re.search(r"9\((\d+)\)", pic)
        length = int(match.group(1)) if match else pic.count("9")
        if length <= 4:
            return {"sql": "SMALLINT", "json": "integer"}
        elif length <= 9:
            return {"sql": "INTEGER", "json": "integer"}
        else:
            return {"sql": "BIGINT", "json": "integer"}

    return {"sql": "TEXT", "json": "string"}


_LEVEL_ENTRY = re.compile(r"\s*(0[1-9]|[1-4][0-9]|66|77|88)\s+(?:([A-Z0-9][A-Z0-9\-]*)(?=\s|$))?(.*)", re.S)
_PIC_CLAUSE = re.compile(r"(?<![A-Z0-9\-])PIC(?:TURE)?\s+(?:IS\s+)?([-A-Z0-9(),.$/*+]+)")
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
    for raw in re.split(r"\.(?=\s|$)", code):
        m = _LEVEL_ENTRY.match(raw)
        if not m:
            continue
        level, name, rest = m.group(1), m.group(2), m.group(3)
        if name in _CLAUSE_WORDS:  # an unnamed item: the "name" is its first clause
            rest, name = f"{name} {rest}", None
        pic = _PIC_CLAUSE.search(rest)
        usage = _USAGE_CLAUSE.search(rest)
        entries.append(
            {
                "level": level,
                "name": name,
                "pic": pic.group(1) if pic else None,
                "usage": usage.group(1) if usage else None,
                "depending": "DEPENDING ON" in re.sub(r"\s+", " ", rest),
            }
        )
    return entries


def forge_schemas(filepath: Path, ignore_vars: Optional[set] = None, corporate_header: str = ""):
    """
    Analyzes a COBOL/Copybook file and generates modern schemas.
    Upgraded to utilize shared IR context to drop unused memory addresses.
    """
    if ignore_vars is None:
        ignore_vars = set()

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore").upper()
    except Exception:
        return None

    # Focus only on the Data Division or raw Copybooks
    if "PROCEDURE DIVISION" in content:
        content = content.split("PROCEDURE DIVISION")[0]
        if "DATA DIVISION" in content:
            content = content.split("DATA DIVISION")[1]

    table_name = filepath.stem.upper().replace("-", "_")
    columns = []
    json_properties = {}

    for entry in data_entries(content):
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
        types = parse_cobol_picture(pic)

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
            "description": f"Legacy PIC: {pic}",
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
    json_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": table_name,
        "type": "object",
        "properties": json_properties,
    }

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
