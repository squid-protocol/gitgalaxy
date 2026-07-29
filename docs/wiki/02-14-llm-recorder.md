# The LLM Recorder (AI Context Exporter)

> **File Reference:** [`gitgalaxy/recorders/llm_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/llm_recorder.py)

The LLM Recorder (`llm_recorder.py`) formats static analysis telemetry into token-dense artifacts optimized for AI context windows, Retrieval-Augmented Generation (RAG) pipelines, and autonomous coding agents. Instead of requiring Large Language Models to parse raw, verbose JSON structures, this module generates structured markdown briefs and a relational SQLite database.

---

## Bi-Directional Dependency Graphing

Before generating output artifacts, the recorder builds a comprehensive reverse-dependency map across all source files, converting raw import statements into a bi-directional graph:

* **Load-Bearing Modules (Blast Radius):** Identifies files with high inbound dependency counts ("Imported By"). Changes to these core components present significant downstream regression risks.
* **Orchestrator Modules (Fragility Index):** Identifies files with high outbound dependency counts ("Imports"). These modules assemble multiple external packages and are sensitive to upstream API modifications.

---

## Token-Dense Markdown Brief (`_galaxy_llm.md`)

The primary text output is a token-compressed Markdown document (`_galaxy_llm.md`) designed to fit within standard LLM context windows (such as Claude 3.5 or GPT-4o). It structures codebase analysis into clear, prioritized sections:

### 1. Security & Malware Summary
Positions XGBoost Machine Learning malware detection findings at the top of the brief. Flagged files and confidence scores alert autonomous agents if hostile payloads or compromised dependencies exist in the repository.

### 2. Analysis Framing & Guidelines
Provides prompt engineering instructions, directing the AI model to evaluate architectural risk objectively using calculated heuristic metrics rather than subjective code style preferences.

### 3. Repository Architecture & AI Topology
Provides global repository metrics, including:
* **Network Graph Topology:** Modularity, assortativity, and cyclic dependency density.
* **Architectural Z-Scores:** Measures structural deviation from language standards.
* **AI Framework Integration Topology:** Identifies vector stores, tool-calling APIs, and machine learning framework footprints (e.g., PyTorch, TensorFlow, LangChain).

### 4. Code Anomalies & Architectural Drift
Highlights files exhibiting low global drift but high local drift—modules that match repo file structure globally but violate standard coding conventions of their native language.

### 5. Priority Refactoring Targets
Cross-references structural metrics to provide actionable engineering targets:
* **Volatility Hotspots:** Modules exhibiting both high revision churn and high risk scores.
* **Single-Maintainer Load Risks:** Core modules modified primarily by a single contributor (high impact combined with siloed knowledge).
* **Systemic Graph Bottlenecks:** Modules positioned along critical shortest paths between sub-systems (high betweenness combined with high state flux).

### 6. AI Application Security Vulnerabilities
Summarizes vulnerabilities specific to generative AI implementations, focusing on Agentic Remote Code Execution (RCE) risks (LLM outputs flowing into OS subprocess calls) and prompt injection surfaces.

---

## Relational Knowledge Graph (`_galaxy_graph.sqlite`)

For agentic frameworks that leverage SQL queries (such as LangChain or AutoGen), the recorder generates a relational SQLite database (`_galaxy_graph.sqlite`).

### Relational Database Schema
Autonomous agents execute SQL queries against the following database tables (table names retain schema compatibility):

* **`stars`**: Core file telemetry, including risk vectors, lines of code, mass, churn frequency, XGBoost threat scores, and PageRank network centrality metrics.
* **`constellations`**: Directory-level and module-level aggregate metrics.
* **`satellites`**: Extracted functions, methods, and classes linked to parent file IDs via foreign keys, complete with Big-O time complexity classifications.
* **`dna_hits`**: Queryable ledger of pattern match triggers per file.
* **`inbound_dependencies` & `outbound_dependencies`**: Relational join tables representing the bi-directional dependency graph for blast radius and coupling queries.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

