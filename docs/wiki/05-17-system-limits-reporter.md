# Architectural Anomaly & Boundary Detector

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_system_limits_reporter.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_system_limits_reporter.py)
>
> **Architecture: Static Integrity Scanning & Non-Deterministic Pattern Detection**
>
> **Summary:** The Architectural Anomaly Detector (System Limits Reporter) is a static analysis sensor. It scans COBOL source files for dynamic routing statements, asynchronous event handlers, and macro substitution patterns that break deterministic static analysis and dependency graph resolution.

## Structural Violation Rules

Certain legacy COBOL constructs alter control flow or program memory dynamically at runtime. The detector scans source lines (bypassing comment lines starting with `*` in column 7) using strict regular expression rules (`SYSTEM_LIMIT_RULES`):

### 1. Dynamic Jump Target Alteration (`ALTER_STATEMENT` - `CRITICAL`)
* **Regex Pattern:** `\bALTER\s+[A-Z0-9\-]+\s+TO\s+(?:PROCEED\s+TO\s+)?[A-Z0-9\-]+\b`
* **Architectural Impact:** The `ALTER` statement dynamically overwrites the destination target of a `GO TO` statement at runtime. This invalidates static control flow graphs and makes static data flow analysis unreliable.

### 2. Asynchronous Event Handling (`CICS_ASYNC_JUMP` - `CRITICAL`)
* **Regex Pattern:** `EXEC\s+CICS\s+HANDLE\s+CONDITION`
* **Architectural Impact:** Registers asynchronous condition handlers that intercept runtime events and jump to error-handling paragraphs. Execution flow can bypass normal sequential logic at any point, breaking static topological execution mapping.

### 3. Macro Substitution (`COPY_REPLACING` - `HIGH`)
* **Regex Pattern:** `\bCOPY\s+[\'"]?[A-Z0-9\-]+[\'"]?\s+REPLACING\b`
* **Architectural Impact:** Identifies macro substitution within copybooks, flagging potential drift between static source text and compiled execution logic.

## Integrity Verification Workflow

During analysis pipelines, the detector (`scan_system_limits`) evaluates each file and reports structural integrity:

* **Clean Status:** If no anomalies are detected, the analyzer reports that the target codebase is 100% statically deterministic.
* **Violation Reporting:** If anomalies are detected, the detector formats warnings containing target file name, line number, severity level (`CRITICAL` / `HIGH`), and rule description. These findings are passed to downstream task generators or audit reports to flag files requiring architectural review before modernization.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

