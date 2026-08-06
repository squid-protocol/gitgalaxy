# GitGalaxy Security: Threat Inference & Application Security Engine

Welcome to **GitGalaxy Security**. This directory houses the Machine Learning models, Static Application Security Testing (SAST) engines, and Software Supply Chain Security (SSCS) auditors for the GitGalaxy ecosystem.

Unlike traditional security tools that rely on matching specific CVEs or static, known-vulnerable package versions, this security engine evaluates the **structural signatures** of a codebase. It calculates risk exposures by combining raw heuristic signals with topological network graph data, weighting each flagged pattern by how exposed its location is in the dependency graph — a prioritization signal, not a verified exploitability claim (GitGalaxy never executes code or traces runtime dataflow).

## The Why: Context-Aware Security & Defensive Engineering

Modern malware, supply chain substitution attacks, and Agentic RCE (Remote Code Execution) vulnerabilities frequently evade traditional static analysis. Attackers utilize obfuscation, dynamically loaded strings, and distributed payload execution to bypass standard regex sweeps and AST (Abstract Syntax Tree) parsers. 

To counter this without crushing CI/CD pipeline velocity, the GitGalaxy Security engine employs advanced, AST-free defensive paradigms:

### 1. Network-Weighted Threat Scoring
A vulnerability in a core utility file has a radically different systemic impact than a vulnerability in an isolated, unimported test script. The engine dynamically scales vulnerability thresholds based on a node's **Dependency Blast Radius**. It multiplies raw SAST hits by PageRank and Betweenness Centrality metrics, ensuring that highly centralized network choke points face strictly hardened security tolerances.

### 2. O(H) Data Flow Taint Tracking
Tracking execution paths—from an untrusted I/O input to a database sink—typically requires compiling a massive, memory-intensive AST. The security engine bypasses this bottleneck by utilizing an $O(H)$ Offset Mapper. It isolates the specific lines where threat signatures triggered, extracting variable assignments and executing downward flow scans in linear time without ever compiling the file.

### 3. Agentic AI Defenses (Zero-Trust Pipelines)
As codebases integrate LLMs, new vectors emerge. The engine natively detects **Prompt Injection Surfaces** (where untrusted I/O flows directly into an LLM context) and **Autonomous Execution Vectors** (where LLM logic loops are adjacent to OS-level `eval` or subprocess execution), flagging these high-risk architectural patterns before deployment.

### 4. C-Optimized Shannon Entropy
To flag obfuscated payloads and custom decryption routines hidden inside massive string literals, the engine utilizes Shannon Entropy calculations. By restructuring the standard entropy formula to execute division operations completely outside the evaluation loop, it processes thousands of massive strings in milliseconds. High entropy alone doesn't distinguish a hidden payload from a legitimate cryptography routine — it flags the string as worth a closer look, the same recall-over-precision trade-off that applies elsewhere in the engine.

### 5. Shadow Patch & Evasion Detection
Supply chain attackers frequently compromise upstream dependencies without bumping version numbers. The engine correlates runtime metrics with structural mass to detect **Shadow Patches**—files where the cryptographic hash has mutated without a corresponding version bump. It forcefully overrides standard logic to classify these unauthorized modifications as critical security threats.

---

## The What: The Information Flow (Module Breakdown)

Each file in this directory represents a distinct phase of the security validation and threat hunting pipeline:

* **`manifest_parser.py` (The SSCS Auditor):** The dependency and configuration parser. It builds a deterministic, $O(1)$ global resolution map by auditing manifests like `package-lock.json` and `pip.conf`. It prevents Supply Chain Substitution attacks by identifying non-standard registries, untrusted VCS routing, and insecure tunneling protocols (like `ngrok` or plain `http`).
* **`security_lens.py` (The SAST Engine):** The raw heuristic sensor. It applies highly optimized regular expressions to detect 13 distinct threat categories (e.g., Hardcoded Secrets, Memory Corruption, Prompt Injection). It executes multi-line Taint Tracking and memory-efficient binary header inspection to validate file extension integrity.
* **`security_auditor.py` (The ML Orchestrator):** The threat classification engine. It resolves N-th degree transitive dependency graphs to calculate precise upstream/downstream ratios. It compiles a 50-dimensional feature matrix (evaluating Control Flow Ratio, API Exposure, Authorship Centralization, etc.) and executes it against the local XGBoost model.
* **`gitgalaxy_malware_xgb_multiclass.json`:** The pre-trained, serialized XGBoost Machine Learning model. It evaluates the 50-dimensional feature matrix to classify the specific **Architectural Anomalies** present across 5 distinct taxonomies: Safe Code, Botnet / DDoS, Stealer / Trojan, Dropper / Webshell, and Native Infector.

---

## Engineering Highlights (Architectural Feats & Defenses)

If you are evaluating the `security/` architecture, pay special attention to how we bypass the computational bottlenecks of traditional Static Application Security Testing (SAST) and Software Composition Analysis (SCA). We utilize highly optimized algorithms to detect threats that standard tools miss due to scale or complexity.

* **$O(H)$ Data Flow Taint Tracking (`security_lens.py`):** Tracing an untrusted input to a vulnerable execution sink typically requires compiling a massive, memory-exhaustive Abstract Syntax Tree (AST). We bypass this entirely using an $O(H)$ Offset Mapper. The engine isolates only the exact spatial lines where heuristic threats triggered. It extracts the Left-Hand Side (LHS) variable assignments on those specific lines and scans the downward flow in linear time. This achieves high-fidelity taint tracking (e.g., mapping I/O inputs to OS-level execution) without the massive CPU overhead of AST compilation.
* **Network-Weighted Threat Scaling (`security_auditor.py`):** A vulnerability’s severity is dictated by its location. Standard scanners treat a hardcoded secret in an isolated test file with the same severity as a secret in a core routing configuration. GitGalaxy dynamically scales vulnerability thresholds based on a node's **Dependency Blast Radius**. By multiplying local SAST density scores by the file's PageRank and Betweenness Centrality metrics, the engine ensures that highly centralized **Architectural Choke Points** face strictly hardened security tolerances.
* **Obfuscation Detection (`security_lens.py`):** To flag likely zero-day Trojans, packed payloads, and base64-encoded malware hidden inside massive string literals, the engine utilizes Shannon Entropy. However, standard entropy calculations are computationally expensive inside loops. We implemented a C-level counter that factors the division operation `(/ length)` completely outside the summation loop. This allows the engine to evaluate the cryptographic density of thousands of massive strings in milliseconds without stalling the CI/CD pipeline.
* **Autonomous Execution & Agentic Defenses (`security_lens.py`):** As codebases integrate LLMs, traditional SAST falls behind. GitGalaxy natively maps and detects **Prompt Injection Surfaces** (where untrusted network I/O flows directly into an LLM context) and **Autonomous Execution Vectors** (where LLM state mutations flow downward into `eval` or `subprocess` commands). It flags these AI-specific architectural risk patterns before deployment.
* **$O(1)$ Dependency Graph Resolution (`security_auditor.py`):** Calculating exact **Downstream Exposure** on massive monolithic repositories often causes graph algorithms to stall on circular dependencies. When the C-optimized `NetworkX` backend is unavailable, our fallback engine utilizes a heavily optimized Breadth-First Search (BFS) using Python's `collections.deque`. By popping nodes in strict $O(1)$ time and capping traversal depth to 500 hops, it safely maps deep transitive dependencies without triggering Out-Of-Memory (OOM) deadlocks.
* **Shadow Patch Overrides (`security_auditor.py`):** Supply chain attackers frequently compromise upstream dependencies without bumping version numbers to evade detection. The engine correlates runtime execution metrics with structural mass to detect **Shadow Patches**—files where the cryptographic hash has mutated without a corresponding version bump. When detected, the engine forcefully overrides the XGBoost ML model to classify the unauthorized modification as a critical threat.

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Security is the threat inference layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.