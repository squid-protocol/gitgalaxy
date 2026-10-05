---
description: "You are operating within `cesium`, a massive 3D geospatial visualization engine composed primarily of JavaScript (44.5%), HTML documentation/examples..."
---
# AGENTS.md: cesium Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cesium`, a massive 3D geospatial visualization engine composed primarily of JavaScript (44.5%), HTML documentation/examples (17.4%), and GLSL shaders (9.5%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 6.603. The network topology demonstrates a Hub-and-Spoke model with extreme negative assortativity (-0.5977) but poor modularity (0.2315). This indicates a highly coupled "spaghetti" architecture where rendering components (`Scene`, `DataSources`, `Primitive`) are deeply intertwined with core math and geometry helpers. Do not attempt to impose strict MVC or decoupled micro-patterns; the system relies heavily on direct prototyping and tightly bound object graph traversals.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core WebGL data structures (`getShaderExpression` in `Expression.js`, and `BillboardCollection.js`) operate at extreme O(2^N) recursive time complexities due to shader generation and deep prototype chain mutations. You MUST NOT introduce additional nested loops or O(N^2+) complexity in the rendering loop (`Scene.js`), matrix math (`Matrix4.js`), or geometry processors (`GeometryPipeline.js`).
* **Orchestrator Fragility:** Central orchestrators like `CzmlDataSource.js` (93 outbound dependencies) and `Scene.js` (83 outbound dependencies) dictate the entire rendering pipeline. Any changes to data contracts, prototype definitions, or GLSL variable injections within these files require immediate, comprehensive verification of downstream visual regressions.
* **Avoid Dead Code Pruning:** The `Packages/engine/Source/Core/` directory (e.g., `Matrix4.js` with 44 orphaned functions, `Camera.js` with 32) contains logic that static analysis tools flag as dead code. DO NOT autonomously attempt to prune, format, or clean up these files. CesiumJS is a library intended for external consumers; these "orphaned" methods form the public API surface for developers.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream WebGL testing before modifying the structural signatures, shader injection strings, or public APIs of these files:
* `packages/engine/Source/Scene/Expression.js` (Massive Structural Mass: 2895.22, Core Shader Injector)
* `packages/engine/Source/DataSources/KmlDataSource.js` (Massive Structural Mass: 3576.98, complex XML parsing)
* `packages/engine/Source/Scene/TerrainFillMesh.js` (Key Person Silo - 100% isolated ownership by Matt Schwartz)
* `packages/engine/Source/Scene/GlobeSurfaceTileProvider.js` (Key Person Silo - 100% isolated ownership by Matt Schwartz)
* `packages/sandcastle/templates/Sandcastle.ts` (Severe Blind Bottleneck - 120 inbound connections flying blind with Doc Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files handling third-party editor inputs (`ContentEditableInput.js` in CodeMirror) and core resource fetching (`packages/engine/Source/Core/Resource.js`) possess a 100% Exposure score for Exploit Generation Surface. Because Cesium loads untrusted external data (CZML, KML, GeoJSON, 3D Tiles), you MUST ensure strict input sanitization and secure CORS handling to prevent XSS or arbitrary resource leakage.
2. **Third-Party Libraries:** The `ThirdParty/` directory (especially `codemirror-5.52.0`) contains heavily modified external libraries. Treat these as frozen state. Do not attempt to upgrade or refactor these without explicit architectural review, as they often contain custom patches required for the Sandcastle IDE.
3. **Supply Chain:** There are 769 unknown dependencies bypassing the Zero-Trust whitelist and 90 binary anomalies (likely WebGL textures or compressed WASM payloads). Do not modify or attempt to scan these binary assets.

## 5. Environmental Tooling (The Oracle)
Do not guess GLSL variable bindings, hallucinate Matrix offsets, or rely on generalized JavaScript knowledge to determine blast radius within this 390k+ LOC 3D engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
