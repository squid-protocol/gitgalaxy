# Entity & Memory Mapping

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py)

> **Architecture: Strict Memory Boundary Enforcement & JPA Entity Mapping**
>
> **Summary:** The Java Spring Entity Generator (`cobol_to_java_spring_forge.py`) translates extracted JSON schemas into standard Spring Boot JPA Entities (`@Entity`). Because COBOL uses explicit byte-level memory layouts that do not exist natively in Java or relational databases, the generator applies specialized JPA annotations to represent legacy memory constraints accurately.

## Memory Overlay Resolution (REDEFINES)

In COBOL, the `REDEFINES` clause allows multiple variables to occupy the exact same physical memory address. Relational databases do not support overlapping columns natively.

When the entity generator detects a `redefines` constraint in the schema, it maps the primary variable to a persistent database column while mapping the redefined alias with `@Transient`. This makes the alias available to runtime business logic without creating duplicate, redundant columns in the SQL schema.

## Array Generation (OCCURS)

Legacy `OCCURS` clauses define fixed-length arrays within data records. The generator translates these into Java `List<T>` fields, automatically annotating them with `@ElementCollection` and `@CollectionTable`. It wires foreign key join columns to ensure normalized array elements reference the parent entity's primary key (`sys_id`).

## Financial Precision (PIC Clauses)

The generator parses legacy `PIC` (Picture) clauses to enforce exact structural boundaries on JPA columns:
* **Strings (`PIC X` / `PIC A`):** Extracts byte length and maps to `@Column(length = N)`.
* **Decimals (`PIC S9(7)V99` / `PIC Z`):** Calculates integer and fractional digit counts, mapping them to Java `BigDecimal` fields with `@Column(precision = P, scale = S)` annotations.

## Java Syntax & Naming Sanitization

To ensure all generated Java entities compile cleanly without syntax errors:
1. **CamelCase Conversion:** Converts hyphenated legacy names (`CUSTOMER-NAME`) to standard Java camelCase (`customerName`).
2. **Numeric Prefixing:** Java identifiers cannot begin with a number. Legacy variables starting with digits (e.g., `1099-FORM`) are automatically prefixed (e.g., `v1099Form`).
3. **Reserved Keyword Shielding:** If a legacy variable name collides with a Java reserved keyword (such as `class`, `public`, `return`, `new`), the generator appends a `Val` suffix (e.g., `classVal`) to guarantee compilation.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

