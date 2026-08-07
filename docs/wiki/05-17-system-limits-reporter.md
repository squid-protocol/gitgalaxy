# Architectural Anomaly & Boundary Detector

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_system_limits_reporter.py](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/cobol_to_cobol/cobol_system_limits_reporter.py)

## Engineering Summary
The Architectural Anomaly & Boundary Detector is a static analysis sensor that evaluates the deterministic nature of legacy code structures. It solves the problem of unsafe modernization by identifying logic constructs that dynamically alter execution paths or memory states at runtime. This subsystem serves as a critical safety gate in GitGalaxy, ensuring code meets static analysis requirements before being passed to automated dependency mappers or LLM agents. It is commonly referred to as the System Limits Reporter.

## Purpose
To scan COBOL source files for dynamic routing statements, asynchronous event handlers, and macro substitution patterns that break deterministic static analysis and dependency graph resolution.

## Problem Being Solved
Certain legacy structures, such as dynamic control flow alterations, prevent static tools from accurately modeling program behavior. Attempting to modernize or map dependencies on code containing these non-deterministic constructs can result in severe logic drift and catastrophic runtime errors.

## Design
### Structural Violation Rules
The detector scans source lines (bypassing comment lines starting with `*` in column 7) using strict regular expression rules (`SYSTEM_LIMIT_RULES`):

* **1. Dynamic Jump Target Alteration (`ALTER_STATEMENT` - `CRITICAL`)**
  * **Regex Pattern:** `\bALTER\s+[A-Z0-9\-]+\s+TO\s+(?:PROCEED\s+TO\s+)?[A-Z0-9\-]+\b`
  * **Architectural Impact:** The `ALTER` statement dynamically overwrites the destination target of a `GO TO` statement at runtime. This invalidates static control flow graphs and makes static data flow analysis unreliable.

* **2. Asynchronous Event Handling (`CICS_ASYNC_JUMP` - `CRITICAL`)**
  * **Regex Pattern:** `EXEC\s+CICS\s+HANDLE\s+CONDITION`
  * **Architectural Impact:** Registers asynchronous condition handlers that intercept runtime events and jump to error-handling paragraphs. Execution flow can bypass normal sequential logic at any point, breaking static topological execution mapping.

* **3. Macro Substitution (`COPY_REPLACING` - `HIGH`)**
  * **Regex Pattern:** `\bCOPY\s+[\'"]?[A-Z0-9\-]+[\'"]?\s+REPLACING\b`
  * **Architectural Impact:** Identifies macro substitution within copybooks, flagging potential drift between static source text and compiled execution logic.

### Integrity Verification Workflow
During analysis pipelines, the detector (`scan_system_limits`) evaluates each file and reports structural integrity:
* **Clean Status:** If no anomalies are detected, the analyzer reports that the target codebase is 100% statically deterministic.
* **Violation Reporting:** If anomalies are detected, the detector formats warnings containing target file name, line number, severity level (`CRITICAL` / `HIGH`), and rule description. These findings are passed to downstream task generators or audit reports to flag files requiring architectural review before modernization.

## Pipeline Integration
**Inputs:** Unprocessed legacy source files (COBOL).
**Outputs:** Structural anomaly reports, integrity verification statuses.
**Dependencies:** Downstream dependency mappers and task forges rely on this component's output to determine safe execution paths.

**Flow:**
Raw COBOL Source -> System Limits Reporter -> Integrity Reports & Anomaly Flags

## Tradeoffs
* **Regex Scanning vs Abstract Syntax Tree (AST):** The system chooses strict regular expressions over a full AST parser for speed and fault tolerance on incomplete or malformed legacy files, rejecting a heavy compiler front-end. This sacrifices deep semantic understanding for rapid heuristic pattern matching.
* **Binary Severity Categorization:** Grouping limits strictly into `CRITICAL` or `HIGH` rejects a granular risk scoring system, ensuring modernization pipelines fail quickly and explicitly on any `CRITICAL` finding rather than relying on arbitrary thresholds.

## Limitations
* Regular expressions may misidentify text inside string literals if not properly bounded.
* Does not automatically repair or refactor the flagged non-deterministic limits.

## Performance Notes
Operates at $O(N)$ time complexity relative to the number of lines in the source file, allowing for rapid scanning across massive codebases without significant memory overhead.

## Future Work
* Integration with a full language server or AST parser to eliminate false positives in string literals and comments.
* Expansion of rulesets to detect dynamic SQL injection patterns.

## Related Components
* Autonomous Agent Remediation Task Generator
