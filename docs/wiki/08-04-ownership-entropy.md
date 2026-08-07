# Authorship Distribution (Ownership Entropy)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This statistical analysis component calculates the Shannon Entropy of Git blame data to measure contribution dispersion across modules. It solves the problem of identifying knowledge silos and bus-factor risks hidden behind simple contributor headcounts. It exists to map authorship concentration to the Universal Risk Spectrum. Within GitGalaxy, it highlights whether a module is a single-author bottleneck or a highly distributed community effort.

## Purpose
To measure the distribution of commit contributions across authors within a module using Shannon Entropy, highlighting knowledge siloing versus shared maintenance.

## Problem Being Solved
Simple contributor headcounts fail to capture distribution. A file with 1 primary author (90%) and 10 minor contributors (1% each) has 11 authors but remains a knowledge silo. Shannon entropy correctly identifies this imbalance and penalizes high operational noise.

## Design
Evaluates authorship structure:
- **Low Entropy:** High concentration, individual ownership, high bus factor.
- **High Entropy:** Shared maintenance, high diffusion.

Calculation:
$$p_i = \frac{\text{Commits}_i}{\text{TotalCommits}}$$
$$H = -\sum \left( p_i \times \log_2(p_i) \right)$$
$$\text{OwnershipScore} = \min(H \times 32.0, 100.0)$$

Scores map to tiers: 0-20 (Single Owner), 21-60 (Team Collaboration), 61-100 (High Diffusion).

## Pipeline Integration
- **Inputs:** Git blame contribution maps and commit counts.
- **Outputs:** A normalized scalar entropy score (0-100) and color classification.
- **Dependencies:** Relies on upstream Git history extraction and feeds directly into the visualization shaders.

Git Blame Extractor -> Entropy Calculation Engine -> Visual Render Attributes

## Tradeoffs
Using commit counts as the basis for entropy assumes all commits have equal weight. A massive refactoring commit is weighed identically to a one-line typo fix, sacrificing granular impact analysis for fast, aggregate historical processing.

## Limitations
- Git author email aliases (e.g., user@local vs user@company) will skew entropy unless deduplicated prior to analysis.
- Extremely old legacy code may have high entropy from long-gone contributors, artificially inflating the diffusion score for the current active team.

## Performance Notes
Normalizing authorship into a scalar score ensures constant WebGPU rendering efficiency regardless of the number of unique contributors, guaranteeing 60 FPS performance on massive enterprise codebases.

## Future Work
- Time-decayed entropy weighting, prioritizing recent commit distribution over historical legacy authors.
- Commit size weighting (lines changed) integrated into the probability $p_i$ variable.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
