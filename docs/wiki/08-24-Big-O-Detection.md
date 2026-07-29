# Algorithmic DoS & Big-O Detection

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Algorithmic Denial of Service (DoS) Risk & Algorithmic Complexity

**Summary:** Performance and algorithmic complexity directly impact application security. Deeply nested loops ($O(N^2)$, $O(N^3)$) or exponential recursion ($O(2^N)$) connected to public API endpoints, network I/O, or database queries present severe Algorithmic Denial of Service (DoS) vulnerabilities. GitGalaxy evaluates function nesting depth and correlates it with public exposure and data operations.

**Risk Classification:**
* 🟦 **VERY LOW (Score 0–19):** Linear $O(N)$ execution or safely bounded stream iterations.
* 🟨 **INTERMEDIATE (Score 40–59):** Isolated $O(N^2)$ logic guarded by safety bailouts or low exposure.
* 🟥 **VERY HIGH (Score 80–100):** Recursive $O(2^N)$ or $O(N^3)$ loops directly wired into unauthenticated public API routes, I/O operations, or state-mutating database calls.

---

## Inputs & Detection Signals

The engine analyzes function complexity depth, choke point multipliers, database gravity, and guardrail mitigations:

| Variable | Signal Focus | Role / Multiplier | Description |
| :--- | :--- | :--- | :--- |
| `big_o_depth` | Algorithmic Depth | **Exponential Base** | Evaluates nesting depth. $O(N)$ ($\text{depth} < 2$) is ignored. $O(N^2)$ yields base threat of $4$; $O(N^3)$ yields base threat of $9$. |
| `api` / `io` | Choke Points | **Additive Multiplier** | Functions exposed to public APIs or network I/O act as weaponizable triggers. |
| `db_complexity` | Database Gravity | **Additive Multiplier** | Heavy loops paired with database queries generate severe locking and latency risks ($1.0 + \text{DBComplexity} \times 0.5$). |
| `state_mutation` / `globals` | State Mutation | **Additive Multiplier** | Mutating state inside high-depth loops increases risk. |
| `safety` / `panics_and_aborts` | Guardrails | **0.5x Dampener** | Break statements, return limits, and try/catch blocks reduce function threat mass by $50\%$. |
| `popularity` | Network Posture | **0.1x – 3.0x** | Repository-wide import popularity scales the final threat mass. Safely isolated orphans are scaled to $0.10$. |

---

## Metric Calculation

The calculation proceeds through function threat evaluation, environmental amplification, guardrail mitigation, and network posture scaling:

### 1. Function Base Threat & Amplifiers
For each function with nesting depth $\ge 2$:

$$\text{BaseThreat} = \text{big\_o\_depth}^2$$
$$\text{GravityMultiplier} = 1.0 + (\text{db\_complexity} \times 0.5)$$
$$\text{ChokeMultiplier} = 1.0 + \text{api\_hits} + \text{io\_hits} + \text{flux\_hits}$$
$$\text{FuncThreat} = \text{BaseThreat} \times \text{GravityMultiplier} \times \text{ChokeMultiplier}$$

### 2. Guardrail Mitigation
If safety guardrails (`safety`, `panics_and_aborts`, `cleanup`) exist within the function, threat mass is halved:

$$\text{FuncThreat} = \text{FuncThreat} \times 0.5$$

### 3. Total Threat Mass & Network Posture
Sum all function threat scores to yield `dos_mass`. Then apply the network posture (popularity) multiplier:

$$\text{network\_multiplier} = \begin{cases} 0.10 & \text{if } \text{popularity} = 0 \text{ and } \text{api} = 0 \\ \min(1.0 + \frac{\ln(1 + \text{popularity})}{5.0}, 3.0) & \text{if } \text{popularity} > 0 \\ 1.0 & \text{otherwise} \end{cases}$$

$$\text{TotalThreatMass} = \text{dos\_mass} \times \text{network\_multiplier}$$

### 4. Sigmoid Mapping
Compute density per padded line of code ($\text{LOC} + 150$) and map via Sigmoid (Base threshold = 15.0, slope = 0.3):

$$\text{Density} = \left( \frac{\text{TotalThreatMass}}{\max(\text{LOC} + 150, 1)} \right) \times 100.0$$
$$\text{FinalScore} = \min(\text{Sigmoid}(\text{Density}, \text{Threshold}=15.0, \text{Slope}=0.3) \times 100.0 \times Mp, 100.0)$$

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements algorithmic DoS and Big-O detection:

```python
def _calc_algorithmic_dos(
    self,
    loc: int,
    raw_signals: dict[str, int],
    mp: float,
    functions: list[dict[str, Any]],
    popularity: int,
) -> float:
    """
    Calculates Algorithmic DoS Exposure based on Big-O depth, data gravity, and network choke points.
    """
    if not functions:
        return 0.0

    dos_mass = 0.0

    for func in functions:
        depth = func.get("big_o_depth", 1)
        # 1. Ignore O(N) linear loops
        if depth < 2:
            continue

        # 2. Base Threat (Exponential decay of performance)
        func_threat = float(depth**2)

        # 3. Data Gravity & Network Choke Points
        db_complex = func.get("db_complexity", 0)
        if db_complex > 0:
            func_threat *= 1.0 + (db_complex * 0.5)

        hv = func.get("hit_vector", {})
        api_hits = hv.get("api", 0)
        io_hits = hv.get("io", 0) + hv.get("sec_io", 0)
        flux_hits = hv.get("state_mutation", 0) + hv.get("globals", 0)

        choke_multiplier = 1.0 + api_hits + io_hits + flux_hits
        func_threat *= choke_multiplier

        # 4. Structural Dampeners (Guardrails)
        safety_hits = hv.get("safety", 0) + hv.get("panics_and_aborts", 0) + hv.get("cleanup", 0)
        if safety_hits > 0:
            func_threat *= 0.5  # 50% reduction for bounded iteration

        dos_mass += func_threat

    if dos_mass == 0.0:
        return 0.0

    # 5. Network Posture (Blast Radius)
    network_multiplier = 1.0
    if popularity == 0 and raw_signals.get("api", 0) == 0:
        network_multiplier = 0.10  # Safely isolated orphan
    elif popularity > 0:
        network_multiplier = min(1.0 + (math.log1p(popularity) / 5.0), 3.0)

    total_threat_mass = dos_mass * network_multiplier

    # 6. The Sigmoid Curve
    t = self.risk_tuning.get("algorithmic_dos", {})
    density = (total_threat_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

    threshold = t.get("threshold_base", 15.0)
    slope = t.get("sigmoid_slope", 0.3)

    try:
        score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
    except OverflowError:
        score = 100.0 if density > threshold else 0.0

    return min(score * mp, 100.0)
```

---

### Ecosystem References

* **[Signal Processor Module](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)** - Metric implementation details.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository architecture dashboard.

---

**[⬅️ Back to Master Index](index.md)**