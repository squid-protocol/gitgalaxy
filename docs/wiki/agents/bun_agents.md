---
description: "You are operating within `bun`, an ultra-fast JavaScript runtime, bundler, transpiler, and package manager. The repository is a massive hybrid of Zig..."
---
# AGENTS.md: bun Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bun`, an ultra-fast JavaScript runtime, bundler, transpiler, and package manager. The repository is a massive hybrid of Zig (28.1%) for the core runtime and AST manipulation, and C++ (31.1%) heavily utilized for JavaScriptCore (JSC) bindings and WebCore implementations.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.97. The network topology demonstrates a Hub-and-Spoke model with extreme negative assortativity (-0.1374). A few central C++ headers (`root.h`, `config.h`, `ZigGlobalObject.h`) and massive Zig orchestrators dictate the entire execution flow. Do NOT attempt to apply generic object-oriented or microservice abstractions. The architecture is explicitly optimized for raw execution speed and tight memory locality.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** High-traffic runtime functions (`parse` in `properties_generated.zig`, `parse` in `Arguments.zig`, and AST loaders) operate with extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops, dynamic memory allocations on the hot path, or O(N^2+) complexity in any AST traversal, module loading, or C++ binding serialization.
* **Orchestrator Fragility:** The C++ bindings orchestrators (`ZigGlobalObject.cpp` with 210 outbound dependencies, `bindings.cpp` with 132) are the most fragile nodes in the system. Any changes to Zig <-> C++ FFI contracts, `JSValue` memory layouts, or WebCore DOM logic require immediate, comprehensive verification across the entire runtime boundary.
* **Avoid Dead Code Pruning:** The bindings and crypto implementations (`bindings.cpp` with 231 orphaned functions, `boringssl.translated.zig` with 219) contain massive volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files. The engine relies heavily on reflection, dynamic execution, and WebAssembly compilation that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream benchmark verification before modifying the structural signatures, `JSValue` logic, or C++ headers of these files:
* `src/bun.js/bindings/bindings.cpp` (Extreme Volatility Hotspot: 100% Churn, 231 orphaned functions)
* `src/bun.js/bindings/ZigGlobalObject.cpp` (Extreme Volatility Hotspot: 97.5% Churn, Massive Orchestrator)
* `src/bun.js/node/node_fs.zig` (Massive Structural Mass: 15115.26, handles all synchronous/asynchronous file I/O)
* `src/css/properties/properties_generated.zig` (Key Person Silo - 100% isolated ownership by pfg)
* `src/bun.js/bindings/root.h` (Severe Blind Bottleneck - 363 inbound connections, flying blind with 33% Doc Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** C++ files interfacing with V8/JSC APIs (`ProcessBindingConstants.cpp`, `JSCipherPrototype.cpp`, `App.zig`) rely heavily on raw pointer arithmetic and unsafe memory casting. Any `memcpy`, buffer allocation, or FFI logic here must be rigorously scrutinized for buffer overflows, Use-After-Free (UAF), or segmentation faults.
2. **Exploit Generation Surface:** Files related to JavaScript execution and transpilation (`src/api/schema.js`, `hmr-module.ts`) possess 100% Exposure for Exploit Generation. Because Bun executes untrusted third-party code by design, you must ensure strict sandboxing, boundary checking, and prototype pollution protections remain fully intact.
3. **Supply Chain:** There are 9,758 unknown dependencies bypassing the Zero-Trust whitelist and 46 binary anomalies. Do not add or bump external packages without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess FFI boundaries, hallucinate C++ header imports, or rely on generalized Zig knowledge to determine blast radius within this 900k+ LOC engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
