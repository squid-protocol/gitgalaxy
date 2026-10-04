---
description: "You are operating within the `deno` repository, a secure, high-performance JavaScript and TypeScript runtime built on V8. The codebase is a..."
---
# AGENTS.md: deno Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `deno` repository, a secure, high-performance JavaScript and TypeScript runtime built on V8. The codebase is a heterogeneous mix of JSON (34.9%, primarily tests/config), TypeScript (31.5%), JavaScript (13.1%), and Rust (11.7%) for the core engine and CLI.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.919. The network topology demonstrates a completely flat Modularity (0.0) and negative Assortativity (-0.3363). This indicates a highly coupled, "hub-and-spoke" architecture where isolated frontend JavaScript/TypeScript polyfills and testing environments rely heavily on massive, highly connected Rust orchestrators (`cli/lsp/`, `libs/core/`). 
* **Core Rule:** Maintain strict boundaries between the Rust core execution engine and the TS/JS user-land APIs. Do NOT attempt to decouple foundational orchestrators or introduce unverified dependencies; the architecture requires tight, synchronous execution between V8 isolates, Rust operations (`ops`), and Node.js compatibility polyfills.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core resolution and compilation paths (`new` in `libs/node_resolver/resolution.rs`, `matches_pkg` in `libs/config/workspace/mod.rs`, and `poll_sessions` in `libs/core/inspector.rs`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce additional nested recursion, unbounded iterations, or O(N^2+) logic on the critical path of module resolution, the Language Server Protocol (LSP), or the JIT/V8 bindings.
* **Orchestrator Fragility:** Central orchestrators such as `cli/lsp/language_server.rs` (121 outbound dependencies) and `cli/lsp/tsc.rs` (116 outbound dependencies) are highly fragile. Any changes to AST parsing, diagnostic generation, or Language Server state management require immediate, comprehensive verification against the integration test suite.
* **Avoid Dead Code Pruning:** Files like `cli/tools/lint/ast_buffer/ts_estree.rs` (150 orphaned functions) and extensive test/FFI bindings contain logic flagged as "dead code." DO NOT autonomously attempt to prune or clean up these files. They often represent exhaustive AST definitions or Foreign Function Interface (FFI) exports that are dynamically invoked or reserved for macro expansions.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, V8 memory lifecycles, or public APIs of these files:
* `ext/node/polyfills/_http_outgoing.ts` & `ext/node/polyfills/http.ts` (Highest Cumulative Risk: >690. Node.js compatibility layers are highly volatile and carry massive technical debt and logic bomb risks).
* `cli/lsp/language_server.rs` (Extreme Volatility Hotspot: 73% Churn, 67.8% Cognitive Load. The core developer tooling orchestrator).
* `ext/node_crypto/keys.rs` (Key Person Silo - 85.7% isolated ownership by Bartek Iwańczuk).
* `libs/node_resolver/resolution.rs` (Massive Structural Mass: 3669.3, handles highly complex dependency graph resolution).
* `tests/unit/test_util.ts` (Severe Blind Bottleneck - high blast radius flying blind with a 30% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RUST FFI/V8 CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** Modules handling external file fetching and workspace resolution (`cli/file_fetcher.rs`, `libs/resolver/workspace.rs`) possess 100% Exposure for Injection Vectors. You MUST ensure strict input sanitization, URL parsing, and path canonicalization to prevent Server-Side Request Forgery (SSRF) or arbitrary file reads.
2. **Raw Memory Manipulation:** The Rust core utilizes raw memory manipulation for V8 integration and fast-path execution (`libs/core/arena/mod.rs`, `ext/napi/js_native_api.rs`). Any `unsafe` blocks, pointer arithmetic, or FFI boundary modifications here must be rigorously audited to prevent Use-After-Free (UAF), segmentation faults, or sandbox escapes.
3. **Hardcoded Payload Artifacts:** Multiple `RootCA.pem` files in `tests/specs/cert/` are flagged for hardcoded payloads. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying TLS/SSL behavior.
4. **Supply Chain:** There are 868 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external Cargo or NPM packages without explicit architectural and security review.

## 5. Environmental Tooling (The Oracle)
Do not guess V8 isolate lifecycles, hallucinate Cargo workspace boundaries, or rely on generalized TypeScript/Rust knowledge to determine blast radius within this 500k+ LOC runtime. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
