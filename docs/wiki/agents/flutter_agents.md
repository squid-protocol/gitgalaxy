---
description: "You are operating within the `flutter` repository, a massive (1.3M+ LOC) UI toolkit and rendering engine. The codebase is heavily bifurcated between..."
---
# AGENTS.md: flutter Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `flutter` repository, a massive (1.3M+ LOC) UI toolkit and rendering engine. The codebase is heavily bifurcated between C++ (33.7%) for the core Impeller rendering engine/platform shells, and Dart (30.7%) for the Flutter framework and CLI tooling, supplemented by Objective-C, Java, and Swift for platform-specific embeddings.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.4. The network topology demonstrates a completely flat Modularity (0.0) and negative Assortativity (-0.2414). This indicates a highly centralized, tightly coupled "hub-and-spoke" architecture where the entire framework relies on a few massive, load-bearing cross-language boundaries (like `memory.dart`, `string.cc`, and `vector.h`). 
* **Core Rule:** Do NOT attempt to decouple the Dart framework layer from the underlying C++ Engine/Impeller APIs. The architecture requires rigid synchronization across the FFI/JNI boundaries.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core rendering and platform lifecycle hooks (`flutterPrepareForPresent` in `surface_mtl.mm`, `application` in iOS `AppDelegate.m`, and layout calculations) operate at extreme recursive time complexities (O(2^N) in static analysis) to handle deep render tree traversals. You MUST NOT introduce unbounded recursive loops, dynamic memory allocations on the UI thread, or O(N^2+) complexity in the critical path of the rendering pipeline (`engine/src/flutter/impeller/`) or the widget framework (`packages/flutter/lib/src/widgets/`).
* **Orchestrator Fragility:** Central orchestrators such as `engine/src/flutter/lib/web_ui/lib/src/engine.dart` (159 outbound dependencies) and platform views (`FlutterView.java`, `TextInputPluginTest.java`) are highly fragile. Any changes to window management, input handling, or WebGL/CanvasKit rendering require immediate, comprehensive verification across all supported platforms (iOS, Android, Web, Windows, Linux, macOS).
* **Avoid Dead Code Pruning:** The C++ engine layers (`engine/src/flutter/impeller/toolkit/interop/impeller.cc` with 171 orphaned functions, `color.h`) contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune or clean up these files. The engine utilizes conditional compilation, platform-specific macros, and dynamic dispatch that completely bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream cross-platform integration testing before modifying the structural signatures, rendering pipelines, or public APIs of these files:
* `packages/flutter/lib/src/widgets/framework.dart` (Contagious Mutation Risk: Deeply embedded bridge with 24.9% State Flux. Controls the entire Widget element tree).
* `packages/flutter_tools/lib/src/runner/flutter_command.dart` (Highest Volatility Hotspot: 70.0% Churn, massive Tech Debt. The core CLI execution wrapper).
* `engine/src/flutter/display_list/testing/dl_rendering_unittests.cc` (Key Person Silo - 100% isolated ownership by bungeman).
* `engine/src/flutter/shell/platform/darwin/ios/framework/Source/FlutterTextInputPlugin.mm` (Key Person Silo - 100% isolated ownership by Koji Wakamiya. Extreme cognitive load handling iOS keyboard events).
* `engine/src/flutter/lib/web_ui/dev/felt` (Highest Cumulative Risk: 628.75. 100% Exploit Generation Surface due to raw shell execution).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & SHELL CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the C++ and Objective-C engine components (`FlutterEmbedderKeyResponderTest.mm`, `image_filter_layer_unittests.cc`, `point.h`) inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications to vertex buffers, Skia/Impeller geometry, or platform channels must be rigorously bounded to prevent Use-After-Free (UAF), buffer overflows, or segmentation faults.
2. **Exploit Generation Surface:** CI/CD and tooling scripts (`packages/flutter_tools/bin/xcode_debug.js`, `dev/bots/analyze_snippet_code.dart`) possess a 100% Exposure score for Exploit Generation. Ensure any modifications to code analysis or build tooling strictly sanitize file paths and untrusted inputs to prevent command injection.
3. **Hardcoded Payload Artifacts:** Files like `debug.keystore` and `dummy-cert.pem` are flagged for hardcoded payloads. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying Android build pipelines and TLS behavior.

## 5. Environmental Tooling (The Oracle)
Do not guess Impeller shader uniform layouts, hallucinate Dart-to-C++ FFI signatures, or rely on generalized mobile development knowledge to determine blast radius within this 1.3M+ LOC multi-platform beast. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
