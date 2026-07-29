# Microservice Business Logic Extractor

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_microservice_slicer.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_microservice_slicer.py)
>
> **Architecture: Recursive Data Flow Taint Tracking & Logic Extraction**
>
> **Summary:** The Microservice Logic Extractor isolates specific business rules from monolithic procedural programs. By recursively tracking a target variable through data assignment and computation statements, it extracts only the executable statements relevant to that variable, creating isolated rule slices for microservice refactoring.

## Recursive Data Flow Taint Tracking

Variables in legacy COBOL programs pass state through multiple intermediate variables across different procedural paragraphs. The extractor's `slice_business_logic` function maps these dependencies using multi-pass taint tracking:

* **Assignment Tracking:** Scans procedural statements for assignments (`MOVE`, `ADD`, `SUBTRACT`). If a tainted variable interacts with another variable, the second variable is added to the tainted set.
* **Mathematical Operations:** Parses `COMPUTE` statements (e.g., `COMPUTE X = Y * Z`). If the target variable appears on either side of the assignment, all participating variables are added to the alias set.
* **Multi-Pass Iteration:** Executes multiple passes (default: 3 passes) over the procedural lines to capture multi-level variable aliasing (e.g., Variable A mutates B, which subsequently mutates C).

## Control Flow Context & Dead Code Filtering

The extractor integrates with dead code analysis results (`dead_paras` and `orphaned_vars`) to enforce boundary constraints during extraction:

* **Unused Variable Early Abort:** Checks if the target variable is flagged as dead memory (`orphaned_vars`). If so, the operation aborts immediately (`ORPHANED_MEMORY`) without spending processing cycles.
* **Unreachable Control Flow Masking:** During both taint tracking and code extraction, statements contained within paragraphs identified as unreachable (`dead_paras`) are ignored. This prevents dead code from generating false-positive variable associations.
* **Extracted Statement Generation:** Isolates and returns executable statements referencing any tainted variable, pairing each statement with its line number and containing paragraph name.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

