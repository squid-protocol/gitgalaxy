# Terabyte Log Scanner (High-Volume Telemetry & Dead Code Validator)

> **File Reference:** [gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py)

The `terabyte_log_scanner.py` module in `gitgalaxy/tools/terabyte_log_scanning/` provides single-pass log processing and execution verification. It bridges static security analysis and dynamic runtime telemetry by cross-referencing static code analysis hypotheses against live execution logs (such as mainframe SMF/JCL logs or application server logs). This enables security teams to validate whether suspected dead code or vulnerable modules are active in production environments.

---

## Dual Target Discovery & Ingestion

Scanning multi-terabyte log files requires surgical target definition. The scanner supports two targeting modes:

### 1. Manual Keyword Targeting (`-k / --keywords`)
Engineers can supply explicit target terms (e.g., `-k PROG01 PROG02`) to audit specific application modules or event signatures.

### 2. Automated State Ingestion (`--input_state`)
Ingests a GitGalaxy Intermediate Representation JSON file (`ir_state.json`). The scanner parses the `analysis.known_programs` array to extract target program names automatically:

```json
{
  "analysis": {
    "known_programs": ["PAYROLL01", "ACCTMAIN", "REPORTGEN"]
  }
}
```

This allows the scanner to dynamically extract and verify execution evidence across thousands of repository artifacts in a single log processing pass.

---

## Binary Streaming & Performance Engineering

To process multi-gigabyte and multi-terabyte log files without memory allocation bottlenecks:

1. **Byte-Level Regex Patterns:** Compiles target keywords into binary byte patterns (`re.compile(kw.encode('utf-8'))`).
2. **Single-Pass Binary Read Stream:** Streams the log file in binary mode (`open(..., "rb")`). Non-matching lines are evaluated without triggering UTF-8 string decoding overhead.
3. **Lazy Line Decoding:** Lines matching target byte patterns are decoded into UTF-8 text and written to a filtered results log (`<target_stem>_results.txt`).

---

## Time-Series Histograms & Spike Filtering

The scanner extracts chronological timestamps (`ts_pattern`) and groups execution hits into hourly time buckets:

```
 === TIME-SERIES: PAYROLL01 ===
 (Filtering to Top 15 Highest Volume Spikes)
 [2026-07-29 01:00] ████████████████████████████████████████ (24,500 hits)  <-- VOLUME ANOMALY DETECTED
 [2026-07-29 02:00] ███ (1,800 hits)
```

### Display Safeguards & Anomaly Thresholds
* **Top 15 Volume Spike Filter:** When log spans cover extended periods with numerous time buckets, the terminal output isolates the **Top 15 highest-volume spikes**, re-sorted chronologically.
* **Volume Anomaly Flagging:** Buckets exceeding $3\times$ the average hit rate across all intervals (with $> 10$ hits) trigger an `<-- VOLUME ANOMALY DETECTED` alert.

---

## Telemetry Sidecar Generation (`dynamic_telemetry.json`)

Beyond displaying terminal dashboards, `terabyte_log_scanner.py` exports a telemetry sidecar (`dynamic_telemetry.json`):

```json
{
  "execution_counts": {
    "PAYROLL01": 26300,
    "ACCTMAIN": 0,
    "REPORTGEN": 1420
  },
  "resolved_dynamic_calls": {}
}
```

### Closed-Loop Pipeline Feedback
The sidecar payload can be re-ingested by the main GitGalaxy pipeline:
* **High Execution Counts ($> 0$):** Validates active production modules.
* **Zero Hits ($0$):** Confirms static "dead code" candidates, allowing teams to safely decommission unused legacy modules.

---

## CLI Command Interface

```bash
# Manual Keyword Mode
python3 -m gitgalaxy.tools.terabyte_log_scanning.terabyte_log_scanner /var/log/smf_output.log -k PROG01 PROG02 --out /tmp/logs/

# Automated IR State Mode
python3 -m gitgalaxy.tools.terabyte_log_scanning.terabyte_log_scanner /var/log/smf_output.log --input_state ir_state.json --out /tmp/logs/
```

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `terabyte_log_scanner.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

