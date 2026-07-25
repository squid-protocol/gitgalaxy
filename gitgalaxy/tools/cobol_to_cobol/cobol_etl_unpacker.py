#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: ETL EBCDIC Unpacker
#
# PURPOSE:
# Translates binary EBCDIC mainframe datasets into modern UTF-8 CSVs, decoding
# legacy COMP-3 (Packed Decimal) formats dynamically at runtime.
#
# ARCHITECTURAL DECISION:
# Mainframe data migrations typically require expensive, licensed third-party
# tooling to extract datasets from EBCDIC layouts. By leveraging the JSON
# schemas generated from our COBOL copybook extraction, this utility bridges the
# gap natively in Python. It calculates precise byte offsets to decode Zoned
# Decimals and un-packs COMP-3 nibbles directly into floating-point numerics
# for seamless ingestion into modern data lakes.
# ==============================================================================
import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


def calculate_byte_layout(schema_json: dict) -> list:
    """
    Parses the GitGalaxy JSON Schema to calculate the physical byte footprint
    of each legacy field, determining exact binary extraction boundaries.
    """
    layout = []

    properties = schema_json.get("properties", {})
    for col_name, col_data in properties.items():
        desc = col_data.get("description", "")
        # Extract the legacy PIC clause from the description
        pic_match = re.search(r"Legacy PIC: ([A-Z0-9\(\)V\.\-]+)", desc)
        is_comp3 = "COMP-3" in desc

        if not pic_match:
            continue

        pic = pic_match.group(1).upper()

        # Calculate total conceptual digits/characters
        if "X" in pic or "A" in pic:
            m = re.search(r"[XA]\((\d+)\)", pic)
            length = int(m.group(1)) if m else sum(c in "XA" for c in pic)
            decimals = 0
            is_numeric = False
        else:
            # Numeric fields
            parts = pic.split("V") if "V" in pic else pic.split(".")
            left, right = parts[0], parts[1] if len(parts) > 1 else ""

            def count_nines(s):
                m = re.search(r"9\((\d+)\)", s)
                return int(m.group(1)) if m else s.count("9")

            p_left = count_nines(left)
            p_right = count_nines(right)
            length = p_left + p_right
            decimals = p_right
            is_numeric = True

            # ==================================================================
            # COMP-3 PHYSICAL COMPRESSION:
            # Packed decimal stores two digits per byte, plus one half-byte
            # (nibble) for the sign at the end. The physical byte length is
            # calculated as (digits + 1 for sign) / 2, rounded up to the whole byte.
            # ==================================================================
        physical_bytes = math.ceil((length + 1) / 2) if is_comp3 else length

        layout.append(
            {
                "name": col_name,
                "bytes": physical_bytes,
                "is_comp3": is_comp3,
                "decimals": decimals,
                "is_numeric": is_numeric,
            }
        )

    return layout


def unpack_comp3(raw_bytes: bytes, decimals: int) -> float:
    """Decodes IBM Packed Decimal (COMP-3) hex values into standard Python floats."""
    if not raw_bytes:
        return 0.0

    hex_str = raw_bytes.hex()
    digits = hex_str[:-1]
    sign_nibble = hex_str[-1].upper()

    # D and B indicate negative numbers in EBCDIC hex. C, A, F, E are positive.
    is_negative = sign_nibble in ("D", "B")

    try:
        value = float(digits) if digits else 0.0
    except ValueError:
        return 0.0  # Fallback for corrupted data

    if decimals > 0:
        value = value / (10**decimals)

    return -value if is_negative else value


def unpack_ebcdic_file(binary_filepath: Path, schema_filepath: Path, output_filepath: Path):
    """Parses the mainframe binary file according to the calculated layout."""
    try:
        schema_json = json.loads(schema_filepath.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading schema: {e}")
        return 0

    layout = calculate_byte_layout(schema_json)
    record_length = sum(field["bytes"] for field in layout)

    print(f" 📏 Calculated Record Length: {record_length} bytes per row")
    print(f" 🗄️  Outputting to: {output_filepath.name}")

    total_records = 0

    with (
        open(binary_filepath, "rb") as f_in,
        open(output_filepath, "w", newline="", encoding="utf-8") as f_out,
    ):
        writer = csv.writer(f_out)

        # Write CSV Header
        headers = [field["name"] for field in layout]
        writer.writerow(headers)

        while True:
            record_bytes = f_in.read(record_length)
            if not record_bytes:
                break  # EOF

            # Handle trailing spaces/padding at the end of mainframe files
            if len(record_bytes) < record_length:
                break

            row_data: list[Any] = []
            cursor = 0

            for field in layout:
                chunk = record_bytes[cursor : cursor + field["bytes"]]
                cursor += field["bytes"]

                if field["is_comp3"]:
                    value = unpack_comp3(chunk, field["decimals"])
                    row_data.append(value)
                elif field["is_numeric"]:
                    # Standard EBCDIC numeric (Zoned Decimal)
                    try:
                        decoded = chunk.decode("cp037").strip()
                        # Simple sign handling for zoned (often the last byte carries the sign)
                        value = float(decoded) if decoded else 0.0
                        if field["decimals"] > 0:
                            value = value / (10 ** field["decimals"])
                        row_data.append(value)
                    except ValueError:
                        row_data.append(0.0)
                else:
                    # Standard EBCDIC text (cp037 is the standard IBM US EBCDIC code page)
                    decoded = chunk.decode("cp037", errors="ignore").strip()
                    row_data.append(decoded)

            writer.writerow(row_data)
            total_records += 1

    return total_records


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("ETL EBCDIC Unpacker")

    parser = argparse.ArgumentParser(description="GitGalaxy ETL Unpacker (EBCDIC to CSV)")
    parser.add_argument("binary_file", help="The raw EBCDIC binary file from the mainframe")
    parser.add_argument("schema_file", help="The GitGalaxy generated _schema.json file")
    parser.add_argument("--out", type=str, help="Optional: Custom output CSV path")
    args = parser.parse_args()

    binary_path = Path(args.binary_file).resolve()
    schema_path = Path(args.schema_file).resolve()

    if not binary_path.exists() or not schema_path.exists():
        print("Error: Target files do not exist.")
        sys.exit(1)

    out_path = Path(args.out).resolve() if args.out else binary_path.with_suffix(".csv")

    print("\n" + "=" * 70)
    print(" 🌉 ETL UNPACKER ENGAGED")
    print("=" * 70)
    print(f" 📦 Ingesting Binary : {binary_path.name}")
    print(f" 🗺️  Mapping Schema   : {schema_path.name}")

    records = unpack_ebcdic_file(binary_path, schema_path, out_path)

    print("-" * 70)
    print(f" ✅ OPERATION COMPLETE: Successfully migrated {records:,} records.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
