---
description: "You are operating within `catalyst-runtime`, the core execution engine of the Perl Catalyst MVC web framework. The repository is overwhelmingly..."
---
# AGENTS.md: catalyst-runtime Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `catalyst-runtime`, the core execution engine of the Perl Catalyst MVC web framework. The repository is overwhelmingly dominated by Perl (98.1%) and serves as the foundational dispatch, routing, and request-handling layer.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 7.883. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, indicating a highly coupled, monolithic core. This flat dependency graph is characteristic of Catalyst's dynamic, plugin-heavy nature, where global state and heavily aliased exports dominate. Do not attempt to enforce strict dependency injection or modern IoC (Inversion of Control) patterns; the architecture fundamentally relies on Moose/MRO (Method Resolution Order) and dynamic namespace resolution.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Request dispatch and test simulation files (`t/abort-chain-2.t`, `t/aggregate/unit_core_script_fastcgi.t`) display massive O(2^N) recursive time complexities. This is driven by Catalyst's chained routing mechanics and recursive action traversal. You MUST NOT introduce unbounded recursive calls or O(N^2+) complexity in action dispatchers, plugin loaders, or the dispatcher's `forward`/`go`/`visit` mechanisms.
* **Orchestrator Fragility:** Central orchestrators like `t/arg_constraints.t` (17 outbound dependencies) and `t/utf_incoming.t` (15 outbound dependencies) are highly fragile test harnesses. Modifying how `Catalyst::Request` parses incoming data, especially UTF-8 decoding, will cascade across the entire test suite and break dependent applications relying on legacy behavior.
* **Avoid Dead Code Pruning:** Files like `t/http_exceptions.t` and `t/unicode-exception-bug.t` contain what static analysis flags as "orphaned functions." DO NOT autonomously attempt to prune, format, or clean up these files. Catalyst relies on dynamic method attributes (`:Local`, `:Chained`) and runtime reflection that static AST analyzers misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated testing surface area. 

**MANDATORY RULE:** You require explicit human permission and extensive downstream test verification against CPAN reverse dependencies before modifying the structural signatures, Moose roles, or public APIs of these files:
* `t/utf_incoming.t` (Massive Structural Mass: 1134.84, heavily dictates core request encoding logic)
* `xt/author/http-server.t` (Highest Cumulative Risk: 572.08, 100% Spec Match and Documentation Risk)
* `t/args0_bug.t` (Extreme Volatility Hotspot: 68.9% Churn, highly fragile chained action testing)
* `t/aggregate/unit_controller_config.t` (High state flux and deeply embedded in configuration inheritance)
* `t/aggregate/live_component_controller_action_chained.t` (Complex routing tests simulating massive state flux)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `t/aggregate/unit_core_uri_for.t` and `Makefile.PL` possess ~100% Exposure scores for Exploit Generation. Because Catalyst handles raw HTTP requests and dynamic URI construction, you MUST ensure strict input sanitization, safe URL encoding, and rigid validation of HTTP headers to prevent XSS, HTTP Response Splitting, or arbitrary code execution via forged `uri_for` inputs.
2. **Supply Chain:** There is 1 binary anomaly identified by X-Ray. Do not modify or attempt to execute unrecognized binary blobs or `.tar.gz` fixtures within the `t/` directory unless they are explicitly referenced by a testing harness.

## 5. Environmental Tooling (The Oracle)
Do not guess Moose trait applications, hallucinate namespace resolutions, or rely on generalized Perl knowledge to determine blast radius within this highly dynamic framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file, paying special attention to `Catalyst::Component` and `Catalyst::Action` inheritance.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
