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
import sys
import re
import json
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

    # Regex to capture: Level, Name, PIC clause (optional), and USAGE (optional)
    pattern = re.compile(
        r"^[ \t]*(?P<level>0[1-9]|[1-4][0-9]|77)[ \t]+"
        r"(?P<name>[A-Z0-9\-]+)"
        r"(?:[ \t]+PIC(?:TURE)?[ \t]+(?P<pic>[A-Z0-9\(\)V\.\-]+))?"
        r"(?:[ \t]+(?:IS[ \t]+)?(?P<usage>COMP(?:-[1-5])?|BINARY|PACKED-DECIMAL))?"
        r".*$",
        re.MULTILINE,
    )

    table_name = filepath.stem.upper().replace("-", "_")
    columns = []
    json_properties = {}

    for match in pattern.finditer(content):
        level = match.group("level")
        name = match.group("name")
        pic = match.group("pic")
        usage = match.group("usage")

        # Skip FILLERs (empty byte spaces) and 88-level conditions (booleans)
        if name == "FILLER" or level == "88":
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
        warning = " -- ⚠️ WARNING: OCCURS DEPENDING ON detected. Use JSONB." if "DEPENDING ON" in match.group(0) else ""

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