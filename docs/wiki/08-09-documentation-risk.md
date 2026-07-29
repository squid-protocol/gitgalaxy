# Documentation Risk Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Contextual Knowledge Debt & Undocumented Risk Density
>
> **Summary:** Evaluates documentation risk not by raw comment line counts, but by weighing the structural complexity of undocumented functions against existing inline comments, docstrings, and directory-level documentation (such as `README.md` or `ARCHITECTURE.md`). Risk is amplified for highly imported hub files (blast radius) and single-author files (bus factor risk).
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **VERY LOW (Score 0-19):** Fully Documented. Code is well-commented or protected under a comprehensive directory documentation shield.
> * 🟨 **INTERMEDIATE (Score 40-59):** Moderate. Standard code complexity with acceptable inline comments.
> * 🟥 **VERY HIGH (Score 80-100+):** Critical Exposure. Complex, highly-coupled, or single-author logic operating without documentation.

## The 4 Pillars of Documentation Risk Analysis

GitGalaxy evaluates documentation through four contextual dimensions:

### 1. Undocumented Logic Complexity
Instead of penalizing missing comments equally, the engine measures the structural complexity (`impact` score and `big_o_depth`) of undocumented functions. An undocumented monolithic $O(N^3)$ state machine generates high risk, whereas a simple 5-line utility function carries minimal risk.

### 2. Directory Documentation Shield
The directory resolver sweeps folders for "Knowledge Anchors" (such as `README.md` or `ARCHITECTURE.md`). If present, a `doc_umbrella` defense value is applied across the directory, accounting for high-level architectural documentation that explains lower-level inline code.

### 3. Markdown Formatting Density
Markdown files are parsed to evaluate instructional quality based on structural indicators:
* Code blocks (`lit_code_blocks`)
* Architecture diagrams (`lit_diagrams` e.g., Mermaid, PlantUML)
* Header structure (`lit_headers`)
* Cross-reference links (`lit_links`)

### 4. Blast Radius & Bus Factor Multipliers
The static analyzer integrates module coupling and author distribution metrics:
* **Network Blast Radius:** If an undocumented file is heavily imported across the repository, documentation risk is scaled upward.
* **Silo Risk (Bus Factor):** If a volatile, undocumented file is written primarily (e.g. $>95\%$) by a single author, the risk is further amplified to highlight single-developer knowledge silos.

## Universal Framework Integration

Documentation calculations incorporate standard language framework parameters:
* **$Fc$ (Fidelity Coefficient):** Explicit languages (e.g., Rust, Java) receive higher documentation fidelity scores than implicit scripting languages (e.g., Shell, Groovy).
* **$Irc$ (Implicit Risk Correction):** Added to baseline risk to account for higher syntactical ambiguity in implicit languages.

## Mathematical Formulation

### Step 1: Knowledge Shield Defense Calculation
Defensive mass combines inline docstrings, ownership tags, line counts, and directory umbrella shields, scaled by the Fidelity Coefficient ($Fc$):

$$\text{UmbrellaDefense} = \text{doc\_umbrella} \times 50.0$$
$$\text{DefenseHits} = \left( \text{InlineDocs} \times 1.0 + \text{Ownership} \times 0.5 + \text{DocLOC} \times 0.33 + \text{UmbrellaDefense} \right) \times Fc$$

### Step 2: Undocumented Risk Calculation
Raw risk sums exposed API endpoints, baseline opacity tax ($Irc$), and undocumented complex functions:

$$\text{UndocumentedRisk} = \sum_{\text{undocumented}} \left( 5.0 + (\ln(\text{Impact}) \times (\text{BigO} \times 0.5)) \right)$$
$$\text{RiskHits} = \text{UndocumentedRisk} + (\text{API\_Exposure} \times 2.0) + Irc$$

### Step 3: Net Exposure & Line Density
Net exposure balances risk against defense, normalized per line of code:

$$\text{NetExposure} = \max\left(0, \text{RiskHits} - \frac{\text{DefenseHits}}{2.0}\right)$$
$$\text{Density} = \left( \frac{\text{NetExposure}}{\max(\text{LOC}, 1)} \right) \times 100.0$$

### Step 4: Systemic Multipliers
Multipliers adjust for repository popularity (blast radius) and single-author concentration (bus factor):

$$\text{NetworkMultiplier} = 1.0 + \left(\frac{\text{Popularity}}{10.0}\right)$$
$$\text{SiloMultiplier} = 1.0 + \left(\frac{\text{SiloExposure}}{200.0}\right)$$
$$\text{FinalMultiplier} = \text{NetworkMultiplier} \times \text{SiloMultiplier} \times Mp$$

### Step 5: Sigmoidal Risk Mapping
Density maps to a 0–100 risk score using a Sigmoid curve (threshold $= 10.0$, slope $= 0.2$), multiplied by the systemic modifiers:

$$\text{RawRisk} = \frac{100.0}{1 + e^{-0.2 \times (\text{Density} - 10.0)}}$$
$$\text{FinalRisk} = \min(\text{RawRisk} \times \text{FinalMultiplier}, 100.0)$$

## Python Implementation Reference

```python
import math
from typing import Dict, List, Any

def _calc_documentation(
    self,
    loc: int,
    doc_loc: int,
    eq: Dict[str, int],
    fc: float,
    irc: int,
    mp: float,
    functions: List[Dict[str, Any]] = None,
    doc_umbrella: float = 0.0,
    popularity: int = 0,
    silo_exposure: float = 0.0
) -> float:
    t = self.risk_tuning.get("documentation", {})
    
    # 1. Knowledge Shield Defense Calculation
    umbrella_defense = doc_umbrella * 50.0 
    
    defense_hits = (
        (eq.get("doc", 0) * t.get("doc_weight", 1.0))
        + (eq.get("ownership", 0) * t.get("ownership_weight", 0.5))
        + (doc_loc * t.get("doc_loc_weight", 0.33))
        + umbrella_defense
    ) * fc
    
    # 2. Undocumented Function Risk Calculation
    kinetic_blindness = 0.0
    api_exposure = eq.get("api", 0) * 2.0
    
    if functions:
        for func in functions:
            impact = func.get("impact", 0.0)
            big_o = func.get("big_o_depth", 1)
            
            # Penalize undocumented complex functions
            if (impact > 50.0 or big_o >= 3) and not func.get("docstring"):
                kinetic_blindness += 5.0 + (math.log1p(impact) * (big_o * 0.5))

    risk_hits = kinetic_blindness + api_exposure + irc

    # 3. Density Calculation
    net_exposure = max(0.0, risk_hits - (defense_hits / 2.0))
    density = (net_exposure / max(loc, 1)) * 100.0

    # 4. Systemic Multipliers (Blast Radius & Bus Factor)
    network_multiplier = 1.0 + (popularity / 10.0)
    silo_multiplier = 1.0 + (silo_exposure / 200.0)
    
    final_multiplier = network_multiplier * silo_multiplier * mp
    threshold = t.get("threshold_base", 10.0)
    
    # 5. Sigmoid Risk Curve
    try:
        raw_risk = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.2) * (density - threshold)))
    except OverflowError:
        raw_risk = 100.0 if density > threshold else 0.0

    return min(raw_risk * final_multiplier, 100.0)
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**