# Injection Surface Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Injection Surface Risk (RCE, SQLi, XSS, Command Injection)

**Summary:** Measures exposure to injection attack vectors by analyzing external input boundaries (network requests, user input, SSR parameters) operating near dynamic execution sinks (`eval`, `exec`, shell command execution, dynamic SQL execution) without safety validation.

**Risk Classification:**
* 🟦 **LOW (Score 0–19):** Bounded and sanitized data flow. Network input is isolated from dynamic execution sinks.
* 🟨 **MODERATE (Score 40–59):** Input operations operating near dynamic evaluation in standard framework routes with framework safety nets.
* 🟥 **VERY HIGH (Score 80–100):** Unsanitized untrusted input directly reaching execution sinks (confirmed static taint path or direct SQL injection funnel).

---

## Inputs & Detection Signals

The analysis engine evaluates input vectors and execution vectors:

| Signal Category | Signal Key | Weight | Description |
| :--- | :--- | :--- | :--- |
| **Input Vector** | `sec_io` | **1.0x** | Network request handling, file reads, or public endpoint parameters. |
| **Input Vector** | `ssr_boundaries` | **2.0x** | Server-Side Rendering (SSR) boundaries handling external parameters. |
| **Execution Vector** | `sec_high_risk_execution` | **4.0x** | Dynamic evaluation calls (`eval`, `exec`, OS command execution). |
| **Execution Vector** | `sec_safety_bypasses` | **2.0x** | Security guardrail or type check suppressions. |
| **Taint Confirmation** | `sec_tainted_injection` | **+500.0 Spike** | Verified data flow path from input source to dynamic execution sink. |
| **SQLi Confirmation** | `sec_amplified_sql_injection` | **+500.0 Spike** | Spatial correlation ledger confirmation of public API invoking raw database sinks. |

---

## Metric Calculation & Safeguards

### 1. Vector Formulation
$$\text{InputVectors} = \text{sec\_io} + (\text{ssr\_boundaries} \times 2.0)$$
$$\text{ExecutionVectors} = (\text{sec\_high\_risk\_execution} \times 4.0) + (\text{sec\_safety\_bypasses} \times 2.0)$$

### 2. AI & Hardware Guardrails
* **LLM Orchestration Risk:** If AI orchestrator logic coexists with dynamic code execution (`sec_high_risk_execution > 0` and `llm_orchestrator > 0`), execution vectors are multiplied by $10.0$ and input vectors incremented by $+5.0$ (treating the AI output as an untrusted input vector).
* **Safe Agent & Hardware Dampener:** For standard scientific compute, local LLM inference, or hardware bridges, execution vectors are dampened:
  $$\text{agent\_dampener} = 1.0 + (\text{scientific} \times 2.0) + (\text{llm\_local\_compute} \times 2.0)$$
  $$\text{hardware\_dampener} = 1.0 + (\text{hardware\_bridge} \times 3.0)$$
  $$\text{ExecutionVectors} = \frac{\text{ExecutionVectors}}{\text{agent\_dampener} \times \text{hardware\_dampener}}$$

### 3. Injection Mass & Deterministic Spikes
$$\text{InjectionMass} = (\text{InputVectors} \times \text{ExecutionVectors}) \times \text{ArchetypeMultiplier}$$
* **Confirmed Taint Spike:** Adds $+500.0 \times \text{sec\_tainted\_injection}$.
* **Confirmed SQLi Spike:** Adds $+500.0 \times \text{sec\_amplified\_sql\_injection}$.

### 4. Sigmoid Mapping
$$\text{Density} = \left( \frac{\text{InjectionMass}}{\max(\text{LOC} + 150, 1)} \right) \times 100.0$$

Mapped via Sigmoid (Standard mode threshold = 40.0, slope = 0.4; Paranoid mode threshold = 3.0, slope = 1.2).

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements the injection surface metric:

```python
def _calc_injection_surface(self, loc: int, raw_signals: dict[str, int], mp: float, archetype: str) -> float:
    """
    Calculates Injection Surface Exposure (XSS, SQLi, RCE, Command Injection).
    """
    arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
    arch_multiplier = arch_matrix.get("injection_surface_multiplier", 1.0)

    input_vectors = raw_signals.get("sec_io", 0) + (raw_signals.get("ssr_boundaries", 0) * 2.0)
    execution_vectors = (raw_signals.get("sec_high_risk_execution", 0) * 4.0) + (
        raw_signals.get("sec_safety_bypasses", 0) * 2.0
    )

    # Prompt injection to execution check
    if raw_signals.get("sec_high_risk_execution", 0) > 0 and raw_signals.get("llm_orchestrator", 0) > 0:
        execution_vectors *= 10.0
        input_vectors += 5.0
    else:
        agent_dampener = (
            1.0 + (raw_signals.get("scientific", 0) * 2.0) + (raw_signals.get("llm_local_compute", 0) * 2.0)
        )
        execution_vectors = execution_vectors / agent_dampener

    hardware_dampener = 1.0 + (raw_signals.get("hardware_bridge", 0) * 3.0)
    execution_vectors = execution_vectors / hardware_dampener

    injection_mass = (input_vectors * execution_vectors) * arch_multiplier

    # Direct taint confirmation spike
    taint_confirmed = raw_signals.get("sec_tainted_injection", 0)
    if taint_confirmed > 0:
        injection_mass += taint_confirmed * 500.0

    # Spatial ledger SQL injection confirmation
    sql_injection_confirmed = raw_signals.get("sec_amplified_sql_injection", 0)
    if sql_injection_confirmed > 0:
        injection_mass += sql_injection_confirmed * 500.0

    if injection_mass == 0:
        return 0.0

    explicit_threats = raw_signals.get("sec_high_risk_execution", 0) + raw_signals.get("sec_io", 0)
    if (
        explicit_threats == 0
        and taint_confirmed == 0
        and sql_injection_confirmed == 0
        and not getattr(self, "is_paranoid", False)
    ):
        injection_mass *= 0.10

    t = self.risk_tuning.get("injection_surface", {})
    density = (injection_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

    if getattr(self, "is_paranoid", False):
        threshold = t.get("paranoid_threshold", 3.0)
        slope = t.get("paranoid_slope", 1.2)
    else:
        threshold = t.get("std_threshold", 40.0)
        slope = t.get("std_slope", 0.4)

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
