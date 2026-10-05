---
description: "You are operating within `three.js`, a highly mature and massively adopted 3D JavaScript library. The repository is heavily dominated by JavaScript..."
---
# AGENTS.md: three.js Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `three.js`, a highly mature and massively adopted 3D JavaScript library. The repository is heavily dominated by JavaScript (55.8%) and HTML examples/documentation (37.4%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 11.361. The network topology demonstrates extreme "spaghetti" coupling (Modularity: 0.0361) combined with highly fragile single-points-of-failure (Assortativity: -0.5314). This indicates a tightly interwoven core where nearly all renderers, loaders, and scene graph components rely heavily on a centralized set of objects.
* **Core Rule:** Maintain strict adherence to the existing prototype chains, memory management loops (dispose patterns), and shader chunk structures. Do NOT attempt to decouple foundational orchestrators (`Three.Core.js`, `Addons.js`) or introduce asynchronous execution into synchronous rendering paths (e.g., `WebGLRenderer.js`). 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core asset parsing (`VRMLLoader.js`, `EXRLoader.js`, `opentype.module.js`) and compression/decompression utilities (`fflate.module.js`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep byte-level traversal and AST generation. You MUST NOT introduce unbounded recursive loops, heavy synchronous allocations, or blocking garbage collection events inside the main render loop or asset parsing callbacks.
* **Orchestrator Fragility:** Central orchestrators such as `examples/jsm/Addons.js` (257 outbound dependencies) and `src/nodes/Nodes.js` (139 outbound) are highly fragile. Modifying module aggregators or the core node material system requires immediate, comprehensive verification via the unit test suite and visual example regression checks.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions", particularly within the node-based material system (`src/nodes/core/NodeBuilder.js` with 79 orphans) and math primitives (`src/math/Vector3.js`). DO NOT autonomously attempt to prune, format, or clean up these files. The library relies heavily on exhaustive mathematical APIs and WebGPU node generation that static analysis tools misinterpret as unused.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes" or extreme volatility hotspots. They possess massive structural mass, represent single-points-of-failure, or are actively undergoing architectural rewrites. 

**MANDATORY RULE:** You require explicit human permission and downstream visual regression testing before modifying the structural signatures, WebGL/WebGPU state machines, or public APIs of these files:
* `src/renderers/common/Renderer.js` & `src/renderers/WebGLRenderer.js` (Extreme Volatility Hotspots: >90% Churn. The core execution loops for the entire rendering engine).
* `src/renderers/webgpu/nodes/WGSLNodeBuilder.js` & `src/nodes/core/NodeBuilder.js` (Massive architectural hotspots driving the transition to WebGPU).
* `editor/js/libs/codemirror/codemirror.js` & `editor/js/libs/esprima.js` (Massive Structural Mass. Third-party vendor dependencies driving the in-browser editor).
* `src/renderers/shaders/ShaderChunk/lights_fragment_begin.glsl.js` (Key Person Silo - 100% isolated ownership by `mrdoob`. Critical shader logic).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface (Loaders & Parsers):** Files handling complex external file formats (`examples/jsm/loaders/FBXLoader.js`, `VTKLoader.js`) and AST parsers (`esprima.js`) possess 100% Exposure for Exploit Generation. When parsing untrusted 3D models or fonts (`opentype.module.js`), you MUST ensure strict array bounds checking, prevent prototype pollution, and sanitize geometry indices to prevent browser memory exhaustion or XSS via embedded model metadata.
2. **Obfuscation & Test Minification:** Several unit test files (e.g., `AnimationAction.tests.js`, `MathUtils.tests.js`) triggered obfuscation warnings. Do not flag these as malicious; they rely on minified assertions or dense numerical arrays required for vector math validation.
3. **Supply Chain:** There are 529 unknown dependencies bypassing the Zero-Trust whitelist (mostly within `editor/` or `manual/`). Do not add or bump external packages in `package.json` without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess WebGL context state transitions, hallucinate WGSL shader topologies, or rely on generalized JavaScript knowledge to determine blast radius within this 440k+ LOC graphics library. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
