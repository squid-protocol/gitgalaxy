# COBOL Refactoring Controller

> **File Reference:** [`gitgalaxy/cobol_refractor_controller.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/cobol_refractor_controller.py)

> **Architecture: Hybrid Intermediate Representation (IR) State Manager**
>
> **Summary:** The COBOL Refactoring Controller is the primary orchestration engine for the legacy modernization suite. It scans procedural COBOL codebases, extracts deterministic business logic, and converts it into a standardized JSON Intermediate Representation (IR). 
>
> **Memory Optimization:** To handle large enterprise legacy codebases efficiently, the controller utilizes an adaptive hybrid state manager. Upon launch, it scans repository size; if the volume exceeds safe memory thresholds (>2,000 files or >200 MB), it automatically shifts IR storage from RAM to a localized SQLite database to prevent Out-Of-Memory (OOM) failures.

## Three-Phase Extraction Pipeline

The pipeline processes each legacy module through a shared-state architecture to ensure complete logic extraction during modernization.

### Phase 0: Lexical Sanitization
The engine runs lexical patcher rules to neutralize legacy syntax pitfalls (such as deprecated `NEXT SENTENCE` directives) before static analysis, ensuring clean syntax tree processing.

### Phase 1: Static Analysis & Code Audit
* **Dead Code Analyzer:** Scans source code to identify orphaned variables and unreachable paragraphs (`x_ray_dead_code`). Identified dead code is recorded in the state manager so downstream code generators omit unused data.
* **Data Lineage Analyzer:** Maps program Input/Output relationships (`extract_lineage`), referencing state data to bypass dead code dependencies.
* **Compliance & Limits Audit:** Scans for structural anomalies, system limit overrides, and unresolved dynamic `CALL` statements (`scan_system_limits`), recording them in a central audit report for manual architectural review.

### Phase 2: Context-Aware Code Generation
* **Schema Generator:** Translates active variable maps into database schemas (JSON and PostgreSQL DDL), omitting orphaned variables to eliminate schema bloat.
* **JCL Script Generator:** Uses dataset lineage to build restricted Job Control Language (JCL) execution scripts.
* **Microservice Business Logic Slicer:** Slices business logic around specific target variables, skipping unreachable code blocks to output isolated JSON business rules.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

