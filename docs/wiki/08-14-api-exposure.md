# API Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Public API Surface Area & Export Ratio
>
> **Summary:** Measures the permeability of a module's public boundary by comparing exported public endpoints to total declared entities (functions + classes). It allows developers to distinguish encapsulated internal helpers from heavily exposed public interfaces.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **VERY LOW (Score 0-19):** Encapsulated Vault. Internal utility module with no public export surface.
> * 🟨 **MODERATE (Score 40-59):** Balanced API. Balanced mix of public methods and internal private helpers.
> * 🟥 **VERY HIGH (Score 80-100):** Public Entry Point. Exposes a large volume of public functions/classes to external consumers.

## Metric Inputs (Surface Detection)

The engine compares exported **Public Signatures** against **Total Entities** (functions + classes) to compute exposure:

| Input Variable | Regex Key / Target | Weight | Description |
| :--- | :--- | :--- | :--- |
| `api_hits` | `api` | **Numerator** | Export keywords (`export`, `public`, `module.exports`) or export conventions (Go/Python capitalization). |
| `Entities` | `func_start` + `class_start` | **Denominator** | Total declared logical entities (Functions + Classes) ensuring accurate ratios across structural paradigms. |

## Universal Framework Integration

* **$Fc$ (Fidelity Coefficient):** Not applied (public exports are language-agnostic syntactical facts).
* **$Irc$ (Implicit Risk Correction):** Not applied.
* **$Mp$ (Path Modifier):** Contextual multiplier applied to score:
  * *Public API Endpoints (`api/`, `controllers/`, $Mp = 1.2$):* Amplified sensitivity to highlight intended public boundaries.
  * *Internal Utilities (`internal/`, `helpers/`, $Mp = 0.8$):* Dampened sensitivity to reduce background noise unless exports leak unexpectedly.

## Mathematical Formulation

API exposure combines the public export ratio (40% weight) with logarithmic endpoint volume (60% weight):

### Step 1: Encapsulation Short-Circuit
If `api_hits == 0`, the file is fully internal/encapsulated and returns a score of `0.0`.

### Step 2: Exposure Ratio Calculation (40% Weight)
The proportion of exported entities relative to total declared entities is computed and clamped to $\le 1.0$:

$$\text{Entities} = \max(\text{func\_start} + \text{class\_start}, 1)$$
$$\text{Ratio} = \min\left( \frac{\text{api\_hits}}{\text{Entities}}, 1.0 \right)$$

### Step 3: Logarithmic Volume Calculation (60% Weight)
To reflect the higher structural surface area of modules with dozens of endpoints, a logarithmic volume weight is computed and clamped to $\le 1.0$:

$$\text{VolumeWeight} = \min\left( \frac{\log_{10}(\text{api\_hits} + 1)}{1.5}, 1.0 \right)$$

### Step 4: Compound Score & Path Modifier
Ratio and volume weights are combined (0.4 and 0.6 weights), scaled to 100.0, and multiplied by the Path Modifier ($Mp$):

$$\text{RawScore} = \left( (\text{Ratio} \times 0.4) + (\text{VolumeWeight} \times 0.6) \right) \times 100.0$$
$$\text{FinalScore} = \min(\text{RawScore} \times Mp, 100.0)$$

## Python Implementation Reference

```python
import math
from typing import Dict

def _calc_api_exposure(self, raw_signals: Dict[str, int], total_loc: int, popularity: int = 0) -> float:
    # Step 1: Encapsulation Short-Circuit
    api_hits = raw_signals.get("api", 0)
    if api_hits == 0:
        return 0.0

    t = self.risk_tuning.get("api_exposure", {})
    entities = max(raw_signals.get("func_start", 0) + raw_signals.get("class_start", 0), 1)

    # Step 2: Exposure Ratio (40% Weight)
    ratio = min(api_hits / float(entities), 1.0)

    # Step 3: Logarithmic Volume (60% Weight)
    volume_weight = min(math.log10(api_hits + 1) / t.get("log_divisor", 1.5), 1.0)

    # Step 4: Compound Score Calculation
    raw_score = ((ratio * t.get("ratio_weight", 0.4)) + (volume_weight * t.get("volume_weight", 0.6))) * 100.0

    mp = raw_signals.get("multipliers", {}).get("api_exposure", 1.0)
    return min(raw_score * mp, 100.0)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
