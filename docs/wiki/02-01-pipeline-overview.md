# Static Analysis Pipeline Overview

> **File Reference:** [`gitgalaxy/galaxyscope.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/galaxyscope.py)

The GitGalaxy analysis engine provides automated, deterministic static analysis and dependency mapping for multi-language software repositories. The pipeline ingests raw source files, filters out non-code assets and minified dependencies, identifies programming languages, separates executable logic from comments, extracts structural metrics via regular expressions, computes multi-dimensional risk exposures, validates statistical integrity, and serializes the resulting repository graph into structured data formats (SQLite, JSON, Markdown, and WebGL node-graph arrays).

Rather than relying on fragile Abstract Syntax Tree (AST) compilation or non-deterministic LLM inference, the pipeline operates as a high-speed, modular analysis workflow executed by the main pipeline orchestrator (`galaxyscope.py`).

---

## Pipeline Component Architecture

The analysis workflow is divided into specialized engine modules responsible for specific stages of data extraction and transformation:

| Component Name | Source Module (`.py`) | Operational Responsibility | Engine Output |
| :--- | :--- | :--- | :--- |
| **Pipeline Orchestrator** | `galaxyscope.py` | Executable entry point and process manager. Controls parallel execution, phase transitions, and IPC data transfers. | Coordinated analysis pipeline execution. |
| **File Filter Engine** | `aperture.py` | Ingestion filter. Enforces `.gitignore` patterns, file size limits, binary detection, and path exclusions. | Filtered list of analyzable source files. |
| **Project Metadata Parser** | `guidestar_lens.py` | Context resolver. Parses build manifests (`package.json`, `Cargo.toml`), `.gitattributes`, and directory paths to assign language priors. | Pre-configured confidence vectors and language hints. |
| **Language Identification Engine** | `language_lens.py` | Language detector. Evaluates file extensions, shebangs, structural heuristics, and directory context to lock language IDs. | Deterministic language classification per file. |
| **Lexical Stream Splicer** | `prism.py` | Code/comment separator. Masks string literals and heredocs, then splits files into isolated code and comment streams. | Separate code stream and comment stream buffers. |
| **Structural Code Analyzer** | `detector.py` | Heuristic metric extractor. Executes regular expression rules to count functions, parameters, and control-flow structures. | Raw 51-element metric schema per file. |
| **Metrics Normalization Engine** | `signal_processor.py` | Metric calculator. Transforms raw structural hits into 0-100 normalized risk exposure scores (cognitive complexity, safety, debt). | Scaled risk vectors and forensic metric reports. |
| **Statistical Quality Auditor** | `statistical_auditor.py` | Bayesian data validator. Executes Z-score and Median Absolute Deviation (MAD) checks to filter out false positives and unparseable assets. | Validated codebase metrics with outlier exclusion. |
| **Version Control & Churn Analyzer** | `chronometer.py` | Temporal analyzer. Evaluates Git commit history and filesystem metadata to measure file age and modification churn. | File churn rates and historical stability scores. |
| **Dependency Topology Analyzer** | `network_risk_sensor.py` | Directed graph builder. Maps file import relationships to compute PageRank, Betweenness centrality, and blast radius. | Centrality metrics and dependency topology graph. |
| **Vulnerability & Threat Scanner** | `security_lens.py` | AppSec scanner. Detects obfuscation, raw socket usage, dynamic code execution, memory manipulation, secrets, and injection points. | Security exposure scores and vulnerability flags. |
| **AI Vulnerability Sensor** | `ai_appsec_sensor.py` | Agentic security auditor. Identifies unmitigated LLM integration points and prompt injection surfaces. | Remote Code Execution (RCE) risk vector flags. |
| **Agent Guardrail Evaluator** | `dev_agent_firewall.py` | Safety evaluator. Assesses file complexity to flag risk zones before automated modifications by AI dev agents. | Risk boundaries and context-window limitations. |
| **Binary Model Inspector** | `neural_auditor.py` | Machine learning weight auditor. Reads header metadata from binary model weights (`.safetensors`, `.gguf`) without full memory load. | Structural model parameters and architecture metadata. |
| **ML Threat Classifier** | `security_auditor.py` | Machine learning inference engine. Evaluates feature matrices against XGBoost models to predict malware probabilities. | Malicious payload probability scores. |
| **Audit Trail Exporter** | `audit_recorder.py` | Comprehensive report generator. Serializes all scan telemetry, metrics, and rule hits into a master JSON archive. | Structural Health Bill of Materials (SHBOM) JSON. |
| **Relational Database Exporter** | `record_keeper.py` | Database persistence engine. Writes analysis results directly into a structured SQLite database. | Queryable relational SQLite database file. |
| **AI Context Brief Exporter** | `llm_recorder.py` | LLM context generator. Formats codebase architecture and key metric summaries into compressed Markdown briefs. | High-density LLM context document. |
| **Topology Graph Exporter** | `gpu_recorder.py` | Visualization serializer. Outputs spatial coordinates, node dimensions, and edge connections for 3D WebGL rendering. | WebGL-compatible JSON graph payload. |

---

## Sequential Execution Phases

The `Orchestrator` class in `galaxyscope.py` executes analysis across distinct sequential phases:

1. **Phase 0: Project Discovery & Census Ignition**  
   Discovers files using Git index inspection (or filesystem walking as a fallback). Validates file existence, tallies file extension distributions, and applies minimum file size quotas.

2. **Phase 1: Parallel Lexical Extraction (Map-Reduce)**  
   Distributes files across a multi-core `ProcessPoolExecutor`. Each worker process executes the file filter, language detector, lexical stream splicer, and structural code analyzer. A 15-second execution timeout prevents regular expression backtracking (ReDoS) stalls.

3. **Phase 1.5: Dependency Graph Resolution & Typosquatting Analysis**  
   Resolves raw import statements to absolute file paths using a suffix hash map. Evaluates external package dependencies against Levenshtein distance rules to detect potential typosquatting or homoglyph attacks.

4. **Phase 2: Relational Aggregation & Ecosystem Scoring**  
   Aggregates folder-level statistics to determine dominant programming languages across directories. Applies context penalties for mismatched language files and calculates global repository test coverage ratios.

5. **Phase 3: Directed Graph Analysis & Centrality Metrics**  
   Constructs a directed dependency graph via `NetworkRiskSensor`. Computes PageRank (architectural importance), Betweenness (choke points), and Closeness centrality to define file operational roles.

6. **Phase 3.5: AI Integration & Agent Security Assessment**  
   Scans for autonomous agent integration risks, identifying over-permissioned execution hooks, prompt injection paths, and LLM context limits via `DevAgentFirewall` and `AIAppSecSensor`.

7. **Phase 4: Statistical Quality Audit**  
   Runs Bayesian statistical checks via `StatisticalAuditor`. Excludes mathematically improbable or unparseable files from primary code metrics and routes them to an unclassified asset store.

8. **Phase 5: Spatial Layout & Graph Cartography**  
   Generates deterministic 3D layout coordinates for repository visualization via a ray-casting Fibonacci spiral layout algorithm.

9. **Phase 6: Metrics Normalization & Biaxial Anomaly Detection**  
   Normalizes file modification metrics logarithmically across the repository. Evaluates structural drift by comparing global file behavior against local language standards.

10. **Phase 7.8: Machine Learning Threat Inference**  
    Ingests file feature matrices into an XGBoost classifier to compute probabilities of malicious code patterns (trojans, botnet agents, obfuscated payloads).

11. **Phase 8-9: Serialization & Data Recording**  
    Routes processed repository data to selected output writers (JSON audit logs, SQLite database, Markdown briefs, WebGL graph files).

---

## Runtime Configuration & Performance Controls

* **Language Dialect Customization:** Allows pre-flight regular expression adjustments for specific framework conventions (e.g., CPython, Ansible, Redis) without altering global rules.
* **Worker Process Cache Pre-Warming:** Pre-compiles regular expression dictionaries when worker processes initialize, preventing runtime compilation overhead during parallel analysis.
* **Zero-Trust Security Sensitivity Mode:** Enables high-sensitivity vulnerability policies via the `--paranoid` CLI flag, lowering threat score trigger thresholds.
* **High-Risk Asset Highlighting:** Ensures flagged security threats (e.g., leaked private keys or binary AI models) are explicitly included in spatial graph outputs regardless of parsing status.
* **Incremental Delta Analysis:** Supports `execute_delta_mission` to rehydrate previous scan state from RAM, processing only modified files while recomputing graph dependencies and ML inference.
* **Selective Serialization Routing:** Supports flags like `--gpu-only`, `--audit-only`, `--llm-only`, and `--db-only` to skip unnecessary formatting stages and reduce memory usage.
* **Session Metadata Locking:** Binds immutable session metadata (Git commit SHA, active branch, remote repository URL, scan timestamp) to generated analysis artifacts.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Core static analysis source code and CLI tools.
* **[GitGalaxy Visualization Platform](https://gitgalaxy.io/)** - Interactive 3D WebGL repository cartography dashboard.

---

**[⬅️ Back to Master Index](index.md)**

