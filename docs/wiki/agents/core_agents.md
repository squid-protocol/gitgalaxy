---
description: "You are operating within the `vuejs/core` repository, the foundational implementation of the Vue 3 framework. The codebase is heavily dominated by..."
---
# AGENTS.md: vuejs/core Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `vuejs/core` repository, the foundational implementation of the Vue 3 framework. The codebase is heavily dominated by TypeScript (68.0%), functioning as a monolithic workspace containing several interdependent packages (e.g., `runtime-core`, `compiler-core`, `reactivity`).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 8.026. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly coupled, central-hub architecture where the packages are deeply intertwined, despite folder-level separation. 
* **Core Rule:** Do NOT attempt to decouple packages into isolated micro-architectures. The framework requires tight, synchronous execution between the reactivity system, compiler, and renderer. Maintain the existing import structures and internal typings.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core AST transformation and template parsing routines (`helper` in `vFor.ts`, `inferRuntimeType` in `resolveType.ts`, `getNamespace` in `parser.ts`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursion, deep AST clones, or O(N^2+) complexity in the compiler or reactivity update loops, as this will catastrophically degrade framework performance.
* **Orchestrator Fragility:** Central orchestrators such as `packages/runtime-core/src/index.ts` (47 outbound dependencies) and `packages/compiler-sfc/src/compileScript.ts` (25 outbound dependencies) are highly fragile. Any changes to public exports, component lifecycle hooks, or SFC compilation behavior require immediate, comprehensive verification via the core test suite.
* **Avoid Dead Code Pruning:** Files like `packages/compiler-core/src/ast.ts` and `packages/compiler-core/src/utils.ts` contain functions flagged as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. These are often utility functions intended for cross-package use or external plugin consumption that bypass static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and extensive performance benchmarking before modifying the structural signatures, recursive AST walkers, or public APIs of these files:
* `packages/compiler-core/src/utils.ts` (Highest Cumulative Risk: 621.33, 100% Spec Match and Documentation Risk)
* `packages/runtime-core/src/renderer.ts` (Massive Structural Mass: 268.52, O(N^4) rendering complexity)
* `packages/compiler-sfc/src/script/resolveType.ts` (High Cognitive Load, recursive type inference logic)
* `scripts/release.js` & `scripts/build.js` (Key Person Silos - 100% isolated ownership. Critical CI/CD automation)
* `packages/runtime-core/src/componentProps.ts` (Key Person Silo - 100% isolated ownership by Tycho)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH COMPILER CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files related to template compilation (`packages/compiler-core/src/utils.ts`) possess near 100% Exposure for Exploit Generation. Because Vue compiles untrusted templates into executable JavaScript render functions, you MUST ensure strict adherence to existing AST sanitization and code-generation escaping mechanisms to prevent Cross-Site Scripting (XSS).
2. **Supply Chain:** There are 806 unknown dependencies bypassing the Zero-Trust whitelist (expected in a large monorepo with multiple examples/playgrounds). Do not add or bump external NPM packages in the root or package-level `package.json` files without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess TypeScript type inference boundaries, hallucinate AST node transformations, or rely on generalized Vue usage knowledge to determine blast radius within the framework's core. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
