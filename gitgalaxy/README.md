# GitGalaxy: The Core Engine & GalaxyScope Orchestrator

[![Architecture](https://img.shields.io/badge/Architecture-blAST_Engine-00BFFF.svg)](#)
[![Velocity](https://img.shields.io/badge/Velocity-40k%2B_LOC%2Fsec-00C957.svg)](#)
[![CLI](https://img.shields.io/badge/Interface-GalaxyScope_CLI-8A2BE2.svg)](#)

Welcome to the internal source code for the **GitGalaxy Core Engine**. 

This directory contains the central orchestrator—**GalaxyScope**—alongside the core structural mechanics, lexical routing, and mathematical heuristics that power the entire DevSecOps ecosystem. If you are a developer looking to contribute, understand the data pipeline, or run the primary CLI, here is your architectural map.

**Why we built a custom parsing engine:**
Abstract Syntax Trees (ASTs) are excellent for catching syntax errors, but they require fully compilable code and a dedicated parser per language — both of which break down at the scale and polyglot mess of a real enterprise monolith. LLMs solve the language-coverage problem but introduce their own limits: context windows too small for million-line codebases, and probabilistic output that isn't the same twice.

The **blAST (Bypassing LLMs and ASTs) engine** takes a third path, borrowed from a specific insight in computational biology: BLAST proved that a fast heuristic search — willing to accept a small, bounded margin of error — beats an exhaustive, mathematically perfect one once a database gets large enough. GitGalaxy applies that same tradeoff to source code. Instead of compiling a full parse tree, it scans raw text for **Structural Signatures**: bounded, ReDoS-safe regex patterns that mark the boundaries of functions, control flow, I/O, state mutation, and dozens of other structural and security-relevant behaviors — the same way a conserved sequence motif can imply a protein's function without anyone solving its 3D structure.

The result is a deterministic knowledge graph of the repository, built without ever requiring the code to compile. It calculates the ratio of test code to core logic, maps each file's downstream "blast radius" through the dependency graph, and surfaces project-structure signal that line-by-line linters miss entirely. Per-file signal extraction runs in time linear to codebase size; repository-level graph metrics (centrality, community detection) use standard network-analysis algorithms with explicit sampling bounds on very large graphs.

*(Note: raw structural signatures are just counts. The risk scores GitGalaxy reports are derived metrics — density-normalized against file size and weighted by network centrality — not raw hit counts.)*

Think of GitGalaxy as a highly configurable macro-analyzer for codebase risk. Every assumption the system makes is exposed as one of 300+ tunable variables. You can query active API nodes, isolate supply chain threats, or highlight functions exhibiting extreme cognitive load — all adjusted via custom thresholds to reduce false-positive fatigue. Field-tested on over 1,000 repositories, the engine ships with enterprise-oriented defaults ready for CI/CD integration.

* **Heuristic Structural Scanning:** Bypasses LLMs and rigid ASTs. Reads code as raw text without requiring it to compile.
* **Deterministic Signal Extraction:** Maps code using a 97-point structural signal schema (I/O intent, state mutation, execution wrappers, security-relevant patterns, and more), rolled up into 19 aggregate risk categories.
* **Taxonomical Classification:** These structural profiles let us cluster functions, files, and entire repositories into distinct architectural archetypes.
* **Topological Cartography:** Builds a full dependency graph from imports and dynamic execution markers, with PageRank-style centrality and blast-radius scoring.
* **No LLM in the Analysis Loop:** The core mapping and risk-scoring engine makes no calls to any language model — output is fully deterministic and reproducible run over run. (Some optional legacy-migration tools, like COBOL-to-Java translation, do use AI to translate isolated business logic; the analysis engine itself does not.)

### 🗺️ The Developer Map (How the Pipeline Flows)

When you trigger the `galaxyscope` command, the data flows through these physical directories:

* **`/core/` (The Frontline):** The lexical routing layer. Contains the [Aperture Filter](https://squid-protocol.github.io/gitgalaxy/02-03-aperture-filter/) and [The Prism](https://squid-protocol.github.io/gitgalaxy/02-07-the-prism/), which break down source code into structural signals, stripping away inert binaries and separating executable logic from documentation.
* **`/metrics/` (The Math):** The heuristic and statistical engine. Contains the [Signal Processor](https://squid-protocol.github.io/gitgalaxy/02-09-signal-processing/) and [Statistical Auditor](https://squid-protocol.github.io/gitgalaxy/02-19-neural-auditor/), which apply GitGalaxy mathematics to calculate O(N) complexity, topological blast radius, and architectural drift without requiring ASTs.
* **`/security/` (The Threat Validator):** The security inference layer. Contains the [Security Lens](https://squid-protocol.github.io/gitgalaxy/02-06-security-lens/) responsible for identifying embedded malware signatures, autonomous AI execution vectors, and destructive execution patterns during Phase 1 ingestion.
* **`/recorders/` (The Exporters):** The translation layer. Converts the internal state RAM maps into highly relational [SQLite Databases](https://squid-protocol.github.io/gitgalaxy/02-21-record-keeper/), intermediate JSON representation for AI agents, and the final WebGPU visualization payload.
* **`/standards/` (The Calibration Layer):** The source of truth for the engine. Contains the polyglot lexical taxonomies and the global configuration profiles that tune the engine's strictness levels.
* **`/tools/` (The Execution Controllers):** The enterprise automation layer. Contains specialized controllers for CI/CD pipelines—like the [Supply Chain Firewall](https://squid-protocol.github.io/gitgalaxy/04-03-supply-chain-firewall/) and [PII Leak Hunter](https://squid-protocol.github.io/gitgalaxy/04-06-pii-leak-hunter/)—that independently consume the core engine's telemetry. 

*(Note: The `cobol_*_controller.py` scripts at the root level act as dedicated entry points for the Mainframe Legacy Modernization suite, bypassing standard Git orchestration to process flat mainframe directories).*

---

### ⚡ Performance Showcase: NVDA (NonVisual Desktop Access)

To demonstrate the GalaxyScope orchestrator's capability on complex, cross-language system architecture, we executed it against **NVDA**, the open-source Windows screen reader. 

Because NVDA relies heavily on bridging Python application logic with low-level C++ system hooks, it requires advanced polyglot dependency mapping. The blAST engine successfully parsed the mixed-language architecture, analyzing **236,754 lines of code** in just **5.59 seconds** (a velocity of 42,357 LOC/sec). 

Crucially, during the import resolution phase, the local dependency scanner successfully intercepted a structural naming collision (`fstream` vs `sstream`), proving the real-time typosquatting defenses are fully operational without relying on cloud-based CVE APIs.

> **Enterprise Calibration (Zero-Trust Enforcement):** Because `fstream` and `sstream` are both standard C++ libraries, flagging this collision demonstrates the engine's default Zero-Trust strictness. To prevent the pipeline from failing on trusted internal or standard libraries, DevSecOps teams simply add them to the `APPROVED_IMPORTS` allowlist in the [GitGalaxy Config](https://squid-protocol.github.io/gitgalaxy/06-01-gitgalaxy-config/).

![NVDA Processing Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/nvda_processing.gif)

~~~text
[INFO] PASS_1.5: Running Air-Gapped Typosquatting & Dependency Confusion Radar...
[CRITICAL] 🚨 TYPOSQUATTING DETECTED: 'fstream' in nvdaHelper/vbufBase/storage.cpp closely matches anchor 'sstream'!
[WARNING] Intercepted 1 typosquatting attempts via repository baseline analysis.
...
[INFO] --- MISSION_SUCCESS: 849 files mapped in 5.59s ---
[INFO] --- ENGINE_TELEMETRY: Processed 236,754 lines of code at 42,357 LOC/s ---
~~~

---

### 🛠️ Local Development & GalaxyScope Execution

If you are modifying the internal analysis logic or lexical routing, it is highly recommended to install the package in editable mode so your CLI commands instantly reflect your local code changes.

From the **root directory** of the repository, run:
~~~bash
pip install -e .
~~~

**Important:** GitGalaxy contains an embedded commercial licensing guardrail. To prevent a 5-second execution delay while testing your code locally, you must export the Community Free Tier key into your development environment before running the orchestrator:
~~~bash
export GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER"
~~~

Once installed and the key is set, you can trigger the main orchestrator globally from your terminal. This command runs the full [Data Pipeline](https://squid-protocol.github.io/gitgalaxy/02-01-pipeline-overview/) and outputs the final artifact.
~~~bash
galaxyscope /path/to/test/repo --debug
~~~

Before submitting a Pull Request, ensure your changes do not skew the core baseline risk equations by running the test suite:
~~~bash
python3 -m unittest discover tests/
~~~

---
### 🌌 Deep Dive into the Pipeline Architecture
To fully understand how GalaxyScope processes data, maps files, and applies risk exposures, explore the official documentation:

* 📖 **[GalaxyScope CLI Reference](https://squid-protocol.github.io/gitgalaxy/01-02-galaxyscope-cli-reference/)** (Flags, outputs, and behaviors)
* 📖 **[The Data Pipeline Overview](https://squid-protocol.github.io/gitgalaxy/02-01-pipeline-overview/)** (Step-by-step breakdown of the runtime)
* 📖 **[Risk Exposures & Methodology](https://squid-protocol.github.io/gitgalaxy/08-01-methodology/)** (The math behind the heuristics)
* 🪐 **[Return to the Main GitGalaxy Hub](https://github.com/squid-protocol/gitgalaxy)**