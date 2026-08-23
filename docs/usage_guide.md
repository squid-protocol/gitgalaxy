# GitGalaxy Usage Guide

This guide covers the primary tools and execution paths for GitGalaxy. GitGalaxy is not just a single script, but a suite of focused sentinels and mapping tools that operate on the same core structural extraction engine.

## 1. The Orchestrator (Reporting & Observability)

**`galaxyscope`** is the core mapping engine. It reads the repository, extracts structural signatures, calculates risk physics (Cognitive Load, State Flux, Instructional Density), and generates multiple output formats.

**Usage:**
```bash
# Scan the current directory
galaxyscope .

# Scan a specific repository and output an LLM-friendly architecture brief
galaxyscope /path/to/repo --llm-only

# Generate a CycloneDX SBOM
galaxyscope . --sbom-only
```
*Note: `galaxyscope` does not fail pipelines (exit code 1) on findings; it is strictly for reporting, visualization, and cartography.*

## 2. The Sentinels (Zero-Trust Enforcement)

These tools are designed for CI/CD environments. They will `sys.exit(1)` and break the build instantly if a threat is detected.

* **`vault-sentinel`**: High-speed secrets scanner. Detects hardcoded API keys, exposed `.env` variables, and cryptographic vault leaks.
  ```bash
  vault-sentinel .
  ```
* **`xray-inspector`**: Binary and Obfuscation scanner. Hunts for high-entropy encrypted payloads, sub-atomic XOR loops, and hidden executables disguised via magic byte mismatches.
  ```bash
  xray-inspector .
  ```
* **`supply-chain-firewall`**: Dependency execution verifier. Blocks blacklisted imports, identifies shadowed/steganographic imports, and flags tainted I/O access.
  ```bash
  supply-chain-firewall .
  ```

## 3. AI Agent Guardrails (Safe Autonomous Development)

If your team uses autonomous AI agents (Cursor, Claude, Devin), these sentinels ensure they do not create catastrophic security loops or collapse under cognitive load.

* **`ai-appsec-sensor`**: Hunts for weaponized AI architectures (e.g., LLMs given access to OS commands or unfiltered network sockets).
  ```bash
  ai-appsec-sensor .
  ```
* **`dev-agent-firewall`**: Evaluates algorithmic complexity and blast radius to determine if an AI has the context to safely modify the code. Flags "Context Window Black Holes".
  ```bash
  dev-agent-firewall .
  ```

## 4. Specialized Hunters & Artifacts

* **`api-network-map`**: Compares source-code routing against official OpenAPI/Swagger specs to hunt down undocumented Shadow APIs.
  ```bash
  api-network-map . --swagger ./docs/openapi.yaml
  ```
* **`pii-leak-hunter`**: A high-velocity streaming binary scanner. Scrubs database dumps or raw production logs for exposed credit cards, SSNs, and AWS keys, generating a safely masked evidence log.
  ```bash
  pii-leak-hunter /path/to/massive/db_dump.sql
  ```

## Advanced Configuration: Paranoid Mode

When running tools, you can pass the `--paranoid` flag to lower safety thresholds to their absolute minimum.

```bash
galaxyscope . --paranoid
```
**Warning:** This mode is highly false-positive rich by design. It is intended for rigorous security audits and aggressive red-teaming, not standard CI/CD gating.

---
For GitHub Actions integration, see the [GitHub Action Integration Guide](../github-action-readme.md).
