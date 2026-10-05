---
description: "You are operating within `cpython`, the reference implementation of the Python programming language. The repository is a massive, highly optimized C..."
---
# AGENTS.md: cpython Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cpython`, the reference implementation of the Python programming language. The repository is a massive, highly optimized C codebase (64.1%) heavily augmented by Python (15.3%) for the standard library, testing, and build orchestration.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.395. The network topology demonstrates moderate Modularity (0.5568) but significant negative assortativity (-0.2153). This reveals a "hub-and-spoke" architecture where highly isolated C extension modules (`Modules/`) and Python standard library components rely exclusively on massive, highly connected "God Node" headers (like `Include/Python.h` and `Include/internal/pycore_*.h`). 
* **Core Rule:** Do NOT attempt to decouple the core C-API or introduce external dependencies. The architecture requires flat, highly optimized C code that strictly adheres to the established CPython API (both public and internal `pycore_` headers).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core execution functions (`tok_get_normal_mode` in `Parser/lexer/lexer.c`, `doProlog` in `Modules/expat/xmlparse.c`, and macro parsers in `Modules/clinic/`) operate at extreme recursive time complexities (O(2^N) or O(N^6) in static analysis) due to deep tokenization and state machine traversal. You MUST NOT introduce additional nested loops, dynamic memory allocations (`malloc`), or O(N^2+) complexity in the critical bytecode execution paths (`Python/ceval.c`), the parser, or the garbage collector.
* **Orchestrator Fragility:** Central orchestrators like `Python.h` (94 outbound dependencies) and `Python/pylifecycle.c` (51 outbound dependencies) dictate the entire interpreter lifecycle. Modifying the interpreter initialization, finalization, or thread-state management requires immediate, comprehensive verification against the entire C-API test suite.
* **Avoid Dead Code Pruning:** Files like `Makefile.pre.in` (146 orphaned functions) and internal headers (`Include/cpython/pyatomic_gcc.h`) contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. CPython utilizes extensive `#ifdef` platform-specific implementations and macros that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream cross-compilation testing (e.g., buildbots) before modifying the structural signatures, garbage collection logic, or public APIs of these files:
* `Objects/bytesobject.c` (Highest Cumulative Risk: 655.27, 100% Injection Surface Exposure due to format string parsing)
* `Python/ceval.c` & `Python/bytecodes.c` (Extreme Volatility Hotspots: Near 100% Churn, highly fragile interpreter loop)
* `Modules/expat/xmlparse.c` (Massive Structural Mass: 11,720.84, Key Person Silo - 100% isolated ownership by Stan Ulbrych)
* `Include/Python.h` (Severe Blind Bottleneck - 312 inbound connections flying blind with 92.7% Doc Risk)
* `Include/pyerrors.h` (House of Cards - Deeply embedded with 97.9% Error Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations inside `Include/internal/` headers (e.g., `pycore_gc.h`, `pycore_dict.h`) and core modules like `_bz2module.c` rely heavily on raw memory manipulation and pointer arithmetic (10% Exposure). Any `PyMem_Malloc`, buffer parsing, or struct casting here must be rigorously scrutinized for out-of-bounds access, Use-After-Free (UAF), or segmentation faults.
2. **Exploit Generation Surface:** Code generation tools (`Tools/clinic/libclinic/dsl_parser.py`) and JIT optimizers (`Tools/jit/_optimizers.py`) possess a 100% Exposure score for Exploit Generation. Ensure that any modifications to AST generation or bytecode compilation strictly validate inputs to prevent arbitrary code execution during the build process.
3. **Weaponizable Injection Vectors:** Modules handling untrusted inputs (`Modules/mmapmodule.c`, `Objects/bytesobject.c`) have high injection surface exposure. You must ensure strict bounds checking and utilize the secure C-API variants for parsing formats (e.g., `PyArg_ParseTuple`).
4. **Hardcoded Payload Artifacts:** `Lib/test/certdata/*.pem` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic fixtures required for testing the `ssl` module.

## 5. Environmental Tooling (The Oracle)
Do not guess C-API refcounting semantics (`Py_INCREF`/`Py_DECREF`), hallucinate GIL (Global Interpreter Lock) states, or rely on generalized C knowledge to determine blast radius within this 600k+ LOC runtime. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
