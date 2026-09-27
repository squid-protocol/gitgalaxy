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
# Decimals and un-packs COMP-3 nibbles directly into exact decimal numerics
# for seamless ingestion into modern data lakes.
#
# #3833: the code page is a parameter (`--code-page`, default cp037), so a German,
# Nordic or French file decodes to its own letters; numbers are decimal.Decimal
# (binary floating point cannot hold 0.10); a zoned or packed field that is not a
# valid number stops the run naming the record and field -- never a silent 0.0.
# ==============================================================================
from __future__ import annotations

import argparse
import codecs
import csv
import json
import math
import re
import sys
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from gitgalaxy.core.ebcdic_codecs import register
from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

DEFAULT_CODE_PAGE = "cp037"
_EBCDIC_DIGITS = bytes(range(0xF0, 0xFA))  # the zone-F digits 0-9: the same bytes on every EBCDIC page


class UnpackError(ValueError):
    """#3833: a field whose bytes are not a valid value of its PIC; the message names where."""


def resolve_code_page(code_page: str) -> str:
    """#3833: the canonical codec name of an EBCDIC code page, or UnpackError. Registers the national
    pages Python lacks (cp277 / cp278 / cp280 / cp284 / cp285 / cp297 / cp1047, #3816) first."""
    register()
    try:
        name = codecs.lookup(code_page).name
    except LookupError as e:
        raise UnpackError(f"--code-page {code_page!r}: not a known code page") from e
    try:
        is_ebcdic = _EBCDIC_DIGITS.decode(name) == "0123456789"
    except UnicodeDecodeError:
        is_ebcdic = False
    if not is_ebcdic:  # e.g. utf-8 or latin-1: zoned digits would not decode
        raise UnpackError(f"--code-page {code_page!r}: not an EBCDIC code page")
    return name


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


def _scaled(negative: bool, digits: str, decimals: int) -> Decimal:
    """#3833: the exact value digits x 10^-decimals, keeping the field's scale (V99 -> 12.50)."""
    return Decimal((1 if negative and digits.strip("0") else 0, tuple(int(d) for d in digits or "0"), -decimals))


def unpack_comp3(raw_bytes: bytes, decimals: int) -> Decimal:
    """Decodes IBM Packed Decimal (COMP-3) into an exact Decimal (#3833: never float).

    Raises UnpackError for a digit nibble above 9 or a sign nibble that is not A-F."""
    hex_str = raw_bytes.hex().upper()
    digits = hex_str[:-1]
    sign_nibble = hex_str[-1:]

    # D and B indicate negative numbers in EBCDIC hex. C, A, F (unsigned), E are positive.
    if (digits and not digits.isdigit()) or sign_nibble not in ("A", "B", "C", "D", "E", "F"):
        raise UnpackError(f"not a valid packed decimal: X'{hex_str}'")
    return _scaled(sign_nibble in ("D", "B"), digits, decimals)


@cache
def _sign_characters(code_page: str) -> tuple[str, str]:
    """The page's 10 positive and 10 negative overpunch characters, looked up once per page."""
    return zoned_sign_characters(code_page)


def unpack_zoned(raw_bytes: bytes, decimals: int, code_page: str = DEFAULT_CODE_PAGE) -> Decimal:
    """#3833: decodes zoned decimal into an exact Decimal. The last byte may carry the sign as an
    overpunch, read from the code page's own sign characters (cp037 `{A-I` / `}J-R`, cp277 `æ` / `å`...).

    Raises UnpackError for anything else: spaces, letters, a sign anywhere but the last byte."""
    text = raw_bytes.decode(code_page)
    positive, negative = _sign_characters(code_page)
    body, last = text[:-1], text[-1:]
    negative_value = False
    if last in positive:
        last = str(positive.index(last))
    elif last in negative:
        last, negative_value = str(negative.index(last)), True
    digits = body + last
    if not digits or not all("0" <= c <= "9" for c in digits):
        raise UnpackError(f"not a valid zoned decimal: {text!r} (X'{raw_bytes.hex().upper()}')")
    return _scaled(negative_value, digits, decimals)


def format_number(value: Decimal) -> str:
    """#3833: a plain decimal string for the CSV -- no exponent, trailing zeros kept to the scale."""
    return format(value, "f")


def unpack_ebcdic_file(
    binary_filepath: Path, schema_filepath: Path, output_filepath: Path, code_page: str = DEFAULT_CODE_PAGE
):
    """Parses the mainframe binary file according to the calculated layout.

    #3833: text and zoned digits decode in `code_page`. A field that is not a valid value raises
    UnpackError naming the record (1-based) and field; there is no lenient mode writing 0.0."""
    code_page = resolve_code_page(code_page)
    try:
        schema_json = json.loads(schema_filepath.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading schema: {e}")
        return 0

    layout = calculate_byte_layout(schema_json)
    record_length = sum(field["bytes"] for field in layout)

    print(f" 📏 Calculated Record Length: {record_length} bytes per row")
    print(f" 🗄️  Outputting to: {output_filepath.name}")
    print(f" 🔤 Code page      : {code_page}")

    total_records = 0
    unfilled = 0  # numeric fields never filled (all spaces / low-values): empty cells

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

                if (field["is_comp3"] or field["is_numeric"]) and chunk.strip(b"\x40\x00") == b"":
                    # #3833: a numeric field of all EBCDIC spaces / low-values was never filled -- an empty
                    # cell (a NULL downstream), counted and reported; neither 0.0 nor a failed run
                    row_data.append("")
                    unfilled += 1
                    continue
                try:
                    if field["is_comp3"]:
                        row_data.append(format_number(unpack_comp3(chunk, field["decimals"])))
                    elif field["is_numeric"]:
                        # Standard EBCDIC numeric (Zoned Decimal), sign overpunched on the last byte
                        row_data.append(format_number(unpack_zoned(chunk, field["decimals"], code_page)))
                    else:
                        # EBCDIC text: the EBCDIC pages map all 256 bytes, so nothing is dropped
                        row_data.append(chunk.decode(code_page).strip())
                except (UnpackError, UnicodeDecodeError) as e:
                    # #3833: bad data is loud -- it used to become a silent 0.0
                    raise UnpackError(f"record {total_records + 1}, field {field['name']}: {e}") from e

            writer.writerow(row_data)
            total_records += 1

    if unfilled:
        print(f" ⚠️  {unfilled} numeric field(s) never filled (all spaces / low-values): written as empty cells")
    return total_records


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("ETL EBCDIC Unpacker")

    parser = argparse.ArgumentParser(description="GitGalaxy ETL Unpacker (EBCDIC to CSV)")
    parser.add_argument("binary_file", help="The raw EBCDIC binary file from the mainframe")
    parser.add_argument("schema_file", help="The GitGalaxy generated _schema.json file")
    parser.add_argument("--out", type=str, help="Optional: Custom output CSV path")
    parser.add_argument(
        "--code-page",
        default=DEFAULT_CODE_PAGE,
        help="EBCDIC code page of the data (#3833), e.g. cp037 (default), cp273, cp277, cp278, cp297, cp1047",
    )
    args = parser.parse_args()

    try:
        code_page = resolve_code_page(args.code_page)
    except UnpackError as e:
        print(f"Error: {e}")
        sys.exit(2)

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

    try:
        records = unpack_ebcdic_file(binary_path, schema_path, out_path, code_page)
    except UnpackError as e:
        # #3833: stop on bad data rather than write a wrong value; the partial CSV is removed
        out_path.unlink(missing_ok=True)
        print(f"Error: {e}")
        sys.exit(1)

    print("-" * 70)
    print(f" ✅ OPERATION COMPLETE: Successfully migrated {records:,} records.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
