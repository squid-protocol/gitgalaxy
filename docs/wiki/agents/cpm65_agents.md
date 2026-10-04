---
description: "You are operating within `cpm65`, an operating system implementation of CP/M designed specifically for 6502 microprocessors. The codebase is heavily..."
---
# AGENTS.md: cpm65 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cpm65`, an operating system implementation of CP/M designed specifically for 6502 microprocessors. The codebase is heavily dominated by 6502 Assembly (54.5%) and C (16.2%), complemented by Python build and configuration scripts.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species with a high Architectural Drift Z-Score of 7.766. The network topology demonstrates a highly modular (0.7643) and positively assortative (0.2243) core. This indicates a resilient, well-segmented architecture where individual hardware architectures (e.g., `arch/apple2e`, `arch/atari800`, `arch/kim-1`) are kept strictly isolated but rely on a strong, central core of shared includes and emulators. 
* **Core Rule:** Do NOT attempt to abstract away hardware-specific boundaries or introduce high-level design patterns (like OOP or dynamic dispatch) into the Assembly or C components. The system operates under severe memory and CPU constraints inherent to the 6502 architecture.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core parsing and hardware polling routines (`consumeExpressionNode` in `apps/asm.c`, `disk_status` in `format.S`, `banner_wait` in `nano6502.S`) operate at O(2^N) recursive time complexities in static analysis. You MUST NOT introduce additional nested loops or deep recursion in the assembler, terminal emulators, or BIOS/BDOS logic.
* **Orchestrator Fragility:** Central orchestrators like `tools/cpmemu/biosbdos.c` (12 outbound dependencies) and `tools/cpmemu/fileio.c` act as the primary emulation layers for the host environment. Modifying file I/O or BDOS syscall mapping here requires comprehensive verification against the hardware test suites (`mame-test.lua` scripts).
* **Avoid Dead Code Pruning:** Disassemblers and architecture-specific routines (e.g., `apps/objdump.c`, `src/arch/kim-1/boot/bootsd.S`) contain functions flagged as "orphaned." DO NOT autonomously attempt to prune or clean up these files. This logic relies on jump tables, hardware interrupts, or conditional compilation (`#ifdef`) that static analysis misinterprets as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream emulator testing (e.g., MAME) before modifying the structural signatures, hardware registers, or public APIs of these files:
* `apps/asm.c` (Massive Structural Mass: 2218.88, Key Person Silo - 100% isolated ownership by David Given. The core assembler logic).
* `include/cpm65.inc` (Severe Blind Bottleneck - Highest Blast Radius with 100% Documentation Risk. Core OS definitions).
* `config.py` (Severe Blind Bottleneck - 12 inbound connections orchestrating the build environment).
* `apps/drivers.inc` (House of Cards - High Error Risk and deep coupling).
* `src/ccp.S` and `src/bdos/filesystem.S` (Key Person Silos - 100% isolated ownership by David Given. Core OS subsystems).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files in the emulator layer (`tools/cpmemu/biosbdos.c`) and low-level tools (`tools/mkimd.c`, `apps/sys.c`) handle raw memory manipulation. Ensure any modifications to buffer parsing, disk image creation, or emulator state strictly check boundaries to prevent segmentation faults on the host system.
2. **Build and Fuzzing Tools:** Scripts like `scripts/get-roms.sh` and various `mame-test.lua` harnesses execute external dependencies and emulators. Do not modify these to fetch unverified third-party binaries or alter the deterministic nature of the build pipeline.

## 5. Environmental Tooling (The Oracle)
Do not guess 6502 opcodes, hallucinate BDOS call numbers, or rely on generalized C/Assembly knowledge to determine blast radius within this highly specialized OS architecture. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
