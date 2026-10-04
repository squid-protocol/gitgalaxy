---
description: "You are operating within `docker-py`, the official Python library for the Docker Engine API. The repository is predominantly Python (81.1%), focusing..."
---
# AGENTS.md: docker-py Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `docker-py`, the official Python library for the Docker Engine API. The repository is predominantly Python (81.1%), focusing heavily on network I/O, socket management, and JSON serialization.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 9.039. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly centralized, "hub-and-spoke" architecture where almost all API clients and models converge on a single, load-bearing socket abstraction layer (`docker/utils/socket.py`).
* **Core Rule:** Do NOT attempt to introduce object-oriented decoupling or dependency injection patterns that bypass the core `APIClient` or `DockerClient` initialization flows. The architecture is locked into a rigid delegation pattern.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core stream parsing and networking functions (`_stream_helper` in `docker/api/client.py`, `read` in `docker/utils/socket.py`, `contexts` in `docker/context/api.py`) operate at O(2^N) recursive time complexities in static analysis due to blocking network reads, chunked data processing, and recursive directory walking (`docker/utils/build.py`). You MUST NOT introduce unbounded recursive loops, unbounded file system traversals, or heavy synchronous data manipulation into these hot paths.
* **Orchestrator Fragility:** Central orchestrators such as `docker/api/client.py` (29 outbound dependencies) and `docker/utils/utils.py` (14 outbound dependencies) are highly fragile. Any changes to kwargs processing, API version negotiation, or payload serialization require immediate, comprehensive verification against the integration test suite.
* **Avoid Dead Code Pruning:** Files like `docker/transport/npipesocket.py` (23 orphaned functions) and various `__init__.py` files contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The SDK utilizes dynamic method binding and conditional platform imports (e.g., Windows Named Pipes vs. Unix sockets) that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent severe blind bottlenecks. 

**MANDATORY RULE:** You require explicit human permission and downstream containerized testing before modifying the structural signatures, I/O handling, or public APIs of these files:
* `docker/utils/socket.py` (Severe Blind Bottleneck and House of Cards - 44.7 Blast Radius with 61.9% Doc Risk. A failure here breaks the entire SDK).
* `docker/context/context.py` (High Cumulative Risk: 514.93, handles sensitive TLS and credential context).
* `docker/types/containers.py` (Massive Structural Mass: 4142.62, 99.5% Exploit Generation Surface due to raw `exec` capabilities).
* `docker/api/client.py` (The primary execution orchestrator; handles raw HTTP interaction with the Docker daemon).
* `docker/utils/utils.py` (Extreme Tech Debt: 91.0%, highly volatile with complex keyword argument unpacking).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SHELL EXECUTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files related to container lifecycle management (`docker/types/containers.py`) and context definition (`docker/types/services.py`) possess high exposure for Exploit Generation. Because the SDK allows users to mount volumes, execute commands (`exec_run`), and manipulate host networking, ensure any modifications to argument parsing do not inadvertently bypass Docker daemon security configurations.
2. **Hardcoded Payload Artifacts:** The `tests/ssh/config/` and `tests/unit/testdata/certs/` directories tripped hardcoded payload signatures (100% Exposure). DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying SSH and TLS connectivity.
3. **Supply Chain:** There are 0 unknown dependencies bypassing the Zero-Trust whitelist. Do not add external dependencies to `setup.py` or `pyproject.toml` without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Docker API version behaviors, hallucinate Named Pipe implementation details, or rely on generalized Python `requests` knowledge to determine blast radius within this specialized client. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
