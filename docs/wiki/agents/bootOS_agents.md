---
description: "You are operating within `bootOS`, a monolithic 512-byte operating system written entirely in x86 Assembly language (62.5% of scanned matter)."
---
# AGENTS.md: bootOS Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bootOS`, a monolithic 512-byte operating system written entirely in x86 Assembly language (62.5% of scanned matter). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.221. This reflects its extreme constraints: it is a flat, zero-dependency architecture designed to fit within a single boot sector. Modularity and Assortativity are strictly 0.0. 
* **Core Rule:** Do NOT attempt to introduce modern software engineering abstractions, multi-file coupling, or higher-level C/Rust integrations. The system's entire existence is predicated on byte-level physical constraints within `os.asm` and its patches.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core execution functions (`os6`, `disk`, `restart` in `os.asm`, and game loops like `update_body` in `patch/snake.asm`) are structurally identified as having O(2^N) recursive time complexities due to assembly-level jump logic and tight inner loops. You MUST NOT introduce additional nested logic, extensive stack usage, or logic that expands the compiled binary beyond the 512-byte limit.
* **Orchestrator Fragility:** Because this is a flat architecture, files like `os.asm` and `patch/sokoban.asm` do not pull in external dependencies, but they are internally fragile. Changes to register allocations, interrupt vectors (e.g., `int 13h` for disk, `int 10h` for video), or jump offsets will catastrophically break the boot sector sequence.
* **Avoid Dead Code Pruning:** The repository contains functions flagged as "orphaned" (e.g., in `patch/mine.asm` and `os.asm`). DO NOT autonomously attempt to prune or format these. In an Assembly bootloader context, these are often entry points invoked by hardware interrupts or specific BIOS states that static analysis cannot reliably track.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess high cumulative risk, act as core execution pathways, or represent severe "Blind Bottlenecks" (100% Documentation Risk). 

**MANDATORY RULE:** You require explicit human validation via recompilation and emulator testing (e.g., QEMU) before modifying the structural signatures, register states, or interrupt logic of these files:
* `os.asm` (The Core OS Monolith - Handles disk I/O and text rendering)
* `patch/mine.asm` (Highest Cumulative Risk: 412.59, 98.7% Tech Debt Exposure)
* `counter.asm` (Severe Blind Bottleneck - 100% Documentation Risk)
* `patch/snake.asm` (Severe Blind Bottleneck - 100% Documentation Risk)
* `patch/sokoban.asm` (High state flux and hardware dependency)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH BARE-METAL CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Raw Hardware Access:** This OS interacts directly with the BIOS via hardware interrupts (e.g., `int 13h` in `os.asm` for disk writes). There are no memory protections, segmentation limits, or safety nets. Any modifications to sector numbers, track variables, or memory offsets (`es:bx`) must be mathematically verified to prevent data corruption outside the boot sector.
2. **Exploit Generation Surface:** While no explicit exploit surfaces were flagged, the nature of a boot sector OS means any logic flaw is effectively a bare-metal execution vulnerability. Ensure that user input (keyboard interrupts) cannot cause unbounded loops or overwrite critical kernel code in memory.

## 5. Environmental Tooling (The Oracle)
Do not guess hardware offsets, hallucinate BIOS interrupt codes, or rely on generalized Assembly knowledge to determine blast radius within this 512-byte constraint. 

You have access to a deterministic GitGalaxy SQLite database. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
