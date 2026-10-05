---
description: "Sophisticated attackers rarely commit plain-text malware into a repository. To bypass standard security scanners, they employ stealth vectors like..."
---
# How to Hunt Encrypted Payloads and Binary Anomalies

Sophisticated attackers rarely commit plain-text malware into a repository. To bypass standard security scanners, they employ stealth vectors like **Steganography** (hiding executable code inside an image file) or **Cryptographic Packing** (encrypting the payload into a dense string and decrypting it at runtime).

Because traditional static analysis tools rely on reading plain-text syntax trees (ASTs), they are completely blind to these encrypted payloads. 

GitGalaxy solves this using the **X-Ray Inspector**. Instead of reading code, it measures the physical properties of the files using Magic Byte verification and Shannon Entropy mathematics to detect hidden logic.

## The X-Ray Mechanics

The Inspector rips through the first 8KB of every file, treating it as raw bytes rather than source code. It hunts for three specific anomalies:

1. **Magic Byte Mismatches:** Every valid binary (like a `.png` or `.zip`) starts with a specific sequence of "Magic Bytes." If an attacker renames a malicious `.sh` script to `logo.png`, the Magic Bytes will not match, and the Inspector will instantly flag the anomaly.
2. **Parasitic Execution Headers:** The engine scans data blobs for execution headers (e.g., `#!/bin/bash` or `\x7fELF`) hidden deep inside normally inert files.
3. **High-Entropy Encrypted Payloads:** Normal, human-written strings have a predictable level of mathematical randomness. The Inspector runs a C-backed Shannon Entropy calculation on dense strings. If the entropy exceeds `4.8`, it indicates the string is a packed or encrypted payload. It simultaneously looks for sub-atomic `XOR` bitwise loops typically used to decrypt these payloads at runtime.

### 1. Execute the Scan
You can run the X-Ray Inspector manually or deploy it as a specialized pre-commit hook or CI/CD gatekeeper.

```bash
python gitgalaxy/tools/binary_anomaly_detector.py /path/to/target_directory
```

### 2. The Triage Report
If the Inspector detects a structural anomaly, it halts the pipeline and provides the exact file and the physical reason for the breach.

```text
==========================================================
 ☢️  X-RAY INSPECTOR: MISSION REPORT
==========================================================
 Files Evaluated    : 8,402
 Files Deep Scanned : 8,150
 Time Elapsed       : 1.82 seconds
 Scan Velocity      : 4,478 files/sec
----------------------------------------------------------
 Active Anomalies   : 2
 File Denylist Blocks : 0
 File Allowlist Bypasses: 45
----------------------------------------------------------

☢️  [ANOMALY DETECTED] src/assets/images/header_bg.png
   -> Expected b'\x89PNG\r\n\x1a\n', found mismatch
   -> Embedded execution header found: b'#!/bin/'

☢️  [ANOMALY DETECTED] src/utils/legacy_loader.js
   -> Mathematically dense/encrypted strings detected (Shannon Entropy > 4.8)
   -> Sub-atomic decryption routines (XOR loops) detected

❌ TRIAGE ALERT: 2 structural anomalies detected. Blocking commit/PR.
==========================================================
```

### 3. Tuning the X-Ray (Handling False Positives)
Because the X-Ray uses entropy math, it will naturally flag highly compressed data, cryptographic keys, or dense mock data generated for unit tests. 

*Note: The Inspector automatically bypasses files in `/test/` directories.*

To prevent false positives from breaking your build, you can explicitly tune the X-Ray bypass lists inside `gitgalaxy/standards/gitgalaxy_config.py`:
* **`XRAY_BYPASS_EXTENSIONS`:** Add safe extensions that naturally have high entropy (e.g., `['.gz', '.woff2', '.dat']`).
* **`XRAY_BYPASS_PATHS`:** Add specific, known-safe files that trigger the scanner (e.g., `['src/crypto/seed_data.json']`).

> **Read the full technical specification:** [Binary Anomaly Detector](../04-05-binary-anomaly-detector.md)

---

**[⬅️ Back to Master Index](../index.md)**
