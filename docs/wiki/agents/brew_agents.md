---
description: "You are operating within `brew`, the Homebrew package manager for macOS and Linux. The repository is a hybrid architecture consisting primarily of Ruby..."
---
# AGENTS.md: brew Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `brew`, the Homebrew package manager for macOS and Linux. The repository is a hybrid architecture consisting primarily of Ruby (65.0%) for the core DSL and API interactions, alongside emerging Rust components (13.9%) and foundational Shell scripts (8.8%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 6.217. The network topology demonstrates high Modularity (0.6667) but perfectly neutral Assortativity (0.0). This indicates a highly isolated component structure where the Ruby API wrapper, Rust rewrite components (`brew-rs`), and shell orchestration operate in distinct silos with very specific communication bridges.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core networking and parsing utilities (`Utils` in `curl.rb`, `github.rb`, `pypi.rb`) operate at extreme O(2^N) recursive time complexities in static analysis due to complex API pagination, retry logic, and recursive dependency fetching. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the Github API wrappers or the Curl invocation logic.
* **Orchestrator Fragility:** Central coordinators in the new Rust architecture, such as `fetch.rs` (27 outbound dependencies) and `list.rs` (13 outbound dependencies), are highly fragile. Any changes to data contracts, CLI flags, or file-system interactions within the Rust rewrite require immediate verification against the existing Ruby implementations.
* **Avoid Dead Code Pruning:** The `utils/` directory (`shared_audits.rb`, `github.rb`, `helpers.sh`) contains many functions flagged as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. Homebrew relies on dynamic dispatch, global aliases, and formula-specific metaprogramming that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, network I/O, or public APIs of these files:
* `bin/brew` (The Core Entrypoint - Extreme Volatility Hotspot: 100% Churn, 91.7% Cognitive Load)
* `Library/Homebrew/utils/github.rb` (Highest Cumulative Risk: 580.17, 100% Logic Bomb Exposure)
* `Library/Homebrew/utils/github/api.rb` (Severe Blind Bottleneck - High Blast Radius, missing documentation)
* `Library/Homebrew/utils/shfmt.sh` (Key Person Silo - 100% isolated ownership by John E)
* `Library/Homebrew/rust/brew-rs/src/commands/install.rs` (Key Person Silo - 100% isolated ownership by Mike McQuaid)
* `Library/Homebrew/utils/wrapper.sh` (Hotspot: 81.07% Churn, 94% Cognitive Load)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT GENERATION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `Library/Homebrew/utils/curl.rb`, `gems.rb`, and `github/api.rb` possess a 100% Exposure score for Exploit Generation Surface. Because Homebrew inherently downloads, verifies, and executes third-party code (Formulas/Casks), you MUST ensure strict input sanitization, checksum validation, and secure temporary directory handling when modifying fetching or installation logic.
2. **Hardcoded Payload Artifacts:** `Library/Homebrew/api/homebrew-1.pem` and `cask/container.tar.xz.gpg` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are public keys and test fixtures required for API attestation and test suites.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Ruby/Rust knowledge to determine blast radius within this cross-language codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
