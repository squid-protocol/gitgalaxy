---
description: "You are operating within `ack3`, an ecosystem primarily composed of Perl logic (56.6%) and heavily reliant on an extensive testing framework (the `t/`..."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `ack3`, an ecosystem primarily composed of Perl logic (56.6%) and heavily reliant on an extensive testing framework (the `t/` directory contains almost half the repository's mass).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species with an Architectural Drift Z-Score of 5.478. The architecture is procedurally driven by a massive, monolithic entry point script (`ack`). Standard object-oriented or decoupled design patterns DO NOT APPLY here. Do not attempt to force modular decoupling onto the core monolith.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The core application (`ack`) and the testing utilities (`t/Util.pm`) contain deep, computationally expensive recursive functions (e.g., `print_line_with_options` operating at O(2^N) with a DB Complexity of 505). You MUST NOT introduce additional nested loops or recursive execution paths within these bottlenecks.
* **Orchestrator Fragility:** The primary `ack` script acts as a fragile orchestrator pulling in 23 outbound dependencies. Any changes to data contracts, argument parsing, or file filtering within this script require immediate, comprehensive verification against the `t/` test suite.
* **Avoid Tech Debt Pruning:** Files such as `dev/docker/docker-entrypoint.sh` and legacy components (`stack`, `tack`) exhibit 100% Tech Debt Exposure. DO NOT autonomously attempt to prune or "clean up" these files unless explicitly instructed.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silo: Andy Lester). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures or public APIs of these files:
* `ack` (The Core Monolith - Extreme Mass: 9357.12, 100% isolated ownership by Andy Lester)
* `t/Util.pm` (The Testing Foundation - Extreme Blast Radius: 246.0, 100% Churn Volatility, 100% Documentation Risk)
* `t/mutex-options.t` (Key Person Silo and High State Flux)
* `dev/crank-mutex` (Key Person Silo)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Supply Chain anomalies. 

**CRITICAL WARNING:** `t/Util.pm` and `ack` possess a 100% Exposure score for **Weaponizable Injection Vectors** and **Exploit Generation Surface**. This is due to heavy reliance on system command execution (e.g., `run_cmd` and `run_piped`). When modifying these files, you MUST ensure strict input sanitization and avoid passing untrusted data directly into shell or execution contexts. 

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Perl knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
