---
description: "You are operating within `ghostty`, a high-performance terminal emulator. The codebase is a cross-platform, multi-language system dominated by Zig..."
---
# AGENTS.md: ghostty Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `ghostty`, a high-performance terminal emulator. The codebase is a cross-platform, multi-language system dominated by Zig (60.1%) for the core terminal/rendering logic, Swift (17.2%) and Objective-C for the macOS native frontend, and C/C++ (6.5%) for foundational dependencies like `stb_image`.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species. The network topology demonstrates high Modularity (0.7929) but significantly negative Assortativity (-0.5048). This indicates a cleanly separated micro-boundary structure (e.g., decoupled rendering, font shaping, and terminal backends) that nonetheless relies heavily on fragile, central single-points-of-failure (`PageList.zig`, `Terminal.zig`).
* **AI & Machine Learning Topology:** The repository contains a "Cloud API Wrapper" integration. While local compute mass for AI is low, the integration acts as a 'Pure Consumer' with a massive blast radius. Prompt injections or unexpected API payloads here will cascade across the system.
* **Core Rule:** Maintain strict adherence to the language boundaries and memory management paradigms. Do NOT attempt to leak macOS-specific Swift/Objective-C logic into the cross-platform Zig core (`src/terminal/`), and respect the explicit memory allocation boundaries defined in Zig.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core terminal execution paths (`DecodeUTF8` in `src/simd/vt.cpp`, `screenPoint` in `src/terminal/PageList.zig`, and `csiDispatch` in `src/terminal/stream.zig`) operate at extreme recursive or highly dense algorithmic complexities (O(2^N) or deep O(N^6) branching in static analysis) to process high-throughput text and control sequences. You MUST NOT introduce unbounded loops, dynamic memory allocations on the hot rendering path, or unoptimized string copies within `src/terminal/` or `src/simd/`.
* **Orchestrator Fragility:** Central orchestrators such as `include/ghostty/vt.h` (20 outbound dependencies) and the GTK/macOS application delegates (`AppDelegate.swift`) are highly fragile. Altering the terminal virtual machine (VT) specifications or application lifecycle hooks requires extreme caution and cross-platform verification.
* **Avoid Dead Code Pruning:** The repository contains files like `src/apprt/embedded.zig` (77 orphaned functions) and various Swift tests with logic flagged as "dead code." DO NOT autonomously attempt to prune or refactor these files. The codebase relies heavily on conditional compilation (e.g., `comptime` in Zig) and Objective-C/Swift dynamic message dispatch that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream performance profiling before modifying the structural signatures, memory grids, or public APIs of these files:
* `src/terminal/PageList.zig` & `src/terminal/Terminal.zig` (Massive Structural Mass and Key Person Silos - 100% isolated ownership by Mitchell Hashimoto. These files manage the absolute reality of the terminal grid state).
* `macos/Sources/App/macOS/AppDelegate.swift` (Highest Cumulative Risk: 606.95, controls the macOS native window and lifecycle management).
* `src/terminal/stream.zig` (Key Person Silo and highly complex control sequence dispatcher).
* `src/font/shaper/coretext.zig` & `src/font/shaper/harfbuzz.zig` (Core font shaping engines. High cognitive load and complex FFI bridging).
* `src/shell-integration/bash/ghostty.bash` (Extreme Volatility Hotspot: 58.9% Churn. High risk of breaking user environments).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the `src/stb/` C headers and `src/apprt/gtk/class/` Zig wrappers inherently rely on raw memory manipulation and pointer arithmetic (up to 10% Exposure). Any modifications to image resizing, buffer casting, or FFI pointers must be mathematically proven to prevent Use-After-Free (UAF), buffer overflows, or segmentation faults.
2. **Exploit Generation Surface:** Code handling shell integrations (`snap/local/launcher`, `src/shell-integration/bash/ghostty.bash`) and WASM web wrappers (`example/wasm-sgr/index.html`) possess high exposure for Exploit Generation. Because a terminal emulator processes untrusted standard output, ensure any modifications to VT sequence parsing strictly sanitize escape codes to prevent arbitrary command execution or terminal hijacking.
3. **Obfuscation & Evasion Surface:** `macos/Sources/Features/Update/UpdatePopoverView.swift` triggered obfuscation warnings, likely due to complex UI view routing or packed assets. Approach UI modifications carefully to avoid breaking the auto-update mechanisms.

## 5. Environmental Tooling (The Oracle)
Do not guess Zig `comptime` behaviors, hallucinate HarfBuzz/CoreText layout APIs, or rely on generalized systems programming knowledge to determine blast radius within this highly optimized terminal. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
