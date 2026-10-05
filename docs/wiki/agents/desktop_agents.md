---
description: "You are operating within the `desktop` repository, the source code for GitHub Desktop. This is a heavy client application built primarily on TypeScript..."
---
# AGENTS.md: GitHub Desktop Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `desktop` repository, the source code for GitHub Desktop. This is a heavy client application built primarily on TypeScript (81.0%) utilizing Electron and React.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 8.342. The network topology demonstrates extremely low Modularity (0.0256) and neutral Assortativity (0.0). This indicates a highly coupled, monolithic architecture characteristic of complex React/Flux-like stores where a few massive "God Nodes" (the stores and the main dispatcher) manage the entire application state. Do NOT attempt to decouple this into isolated micro-architectures; the system relies heavily on synchronous state updates and rigid unidirectional data flow.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core git operations (`merge` in `git-store.ts`, `renameBranch`, `fetch`) and React render paths (`safeDirectoryName`, `renderUpdateErrors`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep component trees and nested shell executions. You MUST NOT introduce unbounded loops, deep recursion, or heavy synchronous file-system I/O onto the main React render thread or within the `Dispatcher` methods.
* **Orchestrator Fragility:** Central orchestrators such as `app/src/ui/app.tsx` (153 outbound dependencies), `app-store.ts` (115 outbound), and the global SCSS (`_ui.scss`) are highly fragile. Any changes to global state shapes, IPC (Inter-Process Communication) event listeners, or base layout components require immediate, comprehensive verification across the entire UI.
* **Avoid Dead Code Pruning:** Files like `app/src/lib/stores/app-store.ts` (116 orphaned functions) and `dispatcher.ts` (67 orphaned functions) contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The application utilizes a Flux-like architecture where actions are dispatched dynamically and handled by stores, which static AST analyzers misinterpret as unused functions.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream Electron/React testing before modifying the structural signatures, IPC boundaries, or public APIs of these files:
* `app/src/lib/stores/app-store.ts` (Highest Cumulative Risk: 713.52, 100% Churn. The central state machine).
* `app/src/ui/dispatcher/dispatcher.ts` (Massive Structural Mass and Tech Debt. Translates UI actions to state mutations).
* `app/src/ui/app.tsx` (The root React component; highly volatile with massive blast radius).
* `app/src/ui/lib/list/list.tsx` & `section-list.tsx` (Key Person Silos - 100% isolated ownership by `tidy-dev`. Core virtualized list implementations).
* `app/src/lib/path.ts` & `http.ts` (Foundational Pillars; changes here cascade instantly across the app).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH IPC/SHELL CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files handling external API requests (`app/src/lib/api.ts`) and shell process execution (`app/src/lib/diff-parser.ts`, `app/src/main-process/main.ts`) possess high exposure for Exploit Generation. Because GitHub Desktop executes Git commands via local shell processes, you MUST ensure strict input sanitization of branch names, repository paths, and user inputs to prevent Command Injection.
2. **Hardcoded Payload Artifacts:** `app/.npmrc` and `app/src/ui/diff/diff-helpers.tsx` tripped payload signatures. DO NOT flag these as leaked secrets; these are required configurations and fixture mappings for syntax highlighting/diff rendering.
3. **Supply Chain:** There are 588 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external NPM packages in the root `package.json` without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess IPC channel names, hallucinate Git command arguments, or rely on generalized React knowledge to determine blast radius within this 116k+ LOC Electron application. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
