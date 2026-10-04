---
description: "You are operating within `ant-design`, a massive React UI component library primarily composed of TypeScript (63.5%) and Markdown documentation (35.6%)."
---
# AGENTS.md: ant-design Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `ant-design`, a massive React UI component library primarily composed of TypeScript (63.5%) and Markdown documentation (35.6%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.309. The network topology demonstrates a Modularity of 0.0, indicating highly intertwined "spaghetti" coupling across components and their configuration providers. Do not attempt to force strict, isolated modularity or generic application-level MVC patterns onto the component architecture, as cross-component styling and context sharing are foundational to the library's design.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core table hooks and styling computations (`components/table/hooks/useSorter.tsx`, `components/table/style/index.ts`, and `components/steps/index.tsx`) currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying table sorting, filtering, or CSS-in-JS style generation logic.
* **Orchestrator Fragility:** Central coordinators such as `components/index.ts` (83 outbound dependencies) and `components/config-provider/context.ts` (69 outbound dependencies) are highly fragile orchestrators. Any changes to data contracts, context providers, or public properties within these files require immediate, comprehensive verification of downstream component integration.
* **Avoid Dead Code Pruning:** Test utilities and core components (`tests/utils.tsx`, `.dumi/theme/utils/index.ts`, and `components/modal/confirm.tsx`) contain a high volume of unreferenced (orphaned) logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as the documentation engine (dumi) and test runners often rely on dynamic imports or specific structural conventions.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, recursive hooks, or public APIs of these files:
* `scripts/build-style.tsx` (Highest Cumulative Risk: 609.19, Extreme Volatility Hotspot: 72.04% Churn)
* `components/table/hooks/useSelection.tsx` (Heavy Mass: 106.02, critical table selection logic)
* `components/color-picker/color.ts` (High Cumulative Risk: 578.33, highly complex class logic)
* `scripts/visual-regression/upload.js` (Key Person Silo - 100% isolated ownership by `thinkasany`)
* `components/table/hooks/useSorter.tsx` (Key Person Silo - 100% isolated ownership by `lijianan`)
* `eslint.config.mjs` (Extreme Volatility Hotspot: 100% Churn)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Hardcoded Payload Artifacts:** `.npmrc` has tripped hardcoded payload signatures (100% Exposure). DO NOT flag this as a leaked secret or attempt to remove/obfuscate it unless explicitly auditing for accidental credential commits.
2. **Supply Chain:** There are 875 unknown dependencies bypassing the Zero-Trust whitelist and 33 binary anomalies within the repository structure. Do not add or bump external dependencies (especially in the `scripts/` or `.dumi/` directories) without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized React knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
