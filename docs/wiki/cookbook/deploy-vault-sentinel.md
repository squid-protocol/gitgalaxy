---
description: "Hardcoded secrets (AWS keys, database passwords, API tokens) committed to Git stay in its history. Vault Sentinel fails a pre-commit hook or CI job when one is found..."
---
# How to Block Hardcoded Secrets in CI/CD

Hardcoded secrets (AWS keys, database passwords, API tokens) are a common way credentials leak. If a developer commits one, it stays in the Git history even after the file is fixed.

The cheapest place to stop it is before the commit. A full security scan is often too slow for a pre-commit hook, and a slow hook gets skipped.

GitGalaxy's **Vault Sentinel** is a secrets scanner for pre-commit hooks and CI pipelines. It runs one signature instead of the full engine; no speed benchmark is committed.

## The Vault Sentinel

The Sentinel is a spoke of the GitGalaxy engine. It skips the dependency graph and runs the Security Lens restricted to the `hardcoded_secrets` signature (credential names and known token formats), plus three patterns of its own: AWS secret access keys, Google `AIza` keys and JWTs. It does not use Shannon entropy, so a high-density string with no recognised name or format is not reported. It is tested on planted secrets (`tests/security_auditing/test_vault_sentinel_control.py`); recall on real-world leaks has not been measured.

### 1. Deploy the Sentinel (Pre-Commit Hook)
You can run the Sentinel manually, or bind it to your repository's `.git/hooks/pre-commit` pipeline to scan files the moment a developer types `git commit`.

```bash
vault-sentinel /path/to/target_directory
# or: python -m gitgalaxy.tools.supply_chain_security.vault_sentinel /path/to/target_directory
```

### 2. The Mission Report & Hard Blocking
The Sentinel makes two passes. First it checks file names: secret-file names and extensions (e.g., `id_rsa`, `.env`, `.pem`; a `.pem` holding only a certificate or public key is not counted) fail the run without a content scan. Then it scans the contents of the remaining text files.

If a leak is found, the Sentinel prints the file path, one redacted line per match (it never prints any part of the secret), and exits with status 1, which fails the CI job or Git commit. The output looks like this (illustrative numbers):

```text
[CONTENT BREACH] Hardcoded Credential: src/auth/aws_client.py
   -> ********[REDACTED]********

===========================================================================
 🛡️  VAULT SENTINEL: SCAN SUMMARY
===========================================================================
 Files Evaluated    : 4,512
 Files Deep Scanned : 1,204
 Time Elapsed       : 1.15 seconds
 Scan Velocity      : 1,047 files/sec
---------------------------------------------------------------------------
 SECRETS DETECTED     : 1
 Denylist Blocks      : 0
 Allowlist Bypasses   : 2
 Files Not Scanned    : 0
---------------------------------------------------------------------------
 [BLOCKING ACTION] 1 unauthorized secrets exposed. Failing pipeline.
```

### 3. Managing Exceptions (The Allowlist)
Teams often commit mock or dummy credentials for unit tests. If the Sentinel flags one, it fails the build.

Instead of turning off the scanner, add the file path to `ALLOWLIST_PATHS`, either in `gitgalaxy/standards/gitgalaxy_config.py` or under `galaxyscope:` in a `.galaxyscope.yaml` passed with `--config`. An allowlisted file is still scanned; a hit is logged as an allowlist bypass and does not fail the run. An entry is a partial match on the path (an entry ending in `/` matches a folder).

**Check the default first:** `ALLOWLIST_PATHS` ships with `tests/`, which exempts every file under any `tests/` folder (including `src/tests/` and `unit_tests/`). A real secret committed there will not fail the run. Remove that entry if your test folders should be scanned.

> **Read the full technical specification:** [Vault Sentinel](../04-04-vault-sentinel.md)

---

**[⬅️ Back to Master Index](../index.md)**
