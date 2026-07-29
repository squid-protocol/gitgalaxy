# Statistical Quality Auditor & Bayesian Data Validation

> **File Reference:** [`gitgalaxy/metrics/statistical_auditor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/statistical_auditor.py)

The `StatisticalAuditor` module in `gitgalaxy/metrics/statistical_auditor.py` acts as the statistical quality control and data validation gate for GitGalaxy. It performs automated statistical verification across all processed files to ensure assigned language classifications and structural metrics are mathematically plausible.

By applying Bayesian accountability models, the auditor excludes anomalous non-code artifacts (e.g., massive data dumps, raw log files, compressed binary blobs) from repository-wide code metrics.

---

## Empirical Bayes Consensus Loop

Before auditing signal density, the auditor attempts to resolve ambiguous file classifications using local ecosystem consensus:

1. **Classification Triage:** Files with low-confidence locks (Tier 4 discovery or extension collisions) are assigned to an ambiguous evaluation queue. Confident files form the verified core baseline.
2. **Directory Ecosystem Consensus:** Evaluates extension distributions within the verified core. If 80% or more of files matching a specific extension firmly belong to a single language within the target repository, that consensus rule is applied to ambiguous files.
3. **Consensus Elevation & Relegation:** Ambiguous files matching the dominant extension rule are elevated to Tier 2 locks and retained in code metrics. Unresolved ambiguous files are relegated to the unclassified asset store.

---

## Dynamic Auditability Gates

Languages are audited based on their structural sensor coverage across the 32-key metric schema:

* **Inert Asset Gate:** Languages triggering zero active logic sensors (e.g., YAML, CSV, Plaintext) automatically pass quality audits as static content assets.
* **Structural Asset Gate:** Languages utilizing less than 75% of available logic sensors (e.g., HTML, CSS, Dockerfile) are classified as structural assets and audited under relaxed criteria.

---

## Ecosystem Orphan Guard

If a programming language species is represented by a tiny population (e.g., 3 files or fewer in a large repository), the auditor triggers the Orphan Guard:

* **Strict Lock Requirement:** Orphan files must hold a **Tier 0 Convergent Lock** (dual matching evidence) to remain classified as executable code.
* **Fallback to Plaintext:** If orphan files rely on unverified signatures, the auditor strips their language keys and reclassifies them as `plaintext`. This preserves file mass in repository metrics without polluting language composition statistics.

---

## Intent Density & MAD Outlier Protocol

For executable source code, the auditor computes **Intent Density** ($\rho$):

$$\rho = \frac{\text{Verified Signal Hits}}{\text{Total Physical Lines}}$$

To identify statistical outliers without sensitivity to extreme values, the auditor uses the **Median Absolute Deviation (MAD)** protocol:

1. **Baseline Validation Criteria:** Baseline statistics are calculated only if the language population is sufficiently large ($N \ge 50$), highly cohesive ($\text{R-MAD} < 1.0$), and contains at least one high-confidence anchor file ($C_i > 0.85$).
2. **Polyglot Exclusion:** Multi-language hybrid files (< 80% primary language mass) are excluded from baseline calculations to prevent mixed syntax from distorting median metrics.
3. **Robust Z-Score Computation:** Computes the robust Z-score ($M_i$) for each file:
   $$M_i = \frac{0.6745 \times (\rho - \text{Median}_\rho)}{\text{MAD}}$$
4. **Bayesian Dynamic Thresholding ($T_{adj}$):** Adjusts outlier relegation thresholds based on upstream prior confidence ($C_i$):
   $$T_{adj} = -5 \times \max(C_i, 0.1)$$
   High-confidence files receive wider statistical tolerance, whereas unverified low-confidence files face strict scrutiny.

---

## Outlier Handling & Event Horizon Policies

Files violating the 50/0 rule (files over 50 lines with zero structural signals) or failing MAD Z-score thresholds face three evaluation outcomes:

### 1. Quarantine Override Guard (Security Precedence)
Obfuscated malware payloads often register zero structural code signals to evade static analyzers. If a file fails statistical density audits but the security scanner (`security_lens.py`) detects active threat signatures (obfuscation, XOR decryption loops, homoglyphs), the Quarantine Guard intercepts relegation. The file is forced into the main code graph so security alerts remain visible.

### 2. Necrosis Guard (Dead Code Reprieve)
Files failing density audits that contain high comment ratios (> 5:1 comment-to-code ratio) or > 50% commented-out code matches receive an audit reprieve. Dead code is retained in the active file graph for technical debt and legacy analysis.

### 3. Relegation to Unclassified Asset Store
Files failing quality audits (and not saved by Quarantine or Necrosis guards) are stripped of language keys and relegated to the unclassified asset store (Dark Matter). Relegation records preserve Bayesian audit metadata (failed claim, prior confidence, and proof source) for compliance tracking and SBOM audits.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `statistical_auditor.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive 3D repository visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

