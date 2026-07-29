# Memory Corruption Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

**Metric:** Memory Corruption Risk (Buffer Overflows, UAF, Unsafe Memory Management)

**Summary:** Measures exposure to low-level memory corruption vulnerabilities (e.g., Use-After-Free, buffer overflows, unmitigated pointer arithmetic, unsafe casting, inline assembly). This metric operates on an **Opt-In Whitelist** basis, evaluating only native unmanaged programming languages. Managed runtime languages bypass memory corruption calculations entirely.

**Risk Classification:**
* 🟦 **LOW (Score 0–19):** Safe memory management wrappers or managed runtimes (Python, JS, Java, Go, C#).
* 🟨 **MODERATE (Score 40–59):** Bounded pointer operations with explicit allocation and cleanup safety guards.
* 🟥 **VERY HIGH (Score 80–100):** High-density raw pointer arithmetic, inline assembly, or unmitigated memory allocations lacking bounds checking and free/cleanup routines.

---

## Language Opt-In Whitelist

Memory corruption calculation is strictly restricted to native unmanaged languages:

```python
native_memory_langs = {
    "c",
    "cpp",
    "objective-c",
    "rust",
    "zig",
    "assembly",
    "agc_assembly",
    "nim",
}
```

If the file language identifier is not in this whitelist, `_calc_memory_corruption` immediately returns `0.0`.

---

## Inputs & Detection Signals

For whitelisted languages, the analysis engine tallies raw memory heuristics against mitigation routines:

| Variable | Heuristic Signal | Weight | Description |
| :--- | :--- | :--- | :--- |
| `pointers` | `pointers` | **2.5x** | Raw pointer declarations and dereferencing operations (`*`, `->`, `&`). |
| `memory_alloc` | `memory_alloc` | **3.0x** | Dynamic memory allocation calls (`malloc`, `calloc`, `realloc`, `new`). |
| `inline_asm` | `inline_asm` | **5.0x** | Inline assembly blocks (`__asm__`, `asm`). |
| `explicit_casts` | `explicit_casts` | **1.5x** | Unsafe pointer conversions or explicit casting (`reinterpret_cast`). |
| `cleanup` | `cleanup` | **-1.0x** | Explicit memory deallocation calls (`free`, `delete`, destructor calls). |
| `safety` | `safety` | **-1.5x** | Bounds checking assertions, smart pointers, or safe wrappers. |

---

## Metric Calculation

### 1. Raw & Mitigation Mass
$$\text{RawMemoryMass} = (\text{pointers} \times 2.5) + (\text{allocations} \times 3.0) + (\text{inline\_asm} \times 5.0) + (\text{casts} \times 1.5)$$
$$\text{MitigationMass} = \text{cleanup} + (\text{safety} \times 1.5)$$

### 2. Net Risk Synthesis
$$\text{NetRisk} = \max(\text{RawMemoryMass} - \text{MitigationMass}, 0.0) \times \text{ArchetypeMultiplier}$$

If explicit threat signals (`sec_high_risk_execution`, `sec_safety_bypasses`, `sec_reflection_metaprogramming`) are zero and non-paranoid mode is active, net risk is scaled down to $5\%$ ($\times 0.05$).

### 3. Sigmoid Normalization
$$\text{Density} = \left( \frac{\text{NetRisk}}{\max(\text{LOC} + 150, 1)} \right) \times 100.0$$

Standard mode uses a threshold of $25.0$ and slope of $0.4$; paranoid mode uses a threshold of $4.0$ and slope of $0.8$.

---

## Reference Implementation

The following Python method from `gitgalaxy/metrics/signal_processor.py` implements the memory corruption exposure metric:

```python
def _calc_memory_corruption(
    self,
    loc: int,
    raw_signals: dict[str, int],
    mp: float,
    lang_id: str = "",
    archetype: str = "",
) -> float:
    """
    Calculates Memory Corruption Exposure (Buffer Overflows, UAF).
    Strictly Opt-In: Only applies to languages with manual memory/pointers.
    """
    arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
    arch_multiplier = arch_matrix.get("memory_corruption_multiplier", 1.0)

    native_memory_langs = {
        "c",
        "cpp",
        "objective-c",
        "rust",
        "zig",
        "assembly",
        "agc_assembly",
        "nim",
    }

    if lang_id.lower() not in native_memory_langs:
        return 0.0

    raw_memory_mass = (
        (raw_signals.get("pointers", 0) * 2.5)
        + (raw_signals.get("memory_alloc", 0) * 3.0)
        + (raw_signals.get("inline_asm", 0) * 5.0)
        + (raw_signals.get("explicit_casts", 0) * 1.5)
    )

    if raw_memory_mass == 0:
        return 0.0

    mitigation_mass = raw_signals.get("cleanup", 0) + (raw_signals.get("safety", 0) * 1.5)

    net_risk = max(raw_memory_mass - mitigation_mass, 0.0) * arch_multiplier

    explicit_threats = (
        raw_signals.get("sec_high_risk_execution", 0)
        + raw_signals.get("sec_safety_bypasses", 0)
        + raw_signals.get("sec_reflection_metaprogramming", 0)
    )
    if explicit_threats == 0 and not getattr(self, "is_paranoid", False):
        net_risk *= 0.05

    t = self.risk_tuning.get("memory_corruption", {})
    density = (net_risk / max(loc + t.get("loc_padding", 150), 1)) * 100.0

    if getattr(self, "is_paranoid", False):
        threshold = t.get("paranoid_threshold", 4.0)
        slope = t.get("paranoid_slope", 0.8)
    else:
        threshold = t.get("std_threshold", 25.0)
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
