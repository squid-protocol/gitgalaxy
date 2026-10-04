---
description: "You are operating within `cakephp`, a mature, full-stack PHP web framework. The repository is predominantly PHP (94.1%) with heavy use of traits for..."
---
# AGENTS.md: cakephp Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cakephp`, a mature, full-stack PHP web framework. The repository is predominantly PHP (94.1%) with heavy use of traits for horizontal code reuse.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits an extreme Architectural Drift Z-Score of 10.767. The network topology demonstrates a Hub-and-Spoke model with high Modularity (0.6285) but negative Assortativity (-0.2337). This indicates that while components (e.g., ORM, Http, Console) are well-separated, they rely heavily on central trait hubs (e.g., `InstanceConfigTrait.php`, `LocatorAwareTrait.php`) and massive orchestrators (`Table.php`, `Controller.php`). 
* **Core Rule:** Strictly adhere to the framework's existing design patterns. Do NOT attempt to replace trait-based composition with deep inheritance hierarchies or force external architectural patterns (like pure DDD or CQRS) onto the active record/ORM implementation.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core collection iterators (`FilterIterator.php`, `SortIterator.php`) and database schema parsers operate at O(2^N) recursive time complexities in static analysis due to deep object graph traversals. You MUST NOT introduce additional nested loops, reflection-heavy operations, or O(N^2+) complexity when modifying the ORM, Query Builders, or Collection pipelines.
* **Orchestrator Fragility:** Central orchestrators such as `src/TestSuite/IntegrationTestTrait.php` (57 outbound dependencies) and `src/ORM/Table.php` (47 outbound dependencies) are highly fragile. Any changes to trait method signatures, event dispatching logic, or query execution within these files require immediate, comprehensive verification of downstream framework components.
* **Avoid Dead Code Pruning:** The framework relies on magic methods, dynamic event listeners (`TableEventsTrait.php`), and reflection (heavily used in PHPStan stubs and Fixtures). DO NOT autonomously attempt to prune, format, or clean up files flagged with "Orphaned Functions" by static analysis, as this will break dynamic framework behaviors.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, SQL generation logic, or public APIs of these files:
* `src/ORM/Query/SelectQuery.php` (Highest Cumulative Risk: 609.08, 100% Logic Bomb & Injection Surface)
* `src/Collection/CollectionTrait.php` (Severe Blind Bottleneck - High Blast Radius with 75% Doc Risk)
* `src/Core/InstanceConfigTrait.php` (House of Cards - Deeply embedded with 56.3% Error Risk)
* `src/ORM/Marshaller.php` (Extreme Volatility Hotspot: 95.18% Churn, highly complex entity hydration)
* `contrib/git-filter-repo` (Massive Python script utilized for repo maintenance; treat as immutable unless explicitly tasked with DevOps maintenance).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SQL/ORM CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface / Injection Vectors:** `src/ORM/Query/SelectQuery.php` and `src/TestSuite/Fixture/SchemaLoader.php` possess 100% Exposure for both Exploit Generation and Injection Vectors. Because CakePHP abstracts raw SQL, you MUST ensure that any modifications to the Query Builder strictly utilize parameterized queries (PDO binding) and established type-casting (`ExpressionTypeCasterTrait`). Do not introduce raw string concatenation in SQL expressions.
2. **Hardcoded Payload Artifacts:** `tests/test_app/config/key.pem` and `key_with_passphrase.pem` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit test fixtures required by the framework's test suite.
3. **Supply Chain:** There are 2 unknown dependencies bypassing the Zero-Trust whitelist and 6 binary anomalies (likely test fixtures or `.sqlite` files). Do not add or bump external dependencies (e.g., in `composer.json`) without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess trait dependencies, hallucinate interface implementations, or rely on generalized PHP knowledge to determine blast radius within this 26k+ LOC framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
