---
description: "You are operating within the `godot` repository, a massive (2.1M+ LOC) and highly complex cross-platform game engine. The codebase is heavily dominated..."
---
# AGENTS.md: godot Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `godot` repository, a massive (2.1M+ LOC) and highly complex cross-platform game engine. The codebase is heavily dominated by C++ (60.8%) and C (8.2%), with extensive use of custom memory management, low-level rendering APIs (Vulkan, OpenGL, Direct3D), and a custom object system (`ClassDB`).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.051. The network topology demonstrates a completely flat Modularity (0.0) but slight negative Assortativity (-0.0571). This indicates a monolithic "hub-and-spoke" architecture where all modules, servers, and engine components are tightly coupled to a few foundational headers (e.g., `class_db.h`, `os.h`, `variant.h`).
* **Core Rule:** Maintain strict adherence to Godot's internal paradigms (e.g., `Ref<T>`, `Variant`, `StringName`). Do NOT attempt to introduce standard C++ library (STL) patterns where Godot's custom implementations (e.g., `Vector`, `HashMap`, `String`) are expected. The engine manages its own memory and RTTI (Run-Time Type Information) via `ClassDB`.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core rendering tasks, shader parsing (`_parse_expression` in `shader_language.cpp`), and third-party compression libraries (`dr_mp3.h`, `tinyexr.h`) operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis) due to deep AST traversal and massive data gravity. You MUST NOT introduce unbounded recursive loops, dynamic memory allocations on the hot path (especially in `servers/rendering/`), or O(N^2+) complexity in any tight loops.
* **Orchestrator Fragility:** Central orchestrators such as `register_scene_types.cpp` (313 outbound dependencies) and `editor_node.cpp` (156 outbound dependencies) are highly fragile. Modifying class registration, editor initialization sequences, or core engine loops (`main.cpp`) requires extreme caution and exhaustive cross-platform compilation checks.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions," particularly in third-party libraries (`thirdparty/pcre2/`, `thirdparty/embree/`) and generated UI components (`rich_text_label.cpp`, `editor_properties.cpp`). DO NOT autonomously attempt to prune, format, or clean up these files. Godot relies on macro-heavy conditional compilation and dynamic property binding that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent severe blind bottlenecks. 

**MANDATORY RULE:** You require explicit human permission and downstream engine regression testing before modifying the structural signatures, rendering pipelines, or public APIs of these files:
* `platform/windows/display_server_windows.cpp` & `platform/linuxbsd/wayland/wayland_thread.cpp` (Highest Cumulative Risk and Volatility. Core OS windowing and event loops are extremely fragile).
* `scene/gui/rich_text_label.cpp` (Massive Structural Mass: 11572.8. Highly complex text rendering and UI logic).
* `servers/rendering/shader_language.cpp` (Massive Data Gravity. Core custom shading language parser).
* `core/typedefs.h` & `core/object/object.h` (Severe Blind Bottlenecks - Huge blast radius with high Documentation Risk. Modifications here trigger massive engine rebuilds and potential ABI breaks).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & C++ CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the rendering drivers (`rendering_device_driver_vulkan.cpp`, `rendering_device_driver_d3d12.cpp`) and core IO (`input_event_codec.cpp`) inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications to vertex buffers, Vulkan command pools, or variant marshalling must be mathematically proven to prevent Use-After-Free (UAF), buffer overflows, or graphics driver crashes.
2. **Exploit Generation Surface:** Code generation and detection scripts (`make_rst.py`, `detect.py`) possess 100% Exposure for Exploit Generation. Ensure any modifications to SCons build scripts or documentation generators safely handle file paths and environment variables to prevent command injection during the build process.
3. **Hardcoded Payload Artifacts:** Files such as `debug.keystore` and `ca-bundle.crt` are flagged for hardcoded payloads. DO NOT flag these as leaked secrets; they are explicit cryptographic fixtures required for Android deployment and SSL/TLS validation.

## 5. Environmental Tooling (The Oracle)
Do not guess Vulkan memory barriers, hallucinate GDScript VM bytecode operations, or rely on generalized C++ knowledge to determine blast radius within this highly specialized game engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
