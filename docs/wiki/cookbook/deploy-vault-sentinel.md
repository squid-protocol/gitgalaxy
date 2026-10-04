---
description: "Hardcoded secrets (AWS keys, database passwords, API tokens) are the leading cause of enterprise data breaches. If a developer accidentally commits a..."
---
# How to Block Hardcoded Secrets in CI/CD

Hardcoded secrets (AWS keys, database passwords, API tokens) are the leading cause of enterprise data breaches. If a developer accidentally commits a credential, it becomes permanently etched into the Git history. 

To prevent this, organizations must block the secret *before* it leaves the developer's laptop. However, traditional security scanners are often too slow to run as local pre-commit hooks, causing developers to bypass them.

GitGalaxy solves this with the **Vault Sentinel**, a hyper-optimized, high-velocity secrets scanner designed specifically for pre-commit hooks and CI/CD pipelines.

## The Vault Sentinel

The Sentinel is a lightweight spoke of the GitGalaxy engine. It bypasses the heavy 3D dependency mapping and uses a "neutered" Security Lens—running only the mathematical string extraction and Shannon Entropy calculations necessary to catch high-density cryptographic payloads and known API key formats.

### 1. Deploy the Sentinel (Pre-Commit Hook)
You can run the Sentinel manually, or bind it to your repository's `.git/hooks/pre-commit` pipeline to scan files the moment a developer types `git commit`.

```bash
python gitgalaxy/tools/vault_sentinel.py /path/to/target_directory
```

### 2. The Mission Report & Hard Blocking
The Sentinel executes a two-pass funnel. First, it scans physical file paths to instantly block unauthorized extensions (e.g., `id_rsa`, `.pem`, `.env`). Then, it deep-scans the internal contents of the remaining files.

If a leak is found, the Sentinel outputs the exact snippet and triggers a `sys.exit(1)`, halting the CI/CD pipeline or Git commit instantly.

```text
==========================================================
 🛡️  VAULT SENTINEL: MISSION REPORT
==========================================================
 Files Evaluated    : 4,512
 Files Deep Scanned : 1,204
 Time Elapsed       : 1.15 seconds
 Scan Velocity      : 1,047 files/sec
----------------------------------------------------------
 UNCONTROLLED LEAKS : 1
 Denylist Blocks    : 0
 Allowlist Bypasses : 2
----------------------------------------------------------
 🚨 [CONTENT BREACH] Hardcoded Credential: src/auth/aws_client.py
   -> secret_key = "AKIAIOSFODNN7EXAMPLE"
 
 ❌ FAILED: 1 unauthorized secrets exposed. Blocking commit/PR.
==========================================================
```

### 3. Managing Exceptions (The Allowlist)
In enterprise environments, developers often need to commit "mock" or "dummy" credentials for unit testing. If the Sentinel flags a safe mock file, it will block the build.

Instead of turning off the scanner, DevSecOps can explicitly whitelist the safe file. 
Open `gitgalaxy/standards/gitgalaxy_config.py` and add the exact file path to the `ALLOWLIST_PATHS` array. The Sentinel will safely bypass it on the next run while keeping the rest of the vault sealed.

> **Read the full technical specification:** [Vault Sentinel](../04-04-vault-sentinel.md)

---

**[⬅️ Back to Master Index](../index.md)**
