---
description: "You are operating within `bitcoin-0.1.0`, the historical original release of the Bitcoin software, primarily composed of monolithic C++ (78.8%)."
---
# AGENTS.md: bitcoin-0.1.0 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bitcoin-0.1.0`, the historical original release of the Bitcoin software, primarily composed of monolithic C++ (78.8%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species with a severe Architectural Drift Z-Score of 7.991. The network topology demonstrates highly negative assortativity (-0.8321), indicating an extremely fragile "hub-and-spoke" model where almost all files route through massive, centralized headers (e.g., `src/headers.h`). Do NOT attempt to introduce modern decoupled architectures, micro-patterns, or standard C++11/14/20 refactoring. The system is structurally locked to its original paradigm.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core transaction processing and consensus mechanisms (`EvalScript` in `src/script.cpp`, `ProcessMessage` and `SelectCoins` in `src/main.cpp`, and threading in `src/net.cpp`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity. Maintain the exact execution flow of the stack machine and networking handlers.
* **Orchestrator Fragility:** Central coordinators such as `src/headers.h` (50 outbound dependencies) and `src/uibase.h` (28 outbound dependencies) are highly fragile orchestrators. They act as "God Headers". Any changes to `#include` directives, macros, or global data contracts within these files will cause immediate, cascading compilation failures across the entire project.
* **Avoid Dead Code Pruning:** Files like `src/ui.cpp` (133 orphaned functions) and `src/uibase.h` (65 orphaned functions) contain logic that static analysis tools misinterpret as dead code, often due to event-driven UI binding or conditional compilation. DO NOT autonomously attempt to prune, format, or clean up these files.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, custom serialization, or public APIs of these files:
* `src/headers.h` (Severe Blind Bottleneck - 15438 Severity Score, imports everything, 100% Documentation Risk)
* `src/main.cpp` (Core Consensus & Mining - Extreme Mass: 4972.1, handles `ProcessMessage` and `BitcoinMiner`)
* `src/script.cpp` (Core Execution - `EvalScript` has a DB Complexity of 161, 91.4% Cognitive Load)
* `src/bignum.h` & `src/uint256.h` (House of Cards - Custom cryptographic math, deeply embedded with high error risk)
* `src/db.h` / `src/db.cpp` (House of Cards - Database cursors and Berkeley DB wrappers)
* `src/serialize.h` (Extreme structural footprint handling peer-to-peer and disk serialization)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files such as `src/main.cpp`, `src/sha.cpp`, and `src/net.cpp` rely heavily on raw memory manipulation, pointer arithmetic, and C-style casting. Any modifications to buffer parsing, serialization (`src/serialize.h`), or networking buffers MUST be rigorously bounded to prevent buffer overflows or remote code execution (RCE).
2. **Exploit Generation Surface:** `src/script.cpp` (the Forth-like stack machine), `src/bignum.h`, and `src/serialize.h` possess a 20% Exploit Generation Surface. Because this code parses untrusted peer-to-peer network data, you must ensure strict bounds checking and validation logic (e.g., inside `CheckTransaction` or `EvalScript`) remains fully intact.
3. **Concurrency:** `src/net.cpp` implements raw thread handling (e.g., `ThreadSocketHandler2`). Ensure thread-safety blocks (`CRITICAL_BLOCK`) are never bypassed or re-ordered.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on modern C++ knowledge to determine blast radius in this heavily coupled historical codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
