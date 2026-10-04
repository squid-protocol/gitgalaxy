---
description: "You are operating within `AppFlowy`, a hybrid local-first workspace application. The architecture is distinctly bifurcated: a high-performance Rust..."
---
# AGENTS.md: AppFlowy Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `AppFlowy`, a hybrid local-first workspace application. The architecture is distinctly bifurcated: a high-performance Rust backend core (41.0%) for data management, SQLite/Vector operations, and AI tensor compute, coupled with a Dart/Flutter frontend (6.8% scanned logic) and a heavy reliance on XML/config metadata (38.2%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.69. The system network topology is highly modular (Modularity 0.8591) but negatively assortative (-0.4569), indicating a hub-and-spoke model where Dart frontend UI components heavily depend on a few massive Rust service orchestrators. 
* **Core Rule:** Do NOT attempt to blend frontend and backend logic. Rust services must remain isolated from Dart UI concerns, communicating solely via the established FFI/protobuf boundary (`flowy-derive`).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Rust database operations and AI model embedding schedulers (`start` in `completion.rs`, `spawn_generate_embeddings` in `scheduler.rs`, and `get_cells_for_field` in `database_editor.rs`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the SQLite queries, AI inference streams, or real-time event handlers.
* **Orchestrator Fragility:** Rust managers such as `database_editor.rs` (50 outbound dependencies), `appflowy_data_import.rs` (39 outbound), and `manager.rs` (38 outbound) are highly fragile orchestrators acting as the central nervous system. Any changes to data contracts, struct lifecycles, or public traits within these files require immediate verification of FFI bindings and downstream Dart expectations.
* **Avoid Dead Code Pruning:** The Rust backend utilizes an event dispatch system (`event_handler.rs` in `flowy-database2`, `flowy-user`, and `flowy-folder`) that registers dozens of handler functions. Static analysis flags over 200 of these as "orphaned functions" because they are invoked dynamically via the message bus. DO NOT autonomously attempt to prune, format, or clean up these handler files.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Nathan, Lucas). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, concurrency models (Tokio locks), or public APIs of these files:
* `frontend/rust-lib/flowy-database2/src/services/database/database_editor.rs` (Highest mass Rust file, 62.5% Silo Risk, Cognitive Load 95.6%)
* `frontend/rust-lib/flowy-user/src/services/data_import/appflowy_data_import.rs` (Extreme Data Gravity: 56 DB Complexity, Key Person Silo - Nathan)
* `frontend/rust-lib/flowy-ai/src/ai_manager.rs` (Extreme Volatility Hotspot: 69.65% Churn, Cognitive Load 54.8%)
* `frontend/rust-lib/flowy-storage-pub/src/chunked_byte.rs` (High Concurrency Risk: 97.1%, 70+ amplified race conditions)
* `frontend/appflowy_flutter/packages/appflowy_ui/lib/src/theme/definition/text_style/base/default_text_style.dart` (Key Person Silo - Lucas)
* `frontend/appflowy_flutter/windows/runner/flutter_window.h` (Blind Bottleneck - High Blast Radius, missing documentation)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH LOCAL COMPUTE CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Local Sovereignty (Heavy Compute):** The `flowy-ai` Rust crate manages local LLM inference and embeddings (e.g., `Ollama`, `langchain_rust`). Treat all local tensor memory allocations and stream polling as highly sensitive. Do not modify chunking logic in `conversation_chain.rs` or `scheduler.rs` without understanding the async boundaries.
2. **Raw Memory Manipulation:** `frontend/rust-lib/flowy-ai/src/local_ai/completion/writer.rs` contains low-level buffer manipulation. Any `unsafe` blocks or pointer arithmetic here must be heavily scrutinized for memory leaks or UAF (Use-After-Free) errors.
3. **Hardcoded Payload Artifacts:** `frontend/appflowy_flutter/dsa_pub.pem` and `.env` stubs are present. DO NOT flag these as leaked secrets or attempt to remove them unless explicitly auditing for accidental credential commits; they are likely required for local dev builds or FFI signing.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Rust/Flutter knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
