---
description: "You are operating within `mediawiki`, the massive, foundational PHP application that powers Wikipedia and its sister projects. The repository is..."
---
# AGENTS.md: mediawiki Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `mediawiki`, the massive, foundational PHP application that powers Wikipedia and its sister projects. The repository is heavily dominated by PHP (51.0%) for backend logic and APIs, supported by massive JSON configurations (36.7%) and a dense JavaScript/CSS frontend layer via ResourceLoader (5.6%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits an Architectural Drift Z-Score of 4.841. The network topology demonstrates high Modularity (0.7819) but negative Assortativity (-0.1254). This indicates a highly decoupled but "hub-and-spoke" architecture where isolated modules and extensions rely entirely on massive, centralized God Nodes (like `ServiceWiring.php` and `MediaWikiServices.php`) for dependency injection and state management.
* **Core Rule:** Maintain strict adherence to MediaWiki's Dependency Injection (DI) container and ResourceLoader paradigms. Do NOT attempt to decouple foundational orchestrators or introduce asynchronous execution into synchronous PHP lifecycles. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Several frontend JavaScript UI components (`initialize` in `BookletLayout.js`, `login` in `mediawiki.api/login.js`, and `formatRequest` in `ApiSandbox.js`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep DOM traversals and promise chaining. You MUST NOT introduce unbounded loops, heavy synchronous operations, or recursive event listeners on the critical path of the browser UI or ResourceLoader module execution.
* **Orchestrator Fragility:** Central orchestrators such as `includes/ServiceWiring.php` (301 outbound dependencies) and `includes/MediaWikiServices.php` (241 outbound) are highly fragile. Modifying service registration, global configuration definitions (`MainConfigSchema.php`), or special page routing (`SpecialPageFactory.php`) requires immediate, comprehensive verification via the PHPUnit integration test suite.
* **Avoid Dead Code Pruning:** Files like `FiltersViewModel.js` (24 orphaned functions), `Controller.js` (18 orphans), and `LinksTable.php` contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. MediaWiki heavily utilizes dynamic hook dispatching (`HookContainer`), event emissions, and late static binding that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, hook definitions, or public APIs of these files:
* `includes/MainConfigSchema.php` (Highest Volatility and Risk: 80.5% Churn, 100% Injection Surface. Dictates global configuration schema).
* `resources/src/mediawiki.rcfilters/Controller.js` & `FiltersViewModel.js` (Key Person Silos - 100% isolated ownership by Cormac Parle. Critical to Recent Changes UI).
* `resources/src/mediawiki.special.apisandbox/ApiSandbox.js` (Key Person Silo - 100% isolated ownership by Ammarpad).
* `includes/libs/StatusValue.php` (Severe House of Cards - 107 inbound connections with 58.8% Error Risk. Fundamental return type for operations).
* `resources/src/mediawiki.widgets.datetime/DiscordianDateTimeFormatter.js` (Key Person Silo - 100% isolated ownership by Ed Sanders).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** Core schema and module files (`includes/MainConfigSchema.php`, `includes/ResourceLoader/CodexModule.php`, `maintenance/benchmarks/benchmarkEval.php`) possess 100% Exposure for Weaponizable Injection. Because MediaWiki handles immense volumes of untrusted, user-generated wikitext, you MUST ensure strict sanitization, CSRF token validation, and correct usage of `Html::escape()` or equivalent DOM sanitizers to prevent XSS or SQL Injection.
2. **Exploit Generation Surface:** Client-side orchestration scripts (`mediawiki.api/index.js`, `startup/mediawiki.loader.js`) possess 100% Exposure for Exploit Generation. Any modifications to API request handling or dynamic module loading must rigorously validate module names and endpoints.
3. **Hardcoded Payload Artifacts:** Files such as `tests/phpunit/integration/includes/Json/key1.pem` and `key2.pem.pub` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying JSON Web Token (JWT) or OAuth implementations.
4. **Supply Chain:** There are 374 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external packages in `composer.json` or `package.json` without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess MediaWiki Hook arguments, hallucinate ResourceLoader module definitions, or rely on generalized PHP knowledge to determine blast radius within this 495k+ LOC wiki engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
