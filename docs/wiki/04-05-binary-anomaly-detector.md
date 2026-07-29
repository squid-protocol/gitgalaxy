# Binary Anomaly Detector (Heuristic File Integrity Scanner)

> **File Reference:** [gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py)

The `binary_anomaly_detector.py` module in `gitgalaxy/tools/supply_chain_security/` performs high-speed triage of binary anomalies, magic byte mismatches, and obfuscated payloads within the build pipeline. While standard source code parsers drop binary assets to conserve memory, the Binary Anomaly Detector selectively inspects binary files (`.png`, `.zip`, `.dll`, `.exe`, etc.) using byte-level headers and Shannon entropy math to flag hidden malware and steganographic payloads.

---

## Selective Binary Ingestion Logic

Most GitGalaxy scanning modules utilize the `ApertureFilter` to exclude binary assets and minified code. The Binary Anomaly Detector explicitly overrides this behavior to perform targeted file integrity audits:

* **Binary Ingestion Exemption:** Bypasses standard binary path exclusion rules during queue generation, ensuring binary file types are enqueued for header inspection.
* **Test Data Shield:** Automatically whitelists paths containing `/test/`, `/tests/`, or `phpunit` to prevent false positive alerts on mock data fixtures or synthetic binary test files.
* **Configurable Bypasses:** Evaluates project-level configuration (`XRAY_BYPASS_EXTENSIONS` and `XRAY_BYPASS_PATHS`) to permit designated compressed formats (e.g., `.gz`, `.json` fixtures) without triggering pipeline failures.

---

## 8KB Header Inspection & Mathematical Entropy

To maintain high throughput and eliminate out-of-memory risks on large assets, the detector reads only the first 8,192 bytes ($8\text{ KB}$) of target files:

```python
with open(file_path, "rb") as f:
    head_bytes = f.read(8192)
```

The 8KB chunk provides sufficient data for header signature verification, magic byte checks, and entropy calculation:

### 1. Magic Byte & Extension Matching (`scan_binary`)
Inspects file magic bytes against declared file extensions. Mismatches—such as an executable payload disguised with a `.png` or `.jpg` extension—trigger `[ANOMALY DETECTED]` warnings.

### 2. Expected Shell Shebang Exception
Shell scripts (`.sh`, `.bash`, `.zsh`, `.command`) legitimately contain executable header signatures (`#!/bin/bash`). If a binary threat flag matches an expected script shebang, the anomaly alert is safely suppressed.

### 3. Shannon Entropy & Encrypted Payload Detection
Decodes the raw 8KB byte buffer to evaluate mathematical string entropy:
$$\text{Entropy} > 4.8$$
High Shannon entropy indicates packed executables, encrypted payloads, or high-density obfuscated arrays embedded within non-executable files.

### 4. Obfuscated Bitwise Operation Traps
Inspects byte buffers for raw bitwise operations (`bitwise_ops`). Dense clusters of XOR math operations indicate potential unpacking routines or steganographic decryption loops.

---

## Programmatic & CLI Execution

The detector supports both standalone CLI invocation and programmatic execution within orchestrator runs (`run_xray_audit`):

### Standalone CLI Execution

```bash
python3 -m gitgalaxy.tools.supply_chain_security.binary_anomaly_detector /path/to/repo --config .galaxyscope.yaml
```

### Programmatic Invocation (`run_xray_audit`)

```python
from gitgalaxy.tools.supply_chain_security.binary_anomaly_detector import run_xray_audit

audit_results = run_xray_audit(target_path=repo_path, config=resolved_config)
print(f"Anomalies detected: {audit_results['anomalies_found']}")
```

If unwhitelisted anomalies or magic byte mismatches are discovered (`anomalies_found > 0`), the CLI tool prints detailed evidence snippets and exits with status code `1`, preventing corrupted or weaponized assets from advancing in the build pipeline.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `binary_anomaly_detector.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

