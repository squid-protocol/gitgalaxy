---
description: "Modern applications are assembled, not written. A typical enterprise project contains thousands of transitive dependencies pulled from `npm`, `PyPI`,..."
---
# How to Enforce a Zero-Trust Supply Chain Firewall

Modern applications are assembled, not written. A typical enterprise project contains thousands of transitive dependencies pulled from `npm`, `PyPI`, or `Maven`. 

Traditional Software Bill of Materials (SBOM) tools are passive—they tell you what you have installed, but they do not stop a compromised package (like the `xz` backdoor or `colors.js` sabotage) from executing malicious code. 

GitGalaxy shifts this paradigm from passive monitoring to active defense using the **Supply Chain Firewall**. It scans `node_modules` or `venv` directories during the CI/CD build process, blocking compromised packages *before* they are compiled into the production artifact.

## The Firewall Mechanics

The firewall operates on a two-pass funnel, combining Zero-Trust package verification with the raw structural threat detection of the GitGalaxy Physics Engine.

### 1. Zero-Trust Package Verification
The firewall rips through the raw source code of your dependencies and extracts every `require()`, `import`, and `from` statement. It cross-references these against your enterprise `gitgalaxy_config.py`:

* **Audit Mode (Default):** Blocks anything explicitly listed in `BLACKLISTED_IMPORTS` (known bad actors). Allows everything else.
* **Strict Mode (Air-Gapped):** If `STRICT_IMPORT_MODE = True`, the firewall blocks *everything* except the packages explicitly listed in `APPROVED_IMPORTS`. If an engineer introduces a new, unvetted package, the build automatically fails.

### 2. Structural Malware Detection
Attackers frequently use "typo-squatting" or Unicode Homoglyphs (replacing a standard 'a' with a Cyrillic 'а') to bypass simple scanners. 

The firewall subjects all external dependencies to the `SecurityLens`, specifically hunting for:
* **Unicode Homoglyphs & Typo-squatting:** Invisible characters or look-alike imports.
* **Shadow Imports:** Steganography (e.g., hiding executable code inside a `.png` or `.pdf` file).
* **Tainted I/O:** Untrusted network sockets combined with `eval()` or `exec()`.

*Note: The engine employs an "Inert Data Shield," intentionally bypassing static files like `.json`, `.md`, and `.css` to maintain extreme processing velocity.*

## Deployment Pipeline

To deploy the firewall, bind it to a CI/CD workflow step immediately after dependencies are installed, but before the application builds.

```bash
# Example: Scanning a Node.js project's dependencies
python gitgalaxy/tools/supply_chain_firewall.py ./node_modules
```

### The Mission Report
If a malicious package is detected—either via a Blacklist match or a structural malware density breach—the firewall triggers a `sys.exit(1)` to halt the build pipeline and provides exact forensic evidence.

```text
==========================================================
 🧱 SUPPLY CHAIN FIREWALL: MISSION REPORT
==========================================================
 Mode               : Strict (Exclude Blacklist and Unknown)
 Files Deep Scanned : 14,205
 Scan Velocity      : 2,140 files/sec
----------------------------------------------------------
 Approved Packages    : 142
 Banned Packages      : 1
 Unknown Packages     : 3
----------------------------------------------------------
 Active Threats       : 4
 File Denylist Blocks : 0
 File Allowlist Bypasses: 0
----------------------------------------------------------

🚨 [BLACKLISTED IMPORT] Malicious package 'node-ipc' blocked in: node-ipc/dao.js
🚨 [ZERO-TRUST BREACH] Unknown package 'random-string-gen' blocked by Strict Mode in: src/utils.js

❌ BUILD FAILED: 4 infected dependencies or policy violations blocked.
==========================================================
```

> **Read the full technical specification:** [Supply Chain Firewall](../04-03-supply-chain-firewall.md)

---

**[⬅️ Back to Master Index](../index.md)**
