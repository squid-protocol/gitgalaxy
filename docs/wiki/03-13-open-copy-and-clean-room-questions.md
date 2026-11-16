---
description: "What empirical evidence from doom-dna, agent-habits, and keyword-rosetta suggests for open questions around code copying, cross-language ports, clean-room rewrites, and AI-generated implementations."
---
# Claim 13 — Open Copy, Clean-Room & AI-Convergence Questions

When debates arise over whether a port, rewrite, or AI-generated codebase "copied" an upstream project—or genuinely reimplemented it from scratch—arguments usually rely on either surface identifier matching or subjective reading. Across [`doom-dna`](https://github.com/squid-protocol/doom-dna), `agent-habits`, and [`keyword-rosetta`](https://github.com/squid-protocol/keyword-rosetta), blind two-layer structural measurement ([Claim 12](03-12-seed-extend-and-keyword-lattices.md)) gives concrete, falsifiable answers to four recurring questions.

> **Scope note:** Structural homology measures **call-graph topology and idiomatic texture**, not legal copyright. It tells you *what structural ancestry or shared template survived* without reading names, comments, or file paths.

---

## 1. Does translating into another language or flattening directories erase lineage?

**No — not when the imperative call graph is preserved.**

- **Flattened C:** `puredoom` (single-header C, `14.8%` directory-taxonomy score) still recovers **`89.0%`** (`590/663`) 1-to-1 functions against `linuxdoom` via Seed-and-Extend.
- **Cross-language C → Go:** `gore` (Go, `0.2%` directory-taxonomy score) recovers **`75.9%`** (`426/561`) 1-to-1 functions against `linuxdoom` (`FGW_cost=0.663`).
- **Python bindings over C:** In preregistered `DOOM-E5`, `cydoomgeneric` hit **`100.0%`** Tier-1 (`156/156`, `FGW_cost=0.313`) against `doomgeneric`, pinpointing its exact parent port.

**Implication:** Stripping identifiers, moving files into a single file or flat folder, or translating imperative functions into another imperative language does **not** hide structural descent.

---

## 2. Does rewriting into a different paradigm (e.g. ECS) or from scratch preserve call-graph DNA?

**No — paradigm-shifting rewrites and from-scratch engines sit at the `0.0%` floor.**

- **From-scratch engines:** `room4doom` (`0.0%`), `rust-doom` (`0.0%`), `helion` (`0.0%`), `doome` (`0.0%`), and `DOOM-style-Game` (`0.0%`) are indistinguishable from unrelated C codebases (`lua` `0.0%`, `quake` `0.6%`, `quake2` `0.6%`).
- **Paradigm-shifting port (`DOOM-E5` falsification):** `iron-doom` states it is built on Chocolate Doom, yet rewrote the engine into **Bevy ECS** (`crates_plugins.rs` + Bevy systems). Because decoupled ECS systems replace the imperative call graph, `iron-doom` dropped to **`0.0%`** (`0/24` Tier-1, `0/147` SE, `FGW_cost=0.734`) against `linuxdoom`.
- **Externalized dependency wrapper:** `doomarkable` (41-function Rust platform wrapper calling `doomgeneric-rs` externally) also scored **`0.0%`** because the engine call graph is not vendored in the repo.

**Implication:** A low Seed-and-Extend score does *not* by itself prove zero conceptual inspiration—it proves the **imperative call-graph skeleton** was not carried over (either because it was written from scratch, or because it was re-architected into a different paradigm like ECS).

---

## 3. Can we distinguish borrowing one library from porting an entire codebase?

**Yes — horizontal borrowing concentrates Seed-and-Extend matches inside a single subgraph.**

- `eternity` (SMMU/MBF branch) and `odamex` (ZDoom branch) score only `12` and `6` Tier-1 hits against `linuxdoom`.
- Yet blind Seed-and-Extend against `chocolate-doom` recovers **`210/276` (`76.1%`)** Tier-1 hits for `eternity` and **`178/212` (`84.0%`)** for `odamex`—almost entirely inside Chocolate Doom's horizontally borrowed `textscreen` (`TXT_*`) UI library—and **`190/228` (`83.3%`)** directly between `eternity ↔ odamex`.

**Implication:** Function-level alignment localizes *which* subsystem was copied vs. written independently, rather than collapsing a whole repository to a single similarity number.

---

## 4. Why do independent AI runs look like "copies" of each other—and is that codebase copying?

**No — same-model convergence reflects a shared learned template, not shared source ancestry.**

- **Model self-similarity (`agent-habits`, 56 runs):** Independent Sonnet runs on `chess` and `sat` converge to **`FGW = 0.154–0.489`** (`78.7%` Tier-1 / `68.1%` SE)—as tight as true C DOOM forks (`doomgeneric ↔ linuxdoom` `0.567`)—even with **zero shared codebase**, because the model's learned architectural template acts as a common ancestor. Switching models (`same_task_same_lang_diff_model`) jumps median `FGW_cost` from `0.548` to `0.696` and halves 3-hop SE precision (`50.9% → 26.5%`).
- **Domain architecture vs. upstream copying (COBOL controls):** Agentic COBOL raycasters (`agentic-cobol-doom-cc`, `agentic-cobol-doom-codex`) cluster with human `fps-cob` at **`FGW 0.670–0.706`** (tighter than business COBOL `carddemo-cobol-ctrl` at `0.748–0.772`), yet score **0–1** name hits against `linuxdoom` (`FGW 0.749–0.800`). They share **raycaster domain architecture**, not `linuxdoom` code.
- **Separating model style from language syntax:** In the 32-keyword-family lattice, subtracting an additive language-translation vector (`delta_lang`) isolates model style (`0.944` ROC AUC within `(task, lang)`; `0.730` zero-shot AUC on held-out `explore/`, ordering `Claude Code > Codex CLI` in `6/7` pairs including `agentic-cobol-doom-cc > agentic-cobol-doom-codex`).

**Implication:** When two AI-generated or AI-assisted repositories show high structural similarity, you must test against **same-model / same-domain baselines** before inferring codebase copying: two independent runs of the same model on the same problem will naturally look like forks of each other.

---

**[⬅️ Back to Master Index](index.md)**
