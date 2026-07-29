# Metrics Normalization & Risk Score Processor

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

The `SignalProcessor` module in `gitgalaxy/metrics/signal_processor.py` acts as the metrics normalization and risk evaluation engine for GitGalaxy. Once the structural code analyzer (`detector.py`) extracts raw 60-point structural counts (`SIGNAL_SCHEMA`), the signal processor normalizes these values and maps them into an 18-point scaled risk score vector (`RISK_SCHEMA`).

The engine evaluates files in context, comparing individual metrics against directory language distributions, repository-wide baseline curves, and Git commit history.

---

## Domain Ontologies & Context Mismatch Detection

A file's risk profile depends heavily on its surrounding directory context. High-level systems code located in backend directories is expected, whereas system-level binaries located inside web frontend folders represent architectural anomalies.

To detect misplaced or hidden executable components, the processor evaluates the **Context vs. Entity Matrix**:

* **Native Directory Context:** If a file's language matches the dominant language domain of its parent directory (e.g., Python files inside a Python service directory), standard scoring weights are applied.
* **Anomalous Directory Context (Alien Entity Detection):** If a file's language conflicts with its directory context (e.g., C/Rust source files located inside a JavaScript static asset folder), the processor injects risk multipliers. `Logic Bomb` and `Memory Corruption` exposure scores receive dynamic scaling penalties to flag anomalous placement.

---

## Tiered Language Standardization Model

To ensure comparative fairness across programming languages with varying syntactic verbosity, the processor applies linguistic normalization:

| Language Tier | Classification | Example Languages | Normalization Treatment |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Explicit** | Rust, Go, Swift, Java | Signals trusted directly. Fidelity coefficient = 1.0, zero implicit opacity penalty. |
| **Tier 2** | **Structured** | Python, JavaScript, C++ | Translucent syntax. Applies minor opacity adjustment for dynamic runtime behavior. |
| **Tier 3** | **Implicit** | Shell, SQL, Assembly | Opaque syntax. Applies baseline phantom risk penalty requiring higher test density for safe ratings. |

---

## Biaxial Anomaly Detection (Global vs. Local Drift)

The processor evaluates two axes of structural drift:

* **Global Repository Drift:** Compares a file's structural metrics against all files across the repository.
* **Local Language Drift:** Compares a file's structural metrics strictly against other files written in the *same* programming language.

### Biaxial Spike Detection
If a file displays low global drift (appearing benign relative to the codebase overall) but exhibits extreme local language drift (heavily violating structural conventions of its native language), the processor triggers a **Biaxial Anomaly Penalty**. Exponential multipliers are applied to `Logic Bomb` and `Obfuscated Payload` risk scores to highlight potential masquerading code.

---

## Infrastructure Shields & Score Bypasses

To prevent false positives on non-code assets or static configurations, the processor enforces bypass rules:

* **Extension Mismatch Shield:** Detects files with non-executable extensions (`.txt`, `.json`) that contain active code logic, setting a `sec_extension_mismatch` security flag.
* **Exposed Secret Bypass:** Exposed credential files (`.pem`, `.env`) bypass standard metric scaling and set `secrets_risk` directly to 100%.
* **Minified & Vendor Shield:** Minified bundles (`.min.js`) zero out cognitive complexity and debt metrics. However, if dynamic execution (`eval`) or network calls are detected inside minified code, the `Obfuscated Payload` risk score spikes to 100%.
* **Documentation Bypass:** Documentation assets (`markdown`, `plaintext`) zero out executable code metrics and bus-factor risk.

---

## Two-Pass Temporal Normalization

Commit modification frequency (churn) varies significantly across repositories. Hardcoded churn limits are ineffective across projects with different commit volumes.

The processor resolves this via **Two-Pass Normalization**:

1. **Pass 1 (Raw Extraction):** Computes absolute file age and raw commit count per file from Git history.
2. **Pass 2 (Repository Scaling Curve):** Identifies the maximum commit churn file in the repository. Applies a logarithmic curve ($\log(1 + \text{churn})$) via `_normalize_temporal_metrics` to scale all file churn scores relative to the repository ceiling.

---

## Systemic Risk Bottleneck Evaluation

The processor synthesizes local file risk scores with directed graph centrality metrics from `NetworkRiskSensor`:

* **Active Logic Filtering:** Excludes non-executable assets (JSON configs, Markdown docs) from risk rankings, ensuring only executable source code competes for top risk spots.
* **Contagious Mutation Index:** Calculates $\text{Betweenness Centrality} \times \text{State Mutation}$. Flags architectural choke points with volatile mutating state.
* **Cascading Error Risk (House of Cards):** Calculates $\text{Closeness Centrality} \times \text{Error Exposure}$. Flags central nodes where unhandled exceptions cascade across downstream callers.
* **Undocumented Critical Nodes:** Calculates $\text{Blast Radius} \times \text{Documentation Risk}$. Flags critical core modules that lack documentation.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `signal_processor.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

