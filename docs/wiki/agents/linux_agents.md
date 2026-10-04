---
description: "You are operating within the `linux` repository, the core source tree of the Linux operating system kernel. The codebase is staggering in scale (24.2M+..."
---
# AGENTS.md: linux Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `linux` repository, the core source tree of the Linux operating system kernel. The codebase is staggering in scale (24.2M+ LOC) and is structurally dominated by C (82.4%), supported by Makefiles, Assembly, and Shell scripts. 
* **Architectural Paradigm:** The system maps to a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 5.489. The network topology demonstrates a Modularity of 0.0 and positive Assortativity (0.0176), representing a highly monolithic but rigorously hierarchical core. The kernel acts as a dense "resilient core" tightly coupled to essential POSIX/kernel headers, while peripheral subsystems (drivers, architectures, file systems) act as massive, isolated spokes.
* **Information Flow:** Execution flows from user-space syscall boundaries through standard virtualization and file system abstraction layers, down to specific hardware driver endpoints. 
* **Core Rule:** Maintain strict adherence to kernel space vs. user space boundaries. Do NOT introduce standard library dependencies, user-space semantics, or blocking calls within atomic contexts (e.g., interrupt handlers, RCU critical sections).

## 2. Notable Structures & Architecture
* **Foundational Load-Bearers:** Core utility and API headers carry immense blast radii. Files like `tools/include/nolibc/stdio.h` (1382 inbound connections), `unistd.h`, and `errno.h` are the fundamental pillars of the kernel and toolchain interconnectivity. Changes here risk breaking the entire compilation ecosystem.
* **Fragile Orchestrators:** Process execution and scheduling mechanics (`init/main.c`, `kernel/fork.c`) alongside the eBPF verifier (`tools/testing/selftests/bpf/prog_tests/verifier.c`) act as highly coupled orchestrators. These files handle incredibly complex state machines and API surfaces.
* **Massive Subsystems:** The repository's visible mass is highly concentrated in network stacks (`net/wireless/nl80211.c`) and graphics drivers (`drivers/gpu/drm/amd/amdgpu/amdgpu_dm.c`). These are heavily monolithic structures containing thousands of LOC and extreme structural density.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH CRITICAL RAW MEMORY / EXPLOIT CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts, but the domain requires absolute precision regarding memory safety.

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Architecture-specific core routines (`arch/alpha/kernel/core_tsunami.c`, `arch/alpha/kernel/signal.c`) natively require raw pointer arithmetic and direct memory manipulation. Any modifications to memory mapping, DMA operations, or page table management must be strictly verified against memory corruption vulnerabilities (e.g., Buffer Overflows, UAF).
2. **Weaponizable Injection Vectors:** Tools parsing BPF bytecode (`tools/bpf/bpf_jit_disasm.c`) and performance tracing logic (`tools/perf/util/expr.c`) exhibit 100% Exposure to weaponizable injection. Ensure parsers handling bytecode, tracepoints, or user-provided configurations strictly validate offsets, lengths, and instructions.
3. **Local Sovereignty (Heavy Compute):** The repository interacts intimately with deep hardware capabilities (GPU compute, tensor math). Changes to `amdgpu` or `nouveau` drivers have a significant systemic risk (Blast Radius: 3.238); unsafe driver operations will lead directly to kernel panics or hardware lockups.

## 4. Outliers & Extremes
* **The Hotspot Matrix (Volatility + Risk):** Core scheduling and verification mechanics are undergoing extreme churn. `kernel/sched/ext.c` (100% churn) and `kernel/bpf/verifier.c` (89.6% churn, 86.4% Cognitive Load) are massive sources of developer friction and systemic risk. These are active battlegrounds for kernel performance optimization and security hardening.
* **Extreme Structural Mass:** Files like `net/wireless/nl80211.c` (23.7K Mass) and `drivers/video/fbdev/sis/init301.c` (20K Mass) possess gravitational pull within their subsystems. They operate at high algorithmic complexities (O(N^3) to O(N^6)) with thousands of branching paths.
* **Blind Bottlenecks (God Nodes):** Deeply embedded headers such as `vmlinux.h` (BPF skeleton) and `perf/core.h` have 100% Documentation Risk paired with high blast radii. Operating on these nodes is flying blind without explicit context tracing.
* **Key Person Silos:** Massive driver ecosystems are often maintained by single domain experts (e.g., `drivers/usb/typec/tcpm/tcpm.c` by Xu Yang, `drivers/scsi/lpfc/lpfc_sli.c`).

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **Modularize the eBPF Verifier & Schedulers:** Given the extreme volatility and cognitive load in `kernel/bpf/verifier.c` and `kernel/sched/ext.c`, break down the validation passes and scheduling heuristics into isolated, testable compilation units. This will reduce merge conflicts and stabilize the core security/performance boundary.
2. **Audit and Document Blind Bottlenecks:** Address the 100% documentation risk in foundational headers like `vmlinux.h` and `nolibc/stdio.h`. Adding structured, architectural inline documentation detailing ABI constraints and usage rules will prevent cascading failures across BPF tools and user-space binaries.
3. **Prune Driver Design Slop:** Target specific legacy driver files showing high orphaned function counts (e.g., `drivers/net/wireless/realtek/rtw89/fw.h` with 244 orphans). Deprecating and removing dead hardware logic will lower overall repository mass and reduce the maintenance surface area for security patches.


---

**[⬅️ Back to Master Index](../index.md)**
