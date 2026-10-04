---
description: "You are operating within `cyber`, a fast, concurrent, and embeddable programming language. The repository is heavily dominated by Zig (52.8%) for the..."
---
# AGENTS.md: cyber Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cyber`, a fast, concurrent, and embeddable programming language. The repository is heavily dominated by Zig (52.8%) for the core compiler, standard library, and JIT components, supplemented by C (9.2%) for the VM and FFI boundaries.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 9.661. The network topology demonstrates a Hub-and-Spoke model with high Modularity (0.676) but highly negative Assortativity (-0.4442). This indicates that while domains (like parsing, JIT, or stdlib) are well-segmented, they all depend heavily on a few extremely dense, highly centralized "God Nodes" (the compiler pipeline and VM core) and single-point-of-failure headers like `src/include/cyber.h` and `src/vm.h`. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The core compilation pipeline functions (`semaExprNoCheck` in `src/sema.zig`, `evalExprNoCheck` in `src/cte.zig`, and `tokenizeOne` in `src/tokenizer.zig`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursion, dynamic memory allocations on the hot path, or O(N^2+) logic within the parser, semantic analyzer, or compile-time evaluation (CTE) engine.
* **Orchestrator Fragility:** Central orchestrators like `src/aot.h` (9 outbound dependencies) and the core VM engine (`src/vm.c`) are highly fragile. Any changes to bytecode definitions, stack frame handling, or memory layout within these files require immediate, comprehensive verification across all JIT and AOT targets.
* **Avoid Dead Code Pruning:** The AST and semantic analysis files (`src/lib.zig` with 92 orphaned functions, `src/value.zig` with 70) contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The compiler utilizes dynamic dispatch, comptime evaluation, and target-specific conditional compilation that bypasses static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream JIT/VM testing before modifying the structural signatures, bytecode generation, or public APIs of these files:
* `src/sema.zig` (Massive Structural Mass: 20,734.36, Key Person Silo - 90.0% isolated ownership by fubark. The central semantic analyzer).
* `src/vm.c` (Extreme Volatility Hotspot: 89.6% Churn, 87.7% Cognitive Load. The core C execution engine).
* `src/jit/gen.zig` (Highest Volatility: 100% Churn, highly complex JIT generation logic).
* `src/parser.zig` & `src/cte.zig` (Key Person Silos - 100% isolated ownership by fubark).
* `src/stdx/time.zig` (Severe Blind Bottleneck - 32.7 Severity, flying blind with 100% Documentation Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the core VM (`src/vm.c`, `src/builtins/core.zig`, `src/thread.zig`) inherently rely on raw memory manipulation and pointer casting. Any modifications to the heap allocator, stack management, or Garbage Collector (GC) must be rigorously bounded to prevent Use-After-Free (UAF), buffer overflows, or segmentation faults.
2. **Exploit Generation Surface:** The web playground environment (`examples/web-playground/cyber-mode.js`) possesses a 25.2% Exposure for Exploit Generation. Ensure any modifications to the in-browser execution or DOM manipulation strictly sanitize inputs to prevent Cross-Site Scripting (XSS).
3. **Supply Chain:** There is 1 binary anomaly identified by X-Ray. Do not modify or attempt to execute unrecognized binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Zig `comptime` behaviors, hallucinate bytecode instruction formats, or rely on generalized compiler knowledge to determine blast radius within this 63k+ LOC language implementation. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
