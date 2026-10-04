---
description: "You are operating within the `gnucobol` repository, a free, modern COBOL compiler. Based on the current visibility scope, the scanned architecture is..."
---
# AGENTS.md: gnucobol Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `gnucobol` repository, a free, modern COBOL compiler. Based on the current visibility scope, the scanned architecture is massively dominated by the GNU Autotools build system (M4 - 50.0%), testing orchestration scripts (Perl, Shell), and test definitions. 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly centralized, macro-driven architecture where a few massive orchestrator files (like `configure.ac` and `report.pl`) dictate the entire build and verification pipeline.
* **Core Rule:** Do NOT attempt to "modernize" or decouple the M4 macros or Perl test orchestrators into object-oriented paradigms. This infrastructure relies on standard, legacy GNU build patterns (Autoconf/Automake/Autotest).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core configuration (`AC_DEFUN` macros in `configure.ac`) and Makefile generation (`tests/cobol85/Makefile.module.in`) exhibit recursive or highly complex static analysis signatures (O(N^5) and O(2^N)). You MUST NOT introduce unbounded loops, complex shell variable expansions, or heavy synchronous blocking operations during the build or test configuration phases.
* **Orchestrator Fragility:** The COBOL85 test suite orchestrators (`tests/cobol85/report.pl`, `summary.pl`, `expand.pl`) and execution scripts (`tests/run_prog_manual.sh.in`) are highly fragile. Modifying these Perl/Shell scripts carries a high risk of cascading breaks across the entire test matrix. 
* **Avoid Dead Code Pruning:** Files like `tests/cobol85/Makefile.module.in` (9 orphaned functions) and various M4 test definitions (`.at` files) contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The Autotools toolchain utilizes dynamic macro expansion and implicit variable resolution that bypasses static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream build/test suite verification (`make check`) before modifying the structural signatures, regex patterns, or public APIs of these files:
* `configure.ac` (Massive Structural Mass: 282.74, 100% Doc Risk. Key Person Silo - 85.7% isolated ownership by `sf-mensch`. The absolute core of the build system).
* `tests/cobol85/report.pl` (Highest Cumulative Risk: 399.43, High Data Gravity. Drives the COBOL85 standard compliance test reporting).
* `tests/run_prog_manual.sh.in` (Key Person Silo - 100% isolated ownership by `sf-mensch`. High I/O latency risk).
* `tests/testsuite.src/data_display.at` & `run_extensions.at` (Massive M4 test definitions. Key Person Silos - 100% isolated ownership by `ddeclerck`).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** The `tests/cobol85/expand.pl` script possesses a minor (0.19%) Exposure score for Exploit Generation. Because these scripts process numerous external test definitions and files, ensure that any modifications to file parsing, regex extraction, or shell invocations (`system()`, `qx//`, or backticks in Perl/Shell) strictly sanitize file paths to prevent Command Injection.
2. **Path Resolution:** When modifying `.sh.in` or `Makefile` templates, ensure variable expansions (e.g., `$srcdir`, `$builddir`) are properly quoted to prevent word-splitting vulnerabilities if paths contain spaces.

## 5. Environmental Tooling (The Oracle)
Do not guess M4 macro expansions, hallucinate Perl regex behaviors, or rely on generalized build system knowledge to determine blast radius within this highly specialized GNU toolchain. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
