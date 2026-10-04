---
description: "You are operating within `tailwindcss`, a highly adopted, utility-first CSS framework. The codebase is heavily dominated by TypeScript (78.8%) and CSS..."
---
# AGENTS.md: tailwindcss Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `tailwindcss`, a highly adopted, utility-first CSS framework. The codebase is heavily dominated by TypeScript (78.8%) and CSS (13.7%), with significant logic dedicated to AST (Abstract Syntax Tree) parsing, configuration resolution, and dynamic CSS generation.

* **Architectural Paradigm:** The repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 6.945. The network topology demonstrates a Hub-and-Spoke model with high Modularity (0.6559) but negative Assortativity (-0.197). This signifies a centralized architecture where isolated utility plugins (e.g., within `src/corePlugins.js`) rely entirely on a dense core of shared utilities and AST orchestrators (`pluginUtils.js`, `resolveConfig.js`).
* **Core Rule:** Maintain strict adherence to the AST transformation pipeline. Do NOT attempt to decouple foundational orchestrators or bypass the standard plugin API. The architecture relies on predictable, functional data flows through PostCSS node transformations.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core CSS parsing and AST manipulations (`expandApplyAtRules`, `resolveConfig`, and `parseObjectStyles`) operate at extreme recursive time complexities (O(2^N) and O(N^6) in static analysis) due to deep configuration merging and recursive `@apply` resolution. You MUST NOT introduce unbounded recursive loops, synchronous blocking file I/O, or deeply nested object iterations into the hot paths of the CSS compiler.
* **Orchestrator Fragility:** Central orchestrators such as `src/plugin.js` (62 outbound dependencies), `src/util/resolveConfig.js` (54 outbound), and `src/corePlugins.js` (49 outbound) are highly fragile. Modifying configuration resolution or plugin registration requires rigorous verification against the test suite, as failures here break the entire compilation pipeline.
* **Avoid Dead Code Pruning:** Files like `src/corePlugins.js` (89 orphaned functions) and `src/util/transformThemeValue.js` (54 orphaned functions) contain logic flagged as "dead code." DO NOT autonomously attempt to prune or refactor these files. Tailwind relies heavily on dynamic plugin registration and object key mapping that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and extensive compilation testing before modifying the structural signatures, AST transformations, or public APIs of these files:
* `src/lib/expandApplyAtRules.js` & `src/util/resolveConfig.js` (Extreme Volatility Hotspots: >80% Churn. Key Person Silos - 100% isolated ownership by Adam Wathan. The absolute core of the compilation engine).
* `src/util/pluginUtils.js` (Severe Blind Bottleneck - 112 inbound connections with 100% Documentation Risk. Massive blast radius affecting nearly all plugins).
* `src/util/color.js` (High Tech Debt and 100% Documentation Risk. A heavily relied-upon utility that touches almost every color-related class).
* `src/corePlugins.js` (The central registry for all default Tailwind utilities).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts.

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** AST generation logic (`src/util/parseObjectStyles.js`) possesses 100% Exposure for Exploit Generation. Ensure any modifications that handle object-to-CSS conversion safely escape keys and values to prevent injection of malicious CSS expressions.
2. **Weaponizable Injection Vectors:** Code responsible for parsing external dependencies and values (`src/util/parseDependency.js`, `src/util/parseBoxShadowValue.js`) exhibit 100% Weaponizable Injection Exposure. Because Tailwind processes untrusted user configurations (`tailwind.config.js`), you MUST ensure that dynamically parsed strings (especially those involving file paths or complex CSS values) are rigorously sanitized to prevent arbitrary file reads or malicious CSS generation.

## 5. Environmental Tooling (The Oracle)
Do not guess PostCSS AST structures, hallucinate configuration resolution logic, or rely on generalized TypeScript knowledge to determine blast radius within this compiler. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
