---
description: "You are operating within `berry`, the repository for Yarn v2+ (Plug'n'Play), primarily composed of TypeScript (41.3%) and JavaScript (19.6%)."
---
# AGENTS.md: berry (Yarn v2+) Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `berry`, the repository for Yarn v2+ (Plug'n'Play), primarily composed of TypeScript (41.3%) and JavaScript (19.6%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 6.157. The network topology demonstrates a clean Modularity (0.5945) due to its monorepo package structure, but a significant negative assortativity (-0.3068). This indicates the architecture relies heavily on highly connected hub nodes (fragile single points of failure) coordinating many isolated plugins. Do not attempt to break encapsulation between packages (`yarnpkg-core`, `yarnpkg-pnp`, `plugin-essentials`).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core resolution and tree-building functions (`addPackageToTree` in `buildNodeModulesTree.ts`, `makeLockfileChecksum` in `Project.ts`, and `makePathWrapper` in `scriptUtils.ts`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the dependency resolution graph, PnP loader, or lockfile generation logic.
* **Orchestrator Fragility:** Central coordinators such as `packages/plugin-essentials/sources/index.ts` (41 outbound dependencies) and `packages/yarnpkg-core/sources/Project.ts` (38 outbound dependencies) are highly fragile orchestrators. Any changes to package lifecycles, configuration contracts, or plugin hooks within these files require immediate, comprehensive verification of downstream integration tests.
* **Avoid Dead Code Pruning:** AST parsers and virtual file system (ZipFS) implementations (`packages/yarnpkg-libzip/sources/ZipFS.ts`, `packages/yarnpkg-core/sources/structUtils.ts`) contain dozens of orphaned functions. DO NOT autonomously attempt to prune, format, or clean up these files. The PnP runtime and CLI plugins rely on dynamic dispatch and reflection that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, recursive parsing logic, or public APIs of these files:
* `packages/yarnpkg-core/sources/Project.ts` (Highest Cumulative Risk: 693.19, Massive Volatility Hotspot: 69.9% Churn)
* `packages/plugin-essentials/sources/commands/entries/clipanion.ts` (Severe Blind Bottleneck - 77 inbound connections flying blind)
* `packages/plugin-pnpm/sources/PnpmLinker.ts` (High Cumulative Risk, 100% Cognitive Load)
* `packages/yarnpkg-pnp/sources/node/resolve.js` (House of Cards - Embedded core resolution logic with 77.3% Error Risk)
* `packages/yarnpkg-libzip/sources/ZipFS.ts` (Key Person Silo - 100% isolated ownership by Maël Nison)
* `packages/yarnpkg-pnpify/sources/NodeModulesFS.ts` (Key Person Silo - Maël Nison)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT GENERATION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `packages/yarnpkg-core/sources/Project.ts`, `packages/yarnpkg-pnp/sources/loader/makeApi.ts`, and the `libzip` bindings possess a 100% Exposure score for Exploit Generation Surface due to the nature of parsing, unpacking, and executing third-party code. When modifying package resolution or shell execution (`packages/yarnpkg-parsers/sources/shell.ts`), you MUST ensure strict input sanitization and boundary checking to prevent malicious package payloads from escaping the PnP sandbox.
2. **Supply Chain:** There are 1,664 unknown dependencies bypassing the Zero-Trust whitelist and 29 binary anomalies (likely packed WASM or native bindings). Do not add or bump external dependencies without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Node/Yarn knowledge to determine blast radius within this highly complex monorepo. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
