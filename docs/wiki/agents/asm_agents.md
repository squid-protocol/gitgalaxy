---
description: "You are operating within `asm`, a highly concentrated repository consisting of x86 Assembly language routines (19.4%), C wrappers (5.6%), and Makefiles..."
---
# AGENTS.md: asm Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `asm`, a highly concentrated repository consisting of x86 Assembly language routines (19.4%), C wrappers (5.6%), and Makefiles (22.2%) alongside Markdown documentation. 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, which is expected for a flat collection of isolated low-level procedural scripts and their build files. Do not attempt to introduce high-level abstractions, object-oriented patterns, or directory-wide coupling. The codebase is designed for raw execution and pedagogical demonstration of processor-level instructions.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity & Assembly Loops:** Routines such as `_calculate_dot_product` in `float/dot_product.asm` and `reverseStringAndPrint` in `strings/reverse.asm` heavily utilize jumps and branching that register as high-complexity recursive operations. You MUST NOT attempt to "optimize" these control flows using higher-level logic. Preserve the exact register allocation, stack alignment, and instruction selection.
* **Orchestrator Fragility:** The C files in `casm/` (e.g., `casm/casm2/casm.c` and `casm/casm3/casm.c`) act as external caller interfaces to the Assembly routines. Any changes to the Assembly function signatures, calling conventions, or exported symbols (`global _start` vs `global my_strlen`) require immediate, synchronized updates to the C wrappers and `Makefile` linkers.
* **Avoid Dead Code Pruning:** Files like `strings/reverse.asm` and `float/dot_product.asm` exhibit high Graveyard Exposure (commented-out blocks). DO NOT autonomously attempt to prune these. In an Assembly repository, these often represent alternate implementations, preserved cycle-counting experiments, or instructional notes.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess high cumulative risk, act as blind bottlenecks, or are isolated knowledge silos (Key Person Silos: Alex Kuleshov). 

**MANDATORY RULE:** You require explicit human permission and downstream build verification before modifying the structural signatures, system calls, or memory offsets of these files:
* `casm/casm2/casm.c` (Highest Cumulative Risk: 476.65, Blind Bottleneck with 100% Documentation Risk)
* `float/dot_product.asm` (Key Person Silo - 100% isolated ownership by Alex Kuleshov, High I/O Latency)
* `stack/stack.asm` (Key Person Silo - 100% isolated ownership by Alex Kuleshov)
* `strings/reverse.asm` (High Cumulative Risk: 400.89, High Graveyard Exposure)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH LOW-LEVEL MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Raw Memory Manipulation:** By definition, this repository directly manipulates the stack, heap, and registers. You must rigorously verify buffer boundaries, system call numbers (syscalls), and segment register states when modifying `stack/stack.asm` or `strings/reverse.asm` to prevent segmentation faults.
2. **Obfuscation Surface:** `float/dot_product.asm` flagged minor exposure for obfuscation. Ensure any added floating-point math or vector parsing logic remains cleanly documented and explicitly comments its FPU/SSE register usage.

## 5. Environmental Tooling (The Oracle)
Do not guess linking dependencies, hallucinate libc import paths, or rely on generalized Assembly knowledge to determine the blast radius of a modified symbol. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
