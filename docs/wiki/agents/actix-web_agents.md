---
description: "You are operating within `actix-web`, a high-performance web framework ecosystem overwhelmingly composed of Rust (84.4%)."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `actix-web`, a high-performance web framework ecosystem overwhelmingly composed of Rust (84.4%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species but exhibits a high Architectural Drift Z-Score of 6.256. The architecture relies on highly unique, asynchronous HTTP state machines and complex routing macros. Standard or generic Rust web-server boilerplate DO NOT APPLY here. Do not attempt to force simplistic routing patterns onto the core dispatcher.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core HTTP protocol handlers (`actix-http/src/h1/client.rs`, `actix-http/src/encoding/decoder.rs`) and file streaming utilities (`actix-files/src/chunked.rs`) already operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursive loops or O(N^2+) complexity when modifying the encoder/decoder state machines.
* **Orchestrator Fragility:** Connectors and middleware such as `awc/src/client/connector.rs` (26 outbound dependencies) and `actix-web/src/middleware/logger.rs` are highly fragile coordinators. Any changes to trait bounds, generic lifetimes, or data contracts within these files require immediate verification of downstream integration.
* **Avoid Dead Code Pruning:** Files such as `actix-files/src/lib.rs` and `actix-http/src/h1/decoder.rs` contain a high volume of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, unsafe blocks, or public APIs of these files:
* `actix-web/src/request.rs` (Highest Cumulative Risk & Extreme Churn Hotspot - 54.42%)
* `actix-files/src/lib.rs` (Extreme Churn Hotspot - 53.74%)
* `actix-web/src/introspection.rs` (Key Person Silo - Guillermo Céspedes Tabárez)
* `actix-web-codegen/src/route.rs` (Key Person Silo - Luca Cappelletti)
* `actix-multipart/src/form/mod.rs` (Key Person Silo - fasilmveloor)
* `actix-http/src/h1/dispatcher.rs` (The Core Dispatcher - Extreme Mass: 1703.96)
* `actix-files/src/chunked.rs` (Blind Bottleneck - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Supply Chain anomalies. 

**CRITICAL WARNING:** Multiple core modules (`actix-multipart/src/form/mod.rs`, `actix-web/src/guard/mod.rs`, `actix-web/src/middleware/compress.rs`, `actix-web/src/response/builder.rs`) possess a 100% Exposure score for **Weaponizable Injection Vectors**. When modifying these files, you MUST ensure strict input sanitization, enforce payload size limits, and properly escape headers. Additionally, `actix-http/src/responses/response.rs` contains raw memory manipulation; `unsafe` blocks here must be heavily scrutinized for out-of-bounds access.

## 5. Environmental Tooling (The Oracle)
Do not guess trait implementations, hallucinate import paths, or rely on generalized Rust knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
