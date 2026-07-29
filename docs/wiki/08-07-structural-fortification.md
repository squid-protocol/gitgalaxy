# Structural Fortification (Safety Exposure)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Ratio of Defensive Controls to Execution Stressors
>
> **Summary:** Evaluates how well source files are protected by defensive programming practices. It balances risk triggers (such as unsafe execution, type-suppression, and mutable state) against defensive controls (such as `try/catch` error handling, type guards, and test assertions).
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **VERY LOW (Score 0-19):** Highly Fortified. Defensive controls (`try/catch`, type guards) comfortably exceed execution stressors.
> * 🟨 **INTERMEDIATE (Score 40-59):** Stable. Execution stressors and defensive controls are in equilibrium.
> * 🟥 **VERY HIGH (Score 80-100):** Fragile / High Exposure. Execution stressors significantly exceed defensive controls, leaving code vulnerable to runtime failures.

## Metric Inputs (Risk Triggers vs. Defensive Controls)

Heuristic signals are categorized into **Execution Stressors** (Risk Signals) and **Defensive Controls** (Safety Signals), weighted by their structural impact:

| Input Variable | Syntax Patterns | Weight | Category | Structural Role |
| :--- | :--- | :--- | :--- | :--- |
| `danger_hits` | `eval`, `exec`, unsafe pointer math | 4.0x | **Stressor** | **High Impact Risk.** Critical execution points exerting major runtime stress. |
| `safety_neg_hits` | `any`, `@ts-ignore`, explicit bypasses | 1.5x | **Stressor** | **Type Evasions.** Anti-patterns that bypass type-checking or safety mechanisms. |
| `flux_hits` | Mutated global/local state | 0.5x | **Stressor** | **State Friction.** Mutable state operations that increase runtime variability. |
| `safety_hits` | `try/catch`, guard clauses, bounds checks | 1.0x | **Control** | **Runtime Safety.** Explicit exception handling and input validation boundaries. |
| `test_hits` | `describe`, `assert`, `expect` | 0.5x | **Control** | **Test Proximity.** Inline assertions or test coverage providing verification. |
| `doc_hits` | JSDoc, docstrings, typed comments | 0.1x | **Control** | **Contextual Documentation.** Inline documentation offering mild clarity value. |

## Universal Framework Integration

Standard environmental parameters govern safety calculations:

* **$Fc$ (Fidelity Coefficient):** Applied to **Defensive Controls**. Explicit languages (e.g., Java, Rust) receive higher defensive fidelity weighting than implicit scripting languages (e.g., Shell, Perl).
* **$Irc$ (Implicit Risk Correction):** Added to **Execution Stressors**. Implicit languages start with a baseline opacity risk tax.
* **$Mp$ (Path Modifier):** Contextual directory multiplier applied to stressors:
  * *Test/Experimental Files ($Mp = 0.9$):* Slight discount, though high danger signals remain highlighted.
  * *Core Infrastructure ($Mp = 1.2$):* Amplified penalty where lack of defensive controls is unacceptable.

## Mathematical Formulation

The metric evaluates Net Exposure using Laplace Smoothing ($LOC + 20.0$) to stabilize scores for small files:

### Step 1: Zero-Risk Shortcut
If total weighted execution stressors equal `0`, the calculation immediately short-circuits and returns a score of `0.0`.

### Step 2: Calculate Laplace-Smoothed Densities
Stressors and controls are normalized using a smoothed line count ($LOC + 20.0$):

$$\text{SmoothedLOC} = \max(\text{LOC}, 1) + 20.0$$
$$\text{StressorDensity} = \left(\frac{\text{WeightedStressors} + Irc}{\text{SmoothedLOC}}\right) \times Mp$$
$$\text{ControlDensity} = \left(\frac{\text{WeightedControls}}{\text{SmoothedLOC}}\right) \times Fc$$

### Step 3: Net Exposure & Systems Buffer
Defensive controls are subtracted from execution stressors. An additional system buffer is subtracted for implicit languages ($Fc < 1.0$):

$$\text{NetExposure} = (\text{StressorDensity} - \text{ControlDensity}) - \text{SystemsBuffer}$$

### Step 4: Sigmoid Scoring & Breach Floor
Net Exposure is mapped through a Sigmoid function (slope $= 12.0$):

$$\text{RawScore} = \frac{100.0}{1 + e^{-12.0 \times \text{NetExposure}}}$$

If danger signals (`danger_hits` or `safety_neg_hits`) exceed a minimum threshold density ($> 0.03$) and stressors outpace controls, a hard **Breach Floor** (up to 80.0) is enforced. This ensures high-risk execution cannot be masked simply by adding superficial comments.

## Python Implementation Reference

```python
import math
from typing import Dict

def _calc_safety(self, loc: int, eq: Dict[str, int], irc: int, fc: float, mp: float) -> float:
    safe_loc = max(loc, 1)
    t = self.risk_tuning.get("safety", {})

    # 1. Calculate Weighted Sums
    attack_hits = (eq.get("danger", 0) * t.get("danger_weight", 4.0)) + \
                  (eq.get("safety_neg", 0) * t.get("safety_neg_weight", 1.5)) + \
                  (eq.get("flux", 0) * t.get("flux_weight", 0.5))

    defense_hits = (eq.get("safety", 0) * self.WEIGHT_DEFENSE) + \
                   (eq.get("test", 0) * t.get("test_weight", 0.5)) + \
                   (eq.get("doc", 0) * t.get("doc_weight", 0.1))

    # Zero-Risk Shortcut
    if attack_hits == 0:
        return 0.0

    # 2. Laplace Smoothing (+20 LOC)
    smoothed_loc = safe_loc + t.get("laplace_smoothing", 20.0)

    attack = ((attack_hits + irc) / smoothed_loc) * mp
    defense = (defense_hits / smoothed_loc) * fc

    # 3. Net Exposure Calculation
    systems_buffer = t.get("systems_buffer", 0.25) if fc < 1.0 else 0.0
    net_exposure = (attack - defense) - systems_buffer

    # 4. Sigmoid Mapping
    try:
        score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 12.0) * net_exposure))
    except OverflowError:
        score = 100.0 if net_exposure > 0 else 0.0

    # 5. Breach Floor Enforcer for Undefended Risks
    danger_density = (eq.get("danger", 0) + eq.get("safety_neg", 0)) / safe_loc
    if danger_density > t.get("breach_density_min", 0.03) and attack > defense:
        floor = min(t.get("breach_floor_max", 80.0), 30.0 + (danger_density * t.get("breach_floor_mult", 500.0)))
        score = max(score, floor)

    return max(score, 0.0)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
