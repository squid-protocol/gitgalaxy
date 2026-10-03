# GitGalaxy Security: Threat Inference & Application Security Engine

Welcome to **GitGalaxy Security**. This directory houses the Machine Learning models, Static Application Security Testing (SAST) engines, and Software Supply Chain Security (SSCS) auditors for the GitGalaxy ecosystem.

Unlike traditional security tools that rely on matching specific CVEs or static, known-vulnerable package versions, this security engine evaluates the **structural signatures** of a codebase. It calculates risk exposures by combining raw heuristic signals with topological network graph data, weighting each flagged pattern by how exposed its location is in the dependency graph — a prioritization signal, not a verified exploitability claim (GitGalaxy never executes code or traces runtime dataflow).

## The Why: Context-Aware Security & Defensive Engineering

Modern malware, supply chain substitution attacks, and Agentic RCE (Remote Code Execution) vulnerabilities frequently evade traditional static analysis. Attackers utilize obfuscation, dynamically loaded strings, and distributed payload execution to bypass standard regex sweeps and AST (Abstract Syntax Tree) parsers. 

To counter this without crushing CI/CD pipeline velocity, the GitGalaxy Security engine employs advanced, AST-free defensive paradigms:

### 1. Network-Weighted Threat Scoring
A vulnerability in a core utility file has a radically different systemic impact than a vulnerability in an isolated, unimported test script. The [supply-chain firewall](../tools/supply_chain_security/supply_chain_firewall.py) can scale a file's threat score by its network centrality (betweenness), opt-in, so a hit in a central file counts for more than one in a peripheral file. The multiplier only ever amplifies, and it is skipped when a metric was not computed.

### 2. Agentic AI Defenses (opt-in)
The AI guardrails (below) flag an **Over-Permissioned Agent Binding**: an agent framework imported into a file with raw network or disk write access and little defensive code. GitGalaxy does no data-flow or taint tracking, so it does not claim a prompt-injection or agentic-RCE path. Those detectors were removed as unprovable (#1020, #1102).

### 3. C-Optimized Shannon Entropy
To flag obfuscated payloads and custom decryption routines hidden inside massive string literals, the engine utilizes Shannon Entropy calculations. By restructuring the standard entropy formula to execute division operations completely outside the evaluation loop, it processes thousands of massive strings in milliseconds. High entropy alone doesn't distinguish a hidden payload from a legitimate cryptography routine — it flags the string as worth a closer look, the same recall-over-precision trade-off that applies elsewhere in the engine.

### 4. Shadow Patch & Evasion Detection
Supply chain attackers frequently compromise upstream dependencies without bumping version numbers. The engine correlates runtime metrics with structural mass to detect **Shadow Patches**—files where the cryptographic hash has mutated without a corresponding version bump. It forcefully overrides standard logic to classify these unauthorized modifications as critical security threats.

---

## The What: The Information Flow (Module Breakdown)

Each file in this directory represents a distinct phase of the security validation and threat hunting pipeline:

* **`manifest_parser.py` (The SSCS Auditor):** The dependency and configuration parser. It builds a deterministic, $O(1)$ global resolution map by auditing manifests like `package-lock.json` and `pip.conf`. It prevents Supply Chain Substitution attacks by identifying non-standard registries, untrusted VCS routing, and insecure tunneling protocols (like `ngrok` or plain `http`).
* **`security_lens.py` (The SAST Engine):** The raw heuristic sensor. It applies regular expressions to detect threat categories such as hardcoded secrets and memory corruption (the prompt-injection and agentic-RCE columns survive only as always-zero placeholders, #1020). It executes memory-efficient binary header inspection to validate file extension integrity.
* **`security_auditor.py` (The ML Orchestrator):** The threat classification engine. It resolves N-th degree transitive dependency graphs to calculate precise upstream/downstream ratios. It builds a feature frame from the signal schema plus derived columns and, when an XGBoost model is present, classifies it. Without one it warns and runs the graph resolution only.
* **`gitgalaxy_malware_xgb_multiclass.json` (not included):** the XGBoost model `security_auditor.py` loads when present, to classify five taxonomies (Safe Code, Botnet / DDoS, Stealer / Trojan, Dropper / Webshell, Native Infector). It is not shipped in this repository, and XGBoost itself is an optional extra (`pip install gitgalaxy[full]`).
* **`credential_lexicon.py` and `dependency_audit_cache.py`:** the multilingual credential vocabulary behind the hardcoded-secrets signature (`senha`, `PASSWORT`, not only `password`), and a content-hash-keyed cache of dependency-file audit verdicts, so later scans verify only what changed.
* **`ai_appsec_sensor.py` (The AI AppSec Sensor):** The AI-feature threat hunter. It detects **Over-Permissioned Agent Bindings**: a file that imports a known agent-orchestration framework (langchain/llama_index) and has raw Network/Disk IO write access, combined with critically low defensive programming density. Because GitGalaxy has no data-flow or taint tracking, the sensor is deliberately scoped to that honest co-location claim — it never asserts a proven RCE or exfiltration path (two such checks were removed in #1102 as unprovable).
* **`dev_agent_firewall.py` (The Dev Agent Firewall):** The Zero-Trust guardrail against autonomous AI coding agents. It flags **Context Window Exhaustion** (token mass beyond what an agent's context can safely hold), **Hallucination Risk** (undocumented dynamic metaprogramming), **Cascading State Flux** (high state mutation plus dense downstream dependencies with zero test coverage), and mandates **Human-In-The-Loop review** for files with a high Dependency Blast Radius and severe Technical Debt.

The two AI-guardrail modules run inside the main engine as **"Phase 5: Zero-Trust Guardrails"**. The phase is **opt-in**: most targets (e.g. a large COBOL-modernization scan) have no AI/agentic surface, so it only runs when enabled with the `--ai-guardrails` CLI flag (or `ai-guardrails: true` under the `galaxyscope:` section of `.galaxyscope.yaml`). On a default scan the guardrail columns record `NULL` ("not evaluated"); `0` is reserved for "evaluated, no risk found".

---

## Engineering Highlights (Architectural Feats & Defenses)

If you are evaluating the `security/` architecture, pay special attention to how we bypass the computational bottlenecks of traditional Static Application Security Testing (SAST) and Software Composition Analysis (SCA). We utilize highly optimized algorithms to detect threats that standard tools miss due to scale or complexity.

* **Network-Weighted Threat Scaling (`supply_chain_firewall.py`):** A vulnerability’s severity is dictated by its location. Standard scanners treat a hardcoded secret in an isolated test file with the same severity as a secret in a core routing configuration. The supply-chain firewall can scale a file's threat score by its betweenness centrality (opt-in, amplify-only), so a central **Architectural Choke Point** counts for more than a peripheral file.
* **Obfuscation Detection (`security_lens.py`):** To flag likely zero-day Trojans, packed payloads, and base64-encoded malware hidden inside massive string literals, the engine utilizes Shannon Entropy. However, standard entropy calculations are computationally expensive inside loops. We implemented a C-level counter that factors the division operation `(/ length)` completely outside the summation loop. This allows the engine to evaluate the cryptographic density of thousands of massive strings in milliseconds without stalling the CI/CD pipeline.
* **Dependency Graph Resolution (`security_auditor.py`):** **Downstream Exposure** over a graph with cycles: the cycles are condensed, then the transitive closure is computed exactly by GitGalaxy's own stdlib graph engine ([`core/graph_engine.py`](../core/graph_engine.py), #3033 / #3040). NetworkX is not a runtime dependency, and there is no depth cap.
* **Shadow Patch Overrides (`security_auditor.py`):** Supply chain attackers frequently compromise upstream dependencies without bumping version numbers to evade detection. The engine correlates runtime execution metrics with structural mass to detect **Shadow Patches**—files where the cryptographic hash has mutated without a corresponding version bump. When detected, the engine forcefully overrides the XGBoost ML model to classify the unauthorized modification as a critical threat.
* **Library-Identity Binding Detection (`ai_appsec_sensor.py`):** GitGalaxy is AST-free and does no data-flow/taint analysis, so it can't prove an LLM Orchestrator's output actually reaches a given I/O sink — only that both exist in the same file. This sensor sticks to what a regex-only engine can honestly claim: it detects when a known agent-orchestration framework is imported into a file with raw network/disk write access and low defensive programming density, flagging an **Over-Permissioned Agent Binding**.
* **Context Mass Validation (`dev_agent_firewall.py`):** Autonomous coding agents blindly attempt to refactor files regardless of size. The firewall calculates the physical Token Mass of a file and flags it once that mass exceeds what an agent's context window can safely hold, raising a **Context Window Exhaustion** risk before the agent hallucinates and corrupts the logic.
* **Blast Radius Sandboxing (`dev_agent_firewall.py`):** AI agents are strictly prohibited from modifying the structural load-bearing pillars of your architecture unchecked. By querying the Knowledge Graph for a file's **Dependency Blast Radius** (PageRank / Downstream Exposure), the firewall automatically mandates Human-In-The-Loop (HITL) reviews for any PRs targeting highly centralized nodes with existing Technical Debt.

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Security is the threat inference layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.