# Deep Churn (Codebase Volatility)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Relative Commit Volatility & Change Frequency
>
> **Summary:** Measures how frequently a source file is modified over time relative to the rest of the repository. Churn is auto-scaled across the codebase so that the most volatile file anchors the maximum score (100.0), and all other files are normalized logarithmically against this maximum.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum, scaling from 🟦 **Deep Blue** (stable, rarely touched code) to 🟥 **Intense Red** (highly active hotspots).

## Architectural Overview

Version control history reveals which components experience constant revision. Code stability varies naturally across project types, so raw commit counts can be misleading. A rapidly evolving repository might see dozens of commits per week, whereas a stable library might average one commit per month.

GitGalaxy uses a two-pass auto-scaling normalization model to measure relative volatility across the repository:

* **Stable / Settled (Score 0 - 20):** Files that are rarely modified after creation.
* **Moderate Activity (Score 21 - 79):** Files receiving periodic updates, maintenance, or feature expansions.
* **High Volatility Hotspot (Score 80 - 100):** Files undergoing frequent, intense modification relative to project history.

## Metric Inputs (Git History Data)

| Variable | Data Source | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `commit_count` | Git Log Analyzer | Integer | Total number of commits modifying the file. |
| `age_in_weeks` | Version Control Metadata | Float | File age in weeks relative to the newest commit in the repository. |
| `max_freq` | Pre-scan Phase 1 | Float | Highest raw change frequency observed across all files in the repository. |

## Universal Framework Integration

Because Churn is globally auto-scaled, certain baseline modifiers are handled specifically:

* **$Fc$ (Fidelity Coefficient):** Not applied (commit history is an exact, deterministic log).
* **$Irc$ (Implicit Risk Correction):** Not applied.
* **$Mp$ (Path Modifier):** Applied. High churn in experimental directories (`experiments/`, `scratch/`) is expected ($Mp < 1.0$), whereas high churn in core infrastructure (`core/`, `kernel/`) signals architectural instability ($Mp > 1.0$).

## Mathematical Formulation

The auto-scaling temporal model executes in three phases:

### Phase 1: Raw Commit Frequency
During the initial scan, the engine calculates the raw commit frequency for each file. Commit volume is normalized against the square root of the file's age in weeks to dampen the penalty on long-standing legacy files:

$$\text{RawFrequency} = \frac{\text{Commits}}{\sqrt{\max(\text{AgeInWeeks}, 1.0)}}$$

### Phase 2: Logarithmic Normalization
After scanning all files and finding the global maximum frequency ($\text{MaxFreq}$), a logarithmic transformation $\ln(1 + x)$ flattens extreme outliers and scales all scores onto a 0–100 range:

$$\text{BaseScore} = \left( \frac{\ln(1 + \text{RawFrequency})}{\ln(1 + \max(\text{MaxFreq}, 1.0))} \right) \times 100.0$$

### Phase 3: Contextual Path Adjustment
The logarithmic score is multiplied by the directory Path Modifier ($Mp$):

$$\text{FinalScore} = \min(\text{BaseScore} \times Mp, 100.0)$$

## Python Implementation Reference

```python
import math
from typing import List, Dict, Any

def _normalize_temporal_metrics(self, stars: List[Dict[str, Any]]):
    """Normalizes commit churn using a Logarithmic Curve for smooth relative scaling."""
    if not stars:
        return

    max_freq = 0.0

    # Phase 1: Find the global maximum change frequency
    for s in stars:
        freq = s.get("telemetry", {}).get("raw_churn_freq", 0.0)
        if freq > max_freq:
            max_freq = freq

    # Apply logarithmic curve to the repository ceiling
    safe_max_f = math.log1p(max(max_freq, 1.0))
    idx = self.RISK_SCHEMA.index("churn")

    # Phase 2: Normalize every file against the logarithmic maximum
    for s in stars:
        freq = s.get("telemetry", {}).get("raw_churn_freq", 0.0)
        base_score = (math.log1p(freq) / safe_max_f) * 100.0

        # Phase 3: Apply contextual Path Modifiers
        mp = s.get("telemetry", {}).get("multipliers", {}).get("churn", 1.0)
        final_churn = min(base_score * mp, 100.0)

        # Record normalized churn score in the risk vector
        if "risk_vector" in s and len(s["risk_vector"]) > idx:
            s["risk_vector"][idx] = round(final_churn, 2)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
