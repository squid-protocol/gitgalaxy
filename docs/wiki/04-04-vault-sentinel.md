# Vault Sentinel (High-Speed Secrets Scanner)

> **File Reference:** [gitgalaxy/tools/supply_chain_security/vault_sentinel.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/supply_chain_security/vault_sentinel.py)

The `vault_sentinel.py` module in `gitgalaxy/tools/supply_chain_security/` provides high-speed secret scanning designed for developer pre-commit hooks and CI/CD pull request validation. It detects hardcoded API keys, SaaS credentials, private key certificates, and uncommitted `.env` files before code is pushed to public repositories.

---

## Sensor Optimization for Low Latency

Pre-commit hooks must complete in milliseconds to avoid blocking local developer workflows. To achieve sub-second execution speeds, `vault_sentinel.py` narrows the scope of `SecurityLens` signature matching exclusively to high-priority targets:

```python
security.THREAT_SIGNATURES = {
    "hardcoded_secrets": security.THREAT_SIGNATURES["hardcoded_secrets"],
    "dead_code": security.THREAT_SIGNATURES["dead_code"],
}
```

By stripping general AST, cyclomatic complexity, and non-credential regex rules, the scanner maximizes file throughput while retaining precise detection for hardcoded tokens and commented-out credentials.

---

## Two-Pass Detection Pipeline

The scanner processes repository files through a two-pass detection funnel to minimize file system I/O and memory allocations:

```
                          Repository Root
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
             [Phase 1: Path Radar]     [Directory Ignores]
                    │
            ┌───────┴───────┐
            ▼               ▼
      [Denylist Match] [Path Integrity]
            │               │
       (Block/Alert)  ┌─────┴─────┐
                      ▼           ▼
               [Deny/Leaked]  [Valid Source]
                      │           │
                 (Alert/Count)    ▼
                         [Phase 2: Deep Content]
                                  │
                             (Redact/Alert)
```

### Phase 1: Path Surface Radar (Zero-I/O Checks)
Evaluates file paths against ignore patterns (`ApertureFilter`), wildcard denylist rules (`DENYLIST_PATTERNS`), and path integrity checks prior to opening file handles:

1. **Denylist Pattern Matching:** Checks filenames against wildcard patterns (`*.pem`, `id_rsa*`, `.env*`, `*.key`). Matching files increment leak counters and are blocked immediately without reading file contents.
2. **Tier 0 Path Inspection:** Uses `evaluate_path_integrity()` to detect critical key formats. If a file path indicates a credential leak, it triggers a `[PATH BREACH]` alert.

### Phase 2: Deep Content Inspection
Files passing Phase 1 are loaded into memory and scanned by the optimized `SecurityLens`:

* **Cloud Infrastructure Credentials:** Hunts for AWS (`AKIA...`), GCP, and Azure management tokens.
* **SaaS Tokens & Private Keys:** Identifies GitHub PATs, Stripe secret keys, JWT private keys, and SSH private keys (`-----BEGIN RSA PRIVATE KEY-----`).
* **Commented Credential Recovery:** Inspects commented-out code blocks (`dead_code`), flagging credentials disabled by developers rather than deleted.
* **Console Redaction Shield:** Detected secret snippets are automatically redacted in console logs to prevent credentials from being exposed in public build output:
  ```
  [CONTENT BREACH] Hardcoded Credential: config/settings.py
     -> ********[REDACTED]********
  ```

---

## Configuration & Allowlist Management

The scanner resolves configuration settings via `resolve_config()` (supporting local `.galaxyscope.yaml` files or global `gitgalaxy_config.py` definitions):

* **`ALLOWLIST_PATHS`:** Specifies path patterns (e.g., `tests/mocks/`, `fixtures/keys/`) exempt from blocking action. Matched secrets in allowlisted paths emit `[ALLOWLIST BYPASS]` warnings without failing the scan.
* **`DENYLIST_PATTERNS`:** Defines global wildcard rules for forbidden credential file extensions.
* **`APERTURE_CONFIG`:** Controls max file size limits and directory exclusion boundaries.

---

## CI/CD & Pre-Commit Execution

Vault Sentinel can be run standalone or integrated into `git` pre-commit hooks:

```bash
python3 -m gitgalaxy.tools.supply_chain_security.vault_sentinel /path/to/repo --config .galaxyscope.yaml
```

Upon completion, the tool outputs scan velocity metrics (`files/sec`), total leaks found, denylist blocks, and allowlist bypasses. If unauthorized secrets are discovered (`leaks_found > 0`), the script exits with status code `1`, blocking the commit or build step.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `vault_sentinel.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

