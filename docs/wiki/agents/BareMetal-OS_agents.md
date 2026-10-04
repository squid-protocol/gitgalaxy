---
description: "You are operating within `BareMetal-OS`, an operating system repository. Based on the visible architectural scan, the structural footprint is entirely..."
---
# AGENTS.md: BareMetal-OS Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `BareMetal-OS`, an operating system repository. Based on the visible architectural scan, the structural footprint is entirely dominated by a single execution artifact (`baremetal.sh`). 
* **Architectural Paradigm:** The repository functions as a "Cluster 3" macro-species with an Architectural Drift Z-Score of 4.072. It exhibits 0.0 Modularity and 0.0 Assortativity, indicating a flat, monolithic coupling structure. 
* **Dark Matter Awareness:** Be highly aware that the vast majority of the repository's artifacts (22 out of 25) are classified as "Dark Matter" (likely raw assembly, binaries, or unsupported extensions). You must not assume the shell script is the entire system; it is merely the orchestration/bootstrapping layer for the underlying OS.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The central `baremetal.sh` script possesses an extreme Database Complexity score of 219 and high Cognitive Load Exposure (49.8%). You MUST NOT introduce additional nested logic, complex parameter parsing, or heavy control-flow branching into this script.
* **Orchestrator Fragility:** `baremetal.sh` acts as the sole orchestrator for I/O and execution. Any modifications to its hardware emulation flags (e.g., QEMU device configurations, MAC addresses, disk controllers) require immediate, comprehensive verification of downstream runtime behavior.
* **Avoid Dead Code Pruning:** Static analysis has flagged orphaned functions within `baremetal.sh`. DO NOT autonomously attempt to prune or refactor these blocks, as shell-based hardware initialization scripts often rely on dynamic evaluation or environment-specific fallbacks that static analysis cannot reliably track.

## 3. Restricted Zones (The God Nodes)
The following file is a load-bearing "God Node." It possesses extreme cumulative risk, massive structural mass, volatile churn, and 100% isolated human ownership (Key Person Silo). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, execution flags, or operational logic of this file:
* `baremetal.sh` (The Core Monolith - Highest Cumulative Risk: 563.81, 100% Silo Risk by Ian Seyler)
    * *Note:* This file is considered a severe "Blind Bottleneck" with a Severity Score of 33333.3 (High Blast Radius × 100% Documentation Risk). Modifying this file is flying blind without explicit context.

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 
* **Security Posture:** While no explicit injection surfaces were detected in the scanned matter, you must treat all hardware configuration strings and network bridging commands within `baremetal.sh` as highly sensitive. Do not expose these configurations to untrusted external inputs.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized OS-level knowledge to determine blast radius within this highly specialized environment. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
