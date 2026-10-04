---
description: "You are operating within `angr`, a heavily coupled binary analysis and symbolic execution framework primarily composed of Python (78.7%)."
---
# AGENTS.md: angr Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `angr`, a heavily coupled binary analysis and symbolic execution framework primarily composed of Python (78.7%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.573. The network topology demonstrates negative assortativity (-0.4823), meaning the architecture relies heavily on fragile, highly connected hub nodes (single points of failure) rather than a distributed, resilient core. Do not attempt to introduce decoupled or asynchronous micro-patterns into the core analyses, constraint solving, or control-flow graph (CFG) generation pipelines.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core decompilation, AIL (Angr Intermediate Language) conversion, and condition processing methods (`decompile` in `angr/__main__.py`, `convert` in `angr/ailment/converter_vex.py`, and `remove_claripy_bool_asts` in `angr/analyses/decompiler/condition_processor.py`) currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the decompiler, block simplifiers, or peephole optimizations.
* **Orchestrator Fragility:** Module initializers and analysis routers such as `angr/analyses/decompiler/peephole_optimizations/__init__.py` (63 outbound dependencies) and `angr/analyses/__init__.py` (52 outbound dependencies) act as highly fragile orchestrators. Any changes to data contracts, analysis registration, or public API surfaces within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Execution engines and analysis files such as `angr/engines/ail/engine_light.py` (99 orphaned functions) and `angr/analyses/purity/engine.py` (60 orphaned functions) contain high volumes of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as the symbolic execution engine relies on dynamic dispatch and reflection to invoke these handlers.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Fish). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, AST resolution logic, or public APIs of these files:
* `angr/analyses/cfg/cfg_base.py` (Highest Cumulative Risk: 618.3, Extreme Churn Hotspot: 97.65%)
* `angr/analyses/cfg/cfg_fast.py` (Extreme Mass: 8079.08, Key Person Silo - 84.6% isolated ownership by Fish)
* `angr/calling_conventions.py` (Extreme Mass: 6291.4, High Verification Risk)
* `angr/storage/file.py` (Key Person Silo - 100% isolated ownership by Fish)
* `angr/concretization_strategies/logging.py` (House of Cards / Blind Bottleneck - 433 inbound connections flying blind)
* `angr/knowledge_plugins/cfg/spilling_cfg.py` (High Volatility and Verification Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT GENERATION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Supply Chain anomalies. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `angr/analyses/decompiler/callsite_maker.py`, `angr/analyses/ddg.py`, and `angr/analyses/cfg/indirect_jump_resolvers/jumptable.py` possess a 100% Exposure score for Exploit Generation Surface due to the nature of analyzing and generating binary exploits/ROP chains. When modifying these, ensure you do not inadvertently break the safety constraints of the analysis environment itself.
2. **Weaponizable Injection Vectors:** `angr/engines/light/engine.py` and several libc test procedures involve untrusted data flowing into dynamic execution contexts. Ensure strict input sanitization if modifying how angr handles user-provided binaries or lifting procedures.
3. **Raw Memory Manipulation:** `native/angr/src/automaton/state.rs` contains raw memory manipulation. Any `unsafe` blocks, pointer arithmetic, or buffer logic here must be heavily scrutinized for out-of-bounds access.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python knowledge to determine blast radius in this 230k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
