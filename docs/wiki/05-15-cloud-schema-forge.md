# Relational Database & JSON Schema Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_schema_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_schema_forge.py)
>
> **Architecture: Multi-Target DDL & Schema Mapping**
>
> **Summary:** The Cloud Schema Generator converts COBOL `DATA DIVISION` byte-mapped definitions (`PIC` clauses and usage specifiers) into modern relational database structures. It outputs PostgreSQL Data Definition Language (DDL) scripts and REST-compliant JSON Schemas.

## Picture (`PIC`) Clause Data Type Translation

The parser inspects COBOL `PIC` declarations (`parse_cobol_picture`) and maps legacy memory bounds to SQL and JSON data types:

* **Alphanumeric & Text:** Converts `PIC X(n)` or `PIC A(n)` to SQL `VARCHAR(n)` and JSON `string`.
* **Integer Types:** Analyzes numeric string lengths (`PIC 9(n)`):
  * $n \le 4$: Maps to `SMALLINT` and JSON `integer`.
  * $5 \le n \le 9$: Maps to `INTEGER` and JSON `integer`.
  * $n \ge 10$: Maps to `BIGINT` and JSON `integer`.
* **Fixed-Point Decimal Types:** Splits clauses containing `V` or `.` (e.g., `PIC S9(7)V99`) into integer and fractional digit counts, mapping them to SQL `DECIMAL(precision, scale)` and JSON `number`.

## Dead Code Filtering & Data Structure Parsing

The generator processes files (`forge_schemas`) to build relational tables:

* **Structural Noise Filtering:** Ignores `FILLER` declarations (unnamed byte allocations) and `88`-level condition names (boolean expressions).
* **Unused Variable Exclusion:** Checks variable names against static analysis dead memory results (`ignore_vars`) to drop unused fields, preventing unnecessary columns in generated database tables.
* **Specialized Storage Annotations:** 
  * **Dynamic Arrays:** Detects `OCCURS DEPENDING ON` clauses (variable-length arrays) and appends warning comments recommending PostgreSQL `JSONB` data types.
  * **Packed Decimals:** Identifies binary-compressed fields (`COMP-3` / `PACKED-DECIMAL`) and adds inline SQL comments to inform downstream developers of packed storage origins.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

