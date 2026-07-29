# Relational Database & JSON Schema Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_schema_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_schema_forge.py)

## Engineering Summary
The Relational Database & JSON Schema Generator translates legacy memory-bound structure definitions into modern database and application schemas. It solves the problem of data interoperability during modernization by automatically converting byte-mapped `DATA DIVISION` declarations into strongly-typed structures for downstream storage and API consumption. This subsystem is a key data transformation component in GitGalaxy, bridging static analysis of legacy code with cloud-native data representations. It is commonly referred to within the project as the Cloud Schema Forge.

## Purpose
To automatically generate PostgreSQL Data Definition Language (DDL) scripts and REST-compliant JSON Schemas from COBOL `DATA DIVISION` byte-mapped definitions (`PIC` clauses and usage specifiers).

## Problem Being Solved
Legacy systems define data structures using exact memory bytes, fixed-point representations, and specialized annotations (like `OCCURS DEPENDING ON`), which are fundamentally incompatible with modern relational databases and JSON APIs. Manually translating these structures is error-prone and scales poorly.

## Design
### Picture Clause Data Type Translation
The parser inspects COBOL `PIC` declarations (`parse_cobol_picture`) and maps legacy memory bounds to SQL and JSON data types:
* **Alphanumeric & Text:** Converts `PIC X(n)` or `PIC A(n)` to SQL `VARCHAR(n)` and JSON `string`.
* **Integer Types:** Analyzes numeric string lengths (`PIC 9(n)`):
  * $n \le 4$: Maps to `SMALLINT` and JSON `integer`.
  * $5 \le n \le 9$: Maps to `INTEGER` and JSON `integer`.
  * $n \ge 10$: Maps to `BIGINT` and JSON `integer`.
* **Fixed-Point Decimal Types:** Splits clauses containing `V` or `.` (e.g., `PIC S9(7)V99`) into integer and fractional digit counts, mapping them to SQL `DECIMAL(precision, scale)` and JSON `number`.

### Dead Code Filtering & Data Structure Parsing
The generator processes files (`forge_schemas`) to build relational tables:
* **Structural Noise Filtering:** Ignores `FILLER` declarations (unnamed byte allocations) and `88`-level condition names (boolean expressions).
* **Unused Variable Exclusion:** Checks variable names against static analysis dead memory results (`ignore_vars`) to drop unused fields, preventing unnecessary columns in generated database tables.
* **Specialized Storage Annotations:** 
  * **Dynamic Arrays:** Detects `OCCURS DEPENDING ON` clauses (variable-length arrays) and appends warning comments recommending PostgreSQL `JSONB` data types.
  * **Packed Decimals:** Identifies binary-compressed fields (`COMP-3` / `PACKED-DECIMAL`) and adds inline SQL comments to inform downstream developers of packed storage origins.

## Pipeline Integration
**Inputs:** COBOL source files (`DATA DIVISION`), dead memory static analysis results.
**Outputs:** PostgreSQL DDL scripts, JSON Schemas.
**Dependencies:** Upstream static analysis dead code flags.

**Flow:**
COBOL Source + Dead Code Flags -> Cloud Schema Forge -> DDL & JSON Schemas

## Tradeoffs
* **Standard SQL Types vs Exact Precision Bounds:** Mapping COBOL's exact memory bounds to generalized SQL types (`INTEGER`, `BIGINT`) rather than attempting custom constraint mapping ensures native compatibility and optimization in relational databases, sacrificing exact byte-level storage replication.
* **Comment Annotations vs Automated Relational Refactoring:** Choosing to annotate complex legacy structures (like packed decimals and dynamic arrays) via inline comments rejects automatic multi-table normalization. This avoids automated structural guessing, passing responsibility to downstream developers for safer schema design.

## Limitations
* Does not automatically refactor unstructured legacy flat files into normalized relational schemas.
* Heuristic handling of arrays requires manual developer intervention to convert to `JSONB` or separate relational tables.

## Performance Notes
Processing depends on static mapping of text to type definitions, running efficiently in linear time over large codebases without complex graph traversals.

## Future Work
* Full automatic normalization of array definitions into distinct tables with foreign key constraints.
* Built-in support for generating MongoDB or Elasticsearch index schemas alongside relational databases.

## Related Components
* Static Analysis Engine

