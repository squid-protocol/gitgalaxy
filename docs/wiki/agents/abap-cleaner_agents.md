---
description: "You are operating within `abap-cleaner`, a repository overwhelmingly composed of Java (97.3%)."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `abap-cleaner`, a repository overwhelmingly composed of Java (97.3%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species but exhibits a severe Architectural Drift Z-Score of 9.447. Standard Java MVC or modular design patterns DO NOT APPLY here. The architecture relies on highly unique, centralized parsing logic and tightly coupled GUI orchestrators. Do not attempt to force boilerplate design patterns onto this codebase.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The core parsing and comparing classes (`CompareDoc.compareTo`, `RuleForLogicalExpressions.executeOn`, `Profile.getLoadPaths`) already operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursive loops or O(N^2+) complexity when modifying the parser or AST logic.
* **Orchestrator Fragility:** GUI classes such as `AbapCleanerHandlerBase.java`, `FrmMain.java`, and `FrmProfiles.java` are highly fragile coordinators with heavy outbound dependencies (36+ outbound imports each). Any changes to data contracts within these files require immediate verification of downstream integration.
* **Avoid Dead Code Pruning:** Test files such as `AlignParametersTest.java` and `TokenTest.java` contain hundreds of orphaned (dead) functions. DO NOT autonomously attempt to prune or refactor these test files unless explicitly instructed by the user.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or 100% isolated human ownership (Key Person Silo: Jörg-Michael Grassau). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures or public APIs of these files:
* `com.sap.adt.abapcleaner/src/com/sap/adt/abapcleaner/parser/Token.java` (Extreme Mass & Churn Hotspot)
* `com.sap.adt.abapcleaner/src/com/sap/adt/abapcleaner/parser/Command.java` (Extreme Mass & Churn Hotspot)
* `com.sap.adt.abapcleaner/src/com/sap/adt/abapcleaner/rulehelpers/CommentIdentifier.java` (High Logic Execution Complexity)
* `com.sap.adt.abapcleaner.gui/src/com/sap/adt/abapcleaner/gui/CodeDisplay.java` (Blind Bottleneck - 100% Documentation Risk)
* `com.sap.adt.abapcleaner.gui/src/com/sap/adt/abapcleaner/gui/FrmMain.java` (Key Person Silo)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. No critical weaponizable surfaces or supply chain anomalies exist. You may operate freely without triggering external firewall or Zero-Trust isolation protocols, provided you do not introduce external dependencies.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Java knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
