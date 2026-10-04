---
description: "You are operating within `cython`, a highly complex compiler that translates Python-like code into highly optimized C/C++ extensions. The repository is..."
---
# AGENTS.md: cython Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cython`, a highly complex compiler that translates Python-like code into highly optimized C/C++ extensions. The repository is predominantly Python (93.8%), which drives the entire parsing, abstract syntax tree (AST) generation, optimization, and code-emission pipelines.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 6.372. The network topology demonstrates moderate Modularity (0.6006) but negative Assortativity (-0.2822). This indicates a "hub-and-spoke" architecture where specific orchestration files (like `cython.py` and `runtests.py`) act as central hubs, heavily coupled to isolated compiler modules. Do NOT attempt to decouple the core AST phases (`Parsing.py`, `ExprNodes.py`, `ModuleNode.py`); they are intentionally tightly bound by the visitor pattern required for compiler passes.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core AST transformation and node generation functions (`_check_valid_cython_module` in `ParseTreeTransforms.py`, `generate_function_definitions` in `Nodes.py`) operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis) due to deep tree traversal. You MUST NOT introduce additional nested recursion, redundant AST walks, or O(N^2+) complexity in the critical path of the compiler pipeline.
* **Orchestrator Fragility:** Central orchestrators such as `runtests.py` (66 outbound dependencies) and `Cython/Compiler/Main.py` are highly fragile. Any changes to compiler flags, pipeline initialization, or test bootstrapping require immediate, comprehensive verification via the massive integrated test suite.
* **Avoid Dead Code Pruning:** Files like `Cython/Compiler/Optimize.py` (79 orphaned functions) and various `pyx` test files contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Cython relies heavily on dynamic dispatch (visitor patterns on AST nodes) and conditionally generated code that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and extensive compilation verification against real-world downstream projects (e.g., NumPy, Pandas) before modifying the structural signatures, tree transformations, or public APIs of these files:
* `Cython/Compiler/ExprNodes.py` & `Nodes.py` (Massive Structural Mass and core AST definitions; any change here cascades globally).
* `Cython/Compiler/Symtab.py` (Extreme Volatility Hotspot: 71.2% Churn, 67.2% Tech Debt. Handles all variable/type scoping).
* `Cython/Compiler/ParseTreeTransforms.py` (High Volatility and 65.4% Tech Debt. Critical path for AST optimization).
* `cython.py` (Severe Blind Bottleneck - 161 inbound connections with high Doc Risk).
* `Cython/Debugger/libpython.py` (Key Person Silo - 100% isolated ownership by Matti Picus).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT/INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Debugging scripts (`Cython/Debugger/libpython.py`) and test orchestrators (`runtests.py`) possess a 100% Exposure score for Exploit Generation. Because Cython interfaces directly with GDB and executes compiled C extensions, you MUST ensure strict input sanitization and avoid arbitrary `eval()` or `subprocess` execution with untrusted paths.
2. **Obfuscation & Evasion Surface:** The Lexicon and parser definitions (`Cython/Compiler/Lexicon.py`) handle raw string manipulation and encoding/escaping. Be extremely careful modifying regex patterns or string literal handlers (`tests/run/strliterals.pyx`), as failures here can lead to generated C code that is uncompilable or contains injection vulnerabilities.
3. **Raw Memory Manipulation:** Core C utility wrappers (`Cython/Utility/Buffer.c`, `Cython/Utility/ObjectHandling.c`) handle raw memory manipulation and CPython C-API interactions (10% Exposure). Any modifications to the generated C code templates must be rigorously scrutinized for reference counting leaks (`Py_INCREF`/`Py_DECREF`), buffer overflows, or segmentation faults.

## 5. Environmental Tooling (The Oracle)
Do not guess AST node behaviors, hallucinate C-API macro mappings, or rely on generalized Python knowledge to determine blast radius within this specialized compiler. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
