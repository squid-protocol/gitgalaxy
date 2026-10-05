---
description: "You are operating within `ansible`, a configuration management and automation ecosystem primarily composed of YAML (41.5%) and Python (36.2%)."
---
# AGENTS.md: ansible Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `ansible`, a configuration management and automation ecosystem primarily composed of YAML (41.5%) and Python (36.2%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.54. The network topology demonstrates relatively clean micro-boundaries (Modularity 0.495) but negative assortativity (-0.1021), indicating the architecture relies on fragile, highly connected hub nodes (single points of failure). Do not attempt to introduce decentralized patterns or bypass established core utilities when handling variable resolution or collection loading.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core utility methods (`merge_hash` in `lib/ansible/utils/vars.py`, `__call__` in `lib/ansible/utils/singleton.py`, and various argument parsers in `hacking/`) currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying configuration merging, plugin loading, or variable resolution logic.
* **Orchestrator Fragility:** Central coordinators such as `lib/ansible/utils/display.py` (36 outbound dependencies) and `packaging/release.py` (34 outbound dependencies) are highly fragile orchestrators. Any changes to data contracts, display formatting, or public properties within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Test files (`test/units/utils/collection_loader/test_collection_loader.py` with 42 orphaned functions) and core utilities (`lib/ansible/utils/display.py`) contain high volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as dynamic plugin loading and reflection may rely on these structures.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, recursive logic, or public APIs of these files:
* `lib/ansible/utils/collection_loader/_collection_finder.py` (Extreme Volatility Hotspot: 97.28% Churn, 98.2% Tech Debt)
* `lib/ansible/utils/display.py` (Highest Cumulative Risk: 591.09, 100% Logic Bomb Exposure)
* `packaging/release.py` (Key Person Silo - 100% isolated ownership by Matt Clay)
* `lib/ansible/cli/scripts/ansible_connection_cli_stub.py` (Key Person Silo - 100% isolated ownership by Martin Krizek)
* `lib/ansible/parsing/utils/yaml.py` (House of Cards - Embedded core utility with 78.3% Error Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH FIXTURE CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** `hacking/azp/incidental.py`, `lib/ansible/utils/display.py`, and `test/units/utils/collection_loader/test_collection_loader.py` possess a 100% Exposure score for Exploit Generation Surface. When modifying logging, display utilities, or collection loading, you MUST ensure strict input sanitization to prevent arbitrary code execution or template injection.
2. **Hardcoded Payload Artifacts:** The `test/units/module_utils/urls/fixtures/cbt/` directory contains hardcoded `.pem` payload artifacts (e.g., `ecdsa_sha256.pem`, `rsa_md5.pem`). These are explicitly for testing SSL/TLS behaviors. DO NOT flag these as leaked secrets or attempt to remove/obfuscate them.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python/Ansible knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
