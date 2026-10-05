---
description: "You are operating within `bootstrap`, the world's most popular CSS framework. The repository is a highly structured blend of CSS/SCSS (42.7%),..."
---
# AGENTS.md: bootstrap Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bootstrap`, the world's most popular CSS framework. The repository is a highly structured blend of CSS/SCSS (42.7%), Astro/HTML documentation (26.3%), and vanilla JavaScript UI components (15.8%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates excellent Modularity (0.665) typical of a component-driven framework, but significant negative assortativity (-0.5261). This indicates a "hub-and-spoke" dependency model: isolated UI components (the spokes) rely heavily on a few central SCSS variables, mixins, and core JS utilities (the hubs). Do not attempt to introduce deep hierarchical inheritance or tight coupling between sibling UI components.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core DOM manipulation and UI component state management (`parseSelector` in `js/src/util/index.js`, `show` in `js/src/tooltip.js`) operate at high algorithmic complexity (`O(2^N)` in static analysis) due to deeply recursive DOM traversal and event delegation. You MUST NOT introduce additional nested loops or heavy synchronous queries inside these Javascript components to prevent main-thread blocking.
* **Orchestrator Fragility:** Central SCSS orchestrators like `scss/bootstrap.scss` (40 outbound dependencies) and `scss/_mixins.scss` (25 outbound dependencies) are highly fragile. Any changes to SCSS variable maps, mixin signatures, or import orders within these files will cause immediate, cascading visual breaks across the entire framework.
* **Avoid Dead Code Pruning:** The JavaScript utilities (`js/src/dom/selector-engine.js`, `site/src/libs/utils.ts`) and `js/src/tooltip.js` contain logic that static analysis tools flag as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. Bootstrap relies heavily on dynamic event listeners (`data-bs-*` attributes) and reflection that bypass static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream visual regression testing before modifying the structural signatures, event handlers, or public APIs of these files:
* `js/src/tooltip.js` (Highest Cumulative Risk: 530.0, Key Person Silo - 100% isolated ownership by Amit Rathiesh)
* `js/src/dropdown.js` (Key Person Silo - 100% isolated ownership by Mark Otto, High Tech Debt)
* `js/src/collapse.js` (Key Person Silo - 100% isolated ownership by Mohamad Salman)
* `site/src/libs/astro.ts` (Severe Blind Bottleneck - 100% Documentation Risk, High Blast Radius)
* `js/src/util/index.js` (Core DOM query engine, High impact O(2^N) complexity)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **DOM Injection Surface:** The core DOM manipulator (`js/src/dom/manipulator.js`) handles user-provided `data-*` attributes to instantiate JavaScript components. While Bootstrap includes a sanitizer (`js/src/util/sanitizer.js`), any modifications to attribute parsing or template rendering MUST be rigorously audited to prevent Cross-Site Scripting (XSS) vulnerabilities.
2. **Supply Chain:** There are 63 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external NPM packages or modify the build scripts without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized CSS/JS knowledge to determine blast radius within this highly coupled framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
