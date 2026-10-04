---
description: "You are operating within the `Dancer2` repository, a lightweight yet powerful web application framework for Perl (79.2%). It is the successor to..."
---
# AGENTS.md: Dancer2 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `Dancer2` repository, a lightweight yet powerful web application framework for Perl (79.2%). It is the successor to Dancer, rebuilt around Moo (a modern object-oriented system for Perl) to provide a robust routing and middleware layer (Plack/PSGI).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 8.291. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, indicating a highly monolithic and tightly coupled test-driven architecture. The core framework logic is deeply intertwined with its massive test suite (`t/`), meaning any change to the core routing, DSL, or application state objects will cascade across hundreds of integration tests.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Test orchestrators like `t/request_upload.t`, `t/hooks.t`, and `t/dsl/uri_for_route.t` exhibit extreme O(2^N) or O(N^6) recursive time complexities in static analysis. This is due to deep Plack/PSGI mocking, nested route definitions, and repetitive HTTP request simulations. You MUST NOT introduce unbounded recursive loops, dynamic `eval` statements, or heavy I/O operations directly within the core DSL or routing engine (`Dancer2::Core::Route`).
* **Orchestrator Fragility:** Test orchestrators pull in massive amounts of dependencies to simulate the framework environment (e.g., `t/error.t` with 16 outbound dependencies, `t/plugin_syntax.t` with 14). Modifications to how the `Dancer2::Core::App` or `Dancer2::Core::Request` singletons are instantiated will break these test harnesses instantly.
* **Avoid Dead Code Pruning:** The test suite utilizes dynamic hook registration and DSL extensions (`t/roles/hook.t`, `t/dsl/extend.t`) which static analysis flags as "orphaned functions." DO NOT autonomously attempt to prune, format, or clean up these files. They rely heavily on Perl's dynamic symbol table (`glob` assignment) and Moo role composition which bypasses static AST mapping.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and extensive PSGI integration testing before modifying the structural signatures, hook lifecycles, or public APIs of these files:
* `t/request_upload.t` (Highest Cumulative Risk: 639.97, Key Person Silo - 100% isolated ownership by Sawyer X. High churn and 100% Exploit Generation Surface due to raw file upload handling).
* `t/error.t` (Secrets Risk: 97.7%. Contains hardcoded payload artifacts/fixtures needed for error state rendering).
* `t/hooks.t` (Extreme Volatility Hotspot: 99.1% Churn. Defines the critical `before`/`after` hook lifecycle).
* `t/session_bad_client_cookie.t` (High State Flux: 26.6%. Handles sensitive session validation logic).
* `t/issues/gh-1449/TestPlugin.pm` (Severe Blind Bottleneck - High blast radius with 73.3% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT/INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files handling raw HTTP inputs and file uploads (`t/request_upload.t`) possess 100% Exposure for Exploit Generation. You MUST ensure strict validation of content types, multipart boundaries, and temporary file paths to prevent directory traversal or remote code execution via malformed uploads.
2. **Hardcoded Payload Artifacts:** `t/error.t` tripped hardcoded payload signatures. DO NOT flag this as a leaked secret; it contains explicit HTML/stack-trace fixtures used to validate the error rendering engine.
3. **Weaponizable Injection Vectors:** The CLI scaffolding tool (`script/dancer2`) has minor exposure to weaponizable injection. Ensure any template generation or command-line argument parsing strictly escapes input to prevent arbitrary shell execution.

## 5. Environmental Tooling (The Oracle)
Do not guess Moo role compositions, hallucinate Plack middleware wrapping, or rely on generalized Perl knowledge to determine blast radius within this highly dynamic framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
