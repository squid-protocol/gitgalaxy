# Graveyard Exposure (Dead & Commented-Out Code)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Dead Code Density & Inactive Logic Retention
>
> **Summary:** Measures the density of commented-out source code blocks ("dead code"). Commented-out logic adds cognitive noise for developers who must mentally parse and discard inactive code paths.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **CLEAN (Score 0-19):** Active, clean, executable code. Zero dead code detected.
> * 🟨 **INTERMEDIATE (Score 40-59):** Minor inactive snippets or temporary commented blocks.
> * 🟥 **HIGH GRAVEYARD RISK (Score 80-100):** Heavily polluted with dead code blocks requiring cleanup.

## Metric Inputs (Heuristic Dead Code Detection)

The static analysis engine differentiates between natural language documentation (English docstrings) and commented-out program code (syntax-dense comment blocks):

| Variable | Weight / Multiplier | Description |
| :--- | :--- | :--- |
| `graveyard_hits` | 3.0x lines / hit | Number of dead code block hits identified by the static analyzer. Estimated at 3 lines of inactive logic per hit. |
| `total_loc` | Denominator Floor | Total physical line count of the file. Measured against a minimum safe floor of 50 LOC. |

## Universal Framework Integration

* **$Fc$ (Fidelity Coefficient):** Not applied (dead code detection is language-agnostic).
* **$Irc$ (Implicit Risk Correction):** Not applied.
* **$Mp$ (Path Modifier):** Applied to the **Dynamic Tolerance Threshold**:
  * *Prototypes / Scratchpad ($Mp = 2.0$):* High tolerance for keeping inactive snippets while experimenting ($Mp > 1.0$ raises threshold).
  * *Legacy Archives ($Mp = 1.5$):* Moderate tolerance.
  * *Core Production Infrastructure ($Mp = 0.5$):* Strict low tolerance ($Mp < 1.0$ lowers threshold).

## Mathematical Formulation

### Step 1: Clean File Short-Circuit
If `graveyard_hits == 0`, the engine immediately returns a risk score of `0.0`.

### Step 2: Calculate Dead Code Density
Estimated inactive lines (`graveyard_hits` $\times 3.0$) are normalized against total LOC (using a safe minimum floor of 50 lines):

$$\text{GhostLines} = \text{graveyard\_hits} \times 3.0$$
$$\text{Density} = \left( \frac{\text{GhostLines}}{\max(\text{TotalLOC}, 50.0)} \right) \times 100.0$$

### Step 3: Compute Contextual Tolerance Threshold
A base tolerance threshold of 10% dead code density is adjusted by the directory Path Modifier ($Mp$):

$$\text{Threshold} = \frac{10.0}{\max(Mp, 0.1)}$$

### Step 4: Sigmoidal Score Mapping
Density maps to a 0–100 risk score using a Sigmoid curve (slope $= 0.3$):

$$\text{Score} = \frac{100.0}{1 + e^{-0.3 \times (\text{Density} - \text{Threshold})}}$$
$$\text{FinalScore} = \min(\text{Score}, 100.0)$$

## Python Implementation Reference

```python
import math
from typing import Dict

def _calc_graveyard(self, total_loc: float, raw_signals: Dict[str, int], mp: float) -> float:
    # Step 1: Clean File Short-Circuit
    hits = raw_signals.get("graveyard", 0)
    if hits == 0:
        return 0.0
        
    t = self.risk_tuning.get("graveyard", {})
    
    # Step 2: Calculate Dead Code Density
    ghost_lines = hits * t.get("hit_mult", 3.0)
    safe_floor = t.get("safe_mass_floor", 50.0)
    density = (ghost_lines / max(total_loc, safe_floor)) * 100.0
    
    # Step 3: Compute Contextual Tolerance Threshold 
    threshold = t.get("threshold_base", 10.0) / max(mp, 0.1) 
    
    # Step 4: Sigmoid Mapping
    try:
        score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.3) * (density - threshold)))
    except OverflowError:
        score = 100.0 if density > threshold else 0.0
        
    return min(score, 100.0)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
