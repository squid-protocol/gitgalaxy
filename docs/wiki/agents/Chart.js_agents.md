---
description: "You are operating within `Chart.js`, a highly popular HTML5 Canvas-based charting library. The repository is predominantly JavaScript (52.0%) and..."
---
# AGENTS.md: Chart.js Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `Chart.js`, a highly popular HTML5 Canvas-based charting library. The repository is predominantly JavaScript (52.0%) and TypeScript (32.5%), reflecting an ongoing, partial migration toward static typing.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 8.721. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, indicating a monolithic, highly coupled architecture. The entire system relies on a flat dependency graph where core controllers, scales, and plugins mutate shared canvas context and global configurations. Do NOT attempt to introduce deep inheritance or purely functional paradigms; the architecture requires direct, procedural canvas mutation and mutable state sharing.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core rendering and layout functions (`itemsEqual` in `src/plugins/plugin.legend.js`, `draw` in `src/core/core.datasetController.js`) operate at high recursive time complexities (O(2^N) in static analysis) due to deep object traversal and nested canvas drawing loops. You MUST NOT introduce additional nested iterations, deep clones, or O(N^2+) complexity in the critical rendering path (`draw()` or `update()` methods).
* **Orchestrator Fragility:** Central orchestrators like `src/index.umd.ts` (18 outbound dependencies) and `src/core/core.controller.js` (13 outbound dependencies) are highly fragile. Any changes to object exports, plugin registration, or scale initialization within these files require immediate, comprehensive verification of downstream chart instantiations.
* **Avoid Dead Code Pruning:** The core architecture relies heavily on dynamic property resolution and optional plugin interfaces. Files like `src/core/core.datasetController.js` (19 orphaned functions) and `src/core/core.scale.js` (17 orphaned functions) contain logic that static analysis tools flag as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. These are critical lifecycle hooks intended to be overridden or called dynamically by users.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream visual regression testing before modifying the structural signatures, canvas contexts, or public APIs of these files:
* `src/core/core.scale.js` (Massive Structural Mass: 1373.12, Key Person Silo - 100% isolated ownership by asmenezes)
* `src/plugins/plugin.legend.js` (High Cognitive Load: 66.7%, massive O(2^N) complexity in `itemsEqual`)
* `src/controllers/controller.bar.js` (Key Person Silo - 100% isolated ownership by Xavier Leune)
* `src/core/core.controller.js` (Primary class instantiation and lifecycle manager)
* `src/core/core.datasetController.js` (High Tech Debt: 82.9%, highly coupled data parsing logic)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Supply Chain:** There are 22 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external NPM packages without explicit architectural review.
2. **Zero-Dependency Mandate:** Chart.js is historically a zero-dependency library (excluding build tools). You MUST NOT introduce runtime dependencies (e.g., Lodash, D3) into the `src/` directory. All math and collection utilities must use the internal `src/helpers/` functions.

## 5. Environmental Tooling (The Oracle)
Do not guess canvas rendering contexts, hallucinate scale ID resolutions, or rely on generalized DOM knowledge to determine blast radius within this highly specific Canvas wrapper. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
