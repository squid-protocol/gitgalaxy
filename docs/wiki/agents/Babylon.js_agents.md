---
description: "You are operating within `Babylon.js`, a massive, high-performance 3D rendering engine primarily composed of TypeScript (81.2%)."
---
# AGENTS.md: Babylon.js Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `Babylon.js`, a massive, high-performance 3D rendering engine primarily composed of TypeScript (81.2%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 7.742. The network topology demonstrates significant negative assortativity (-0.3313), meaning the architecture relies heavily on highly connected hub nodes (fragile single points of failure) rather than a distributed core. Do not attempt to introduce decentralized or loosely coupled patterns into the core rendering loop, scene graph, or materials pipelines. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core WebGL/WebGPU and scene graph traversal methods (`createRenderPipelineAsync` in `webgpuEngine.ts`, `isReady` in `scene.ts`, and GLTF loader pipelines) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the render loop, geometry buffers, or shader compilation.
* **Orchestrator Fragility:** Central coordinators such as `packages/dev/core/src/Meshes/mesh.ts` (283 API surface hits, 83 imports) and `packages/dev/core/src/scene.ts` (83 imports) are highly fragile orchestrators. Any changes to data contracts, lifecycle hooks, or public APIs within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** The core engine (`scene.ts`, `thinNativeEngine.ts`, `webgpuEngine.ts`) contains hundreds of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files. The engine relies on dynamic runtime compilation, shader injection, and WebAssembly bindings that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, WebGL/WebGPU state, or public APIs of these files:
* `packages/dev/inspector/src/components/actionTabs/tabs/propertyGrids/particleSystems/particleSystemPropertyGridComponent.tsx` (Highest Cumulative Risk: 801.82, 100% Logic Bomb)
* `packages/dev/core/src/Engines/webgpuEngine.ts` (Extreme Structural Mass: 767.93, Volatility Hotspot: 78.7% Churn)
* `packages/dev/core/src/Engines/abstractEngine.ts` (Highest Volatility: 100% Churn, Key Person Silo)
* `packages/tools/playground/src/tools/monaco/utils/path.ts` (House of Cards / Blind Bottleneck - 79 inbound connections flying blind)
* `packages/dev/core/src/Meshes/mesh.ts` (Massive AST orchestrator, High Cumulative Risk)
* `packages/dev/core/src/Materials/Node/Blocks/PBR/pbrMetallicRoughnessBlock.ts` (Key Person Silo - 100% isolated ownership by Ryan Tremblay)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `packages/tools/babylonServer/public/gltf_validator.js` and `packages/dev/core/src/Loading/sceneLoader.ts` possess a 100% Exposure score for Exploit Generation Surface. When modifying model loaders or asset parsers, you MUST ensure strict input sanitization and boundary checking to prevent malicious `.gltf`/`.babylon` payloads from causing buffer overflows or arbitrary execution.
2. **Weaponizable Injection Vectors:** The Inspector and Particle systems (`packages/dev/inspector-v2/src/extensions/quickCreate/particles.tsx`, `packages/dev/core/src/Particles/particleHelper.ts`) possess 100% Exposure for Injection Surfaces. Ensure strict boundary validation if modifying node graphs or property grids that accept user configuration.
3. **Supply Chain:** There are 5,639 unknown dependencies bypassing the Zero-Trust whitelist and 36 binary anomalies (likely packed WASM or WebGL binaries). Do not add or bump external dependencies without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized TypeScript/WebGL knowledge to determine blast radius in this 550k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
