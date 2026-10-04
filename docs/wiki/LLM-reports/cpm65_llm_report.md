---
description: "The `cpm65` repository implements an operating system designed for the 6502 microprocessor architecture, heavily inspired by CP/M. The codebase is..."
---
# Architectural Brief: cpm65

## 1. Information Flow & Purpose (The Executive Summary)
The `cpm65` repository implements an operating system designed for the 6502 microprocessor architecture, heavily inspired by CP/M. The codebase is dominated by Assembly (54.5%) for core system operations (BDOS, CCP, and hardware-specific abstractions) and C (16.2%) for emulation tooling and user-space applications (e.g., assemblers, terminals). Information flows from foundational configuration files (`config.py`) and global assembly macros (`include/cpm65.inc`) downward into specific architectural ports (`src/arch/`), while auxiliary tools (`tools/cpmemu/`) simulate the OS environment for cross-platform development.

The system is categorized under the `Cluster 4` macro-species with a highly abnormal Architectural Drift Z-Score of 7.766. This severe deviation is characteristic of retro-computing and low-level hardware projects, which eschew modern modular abstractions in favor of monolithic, deeply hardware-coupled assembly routines and raw memory mappings.

## 2. Notable Structures & Architecture
Despite the low-level nature of the codebase, the network graph reveals a high Modularity score (0.7643), indicating clean micro-boundaries, primarily organized around the distinct hardware architectures supported by the OS.
* **Foundational Load-Bearers:** Core global headers and configuration files act as the system's structural pillars. `include/cpm65.inc` (13 inbound connections) and `config.py` (12 inbound connections) establish the fundamental macros and build configurations required across all architectural targets.
* **Fragile Orchestrators:** The C-based emulator utilities exhibit the highest outbound coupling. Files such as `tools/cpmemu/biosbdos.c` (12 outbound dependencies) and `tools/cpmemu/fileio.c` (11 outbound) function as fragile orchestrators. They bridge modern POSIX filesystem/I/O logic with simulated 6502 memory states, making them highly sensitive to changes in either the host OS or the internal BDOS specification.

## 3. Security & Vulnerabilities
**✅ SECURE: No Malware Detected.** The XGBoost Structural DNA model found no malicious artifacts.

The rule-based lens flagged `tools/cpmemu/biosbdos.c` and `apps/sys.c` with minor "Raw Memory Manipulation" exposures. In the context of a 6502 emulator and OS system utilities, this is standard operational behavior. These files are explicitly designed to perform direct pointer arithmetic, memory-mapped I/O, and page-boundary crossings to simulate the target hardware. No significant web-facing or injection vulnerabilities were detected.

## 4. Outliers & Extremes
The repository contains localized technical debt and algorithmic density, primarily in its user-space parsers and core file system implementations:
* **Algorithmic Choke Points:** The ANSI terminal application (`apps/ansiterm.c`) contains extreme structural density. The `ansi_parse` function represents a massive bottleneck (Impact: 568.6, DB Complexity: 86), utilizing a dense, monolithic state machine to decode terminal escape sequences.
* **Key Person Dependencies (Silos):** The project suffers from severe ownership isolation. David Given holds 100% isolated ownership over nearly all critical, load-bearing components, including `apps/asm.c` (Mass: 2218.8), `src/bdos/filesystem.S`, and `src/ccp.S`. This represents a critical 'Bus Factor' risk for the operating system's core logic.
* **Blind Bottlenecks:** Foundational configurations like `config.py` and core macros like `include/cpm65.inc` carry 100% Documentation Risk despite massive Blast Radii. They govern the entire compilation and execution landscape but lack human-readable intent, meaning developers must infer system-wide constraints from raw code.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the OS architecture and distribute operational knowledge, prioritize the following engineering efforts:

1.  **Illuminate the God Nodes:** Mandate immediate, structured documentation (e.g., standard block comments) for `include/cpm65.inc` and `config.py`. As these files are the root load-bearers for the build system and assembly macros, mitigating their 100% Documentation Risk is essential to lower the barrier to entry for new contributors.
2.  **Decompose the Terminal State Machine:** Refactor `apps/ansiterm.c`. The `ansi_parse` and `vt52_parse` functions should be broken down into discrete dispatch tables or isolated helper functions for specific escape codes. This will reduce the extreme cognitive load and Database Complexity currently housed in single functions.
3.  **Distribute Core Domain Knowledge:** Address the 100% ownership isolation currently held by David Given on core OS subsystems (`src/bdos/filesystem.S`, `apps/asm.c`). Encourage secondary maintainers to review and document these dense assembly and C modules to distribute critical knowledge regarding the BDOS and filesystem implementation.


---

**[⬅️ Back to Master Index](../index.md)**
