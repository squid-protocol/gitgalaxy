---
description: "You are operating within `micropython`, a lean and efficient implementation of the Python 3 programming language optimized to run on microcontrollers..."
---
# AGENTS.md: micropython Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `micropython`, a lean and efficient implementation of the Python 3 programming language optimized to run on microcontrollers and in constrained environments. The codebase is heavily bifurcated between C (41.6%) for the core runtime, memory management, and hardware ports, and Python (35.5%) for standard libraries and tests.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.936. The network topology demonstrates a Hub-and-Spoke model with high Modularity (0.5699) but negative Assortativity (-0.1231). This signifies a highly centralized architecture where isolated hardware ports (e.g., `ports/stm32/`, `ports/esp32/`) and extension modules (`extmod/`) connect exclusively through a massive, load-bearing central C-runtime core (`py/`).
* **Core Rule:** Maintain strict adherence to MicroPython's constrained memory paradigms and Garbage Collection (GC) boundaries. Do NOT introduce standard glibc allocations (`malloc`/`free`) where MicroPython's GC allocator (`gc_alloc`/`m_new`) is expected. Respect the hardware abstraction layer (HAL) boundaries across different microcontroller ports.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core garbage collection (`gc_sweep_free_blocks` in `py/gc.c`), object typing (`mp_obj_class_lookup`), and networking event handlers (`_SlDrvNetAppEventHandler`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep memory traversal and interrupt handling. You MUST NOT introduce unbounded loops, deep recursion, or heavy synchronous blocking operations into the core runtime or interrupt service routines (ISRs).
* **Orchestrator Fragility:** Hardware configuration orchestrators (e.g., `ports/stm32/boards/stm32u5xx_hal_conf_base.h` with 64 outbound dependencies) and central build scripts (`tools/ci.sh` with 93.75% Churn and 99.7% Cognitive Load) are extremely fragile. Modifying these configurations carries a high risk of breaking cross-platform builds.
* **Avoid Dead Code Pruning:** Files like `py/asmrv32.h` (74 orphaned functions), `ports/cc3200/hal/i2c.c` (50 orphaned functions), and `py/asmx86.c` contain logic flagged as "dead code." DO NOT autonomously attempt to prune or format these files. They contain hardware-specific bindings, assembly emission logic, and conditional macros that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and rigorous multi-architecture testing (e.g., across STM32, ESP32, RP2040) before modifying the structural signatures, C structs, or public APIs of these files:
* `py/runtime.h` & `py/obj.h` (Massive Structural Mass and Severe Blind Bottlenecks. These headers define the absolute reality of the Python object model and runtime environment).
* `tools/ci.sh` (Highest Volatility Hotspot: 93.7% Churn. The central CI orchestrator is a fragile choke point).
* `py/emitnative.c` (Key Person Silo - 100% isolated ownership by Alessandro Gatti. Controls native machine code emission).
* `extmod/btstack/modbluetooth_btstack.c` (Key Person Silo - 100% isolated ownership by Andrew Leech. Central Bluetooth stack integration).
* `py/mpz.c` (Key Person Silo - 100% isolated ownership by Jeff Epler. Core multi-precision integer math).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the hardware drivers (`drivers/cc3100/src/driver.c`) and low-level extension modules (`extmod/modselect.c`, `extmod/modlwip.c`) inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications here must be mathematically proven to prevent Buffer Overflows, Use-After-Free (UAF), or heap corruption within the constrained MicroPython GC heap.
2. **Exploit Generation Surface:** CI/CD and build tooling scripts (`tests/run-tests.py`, `tools/boardgen.py`, `tools/mpremote/mpremote/transport.py`) possess 100% Exposure for Exploit Generation. Ensure any modifications to test runners or remote board execution tooling strictly sanitize untrusted inputs and file paths to prevent arbitrary command injection on the host machine.
3. **Supply Chain / External Dependencies:** The repository contains 179 unknown dependencies bypassing the Zero-Trust whitelist, primarily within `lib/` and `extmod/`. Do not update or alter third-party submodules (like `mbedtls`, `lwip`, `btstack`) without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess garbage collection implications, hallucinate QSTR (Quality String) generation paths, or rely on generalized C/Python knowledge to determine blast radius within this 360k+ LOC embedded runtime. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
