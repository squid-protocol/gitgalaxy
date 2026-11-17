---
description: "Set up the Supply Chain Firewall: import block and allow lists plus a secrets-risk gate. Known bug #8428: the standalone CLI does not block yet."
---
# How to Enforce the Supply Chain Firewall

> **Known bug (#8428): the standalone `supply-chain-firewall` CLI, and `tool: supply-chain-firewall` in the GitHub Action, currently never block on real scan output.** The CLI hands the gate entries from the audit JSON, which lack the `raw_imports` and `risk_vector` keys the gate reads, so every check is skipped and the run exits 0. Until #8428 is fixed, the steps below set the policy up but do not fail a build. The firewall does run inside a `galaxyscope` scan, where its result is recorded in the scan summary (`ecosystem_audits.firewall`) without failing the scan.

## What the firewall gates

The firewall checks the scanned repository's **own** files. It does not read installed dependencies: `node_modules`, `venv`, `.venv`, `vendor` and `third_party` are excluded by the default scan config. For each file it checks:

1. **Imports against your lists** (`gitgalaxy_config.py` or `.galaxyscope.yaml`):
   * **Audit mode (default):** blocks packages listed in `BLACKLISTED_IMPORTS`. The list ships empty, so add entries before relying on it.
   * **Strict mode:** with `STRICT_IMPORT_MODE = True`, also blocks every package not in `APPROVED_IMPORTS`.
2. **One behavioural score:** the engine's `secrets_risk` score for the file, flagged at 50 or above. The score is multiplied by 10 for setup.py, `build.rs`, `preinstall.js` and `postinstall.js`.

Both checks are tested on hand-built inputs (`tests/security_auditing/test_supply_chain_firewall.py`). There is no measured detection rate on real compromised packages.

What it does not check: network calls, typosquatting, Unicode homoglyphs, files hidden in images, I/O taint, or `package.json` install scripts (`.json` files are skipped). It also skips any path containing `/test/` or `/tests/` and any file name containing `test_` or `_test` (#8432). These gaps are tracked in #8432.

## Configuration

```python
# gitgalaxy_config.py (or the same keys in .galaxyscope.yaml)
STRICT_IMPORT_MODE = True
APPROVED_IMPORTS = ["requests", "numpy"]
BLACKLISTED_IMPORTS = ["event-stream"]
FIREWALL_NETWORK_WEIGHTING = False  # opt-in: raises the multiplier for highly central files
```

## Running it

```bash
# A directory target runs a GalaxyScope scan first; a GalaxyScope audit JSON is also accepted.
# Currently exits 0 on real input regardless of findings (#8428).
supply-chain-firewall . --config .galaxyscope.yaml
```

When the CLI counts a threat it prints a summary and exits 1:

```text
===========================================================================
 🧱 SUPPLY CHAIN FIREWALL: SCAN SUMMARY
===========================================================================
 Mode                 : Strict (Exclude Blacklist and Unknown)
 Files Evaluated      : <n>
---------------------------------------------------------------------------
 Approved Packages    : <n>
 Banned Packages      : <n>
 Unknown Packages     : <n>
---------------------------------------------------------------------------
 Active Threats       : <n>
 Allowlist Bypasses   : <n>
---------------------------------------------------------------------------
 [BLOCKING ACTION] <n> high-risk dependencies or policy violations blocked.
```

This is the format `supply_chain_firewall.py` prints, with placeholders; it is not output from a real run.

> **Read the full technical specification:** [Supply Chain Firewall](../04-03-supply-chain-firewall.md)

---

**[⬅️ Back to Master Index](../index.md)**
