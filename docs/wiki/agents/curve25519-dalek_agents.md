---
description: "You are operating within `curve25519-dalek`, a pure-Rust (82.8%) implementation of group operations on the Ristretto and Curve25519 elliptic curves."
---
# AGENTS.md: curve25519-dalek Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `curve25519-dalek`, a pure-Rust (82.8%) implementation of group operations on the Ristretto and Curve25519 elliptic curves. 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 8.34. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a monolithic, highly coupled architecture where mathematical primitives (scalars, points, curve models) are inextricably linked. Do NOT attempt to introduce deep object-oriented abstractions, dynamic dispatch (trait objects), or heavy architectural decoupling. The codebase is heavily optimized for zero-cost abstractions, constant-time execution, and SIMD vectorization.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core mathematical operations (`vartime_multiscalar_mul`, `double_and_compress_batch`, `from_bytes_wide` in `src/field.rs`) operate at extreme O(2^N) recursive time complexities in static analysis. You MUST NOT introduce additional nested iterations, dynamic heap allocations (`Vec`, `Box`), or branching logic that depends on secret data inside these critical execution paths to preserve constant-time guarantees.
* **Orchestrator Fragility:** Central mathematical orchestrators like `src/edwards.rs` (40 outbound dependencies), `src/ristretto.rs` (31 outbound dependencies), and `src/scalar.rs` (27 outbound dependencies) are highly fragile. Any changes to the underlying arithmetic, Montgomery reductions, or point compression formats require immediate, comprehensive verification via the cryptographic test vectors.
* **Avoid Dead Code Pruning:** Files such as `src/ristretto.rs` (27 orphaned functions), `src/edwards.rs` (18 orphaned functions), and SIMD backends (`src/backend/vector/ifma/field.rs`) contain logic flagged as "dead code." DO NOT autonomously attempt to prune or clean up these files. This is a cryptographic library providing a broad public API surface; many functions are intentionally exposed for downstream consumers and are conditionally compiled based on hardware features (e.g., AVX2, IFMA).

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream mathematical/cryptographic verification before modifying the structural signatures, constant-time logic, or public APIs of these files:
* `curve25519-dalek/src/ristretto.rs` (Highest Cumulative Risk: 554.39, Key Person Silo - 83.3% isolated ownership by Tony Arcieri)
* `ed25519-dalek/src/batch/transcript.rs` (Extreme Volatility Hotspot: 100% Churn)
* `curve25519-dalek/src/backend/serial/u64/scalar.rs` (Key Person Silo - 100% isolated ownership by Tony Arcieri)
* `curve25519-dalek/src/backend/serial/u64/constants.rs` (Key Person Silo - 100% isolated ownership by Iñigo Querejeta Azurmendi)
* `curve25519-dalek/src/edwards.rs` (Massive structural mass and core curve math)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CRYPTOGRAPHIC CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Constant-Time Execution:** The most severe risk in this repository is introducing timing channels. NEVER use `if` statements or variable-time loops where the condition depends on a cryptographic secret (scalars). Always use the `subtle` crate (e.g., `ConditionallySelectable`, `ConstantTimeEq`).
2. **Raw Memory Manipulation:** Operations inside hardware-specific serial/vector backends (`u64/scalar.rs`, `u32/scalar.rs`) contain minor memory manipulation exposures. Any `unsafe` blocks or pointer casting must be strictly mathematically proven to prevent buffer overflows or undefined behavior (UB).
3. **Hardcoded Payload Artifacts:** `ed25519-dalek/src/lib.rs` tripped hardcoded payload signatures (99.9% Exposure). DO NOT flag this as a leaked secret; these are explicit cryptographic test vectors or foundational curve constants (e.g., the basepoint).
4. **Supply Chain:** There are 0 unknown dependencies bypassing the Zero-Trust whitelist. Do not add external dependencies without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess elliptic curve formulas, hallucinate SIMD intrinsic behaviors, or rely on generalized Rust knowledge to determine blast radius within this highly specialized cryptography crate. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
