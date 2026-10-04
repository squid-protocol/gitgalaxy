---
description: "You are operating within the `livecode` repository, a cross-platform rapid application development environment. The codebase is heavily bifurcated..."
---
# AGENTS.md: livecode Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `livecode` repository, a cross-platform rapid application development environment. The codebase is heavily bifurcated between a low-level engine written in C++ (51.3%), Objective-C (5.2%), and C (1.8%), and a high-level tooling/IDE layer written in LiveCode script itself (18.3%). 

* **Architectural Paradigm:** The system maps to a "Cluster 3" macro-species with an Architectural Drift Z-Score of 4.365. The network topology demonstrates a moderate Modularity (0.2678) but a negative Assortativity (-0.0602). This indicates a fragile "hub-and-spoke" architecture where isolated modules and platform-specific implementations (e.g., iOS, Android, Windows) are tightly coupled to a central core of C++ engine headers and monolithic LiveCode orchestrator scripts.
* **Information Flow:** Execution flows from high-level LiveCode scripts (`ide-support`, `builder`) down through the execution engine (`engine/src/exec*.cpp`), which binds to platform-specific C++/Objective-C implementations for rendering, OS integration, and I/O.
* **Core Rule:** Strictly observe the boundary between the C++ execution engine and the LiveCode standard library. Do NOT attempt to leak engine internals directly into the LiveCode layer without passing through the established `exec-interface` abstractions.

## 2. Notable Structures & Architecture
* **Foundational Load-Bearers:** The C++ engine relies heavily on a cluster of highly coupled core headers: `prefix.h` (435 inbound connections), `parsedef.h` (422), `globdefs.h` (416), and `objdefs.h` (402). These define the memory layout, types, and macros for the entire engine. Any modification to these headers carries a massive compilation and ABI blast radius.
* **Fragile Orchestrators:** C++ orchestrators like `globals.cpp` (58 outbound dependencies), `opensslsocket.cpp`, and `object.cpp` drive the external module integrations. Concurrently, massive LiveCode scripts such as `ide-support/revliburl.livecodescript` and `revsaveasstandalone.livecodescript` orchestrate the IDE and deployment pipelines.
* **Algorithmic Complexity:** Core UI event loops (`MCWindowProc` in `w32dcw32.cpp`) and rendering functions (`MCButton::draw`) operate with high data gravity and recursive traits. Code paths in the deployment builder (`FixFilenames`) exhibit O(2^N) static analysis signatures.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH RAW MEMORY & EXPLOIT CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Platform integration boundaries (`mac-internal.h`, `imagebitmap.cpp`, `lnxdclnx.cpp`) possess 10% exposure to raw memory manipulation. Ensure strict boundary checks when casting pointers across the OS-to-engine rendering layer to prevent Buffer Overflows or Use-After-Free (UAF) vulnerabilities.
2. **Exploit Generation Surface:** Configuration and builder scripts (`config.py`, `builder_utilities.livecodescript`, `stackbehavior.livecodescript`) possess 100% Exposure for Exploit Generation. As these scripts compile user applications and interface with the host filesystem, any input handling must rigorously sanitize paths to prevent Command Injection or Path Traversal.
3. **Supply Chain / Binary Data:** The repository contains 16 binary anomalies (X-Ray). Given the 11k+ unscanned artifacts (likely assets, prebuilt binaries, or test fixtures), do not alter binary blobs without explicit architectural review.

## 4. Outliers & Extremes
* **Extreme Structural Mass:** `ide-support/revliburl.livecodescript` possesses an astronomical Structural Mass (388,670) and heavily dominates the IDE layer. It acts as a massive procedural hub rather than a modular component.
* **Blind Bottlenecks (God Nodes):** Foundational engine headers like `libfoundation/include/foundation-auto.h`, `foundation-span.h`, and `engine/src/object.h` exhibit massive blast radii combined with 100% Documentation Risk. Modifying these is effectively flying blind and risks breaking core engine assumptions.
* **Contagious Mutations & House of Cards:** `engine/src/exec.h` and `engine/src/object.h` exhibit high State Flux (~30%) combined with high betweenness. They act as structural bridges; a runtime error or bad state mutation here will cascade instantly across the interpreter.
* **Design Slop:** The `exec-interface-*.cpp` files contain hundreds of orphaned functions (e.g., `exec-interface-object.cpp` with 233 orphans). These likely represent generated or macro-bound C++-to-LiveCode API bridges, rather than true dead code.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **Decouple and Document Engine Headers:** Address the 100% documentation risk in `foundation-auto.h`, `foundation-span.h`, and `object.h`. Add explicit architectural documentation outlining the memory ownership models and macro contracts to stabilize the core C++ interface layer.
2. **Decompose LiveCode Monoliths:** The massive LiveCode scripts (`revliburl.livecodescript`, `revsaveasstandalone.livecodescript`, `package_compiler.livecodescript`) are immense single points of failure. Refactor these into smaller, single-responsibility domain libraries to reduce their structural mass and limit testing exposure.
3. **Audit Execution Interface Bindings:** The `exec-interface-*.cpp` files have severe "Design Slop" metrics due to orphaned functions. Audit the build system's macro expansion or code generation to ensure these API bridges are actually necessary, removing truly dead bindings to lower compilation overhead.


---

**[⬅️ Back to Master Index](../index.md)**
