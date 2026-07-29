# DAG Architect (Data Lineage)

> **File Reference:** [`gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py)

> **Architecture: Topological Sorting & Data Lineage Extraction**
>
> **Summary:** The Data Lineage DAG Architect (`cobol_dag_architect.py`) parses structural source declarations to map Input/Output data flows across COBOL programs. By statically analyzing dataset file assignments and file access modes, it constructs a Directed Acyclic Graph (DAG) and computes the deterministic execution order for legacy batch workflows.

## Unreachable Code Masking

To prevent false dependencies in the data lineage graph, the lineage extractor (`extract_lineage`) accepts a set of known unreachable paragraphs (`dead_paras`). Before parsing `OPEN` statements in the `PROCEDURE DIVISION`, the engine masks out dead paragraph text with whitespace. This ensures that unused or unreachable legacy logic does not produce false dataset dependency edges.

## Input / Output Intent Mapping

The analyzer maps internal COBOL file control blocks (`SELECT ... ASSIGN TO`) to physical external dataset identifiers (DD names) and classifies access modes:
* **Read Operations:** `OPEN INPUT` declarations register the dataset as a program input dependency.
* **Write Operations:** `OPEN OUTPUT` declarations register the dataset as a program output dependency.
* **Mutation Operations:** `OPEN I-O` and `OPEN EXTEND` declarations register the dataset as both an input requirement and an output modification.

## Topological Sorting & Execution Pipeline

Once data lineage is extracted across the repository, the engine calculates execution ordering using **Kahn's Algorithm**:
1. **In-Degree Calculation:** Computes the number of prerequisite dataset providers required by each program.
2. **Dependency Resolution:** Successively enqueues programs with zero pending prerequisites, constructing a deterministic execution sequence.
3. **Cyclic Dependency Detection:** If circular dataset dependencies exist (e.g., Program A requires output from Program B, while Program B requires output from Program A), the algorithm halts execution and isolates deadlocked program nodes for developer remediation.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

