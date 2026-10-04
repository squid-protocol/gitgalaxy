---
description: "You are operating within `blst`, a highly optimized cryptography library (BLS12-381 signatures) primarily composed of C (37.6%), Perl-based Assembly..."
---
# AGENTS.md: blst Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `blst`, a highly optimized cryptography library (BLS12-381 signatures) primarily composed of C (37.6%), Perl-based Assembly generators (24.8%), and various language bindings (Rust, Go, C++, etc.).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 5.886. The network topology demonstrates moderate Modularity (0.35) but significant negative assortativity (-0.4895). This indicates a hub-and-spoke model where multiple language bindings (the spokes) wrap and depend heavily on a hyper-concentrated, immutable C/Assembly core (the hub). Do not attempt to introduce modern software abstractions into the C core or the Perl ASM generators; they are strictly optimized for hardware-level mathematical operations.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core mathematical operations and bindings (`mult` and `add` in `bindings/rust/src/pippenger.rs`, `from` in `bindings/rust/src/lib.rs`, and `mult_pippenger` in `bindings/blst.hpp`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the multipk/aggregate verification logic or Pippenger algorithms.
* **Orchestrator Fragility:** Central orchestrators like `src/server.c` (20 outbound dependencies) and `bindings/rust/src/lib.rs` (13 outbound dependencies) are highly fragile. Any changes to data contracts or memory alignment within these files require immediate, comprehensive verification of downstream cross-language integrations.
* **Avoid Dead Code Pruning:** The C and Go bindings (`src/exports.c`, `src/e1.c`, `src/e2.c`, and `bindings/go/blst.go`) contain high volumes of functions that static analysis tools flag as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. Cryptographic libraries rely heavily on conditional compilation, macros, and FFI (Foreign Function Interface) exports that bypass static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Andy Polyakov). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, raw memory bounds, or public APIs of these files:
* `bindings/go/blst.go` (Highest Cumulative Risk: 627.56, Extreme Volatility Hotspot: 100% Churn)
* `src/asm/x86_64-xlate.pl` (Massive Structural Mass: 3118.76, Perl script generating core Assembly logic)
* `bindings/rust/src/lib.rs` (Key Person Silo - 100% isolated ownership by Andy Polyakov)
* `src/asm/arm-xlate.pl` (Key Person Silo - 100% isolated ownership by Andy Polyakov)
* `src/vect.h` (Severe Blind Bottleneck - Blast Radius of 97.49 with 100% Documentation Risk)
* `src/multi_scalar.c` (High Volatility and Core Execution Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files such as `src/aggregate.c`, `src/map_to_g2.c`, and the core point math headers (`src/point.h`, `src/fields.h`) rely heavily on raw memory manipulation and pointer arithmetic (e.g., `PAIRING_Aggregate_PK_in_G1`). Any modifications to memory buffers, byte alignments, or C-struct layouts here must be rigorously scrutinized for buffer overflows, side-channel leaks, or segmentation faults.
2. **Exploit Generation Surface:** `src/asm/x86_64-xlate.pl` and `src/asm/sha256-armv8.pl` possess a 100% Exposure score for Exploit Generation Surface due to the nature of generating raw executable Assembly code from scripting languages. Modifying these generators requires extreme caution to ensure valid and secure opcode emission.
3. **Supply Chain:** There are 5 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external packages (especially in the language bindings) without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized C/Rust/Go knowledge to determine blast radius within this highly specialized cryptographic codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
