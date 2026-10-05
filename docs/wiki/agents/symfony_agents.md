---
description: "You are operating within the `symfony` repository, the core codebase for the sprawling, enterprise-grade Symfony PHP framework. The architecture is..."
---
# AGENTS.md: symfony Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `symfony` repository, the core codebase for the sprawling, enterprise-grade Symfony PHP framework. The architecture is overwhelmingly dominated by PHP (97.7%), structured into highly decoupled, reusable components.
* **Architectural Paradigm:** The system maps to a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.447. The network topology demonstrates high Modularity (0.6976) but negative Assortativity (-0.1065). This indicates a cleanly segregated component architecture that still relies heavily on a few fragile, central "hub" nodes (e.g., Dependency Injection containers, core Parsers).
* **Core Rule:** Maintain strict adherence to the established Dependency Injection (DI) and interface-driven contracts. Do NOT tightly couple discrete components directly to one another; always interface through abstract service definitions and respect component boundaries.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core AST and string processing tasks, such as `parse` in `src/Symfony/Component/Yaml/Parser.php` and `doParse` in `src/Symfony/Component/ExpressionLanguage/Parser.php`, operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis) due to deep token traversal and regex matching. You MUST NOT introduce unbounded recursion, heavy synchronous file I/O, or massive object allocations inside these hot paths.
* **Orchestrator Fragility:** Central orchestrators like `src/Symfony/Component/VarExporter/Internal/Exporter.php` (85 outbound dependencies) and `src/Symfony/Component/DependencyInjection/Dumper/PhpDumper.php` (59 outbound) are highly coupled. Modifying how PHP code is generated, exported, or how the DI container is dumped requires comprehensive verification against the entire framework test suite.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `ConstraintViolationList.php` with 134 orphans, `ConstraintViolation.php` with 124 orphans). DO NOT autonomously attempt to prune or clean up these files. Symfony relies entirely on reflection, dynamic method invocation, and interface satisfaction that static dependency analysis tools interpret as unused.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent severe single-points-of-failure/Key Person Silos. 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, regex patterns, or public APIs of these files:
* `src/Symfony/Component/DependencyInjection/ContainerBuilder.php` (Massive Structural Mass: 4799.0, 64% Churn. The absolute core of the DI container).
* `src/Symfony/Component/Yaml/Parser.php` & `src/Symfony/Component/ExpressionLanguage/Parser.php` (Key Person Silos - 100% isolated ownership by Fabien Potencier. Core translation layers).
* `src/Symfony/Component/VarExporter/Internal/Exporter.php` (Key Person Silo - 100% isolated ownership by Nicolas Grekas. Highly fragile serialization logic).
* `src/Symfony/Component/Console/Application.php` (Extreme structural mass; orchestrates all CLI interactions).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation & Weaponizable Injection:** Files handling YAML parsing (`Yaml/Inline.php`, `Yaml/Parser.php`) and expression evaluation (`ExpressionLanguage/Parser.php`) possess 100% Exposure for Exploit Generation and Injection. Because Symfony processes untrusted configuration and dynamic templates, you MUST ensure strict input sanitization. Failure to properly escape values or safely unserialize data can introduce Remote Code Execution (RCE) or Object Injection vulnerabilities.
2. **Hardcoded Payload Artifacts:** Numerous `.pem` and `.crt` files in the `src/Symfony/Component/HttpClient/Tests/Fixtures/` directory (e.g., `server.crt`, `ca.crt`) tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying HTTP client SSL/TLS behaviors.
3. **Supply Chain:** There are 70 unknown dependencies bypassing the Zero-Trust whitelist. Given the scale of the Composer ecosystem, this is expected, but adding new third-party dependencies requires strict architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess container compilation logic, hallucinate YAML parsing mechanics, or rely on generalized PHP knowledge to determine blast radius within this 1.2M+ LOC framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
