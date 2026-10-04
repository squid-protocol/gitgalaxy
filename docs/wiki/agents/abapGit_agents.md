---
description: "You are operating within `abapGit`, an ecosystem primarily composed of ABAP logic (52.5%) and XML structural definitions (45.9%)."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `abapGit`, an ecosystem primarily composed of ABAP logic (52.5%) and XML structural definitions (45.9%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species but exhibits a high Architectural Drift Z-Score of 5.952. Standard modular design patterns DO NOT FULLY APPLY here. The architecture relies on unique, highly centralized parsing and Git delta calculation logic. Do not attempt to force boilerplate architectural patterns onto this codebase.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The core diffing, JSON mapping, and authorization classes (`zcl_abapgit_diff3.clas.abap`, `zcl_abapgit_ajson_mapping.clas.locals_imp.abap`, `zcl_abapgit_auth.clas.abap`) already operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursive loops or O(N^2+) complexity when modifying diff logic or serializers.
* **Orchestrator Fragility:** Core execution hubs such as `zabapgit_parallel.fugr.saplzabapgit_parallel.abap`, `zcl_abapgit_ui_factory.clas.abap`, and `zabapgit.prog.abap` are highly fragile coordinators with heavy outbound dependencies. Any changes to data contracts within these files require immediate verification of downstream integration.
* **Avoid Dead Code Pruning:** Test files such as `zcl_abapgit_flow_logic.clas.testclasses.abap` contain high volumes of orphaned (dead) functions. DO NOT autonomously attempt to prune or refactor these test files unless explicitly instructed by the user.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Lars Hvam, Marc Bernard). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures or public APIs of these files:
* `src/ui/zabapgit_js_common.w3mi.data.js` (Highest Cumulative Risk & Volatility Hotspot)
* `src/diff/diff3/zcl_abapgit_diff3.clas.abap` (Key Person Silo - Lars Hvam & Extreme I/O Latency)
* `src/ui/zcl_abapgit_popups.clas.abap` (Key Person Silo - Lars Hvam)
* `src/objects/zcl_abapgit_object_fugr.clas.abap` (Key Person Silo - Marc Bernard)
* `src/ui/flow/zcl_abapgit_flow_logic.clas.testclasses.abap` (Extreme Churn Hotspot - 84.76%)
* `ci/push-tag.sh` & `ci/deploy-release-tag.sh` (Blind Bottlenecks - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. No critical weaponizable surfaces or supply chain anomalies exist. You may operate freely without triggering external firewall or Zero-Trust isolation protocols, provided you do not introduce external dependencies. 

*Note: `src/ui/zabapgit_js_common.w3mi.data.js` contains a high Exploit Generation Surface due to raw DOM manipulation; proceed with strict input validation if modifying UI event listeners.*

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized ABAP knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
