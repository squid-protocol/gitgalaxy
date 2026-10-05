---
description: "You are operating within `ChrysaLisp`, an experimental, parallel 64-bit OS/GUI/IDE written as a Lisp dialect embedded within C++ (88.1%). The..."
---
# AGENTS.md: ChrysaLisp Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `ChrysaLisp`, an experimental, parallel 64-bit OS/GUI/IDE written as a Lisp dialect embedded within C++ (88.1%). The architecture relies heavily on shell/PowerShell scripts for boot orchestration and massive `.inc` files containing raw Lisp code mapped directly into C.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 7.559. The network topology demonstrates infinite positive assortativity but average modularity (0.5562). This indicates an extremely centralized "kernel-and-modules" architecture where the host environment (`src/host/`) orchestrates everything, and individual Lisp classes/apps are completely isolated from each other, communicating only via the core engine. Do NOT attempt to introduce deep dependencies between Lisp modules or rewrite the C++ host into modern idioms; it is explicitly designed as a bare-metal abstraction layer.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Host GUI rendering (`get_event_timeout`, `blit_colorblend` in `src/host/gui_fb.c`) and script execution (`boot_cpu_gui` in `funcs.ps1`) operate at O(N^6) and O(N^4) static complexities. You MUST NOT introduce additional nested rendering loops, blocking I/O, or dynamic memory allocations inside the `src/host/` polling loops.
* **Orchestrator Fragility:** Central orchestrators like `gui_fb.c` (17 outbound dependencies) and platform shims (`pii_windows.cpp`, `pii_darwin.cpp`) are highly fragile. Any changes to window management, framebuffer creation, or OS-level threading APIs require immediate, cross-platform verification (Linux, macOS, Windows).
* **Avoid Dead Code Pruning:** Shell scripts and PowerShell bootloaders (`funcs.ps1`, `run.sh`) contain numerous functions flagged as "orphaned." DO NOT autonomously attempt to prune these. They are invoked dynamically by the user or build system based on environment flags (e.g., GUI vs. TUI boot modes).

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Chris Hinsley). 

**MANDATORY RULE:** You require explicit human permission and extensive cross-platform compilation before modifying the structural signatures, raw memory mapping, or platform APIs of these files:
* `src/host/gui_fb.c` (Massive Structural Mass: 1160.16, Core Framebuffer implementation, Key Person Silo)
* `src/host/gui_raw.cpp` (Core GUI drawing routines, Key Person Silo)
* `funcs.sh` and `funcs.ps1` (Extreme Risk: Severe Blind Bottlenecks with 100% Documentation Risk and High House of Cards severity)
* `src/host/pii_windows.cpp` & `pii_linux.cpp` & `pii_darwin.cpp` (Platform abstraction layers)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files such as `service/gui/actions.inc` and `usr/Guest/env.inc` possess a 10% Exposure score for Raw Memory Manipulation. Because this system implements an OS/Lisp runtime, it inherently handles raw memory pointers, garbage collection, and direct framebuffer writes. Any modifications here must be mathematically verified to prevent segmentation faults or memory corruption.
2. **Execution Context:** The `.inc` files are essentially raw ChrysaLisp code loaded directly into the C++ runtime. Be extremely careful when formatting or modifying these files, as they dictate the base environment of the OS.
3. **Supply Chain:** There are 2 binary anomalies identified by X-Ray. Do not modify or attempt to execute unrecognized binary blobs.

## 5. Environmental Tooling (The Oracle)
Do not guess platform-specific API calls (`#ifdef _WIN32`), hallucinate Lisp standard library functions, or rely on generalized C++ knowledge to determine blast radius within this highly unconventional codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
