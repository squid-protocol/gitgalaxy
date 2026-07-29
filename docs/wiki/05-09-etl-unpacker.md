# ETL Unpacker (EBCDIC to CSV)

> **File Reference:** [`gitgalaxy/tools/cobol_to_cobol/cobol_etl_unpacker.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_etl_unpacker.py)

> **Architecture: Binary Data Unpacking & Character Decoding**
>
> **Summary:** The ETL Unpacker (`cobol_etl_unpacker.py`) serves as a data migration utility between legacy mainframe datasets and modern cloud databases. It converts raw EBCDIC binary byte streams into UTF-8 CSV files, parsing Packed Decimal (COMP-3) and Zoned Decimal fields using layout metadata from generated JSON schemas.

## Schema-Driven Record Byte Slicing

Mainframe binary datasets lack row delimiters (such as newlines or commas). Instead, data records are stored as fixed-length byte blocks. 

The unpacker (`calculate_byte_layout`) reads the GitGalaxy JSON Schema (`_schema.json`) to calculate exact field byte boundaries:
* Parses legacy `PIC` clauses to determine conceptual character or numeric length.
* Computes field byte offsets and record row lengths (`record_length`).
* Slices incoming binary streams row-by-row based on calculated byte boundaries.

## Packed Decimal (COMP-3) Decoding

To optimize storage space, mainframes compress numeric values using Packed Decimal (COMP-3) formatting, storing two decimal digits per byte (one per nibble) with the final nibble reserved for sign representation:
* **Byte Size Calculation:** Determines physical byte footprint using `ceil((digits + 1) / 2)`.
* **Sign Nibble Parsing:** Inspects the final nibble of the byte array (`D` or `B` indicate negative values; `C`, `A`, `F`, or `E` indicate positive values).
* **Decimal Scale Application:** Divides the parsed numeric integer by `10^decimals` according to the schema scale specification to produce standard floating-point values (`unpack_comp3`).

## EBCDIC Character Encoding Conversion

Alphanumeric text fields and Zoned Decimal numbers are decoded from raw EBCDIC bytes to UTF-8 text using the standard IBM US EBCDIC code page (`cp037`). This ensures special characters and text formatting are preserved accurately during database migration.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

