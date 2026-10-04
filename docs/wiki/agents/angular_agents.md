---
description: "You are operating within `angular`, a massive web framework ecosystem primarily composed of TypeScript (59.5%)."
---
# AGENTS.md: angular Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `angular`, a massive web framework ecosystem primarily composed of TypeScript (59.5%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 6.334. The network topology demonstrates highly negative assortativity (-0.4831), meaning the architecture relies heavily on highly connected hub nodes (fragile single points of failure) rather than a distributed core. Do not attempt to introduce decentralized or loosely coupled patterns into the core compiler (`ngtsc`), Ivy rendering engine (`render3`), or core dependency injection mechanisms.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core rendering and parsing methods (`walkIcuTree` in `i18n_parse.ts`, `visitBoundAttribute` in `inlay_hints.ts`, and `CreateTypeHintFn`) currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the language service, i18n parser, or Ivy template pipelines.
* **Orchestrator Fragility:** Central coordinators such as `packages/compiler/src/template/pipeline/src/emit.ts` (73 outbound dependencies) and `packages/core/src/core_private_export.ts` (60 outbound dependencies) are highly fragile orchestrators. Any changes to data contracts, AST generation, or public API surfaces within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Execution engines and AST components such as `packages/core/src/render3/state.ts` (43 orphaned functions) and `packages/compiler/src/output/output_ast.ts` (38 orphaned functions) contain high volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed, as the framework relies on dynamic runtime compilation, Ivy instructions, and metaprogramming that static analysis tools may misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, AST resolution logic, or public APIs of these files:
* `packages/compiler-cli/src/ngtsc/util/src/typescript.ts` (House of Cards / Blind Bottleneck - 422 inbound connections, 45.2% Error Risk)
* `packages/service-worker/worker/src/idle.ts` (Highest Cumulative Risk: 743.83, 100% Injection Surface)
* `packages/animations/browser/src/render/transition_animation_engine.ts` (High Cumulative Risk: 734.35, 100% Exploit Generation Surface)
* `packages/common/http/src/client.ts` (Key Person Silo - 100% isolated ownership by SkyZeroZx)
* `packages/forms/signals/src/field/node.ts` (Extreme Volatility Hotspot - 89.27% Churn)
* `packages/core/src/util/assert.ts` (House of Cards - Embedded core utility with 26.4% Error Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `packages/animations/browser/src/render/transition_animation_engine.ts`, `packages/compiler/src/ml_parser/lexer.ts`, and `packages/common/http/src/client.ts` possess a 100% Exposure score for Exploit Generation Surface. When modifying the HTML/Template lexer or HTTP client, you MUST ensure strict input sanitization and avoid inadvertently bypassing XSS or CSRF protections.
2. **Weaponizable Injection Vectors:** `packages/router/src/models.ts` and `packages/service-worker/worker/src/idle.ts` possess 100% Exposure for Injection Surfaces. Ensure strict boundary validation if modifying routing state parsing or service worker caching strategies.
3. **Hardcoded Payload Artifacts:** Files like `.npmrc`, `adev/src/app/environment.ts`, and `packages/core/src/application/application_init.ts` have tripped hardcoded payload signatures. DO NOT flag these as leaked secrets or attempt to remove/obfuscate them unless explicitly auditing for accidental credential commits.
4. **Supply Chain:** There are 12,915 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external dependencies without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Angular knowledge to determine blast radius in this 480k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
