---
description: "You are operating within `cosmopolitan`, a build-once-run-anywhere C library and toolchain. The repository is predominantly C (52.2%) and Assembly..."
---
# AGENTS.md: cosmopolitan Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cosmopolitan`, a build-once-run-anywhere C library and toolchain. The repository is predominantly C (52.2%) and Assembly (38.8%), reflecting its role as a cross-platform libc implementation and executable formatter (Actually Portable Executable).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.004. The network topology demonstrates moderate Modularity (0.4159) but extreme negative Assortativity (-0.1218). This signifies a classic "hub-and-spoke" architecture where isolated hardware-specific or platform-specific implementations rely heavily on massive, highly connected "God Node" headers (like `str.h` and `dce.h`). Do NOT attempt to introduce deep object-oriented abstractions or modern service locators; the architecture requires flat, highly optimized, and tightly coupled C-ABI interfaces.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core executable loading mechanisms (`ape_macho` and `ape_grub_entry` in `ape/ape.S`) and audio DSP polling logic operate at extreme recursive time complexities in static analysis due to deep platform switching and bitwise masking. You MUST NOT introduce additional nested loops, dynamic memory allocations (`malloc`), or O(N^2+) complexity in the bootloader (`ape/`) or critical `libc/intrin/` paths.
* **Orchestrator Fragility:** Central orchestrators like `Makefile` (166 outbound dependencies) and `tool/net/redbean.c` (123 outbound dependencies) are highly fragile. Any changes to build flags, object linkage, or core server routing require comprehensive verification across all supported platforms (Linux, Mac, Windows, FreeBSD, OpenBSD, NetBSD).
* **Avoid Dead Code Pruning:** The `libc/intrin/` and `tool/net/` directories contain functions flagged as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. Cosmopolitan utilizes extensive `#ifdef` blocks and linker tricks that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream cross-compilation testing before modifying the structural signatures, assembly macros, or public APIs of these files:
* `libc/str/str.h` & `libc/math.h` (Severe Blind Bottlenecks - Massive blast radius with 100% Documentation Risk)
* `tool/cosmocc/bin/cosmocross` (Extreme Volatility Hotspot: 100% Churn, 99.8% Cognitive Load)
* `tool/net/redbean.c` (Massive Structural Mass: 5949.66, handles complex, multi-platform asynchronous networking)
* `libc/intrin/demangle.c` (Key Person Silo - 100% isolated ownership by Justine Tunney, high exploit generation surface)
* `dsp/audio/cosmoaudio/miniaudio.h` (Key Person Silo - 100% isolated ownership by Justine Tunney)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files in `ape/` and `libc/calls/` (e.g., `flocks.c`, `ioctl.c`) rely heavily on raw memory manipulation and pointer arithmetic (10% Exposure). Any `mmap`, buffer parsing, or struct casting here must be rigorously scrutinized for out-of-bounds access or segmentation faults, especially when interacting with different OS kernels.
2. **Weaponizable Injection Vectors:** The networking scripts (`tool/net/definitions.lua`) possess a 100% Exposure score for Injection Vectors. Because Redbean/Cosmopolitan serves web traffic, ensure any modifications to routing or Lua bindings strictly sanitize inputs to prevent Server-Side Template Injection (SSTI) or Lua code injection.
3. **Supply Chain / Binary Data:** There are 38 binary anomalies identified by X-Ray (likely embedded payloads or APE headers). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess assembly offsets, hallucinate libc macro definitions, or rely on standard POSIX knowledge to determine blast radius, as Cosmopolitan actively bridges POSIX and Windows NT. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
