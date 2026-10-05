---
description: "You are operating within `Carbon`, a widely adopted PHP API extension for DateTime. The codebase is almost exclusively PHP (99.1%)."
---
# AGENTS.md: Carbon Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `Carbon`, a widely adopted PHP API extension for DateTime. The codebase is almost exclusively PHP (99.1%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 7.409. The network topology demonstrates a hub-and-spoke model with moderate Modularity (0.6036) but negative Assortativity (-0.3468). This indicates that the core classes (like `CarbonInterval` and `CarbonPeriod`) act as massive orchestrators, relying heavily on a distributed network of highly specific PHP Traits (`src/Carbon/Traits/`) to compose their functionality. 
* **Core Rule:** Do NOT attempt to replace the existing trait-based composition with traditional inheritance hierarchies. The library is explicitly designed to inject modular behaviors (e.g., Boundaries, Formatting, Modifiers) horizontally into the primary Carbon objects.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core formatting and temporal calculations (`format` in `MessageFormatterMapperStrongType.php` and `startOf` in `Traits/Boundaries.php`) operate with recursive O(2^N) time complexities in static analysis due to deep runtime dynamic dispatch and catalogue lookups. You MUST NOT introduce nested iterations or reflection-heavy type checking on the hot path of these formatting and localization routines.
* **Orchestrator Fragility:** Central orchestrators such as `src/Carbon/CarbonInterval.php` (38 outbound dependencies) and `src/Carbon/CarbonPeriod.php` (37 outbound dependencies) are highly fragile. Altering their internal state management or dependency chains requires rigorous verification against the massive downstream testing suite.
* **Avoid Dead Code Pruning:** Files like `src/Carbon/Traits/Boundaries.php` (20 orphaned functions) and `src/Carbon/Traits/Comparison.php` (16 orphaned functions) contain logic that static analysis tools often flag as "dead code." DO NOT autonomously attempt to prune these methods. Carbon relies on dynamic macro invocation (`__call`, `__callStatic`) and runtime trait resolution which bypasses static AST mapping.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and extensive unit test verification before modifying the structural signatures, macro reflections, or public APIs of these files:
* `src/Carbon/Traits/Localization.php` (High Volatility Hotspot: 59.1% Churn, 100% Tech Debt, Key Person Silo - `kylekatarnls`)
* `src/Carbon/Callback.php` (Severe Blind Bottleneck - 100% Documentation Risk)
* `src/Carbon/PHPStan/MacroMethodReflection.php` (Severe Blind Bottleneck and critical for static analysis type-hinting downstream)
* `src/Carbon/Traits/Test.php` and `src/Carbon/CarbonTimeZone.php` (Key Person Silos - 100% isolated ownership by `kylekatarnls`)
* `tests/remove-comments-in-switch.php` (Highest Cumulative Risk: 472.48, extreme injection surface due to AST/Regex operations on PHP code itself)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SCRIPTING CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** The utility script `tests/remove-comments-in-switch.php` has a 100% Injection Surface Exposure. Because it programmatically modifies other PHP files, any changes to its regex or file-writing logic must be strictly bounded to prevent arbitrary code injection or source-code corruption.
2. **Exception Handling Architecture:** The system relies heavily on specific exception types (`InvalidArgumentException`, `RuntimeException`, `NotLocaleAwareException`). Do not mask or swallow these exceptions; the overarching framework depends on them for precise error state resolution.
3. **Supply Chain:** There are 3 binary anomalies identified by X-Ray. Do not modify or attempt to execute unrecognized binary blobs or test fixtures without verifying their integrity via the build pipeline.

## 5. Environmental Tooling (The Oracle)
Do not guess trait dependencies, hallucinate method resolutions, or rely on generalized PHP knowledge to determine blast radius within this heavily dynamic, macro-driven extension. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file, paying special attention to trait inclusion matrices.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
