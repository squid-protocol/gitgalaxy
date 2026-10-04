---
description: "You are operating within `bevy`, a data-driven, massively parallel game engine primarily composed of Rust (84.5%)."
title: "Bevy Agent Context & Architecture Rules"

---
# AGENTS.md: bevy Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `bevy`, a data-driven, massively parallel game engine primarily composed of Rust (84.5%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.009. The network topology demonstrates clean micro-boundaries (Modularity 0.64) typical of a highly decoupled workspace/crate structure, but with significant negative assortativity (-0.6667). This indicates that while crates are separated, the execution flow relies heavily on massive, highly connected "hub" modules (the ECS core, query engines, and render pipelines) acting as fragile single-points-of-failure. Do NOT attempt to apply object-oriented design patterns; you must strictly adhere to the Entity-Component-System (ECS) paradigm.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core query iterators and component lifecycles (`fold_over_storage_range` in `crates/bevy_ecs/src/query/iter.rs` and `from_states_uninitialized` in `crates/bevy_ecs/src/query/state.rs`) operate at extreme O(2^N) recursive time complexities with massive Database Complexities. You MUST NOT introduce additional nested loops, locking mechanisms, or O(N^2+) complexity when modifying query iteration, state transitions, or component fetching.
* **Orchestrator Fragility:** Central coordinators such as `crates/bevy_internal/src/lib.rs` (53 outbound dependencies) and `crates/bevy_pbr/src/render/mesh.rs` (48 outbound dependencies) are highly fragile orchestrators. Any changes to trait bounds, generic parameters, or macro exports within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** The ECS core (`crates/bevy_ecs/src/system/mod.rs`, `crates/bevy_ecs/src/entity/clone_entities.rs`, and `crates/bevy_ecs/src/schedule/executor/mod.rs`) contains dozens of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files. The engine relies heavily on macros, reflection, and generic monomorphization that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, `unsafe` blocks, or public APIs of these files:
* `crates/bevy_ecs/src/lib.rs` (Highest Cumulative Risk: 664.89, Extreme Volatility Hotspot: 83.5% Churn)
* `crates/bevy_ecs/src/system/commands/mod.rs` (Extreme Cognitive Load and High Tech Debt)
* `crates/bevy_ecs/src/query/iter.rs` (Extreme Structural Mass: 3076.64, Core iteration logic)
* `crates/bevy_gizmos/src/primitives/dim3.rs` & `dim2.rs` (Key Person Silos - 100% isolated ownership by Kevin Chen and Joel Uckelman)
* `crates/bevy_reflect/src/impls/uuid.rs` (Blind Bottleneck - High Blast Radius, missing documentation)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Raw Memory Manipulation:** Files such as `crates/bevy_ptr/src/lib.rs`, `crates/bevy_ecs/src/entity/clone_entities.rs`, and `crates/bevy_ecs/src/query/fetch.rs` contain raw memory manipulation, type aliasing, and `unsafe` Rust. Any pointer arithmetic, lifetime casting, or buffer logic here must be heavily scrutinized for undefined behavior (UB), out-of-bounds access, or broken aliasing rules.
2. **Concurrency Exposure:** The engine heavily parallelizes tasks. When modifying modules like `crates/bevy_tasks/src/task_pool.rs`, `crates/bevy_winit/src/system.rs`, or the `render` sub-crates, you must strictly respect established atomics, memory barriers, and synchronization primitives.
3. **Supply Chain:** There are 6 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external crates without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess trait implementations, hallucinate import paths, or rely on generalized Rust knowledge to determine blast radius in this 324k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
