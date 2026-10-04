---
description: "You are operating within `fastapi`, a modern, high-performance web framework for building APIs with Python (96.4%). It is heavily reliant on Python..."
---
# AGENTS.md: fastapi Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `fastapi`, a modern, high-performance web framework for building APIs with Python (96.4%). It is heavily reliant on Python type hints (Pydantic) and asynchronous execution (Starlette). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 9.902. The network topology demonstrates a Hub-and-Spoke model with high Modularity (0.4272) but neutral Assortativity (0.0). This indicates that while the framework components (routing, dependencies, security) are logically separated, they all heavily rely on a few massive, centralized routing and execution orchestrators.
* **Core Rule:** Respect the separation of concerns between Pydantic (data validation), Starlette (ASGI/routing mechanics), and FastAPI (the glue and OpenAPI generation). Do NOT attempt to rewrite core ASGI logic unless absolutely necessary; favor dependency injection.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core routing functions (`app` in `fastapi/routing.py`) and type inspection utilities (`field_annotation_is_scalar_sequence` in `fastapi/_compat/shared.py`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep AST parsing and generic type resolution. You MUST NOT introduce unbounded recursive loops, heavy synchronous blocking operations, or deep reflection within the routing or dependency injection execution paths.
* **Orchestrator Fragility:** Central orchestrators like `fastapi/routing.py` (36 outbound dependencies) and `fastapi/applications.py` (34 outbound dependencies) are highly fragile. Modifying route generation, middleware stacks, or OpenAPI schema building requires immediate, comprehensive verification via the massive integrated test suite (thousands of tests in `tests/`).
* **Avoid Dead Code Pruning:** The extensive `tests/` directory contains numerous files with high volumes of logic flagged as "dead code" (e.g., `tests/test_path.py` with 75 orphaned functions). DO NOT autonomously attempt to prune, format, or clean up these files. FastAPI heavily utilizes dynamic test generation (pytest fixtures) and reflection which bypasses static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, route parsing, or public APIs of these files:
* `fastapi/routing.py` (Highest Cumulative Risk, 83.3% Key Person Silo by Sebastián Ramírez. The core route execution engine).
* `scripts/docs.py` (Massive Structural Mass: 1341.64. Key Person Silo - 100% isolated ownership. Controls the documentation generation pipeline).
* `fastapi/types.py` (Severe Blind Bottleneck - 17 inbound connections flying blind with 66.6% Doc Risk).
* `fastapi/security/http.py` (House of Cards - Deeply embedded with high Error Risk).
* `tests/test_response_model_as_return_annotation.py` (Key Person Silo - 100% isolated ownership. Critical regression testing for Pydantic integration).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files handling routing (`fastapi/routing.py`) and security extraction (`fastapi/security/http.py`) possess high exposure for Exploit Generation. Because FastAPI automatically parses and executes user-provided JSON/Form payloads, you MUST ensure strict adherence to Pydantic validation boundaries to prevent Deserialization Attacks or arbitrary execution.
2. **Weaponizable Injection Vectors:** The testing suite (e.g., `tests/test_default_response_class.py`) possesses 100% Exposure for Injection Vectors. When simulating malicious payloads or edge cases, ensure the test isolation remains intact.
3. **Supply Chain:** There is 1 unknown dependency bypassing the Zero-Trust whitelist. Do not add or bump external pip packages without explicit architectural review, as FastAPI is highly sensitive to Pydantic and Starlette versioning.

## 5. Environmental Tooling (The Oracle)
Do not guess ASGI scopes, hallucinate Pydantic V1/V2 compatibility layer internals (`fastapi/_compat/`), or rely on generalized Python knowledge to determine blast radius within this 80k+ LOC framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
