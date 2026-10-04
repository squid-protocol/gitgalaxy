---
description: "You are operating within `flask`, a lightweight but deeply established WSGI web application framework. The repository is heavily dominated by Python..."
---
# AGENTS.md: flask Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `flask`, a lightweight but deeply established WSGI web application framework. The repository is heavily dominated by Python (66.9%) and HTML templates (16.1%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 8.246. The network topology demonstrates moderate Modularity (0.415) but significantly negative Assortativity (-0.2377). This signifies a classic "hub-and-spoke" architecture where the entire framework revolves around a few massive, centrally coupled orchestrators (e.g., `app.py`, `cli.py`) and foundational typing/global modules.
* **Core Rule:** Maintain strict adherence to Flask's established separation between I/O-bound layers and the pure-logic `sansio` (Sans-I/O) modules. Do NOT attempt to decouple foundational orchestrators or introduce external dependencies.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core route registration (`register` in `src/flask/sansio/blueprints.py`), template discovery (`list_templates` in `src/flask/templating.py`), and context management (`pop` in `src/flask/ctx.py`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce additional nested recursion, dynamic imports on hot paths, or heavy synchronous loops within the request context or blueprint registration pipelines.
* **Orchestrator Fragility:** Central orchestrators such as `src/flask/app.py` (37 outbound dependencies) and `src/flask/cli.py` (30 outbound dependencies) are extremely fragile. Any changes to application setup, middleware stacks, or CLI command resolution require immediate, comprehensive verification via the Pytest suite.
* **Avoid Dead Code Pruning:** Test files (`tests/test_basic.py` with 90 orphaned functions, `tests/test_blueprints.py` with 47 orphaned functions) contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Flask's test suite relies heavily on dynamic Pytest fixtures, reflection, and localized decorator execution that bypasses static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, lifecycle hooks, or public APIs of these files:
* `src/flask/app.py` & `src/flask/sansio/app.py` (Massive Structural Mass, High Churn. The central application state objects. 100% isolated ownership by David Lord).
* `src/flask/cli.py` (High Cumulative Risk, Key Person Silo - 100% isolated ownership by David Lord).
* `src/flask/ctx.py` (Extreme Volatility Hotspot: 99.4% Churn, 92.9% Tech Debt. Manages the request/app context locals).
* `src/flask/typing.py` (Severe Blind Bottleneck / House of Cards - 22 inbound connections flying blind with 82.5% Doc Risk).
* `src/flask/sansio/scaffold.py` (High Risk: 568.11 Cumulative Risk, 96.1% Tech Debt. Handles core application structure logic).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Code handling dynamic module loading and path resolution (`src/flask/sansio/scaffold.py`) possesses near 100% Exposure for Exploit Generation. Because Flask handles arbitrary user-defined structures and configurations, you MUST ensure strict path canonicalization and sanitization to prevent Directory Traversal or arbitrary code execution.
2. **Weaponizable Injection Vectors:** The testing suite (`tests/test_blueprints.py`, `tests/test_templating.py`) possesses 100% Exposure for Injection Vectors. When simulating malicious payloads or Jinja template edge cases, ensure the test isolation boundaries remain intact.
3. **Hardcoded Payload Artifacts:** `tests/test_apps/.env` is flagged for hardcoded payloads. DO NOT flag this as a leaked secret; it is an explicit configuration fixture required for testing environment variable loading.

## 5. Environmental Tooling (The Oracle)
Do not guess WSGI/ASGI transition boundaries, hallucinate context-local proxy resolutions (`werkzeug.local`), or rely on generalized Python web framework knowledge to determine blast radius within this highly mature system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
