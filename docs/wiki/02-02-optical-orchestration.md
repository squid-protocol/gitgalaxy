# Pipeline Orchestration Framework

> **File Reference:** [`gitgalaxy/galaxyscope.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/galaxyscope.py)

The `Orchestrator` class defined in `galaxyscope.py` serves as the primary execution engine and process manager for the GitGalaxy static analysis framework. It coordinates data ingestion, worker process pools, multi-pass metric evaluations, network dependency mapping, and serialization exporters. The orchestrator ensures deterministic, sequential execution across all pipeline phases.

---

## Sequential Execution Pipeline

The analysis pipeline processes codebase artifacts through multi-stage sequential passes to eliminate non-code noise early and aggregate global repository properties across files.

### Phase 0: Project Census & Pre-Flight Validation
Initializes the scan by querying the Git index (or executing a filesystem walk if Git authority is unavailable). Performs path validation to purge broken symlinks or deleted references, tallies file extension distributions, and applies folder micro-file quotas to exclude low-value assets.

### Phase 1: Parallel Lexical Extraction (Map-Reduce)
Spawns a multi-core `ProcessPoolExecutor` to analyze files concurrently across worker memory spaces, bypassing Python's Global Interpreter Lock (GIL). Worker processes pass each file through the File Filter (`aperture.py`), Language Identifier (`language_lens.py`), Lexical Splicer (`prism.py`), and Structural Analyzer (`detector.py`). A 15-second execution timeout guard is enforced per file to prevent Regular Expression Denial of Service (ReDoS) stalls.

### Phase 1.5: Dependency Graph Resolution & Security Checking
Builds an $O(1)$ pre-computed suffix hash map to resolve raw import strings to physical repository file paths. Simultaneously executes Levenshtein distance checks on external dependencies to detect potential typosquatting or homoglyph library threats.

### Phase 2: Relational Aggregation & Global Context
Evaluates repository-wide relationships across directories:
* **Directory Ecosystem Classification:** Tallies language distributions per folder to establish dominant ecosystem contexts (e.g., frontend vs. backend), penalizing anomalous cross-domain language placement.
* **Repository Test Umbrella:** Calculates aggregate test code density to apply global defense score bonuses repository-wide.

### Phase 3: Directed Graph Topology & Centrality Metrics
Constructs a directed dependency graph via `NetworkRiskSensor` using resolved imports. Computes PageRank (structural dependency mass), Betweenness centrality (architectural choke points), and Closeness centrality to define operational roles for every file.

### Phase 3.5: AI Guardrails & AppSec Threat Assessment
Evaluates codebase agentic security via `DevAgentFirewall` and `AIAppSecSensor`. Identifies over-permissioned execution hooks, LLM context-window limits, and prompt injection attack vectors that could expose systems to Remote Code Execution (RCE).

### Phase 4: Statistical Quality Audit
Runs Bayesian statistical quality checks via `StatisticalAuditor`. Enforces the 50/0 rule (flagging zero-signal code files over 50 lines) and robust Z-score density checks, excluding unparseable blobs from primary code metrics.

### Phase 5: Spatial Layout & Cartography
Transforms verified file node data into 3D spatial layout coordinates using a ray-casting Fibonacci packing algorithm in `detector.py` and spatial layout mappers.

### Phase 6: Metrics Synthesis & Drift Analysis
Executes Pass 2 metric normalization via `SignalProcessor`. Scales modification metrics logarithmically against repository maximums and measures biaxial architectural drift (global repository norms vs. local language patterns).

### Phase 7.8: Machine Learning Threat Inference
Ingests file metric feature matrices into an XGBoost multiclass model in `SecurityAuditor` to predict probabilities of trojan payloads, botnet routines, and obfuscated executables.

### Phase 8 & 9: Multi-Format Output Serialization
Routes processed graph state to configured exporters (Audit JSON, LLM Markdown context, SQLite database, WebGL visualization payload).

---

## Adaptive Configuration & Execution Overrides

The orchestrator supports dynamic configuration adjustments and runtime execution controls based on repository context:

### Domain Dialect Pre-Flight Patching
Checks scanning configuration for registered project dialects (e.g., CPython, Ansible, Redis). Live-patches regular expression rules and path filters to match specific framework conventions without breaking global standards.

### Worker Process Cache Pre-Warming
Pre-loads regular expression rule dictionaries into worker processes upon initialization (`LogicSplicer` cache warming). Prevents redundant regex compilation logs and eliminates CPU throttling during process pool execution.

### Runtime Security Policy Switches (Zero-Trust Mode)
Allows runtime adjustment of security scanner thresholds. When executed with the `--paranoid` flag, the orchestrator injects strict threat policies, lowering detection thresholds for memory corruption, command injection, and logic bombs.

### Critical Threat Asset Highlighting
Ensures critical security findings (e.g., exposed private keys flagged by `SecurityLens` or binary model files parsed by `NeuralAuditor`) are explicitly injected into visualization outputs, guaranteeing visual representation even if structural parsing was bypassed.

### Delta Scans via RAM Rehydration
Supports incremental scans (`execute_delta_mission`). Rehydrates previous scan results into memory, re-analyzing only added or modified files through Phase 1 before instantly recalculating global graph metrics and ML inferences (Phases 2-7).

### Selective Output Serialization
Includes dedicated CLI output flags (`--gpu-only`, `--audit-only`, `--llm-only`, `--db-only`) that bypass unneeded formatting passes, reducing memory usage and disk I/O latency.

### Immutable Session Metadata Locking
Attaches an immutable `session_meta` dictionary to generated output artifacts, recording engine version, scan duration, Git commit SHA-1 hash, branch name, remote repository URL, and commit timestamp for regulatory and compliance tracking (SBOM).

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Pipeline source code and execution modules.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - WebGL graph cartography interface.

---

**[⬅️ Back to Master Index](index.md)**

