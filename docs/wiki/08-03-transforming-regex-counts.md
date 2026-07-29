# Normalizing Heuristic Regex Counts (Universal Exposure Framework)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

> **The Universal Exposure Framework**
>
> Raw static regex counts can be noisy or misleading if uncalibrated (for instance, being skewed by empty catch blocks or lacking full AST compiler context). To convert heuristic signals into actionable architecture metrics, GitGalaxy implements the Universal Exposure Framework (UEF), which processes raw occurrence counts through deterministic normalization transformations.

## The Four Stabilizing Principles

To mitigate false positives and count instability, the static analysis engine applies four core normalization principles:

* **Weighted Asymmetry (Defensive Multiplier):** Heuristic counters should not treat vulnerabilities and safeguards as equivalent 1:1 offsets ($1 - 1 = 0$). Securing complex logic requires greater effort than introducing flaws. The engine applies a **2.5x multiplier** to identified risk signals, requiring modules to exhibit strong defensive density before earning a "Defended" rating.
* **The Breach Cap (Zero-Trust Guardrail):** High test coverage or defensive comments must not hide severe architectural defects. If raw **Risk Hits** exceed **Guardrail Hits**, the module's safety rating is capped at "Fragile," overriding standard mathematical averages with a strict risk threshold.
* **Sigmoid Gating (Noise Suppression):** Linear counting penalizes large files for minor, isolated issues. The engine uses a logistic sigmoid function to filter out low-density noise (0–5% risk density) while scaling exponentially as risk density crosses critical thresholds (~20%).
* **Quantized Metric Tiering:** Numerical scores like "87.4%" imply artificial precision in static regex scanning. Score outputs are binned into five qualitative operational tiers (**Unshielded, Fragile, Stable, Defended, Fortified**), giving teams a clear binary signal on module health.

## Metric Calibration and Language Risk Models

Rather than applying a uniform formula across all source files, the engine instantiates calibrated risk models tailored to each risk domain and programming language paradigm.

### Language Confidence Tiers

Programming languages are categorized into confidence tiers that govern defensive dampening and risk penalties:

| Confidence Tier | Classification | Example Languages | Normalization Treatment |
| :--- | :--- | :--- | :--- |
| **Tier 1** | Explicit / Strongly Typed | Rust, Go, C++ | Baseline calculations; maximum trust in type system and error handling keywords. |
| **Tier 2** | Structured / Managed | Java, TypeScript | Standard calculations with minor defensive dampening. |
| **Tier 3** | Implicit / Dynamic | Shell, Python, JavaScript | Elevated risk penalty ("Opacity Tax") and dampened defensive keyword confidence. |

### Universal Model Variables

* **$Fc$ (Fidelity Coefficient):** Scaling factor reducing confidence weight for defensive keywords in dynamic or weakly-typed languages.
* **$Irc$ (Implicit Risk Correction):** Flat risk penalty added to dynamic languages to compensate for missing compile-time checks.
* **$Mp$ (Path Multiplier):** Contextual weight modifier based on repository file location (e.g., Core vs. Utility vs. Test directories).

### General Risk Equation

All risk domain calculations conform to this unified mathematical structure:

$$RiskExposure = \left( \frac{((RiskHits + Irc) \times Weight) - (DefenseHits \times Fc)}{LOC} \right) \times Mp$$

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

