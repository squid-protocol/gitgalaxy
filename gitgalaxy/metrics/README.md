# GitGalaxy Metrics: Heuristic Synthesis & Statistical Auditing

[![Architecture](https://img.shields.io/badge/Architecture-Heuristic_Synthesis-8A2BE2.svg)](#)
[![Reliability](https://img.shields.io/badge/Reliability-False__Positive_Eradication-00BFFF.svg)](#)
[![Performance](https://img.shields.io/badge/Performance-Zero--RAM_Auditing-FF4500.svg)](#)

Welcome to **GitGalaxy Metrics**. If the `core/` directory is the extraction layer (identifying raw structural signals), this directory is the analytical brain. 

It is responsible for consuming raw lexical data, merging it with temporal Git telemetry, and translating it into actionable, multi-dimensional risk vectors. This is where raw data becomes architectural intelligence.

## The Why: False-Positive Eradication & Alert Fatigue

Traditional Static Application Security Testing (SAST) tools suffer from a fatal flaw: they flag raw vulnerabilities in a vacuum. A raw execution command inside a deprecated, unimported sandbox script generates the same critical alert as one sitting in your primary routing controller. This lack of context generates massive false-positive fatigue, eventually causing engineering teams to ignore the scanner entirely.

The GitGalaxy Metrics engine is engineered to solve this through **Contextual Synthesis**. It operates on a fundamental rule: **Risk exposures are calculated metrics derived from structural hits; they are not the hits themselves.** The engine applies mathematical dampeners (like testing umbrellas, network isolation, and documentation shields) to raw signals. For example, a high "state flux" signal in a file with 100% test coverage and zero downstream dependents has its ultimate risk exposure mathematically dampened, reflecting true ecosystem reality rather than isolated syntax panic.

---

## The What: Core Modules & Data Flow

All modules in this directory are engineered to operate strictly in $O(1)$ or $O(N)$ linear time complexity. Because expensive disk I/O and regex parsing have already concluded in the `core/` phase, these mathematical operations execute across tens of thousands of files in milliseconds.

### 1. `signal_processor.py` (The Mathematical Core)
The primary heuristic synthesis engine. It translates raw structural hits into an 18-point risk vector evaluating dimensions like Technical Debt, Cognitive Load, and State Flux.
* **Dual-Axis Anomaly Detection:** Evaluates threats using both global repository baselines and local language models. It leverages **Architectural Drift (Z-Score)** to mathematically flag files that blend in globally but violate their local ecosystem's structural norms.
* **Autonomous Execution Vectors & AI Topology:** Analyzes the density of LLM orchestration tools, vector databases, and execution loops to classify the repository's AI footprint. It explicitly flags vulnerabilities where raw **Prompt Injection Surfaces** flow directly into OS-level execution.

### 2. `statistical_auditor.py` (The Quality Gate)
A statistical gatekeeper designed to protect downstream Machine Learning models and LLMs from context poisoning.
* **Anomaly Quarantine:** Calculates the Median Absolute Deviation (MAD) of logic density across the assembled repository graph. Files that fall outside mathematical norms (e.g., massive auto-generated JSON dumps masquerading as code) are automatically quarantined and dropped before they can distort the final architectural map.

### 3. `chronometer.py` (The Temporal Engine)
Static code analysis is often blind to human behavior. The Chronometer bridges this gap by merging temporal Git telemetry with structural static analysis.
* **Authorship Centralization:** Extracts Git volatility, churn velocity, and ownership entropy without requiring heavy dependency parsing. By cross-referencing code mass with developer churn, the engine calculates centralization—identifying critical, load-bearing files authored and understood entirely by a single developer.

### 4. `tensor_scanner.py` (The AI Infrastructure Auditor)
As repositories increasingly embed local AI models, standard parsers crash attempting to evaluate gigabyte-scale binaries.
* **Zero-RAM Auditing:** Performs binary header audits on local model weights (`.gguf`, `.safetensors`). It surgically extracts architectural metadata without loading the massive weights into system memory, safely visualizing AI infrastructure without risking OS-level crashes.

---

## 🧠 Engineering Highlights (Architectural Defenses)

If you are evaluating the `metrics/` architecture, pay special attention to how we bypass the computational and statistical bottlenecks of enterprise-scale analysis:

* **Zombie Process & FD Leak Prevention (`chronometer.py`):** Parsing a decade-long Git log for a monolithic repository will crash CI/CD runners by exhausting RAM and stalling the CPU. We enforce a dual-axis kill switch (volume targets and hard timeouts) via buffered `Popen` streams. To prevent zombie processes, we execute strict `SIGKILL` and `communicate()` flushing, ensuring OS file descriptors are perfectly sterilized even when the stream is aborted early.
* **Heuristic Extension Consensus (`statistical_auditor.py`):** Certain file extensions (`.h`, `.m`) are ambiguous across languages (C vs. C++ vs. Objective-C). Instead of guessing, the engine surveys the macro-state of the repository. If 80% of the repository's confidently parsed `.h` files are confirmed as C++, the auditor mathematically forces all ambiguous headers to align with the ecosystem consensus, resolving collisions dynamically without AST compilation.
* **The Impossible Density Law (`statistical_auditor.py`):** Normal human code rarely sustains > 1.5 structural signature hits per physical line. If a file sustains > 3.0 across 30+ lines, it is mathematically guaranteed to be minified, obfuscated, or packed with embedded binaries. The auditor catches these "Packed Payloads" and shunts them out of the standard risk pool, preventing malicious obfuscation from hiding in the noise.
* **Zero-RAM Exhaustion Guards (`tensor_scanner.py`):** A malicious actor can craft a tiny `.safetensors` file claiming its JSON header is 500GB, triggering a catastrophic memory exhaustion attack when a Python parser attempts to read it. Our tensor scanner reads strictly the first 8 bytes to extract the header size and enforces a hard 100MB cap, mathematically guaranteeing pipeline survival in $O(1)$ space complexity.

---

## 🌌 The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Metrics is the analytical processing layer of the broader **GitGalaxy Ecosystem**—a high-velocity, AST-free, LLM-free heuristic knowledge graph engine designed for planetary-scale repositories.

Explore the ecosystem:

* 🪐 **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* 🔭 **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* 📖 **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* ⚙️ **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.