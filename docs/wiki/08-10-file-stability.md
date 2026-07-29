# File Stability (Commit Age & Timestamp Heat)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Relative Temporal Distance & File Modifications
>
> **Summary:** Evaluates file age and timestamp stability across the repository. Instead of treating older code as inherently problematic, stability measures the relative time elapsed since a file was last modified compared to the newest and oldest timestamps in the repository.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **RECENT / ACTIVE (Score 0-19):** Code modified very recently (the active edge of development).
> * 🟨 **SETTLED (Score 40-59):** Code modified near the midpoint of the repository timeline.
> * 🟥 **ESTABLISHED BASELINE (Score 80-100):** The oldest, long-unmodified files in the repository.

## Metric Inputs (File System & Version Control)

Using auto-scaling normalization, Phase 1 scans the entire codebase to establish the repository's active lifespan boundary (`RepoMinTime` to `RepoMaxTime`):

| Variable | Data Source | Units | Description |
| :--- | :--- | :--- | :--- |
| `FileMTime` | `os.path.getmtime` / Git Commit | Epoch Timestamp | Last modified timestamp of the target file. |
| `RepoMinTime` | Repository Scanner Phase 1 | Epoch Timestamp | Oldest modified timestamp observed in the repository. |
| `RepoMaxTime` | Repository Scanner Phase 1 | Epoch Timestamp | Newest modified timestamp observed in the repository. |

## Universal Framework Integration

File stability is a linear physical timestamp measurement:

* **$Fc$ (Fidelity Coefficient):** Not applied (timestamps are exact epoch values).
* **$Irc$ (Implicit Risk Correction):** Not applied.
* **$Mp$ (Path Modifier):** Not applied (file modification age is an absolute measurement).

## Mathematical Formulation

Stability measures relative temporal distance from the repository's newest modification point:

### Step 1: Calculate Temporal Distance
The elapsed time between the newest repository file (`RepoMaxTime`) and the target file's timestamp (`FileMTime`) is calculated and clamped to $\ge 0.0$:

$$\text{SecondsFromMax} = \max(\text{RepoMaxTime} - \text{FileMTime}, 0.0)$$

### Step 2: Calculate Relative Ratio
The distance is normalized against the total active time range of the repository ($\ge 1.0$ second floor to prevent division by zero):

$$\text{TimeRange} = \max(\text{RepoMaxTime} - \text{RepoMinTime}, 1.0)$$
$$\text{StabilityScore} = \min\left( \left( \frac{\text{SecondsFromMax}}{\text{TimeRange}} \right) \times 100.0, 100.0 \right)$$

* When $\text{FileMTime} == \text{RepoMaxTime}$ (Newest file), $\text{StabilityScore} = 0.0$.
* When $\text{FileMTime} == \text{RepoMinTime}$ (Oldest file), $\text{StabilityScore} = 100.0$.

## Python Implementation Reference

```python
import math
from typing import Dict, Any, Tuple

def _calc_raw_temporal_signals(self, temp: Dict[str, Any]) -> Tuple[float, float]:
    """Calculates File Stability (Age score) and Raw Churn (Commit frequency)."""
    if not temp or not temp.get("is_git_tracked", False):
        return 50.0, 0.0 

    mtime = temp.get("mtime", 0.0)
    repo_min = temp.get("repo_min_time", mtime)
    repo_max = temp.get("repo_max_time", mtime)
    commits = temp.get("commit_count", 0)

    # Clamp the time difference to prevent negative values
    seconds_from_max = max(repo_max - mtime, 0.0)
    time_range = max(repo_max - repo_min, 1.0)

    # 1. Stability Score (0 = Newest/Active, 100 = Oldest Baseline)
    stability_ratio = seconds_from_max / time_range
    stability_score = min(stability_ratio * 100.0, 100.0)

    # 2. Raw Churn Frequency calculation
    age_weeks = max(seconds_from_max / 604800.0, 1.0) 
    raw_churn_freq = commits / math.sqrt(age_weeks)

    return stability_score, raw_churn_freq
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
