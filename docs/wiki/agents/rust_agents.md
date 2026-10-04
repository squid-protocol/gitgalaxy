---
description: "You are operating within the `rust` repository (`https://github.com/rust-lang/rust`). Based on the current GitGalaxy telemetry, the repository scan..."
---
# AGENTS.md: rust Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `rust` repository (`https://github.com/rust-lang/rust`). Based on the current GitGalaxy telemetry, the repository scan yielded an anomalous state: **0 visible artifacts and 0 lines of code scanned**. 

* **Architectural Paradigm:** The system is currently unclassified (Z-Score: 0.0) due to a lack of parseable structural mass. 
* **Information Flow:** Information flow, dependency graphs, and language composition cannot be traced. The engine is effectively blind to the internal syntax tree of the repository.
* **Core Rule:** Before engaging in standard architectural refactoring or feature development, you must resolve the telemetry and visibility failure within the scanning pipeline. Standard code-level guardrails cannot be enforced until the source tree is properly indexed.

## 2. Notable Structures & Architecture
Due to the scan resolving 0 active execution logic clusters and 0 dependencies, there is no mapping of structural load-bearers (highest inbound connections) or fragile orchestrators (highest outbound dependencies). The network topology is completely flat (Modularity: 0.0, Assortativity: 0.0).

## 3. Security & Vulnerabilities
**Status: UNVERIFIED PERIMETER (SCAN FAILURE).** While the XGBoost Threat Intelligence audits flagged 0 malicious artifacts, this is a byproduct of zero files being analyzed. 

**CRITICAL WARNINGS:**
1. **Supply Chain & Binary Anomalies:** Despite the lack of source code visibility, the ecosystem audit detected **63 Binary Anomalies** (high entropy, packed payloads, or magic byte mismatches) and **101 Unknown Dependencies** bypassing the Zero-Trust whitelist. These must be manually vetted to ensure they are standard compiler bootstrapping artifacts or test fixtures, rather than supply chain compromises.

## 4. Outliers & Extremes
No statistical anomalies, extreme risk hits, cognitive load spikes, or state flux outliers were detected because the underlying source matter is missing from the index.

## 5. Recommended Next Steps (Refactoring for Stability)
Given the anomalous telemetry, the immediate next steps are strictly operational rather than architectural:

1. **Diagnose Scanner Configuration:** Investigate the GitGalaxy data extraction pipeline targeting `/srv/storage_16tb/projects/gitgalaxy/data/rust`. Verify file permissions, `.gitignore` or `.gitattributes` exclusions, and ensure the engine has correct read access to the source tree. 
2. **Audit Binary Artifacts:** Prioritize a manual or secondary tool review of the 63 flagged binary anomalies. Since source-level static analysis is currently disabled, binary vetting is the primary line of defense against injected payloads.
3. **Verify Supply Chain Whitelist:** Reconcile the 101 unknown dependencies against the official Rust compiler (rustc) and Cargo bootstrap requirements to ensure a secure build environment.


---

**[⬅️ Back to Master Index](../index.md)**
