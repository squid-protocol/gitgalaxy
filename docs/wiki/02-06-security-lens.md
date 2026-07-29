# Vulnerability & Threat Scanner

> **File Reference:** [`gitgalaxy/security/security_lens.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/security/security_lens.py)

The `SecurityLens` module in `gitgalaxy/security/security_lens.py` provides pattern-based security analysis and threat detection for GitGalaxy. Rather than depending on static vulnerability databases (CVE lists) or simple string-matching rules that can be bypassed by variable renaming or code obfuscation, the engine detects **structural attack patterns** and behavioral execution mechanics.

By evaluating the structural density of high-risk operations—such as dynamic string execution, raw socket creation, prototype mutation, and unmitigated taint flow—the scanner detects both known vulnerabilities and zero-day attack patterns.

---

## Dynamic Threat Policy Governance

The `SecurityLens` module decouples threat measurement from policy enforcement:

* **Policy Injection:** Upon initialization, the scanner ingests a threat threshold policy (`gitgalaxy_standards.ThreatPolicy`). This policy defines alert thresholds for key risk categories, including Credential Leaks, Hidden Malware, Injection Surfaces, Logic Bombs, and Memory Corruption.
* **Configurable Sensitivity:** Security teams can adjust detection thresholds based on environment requirements. Executing the orchestrator in high-sensitivity mode (`--paranoid`) lowers trigger limits, increasing scrutiny for high-risk environments.

---

## Structural Threat Patterns

The scanner uses hardware-optimized regular expression engines to identify behavioral threat patterns:

1. **Obfuscation Patterns:** Detects obfuscation structures, including nested decoding wrappers (`atob`, `base64_decode`, `gzuncompress`), high-density base64 payloads, and zero-width invisible Unicode characters used to conceal logic.
2. **Security Controls Bypass:** Identifies routines that disable host security controls, such as turning off TLS verification (`NODE_TLS_REJECT_UNAUTHORIZED=0`), disabling PHP `safe_mode`, or suppressing security warnings.
3. **Unauthorized Exfiltration Vectors:** Detects suspicious network routines, including hardcoded IP address literals, raw socket allocation, and connections to tunneling services (`ngrok.io`, `pastebin.com`).
4. **Dynamic Execution Hits:** Identifies arbitrary code execution structures, including raw `eval()` calls, OS command execution (`child_process.exec`), and unsafe reflection.
5. **Environment & Prototype Poisoning:** Flags attempts to mutate application state or global prototypes (`__proto__` pollution, overriding global `fetch`/`eval`, modifying server environment arrays).
6. **Commented Execution Threats:** Scans the comment stream for executable commands (`nc -e`, `curl | bash`) trapped within inactive code blocks.
7. **Custom Decryption Routines:** Detects dense clusters of bitwise XOR (`^`) operations within loops, a common indicator of custom payload decryption.
8. **Steganography & Unsafe Imports:** Flags attempts to import or execute non-script media assets (`.png`, `.jpg`, `.pdf`) as executable modules.
9. **Homoglyph & Unicode Spoofing:** Identifies Cyrillic or special Unicode characters injected into `import` or `fetch` statements designed to mimic legitimate dependency names.
10. **Credential & Secret Exposure:** Identifies high-entropy literal strings assigned to sensitive key names (`api_key`, `client_secret`, `private_key`).
11. **Memory Override Mechanics:** Scans C/C++ logic for unsafe memory allocations (`malloc`, `memcpy`, `free`) and inline assembly (`__asm__`) that pose buffer overflow risks.
12. **Agentic RCE & Prompt Injection Surfaces:** Identifies unmitigated hooks connecting LLM output directly to OS execution sinks.
13. **Database Injection Sinks:** Identifies unsanitized SQL query strings passed into database execution drivers.

---

## Content Scanning & Taint Analysis

The `scan_content` method processes code buffers to extract threat telemetry:

* **Minification Guard:** Excludes lines exceeding 250 characters from intensive regex parsing to avoid performance degradation on compressed bundles.
* **Machine-Generated Code Shield:** Bypasses entropy and homoglyph checks on auto-generated code headers (`DO NOT EDIT`).
* **Shannon Entropy Math:** Computes Shannon entropy on string literals longer than 64 characters. Strings exceeding entropy thresholds (> 7.9) are flagged as encrypted or packed payloads.
* **Data Flow Taint Analysis:**
  * **Same-Line Detonation:** Flags instances where I/O retrieval and dynamic execution occur on the same line (e.g., fetching a URL and immediately evaluating the response).
  * **Variable Taint Propagation:** Tracks variables assigned from untrusted I/O or LLM responses down through execution sinks. If tainted variables enter command execution calls, an **Agentic RCE** alert is raised.

---

## Threat Density & Exposure Metrics

Raw threat hit counts are normalized against file size to calculate **Threat Density**:

$$\text{Threat Density} = \frac{\text{Total Threat Hits}}{\text{Executable LOC}}$$

### Network Centrality Multiplier
Files with high centrality (high PageRank or Betweenness centrality computed by `NetworkRiskSensor`) represent critical system bottlenecks. Threat density scores for central nodes are scaled exponentially to enforce near-zero tolerance on core infrastructure.

### Exposure Score Vectors
The scanner aggregates threat telemetry into 0-100 exposure scores:

* **Hidden Malware Exposure:** Aggregates obfuscation, bitwise XOR loops, steganography, and string entropy.
* **Logic Bomb Exposure:** Aggregates commented execution threats and dynamic payload functions.
* **Data Injection Exposure:** Aggregates I/O execution flows, state mutation, and database sink hits.
* **Memory Corruption Exposure:** Aggregates raw memory allocation and inline assembly counts.
* **Secrets Exposure:** Aggregates credential assignment matches.
* **Agentic RCE Exposure:** Triggered when untrusted LLM outputs flow into OS execution sinks.

---

## Binary File Inspection (X-Ray Header Sensor)

When binary files pass through ingestion, the scanner evaluates the first 8KB of data:

* **Magic Byte Verification:** Validates binary headers against file extensions (detecting mismatched executable extensions).
* **Parasite Detection:** Scans binary headers for embedded execution markers (`ELF`, `MZ`, `#!/bin/`) inside non-executable media files.
* **Entropy Threshold Check:** Flags binary payloads exceeding 7.95 entropy as packed or encrypted executables.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `security_lens.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository visualization interface.

---

**[⬅️ Back to Master Index](index.md)**

