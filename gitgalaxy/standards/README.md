# GitGalaxy Standards: Heuristics Registry & Calibration Layer

Welcome to **GitGalaxy Standards**. This directory contains the immutable mathematical constants, structural regex dictionaries, security thresholds, and ingestion constraints that govern the entire GitGalaxy engine. 

No active execution, file I/O, or graph resolution occurs in this directory. Instead, this acts as the **Central Calibration Layer**. It defines the universal rulesets consumed by the Orchestrator, the Prism, the Signal Processor, and the Security Lens to guarantee deterministic analysis across polyglot ecosystems.

## Architectural Philosophy & Defensive Engineering

Engineers accustomed to traditional AST (Abstract Syntax Tree) parsers often view regular expressions with skepticism, assuming they are too brittle or prone to Catastrophic Backtracking (ReDoS) to parse enterprise code. 

GitGalaxy explicitly bypasses ASTs to **visualize functional intent rather than rigid syntax**, allowing it to map severely fragmented, legacy, or un-compilable code. To achieve processing speeds exceeding 100,000 LOC/sec without crashing the Python GIL, the dictionaries in this directory are engineered with strict defensive boundaries:

### 1. ReDoS Immunity & Strict Bounding
The regex dictionaries defined in `language_standards.py` strictly prohibit unbounded quantifiers (like `.*` or `\s+`) in high-risk zones. To safely leap across multi-line function declarations and modern attribute stacking (e.g., C++23 `[[attributes]]` or Java `@Annotations`), the engine utilizes strict boundary limits. It enforces rigid numeric clamps (e.g., `{0,5}`) and mutually exclusive character sets, guaranteeing O(1) or linear O(N) evaluation time per match.

### 2. Bayesian Confidence Hierarchy
Inferring a file's language purely by its extension leads to catastrophic collisions (e.g., `.m` being Objective-C, MATLAB, or Mathematica). `language_lens.py` resolves these collisions natively without AST evaluation. It builds a Bayesian confidence score by cross-referencing sibling files, structural neighborhood context, and package manifests, only falling back to an expensive lexical scan if the file's identity drops below a strict ambiguity threshold.

### 3. Contextual Threat Calibration (Architectural Anomaly Detection)
A vulnerability’s severity is dictated by its environment. Standard OS shell execution is expected in a bash script but highly anomalous in a React frontend component. `analysis_lens.py` defines an **Ecosystem Mismatch Matrix** that dynamically multiplies threat scores when an asset exhibits behaviors hostile to its native architecture (e.g., detecting C-style memory pointers inside a Node.js web layer), instantly flagging it as a high-risk anomaly or potential backdoor.

### 4. Structural Impact Score Normalization
AST parsers typically collapse when analyzing massive machine-generated files (e.g., Swagger JSONs, Webpack chunks, Protobuf definitions). `analysis_lens.py` deploys pre-calculated modifiers to programmatically reduce the calculated Structural Impact Score of generated code. This ensures human-written architecture remains the focal point of the analysis without risking Out-Of-Memory (OOM) exceptions or skewing repository metrics.

---

## Data-Driven Configuration: Decoupled Architecture & False-Positive Eradication

The true flexibility of GitGalaxy lies in its decoupled architecture. The core execution logic is entirely separated from the mathematical constants that govern it. This directory exposes over **175 discrete tuning variables**—from sigmoid curve slopes and anomaly thresholds to architectural mass dampeners.

* **Risk Equation Tuning (75+ Variables):** Highly specific parameters (sigmoid slopes, offsets, clamps, and threshold floors) for multiple risk dimensions. The math curves for `cognitive_load`, `concurrency`, or `injection_surface` can be stretched or compressed independently.
* **Path & Impact Modifiers (35+ Variables):** Regex-targeted multipliers that artificially increase or decrease Structural Impact Scores based on domain context (e.g., dampening UI framework cognitive load by 0.50x, or multiplying global state manipulation by 1.15x).
* **Security & Ecosystem Matrices (50+ Variables):** Specific baseline weights for systems vs. web vs. infrastructure, cross-ecosystem mismatch penalties (e.g., `systems_in_web`), and the 10-cluster Archetype Violation Matrix.
* **Hardware & Ingestion Limits (15+ Variables):** Hard operational ceilings like `MAX_FILE_SIZE_MB`, `MAX_LINE_LENGTH`, `HANDSHAKE_LOOKAHEAD_LIMIT`, and `NESTED_PEEL_LIMIT` to tune exactly how hard the engine pushes the CPU before backing off.

While 175+ variables might sound intimidating, they are your primary lever against alert fatigue. Every single dial can be tuned to reduce false positives for your specific environment—giving you a scanner that highlights genuine architectural threats without wasting engineering time on expected structural noise.

Want to scan an untrusted package? Flip the engine to `paranoid` mode to instantly tighten the `ThreatPolicy` thresholds. Need to support a proprietary, in-house legacy language? Inject a new structural dictionary into `language_standards.py`. The engine dynamically adopts these new constraints at runtime without requiring a single modification to the core parsing algorithms.

---

## Core Configurations (Module Breakdown)

Each file in this directory serves a distinct calibration purpose for the downstream engines:

* **`gitgalaxy_config.py` (Global Ingestion Firewall):** Defines Zero-Trust ingestion boundaries. It houses the Supply Chain Firewall configurations (approved vs. blacklisted imports), global file denylists, X-Ray binary scanner bypasses, and physical file-size clamps.
* **`language_lens.py` (Identity Classifier):** The Bayesian engine that assigns definitive "Identity Locks" to files. It defines the multi-tiered confidence hierarchy, resolving extension collisions by weighing exact filename matches against Contextual Baselines.
* **`language_standards/` (Structural Signature Registry):** A package with one file per language under `languages/` (59 today), assembled by `__init__.py` into the `LANGUAGE_DEFINITIONS` registry every downstream engine imports. Each per-language file defines exactly how to slice that language into Branch Logic, State Flux, High-Risk Execution, and Object Declarations using ReDoS-proof regular expressions; cross-language shared pieces (`LENS_CONFIG`, `PRISM_CONFIG`, the `GLOBAL_*` debt/AI-SDK detectors, `PROJECT_OVERRIDES`) live in their own sibling modules. See `how_to_add_a_language.md` for the registration mechanics.
* **`analysis_lens.py` (Mathematical Constants & Threat Policies):** The repository of Threat Policies, Sigmoid Curve tuning, and K-Means clustering medians. It dictates how raw structural signals are mathematically converted into normalized 0-100% risk exposure vectors.
* **`how_to_add_a_language.md` (Extension Protocol):** Contains the strict prompt engineering protocols required to generate ReDoS-proof language dictionaries using advanced LLMs, bypassing the need for manual parser development.

---

## Extending the Engine (AST-Free Onboarding)

Because GitGalaxy is AST-free, adding support for a new language does not require writing a complex, brittle parser. You simply need to calibrate the structural heuristics of the target language by generating a new dictionary entry for `language_standards.py`. 

For strict guidelines and the LLM Master Prompt required to generate ReDoS-proof structural definitions, review: **[Architecting a New Language](how_to_add_a_language.md)**.

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Standards is the calibration layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.