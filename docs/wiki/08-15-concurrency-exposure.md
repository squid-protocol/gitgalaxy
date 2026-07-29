# Concurrency Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Concurrency Exposure & Thread Starvation Risk

**Summary:** Evaluates the density of asynchronous execution primitives, multithreading logic, and potential thread starvation within a source file. Concurrent programming increases non-deterministic execution paths, raising cognitive load and introducing risks such as race conditions, deadlocks, and resource contention.

**Risk Classification:**
* 🟦 **LOW (Score 0–19):** Sequential execution. Logic runs deterministically with minimal or no asynchronous branching.
* 🟨 **MODERATE (Score 40–59):** Standard asynchronous operations (e.g., standard `async`/`await` patterns or thread management) with bounded execution.
* 🟥 **VERY HIGH (Score 80–100):** High-density multithreading, unmitigated concurrency channels, or concurrent functions containing high algorithmic complexity (potential thread starvation).

---

## Inputs & Detection Signals

The static analysis engine extracts concurrency keywords and synchronization primitives across supported language standards:

| Variable | Signal Category | Weight / Role | Description |
| :--- | :--- | :--- | :--- |
| `raw_concurrency` | Keywords | **1.0x** | Asynchronous and threading constructs: `async`, `await`, `Promise`, `thread`, `spawn`, `go`, `chan`, `synchronized`. |
| `sync_locks` | Mitigations | **-1.5x** | Synchronization primitives (mutexes, locks, semaphores). Each lock mitigates 1.5 thread spawns. |
| `starvation_multiplier` | Resource Guard | **1.0x – 5.0x** | Escalates risk if concurrent functions contain $O(N^2)$, $O(N^3)$, or recursive logic. |
| `loc` | Denominator | **Base Density** | Meaningful lines of code, padded by `loc_padding` (default 150). |
| `irc` | Language Modifier | **0.1x** | Implicit Risk Correction for dynamically typed or implicit concurrency models. |
| `mp` | Path Modifier | **Threshold Modifier** | Context-specific modifier (e.g., `0.5` for UI components where race conditions trigger UI defects). |

---

## Metric Calculation

The calculation balances raw concurrency against synchronization locks, evaluates resource exhaustion risk, and applies a sigmoid transformation.

### 1. Net Concurrency Balance
Subtract synchronization primitives from raw concurrency signals:

$$\text{net\_concurrency} = \max(0.0, \text{raw\_concurrency} - (\text{sync\_locks} \times 1.5))$$

If $\text{net\_concurrency} = 0$, the metric immediately returns $0.0$.

### 2. Thread Starvation Multiplier
Inspects individual functions to identify high-complexity loops operating within concurrent contexts:
* **Recursive Functions:** Sets `starvation_multiplier` to $5.0$.
* **$O(N^3)$ or Higher Complexity:** Sets `starvation_multiplier` to $4.0$.
* **$O(N^2)$ Complexity:** Sets `starvation_multiplier` to $2.0$.

### 3. Density Calculation
Density measures concurrent logic per line of code, factoring in implicit language risk ($\text{IRC} \times 0.1$):

$$\text{Density} = \left( \frac{\text{net\_concurrency} \times \text{starvation\_multiplier}}{\max(\text{LOC} + \text{loc\_padding}, 1)} \right) \times 100.0 + (\text{IRC} \times 0.1)$$

### 4. Sigmoid Transformation
Maps density to a 0–100 score using a base threshold of $4.0$ and slope of $0.4$, scaled by the path modifier ($Mp$):

$$\text{RawScore} = \frac{1.0}{1.0 + e^{-0.4 \times (\text{Density} - 4.0)}}$$
$$\text{FinalScore} = \min(\text{RawScore} \times 100.0 \times Mp, 100.0)$$

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements the concurrency exposure metric:

```python
def _calc_concurrency(
    self,
    loc: int,
    raw_signals: dict[str, int],
    irc: int,
    mp: float,
    functions: Optional[list[dict[str, Any]]] = None,
) -> float:
    """
    Calculates Concurrency Exposure & Thread Starvation Risk.
    """
    tuning = self.risk_tuning.get("concurrency", {})
    loc_padding = tuning.get("loc_padding", 150)

    raw_concurrency = float(raw_signals.get("concurrency", 0))
    sync_locks = float(raw_signals.get("sync_locks", 0))

    # Resource exhaustion guard
    starvation_multiplier = 1.0
    if functions:
        for func in functions:
            if func.get("hit_vector", {}).get("concurrency", 0) > 0:
                big_o = func.get("big_o_depth", 1)
                is_rec = func.get("is_recursive", False)
                if is_rec:
                    starvation_multiplier = max(starvation_multiplier, 5.0)
                elif big_o >= 3:
                    starvation_multiplier = max(starvation_multiplier, 4.0)
                elif big_o == 2:
                    starvation_multiplier = max(starvation_multiplier, 2.0)

    # Balance concurrency with synchronization locks
    net_concurrency = max(0.0, raw_concurrency - (sync_locks * 1.5))

    if net_concurrency == 0:
        return 0.0

    density = ((net_concurrency * starvation_multiplier) / max(loc + loc_padding, 1)) * 100.0
    density += irc * tuning.get("irc_mult", 0.1)

    threshold = tuning.get("threshold_base", 4.0)
    slope = tuning.get("sigmoid_slope", 0.4)

    return min(self._sigmoid(density, threshold, slope) * 100.0 * mp, 100.0)
```

---

### Ecosystem References

* **[Signal Processor Module](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)** - Metric implementation details.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository architecture dashboard.

---

**[⬅️ Back to Master Index](index.md)**
