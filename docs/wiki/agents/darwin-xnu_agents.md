---
description: "You are operating within `darwin-xnu`, the core kernel for Apple's macOS, iOS, and related operating systems. This is an immense, deeply complex..."
---
# AGENTS.md: darwin-xnu Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `darwin-xnu`, the core kernel for Apple's macOS, iOS, and related operating systems. This is an immense, deeply complex codebase dominated by C (68.5%) and C++ (7.6%, primarily in IOKit), with heavy use of assembly for architecture-specific trap/interrupt handling.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates relatively high Modularity (0.6636) due to the separation of subsystems (BSD, Mach/osfmk, IOKit, libkern), but significant negative Assortativity (-0.1535). This indicates a strong "hub-and-spoke" dependency model where isolated driver/subsystem code heavily couples to foundational, massive kernel headers (e.g., `stdint.h`, `unistd.h`, `AvailabilityInternal.h`). 
* **Core Rule:** Do NOT attempt to refactor across subsystem boundaries (e.g., mixing Mach semantics with BSD network stack semantics) unless explicitly bridging them via established APIs. The architecture relies on rigid separation of concerns between Mach (microkernel), BSD (POSIX layer), and IOKit (driver framework).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core system call mapping (`bsd/kern/makesyscalls.sh`), lock acquisition (`ctl_getlock` in `bsd/kern/kern_control.c`), and virtual memory fault handling (`vm_fault_page` in `osfmk/vm/vm_fault.c`) operate at O(2^N) recursive time complexities in static analysis. You MUST NOT introduce unbounded loops, deep recursion, or O(N^2+) complexity in any kernel fast-paths, specifically within `osfmk/vm`, `bsd/net`, or interrupt handlers.
* **Orchestrator Fragility:** Central orchestrators like `iokit/Kernel/Tests/Tests.cpp` (144 outbound dependencies), `bsd/kern/bsd_init.c` (91 outbound), and `osfmk/kern/startup.c` (70 outbound) are highly fragile. Any changes to kernel initialization sequences, subsystem bootstrap ordering, or IOKit registry matching require extreme caution and extensive kernel-level debugging.
* **Avoid Dead Code Pruning:** The `iokit/Kernel/` directory contains massive C++ files (e.g., `IOServicePM.cpp`, `IOPMrootDomain.cpp`) with hundreds of functions flagged as "orphaned." DO NOT autonomously attempt to prune these. IOKit utilizes extensive vtable dispatch, dynamic registry matching, and power management callbacks that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or represent severe "House of Cards" bottlenecks. 

**MANDATORY RULE:** You require explicit human permission and rigorous kernel panic (panic.log) testing before modifying the structural signatures, locking semantics, or public APIs of these files:
* `bsd/net/pf.c` (Massive Structural Mass: 18,457.94. Packet filter core; high complexity and flux).
* `osfmk/vm/vm_map.c` (Massive Structural Mass: 13,911.22. Virtual memory management; hyper-critical path).
* `bsd/dev/dtrace/dtrace.c` (Massive Structural Mass: 13,333.3. Deep inspection framework with high cognitive load).
* `bsd/kern/uipc_socket.c` & `bsd/netinet/tcp_input.c` (Core networking stack; extremely high data gravity and complexity).
* `EXTERNAL_HEADERS/stdint.h` & `EXTERNAL_HEADERS/AvailabilityInternal.h` (Severe Blind Bottlenecks - hundreds of inbound connections flying blind with near 100% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** As a kernel, the entire `osfmk/vm/`, `bsd/dev/`, and `iokit/` subtrees rely on raw memory manipulation and pointer arithmetic (10% Exposure in files like `bsd/dev/arm/munge.c` and `bsd/dev/dtrace/fbt.c`). Any `kalloc`, `copyin`/`copyout`, or page table manipulation must be mathematically proven to prevent privilege escalation, Use-After-Free (UAF), or kernel panics.
2. **Exploit Generation Surface:** Debugging and introspection scripts (`tools/lldbmacros/*.py`) possess a 100% Exposure score for Exploit Generation. While these execute in user-space (LLDB), ensure any modifications handle kernel memory dumps and task structures securely without introducing vulnerabilities into the debugging toolchain.
3. **Supply Chain / Binary Data:** There are 11 binary anomalies identified by X-Ray. Do not alter or attempt to scan these binary blobs (often firmware or microcode fixtures) without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Mach port semantics, hallucinate IOKit retain/release cycles (`OSRetain`/`OSRelease`), or rely on standard POSIX knowledge to determine blast radius within this highly specialized kernel environment. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
