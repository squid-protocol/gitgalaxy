---
description: "You are operating within `iwubi`, a compact, Python-based input method engine (likely for IBus). The repository is extremely concentrated, consisting..."
---
# AGENTS.md: iwubi Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `iwubi`, a compact, Python-based input method engine (likely for IBus). The repository is extremely concentrated, consisting almost entirely of Python (50.0% of file count, but 100% of execution logic), supplemented by build tooling (Makefile, YAML, XML).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.337. The network topology demonstrates completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly centralized, single-point-of-failure architecture where nearly all execution logic is packed into a single monolithic orchestrator (`iwubi.py`).
* **Core Rule:** Do NOT attempt to enforce heavy object-oriented decoupling or over-engineer the file structure. The system is designed as a focused, lightweight script wrapper around an SQLite database. Keep logic localized but clean.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core keystroke processing and navigation functions (`_process_key_event`, `find_characters`, `page_up`, `page_down`, `cursor_up`) operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis). This is a severe risk for an input method, where latency must be near-zero. You MUST NOT introduce unbounded loops, heavy I/O operations, or unoptimized database queries inside the hot path of the `_process_key_event` lifecycle.
* **Orchestrator Fragility:** `iwubi.py` acts as the absolute master orchestrator (pulling in 9 outbound dependencies). Any modifications to the event loop, state management, or key bindings require extreme caution, as failures here crash the user's input mechanism.
* **Avoid Dead Code Pruning:** The repository contains a few functions flagged as "orphaned" (10 in `iwubi.py`). DO NOT autonomously attempt to prune these files. They likely represent IBus API callback handlers or dynamic GTK event triggers that bypass static dependency mapping.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as severe "House of Cards" bottlenecks.

**MANDATORY RULE:** You require explicit human permission and local IBus environment testing before modifying the structural signatures, I/O handling, or state logic of these files:
* `iwubi.py` (Highest Cumulative Risk: 458.58, Massive Structural Mass. Controls the entire application state and keystroke interception).
* `logconfig.py` (Severe Blind Bottleneck - High blast radius flying blind with nearly 95% Documentation Risk. A failure here breaks the logging chain for the entire engine).
* `insert_pinyin_to_db.py` (Handles the static SQLite database population; do not alter the schema without understanding the downstream read constraints in `iwubi.py`).
* `Makefile` (High Tech Debt: 99.8%. Controls the fragile installation/uninstallation routines across Linux file systems).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Input Sanitization & Injection:** While no explicit SQL injection vectors were flagged by XGBoost, the application relies on an SQLite backend (`find_characters` in `iwubi.py`). You MUST ensure that any modifications to database queries strictly utilize parameterized SQL statements (`?` placeholders) and never use string formatting/interpolation with user input.
2. **System Permissions:** The `Makefile` manages system-level installation. Do not introduce arbitrary shell commands (`system()`, `os.popen()`) or escalate privileges unnecessarily within the setup scripts.

## 5. Environmental Tooling (The Oracle)
Do not guess GTK/IBus main loop behaviors, hallucinate SQLite schema fields, or rely on generalized Python knowledge to determine blast radius within this specialized input method. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
