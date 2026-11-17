---
description: "Machine-readable playbook for LLM coding agents using sfs quality, sfs lattice-compare, sfs explain, and sfs twins to compare repositories and interpret structural homology."
---
# LLM Agent Playbook: Comparing Repositories & Explaining Structural Differences

This cookbook is written for **LLM agents and automated tool-use loops** calling `structural-fingerprint-scanner` (`sfs`) via `--json`.

---

## Agent Decision Loop (3 Commands)

```bash
# 1. Pre-flight quality check (verify scan completeness before trusting numbers)
sfs quality repo_a/ --source repo_a/ --verify --json
sfs quality repo_b/ --source repo_b/ --verify --json

# 2. Two-layer comparison (Layer 1: FGW Seed-and-Extend, Layer 2: 32-keyword lattice)
sfs lattice-compare repo_a/ repo_b/ --lens portable --matches --json

# 3. Feature-level explanation (when the user asks "what drifted?")
sfs explain repo_a/ repo_b/ --json
```

---

## How an LLM Should Interpret `--json` Outputs

### Step 1: Gate on `accurate_numbers`
In `sfs quality --json`, inspect `overall_status` and `accurate_numbers`:
- If `accurate_numbers` is `false` (`overall_status == "fail"`), **do not** report `fgw_cost` or `kw_jsd` as definitive structural findings. Instead, inspect `languages[]` for low `ctags_recall`/`treesitter_recall` or high `zero_signal_rate` and run the [Disagreement Cell Triage](llm-disagreement-cell-triage-and-issue-filing.md) workflow.

### Step 2: Classify the Pair from `sfs lattice-compare --json`

| Pattern in JSON | Interpretation to Report | Example |
|---|---|---|
| Low `fgw_cost` (`< 0.58`) + high `se_coverage` + high `matched_arch_agree` | **Direct vertical fork or close translation** | `cydoomgeneric ↔ doomgeneric` (`FGW=0.313`), `doomgeneric ↔ linuxdoom` (`0.567`) |
| Low `fgw_cost` (`~0.60–0.66`) + high `matched_kw_cos` across a different language | **Paradigm-preserving cross-language port** | `gore ↔ linuxdoom` (`75.9%` SE name recovery in Go) |
| Moderate `fgw_cost` + `matches` (`tier=0,1`) concentrated in one cluster | **Horizontal module borrowing** | `textscreen` shared between `eternity` and `odamex` (`76–84%` of Tier-1 hits) |
| Same-task, same-lang pair with low `kw_jsd` (`~0.11`) & low `fgw_cost` | **Shared model/author template** | Independent Sonnet runs (`FGW 0.154–0.489`) |
| High `fgw_cost` (`> 0.70`) + near-zero `se_coverage` | **From-scratch rewrite, paradigm shift, or unrelated domain** | `iron-doom` (Bevy ECS), `room4doom`, `rust-doom`, `lua` |

---

## Worked Agent Prompt Examples

### Example A: "Did Repo B copy or port Repo A?"
1. Run `sfs lattice-compare repo_a/ repo_b/ --lens portable --matches --json`.
2. Check if `fgw_cost < 0.65` and `se_n` is substantial.
3. Group `matches` by `tier == 0` (Tier-1 FGW anchors) and `tier >= 1` (hop extensions) to report whether similarity is **repo-wide** (vertical port) or **localized** (horizontally borrowed subsystem).

### Example B: "Were these two implementations written by the same AI model?"
1. Confirm both implementations are on the **same task and language** (or apply `LanguageDeltaModel` centering when cross-language).
2. Compare `kw_jsd` (`0.944` ROC AUC within task+language) alongside `matched_arch_agree` (`77.3%` same-model median vs. `54.2%` cross-model).
3. Use `sfs explain repo_a/ repo_b/ --json` to cite the exact signal densities (`bitwise_ops`, `state_pointers`, `struct_branch`, etc.) that separate them.

---

**[⬅️ Back to Master Index](../index.md)**
