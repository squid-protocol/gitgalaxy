---
description: "Two-layer blind structural comparison combining Fused Gromov-Wasserstein Seed-and-Extend with 14-archetype and 32-keyword-family lattices."
---
# Claim 12 — Two-Layer Structural Homology (Seed-and-Extend + Keyword & Archetype Lattices)

[Claim 5b](03-05b-composition-archetypes.md) introduced the 14-archetype function taxonomy, and [Claim 7](03-07-claim-7-doom-comparisons.md) established cross-language DOOM comparison via structural twins. **Seed-and-Extend + Keyword Lattices** unify those ideas into a **blind, two-layer structural homology and stylometry pipeline** (implemented in `structural-fingerprint-scanner`) that reads **zero function names, comments, or file paths**.

---

## The Two Layers

| Layer | Representation | What It Measures | Invariant To | Breaks On |
|---|---|---|---|---|
| **1. Macro-Topology (FGW + Seed-and-Extend)** | Function geometry + hop-distance call graph | **Shared architectural ancestry** (source forks, horizontal modules, domain templates, or a model's learned skeleton) | Symbol names, directory layout, paradigm-preserving translations (`C → Go`) | Paradigm shifts (`C → Bevy ECS`), thin external wrappers |
| **2. Micro-Idiomatic Texture (32-Keyword-Family Lattice)** | 32-signal family distribution (`kw_JSD`) & post-SE matched cosine | **Author / model cognitive habits** (branching vs. bitwise ops vs. pointer/state flux) | Language syntax (once `delta_lang`-centered) | Missing keyword-family regexes (`>= 25%` signal loss) |

### How Layer 1 Works (Seed-and-Extend)
1. **Seed (Tier-1):** Compute Fused Gromov–Wasserstein (`FGW`, `alpha=0.5, eps=0.05`) optimal transport between two repositories' function descriptors and hop-distance call graphs, taking the top reciprocal best hits as structural anchors.
2. **Calibrate (`delta`):** Estimate the repo-to-repo translation vector `delta` in composition space directly from the Tier-1 seeds.
3. **Extend (3-Hop):** Iteratively propagate outward along 1-hop call-graph neighbors, matching functions reachable from anchored neighbors.

### How Layer 2 Works (Archetype & 32-Keyword-Family Lattices)
- **14-Archetype Lattice (`arch_JSD`, `matched_arch_agree`):** Tracks the mix of the 14 `portable` function archetypes. On `agent-habits`, post-SE archetype agreement nearly doubles separation between same-model repeats (`77.3%`) and cross-model pairs (`54.2%`).
- **32-Keyword-Family Lattice (`kw_JSD`, `matched_kw_cos`):** Tracks the full 32-dimensional signal-family simplex. Within `(task, language)`, `-kw_JSD` achieves **`0.944` ROC AUC** for same-model vs. different-model attribution (beating FGW Seed-and-Extend at `0.874` and 14-archetype JSD at `0.655`).
- **Additive Language Centering (`delta_lang`):** Language shifts in the 32D keyword-family simplex behave as **pure additive translations** rather than rotations—matching or outperforming 32×32 Orthogonal Procrustes (`0.698` vs. `0.645` on held-out `chess`). Subtracting `delta_lang` yields a zero-shot `Claude Code vs. Codex CLI` axis that transfers to held-out `explore/` tasks at **`0.730` ROC AUC** (`6/7` pairwise ordering).

---

## Empirical Validation Summary

1. **`doom-dna` (41 ports + controls):**
   - Unrelated C (`lua` `0.0%`, `quake`/`quake2` `0.6%`) and from-scratch rewrites (`room4doom`, `rust-doom`, `helion` `0.0%`) sit at the noise floor, while layout-stripped ports recover 1-to-1 (`puredoom` `89.0%` / `590` funcs; Go port `gore` `75.9%` / `426` funcs).
   - **Horizontal gene transfer:** Blindly surfaces Chocolate Doom's `textscreen` UI library inside `eternity` (`76.1%` of Tier-1 hits) and `odamex` (`84.0%`), and directly between `eternity ↔ odamex` (`190` Tier-1 hits).
   - **Preregistered `DOOM-E5` boundary:** `cydoomgeneric` (`FGW=0.313`, `100.0%` Tier-1 vs. `doomgeneric`) confirmed; `iron-doom` (`0.0%`, rewritten into Bevy ECS) and `doomarkable` (`0.0%`, 41-function external crate wrapper) pinpointed the imperative-call-graph boundary.
2. **`keyword-rosetta` (`language-crucible` v4.3.1, 24 languages):**
   - Adding universal `rosetta[lang] - rosetta["c"]` deltas to `linuxdoom` reduces JSD across all 5 tested cross-language DOOM translations (`mochadoom` `0.358 → 0.193`, `doomf77` `0.353 → 0.253`, `managed-doom` `0.332 → 0.273`, `gore` `0.329 → 0.273`, `dartdoom` `0.350 → 0.302`).

---

## Asymmetric Degradation Floors

Controlled ablations on `doomgeneric`, `gore`, and `rust-doom` against `linuxdoom` show that Layer 1 and Layer 2 fail in opposite ways:

- **Missing functions / call edges:** Layer 1 holds `>70–80%` Tier-1 precision through `50%` loss in same-language C (cliff at `75%` drop) and `~25%` loss in cross-language Go (cliff at `50%` drop), while Layer 2 (`kw_JSD`) stays flat (`0.101–0.109`) up to `90%` function loss.
- **Missing keyword signals:** Layer 1 stays at `98.7%` (C) / `91.5%` (Go) Tier-1 precision even with `90%` of signal columns zeroed, while Layer 2 (`kw_JSD`) jumps from `0.104 → 0.392` at just `25%` signal loss.

---

**[⬅️ Back to Master Index](index.md)**
