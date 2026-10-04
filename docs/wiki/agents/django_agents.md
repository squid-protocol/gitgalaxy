---
description: "You are operating within `django`, a massive, high-level Python web framework. The repository is heavily dominated by Python (82.9%), supported by HTML..."
---
# AGENTS.md: django Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `django`, a massive, high-level Python web framework. The repository is heavily dominated by Python (82.9%), supported by HTML templates (10.8%) and static assets for the admin interface.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.977. The network topology demonstrates high Modularity (0.6239) but negative Assortativity (-0.1197). This indicates a strict "hub-and-spoke" architecture where well-defined subsystems (e.g., ORM, Forms, Admin, GIS) are cleanly separated but rely entirely on a few massive, highly centralized God Nodes (like the model base classes and query compilers).
* **Core Rule:** Maintain strict boundaries between subsystems. Do NOT introduce cross-coupling between decoupled modules (e.g., do not leak `django.contrib.admin` logic into `django.db.models`). Adhere strictly to the established metaprogramming and class-based view patterns.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core application registry loading (`populate` in `django/apps/registry.py`), form rendering (`fields` in `django/contrib/admin/helpers.py`), and admin UI logic operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded recursive loops, heavy synchronous blocking operations, or N+1 queries within the ORM compiler (`django/db/models/sql/compiler.py`) or app initialization pathways.
* **Orchestrator Fragility:** Central orchestrators such as `django/contrib/admin/options.py` (40 outbound dependencies) and extensive test suites (`tests/admin_views/tests.py`, `tests/cache/tests.py`) are highly fragile. Modifying the ModelAdmin base classes or caching backends requires immediate, comprehensive verification across the entire Django test suite.
* **Avoid Dead Code Pruning:** Test files (`tests/admin_views/tests.py` with 197 orphaned functions, `tests/migrations/test_autodetector.py`) and certain internal modules contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Django utilizes extensive dynamic dispatch, reflection, and signal handling that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, metaprogramming metaclasses, or public APIs of these files:
* `django/db/models/query.py` & `django/db/models/base.py` (Massive Structural Mass and Cumulative Risk. These files dictate the entire Object-Relational Mapping (ORM) logic).
* `django/core/cache/backends/base.py` (High Cognitive Load and Logic Bomb risk. Core abstraction for all cache interactions).
* `django/forms/fields.py` (Key Person Silo - 100% isolated ownership by Natalia).
* `django/db/models/options.py` (Key Person Silo - 100% isolated ownership by Senthil Kumar).
* `django/core/management/commands/makemessages.py` & `tests/i18n/test_extraction.py` (Key Person Silos - 100% isolated ownership by michalpokusa).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH ASGI AND ADMIN CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Core request handlers and validators (`django/core/handlers/asgi.py`, `django/core/validators.py`, `django/contrib/admin/options.py`) possess 100% Exposure for Exploit Generation. Because Django handles raw HTTP/ASGI requests and user-submitted data, you MUST ensure strict input validation, adherence to CSRF/XSS protections, and secure asynchronous scope handling.
2. **Database Compilers:** When modifying `django/db/models/sql/query.py` or GIS extensions (`django/contrib/gis/geos/geometry.py`), never introduce raw string concatenation for SQL queries; always utilize the established parameterization and expression APIs to prevent SQL Injection.
3. **Supply Chain:** There are 102 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external packages in setup or requirement files without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess ORM compilation stages, hallucinate Django signal bindings, or rely on generalized Python knowledge to determine blast radius within this 360k+ LOC framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
