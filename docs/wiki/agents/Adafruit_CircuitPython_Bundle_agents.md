---
description: "You are operating within `Adafruit_CircuitPython_Bundle`. This is a meta-repository/bundle manager primarily composed of Markdown documentation..."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `Adafruit_CircuitPython_Bundle`. This is a meta-repository/bundle manager primarily composed of Markdown documentation (37.5%), Plaintext (25.0%), and minor Shell/Python glue code (25.0%). 
* **Architectural Paradigm:** The repository exhibits an Architectural Drift Z-Score of 2.904 and relies on a massive amount of "Dark Matter" (854 unscanned artifacts, likely binary assets or submodules). This is NOT a standard application architecture; it is an aggregation hub. Do not attempt to force application-level design patterns (like MVC or OOP) onto these initialization and management scripts.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Submodule Operations:** The file `update-submodules.sh` operates as the primary state mutator for the bundle and currently possesses a 100% Tech Debt Exposure score. You MUST NOT autonomously refactor, "clean up", or prune logic within this shell script, as doing so may shatter the bundle's build pipeline.
* **Declarative Glue:** Scripts like `add_import_names.py` act as declarative glue. Do not attempt to increase their algorithmic complexity or add unnecessary asynchronous overhead.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing nodes for the bundle management process. They possess high technical debt, documentation risk, or structural mass relative to the repository size. 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures or execution logic of these files:
* `update-submodules.sh` (100% Tech Debt Exposure)
* `add_import_names.py` (Blind Bottleneck - High Blast Radius with low Documentation Coverage)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. No critical weaponizable surfaces or supply chain anomalies exist. You may operate freely without triggering external firewall or Zero-Trust isolation protocols, provided you do not introduce external dependencies.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python/Shell knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
