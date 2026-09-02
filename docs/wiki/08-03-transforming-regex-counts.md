# Transforming Regex Counts (Universal Exposure Framework)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This metric normalization subsystem, known as the Universal Exposure Framework (UEF), recalibrates raw static regex counts into stable architectural indicators. It solves the problem of raw hit counts being noisy, misleading, or skewed by codebase size. It exists to provide deterministic, language-aware filtering of heuristic signals. Within GitGalaxy, the UEF calculates final, tiered risk outputs from raw data variables.

## Purpose
To process raw occurrence counts through deterministic normalization transformations, stabilizing signals and eliminating false positives across different language paradigms.

## Problem Being Solved
Uncalibrated static regex counts penalize large files for minor issues and treat structural risk and defensive logic as a flawed 1:1 offset. The UEF stabilizes these signals into actionable, normalized intelligence.

## Design
Applies four stabilizing principles:
1. **Weighted Asymmetry:** Defensive hits receive a 2.5x multiplier to demand strong defensive density.
2. **The Breach Cap:** If raw risk hits exceed guardrail hits, the safety rating is severely capped, bypassing averages.
3. **Sigmoid Gating:** Uses a logistic sigmoid function to filter low-density noise (0-5%) and scale exponentially as risk crosses thresholds.
4. **Quantized Tiering:** Scores are binned into qualitative tiers (Unshielded to Fortified).
5. **Evidence-Mass Floor:** Every per-file density divides by $\max(LOC, 50)$, never by raw LOC. Below 50 coding lines a file is scored on its *counts* (a two-hit file is a two-hit file whether it is 5 or 49 lines long), so identical intent scores identically regardless of file length; at or above the floor the density regime is untouched. This is the per-file analog of the mass-weighted averaging used at directory scope, and it is the *only* small-file mechanism -- it replaced six independent guards (a `<15 LOC` cognitive-load cliff, two `+20` paddings, a `loc/15` dampener, an unbounded $Irc/LOC$ floor, a `max(total_loc, 10)` API guard) that each fired on a different LOC range and fought each other (#2655). Files below the floor carry `mass_floored: true` and their `evidence_mass` in telemetry. Two consistency rules follow from it: $Irc$ *corrects* measured risk and never creates it (zero measured evidence scores zero in every tier), and a file with no branches carries no cognitive load at any length.

Language Confidence Tiers (1 to 3) apply Fidelity Coefficients ($Fc$) and Implicit Risk Corrections ($Irc$) based on language strictness.
General Risk Equation:
$$RiskExposure = \left( \frac{((RiskHits + Irc) \times Weight) - (DefenseHits \times Fc)}{\max(LOC,\ 50)} \right) \times Mp$$

## Pipeline Integration
- **Inputs:** Raw regex counts, LOC, language metadata.
- **Outputs:** Normalized, quantized risk tiers (1-5).
- **Dependencies:** Receives input from the scanner extraction module and feeds into the knowledge graph and visual mapping layers.

Scanner Extraction -> Universal Exposure Framework -> Quantized Tier Output

## Tradeoffs
The sigmoid gating principle aggressively suppresses minor risks in large files, intentionally sacrificing micro-level visibility to prevent "alert fatigue" on the macro level. Language confidence tiers generalize thousands of languages into three buckets, reducing precision for niche languages.

## Limitations
- The 2.5x defensive multiplier is empirically derived and may not perfectly align with specific internal security postures.
- Path Multipliers ($Mp$) rely on standard directory naming conventions (`src/`, `test/`) which may fail in non-standard repositories.

## Performance Notes
Processing utilizes constant-time floating-point math per file component, resulting in $O(1)$ metric transformation time per unit post-extraction.

## Future Work
- Machine learning parameter tuning for Fidelity Coefficients based on historical vulnerability tracking.
- Configurable Breach Cap thresholds per repository.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
- [Sub-Equations](08-02-sub-equations.md)
