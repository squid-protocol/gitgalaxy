# JCL Security & Reduction Auditor

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_jcl_auditor.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_jcl_auditor.py)
>
> **Architecture: Execution Intent Parsing & Security Boundary Validation**
>
> **Summary:** The Zero-Trust JCL Auditor is a verification tool that compares generated, program-specific Job Control Language (JCL) scripts against legacy IBM JCL files. It quantifies code bloat reduction and measures the elimination of over-permissioned I/O access boundaries.

## Intent Parsing & Legacy Script Mapping

Legacy mainframe environments often retain multi-step or redundant JCL scripts that execute identical COBOL programs with broad file access rights.

* **Executable Grouping:** The auditor scans legacy JCL files (`.jcl`, `.txt`) and groups them by their target binary (`EXEC PGM=`).
* **Baseline Selection:** When multiple legacy scripts reference the same executable, the auditor designates the largest script (highest line count and dataset allocations) as the baseline for audit comparison.
* **System Component Filtering:** Ignores standard IBM system programs (e.g., `IEFBR14`, `IDCAMS`, `IEBGENER`, `IGYCRCTL`) and system data definitions (e.g., `STEPLIB`, `SYSOUT`, `SYSPRINT`, `SYSUDUMP`, `SYSIN`) to focus exclusively on application data definitions.

## Security & Reduction Metrics Calculation

The auditor compares baseline legacy metrics against modernized JCL files:

* **Code Bloat Reduction:** Measures the net reduction in lines of code achieved by replacing multi-step legacy jobs with focused, single-program scripts (`bloat_reduction_pct`).
* **Over-Permissioned I/O Elimination:** Calculates `excess_dds_blocked` by evaluating datasets defined in legacy JCLs that are omitted from modernized execution scripts. For example, if a legacy JCL allocated 15 datasets but static analysis proves the COBOL program only accesses 3, the 12 unreferenced datasets are flagged as blocked excess permissions (enforcing least privilege).
* **Reporting Options:** Outputs results as a structured CLI report or as raw JSON (`--json`) for automated integration testing pipelines.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

