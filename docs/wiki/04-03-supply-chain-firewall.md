# Supply Chain Firewall (Zero-Trust Dependency Gate)

> **File Reference:** [gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py)

The `supply_chain_firewall.py` module in `gitgalaxy/tools/supply_chain_security/` provides zero-trust dependency verification and behavioral policy enforcement. Operating as an in-memory logic gate during pipeline execution, the firewall consumes pre-tokenized artifact graph data to evaluate package imports, detect namespace hijacking, and enforce risk thresholds before third-party code reaches production build environments.

---

## In-Memory Graph Processing (Zero Disk I/O)

To ensure sub-second policy enforcement across large dependency trees, the firewall operates directly on the tokenized artifact graph (`parsed_files`) produced in early pipeline stages:

* Eliminates redundant file reads from disk during security policy evaluation.
* Evaluates raw package import declarations against configured allowlists, denylists, and policy flags.
* Integrates with `ResolvedConfig` (via `.galaxyscope.yaml` or `resolve_config()`) to honor project-specific security rules.

---

## Import Verification & Alias Resolution

The firewall evaluates every external `import` or `require` statement across supported source languages (`.js`, `.ts`, `.py`, `.php`, `.go`, `.rs`):

### 1. Package Normalization & Relative Import Shield
Internal relative imports (e.g., `./utils`, `../components`) are filtered out. Scoped packages (`@org/pkg`) and deep module paths (`lodash/get`) are normalized to root package names (`@org/pkg`, `lodash`) to prevent deep-path policy evasion.

### 2. Contextual Manifest Alias Resolution
The firewall traverses parent directory structures to locate the nearest manifest alias map (`alias_map`). If a package uses an internal alias, the firewall dereferences the alias to verify the true origin package:
* Prevents **Dependency Confusion** attacks where malicious public packages spoof trusted internal package aliases.

### 3. Policy Enforcement Rules

| Policy Check | Trigger Condition | Action |
| :--- | :--- | :--- |
| **Blacklisted Import** | Package matches `BLACKLISTED_IMPORTS` registry. | Triggers critical alert, increments `imports_blacklisted`, blocks build. |
| **Strict Mode Violation** | `STRICT_IMPORT_MODE` enabled and package is missing from `APPROVED_IMPORTS`. | Increments `imports_unknown`, flags policy violation, blocks build. |
| **Approved Import** | Package matches `APPROVED_IMPORTS` registry. | Increments `imports_whitelisted`, allows execution. |
| **Allowlist Bypass** | File path matches `ALLOWLIST_PATHS` pattern. | Bypasses import policy checks for designated test or mock files. |

---

## Behavioral Policy Enforcement & Risk Vectors

Rather than recomputing static analysis from scratch, the firewall reads risk vectors computed during metrics evaluation (`SignalProcessor.RISK_SCHEMA`). Risk categories evaluated include:

* **Hidden Malware Risk:** Obscured payloads, high string entropy, or hidden dynamic evaluation.
* **Data Injection Risk:** Unsanitized command execution or tainted I/O sinks.
* **Secrets Leak Risk:** Hardcoded API tokens or private key credentials.
* **Logic Bomb Risk:** Time-delayed execution triggers or environment probes.
* **Memory Corruption Risk:** Raw memory manipulation or buffer operations.

Risk scores are evaluated against a sigmoid block threshold (`_FIREWALL_BLOCK_THRESHOLD = 50.0`).

### Contextual Risk Multipliers

1. **Build-Time Execution Multiplier ($10.0\times$):** Build configuration scripts (`setup.py`, `build.rs`, `preinstall.js`, `postinstall.js`, `package.json`) run automatically during package installation. Because remote code execution in build scripts compromises the host environment prior to application launch, risk scores for these assets are multiplied by $10.0\times$.
2. **Network Centrality Multiplier (Opt-in):** When `FIREWALL_NETWORK_WEIGHTING` is active, files acting as central hubs in the dependency call graph (high downstream blast radius or betweenness centrality) receive dynamic risk score multipliers.

### Asset & Test Shields

* **Static Asset Shield:** Inert non-executable extensions (`.svg`, `.xml`, `.html`, `.css`, `.md`, `.json`, `.yaml`, `.d.ts`) bypass behavioral heuristics.
* **Test Suite Shield:** Unit test files (`/test/`, `/tests/`, `test_*`, `*_test`) are exempted from behavioral risk gating to prevent false positives caused by test mocks and fixture data.

---

## CI/CD Execution Modes

The firewall supports both programmatic integration and standalone CLI execution:

### Programmatic Invocation (`run_firewall_audit`)

```python
from gitgalaxy.tools.supply_chain_security.supply_chain_firewall import run_firewall_audit

results = run_firewall_audit(
    parsed_files=repository_graph,
    alias_map=manifest_aliases,
    config=resolved_config
)
```

### Standalone CLI Execution

```bash
python3 -m gitgalaxy.tools.supply_chain_security.supply_chain_firewall /path/to/results.json --config .galaxyscope.yaml
```

If any active threats or unauthorized blacklisted imports are detected (`threats_found > 0`), the firewall exits with status code `1`, causing the CI/CD pipeline step to fail securely.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `supply_chain_firewall.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive WebGPU visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

