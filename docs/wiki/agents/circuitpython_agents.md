---
description: "You are operating within `circuitpython`, an implementation of Python designed to run on microcontrollers. The repository is predominantly composed of..."
---
# AGENTS.md: circuitpython Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `circuitpython`, an implementation of Python designed to run on microcontrollers. The repository is predominantly composed of C (67.5%) for the core interpreter and hardware abstraction layer (HAL), accompanied by Python (20.3%) for testing, tooling, and standard library modules.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.671. The network topology demonstrates relatively clean micro-boundaries (Modularity 0.5582) typical of a port-based hardware abstraction architecture. However, it exhibits significant negative assortativity (-0.255), indicating a "hub-and-spoke" model where isolated ports rely heavily on massive, highly connected "hub" nodes (the core `py/` interpreter headers). Do not attempt to introduce modern decoupled service abstractions; the system must remain a highly integrated, memory-constrained monolith.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core memory management and packet processing (`gc_sweep_free_blocks` in `py/gc.c`, `process_evt_pkt` in BLE HCI, and `mp_obj_str_format_helper` in `py/objstr.c`) operate at high recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce additional nested iterations, unpredictable heap allocations, or O(N^2+) complexity in the garbage collector or interrupt-driven hardware drivers.
* **Orchestrator Fragility:** Central orchestrators such as `ports/stm/hal_conf/stm32h7xx_hal_conf.h` (60 outbound dependencies) and `ports/espressif/supervisor/port.c` are highly fragile. Any changes to hardware definitions, clock configurations, or macros within these files require immediate verification across the specific board port targets.
* **Avoid Dead Code Pruning:** Files like `py/asmrv32.h` (64 orphaned functions) and `py/asmx86.c` contain high volumes of logic flagged as dead code. DO NOT autonomously attempt to prune, format, or clean up these files. CircuitPython utilizes extensive conditional compilation (`#ifdef`) and architecture-specific assembly emission that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream hardware testing before modifying the structural signatures, garbage collection logic, or public APIs of these files:
* `py/objstr.c` (Massive Structural Mass: 5525.88, Key Person Silo - 100% isolated ownership by Dan Halbert)
* `py/compile.c` (Key Person Silo - 100% isolated ownership by Scott Shawcroft, high cognitive load)
* `py/parse.c` (Key Person Silo - 100% isolated ownership by Scott Shawcroft)
* `py/gc.c` (Contagious Mutation Risk - highly volatile state handling garbage collection)
* `py/obj.h` & `shared-bindings/board/__init__.h` (Severe Blind Bottlenecks - Massive blast radius with severe documentation gaps. Flying blind.)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations inside the virtual file system (`extmod/vfs.c`, `extmod/vfs_fat.c`, `extmod/vfs_posix.c`) rely heavily on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications to block reading, inode handling, or `cstack` logic must be rigorously bounded to prevent buffer overflows or memory corruption.
2. **Hardcoded Payload Artifacts:** `ports/nordic/espruino_dfu_private_key.pem` tripped hardcoded payload signatures. DO NOT flag this as a leaked secret; it is an explicit cryptographic fixture required for compiling DFU updates on the Nordic port.
3. **Contagious Runtime Mutability:** Files like `py/runtime.h` and `py/misc.h` act as structural bridges with highly volatile, mutating state. State changes here will cause unpredictable side-effects for all downstream hardware modules.

## 5. Environmental Tooling (The Oracle)
Do not guess hardware offsets, hallucinate C macro behaviors, or rely on generalized Python knowledge to determine blast radius within this 340k+ LOC runtime. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
