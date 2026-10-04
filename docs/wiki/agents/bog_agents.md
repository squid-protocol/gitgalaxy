---
description: "You are operating within `bog`, a small, embeddable language interpreted virtual machine and compiler written overwhelmingly in Zig (90.6%) and C (6.2%)."
---
# AGENTS.md: bog Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bog`, a small, embeddable language interpreted virtual machine and compiler written overwhelmingly in Zig (90.6%) and C (6.2%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species but exhibits an *extreme* Architectural Drift Z-Score of 11.139. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, pointing to a highly cohesive, tightly coupled monolithic core. Do NOT attempt to apply decoupled micro-patterns, object-oriented paradigms, or async/await architectures here. The system is designed as a rigid, high-performance execution pipeline (Tokenize -> Parse -> Compile -> VM Execute).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core execution and AST traversal methods (`run` in `src/Vm.zig`, `genNode` in `src/Compiler.zig`, and `next` in `src/tokenizer.zig`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops, dynamic memory allocations, or O(N^2+) complexity inside the core interpreter loop or compiler passes.
* **Orchestrator Fragility:** API wrappers and test boundaries like `examples/bog_from_c.c` are highly fragile orchestrators. Any changes to the Zig-to-C FFI (Foreign Function Interface) or the core `bog.h` header require immediate, comprehensive verification of downstream C integrations.
* **Avoid Dead Code Pruning:** Files such as `src/lib.zig`, `src/multi_array_list.zig`, and `src/Map.zig` contain dozens of orphaned (dead) functions. DO NOT autonomously attempt to prune or refactor these blocks. These are often foundational data structures or public-facing API exports that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as "Blind Bottlenecks" (deeply embedded with 100% documentation risk). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, manual memory management logic, or public APIs of these files:
* `src/Vm.zig` (The Core Monolith - Massive Structural Mass: 7324.08, DB Complexity: 91)
* `src/Compiler.zig` (Extreme Mass: 5748.88)
* `src/value.zig` (Extreme Mass: 4873.26, handles Bog-to-Zig type conversions)
* `src/List.zig` & `src/std/io.zig` (Highest Cumulative Risks in the repository)
* `src/bog.zig` & `src/lib.zig` (Severe Blind Bottlenecks - Massive Blast Radius flying blind with 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Supply Chain anomalies. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** `src/parser.zig`, `src/tokenizer.zig`, and `tests/behavior.zig` possess a 20% Exposure score for Exploit Generation. Because this codebase parses, compiles, and executes arbitrary code, you MUST ensure strict input validation and boundary checking to prevent malicious Bog scripts from achieving VM escapes or buffer overflows.
2. **Raw Memory Manipulation:** Files like `src/Map.zig` and `src/multi_array_list.zig` rely heavily on raw memory manipulation and pointer math (e.g., `shrinkAndFree`, `ensureTotalCapacity`). Any modifications to memory buffers, alignments, or Zig allocators must be rigorously scrutinized for out-of-bounds access, Use-After-Free (UAF), or memory leaks.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Zig knowledge to determine blast radius within this specialized compiler/VM. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
