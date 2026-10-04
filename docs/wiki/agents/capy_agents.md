---
description: "You are operating within `capy`, a cross-platform GUI framework primarily composed of Zig (87.4%), alongside native backend bindings in C, Java, and..."
---
# AGENTS.md: capy Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `capy`, a cross-platform GUI framework primarily composed of Zig (87.4%), alongside native backend bindings in C, Java, and JavaScript (WASM).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits an *extreme* Architectural Drift Z-Score of 10.14. The network topology demonstrates moderate Modularity (0.50) but perfectly neutral Assortativity (0.0). This indicates a highly segregated structure where individual backends (GTK, Win32, Android, macOS, WASM) are isolated from one another but rely heavily on a few central data/container orchestrators. 
* **Core Rule:** Do NOT attempt to introduce cross-backend coupling. Backend implementations must remain strictly isolated within their respective `src/backends/` directories.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core layout calculations and data reactivity (`asc` in `src/containers.zig`, `deinit` and `animate` in `src/data.zig`, and `callback` in `src/backends/android/backend.zig`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops, blocking operations, or O(N^2+) complexity inside the UI thread, event handlers, or layout tree traversals.
* **Orchestrator Fragility:** Native integration files such as `android/src/CanvasView.java`, `android/src/NativeInvocationHandler.java`, and `src/backends/wasm/capy-worker.js` act as fragile orchestrators bridging Zig to host environments. Modifying FFI (Foreign Function Interface) signatures here requires immediate, comprehensive verification of memory alignment and lifecycle management across language boundaries.
* **Avoid Dead Code Pruning:** Backend bindings like `src/backends/gtk/gtk.zig` (203 orphaned functions), `src/backends/win32/backend.zig` (40 orphans), and `src/backends/wasm/capy.js` (34 orphans) contain massive amounts of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files. They rely heavily on external C-ABI dynamic linking and event-driven callbacks that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: zenith391). 

**MANDATORY RULE:** You require explicit human permission and downstream target verification before modifying the structural signatures, raw memory allocations, or public APIs of these files:
* `src/backends/gtk/gtk.zig` (Absolute Leviathan - Massive Structural Mass: 44,236.68, handles complete GTK abstraction)
* `src/data.zig` & `src/containers.zig` (Key Person Silos - 100% isolated ownership by zenith391, core UI reactivity)
* `src/backends/win32/backend.zig` & `src/internal.zig` (Key Person Silos - 100% isolated ownership by zenith391)
* `src/backends/wasm/capy.js` (Severe Blind Bottleneck - High Blast Radius flying blind with 100% Documentation Risk)
* `include/capy.h` (Severe Blind Bottleneck - 95.2% Documentation Risk, critical C API header)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH FFI/MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Cross-language bindings like `src/backends/gtk/gtk.zig`, `android/src/android-bind.zig`, and `src/widget.zig` rely heavily on raw memory manipulation, pointers, and `c_allocator` usage (10% Exposure). Any memory allocation, `extern` struct definition, or pointer arithmetic MUST be rigorously scrutinized to prevent undefined behavior (UB), memory leaks, or segmentation faults during UI rendering.
2. **Exploit Generation Surface:** Files handling external assets and network/host data (`src/assets.zig`, `src/http.zig`, `android/Sdk.zig`) possess ~20% Exposure scores for Exploit Generation. Because this framework loads external resources (fonts, images, data), you must ensure strict boundary checking and resource validation to prevent arbitrary file reads or buffer overflows via malformed assets.

## 5. Environmental Tooling (The Oracle)
Do not guess FFI boundaries, hallucinate Zig-to-C struct layouts, or rely on generalized UI knowledge to determine blast radius within this highly segregated codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
