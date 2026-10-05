---
description: "You are operating within `capstone`, a multi-architecture disassembly framework. The execution core is heavily dominated by C (368k+ LOC), complemented..."
---
# AGENTS.md: capstone Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `capstone`, a multi-architecture disassembly framework. The execution core is heavily dominated by C (368k+ LOC), complemented by extensive declarative configurations (YAML), C# bindings, and Python automation scripts.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits an Architectural Drift Z-Score of 7.35. The network topology demonstrates exceptionally high Modularity (0.8454) but negative Assortativity (-0.2579). This reveals a "hub-and-spoke" architecture where clean micro-boundaries exist per architecture (e.g., `arch/ARM`, `arch/X86`), but they all rely heavily on fragile, highly connected hub nodes (like `cs.c` and `capstone.h`). Do NOT attempt to introduce deep object-oriented abstractions or cross-architecture coupling. The C core must remain flat, ABI-stable, and architecture-isolated.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Translation and decoding functions (`translateOperand` in `arch/X86/X86Disassembler.c`, and auto-sync Python scripts like `suite/auto-sync/src/autosync/Tests/test_mcupdater.py`) register extreme O(2^N) recursive time complexities due to deep switch-cases and bitwise instruction masking. You MUST NOT introduce additional nested loops, dynamic memory allocations on the hot path, or O(N^2+) complexity in the instruction decoding or mapping logic.
* **Orchestrator Fragility:** Central orchestrators like the Python synchronization tool (`suite/auto-sync/src/autosync/cpptranslator/CppTranslator.py` with 77 outbound dependencies) and the C core API (`cs.c` with 35 outbound dependencies) are highly fragile. Any changes to the instruction translation mapping or the core API structs will cascade across all supported architectures.
* **Avoid Dead Code Pruning:** Disassembler implementations (`arch/M68K/M68KDisassembler.c` with 187 orphans, `arch/ARM/ARMInstPrinter.c` with 74) contain massive blocks of functions flagged as "orphaned" by static analysis. DO NOT autonomously attempt to prune, format, or clean up these files. Capstone relies heavily on generated tables, function pointers, and macro-based instruction dispatch that bypass static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, raw memory casts, or public APIs of these files:
* `cs.c` (The Core API Hub - Extreme Volatility: 100% Churn, 68.8% Cognitive Load)
* `arch/RISCV/RISCVMapping.c` (High Volatility Hotspot: 99.1% Churn)
* `include/capstone/arm64.h` (Massive Structural Mass: 4563.36, Key Person Silo - 100% isolated ownership by Rot127, High Error Risk)
* `arch/HPPA/HPPADisassembler.c` & `arch/Mips/MipsDisassembler.c` (Key Person Silos - 100% isolated ownership by Rot127)
* `include/windowsce/stdint.h` & `cstool/cstool.h` (Severe Blind Bottlenecks - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files such as `MCInst.c`, `Mapping.c`, and core test suites (`test_detail_bpf.c`, `test_detail_aarch64.c`) rely heavily on raw memory manipulation and pointer arithmetic (10% Exposure). Any `malloc`, buffer parsing, or struct casting here must be rigorously scrutinized for out-of-bounds access, Use-After-Free (UAF), or segmentation faults, especially when processing malformed binary inputs.
2. **Exploit Generation Surface:** Java bindings (`TestArm64.java`, `TestMips.java`) and Python test scripts possess a 100% Exposure score for Exploit Generation and Obfuscation surfaces. Because Capstone analyzes untrusted, potentially malicious binary executables, you must ensure strict bounds checking and validation logic remain fully intact across all architecture decoders.
3. **Supply Chain:** There are 59 binary anomalies identified by X-Ray (likely test corpus binaries or fuzzing seeds). Do not modify or attempt to execute unrecognized binary blobs within the `suite/` or `tests/` directories.

## 5. Environmental Tooling (The Oracle)
Do not guess opcode bitmasks, hallucinate macro definitions, or rely on generalized C knowledge to determine blast radius within this highly specialized disassembly engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
