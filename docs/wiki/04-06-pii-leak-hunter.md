# PII Leak Hunter (Log Privacy & Incident Responder)

> **File Reference:** [gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py)

The `pii_leak_hunter.py` module in `gitgalaxy/tools/terabyte_log_scanning/` provides high-throughput, single-pass log analysis and sensitive data masking. Engineered for rapid incident response and compliance auditing, the tool streams multi-gigabyte log files or database dumps, detects exposed Personally Identifiable Information (PII), masks sensitive values, and outputs sanitized evidence logs alongside ASCII time-series histograms.

---

## Byte-Level Pattern Matching (Zero UTF-8 Overhead)

Decoding millions of log lines into UTF-8 strings introduces heavy CPU and memory allocation overhead. To maintain maximum streaming velocity, `pii_leak_hunter.py` compiles all detection patterns directly as binary byte regular expressions (`PII_PATTERNS`):

```python
PII_PATTERNS = {
    "VISA": re.compile(rb"\b4[0-9]{12}(?:[0-9]{3})?\b"),
    "MASTERCARD": re.compile(rb"\b(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}\b"),
    "SSN": re.compile(rb"\b\d{3}-\d{2}-\d{4}\b"),
    "AWS_KEY": re.compile(rb"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA)[A-Z0-9]{16}\b"),
}
```

### Streaming Logic & Performance Guarantee
1. **Raw Binary Line Streaming:** Reads input log files line-by-line in binary mode (`open(..., "rb")`).
2. **Lazy Decoding:** Non-matching lines remain un-decoded in memory, avoiding string allocation costs. Lines are decoded into UTF-8 text *only* after a binary regex match is confirmed.
3. **Multi-Pattern Deduction:** Ensures that a single line containing multiple PII instances is logged once with full masking applied across all detected categories.

---

## Sensitive Value Masking & Evidence Output

To allow security teams to investigate incidents without storing toxic or non-compliant raw credentials in secondary log files, `mask_pii()` applies surgical string replacements:

| PII Category | Raw Pattern Example | Masked Output Format |
| :--- | :--- | :--- |
| **VISA Credit Card** | `4111222233334444` | `VISA-MASKED-4444` |
| **Mastercard** | `5500000000000004` | `MC-MASKED-0004` |
| **US Social Security Number** | `123-45-6789` | `XXX-XX-6789` |
| **AWS Access Key** | `AKIAIOSFODNN7EXAMPLE` | `AKIA-XXXX-MPLE` |

Sanitized log entries are written directly to a designated evidence log (`<target_stem>_pii_leak_evidence.log`), enabling compliance teams to verify leak contexts safely.

---

## Time-Series Exposure Histograms & Anomaly Alerts

As the hunter streams through log lines, `ts_pattern` extracts ISO and syslog timestamp formats (`YYYY-MM-DD HH` or `MMM DD HH`). Hits are bucketed chronologically into hourly intervals and displayed via `draw_ascii_histogram()`:

```
 === TIME-SERIES: VISA EXPOSURE ===
 (Filtering to Top 15 Highest Volume Spikes)
 [2026-07-29 02:00] ████████████████████████████████████████ (14,200 hits)  <-- HIGH VOLUME SPIKE DETECTED
 [2026-07-29 03:00] █ (312 hits)
```

### Spike Filtering & Anomaly Criteria
* **Spike Filtering:** If the log file spans hundreds of time intervals, the display automatically isolates the **Top 15 highest-volume spikes**, re-sorting them chronologically for readability.
* **Volume Anomaly Threshold:** Computes average hits per time bucket. Intervals exceeding $3\times$ the average volume (with $> 10$ hits) trigger high-volume anomaly warnings.

---

## Execution & Summary Telemetry

The PII Leak Hunter is executed via command-line interface:

```bash
python3 -m gitgalaxy.tools.terabyte_log_scanning.pii_leak_hunter /var/log/application.log --out /tmp/reports/
```

Upon completion, the tool outputs an executive summary detailing hit counts per category, processing duration, and streaming velocity in **GB/s** or **MB/s**.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `pii_leak_hunter.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

