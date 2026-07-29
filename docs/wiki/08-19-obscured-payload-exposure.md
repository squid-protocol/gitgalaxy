# Obscured Payload Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Obfuscation & Evasion Risk (Malicious Intent Density)

**Summary:** Evaluates source code for obfuscation techniques, evasion patterns, and high-risk execution capabilities. The metric identifies modules that combine code hiding mechanisms (metaprogramming, reflection, bitwise operations, shadow imports, file extension mismatches) with high-risk capabilities (dynamic code execution, data exfiltration, safety bypasses).

**Risk Classification:**
* 🟦 **LOW (Score 0–19):** Explicit, standard code flow using standard imports, explicit typing, and transparent control paths.
* 🟨 **MODERATE (Score 40–59):** Standard reflection or metaprogramming in framework code, mitigated by documentation and safety checks.
* 🟥 **VERY HIGH (Score 80–100):** High obfuscation paired with execution/exfiltration intent, or active evasion indicators (e.g., extension mismatch).

---

## Inputs & Threat Vectors

Signals are grouped into two primary categories—Obfuscation and Intent:

| Threat Vector | Signal Key | Weight | Category | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Metaprogramming** | `sec_reflection_metaprogramming` | **5.0x** | Obfuscation | Dynamic evaluation, reflection, or proxy manipulation. |
| **Bitwise Ops** | `sec_bitwise_ops` | **2.0x** | Obfuscation | Complex bitwise masking or encoding structures. |
| **Dead Code** | `sec_dead_code` | **2.0x** | Obfuscation | Graveyard code or unused blocks used to hide payloads. |
| **Shadow Imports** | `sec_shadow_imports` | **10.0x** | Evasion | Dynamic or hidden module loading mechanisms. |
| **Extension Mismatch** | `sec_extension_mismatch` | **20.0x** | Evasion | Mismatch between file extension and actual format (strong evasion indicator). |
| **Homoglyphs** | `sec_homoglyphs` | **1.0x** | Obfuscation | Lookalike Unicode characters (forgiven in scientific libraries). |
| **Safety Bypasses** | `sec_safety_bypasses` | **3.0x** | Intent | Explicit suppression of runtime security or type checks. |
| **Exfiltration** | `sec_io` | **4.0x** | Intent | Unbounded network or filesystem output operations. |
| **High-Risk Exec** | `sec_high_risk_execution` | **5.0x** | Intent | Direct invocation of dynamic evaluation sinks (`eval`, `exec`, shell command execution). |
| **State Mutation** | `sec_state_mutation` | **3.0x** | Intent | Dynamic modification of core execution state. |
| **Hardcoded Secrets** | `sec_hardcoded_secrets` | **1.5x** | Intent | Embedded API keys, tokens, or credentials. |

---

## Metric Calculation & Safeguards

### 1. Biaxial Mass Grouping
Threat signals are grouped into Obfuscation Mass and Intent Mass:

$$\text{ObfuscationMass} = (\text{reflection} \times 5.0) + (\text{bitwise} \times 2.0) + (\text{dead\_code} \times 2.0) + (\text{shadow\_imports} \times 10.0) + (\text{extension\_mismatch} \times 20.0) + (\text{homoglyphs} \times 1.0)$$

$$\text{IntentMass} = (\text{safety\_bypasses} \times 3.0) + (\text{io} \times 4.0) + (\text{high\_risk\_exec} \times 5.0) + (\text{state\_mutation} \times 3.0) + (\text{secrets} \times 1.5)$$

### 2. Scientific & Cryptography Shields
* **Scientific Code Shield:** Scientific/math libraries naturally use complex symbols and high entropy. The obfuscation mass is divided by `1.0 + (scientific * 2.0)`.
* **Cryptography Shield:** Cryptographic implementations naturally exhibit high entropy. Mass is divided by `1.0 + (cryptography * 5.0)`.
* **Professionalism Quotient:** Well-documented code containing safety blocks (`doc * 0.5 + safety`) reduces threat mass: $\text{prof\_dampener} = 1.0 + (\text{docs\_and\_safety} \times 0.05)$.

### 3. Non-Paranoid Mode Filter & Contextual Drift
* If non-paranoid mode is active:
  * If obfuscation is present without intent, threat mass is scaled down to $5\%$ ($\times 0.05$).
  * If intent is present without obfuscation, threat mass is scaled down to $10\%$ ($\times 0.10$).
* **Contextual Drift Anomaly:** If local language drift significantly exceeds repository global drift ($\text{local\_drift} / \text{global\_drift} > 1.5$), threat mass is multiplied by the drift ratio.

### 4. Sigmoid Mapping
Density is computed against padded lines of code ($\text{LOC} + 150$) and mapped through a sigmoid curve:

$$\text{Density} = \left( \frac{\text{TotalThreatMass}}{\max(\text{LOC} + 150, 1)} \right) \times 100.0$$

Standard mode uses a threshold of $15.0$ and slope of $1.0$; paranoid mode uses a threshold of $2.0$ and slope of $1.5$.

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements the obscured payload exposure metric:

```python
def _calc_obscured_payload(
    self,
    loc: int,
    raw_signals: dict[str, int],
    mp: float,
    archetype: str,
    global_drift: float,
    local_drift: float,
) -> float:
    """
    Calculates Obscured Payload Exposure (Malicious Intent Density).
    """
    arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
    arch_multiplier = arch_matrix.get("obscured_payload_multiplier", 1.0)

    obfuscation_indicators = (raw_signals.get("sec_reflection_metaprogramming", 0) * 5.0) + (
        raw_signals.get("sec_bitwise_ops", 0) * 2.0
    )
    malicious_payload = raw_signals.get("sec_safety_bypasses", 0) * 3.0
    exfiltration = raw_signals.get("sec_io", 0) * 4.0
    rce_indicators = raw_signals.get("sec_high_risk_execution", 0) * 5.0
    state_corruption = raw_signals.get("sec_state_mutation", 0) * 3.0
    dead_code_threat = raw_signals.get("sec_dead_code", 0) * 2.0
    secrets = raw_signals.get("sec_hardcoded_secrets", 0) * 1.5

    evasion_indicators = (raw_signals.get("sec_shadow_imports", 0) * 10.0) + (
        raw_signals.get("sec_extension_mismatch", 0) * 20.0
    )
    homoglyph_threat = raw_signals.get("sec_homoglyphs", 0) * 1.0

    obfuscation_mass = obfuscation_indicators + dead_code_threat + evasion_indicators + homoglyph_threat
    intent_mass = malicious_payload + exfiltration + rce_indicators + state_corruption + secrets

    # Scientific shield dampener
    science_dampener = 1.0 + (raw_signals.get("scientific", 0) * 2.0)
    obfuscation_mass = obfuscation_mass / science_dampener

    total_threat_mass = (obfuscation_mass + intent_mass) * arch_multiplier

    if total_threat_mass == 0:
        return 0.0

    if not getattr(self, "is_paranoid", False):
        if obfuscation_mass > 0 and intent_mass == 0:
            total_threat_mass *= 0.05
        elif intent_mass > 0 and obfuscation_mass == 0:
            total_threat_mass *= 0.10

    # Contextual drift anomaly check
    if local_drift > 0 and global_drift > 0:
        drift_delta = local_drift / global_drift
        if drift_delta > 1.5:
            total_threat_mass *= drift_delta

    # Documentation and safety dampener
    docs_and_safety = (raw_signals.get("doc", 0) * 0.5) + raw_signals.get("safety", 0)
    prof_dampener = 1.0 + (docs_and_safety * 0.05)
    crypto_dampener = 1.0 + (raw_signals.get("cryptography", 0) * 5.0)

    total_threat_mass = (total_threat_mass / prof_dampener) / crypto_dampener

    t = self.risk_tuning.get("obscured_payload", {})
    density = (total_threat_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

    if getattr(self, "is_paranoid", False):
        threshold = t.get("paranoid_threshold", 2.0)
        slope = t.get("paranoid_slope", 1.5)
    else:
        threshold = t.get("std_threshold", 15.0)
        slope = t.get("std_slope", 1.0)

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
