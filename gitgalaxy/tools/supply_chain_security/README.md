# GitGalaxy Security: Supply Chain & CI/CD Defense Suite

This directory contains the CI/CD gating mechanisms, pre-commit hooks, and dependency validation engines for the GitGalaxy architecture. 

Standard Software Composition Analysis (SCA) tools inherently possess a critical blind spot: they act as manifest readers. They scan `package.json` or `requirements.txt` and cross-reference those declarations against known CVE databases. Modern supply chain compromises bypass this entirely by omitting malicious payloads from the manifest declarations, burying the threat in transit, or executing it dynamically during installation.

The GitGalaxy Supply Chain Security Suite operates on a strict Zero-Trust model. Powered by our AST-free Structural Signature Analysis Engine, these tools bypass manifest assumptions and physically scan the structural mechanics of every dependency file on disk and in RAM before it is permitted to enter the build pipeline.

---

## Architectural Philosophy & Defensive Engineering

To intercept zero-day supply chain compromises, steganography, and credential leaks without introducing developer friction or CI/CD bottlenecks, these modules employ several high-velocity defensive paradigms:

### 1. Zero-Trust Dependency Verification
Manifests can be spoofed. The `supply_chain_firewall.py` ignores dependency declarations and instead parses the actual, physical `import` and `require` statements within the downloaded `node_modules` or `venv` directories. It maps this physical execution graph against strict enterprise allowlists, instantly flagging unauthorized network requests, nested typosquatting, or anomalous I/O hooks.

### 2. High-Velocity Secret Detection
Pre-commit hooks must operate in milliseconds, or developers will bypass them. `vault_sentinel.py` utilizes a two-tier approach. Tier 0 performs instant O(1) path evaluation, blocking high-risk file extensions (e.g., `.pem`, `id_rsa`) before disk I/O occurs. Tier 1 executes deep content scanning to isolate exposed cryptographic keys and SaaS tokens—even if they are buried in commented-out logic or deprecated trails.

### 3. Heuristic Binary Triage (Zero-RAM Memory Shielding)
Advanced compromises often hide executable logic inside seemingly inert static assets. `binary_anomaly_detector.py` performs localized binary triage without uploading artifacts to cloud sandboxes. It validates structural magic bytes to catch scripts disguised as images, and utilizes mathematically optimized Shannon Entropy calculations to flag highly obfuscated or packed payloads (Entropy > 4.8) without exhausting system memory.

---

## Core Modules (The Sentinels)

The first three files below live in this directory and act as discrete, specialized firewalls for your development and deployment pipelines. `manifest_parser.py` lives in `gitgalaxy/security/` (it's a shared parser also used outside this suite) and feeds the firewall the resolution data it needs:

* **`supply_chain_firewall.py` (Dependency Integrity Gate):** Scans the physical execution graph of downloaded dependencies. It cross-references the core engine's structural telemetry to block packages exhibiting unauthorized behavioral heuristics (e.g., unexpected data injection routines, execution of OS-level processes during installation).
* **`binary_anomaly_detector.py` (Binary Anomaly Detector):** Designed for rapid triage of binaries and obfuscated files. It detects embedded execution headers hidden inside static data, validates file extension integrity, and flags high cryptographic entropy (Entropy > 4.8) indicating packed malware or byte-level obfuscation loops.
* **`vault_sentinel.py` (Vault Sentinel):** A pre-commit hook strictly for localized credential detection. It enforces Tier 0 path blocking and executes deep-content cryptographic scans to prevent hardcoded cloud keys, database passwords, and API tokens from entering version control.
* **`manifest_parser.py` (SSCS Manifest Auditor, `gitgalaxy/security/`):** Parses ecosystem manifests (NPM, PyPI) to build a deterministic resolution map. It detects namespace hijacking, unverified direct-URI resolutions, and insecure registry routing, and hands the flagged entries to the firewall above to enforce.

---

## Engineering Highlights (How It Works at Scale)

* **RAM-Exclusive Policy Enforcement (`supply_chain_firewall.py`):** Typical firewalls perform redundant O(N) disk parsing. This firewall consumes the pre-computed Dependency Graph from Phase 1. By completely divesting from disk I/O, it achieves near-instant behavioral policy enforcement across tens of thousands of dependencies.
* **Build-Time Execution Multipliers (`supply_chain_firewall.py`):** Configuration scripts (like `setup.py` or `package.json` hooks) are executed by CI/CD runners at build time. Remote Code Execution (RCE) here compromises the host before the application even runs. The engine applies an artificial 10x structural density multiplier to manifest triggers, ensuring any I/O or High-Risk Execution signatures instantly trip the firewall.
* **Namespace Dereferencing & Hijack Mitigation (`manifest_parser.py`):** To catch Dependency Confusion attacks where a malicious package masks itself behind a trusted internal alias, the parser normalizes NPM/PyPI aliases to their true upstream packages. It flags direct URI resolutions (which bypass Subresource Integrity checks) and flags insecure protocols or tunneling services (e.g., `ngrok`) hiding in `pip.conf` for the firewall to block.
* **O(1) Memory Shielding for Binary Triage (`binary_anomaly_detector.py`):** Attempting to calculate the Shannon Entropy of a 2GB binary blob will immediately trigger an Out-Of-Memory (OOM) crash in a CI runner. This detector mathematically guarantees pipeline survival by capping its read buffer at 8KB—sufficient to capture magic bytes, execution headers, and enough string data for accurate entropy calculation without memory exhaustion.

---

## Performance Showcases

#### Showcase A: Vault Sentinel (Secret Detection)
To prove this engine operates fast enough to be a synchronous pre-commit hook without frustrating developers, we executed the **Vault Sentinel** against the massive **tRPC** TypeScript monorepo. 

The engine evaluated 871 files and performed deep-content cryptographic scans on 695 of them in **0.53 seconds** (processing over 1,300 files per second). It successfully intercepted 7 exposed environment files and caught a hardcoded API key before the commit could execute.

![Vault Sentinel Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/vault_sentinel_scan.gif)

#### Showcase B: Binary Anomaly Detector (Malware & Binary Triage)
To test binary detection, we ran the **Binary Anomaly Detector** against **pwntools**, an exploit development framework containing actual compiled binaries and shellcode.

The engine processed the repository at a velocity of **2,825 files per second**. By reading the raw physical bytes rather than trusting file extensions, it instantly detected 13 embedded `ELF` execution headers hidden inside the source tree.

![Binary Anomaly Detector Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/xray_inspector_scan.gif)

~~~text
===========================================================================
 BINARY ANOMALY DETECTOR: SCAN SUMMARY
===========================================================================
 Files Evaluated    : 95
 Files Deep Scanned : 95
 Time Elapsed       : 0.03 seconds
 Scan Velocity      : 2,825 files/sec
---------------------------------------------------------------------------
 Anomalies Detected : 13
---------------------------------------------------------------------------
 [BLOCKING ACTION] 13 structural anomalies detected. Failing pipeline.
~~~

#### Showcase C: Supply Chain Firewall (Infrastructure-as-Code Audit)
To prove the firewall can handle diverse polyglot ecosystems without throwing false positives, we ran it against the **Terraform** repository. 

The engine parsed 1,834 files at a velocity of **436 files per second**. It successfully verified the integrity of the dependency tree, identified 54 unknown packages for audit, and cleared the build without tripping any false alarms on standard Go/HCL syntax.

![Supply Chain Firewall Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/terraform_firewall_scan.gif)

~~~text
===========================================================================
 SUPPLY CHAIN FIREWALL: SCAN SUMMARY
===========================================================================
 Mode               : Audit (Allow Whitelist + Unknown, Exclude Blacklist)
 Files Deep Scanned : 1,834
 Scan Velocity      : 436 files/sec
---------------------------------------------------------------------------
 Approved Packages    : 0
 Banned Packages      : 0
 Unknown Packages     : 54
---------------------------------------------------------------------------
 Active Threats       : 0
---------------------------------------------------------------------------
 [SUCCESS] Dependency supply chain is clean.
~~~

---

## CI/CD & Pre-Commit Integration

These sentinels are designed to be wired directly into your Git workflows to fail compromised builds autonomously.

**Local Pre-Commit Hook Integration:**
To run the Vault Sentinel automatically before every commit, add this configuration to your `.pre-commit-config.yaml` file:

~~~yaml
repos:
  - repo: local
    hooks:
      - id: gitgalaxy-vault-sentinel
        name: GitGalaxy Vault Sentinel
        entry: vault-sentinel
        language: system
        types: [text]
        pass_filenames: true
~~~

**GitHub Actions Integration:**
You can deploy these sentinels directly into your CI/CD pipeline using the official [GitGalaxy GitHub Action](https://github.com/marketplace/actions/gitgalaxy-scanner).

~~~yaml
name: GitGalaxy Zero-Trust Audit
on: [pull_request]

jobs:
  gitgalaxy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run GitGalaxy Supply Chain Firewall
        uses: squid-protocol/gitgalaxy@v2.0.7
        with:
          tool: 'supply-chain-firewall'
~~~

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Security is the threat inference and enforcement layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.