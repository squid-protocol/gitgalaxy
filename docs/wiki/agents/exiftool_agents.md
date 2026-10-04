---
description: "You are operating within `exiftool`, the industry-standard Perl library and command-line application for reading, writing, and editing meta information..."
---
# AGENTS.md: exiftool Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `exiftool`, the industry-standard Perl library and command-line application for reading, writing, and editing meta information in a wide variety of files. The execution logic is overwhelmingly dominated by Perl, with a massive amount of static HTML documentation.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 10.249. The network topology demonstrates a completely flat structure (Modularity: 0.0, Assortativity: 0.0). This signifies a monolithic, single-point-of-entry architecture where the core logic is intentionally centralized into massive standalone scripts (`exiftool` and `windows_exiftool`) rather than distributed across deeply nested module hierarchies.
* **Core Rule:** Do NOT attempt to enforce modern, highly decoupled micro-module architectures on the core executables. ExifTool is designed for portability and standalone execution; aggressive abstraction or splitting of the main script violates its distribution constraints.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core directory traversal and serialization routines (`ScanDir`, `FormatXML`, `EscapeJSON` within the main `exiftool` script) operate at extreme O(2^N) recursive time complexities in static analysis. You MUST NOT introduce unbounded recursive loops, heavy regex backtracking, or synchronous blocking calls in the hot paths of file scanning or metadata extraction.
* **Orchestrator Fragility:** The main `exiftool` script is a highly fragile orchestrator. It manages complex argument parsing (e.g., `-stay_open`), file I/O, and dispatches to specific tag parsing logic. Any changes to argument handling or the `ProcessFiles` routing require rigorous verification against a wide array of binary file formats.
* **Avoid Dead Code Pruning:** The test files (`t/*.t`) and format specifications (`fmt_files/`, `arg_files/`) contain logic or configurations that may appear unreferenced. DO NOT autonomously attempt to prune or format these files. ExifTool relies on dynamic dispatch and format-specific binary parsing where dependencies are not statically visible.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream regression testing (against thousands of image/binary formats) before modifying the structural signatures, regex patterns, or public APIs of these files:
* `exiftool` (Highest Cumulative Risk: 690.89, Massive Structural Mass: 9352.08, 100% Churn. The absolute core of the application).
* `windows_exiftool` (Massive Structural Mass: 3565.4, 100% Churn. The Windows-specific standalone wrapper).
* `build_geolocation` (High Cumulative Risk: 544.85. Key Person Silo).
* `t/ExifTool.t`, `t/Writer.t`, `t/XMP.t` (Critical verification orchestrators mapping to the primary test suites).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Because ExifTool's primary purpose is parsing untrusted, potentially malformed binary data and images from the wild, the core `exiftool` script possesses a 100% Exposure score for Exploit Generation. You MUST ensure that any new metadata parsing logic employs strict bounds checking, handles malformed lengths gracefully, and strictly sanitizes outputs (e.g., utilizing `EscapeJSON` and `CleanXML`) to prevent downstream injection attacks in systems consuming ExifTool output.
2. **Binary Anomalies:** X-Ray analysis identified 12 binary anomalies. These are likely deliberate malformed files or edge-case payloads used in the test suite (`t/images/`). Do not alter or remove these binary test fixtures.
3. **Weaponizable Injection Vectors:** The documentation (`html/index.html`) flagged for weaponizable injection vectors. Ensure that any dynamic generation of documentation or release notes does not evaluate untrusted variables.

## 5. Environmental Tooling (The Oracle)
Do not guess binary offset behaviors, hallucinate Exif tag specifications, or rely on generalized Perl knowledge to determine blast radius within this highly specialized metadata engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
