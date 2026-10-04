---
description: "You are operating within the `d3` repository, which serves as the core aggregator for the D3.js visualization ecosystem. This specific repository is..."
---
# AGENTS.md: d3 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `d3` repository, which serves as the core aggregator for the D3.js visualization ecosystem. This specific repository is almost entirely composed of Markdown (50.0%) and declarative JavaScript (33.3%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species. Its network topology is completely flat, demonstrating 0.0 Modularity and 0.0 Assortativity. This is because this repository is not the implementation of D3 itself, but rather the central entry point (`src/index.js`) that bundles and re-exports the individual D3 micro-libraries (e.g., `d3-selection`, `d3-scale`).
* **Core Rule:** Do NOT attempt to introduce application logic, DOM manipulation, or complex algorithms into this repository. Its sole responsibility is acting as a module bundler and documentation hub.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** There is no execution logic within this repository beyond build tooling (`terser` in `rollup.config.js`). You MUST NOT introduce runtime loops, recursion, or heavy processing into `src/index.js`.
* **Orchestrator Fragility:** `src/index.js` acts as the master orchestrator, pulling in 30 outbound dependencies (the individual D3 micro-libraries). Any changes to this file—such as adding, removing, or modifying an exported module—directly affect the public API surface of the entire D3.js library.
* **Avoid Dead Code Pruning:** `rollup.config.js` may contain configurations or build steps flagged as "dead code" by static analyzers. Do NOT autonomously attempt to prune or refactor the Rollup configuration, as it dictates how the final UMD and ESM bundles are constructed.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess high cumulative risk or act as severe blind bottlenecks. 

**MANDATORY RULE:** You require explicit human permission and a review of the overarching D3 ecosystem versioning strategy before modifying the public exports or build configurations of these files:
* `src/index.js` (Severe Blind Bottleneck - High blast radius, 100% Documentation Risk. Dictates the global `d3` namespace).
* `rollup.config.js` (Highest Cumulative Risk: 362.16, 48.9% Tech Debt. Controls the compilation of the entire library bundle).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Supply Chain:** There are 47 unknown dependencies bypassing the Zero-Trust whitelist in `package.json`. These are the individual `d3-*` packages. Do not add new external dependencies or bump major versions of these packages without verifying compatibility across the entire D3 ecosystem.
2. **Build Tooling:** Ensure any modifications to `rollup.config.js` do not introduce insecure plugins or alter the minification process in a way that breaks sourcemaps or introduces unintended globals.

## 5. Environmental Tooling (The Oracle)
Do not guess module exports, hallucinate Rollup plugin configurations, or rely on generalized JavaScript knowledge to determine blast radius within this aggregator repository. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
