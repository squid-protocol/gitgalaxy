# The Security Auditor (Machine Learning Inference Engine)

> **File Reference:** [`gitgalaxy/security/security_auditor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/security/security_auditor.py)

The Security Auditor (`security_auditor.py`) executes a trained XGBoost multiclass classification model across extracted codebase feature vectors. While pattern-matching static rules identify explicit vulnerability signatures, the machine learning auditor evaluates structural metrics, code complexity distributions, and graph topology to predict malicious software patterns (such as Trojans, Stealers, Droppers, or Botnets) that utilize code obfuscation to evade traditional static analysis.

---

## Dependency Graph Feature Traversal

Before executing model inference, the auditor computes topological dependency metrics across the import graph:

* **Breadth-First Search (BFS) Traversal:** Traces upstream and downstream import connections using BFS traversal. Traversal depth is capped at 10,000 nodes to prevent infinite recursion on circular module dependencies.
* **Transitive Coupling Ratios:** Computes `total_upstream` (total modules feeding into the file) and `total_downstream` (total modules dependent on the file) ratios relative to overall repository size, feeding normalized features to the ML classifier.

---

## Feature Vector Sanitization

The auditor builds a feature matrix (Pandas DataFrame) matching the schema established during XGBoost model training:

* **Logarithmic Metric Scaling:** Structural counts (e.g., lines of code `logic_loc`, function complexity `max_func_complexity`, import counts) are log-transformed (`np.log1p`) to normalize skewed distributions across large codebases.
* **Code Complexity & Distribution Heuristics:** Incorporates Gini complexity coefficients (`func_complexity_gini`), function density metrics, and orphan function ratios (`design_slop_orphans`).
* **Signature & Structural Context:** Combines raw pattern signature counts alongside structural mitigation factors (e.g., `raw_sec_tainted_injection`).
* **Global Architectural Distance:** Integrates global repository Z-scores and archetype cluster distances to measure individual file deviations from overall codebase patterns.
* **Graceful Fallback Mode:** If `xgboost` or `pandas` dependencies are not installed, the auditor falls back gracefully, executing graph traversal while skipping ML inference without interrupting the scan.

---

## Multiclass Threat Taxonomy

Sanitized feature vectors are passed to the XGBoost classifier (`XGBClassifier`), which predicts probability distributions across five structural classifications:

1. **Safe Code**
2. **Botnet / DDoS**
3. **Stealer / Trojan**
4. **Dropper / Webshell**
5. **Native Infector**

Modules scoring above the configured confidence threshold (`AI_THREAT_THRESHOLD`, defaulting to 90.0%) in any hostile category are flagged as machine-learning-confirmed threats.

---

## Supply Chain Integrity Check (`is_shadow_patch`)

To detect stealth supply chain mutations, the auditor supports an `is_shadow_patch` validation flag:

If a file's content hash mutates without a corresponding version bump in source control manifest files, and the file contains executable logic (`structural_mass > 0.5`), the auditor overrides standard ML inference. It classifies the file as a **"Stealer / Trojan"** with 100.0% confidence, flagging the unverified binary change as a critical security issue.

---

## Telemetry & Security Audit Integration

Classification findings—including `AI Threat Class`, `AI Threat Confidence` percentage, and the `is_ml_threat` boolean flag—are written into the file's central telemetry metadata dictionary.

Downstream reporting modules (such as `AuditRecorder` and `LLMRecorder`) consume these fields to position high-confidence machine learning threat findings at the top of exported compliance manifests and AI context briefs.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

