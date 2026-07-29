# The SQLite Record Keeper (Relational Graph Database Exporter)

> **File Reference:** [`gitgalaxy/recorders/record_keeper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/record_keeper.py)

The Record Keeper (`record_keeper.py`) is the database serialization module responsible for writing GitGalaxy's in-memory static analysis state into a portable, relational SQLite database (`_galaxy_graph.sqlite`).

While the GPU Recorder generates compressed array payloads for WebGL visualizers, the Record Keeper builds a normalized relational database designed for autonomous AI agents, Retrieval-Augmented Generation (RAG) workflows, and CI/CD analytics pipelines.

---

## Architectural Rationale: SQLite vs. Graph Databases (Neo4j / Cypher)

Earlier code analysis tools often exported dependency graphs into graph databases (such as Neo4j) queried via domain-specific graph query languages (like Cypher). GitGalaxy utilizes native SQLite for three architectural reasons:

### 1. Superior LLM Synergy (Text-to-SQL vs. Text-to-Cypher)
Large Language Models (such as GPT-4o or Claude 3.5) are trained on massive text corpora containing standard SQL syntax. LLMs generate relational JOINs, GROUP BY aggregations, and subqueries with high precision. Conversely, Cypher training samples are far sparser, leading to syntax hallucinations when agents attempt complex graph traversals. SQLite output allows RAG agents to write reliable SQL queries against codebase metadata.

### 2. Zero-Infrastructure Portability
Graph database servers require running containerized services, managing network ports, and provisioning storage volumes. GitGalaxy's SQLite output is a self-contained `.sqlite` file that can be committed, stored as a CI artifact, or queried by lightweight Python engines (`sqlite3`) and WASM browser runtimes without backend database servers.

### 3. Strict Relational Schema Integrity
Code architecture exhibits structured relational properties. Mapping files to functions, and files to dependency edges via foreign keys eliminates property-graph schema ambiguity while enforcing data types and relational integrity.

---

## Relational Database Schema

The Record Keeper extracts in-memory telemetry objects and constructs a normalized SQLite database schema (table names preserve schema compatibility):

* **`stars` (Source File Ledger):** Core table containing primary file metrics, including 18-point risk vector components, total/logic LOC, structural mass, churn frequency, XGBoost threat scores, and PageRank blast radius values.
* **`constellations` (Directory Groups):** Directory-level aggregate metrics, allowing queries against module and package health.
* **`satellites` (Functions & Methods):** Maps extracted functions, methods, and classes to parent file IDs via foreign keys, recording function lines of code, parameter counts, Control Flow ratios, and Big-O time complexity classifications.
* **`dna_hits` (Pattern Trigger Ledger):** Flattened, indexed table recording every static regex pattern hit per file for security audit queries.
* **`inbound_dependencies` & `outbound_dependencies` (Graph Edge Tables):** Bi-directional dependency tables representing graph edges. Allows agents to query blast radius ("who imports this file?") and fragility ("what does this file import?") using SQL `INNER JOIN` operations.

---

## Autonomous Agent & CI/CD Query Workflows

By structuring codebase telemetry into relational SQL tables, the Record Keeper allows automated tools and AI agents to query codebase structure. 

Instead of traversing Abstract Syntax Trees with custom scripts, AI agents can execute SQL queries to retrieve architectural insights, such as identifying core modules with high blast radius metrics, high state volatility, and missing test coverage.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

