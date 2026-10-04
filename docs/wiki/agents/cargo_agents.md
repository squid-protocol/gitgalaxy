---
description: "You are operating within `cargo`, the official package manager and build system for Rust. The repository is predominantly written in Rust (63.5%) with..."
---
# AGENTS.md: cargo Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cargo`, the official package manager and build system for Rust. The repository is predominantly written in Rust (63.5%) with a massive footprint of test suites, TOML schemas, and XML configurations.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This signifies an intensely monolithic, highly interconnected core where almost every module routes through foundational structs (like `GlobalContext` or `Workspace`). Do NOT attempt to break this monolith into micro-crates without explicit architectural consensus from the maintainers. The system is designed to compile as a tightly cohesive unit.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core resolution and parsing functions (`normalize_dependencies` in `src/cargo/util/toml/mod.rs`, `deserialize` in `crates/cargo-util-schemas/src/manifest/mod.rs`, and the SAT solver tests) operate at extreme O(2^N) recursive time complexities due to deep dependency tree traversal and TOML validation. You MUST NOT introduce additional nested recursion, unbounded iterations, or O(N^2+) logic on the critical path of dependency resolution or manifest parsing.
* **Orchestrator Fragility:** Central orchestrators like `src/cargo/util/context/mod.rs` (60 outbound dependencies) and `src/cargo/core/compiler/mod.rs` (59 outbound dependencies) are highly fragile. Any changes to data contracts, build flags, or environment variables within these files require immediate, comprehensive verification of downstream compilation and test targets.
* **Avoid Dead Code Pruning:** The test suite (`tests/testsuite/*.rs`) contains hundreds of functions flagged as "orphaned" by static analysis. DO NOT autonomously attempt to prune, format, or clean up these files. Cargo's test harness relies heavily on macro expansion and implicit test discovery (`#[cargo_test]`) that static analysis misinterprets as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, logic paths, or public APIs of these files:
* `src/cargo/core/compiler/build_runner/compilation_files.rs` (Extreme Volatility Hotspot: 77.8% Churn, 92.3% Tech Debt)
* `src/cargo/util/toml/mod.rs` (Massive Structural Mass: 2865.08, Core Manifest Parser)
* `src/cargo/ops/cargo_install.rs` (Massive Structural Mass: 2957.56)
* `src/cargo/core/global_cache_tracker.rs` (Key Person Silo - 100% isolated ownership by Ed Page)
* `src/cargo/util/auth/mod.rs` (Key Person Silo - 100% isolated ownership by Sam Privett)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** The PubGrub resolver tests (`crates/resolver-tests/tests/pubgrub.rs`, `validated.rs`, `resolve.rs`) possess a 100% Exposure score for Injection Vectors. While these are tests, any modifications to the core resolver (`src/cargo/core/resolver/`) MUST ensure strict boundary checking to prevent maliciously crafted `Cargo.toml` files from causing denial-of-service via infinite resolution loops or memory exhaustion.
2. **Raw Memory Manipulation:** Operations inside `src/cargo/util/cpu.rs` and credential helpers (e.g., `cargo-credential-libsecret`) contain raw memory manipulation or FFI boundaries. Any `unsafe` blocks or pointer arithmetic here must be rigorously audited to prevent undefined behavior (UB).
3. **Hardcoded Payload Artifacts:** `tests/testsuite/ssh.rs` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicitly designed, dummy SSH keys required for testing the git fetcher.

## 5. Environmental Tooling (The Oracle)
Do not guess dependency behavior, hallucinate trait implementations, or rely on generalized Rust knowledge to determine blast radius within this 200k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
