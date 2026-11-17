---
description: "Use FGW Seed-and-Extend and the 32-keyword-family lattice to detect cross-language codebase lineage, horizontal module borrowing, and model-style signatures."
---
# How to Detect Cross-Language Lineage & Horizontal Code Borrowing

When a codebase is ported to another language, flattened into a single file, or borrows a subsystem from another branch, file paths and symbol names often change completely. Using the standalone `structural-fingerprint-scanner` (`sfs`) tool on GitGalaxy scans, you can align functions and measure idiomatic texture **without reading a single identifier**.

> **Read the empirical background:** [Claim 12 — Two-Layer Structural Homology](../03-12-seed-extend-and-keyword-lattices.md)

---

## 1. Install

```bash
pip install structural-fingerprint-scanner
# Optional: include gitgalaxy to auto-scan raw source directories
pip install 'structural-fingerprint-scanner[scan]'
```

---

## 2. Run Two-Layer Comparison (`sfs lattice-compare`)

Pass either pre-scanned GitGalaxy directories (`*_galaxy_master.db`) or raw source repositories (with `[scan]` installed):

```bash
sfs lattice-compare repo_a/ repo_b/ --lens portable --matches --json
```

### Key Output Fields

| Field | Layer | What It Tells You |
|---|---|---|
| `fgw_cost` | Layer 1 (FGW) | Structural transport cost. Lower = closer call-graph + geometry alignment (e.g. `0.313` for direct forks vs. `0.70+` for unrelated repos). |
| `se_n`, `se_coverage` | Layer 1 (Seed+Extend) | Number and share of functions matched 1-to-1 after Tier-1 seeding + 3-hop call-graph extension. |
| `kw_jsd` | Layer 2 (32-Keyword) | Jensen–Shannon distance (`0..1`) between 32-keyword-family distributions. Strongest discriminator for same-task/same-language author or model style (`0.944` ROC AUC). |
| `matched_kw_cos` | Layer 2 (Post-SE) | Median cosine similarity of 32-keyword vectors across Seed-and-Extend matched pairs. |
| `matched_arch_agree` | Layer 2 (Archetype) | Share of matched pairs sharing the same 14-archetype function label. |
| `matches` | Alignment | Per-pair `(row_a, row_b, tier, kw_cos, delta_res)` when `--matches` is passed (`tier=0` is a Tier-1 FGW seed; `tier=1..3` is a hop extension). |

---

## 3. Interpreting Common Patterns

- **True cross-language port (`C → Go`):** Low `fgw_cost` + high `se_coverage` + high `matched_arch_agree`, even if `kw_jsd` reflects the target language's syntax shift.
- **Horizontal module borrowing (`textscreen` in `eternity` / `odamex`):** Moderate overall `se_coverage` where the `tier=0` seeds and `tier=1` extensions concentrate tightly inside one call-graph community.
- **Paradigm-shifting rewrite (`C → Bevy ECS`):** `se_coverage` and name precision drop to the from-scratch floor (`~0%`) because decoupled ECS systems replace the imperative call graph.

---

**[⬅️ Back to Master Index](../index.md)**
