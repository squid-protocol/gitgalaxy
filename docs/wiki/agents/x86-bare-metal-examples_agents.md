---
description: "You are operating within `x86-bare-metal-examples`, a repository dedicated to low-level hardware interaction, bootloaders, and kernel fundamentals..."
---
# AGENTS.md: x86-bare-metal-examples Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `x86-bare-metal-examples`, a repository dedicated to low-level hardware interaction, bootloaders, and kernel fundamentals without relying on an underlying operating system. The codebase is heavily dominated by Assembly (68.4%) and C (5.1%), coordinated by Makefiles and Shell scripts.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.804. The network topology demonstrates a completely flat structure (Modularity: 0.0, Assortativity: 0.0). This indicates a highly localized, independent architecture where files act as standalone examples or specific hardware tests (e.g., `bios_pixel.S`, `rtc.S`) rather than an interconnected software hierarchy.
* **Core Rule:** Maintain absolute respect for bare-metal execution constraints. Do NOT attempt to introduce operating system-level abstractions (like POSIX calls or standard C library allocations) into raw assembly files or low-level C files (`multiboot/osdev/kernel.c`) unless explicitly building a standard library stub. Adhere strictly to x86 real-mode and protected-mode conventions.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core execution paths, such as the `loop` functions in `bios_hello_world.S` and `ps2_keyboard.S`, or `do_e820` in `bios_detect_memory.S`, flag as extreme recursive time complexities (O(2^N) in static analysis). In this context, these are intentional infinite hardware loops (`jmp $` or polling loops) waiting for interrupts or user input. You MUST NOT attempt to "optimize" or unroll these loops; breaking them will cause the CPU to execute garbage memory and triple fault.
* **Orchestrator Fragility:** Central build and execution orchestrators like `configure` and `multiboot/hello-world/Makefile` carry high technical debt and risk exposure. Modifying the toolchain configurations (e.g., cross-compiler flags, linker scripts, or GRUB/QEMU boot commands) requires extreme caution as they dictate the successful creation of bootable images.
* **Avoid Dead Code Pruning:** Files like `bios_detect_memory.S` (6 orphaned functions) and various `Makefile`s contain logic flagged as "dead code" or "design slop." DO NOT autonomously attempt to prune these files. Assembly labels often act as hardware interrupt service routines (ISRs) or memory map targets invoked dynamically by the CPU or BIOS, bypassing static dependency resolution entirely.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess high cumulative risk, represent critical system entry points, or govern hardware synchronization. 

**MANDATORY RULE:** You require explicit human permission and emulator (QEMU/Bochs) verification before modifying the structural signatures, register states, or boot protocols of these files:
* `configure` (Highest Cumulative Risk: 598.36. The central build environment setup script).
* `multiboot/osdev/boot.S` & `multiboot/osdev/kernel.c` (Critical entry points. Define the Multiboot header and early C environment setup).
* `intel-protected/startup.asm` & `nasm/protected_mode_so.asm` (Govern the highly sensitive transition from 16-bit real mode to 32-bit protected mode, including GDT setup).
* `rtc.S` & `serial.S` (High I/O Latency Risks. Direct hardware port manipulation and polling).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within `intel-protected/startup.asm` and memory mapping examples (`bios_detect_memory.S`) natively rely on direct, raw memory manipulation, segment register loading (CS, DS, GS), and hardware I/O port interactions (`in`, `out` instructions). Ensure all memory offsets and descriptor tables (GDT/IDT) are meticulously calculated. A misaligned pointer or incorrect segment limit will instantly crash the virtual or physical machine.
2. **Execution Surface:** Shell scripts (`run`, `nasm/run`) that launch emulators possess high execution authority on the host machine. Ensure modifications to these scripts do not introduce arbitrary code execution vulnerabilities if host arguments are passed through to the emulator command line.

## 5. Environmental Tooling (The Oracle)
Do not guess BIOS interrupt vectors (e.g., `int 0x10`, `int 0x13`), hallucinate Multiboot magic numbers, or rely on modern high-level programming knowledge to determine blast radius within this bare-metal sandbox. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
