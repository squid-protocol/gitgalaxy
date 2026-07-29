# Specification Alignment Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Architectural Traceability (Specification Alignment)

**Summary:** Measures the gap between executable logic entities (classes and functions) and formal architectural specifications, design documents, or RFC references. Higher spec exposure hits lead to lower risk scores; conversely, modules with numerous functions/classes lacking specification references produce high risk exposure scores ("untraced logic").

**Risk Classification:**
* 🟦 **VERY LOW (Score 0–19):** Fully traceable code. Virtually all functions and classes map to formal design specifications or RFC markers.
* 🟨 **MODERATE (Score 40–59):** Partial traceability. Core functions reference specs while supporting functions do not.
* 🟥 **VERY HIGH (Score 80–100):** Untraced logic. High-volume execution logic without architectural specification linkage.

---

## Inputs & Detection Signals

The analysis engine tallies code structural entities against specification annotations:

| Variable | Signal Category | Role | Description |
| :--- | :--- | :--- | :--- |
| `func_start` | Entity Counter | Denominator Component | Count of function definition starts in the file. |
| `class_start` | Entity Counter | Denominator Component | Count of class definition starts in the file. |
| `spec_exposure` | Specification Hits | Traceability Counter | Count of explicit specification annotations, RFC links, or design doc references. |
| `mp` | Path Modifier | Multiplier | Context modifier adjusting final exposure risk. |

---

## Metric Calculation

The calculation evaluates the ratio of specification hits to total code entities and inverts it to yield risk exposure:

### 1. Code Entity Tally
Sum total structural entities (functions + classes), enforcing a floor of 1:

$$\text{Entities} = \max(\text{func\_start} + \text{class\_start}, 1)$$

### 2. Traceability Ratio
Divide specification hits by total entities, clamped at a maximum ratio of 1.0:

$$\text{Ratio} = \min\left( \frac{\text{spec\_exposure}}{\text{Entities}}, 1.0 \right)$$

### 3. Inverse Risk Exposure Mapping
Invert the traceability ratio so that 100% specification alignment yields 0 risk, modified by $Mp$:

$$\text{Exposure} = \min((1.0 - \text{Ratio}) \times 100.0 \times Mp, 100.0)$$

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements the specification alignment metric:

```python
def _calc_spec_alignment(self, raw_signals: dict[str, int], mp: float) -> float:
    """
    Calculates Architectural Traceability (Specification Alignment Exposure).
    Returns exposure risk score from 0.0 to 100.0.
    """
    entities = max(raw_signals.get("func_start", 0) + raw_signals.get("class_start", 0), 1)
    ratio = min(raw_signals.get("spec_exposure", 0) / entities, 1.0)
    return min((1.0 - ratio) * 100.0 * mp, 100.0)
```

---

### Ecosystem References

* **[Signal Processor Module](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)** - Metric implementation details.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository architecture dashboard.

---

**[⬅️ Back to Master Index](index.md)**
