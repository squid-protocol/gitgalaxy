---
description: "You are operating within `Alamofire`, an ecosystem primarily composed of Swift (67.4%)."
---
# AGENTS.md: Alamofire Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `Alamofire`, an ecosystem primarily composed of Swift (67.4%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits an extreme Architectural Drift Z-Score of 7.208. The network topology demonstrates a highly negative assortativity (-0.6823), meaning the architecture relies heavily on fragile, highly connected hub nodes (single points of failure) rather than a distributed, resilient core. Do not attempt to introduce decentralized or loosely coupled generic patterns into the core request/response pipeline.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core delegation and request parsing methods (`urlSession` in `Source/Core/SessionDelegate.swift` and `response` in `Source/Core/DataRequest.swift`) currently operate at O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the session delegation pipeline or response serialization.
* **Orchestrator Fragility:** Classes such as `Source/Features/MultipartFormData.swift` and test orchestrators (`Tests/RequestTests.swift`) act as fragile coordinators. Any changes to data contracts, boundary generation, or closure signatures within these files require immediate, comprehensive verification of downstream unit tests.
* **Avoid Dead Code Pruning:** Test files such as `Tests/ParameterEncoderTests.swift` (78 orphaned functions) and `Tests/SessionTests.swift` (36 orphaned functions) contain high volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as test frameworks often rely on dynamic dispatch or reflection to discover these methods.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Jon Shier). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, concurrency models, or public APIs of these files:
* `Tests/SessionTests.swift` (Highest Cumulative Risk: 522.73, Extreme Injection Surface)
* `Source/Core/WebSocketRequest.swift` (Blind Bottleneck - 100% Documentation Risk with high impact `listen` function)
* `Source/Core/AFError.swift` (Key Person Silo - 100% isolated ownership by Jon Shier, Extreme Exploit Generation Surface)
* `Source/Core/SessionDelegate.swift` (Extreme Mass: 1776.72, Blind Bottleneck)
* `Source/Core/Request.swift` (High Volatility and Blind Bottleneck)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** `Source/Core/AFError.swift`, `Source/Features/MultipartFormData.swift`, and `Source/Features/ResponseSerialization.swift` possess a 100% Exposure score. When modifying error handling, multipart boundary generation, or response decoding, you MUST ensure strict input sanitization to prevent memory leaks or logic bypasses.
2. **Hardcoded Payload Artifacts:** The `Tests/Resources/Certificates/` directory contains numerous hardcoded `.cer` payload artifacts. These are explicitly used for testing SSL pinning and trust evaluation. DO NOT flag these as leaked secrets or attempt to remove/obfuscate them.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Swift knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
