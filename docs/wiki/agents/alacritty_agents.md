---
description: "You are operating within `alacritty`, a high-performance, OpenGL-accelerated terminal emulator primarily composed of Rust (33.6% by file size, but..."
---
# AGENTS.md: alacritty Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `alacritty`, a high-performance, OpenGL-accelerated terminal emulator primarily composed of Rust (33.6% by file size, but containing the vast majority of execution logic) alongside JSON configuration schemas and GLSL shaders.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species with an Architectural Drift Z-Score of 3.813. The architecture is a highly optimized, low-latency state machine driven by tight event loops and direct graphics pipeline integrations. Do not attempt to force boilerplate decoupling, async/await web paradigms, or generic MVC patterns onto the core terminal grid or rendering engines.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core components such as `alacritty_terminal/src/term/search.rs` (`next_match_left` is O(N^6)) and `alacritty/src/event.rs` operate at extreme computational complexities to manage the terminal grid and event parsing. You MUST NOT introduce additional nested loops, expensive allocations, or O(N^2+) complexity in the rendering loop, search logic, or input handling paths.
* **Orchestrator Fragility:** Central coordinators such as `alacritty/src/event.rs` (51 outbound dependencies), `alacritty/src/display/mod.rs` (47 outbound), and `alacritty/src/input/mod.rs` (38 outbound) are highly fragile. Any changes to trait bounds, event signatures, or public properties within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** `alacritty_terminal/src/term/mod.rs` (24 orphaned functions), `search.rs` (20 orphaned), and `selection.rs` (18 orphaned) contain significant amounts of seemingly dead logic. DO NOT autonomously attempt to prune, format, or clean up these files unless explicitly instructed by the user, as they often contain conditional compilation flags (`#[cfg(...)]`) for different operating systems that standard static analysis might miss.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: Christian Duerr). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, `unsafe` blocks, or public APIs of these files:
* `alacritty/src/event.rs` (The Core Orchestrator - Extreme Mass: 2520.42, Impact: 2364.0)
* `alacritty/src/main.rs` (Extreme Volatility Hotspot - 72.71% Churn, 98.9% Tech Debt)
* `alacritty_terminal/src/term/search.rs` (Key Person Silo - 100% isolated ownership by Christian Duerr, High Cumulative Risk: 543.5)
* `alacritty_terminal/src/selection.rs` (Key Person Silo - Christian Duerr)
* `alacritty_terminal/src/index.rs` (Key Person Silo - Christian Duerr)
* `alacritty_terminal/src/vi_mode.rs` (Key Person Silo - Christian Duerr)
* `alacritty/res/gles2/*` and `alacritty/res/glsl3/*` (Blind Bottlenecks - Shaders lack documentation and are heavily relied upon)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. 

**CRITICAL WARNINGS:** 1. **Raw Memory Manipulation:** `alacritty/src/renderer/text/builtin_font.rs` and `alacritty_terminal/src/index.rs` contain raw memory manipulation and `unsafe` Rust. Any pointer arithmetic or buffer logic here must be heavily scrutinized for out-of-bounds access.
2. **Exploit Generation Surface:** `alacritty/src/config/bindings.rs` and `alacritty_terminal/src/term/mod.rs` manage complex user inputs and configuration parsing (20% Exploit Generation Surface). When modifying these files, you MUST ensure strict input validation and boundary checking to prevent terminal escape sequence injection or configuration-based buffer overflows.

## 5. Environmental Tooling (The Oracle)
Do not guess trait implementations, hallucinate import paths, or rely on generalized Rust knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
