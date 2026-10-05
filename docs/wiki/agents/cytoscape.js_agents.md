---
description: "You are operating within `cytoscape.js`, a graph theory (a.k.e. network) library for analysis and visualization. The repository is predominantly..."
---
# AGENTS.md: cytoscape.js Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cytoscape.js`, a graph theory (a.k.e. network) library for analysis and visualization. The repository is predominantly JavaScript (42.7%) and heavily utilizes standard DOM/Canvas/WebGL APIs for rendering.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates relatively low Modularity (0.3745) and extreme negative Assortativity (-0.7686). This signifies a "hub-and-spoke" model where a few foundational mathematical and coordinate-mapping files are imported by nearly every rendering and layout extension, creating fragile single points of failure.
* **Core Rule:** Maintain the strict boundary between the headless graph analysis core (`src/collection/`) and the rendering extensions (`src/extensions/renderer/`). Do NOT introduce DOM or Canvas dependencies into the mathematical core.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Graph algorithms (`bellmanFord`, `dijkstra`, `a-star` in `src/collection/algorithms/`) and layout functions natively approach O(N^2) or O(2^N) complexities due to recursive traversal of edges and nodes. You MUST NOT introduce unbounded recursive calls, deep DOM queries, or expensive synchronous layouts on the main UI thread. Use bounding boxes (`getAllInBox`) and spatial indexing for collision detection.
* **Orchestrator Fragility:** Central orchestrators like `src/collection/index.mjs` (21 outbound dependencies) and `src/core/index.mjs` are highly fragile. Any changes to the core `Collection` or `Core` prototypes require immediate, comprehensive verification of downstream extensions and user-facing API compatibility.
* **Avoid Dead Code Pruning:** Files like `src/math.mjs` (38 orphaned functions) and WebGL utilities (`src/extensions/renderer/canvas/webgl/atlas.mjs`) contain logic flagged as "dead code." DO NOT autonomously attempt to prune or clean up these files. Cytoscape exposes a massive public math and utility API for external layout authors; these functions are intentionally isolated.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream rendering verification before modifying the structural signatures, WebGL contexts, or public APIs of these files:
* `src/extensions/renderer/base/coord-ele-math/coords.mjs` (Highest Cumulative Risk: 608.29, Extreme Volatility Hotspot: 81.4% Churn. Core coordinate mapping).
* `src/extensions/renderer/base/load-listeners.mjs` (Massive Structural Mass: 2081.0, Key Person Silo - 100% isolated ownership by Max Franz).
* `src/math.mjs` (Key Person Silo - 100% isolated ownership by Max Franz).
* `src/collection/index.mjs` (Key Person Silo - 100% isolated ownership by Felix Pahl).
* `documentation/demos/visual-style/code.js` (Severe Blind Bottleneck - High blast radius flying blind with 100% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH DOM CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **DOM/XSS Exposure:** Because Cytoscape handles user-provided data labels and SVG assets, ensure any modifications to DOM insertion (e.g., tooltips, HTML labels) strictly sanitize inputs to prevent Cross-Site Scripting (XSS).
2. **Event Listener Leaks:** The `src/event.mjs` and `src/extensions/renderer/base/load-listeners.mjs` files manage hundreds of DOM and Canvas event bindings. Ensure proper `removeEventListener` cleanup during graph destruction to prevent severe memory leaks in long-running Single Page Applications (SPAs).
3. **Supply Chain:** There are 18 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external NPM packages without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess WebGL texture packing (`atlas.mjs`), hallucinate Canvas rendering contexts, or rely on generalized JavaScript knowledge to determine blast radius within this highly specialized visualization engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
