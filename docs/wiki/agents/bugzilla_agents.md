---
description: "You are operating within `bugzilla`, a legacy, monolithic defect-tracking system. The repository is heavily reliant on Perl (41.6%) for backend logic..."
---
# AGENTS.md: bugzilla Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bugzilla`, a legacy, monolithic defect-tracking system. The repository is heavily reliant on Perl (41.6%) for backend logic and database abstraction, tightly coupled with HTML templates (44.0%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits an extreme Architectural Drift Z-Score of 8.01. The network topology demonstrates moderate Modularity (0.4919) but negative Assortativity (-0.2657), indicating a fragile "hub-and-spoke" model where complex business logic modules (the hubs) dictate the flow for peripheral scripts. Do NOT attempt to introduce modern MVC or async paradigms; the system relies on synchronous CGI execution and monolithic module inclusion.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core database abstractions and authentication routines (`bz_alter_column` in `Bugzilla/DB.pm`, `create_or_update_user` in `Bugzilla/Auth/Verify.pm`) operate at high O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or recursive SQL generation inside the DB schema modules.
* **Orchestrator Fragility:** Central orchestrators such as `Bugzilla.pm` (31 outbound dependencies) and `Bugzilla/User.pm` (31 outbound dependencies) are highly fragile. Any changes to data contracts, global state, or permission checks within these files require immediate verification against downstream CGI scripts.
* **Avoid Dead Code Pruning:** The extensions and Javascript utility files (`extensions/Example/Extension.pm` with 50 orphans, `js/field.js` with 18 orphans) contain logic that static analysis tools flag as dead code. DO NOT autonomously attempt to prune, format, or clean up these files. Bugzilla relies heavily on dynamic hook execution and template-driven JS injection.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as "House of Cards" (deeply embedded with high error exposure). 

**MANDATORY RULE:** You require explicit human permission and downstream integration verification before modifying the structural signatures, DB queries, or public APIs of these files:
* `Bugzilla/DB.pm` & `Bugzilla/DB/Schema.pm` (The core Database Abstraction Layer - modifications here can corrupt entire instances).
* `Bugzilla/Bug.pm` (Massive Structural Mass: 12617.28, handles all core ticket logic).
* `Bugzilla/WebService/Server/REST/Resources/Bugzilla.pm` (Severe Blind Bottleneck - 100% Documentation Risk with 81 inbound connections).
* `email_in.pl` (High I/O latency risk and deep regex complexity for parsing incoming mail).
* `Bugzilla/Search.pm` (Generates dynamic SQL; extremely high cognitive load and DB complexity).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SQL/HTML CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `Bugzilla/CGI.pm`, `Bugzilla/Attachment.pm`, and `Bugzilla/Component.pm` possess a 100% Exposure score for Exploit Generation Surface. Because Bugzilla inherently handles untrusted user input, file uploads, and CGI parameters, you MUST ensure strict input sanitization using `Bugzilla::Util::html_quote` or `trick_taint` to prevent Cross-Site Scripting (XSS) and SQL Injection (SQLi).
2. **Weaponizable Injection Vectors:** `Bugzilla/Extension.pm` possesses a 100% Exposure for Injection Vectors. Any code managing extension loading or hook execution must rigidly validate file paths and module names to prevent arbitrary code execution.
3. **Supply Chain:** There are 10 binary anomalies identified by X-Ray. Do not modify or attempt to execute unrecognized binary blobs or `.tar.gz` fixtures within the `t/` or `extensions/` directories.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on modern Perl knowledge to determine blast radius within this 116k+ LOC legacy codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
