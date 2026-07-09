# GitGalaxy Tools: Decoupled Execution Controllers & DevSecOps Suite

[![Architecture](https://img.shields.io/badge/Architecture-Decoupled_Controllers-8A2BE2.svg)](#)
[![Performance](https://img.shields.io/badge/Performance-AST--Free_Velocity-00BFFF.svg)](#)
[![Security](https://img.shields.io/badge/Security-Zero--Trust_Pipelines-FF4500.svg)](#)

Welcome to the **GitGalaxy Tools** directory. 

These tools are specific operational deployments of the blAST engine. These are specialized, standalone execution controllers that leverage GitGalaxy's AST-free, high-speed parsing capabilities to solve specific engineering, compliance, and legacy migration challenges at planetary scale.

Each sub-module is designed to execute strictly in $O(1)$ or linear $O(N)$ time complexity, making them uniquely suited for direct integration into high-velocity CI/CD pipelines without introducing latency or Out-Of-Memory (OOM) crashes.

---

## 📂 Ecosystem Suites & Tooling

### 🛡️ [Supply Chain & CI/CD Defense Suite](./supply_chain_security/README.md)
Zero-Trust DevSecOps tools designed for pre-commit hooks and CI/CD pipeline blocking.
* **Supply Chain Firewall:** Scans the physical execution graph of downloaded dependencies to block unauthorized network I/O, typosquatting, and RCE vulnerabilities during installation.
* **Vault Sentinel:** Hyper-speed, two-tier pre-commit hook for detecting exposed cryptographic keys and SaaS tokens.
* **Binary Anomaly Detector:** A localized triage engine that utilizes Shannon Entropy to detect packed malware and execution headers hidden inside static binary artifacts.

### 🕵️ [High-Velocity Log Streaming & Incident Response](./terabyte_log_scanning/README.md)
Unindexed binary streaming engines for processing massive data outputs without RAM exhaustion.
* **PII Leak Hunter:** Streams terabytes of raw database/server logs to instantly detect and redact accidentally exposed PII (SSNs, Credit Cards, AWS Keys).
* **Terabyte Log Scanner:** Maps static architecture to dynamic runtime execution logs to mathematically prove dead code abandonment or isolate brute-force anomalies.

### 🕸️ [API Network Auditing](./network_auditing/README.md)
* **Full API Network Mapper:** Automatically extracts physical outbound and inbound API routing intents across 9+ frameworks (Spring, Express, FastAPI) and compares them against OpenAPI/Swagger docs to expose undocumented **Shadow APIs**.

### 🦕 [Mainframe Modernization Suite](./cobol_to_java/README.md) & [Structural Extraction](./cobol_to_cobol/README.md)
A complete suite of deterministic architectural controllers for modernizing monolithic legacy systems without relying on hallucination-prone LLMs.
* **Deprecated Trails Analyzer & DAG Architect:** Identifies dead mainframe memory and mathematically derives execution topologies.
* **Microservice Logic Extractor:** Performs recursive data-flow taint tracking to isolate COBOL business rules.
* **Java Spring Boot Forge:** Deterministically translates COBOL architectures into 100% compiling Java Spring `@Entity` models, `@RestController` endpoints, and Maven build systems.

### 🤖 [Dual-Sided AI Guardrails](./ai_guardrails/README.md)
* **AppSec Sensor & Dev Agent Firewall:** Deep-inspection middleware sensors. They detect **Autonomous Execution Vectors** to prevent LLMs from being wired to RCE vulnerabilities, and mathematically constrain autonomous AI coding agents from corrupting highly complex legacy code.

---

## 🚀 Execution & CI/CD Integration

The GitGalaxy decoupled architecture allows you to run these specialized tools using three distinct methods:

### 1. GitHub Actions (The Universal Pipeline)
You can trigger any of the standalone CLI tools securely in your CI/CD pipeline using our universal composite action. Simply change the `tool` parameter to the controller you want to execute:

```yaml
      - name: Run GitGalaxy Tool
        uses: squid-protocol/gitgalaxy@main
        with:
          tool: 'supply-chain-firewall' # Options: vault-sentinel, zero-trust-sbom, api-network-map, etc.
          target: '.'
```

### 2. Global CLI Execution
If you have GitGalaxy installed via PyPI (`pip install gitgalaxy`), all the standalone tools are registered as global console scripts. You can run them instantly from your terminal during active incident response or local auditing:

```bash
vault-sentinel .
api-network-map ./src
pii-leak-hunter ./logs/dump.sql
```

### 3. Engine Middleware (AI Guardrails)
Note that the **AI Guardrails** do not operate as standalone CLI tools. They act as deep-inspection middleware. To utilize them, run the primary GitGalaxy analysis engine, and the sensors will automatically inject their AppSec findings and Guardrail constraints into the final project telemetry.

---

## 🌌 The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Tools is the modular deployment layer of the broader **GitGalaxy Ecosystem**—a high-velocity, AST-free, LLM-free heuristic knowledge graph engine designed for planetary-scale repositories.

Explore the ecosystem:

* 🪐 **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* 🔭 **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* 📖 **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* ⚙️ **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.