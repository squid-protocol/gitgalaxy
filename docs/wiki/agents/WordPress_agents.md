---
description: "You are operating within `WordPress`, the highly mature, massive (960k+ LOC) PHP-based content management system. The codebase is heavily dominated by..."
---
# AGENTS.md: WordPress Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `WordPress`, the highly mature, massive (960k+ LOC) PHP-based content management system. The codebase is heavily dominated by PHP (78.3%), supported by JavaScript (11.7%) and CSS (5.8%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.185. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a quintessential "hub-and-spoke" monolith where an immense ecosystem of plugins and themes relies entirely on a dense core of globally accessible God Nodes and procedural APIs.
* **Core Rule:** Maintain absolute adherence to the WordPress Hook (Action/Filter) API. Do NOT attempt to decouple foundational orchestrators, convert pervasive global functions into strict OOP dependency injection, or bypass the `wp-includes/plugin.php` event loop. The architecture relies on dynamic dispatch and global state manipulation.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core initialization and meta-retrieval functions (`wp_cache_init` in `wp-includes/cache.php`, `wp_script_is` in `wp-includes/class-wp-dependencies.php`, `get_post_meta`, `get_post_custom`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded recursive loops, heavy synchronous database queries without caching, or excessive object allocations on the critical path of the front-end rendering or admin initialization loops.
* **Orchestrator Fragility:** Central orchestrators such as `wp-includes/functions.php` (272 outbound dependencies), `wp-includes/load.php` (176 outbound), and `wp-includes/plugin.php` (139 outbound) are highly fragile. Modifying the bootstrap sequence, hook registration, or core utility functions requires immediate, comprehensive verification via the PHPUnit test suite.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `wp-includes/functions.php` with 106 orphans, `wp-includes/pluggable.php` with 86). DO NOT autonomously attempt to prune, format, or clean up these files. WordPress relies entirely on string-based dynamic dispatch (`call_user_func`), template tags, and hook callbacks that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent severe single-points-of-failure. 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, hook executions, or public APIs of these files:
* `wp-includes/plugin.php` (Highest Cumulative Risk: 655.43. The absolute core of the extensibility engine).
* `wp-includes/functions.php` (Massive Structural Mass: 17293.7. The central utility hub with extreme Data Gravity).
* `wp-includes/post.php` & `wp-includes/formatting.php` (Key Person Silos - overwhelmingly owned by Aaron Jorbin and Sergey Biryukov. Critical data modeling and sanitization boundaries).
* `wp-includes/class-wp-query.php` (Core database resolution engine; extreme cognitive load and complexity).
* `wp-includes/pluggable.php` (Functions intended to be overridden by plugins; highly fragile).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CRITICAL INJECTION/EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation & Weaponizable Injection:** Files managing database access, formatting, and extensibility (`wp-includes/wp-db.php`, `wp-includes/formatting.php`, `wp-includes/kses.php`, `wp-includes/functions.php`) possess 100% Exposure for Exploit Generation and Weaponizable Injection. Because WordPress serves untrusted HTTP inputs and executes dynamic queries, you MUST ensure strict data sanitization. Use `wpdb->prepare()` for all SQL queries. Use `esc_html()`, `esc_attr()`, `esc_url()`, and `wp_kses()` for all outputs. Failure to do so will introduce SQLi or XSS vulnerabilities.
2. **Obfuscation & Evasion Surface:** Legacy XML-RPC logic (`wp-includes/class-wp-xmlrpc-server.php`) and core DB classes exhibit obfuscation signatures, likely due to dynamic query building and raw payload parsing. Tread carefully to avoid breaking backward compatibility with external integrations.
3. **Supply Chain:** There are 111 binary anomalies identified by X-Ray (likely images, test fixtures, or pre-compiled assets). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess hook firing sequences, hallucinate `WP_Query` parameter parsing mechanics, or rely on generalized PHP knowledge to determine blast radius within this 960k+ LOC monolith. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
