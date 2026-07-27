# Tech Debt Exposure

> **Metric: Density of Planned vs. Fragile Work Artifacts**
>
> **Summary:** Visualizes the "Topography of Compromise" within the knowledge graph. We view Technical Debt not as a failure, but as a deliberate engineering trade-off. No engineer writes a `HACK` out of laziness; they write it to ship. This metric is about **Honesty**. It relies on the developer's own annotations (in the comment stream) to identify where the "Structural Stress" lies. By visualizing these markers, we move from vague anxiety about "bad code" to a concrete map of where the team knows improvements are needed.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum.
> * 🟦 **VERY LOW (Score 0-19):** Polished. The code matches the spec. No known shortcuts.
> * 🟨 **INTERMEDIATE (Score 40-59):** Honest work-in-progress. A balanced mix of planned tasks.
> * 🟥 **VERY HIGH (Score 80-100):** Fractured. The file is held together by temporary fixes (`HACK`) and unfinished thoughts (`TODO`). It is structurally compromised.

## The Inputs (Heuristics)

The heuristic scanning has been entirely decoupled from the core deterministic engine. The static scanner pre-calculates these hits and passes them into the Signal Processor.

| Variable | Target Syntax | Weight | Structural Definition |
| :--- | :--- | :--- | :--- |
| `planned_debt_hits` | `TODO`, `WIP`, `STUB`, `REFACTOR` | 1.0x | **The Promise.** Future work that doesn't necessarily imply current brokenness. |
| `fragile_debt_hits` | `HACK`, `FIXME`, `XXX`, `UGLY` | 3.0x | **The Fracture.** An explicit admission that the current logic is fragile or dangerous. |
| `irc` | Implicit Language Penalty | 0.5x | **The Fog.** Implicit languages hide debt better, so we add a weighted baseline load to the stress sum. |

## Universal Framework Integration

* **$Fc$ (Fidelity Coefficient):** **Not Applied.** A `TODO` is a `TODO`, regardless of the language's type system.
* **$Irc$ (Implicit Risk Correction):** **Applied.** Added to the Stress Sum to account for language opacity.
* **$Mp$ (Path Modifier):** **Applied.**
  * *Archive/Legacy ($Mp = 0.5$):* Debt is expected here. Discount it.
  * *Scratchpad ($Mp = 0.8$):* Allow messy thoughts.
  * *Core/Kernel ($Mp = 1.2$):* Debt here is dangerous. Amplify it heavily.

## The Equation: The Structural Stress Density

We calculate the Density of Debt per line of code.

**Step A: Calculate Stress Sum**
We sum the markers, applying weights to distinguish "Planned Work" (Good Debt) from "Broken Logic" (Bad Debt). We also add the Implicit Risk Correction ($Irc$), dampened by its own weight multiplier ($0.5$).

$$Stress = (GoodDebt \times 1.0) + (BadDebt \times 3.0) + (Irc \times 0.5)$$

**Step B: Calculate Stress Density**
We normalize against the file size to calculate the stress points per 100 lines. A 1,000-line file with 1 `TODO` is fine. A 10-line file with 1 `HACK` is structurally critical.

$$Density = \left( \frac{Stress}{\max(LOC, 1)} \right) \times 100.0$$

**Step C: The Sigmoid Map & Path Modifier**
We use a Sigmoid function to create a "Tolerance Threshold". We tolerate ~5 points of stress per 100 lines before the score spikes. A gentle slope ($0.5$) allows for nuance as debt accumulates. Finally, we apply the Path Modifier ($Mp$).

$$RawScore = \frac{100}{1 + e^{-0.5 \times (Density - 5.0)}}$$
$$FinalScore = \min(RawScore \times Mp,\ 100)$$

## Implementation (Python Reference)

```python
import math
from typing import Dict

def _calc_tech_debt(self, loc: int, eq: Dict[str, int], irc: int, mp: float) -> float:
    t = self.risk_tuning.get("tech_debt", {})
    good_debt = eq.get("planned_debt", 0)
    bad_debt = eq.get("fragile_debt", 0)
    
    if good_debt == 0 and bad_debt == 0:
        return 0.0
    
    # Step A: Stress Sum
    stress = (good_debt * t.get("good_debt_weight", 1.0)) + \
             (bad_debt * t.get("bad_debt_weight", 3.0)) + \
             (irc * t.get("irc_weight", 0.5))
             
    # Step B: Density Calculation
    density = (stress / max(loc, 1)) * 100.0
    threshold = t.get("threshold", 5.0)
    
    # Step C: Sigmoid Map
    try:
        raw_score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.5) * (density - threshold)))
    except OverflowError:
        raw_score = 100.0 if density > threshold else 0.0
        
    # Step D: Apply Context Modifier
    return min(raw_score * mp, 100.0)

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
