---
description: "> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor..."
---
# File Stability (Commit Age & Timestamp Heat)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Relative Temporal Distance & File Modifications
>
> **Summary:** Evaluates file age and timestamp stability across the repository. Instead of treating older code as inherently problematic, stability measures the relative time elapsed since a file was last modified compared to the newest and oldest timestamps in the repository.
>
> **Effect:** Maps directly to the GitGalaxy Universal Surface Spectrum:
> * 🟦 **RECENT / ACTIVE (Score 0-19):** Code modified very recently (the active edge of development).
> * 🟨 **SETTLED (Score 40-59):** Code modified near the midpoint of the repository timeline.
> * 🟥 **ESTABLISHED BASELINE (Score 80-100):** The oldest, long-unmodified files in the repository.

## Engineering Summary
This subsystem evaluates the relative age of source files based on modification timestamps. It solves the problem of treating older, stable code as inherently stale or problematic by shifting to a relative temporal distance model. It exists to provide a physical timeline context to other risk metrics, differentiating between active feature edges and established foundational baselines. This timestamp normalization integrates directly into the GitGalaxy temporal scaling pipeline.

## Purpose
To calculate the relative time elapsed since a file was last modified, scaling it against the active lifespan boundary of the entire repository.

## Problem Being Solved
Absolute file age is not actionable because a 3-year-old file in a 10-year-old repository is relatively recent, whereas a 3-year-old file in a 3-year-old repository is the foundational baseline. Simple timestamp lookups fail to provide repository-specific context.

## Design
Using auto-scaling normalization, Phase 1 scans the entire codebase to establish the repository's active lifespan boundary (`RepoMinTime` to `RepoMaxTime`). File stability is then calculated as a linear physical timestamp measurement.

**Mathematical Formulation**
1. **Calculate Temporal Distance:**
The elapsed time between the newest repository file (`RepoMaxTime`) and the target file's timestamp (`FileMTime`) is clamped to $\ge 0.0$:
$$\text{SecondsFromMax} = \max(\text{RepoMaxTime} - \text{FileMTime}, 0.0)$$
2. **Calculate Relative Ratio:**
The distance is normalized against the total active time range of the repository:
$$\text{TimeRange} = \max(\text{RepoMaxTime} - \text{RepoMinTime}, 1.0)$$
$$\text{StabilityScore} = \min\left( \left( \frac{\text{SecondsFromMax}}{\text{TimeRange}} \right) \times 100.0, 100.0 \right)$$
*(When Newest file, Score = 0.0; When Oldest file, Score = 100.0)*

**What this measures.** `FileMTime` is the file's last modification time, so the score is the time since the file's **last change** as a share of the repository's whole timeline, not its age since creation: a ten-year-old file edited yesterday scores about 0 (RECENT). With no usable history (not a git checkout, an exported tree with no `.git`, a shallow clone) the engine returns a neutral `50.0`.

## Pipeline Integration
```mermaid
flowchart LR
    A[Repo Scanner] -->|Min/Max Times| B[Temporal Normalizer]
    C[File System/Git] -->|File MTime| B
    B -->|Calculate Distance| D[Stability Score]
```
- **Inputs received:** Target file modification time (`FileMTime`), repository oldest modified time (`RepoMinTime`), repository newest modified time (`RepoMaxTime`).
- **Outputs produced:** A linear normalized stability score (0-100).
- **Dependencies:** Relies upstream on physical file system data or Git commit epoch timestamps.

## Tradeoffs
- Uses a linear scale rather than a logarithmic one. This was chosen to preserve exact temporal proportionality, though it sacrifices the ability to group long tails of legacy files tightly together.
- Operates independently of language or contextual path ($Fc$, $Irc$, $Mp$ are explicitly ignored) because a timestamp is an absolute physical measurement not influenced by syntax or directory structure.

## Limitations
- A single rogue commit (e.g., automated formatting across all files) will reset the `RepoMaxTime` and heavily skew the relative age of untouched files.
- Relies on Git commit timestamps which can be manually spoofed or accidentally rewritten during interactive rebases.- Relies on Git commit timestamps which can be manually spoofed or accidentally rewritten during interactive rebases.
- The same effect as the rogue formatting commit happens at smaller scale all the time: in 13 repositories 4-44% of in-place edits (median about 22%) were mechanical sweeps that reset a file's last-modified time without new work.
- Follows paths, not file identity: renaming or moving a file resets its history (libgit2's 2022 source reorganisation made 15-year-old files look 3.5 years old to a path-following history).
- Neither this value nor [Deep Churn](08-06-deep-churn.md) gives true file age (time since creation) or lifetime commit counts.

## Performance Notes
Requires a complete initial pass (Phase 1) over the codebase to determine global boundaries before calculating individual file scores. Once boundaries are established, the calculation is extremely fast $O(1)$ arithmetic.

## Future Work
Currently relies solely on raw commit epoch timestamps. Planned improvements include clustering algorithms to ignore massive automated formatting commits that artificially reset the active edge of the repository timeline.

## Measured Behavior (exploratory, 2026-11)
> **Research notes:** temporal-crucible, branch `sensor-overhaul`, `docs/sensor-overhaul/` (guide, `sensors/activity.md`, `sensors/tech_debt.md`) and `docs/turn_surface_area.md`. Measurements are exploratory (13 repositories; a 580-repository population sample confirms the descriptive results).

- **It is days since the last change.** Across 35,287 file-intervals in 7 repositories the persisted stability correlates 0.97 (within-repository ranks) with the number of days since the file's last commit.
- **One axis with churn, not two.** Churn and stability correlate -0.86 within repositories and -0.88 across 494 repositories of the population database; the intended short-term versus long-term pair is not realised because both are driven by the same recency input.
- **Relation to outcomes (descriptive).** Within size quartiles, stability ranks later fixes at AUC 0.41 (0.59 inverted: recently changed files get more fixes) and correlates -0.17 with later change.
- **True file age is a different, independent quantity.** Years since the first commit (following renames) correlates at most 0.15 in absolute value with recent activity and is not predictive (AUC 0.47); it is useful as context ("old and settled" versus "new").

## Related Components
- Deep Churn (Volatility normalizer)
- Repository Scanner Phase 1
