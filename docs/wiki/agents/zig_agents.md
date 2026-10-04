---
description: "You are operating within the `zig` repository, the core compiler and standard library for the Zig programming language. The codebase is overwhelmingly..."
---
# AGENTS.md: zig Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `zig` repository, the core compiler and standard library for the Zig programming language. The codebase is overwhelmingly dominated by Zig (98.3%), designed for optimal performance, manual memory management, and robust cross-compilation.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.138. The network topology demonstrates completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly centralized, "hub-and-spoke" architecture where the entire compiler pipeline revolves around a massive, monolithic core (e.g., `Sema.zig`, `Zir.zig`, `Ast.zig`).
* **Core Rule:** Maintain strict adherence to Zig's explicit memory allocation paradigms and data-oriented design. Do NOT attempt to introduce hidden control flow, implicit memory allocations, or decouple the foundational semantic analysis orchestrators.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core semantic analysis and code generation paths (`eval`, `resolve`, `irToNode`, and `resolveTypedValue` within `src/Sema.zig`) operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis) due to deep AST traversal and comptime type resolution. You MUST NOT introduce unbounded recursive loops, heavy synchronous allocations, or complex comptime evaluation traps inside these hot paths.
* **Orchestrator Fragility:** Central orchestrators such as `src/Air.zig` (72 outbound dependencies), `src/Sema.zig` (57 outbound), and `src/Zir.zig` (56 outbound) are extremely fragile. Modifying the intermediate representation (IR) or semantic analysis phases requires immediate, comprehensive verification across the entire test matrix (`test/cli.zig`, `test/behavior.zig`).
* **Avoid Dead Code Pruning:** Files like `src/arch/riscv64/emit.zig` (80 orphaned functions) and various test stubs contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The compiler utilizes exhaustive switch cases, comptime logic, and architecture-specific generation that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream compiler bootstrapping (stage3) before modifying the structural signatures, comptime resolution, or public APIs of these files:
* `src/Sema.zig` (Massive Structural Mass: 104622.68, 100% Churn. Key Person Silo - 100% isolated ownership by Andrew Kelley. The absolute core of the semantic analyzer).
* `src/Ast.zig` (Highest Cumulative Risk: 729.08. Core syntax tree definition).
* `src/Zir.zig` & `src/Air.zig` (Critical Intermediate Representation orchestrators. Modifying these breaks all downstream code generation).
* `src/Compilation.zig` (Orchestrates the entire build and module linkage process).
* `src/link/Elf.zig` (High logic bomb risk. Complex binary format linking).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & COMPTIME CAVEATS).** The GitGalaxy security scanning system you architected has audited the structural DNA and flagged 0 malicious artifacts.

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within WebAssembly emission (`src/Wasm.zig`) and cryptographic libraries (`lib/std/crypto/poly1305.zig`) natively rely on raw pointer arithmetic and slice manipulation (10% Exposure). Any modifications to memory bounds, alignment, or buffer slicing must be mathematically proven to prevent Out-Of-Bounds reads/writes.
2. **Exploit Generation Surface:** Test and build scripts (`test/standalone/pie/build.zig`, `test/cli.zig`) possess high exposure for Exploit Generation. Because the compiler executes arbitrary paths and build scripts, ensure any modifications to CLI parsing or subprocess spawning (`std.process.Child`) strictly sanitize arguments to prevent command injection.
3. **Supply Chain:** There are 13 binary anomalies identified by X-Ray. Do not alter prebuilt native test binaries or fixtures without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Semantic Analysis state transitions, hallucinate ZIR/AIR opcodes, or rely on generalized compiler knowledge to determine blast radius within this 200k+ LOC system. 

Leverage the deterministic GitGalaxy SQLite database to map the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
