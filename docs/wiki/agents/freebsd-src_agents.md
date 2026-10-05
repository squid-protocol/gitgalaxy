---
description: "You are operating within `freebsd-src`, the core operating system repository for FreeBSD. This is a massive, highly complex, low-level systems codebase..."
---
# AGENTS.md: freebsd-src Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `freebsd-src`, the core operating system repository for FreeBSD. This is a massive, highly complex, low-level systems codebase heavily dominated by C (53.9%), supported by shell scripts, Makefiles, and assembly. It encompasses the kernel, device drivers, core utilities, and userland applications.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.772. The network topology demonstrates completely flat Modularity (0.0) but slight positive Assortativity (0.0129). This indicates a highly monolithic, tightly coupled "hub-and-spoke" architecture where specific drivers and kernel subsystems are deeply intertwined with core foundational headers (`stdio.h`, `string.h`, `unistd.h`, `errno.h`).
* **Core Rule:** Maintain strict adherence to FreeBSD kernel coding standards and conventions. Do NOT attempt to decouple foundational kernel headers or introduce high-level abstractions into the C code. The architecture relies on rigid memory management, concurrency primitives (mutexes/spinlocks), and procedural C.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core data structure parsing (`_XML_Parse_SINGLE_BYTES` in Expat, archive extraction in `libarchive`) and fundamental string/compression operations (`uncompress` in bzip2) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep byte-level parsing and bitwise manipulations. You MUST NOT introduce unbounded loops, deep recursion, or heavy synchronous blocking operations on the critical path of kernel networking (`sys/netinet/`), storage (`sys/fs/`), or driver interrupts.
* **Orchestrator Fragility:** Central orchestrators such as `stand/efi/libefi/env.c` (99 outbound dependencies) and LLDB expression parsers (`ClangExpressionParser.cpp`) are highly fragile. Modifying bootloader environment handling or debugger evaluation logic requires extreme caution and extensive cross-architecture testing.
* **Avoid Dead Code Pruning:** Files like `sys/dev/aq/aq_hw_llh.c` (246 orphaned functions) and `sys/contrib/dev/rtw89/fw.h` (244 orphaned functions) contain logic flagged as "dead code." DO NOT autonomously attempt to prune or format these files. Driver implementations often include exhaustive hardware register definitions and hardware-specific callbacks that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission, architectural review, and rigorous kernel panic (panic.log) testing before modifying the structural signatures, locking semantics, or public APIs of these files:
* `sys/netinet/tcp_stacks/rack.c` & `sys/netinet/tcp_stacks/bbr.c` (Massive Structural Mass: >14k LOC. Core TCP congestion control stacks. BBR is a Key Person Silo - 100% isolated ownership by Randall Stewart).
* `sys/fs/nfs/nfs_commonsubs.c` (Massive Structural Mass and Key Person Silo - 85.7% isolated ownership by Rick Macklem. Core NFSv4 operations).
* `sys/cam/ctl/ctl.c` (Key Person Silo - 100% isolated ownership by Gordon Bergling. Core CAM target layer operations).
* `sys/netinet/sctp_output.c` (Key Person Silo - 100% isolated ownership by Gleb Smirnoff. Core SCTP networking protocol).
* `usr.sbin/freebsd-update/freebsd-update.sh` (Highest I/O Latency Risk and Database Complexity. Critical system update mechanism).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & KERNEL CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within core utilities (`bin/pax/cpio.c`, `bin/ps/ps.c`) and the entire kernel (`sys/`) inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications to `malloc`, `copyin`/`copyout`, or mbuf handling (`uipc_mbuf.c`) must be mathematically proven to prevent privilege escalation, Use-After-Free (UAF), buffer overflows, or kernel panics.
2. **Exploit Generation Surface:** Debugging, tracing, and legacy Perl scripts (`cddl/contrib/opensolaris/cmd/dtrace/test/cmd/scripts/dtest.pl`, `contrib/sendmail/contrib/*.pl`) possess a 100% Exposure score for Exploit Generation. Ensure any modifications to DTrace probes or build configurations (`crypto/openssl/Configure`) handle user input and system state securely.
3. **Supply Chain / Binary Data:** There are 1079 binary anomalies identified by X-Ray (often firmware, test fixtures, or cryptographic samples). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess FreeBSD kernel locking (`mtx_lock`/`rw_lock`), hallucinate POSIX system call implementations, or rely on generalized C knowledge to determine blast radius within this 13M+ LOC operating system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
