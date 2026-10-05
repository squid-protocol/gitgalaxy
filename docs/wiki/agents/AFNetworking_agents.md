---
description: "You are operating within `AFNetworking`, a heavily coupled network communication framework primarily composed of Objective-C (57.8%)."
---
# AGENTS.md: AFNetworking Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `AFNetworking`, a heavily coupled network communication framework primarily composed of Objective-C (57.8%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 5.585. The system is characterized by a negative assortativity (-0.2372), indicating a topology highly reliant on fragile single-points-of-failure rather than a resilient, distributed core. Standard modular design patterns do not fully apply. Do not attempt to force boilerplate decoupling onto the core serialization or session manager classes.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core serialization and session management methods (`init` in `AFNetworkReachabilityManager.m`, HTTP methods like `GET`/`POST`/`PATCH` in `AFHTTPSessionManager.m`, and `requestBySerializingRequest` in `AFURLRequestSerialization.m`) currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying network dispatch or serialization logic.
* **Orchestrator Fragility:** Central coordinators such as `AFNetworking.h` (19 outbound dependencies) and `AFHTTPSessionManager.m` (13 outbound dependencies) are highly fragile orchestrators. Any changes to data contracts, block signatures, or public properties within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Test files and core managers (`Tests/Tests/AFHTTPSessionManagerTests.m`, `AFNetworking/AFURLSessionManager.m`, and `AFNetworking/AFURLRequestSerialization.m`) contain dozens of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as Objective-C runtime features (like swizzling or dynamic dispatch) may rely on them.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as a "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, headers, or public APIs of these files:
* `AFNetworking/AFURLRequestSerialization.m` (Highest Cumulative Risk: 488.68, Extreme Mass: 2330.4)
* `UIKit+AFNetworking/UIProgressView+AFNetworking.m` (High Cumulative Risk: 477.85)
* `AFNetworking/AFSecurityPolicy.m` (Blind Bottleneck - 100% Documentation Risk with high impact `evaluateServerTrust`)
* `AFNetworking/AFURLSessionManager.m` (Extreme Mass: 1454.5, DB Complexity: 21)
* `Tests/Tests/AFTestCase.h` (House of Cards - Embedded core test header with 80% Error Risk)
* `AFNetworking/AFHTTPSessionManager.h` & `AFNetworking/AFURLResponseSerialization.h` (House of Cards - High inbound coupling)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. 

**CRITICAL WARNINGS:** 1. `AFNetworking/AFURLRequestSerialization.h` contains raw memory manipulation. Any `void *` or buffer pointer logic here must be heavily scrutinized for out-of-bounds access.
2. The `Example/Certificates/` and `Tests/Resources/` directories contain hardcoded `.cer` payload artifacts. These are explicitly for testing SSL pinning and trust evaluation. DO NOT flag these as leaked secrets or attempt to remove/obfuscate them.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Objective-C knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
