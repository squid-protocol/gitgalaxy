# Tech Debt Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Density of Planned vs. Fragile Work Markers
>
> **Summary:** Measures technical debt density using developer code annotations (`TODO`, `FIXME`, `HACK`, `XXX`). It differentiates between planned pending work (`TODO`, `WIP`) and admitted logic fragility (`HACK`, `FIXME`), calculating a weighted stress score normalized per 100 lines of code.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **VERY LOW (Score 0-19):** Polished. Code aligns with expectations with no active debt annotations.
> * 🟨 **INTERMEDIATE (Score 40-59):** Active Development. A moderate density of planned task markers.
> * 🟥 **VERY HIGH (Score 80-100):** High Risk. High density of fragile fixes (`HACK`, `FIXME`) and unfinished stubs (`TODO`).

## Metric Inputs (Heuristic Comment Scanning)

The static analysis engine pre-scans comment tokens and passes hit counts to the Signal Processor:

| Input Variable | Target Markers | Weight | Description |
| :--- | :--- | :--- | :--- |
| `planned_debt_hits` | `TODO`, `WIP`, `STUB`, `REFACTOR` | 1.0x | **Planned Work.** Tracked future tasks or temporary stubs. |
| `fragile_debt_hits` | `HACK`, `FIXME`, `XXX`, `UGLY` | 3.0x | **Fragile Fixes.** Explicit admissions that current code is fragile or buggy. |
| `irc` | Language Opacity Tax | 0.5x | **Implicit Language Penalty.** Baseline stress addition for implicit language syntax. |

## Universal Framework Integration

* **$Fc$ (Fidelity Coefficient):** Not applied (`TODO` comments carry equal semantic meaning across all languages).
* **$Irc$ (Implicit Risk Correction):** Applied to baseline stress sum to account for implicit syntax opacity.
* **$Mp$ (Path Modifier):** Contextual multiplier applied to final score:
  * *Legacy / Archive ($Mp = 0.5$):* Lower sensitivity (debt is expected in legacy code).
  * *Scratchpad / Prototypes ($Mp = 0.8$):* Moderate tolerance.
  * *Core Architecture ($Mp = 1.2$):* Amplified sensitivity (debt in core paths poses higher system risk).

## Mathematical Formulation

Technical debt density is calculated in four steps:

### Step 1: Stress Sum Calculation
Planned work and fragile logic markers are weighted and combined with the implicit risk correction ($Irc \times 0.5$):

$$\text{StressSum} = (\text{PlannedDebt} \times 1.0) + (\text{FragileDebt} \times 3.0) + (Irc \times 0.5)$$

### Step 2: Density Normalization
Stress is normalized per 100 lines of code to enable fair comparisons across files of varying size:

$$\text{Density} = \left( \frac{\text{StressSum}}{\max(\text{LOC}, 1)} \right) \times 100.0$$

### Step 3: Sigmoidal Threshold Mapping
The density is evaluated against a tolerance threshold ($\approx 5.0$ stress points per 100 lines) using a Sigmoid curve (slope $= 0.5$):

$$\text{RawScore} = \frac{100.0}{1 + e^{-0.5 \times (\text{Density} - 5.0)}}$$

### Step 4: Apply Path Modifier
The final score is adjusted by the directory Path Modifier ($Mp$) and clamped to 100.0:

$$\text{FinalScore} = \min(\text{RawScore} \times Mp, 100.0)$$

## Python Implementation Reference

```python
import math
from typing import Dict

def _calc_tech_debt(self, loc: int, eq: Dict[str, int], irc: int, mp: float) -> float:
    t = self.risk_tuning.get("tech_debt", {})
    good_debt = eq.get("planned_debt", 0)
    bad_debt = eq.get("fragile_debt", 0)
    
    # Shortcut for clean files
    if good_debt == 0 and bad_debt == 0:
        return 0.0
    
    # Step A: Stress Sum
    stress = (good_debt * t.get("good_debt_weight", 1.0)) + \
             (bad_debt * t.get("bad_debt_weight", 3.0)) + \
             (irc * t.get("irc_weight", 0.5))
             
    # Step B: Density Calculation (per 100 LOC)
    density = (stress / max(loc, 1)) * 100.0
    threshold = t.get("threshold", 5.0)
    
    # Step C: Sigmoid Curve Mapping
    try:
        raw_score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.5) * (density - threshold)))
    except OverflowError:
        raw_score = 100.0 if density > threshold else 0.0
        
    # Step D: Apply Context Path Modifier
    return min(raw_score * mp, 100.0)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**ter Index](index.md)**
