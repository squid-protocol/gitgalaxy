---
description: "You are operating within `black`, the uncompromising Python code formatter, primarily composed of Python (95.1%)."
---
# AGENTS.md: black Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `black`, the uncompromising Python code formatter, primarily composed of Python (95.1%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.384. The architecture revolves around parsing Python source code into an Abstract Syntax Tree (AST), manipulating nodes, and re-rendering them. Modularity is relatively high (0.66), but the internal structure is tightly coupled around a few core AST manipulation modules. Do not attempt to introduce generic asynchronous design patterns or decouple the rigid, deeply recursive parsing pipelines.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core AST handlers (`stringify_node` in `src/black/comments.py`, `tokenize` in `src/blib2to3/pgen2/tokenize.py`, and `_recursive_matches` in `src/blib2to3/pytree.py`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying node visits, line generation (`linegen.py`), or bracket matching.
* **Orchestrator Fragility:** Central orchestrators like `src/black/__init__.py` (38 outbound dependencies) and `tests/test_black.py` (36 outbound dependencies) are highly fragile. Any changes to formatting rules, token definitions, or core settings within these files require immediate, comprehensive verification of downstream integration tests.
* **Avoid Dead Code Pruning:** The testing and node structures (`tests/test_black.py` with 89 orphaned functions, `src/black/nodes.py` with 33) contain high volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files. The test suite and dynamic node visitor patterns rely on implicit execution that static analysis misinterprets as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, node rendering rules, or public APIs of these files:
* `tests/test_black.py` (Highest Cumulative Risk: 631.83, Extreme Volatility Hotspot: 100% Churn)
* `src/black/lines.py` (Massive Structural Mass: 2001.8, handles core string logic like `_is_triple_quoted_string`)
* `src/black/trans.py` (High Cumulative Risk, 100% Exploit Generation Surface due to raw AST transformations)
* `src/black/brackets.py` (Key Person Silo - 100% isolated ownership by Hugo van Kemenade)
* `src/blib2to3/pgen2/conv.py` (Key Person Silo - 100% isolated ownership by Gordon Messmer)
* `src/blib2to3/pgen2/tokenize.py` (Severe Blind Bottleneck - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH AST CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `src/black/trans.py`, `tests/test_black.py`, and `src/blib2to3/pytree.py` possess significant Exploit Generation Surface scores. Because this codebase parses, modifies, and outputs raw Python code, you MUST ensure strict input sanitization. Any logic flaw here could result in the formatter outputting syntactically invalid or semantically altered (and potentially malicious) code.
2. **Weaponizable Injection Vectors:** `tests/test_black.py` processes raw string inputs. Ensure that test cases or fixtures do not inadvertently introduce code execution pathways during the test suite run.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python knowledge to determine blast radius within this highly recursive AST parser. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
