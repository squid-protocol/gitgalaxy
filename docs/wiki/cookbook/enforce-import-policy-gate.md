---
description: "Set up the Import Policy Gate: import block and allow lists plus a secrets-risk gate, enforced by the standalone CLI."
---
# How to Enforce the Import Policy Gate

> **Fixed in #8595 (#8428):** the standalone CLI and the Action's `tool: import-policy-gate` now read the audit JSON's real keys and exit 1 on a counted threat. Before the fix they never blocked. In a `galaxyscope` scan the gate's result is recorded in the scan summary (`ecosystem_audits.firewall`) and does not fail the scan; only the standalone CLI sets an exit code. The enforcement gaps that remain are tracked in #8432.

## What the gate gates

The gate checks the scanned repository's **own** files. It does not read installed dependencies: `node_modules`, `venv`, `.venv`, `vendor` and `third_party` are excluded by the default scan config. For each file it checks:

1. **Imports against your lists** (`gitgalaxy_config.py` or `.galaxyscope.yaml`):
   * **Audit mode (default):** blocks packages listed in `BLACKLISTED_IMPORTS`. The list ships empty, so add entries before relying on it.
   * **Strict mode:** with `STRICT_IMPORT_MODE = True`, also blocks every package not in `APPROVED_IMPORTS`.
2. **One behavioural score:** the engine's `secrets_risk` score for the file, flagged at 50 or above. The score is multiplied by 10 for setup.py, `build.rs`, `preinstall.js` and `postinstall.js`.

Both checks are tested on hand-built inputs, and the import checks also end to end (a real scan of a planted repo, then the CLI on its audit JSON) in `tests/security_auditing/test_import_policy_gate.py`. There is no measured detection rate on real compromised packages.

What it does not check: network calls, typosquatting, Unicode homoglyphs, files hidden in images, I/O taint, or `package.json` install scripts (`.json` files are skipped). It also skips any path containing `/test/` or `/tests/` and any file name containing `test_` or `_test` (#8432). These gaps are tracked in #8432.

## Configuration

```python
# gitgalaxy_config.py (or the same keys in .galaxyscope.yaml)
STRICT_IMPORT_MODE = True
APPROVED_IMPORTS = ["requests", "numpy"]
BLACKLISTED_IMPORTS = ["event-stream"]
IMPORT_GATE_NETWORK_WEIGHTING = False  # opt-in: raises the multiplier for highly central files
```

## Running it

```bash
# A directory target runs a GalaxyScope scan first; a GalaxyScope audit JSON is also accepted.
# Exits 1 when it counts a blacklisted or (strict mode) unapproved import, or a secrets-risk file.
import-policy-gate . --config .galaxyscope.yaml
```

When the CLI counts a threat it prints a summary and exits 1:

```text
===========================================================================
 🧱 IMPORT POLICY GATE: SCAN SUMMARY
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

This is the format `import_policy_gate.py` prints, with placeholders; it is not output from a real run.

> **Read the full technical specification:** [Import Policy Gate](../04-03-import-policy-gate.md)

---

**[⬅️ Back to Master Index](../index.md)**
