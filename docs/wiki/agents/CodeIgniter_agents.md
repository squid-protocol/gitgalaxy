---
description: "You are operating within `CodeIgniter` (specifically the 3.x branch), a legacy, lightweight PHP web framework. The repository is predominantly PHP..."
---
# AGENTS.md: CodeIgniter Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `CodeIgniter` (specifically the 3.x branch), a legacy, lightweight PHP web framework. The repository is predominantly PHP (74.0%), supported by static assets and Sphinx documentation.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a moderate Architectural Drift Z-Score of 4.813. The network topology is completely flat, demonstrating 0.0 Modularity and 0.0 Assortativity. This indicates an extremely tightly coupled, monolithic core. The framework relies heavily on global singletons, god objects (`system/core/Controller.php`, `system/core/Loader.php`), and dynamic class instantiation via `&get_instance()`. 
* **Core Rule:** Do NOT attempt to introduce modern PHP patterns like Dependency Injection (DI), Service Locators, namespaces, or strict type-hinting into the core `system/` directory. The architecture is locked into PHP 5.3+ compatibility constraints.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core utility functions (`entity_decode` in `system/helpers/typography_helper.php`) and database driver instantiations operate with recursive O(2^N) time complexities in static analysis due to deep string manipulation and connection routing. You MUST NOT introduce additional nested loops or heavy regex inside the `system/helpers/` or `system/database/` directories.
* **Orchestrator Fragility:** There are no cleanly defined orchestrators in the modern sense; rather, the entire framework is routed through implicit dependency chains. Treat `system/core/Security.php` and `system/database/DB_driver.php` as highly fragile. Any changes to XSS filtering or SQL string building require immediate, comprehensive verification against the test suite.
* **Avoid Dead Code Pruning:** The test mocks (`tests/mocks/`) and core super-classes (`system/core/Controller.php`) contain logic that static analysis tools flag as "orphaned functions." DO NOT autonomously attempt to prune, format, or clean up these files. CodeIgniter utilizes dynamic method invocation and runtime reflection that static analysis misinterprets as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream unit test verification before modifying the structural signatures, SQL abstractions, or public APIs of these files:
* `system/database/drivers/oci8/oci8_driver.php` (Highest Cumulative Risk: 443.63, extremely high Tech Debt)
* `system/core/Security.php` (Core XSS/CSRF defensive layer, massive risk if compromised)
* `system/core/compat/password.php` (High Cumulative Risk: 421.03, polyfills for critical cryptography functions)
* `system/database/DB_driver.php` (The core active record implementation; changes here break all DB interactions)
* `user_guide_src/source/_themes/sphinx_rtd_theme/static/js/theme.js` (Severe Blind Bottleneck - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `system/core/Output.php` and `system/core/Security.php` possess localized exposure for Exploit Generation. Because CodeIgniter handles raw HTTP output and input sanitization, you MUST ensure strict adherence to the existing `xss_clean` and CSRF protection mechanisms. Do not bypass the output buffering system.
2. **Database Abstraction:** The framework uses an old Active Record style pattern (Query Builder). When modifying drivers in `system/database/drivers/`, never introduce raw string concatenation for SQL queries; always utilize the established escape routines (`escape_str()`, `escape_identifiers()`).
3. **Supply Chain:** There are 4 binary anomalies identified by X-Ray (likely test database fixtures like `.sqlite` files). Do not modify or attempt to scan these binary blobs.

## 5. Environmental Tooling (The Oracle)
Do not guess framework lifecycle hooks, hallucinate namespace resolutions, or rely on modern PHP knowledge to determine blast radius within this highly legacy, coupled framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
