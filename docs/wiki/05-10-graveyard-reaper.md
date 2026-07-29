# Dead Code & Unused Data Analysis

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_graveyard_finder.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_graveyard_finder.py)
>
> **Architecture: Static Analysis & Unreachable Logic Isolation**
>
> **Summary:** The Deprecated Trails Analyzer performs static analysis on COBOL source files to isolate unused variable declarations in memory and unreachable execution logic in control flow. Identifying unused data structures and dead paragraphs early prevents downstream tools from generating unnecessary database columns or unneeded microservices.

## Inline Copybook Expansion

COBOL variable declarations and record layouts are frequently stored in external copybook files (`.cpy`). Before performing static analysis, the analyzer expands copybooks to obtain the full execution context.

* **Recursive Processing:** Recursively searches for `COPY` statements (up to 3 nesting levels deep) and injects the contents of target copybook files into the source memory buffer.
* **Variable Substitution:** Parses `REPLACING ==OLD== BY ==NEW==` clauses during copybook expansion, performing word-boundary regex substitutions (`re.sub` with negative lookarounds) so the expanded source code matches compiled behavior.

## Phase 1: Unused Memory Variable Analysis

The analyzer splits the COBOL program at the `PROCEDURE DIVISION` header to inspect memory usage:

1. **Declaration Parsing:** Scans the `DATA DIVISION` for variable declarations across level numbers `01` through `49`, `77`, and `88`, while filtering structural noise such as `FILLER` declarations.
2. **Usage Verification:** Performs word-boundary regex scans against the `PROCEDURE DIVISION` to check if declared variables are ever referenced.
3. **Orphaned Memory Isolation:** Flags variables declared in memory but never referenced in execution logic as orphaned variables. This list is passed to downstream schema generators to prevent unused database columns from being created in SQL DDL statements.

## Phase 2: Unreachable Execution Logic Analysis

To identify dead code blocks in the procedural logic, the analyzer evaluates control flow topology:

1. **Paragraph Cataloging:** Scans the `PROCEDURE DIVISION` to record all declared paragraph headers (`^[ \t]{0,11}([A-Z0-9\-]+)\.`).
2. **Entry Point Identification:** Designates the first paragraph in the `PROCEDURE DIVISION` as the main execution entry point.
3. **Control Flow Mapping:** Scans the file for explicit transfer-of-control statements (`PERFORM` and `GO TO`) to map all reachable targets.
4. **Dead Paragraph Detection:** Flags any declared paragraph that is not reachable from the main entry point or jump statements as unreachable logic. Common loop exit labels (such as `*-EXIT`) are excluded. The analyzer also calculates estimated Lines of Code (LOC) saved: `(dead_paragraphs * 10) + orphaned_variables`.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

