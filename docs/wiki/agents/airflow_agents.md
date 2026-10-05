---
description: "You are operating within `airflow`, a massive data orchestration ecosystem composed primarily of Python (75.1%) and TypeScript (8.8%)."
---
# AGENTS.md: airflow Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `airflow`, a massive data orchestration ecosystem composed primarily of Python (75.1%) and TypeScript (8.8%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.656. It contains heavy local sovereignty with tensor math/compute integrations (classified as Transceiver middle-tiers). The system's network topology reveals zero modularity and negative assortativity (-0.2068), indicating heavy reliance on monolithic central pillars rather than distributed fault tolerance. Do not attempt to force microservice or decoupled architectural patterns onto the core scheduler or DAG parsing engines.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core scheduling and routing functions (`airflow-core/src/airflow/jobs/scheduler_job_runner.py`'s `adopt_or_reset_orphaned_tasks`, FastAPI initializations, and DAG serialization logic) already operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or recursive logic when modifying DAG parsing, serialization, or task instance state machines.
* **Orchestrator Fragility:** Central coordinators such as `task-sdk/src/airflow/sdk/definitions/dag.py` (77 outbound dependencies), `scheduler_job_runner.py` (76 outbound), and core test plugins (`pytest_plugin.py`) are highly fragile orchestrators. Any changes to data contracts, DAG definitions, or public properties within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Test files (e.g., `airflow-core/tests/unit/jobs/test_scheduler_job.py` with 118 orphaned functions) and provider utilities contain hundreds of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as dynamic testing frameworks often rely on implicit fixture discovery.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as "Blind Bottlenecks" (deeply embedded with high documentation risk). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, configurations, or public APIs of these files:
* `task-sdk/src/airflow/sdk/definitions/param.py` (Highest Cumulative Risk: 686.0)
* `task-sdk/src/airflow/sdk/definitions/mappedoperator.py` (High Cumulative Risk: 623.66)
* `airflow-core/src/airflow/utils/json.py` (Severe Blind Bottleneck - 522 inbound dependencies flying blind)
* `task-sdk/src/airflow/sdk/serde/serializers/datetime.py` (Blind Bottleneck - 1030 inbound dependencies)
* `providers/ssh/src/airflow/providers/ssh/operators/ssh_remote_job.py` (Key Person Silo - 100% isolated ownership by Kaxil Naik)
* `providers/google/src/airflow/providers/google/cloud/operators/dataplex.py` (Key Person Silo - 100% isolated ownership by Ankit Chaurasia)
* `dev/breeze/src/airflow_breeze/utils/selective_checks.py` (High structural mass and 95.8% Tech Debt)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** `airflow-core/src/airflow/api_fastapi/auth/tokens.py`, `airflow-core/src/airflow/api_fastapi/common/parameters.py`, and public DAG run routes possess a 100% Exposure score. Any modification to these authentication and API validation layers must strictly enforce type checking and authorization scopes.
2. **Weaponizable Injection Vectors:** `dev/breeze/src/airflow_breeze/utils/path_utils.py` and CLI commands possess 100% Exposure for Injection Surfaces. When modifying these files, you MUST ensure strict input sanitization and avoid passing untrusted user input directly into shell, DB commands, or path resolutions.
3. **Supply Chain:** There are 629 unknown dependencies bypassing the Zero-Trust whitelist and 30 binary anomalies. Do not add or bump external provider dependencies without cross-referencing security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python knowledge to determine blast radius within this massive 1M+ LOC monorepo. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
