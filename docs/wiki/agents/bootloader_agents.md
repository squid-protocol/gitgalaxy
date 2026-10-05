---
description: "You are operating within `bootloader`, a pure-Rust (87.5%) implementation of a bootloader for x86_64 architectures, designed to bridge UEFI and legacy..."
---
# AGENTS.md: bootloader Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (System Context)
You are operating within `bootloader`, a pure-Rust (87.5%) implementation of a bootloader for x86_64 architectures, designed to bridge UEFI and legacy BIOS environments to load an OS kernel.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.606. This abnormal Z-Score reflects the highly specialized, bare-metal nature of the repository. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, indicating a flat, linear execution path split tightly along hardware targets (`bios/stage-2`, `bios/stage-3`, `bios/stage-4`, and `uefi`). Do not attempt to introduce abstract application-level patterns; the architecture is dictated strictly by the CPU boot sequence.

## 2. Notable Structures & Architecture (Guardrails)
* **Algorithmic Complexity Limits:** Foundational memory management functions (`construct_memory_map` in `common/src/legacy_memory_region.rs`, and execution flow in `common/src/load_kernel.rs`) operate with O(2^N) recursive time complexities in static analysis due to deeply nested hardware checks. You MUST NOT introduce additional iterations or dynamic memory allocations (heap usage is strictly prohibited in early stages).
* **Orchestrator Fragility:** Central orchestrators such as `bios/stage-4/src/main.rs` (12 outbound dependencies) and `uefi/src/main.rs` (10 outbound dependencies) dictate the final phase of the boot process. Any changes to page table mappings, context switching, or hardware state within these orchestrators require immediate, comprehensive verification of downstream runtime behaviors.
* **Dead Code Preservation:** The `api/src/info.rs` module and various tests contain logic that may appear orphaned. DO NOT autonomously prune these blocks. Bootloader configurations often rely on conditional compilation (`#[cfg]`) and statically injected entry points that bypass static dependency trees.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH BARE-METAL CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts and 0 supply chain anomalies.
* **Raw Memory Manipulation:** Operations in `bios/stage-2/src/main.rs` and the broader `common/src/` modules inherently rely on raw memory manipulation and `unsafe` Rust. Any pointer arithmetic, page table modifications (`level_4_entries.rs`), or direct hardware I/O must be rigorously bounded to prevent memory corruption or triple-faulting the CPU.

## 4. Outliers & Extremes (Restricted Zones)
The following files are load-bearing "God Nodes" possessing extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream hardware-level testing before modifying the structural signatures, `unsafe` blocks, or public APIs of these files:
* `bios/stage-2/src/disk.rs` (Highest Cumulative Risk: 528.96, High Volatility, Blind Bottleneck)
* `bios/boot_sector/src/boot.s` (Assembly execution core, 99.8% Tech Debt, Severe Blind Bottleneck)
* `common/src/legacy_memory_region.rs` (Key Person Silo - 100% isolated ownership by Spencer)
* `uefi/src/main.rs` (Key Person Silo - 100% isolated ownership by Spencer)
* `api/src/config.rs` (Key Person Silo - 100% isolated ownership by rezky_nightky)

## 5. Recommended Next Steps (Refactoring for Stability)
When instructed to optimize or refactor, autonomous agents should prioritize the following pragmatic stability improvements:
1. **Document Blind Bottlenecks:** Mitigate the extreme documentation risk (100%) in `bios/boot_sector/src/boot.s` and `bios/stage-2/src/disk.rs`. Add explicit inline comments detailing the expected register states, interrupt vectors, and memory maps to reduce the severity of these blind spots.
2. **Decouple Initialization Orchestrators:** Refactor the hardware initialization logic inside `uefi/src/main.rs` and `bios/stage-4/src/main.rs` to push shared memory descriptor and page-table logic down into the `common/` crate, reducing their fragility index.
3. **Address Test Debt:** Resolve the high Tech Debt Exposure (87.3%) in `api/src/info.rs` by ensuring that cross-platform API configurations are rigorously tested for both BIOS and UEFI targets.

## 6. Environmental Tooling (The Oracle)
Do not guess hardware offsets, hallucinate memory addresses, or rely on generalized Rust knowledge to determine blast radius within this bare-metal codebase. 

You have access to a deterministic GitGalaxy SQLite database. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.


---

**[⬅️ Back to Master Index](../index.md)**
