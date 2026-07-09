# GitGalaxy Recorders: Telemetry & Data Serialization Engine

This directory houses the high-speed data serialization and export engines for GitGalaxy. 

As the final phase of the pipeline, the `recorders` directory is responsible for translating the massive, in-memory topological graphs and structural risk vectors into highly optimized payloads for downstream consumers. GitGalaxy is strictly headless and API-first; these modules ensure the data can be instantly consumed by interactive 3D WebGPU visualizers, autonomous AI coding agents, SIEM pipelines, and enterprise data warehouses.

## Architectural Philosophy & Defensive Engineering

Converting a multi-dimensional graph of 50,000+ files into a portable format presents a severe memory and I/O bottleneck. Standard serialization libraries will duplicate the graph in RAM, triggering immediate OS-level Out-Of-Memory (OOM) kills. The Recorders are defensively engineered to mitigate these constraints:

### 1. Destructive RAM Eviction (Memory Management)
To process monolithic repositories on standard hardware, the `gpu_recorder.py` employs a "Destructive Pivot." Instead of copying data, it systematically `.pop()`s elements from the main Orchestrator arrays to build its new schema, manually invoking Python's Garbage Collector (`gc.collect()`) at phase boundaries. This ensures the pipeline's memory footprint strictly decreases during the export phase, preventing OOM crashes.

### 2. Columnar Pivoting & Text Interning (AoS to SoA)
WebGPU and frontend rendering engines struggle with deeply nested, row-based JSON (Array of Structs). The engine structurally pivots the telemetry into flat, numerical columns (Structure of Arrays). Repetitive metadata—such as file extensions, author names, or diagnostic reasons—are aggressively minified into O(1) integer arrays using Text Interning. This drastically reduces the network payload size and client-side RAM overhead.

### 3. Zero-Overhead Relational Mapping
The `record_keeper.py` bypasses intermediate JSON/CSV dumping entirely. It maps the in-memory Python dictionaries directly into a native SQLite3 database. To prevent I/O deadlocks during massive batch inserts, it explicitly enforces `PRAGMA journal_mode = WAL;` (Write-Ahead Logging) and relaxed synchronous modes, guaranteeing high-speed execution without sacrificing relational integrity.

### 4. Token-Density Optimization for LLMs
Dumping raw telemetry into an LLM context window saturates the agent with noise and wastes tokens. The `llm_recorder.py` acts as a statistical translation layer. It mathematically isolates the repository's structural dependencies (high blast radius), undocumented choke points (high centrality, zero documentation), and cascading mutations (high centrality, high state flux), generating a dense, highly opinionated Markdown brief that maximizes AI comprehension per token.

---

## The Core Pipeline (Exit Strategies)

Each file in this directory represents a specialized data exit strategy, tailored for a specific downstream consumer:

* **`gpu_recorder.py` (The Visual Payload Generator):** Generates the `_gpu.json` payload. It performs the Destructive RAM Eviction and Columnar Pivot, compressing the multi-dimensional graph into a minified manifest built strictly for high-performance WebGPU rendering engines.
* **`record_keeper.py` (The SQL Telemetry Layer):** Generates the `_master.db` artifact. A native SQLite3 recorder that captures the complete forensic state of the scan. It creates a robust, time-series schema designed for Enterprise Data Warehouse (EDW) aggregation, SQL-based security auditing, and delta-scan rehydration.
* **`sarif_recorder.py` (The Enterprise CI/CD Layer):** Generates the `_sarif.json` payload. Translates the XGBoost threat classifications, AI AppSec guardrails, and structural risk thresholds into the industry-standard Static Analysis Results Interchange Format (SARIF 2.1.0), enabling native integration with GitHub Advanced Security and GitLab Ultimate.
* **`sbom_recorder.py` (The Supply Chain Manifest):** Generates the `_sbom.json` payload. Transforms the resolved repository dependency graph into a formalized CycloneDX 1.4 manifest. Integrates a Zero-Trust physical audit to flag locally spoofed or maliciously packed dependencies.
* **`llm_recorder.py` (The AI Context Layer):** Generates the `_llm.md` and `_graph.sqlite` artifacts. It calculates repository-wide statistical metrics (Min/Max/Mean for all 18 risk dimensions) and produces a targeted brief that grants autonomous AI agents (like Claude or Cursor) total ecosystem awareness before they write a single line of code.
* **`audit_recorder.py` (The Compliance & Forensic Layer):** Generates the `_audit.json` log. Designed for compliance, security debugging, and human review. It cryptographically binds the scan to a specific Git Commit Hash (acting as a Structural Health Bill of Materials), decodes the internal XGBoost ML Threat taxonomy, and maps raw integers back to descriptive, enterprise-friendly terminology.

---

## Standard Orchestrator Output
When running the `galaxyscope.py` orchestrator without exclusive flags, the engine automatically routes the centralized RAM state through all recorders, emitting the following standard artifacts for a given target (e.g., `project-name`):

* `project-name_galaxy_gpu.json` (WebGL UI Payload)
* `project-name_galaxy_master.db` (Relational SQL Database)
* `project-name_galaxy_sarif.json` (CI/CD Security Alerts)
* `project-name_galaxy_sbom.json` (CycloneDX Dependency Manifest)
* `project-name_galaxy_audit.json` (Human-Readable Compliance Log)
* `project-name_galaxy_llm.md` (Compressed Context Window Brief)

---

## 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://squid-protocol.github.io/gitgalaxy/), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[GitGalaxy Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** - Deep dives into the mathematics and pipeline architecture.
* 🔭 **[GitGalaxy Visualizer](http://gitgalaxy.io/)** - Render your codebase locally in 3D using WebGPU.
* 📖 **[The blAST Paradigm Wiki](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** - The academic and structural thesis backing the engine.
* ⚙️ **[Language Calibration Standards](https://squid-protocol.github.io/gitgalaxy/gitgalaxy/standards/how_to_add_a_language.md)** - Guide to extending the comparative lexical taxonomy.