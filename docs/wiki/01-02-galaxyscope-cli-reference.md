# GalaxyScope CLI Reference

> **Architecture: Hyper-Scale Static Analysis Wrapper**
>
> **Summary:** The `galaxyscope` Command Line Interface (CLI) is the primary entry point for the GitGalaxy blAST engine. It acts as the master orchestrator, initializing the physics engine, routing the target repository through the appropriate Language and Security Lenses, and dispatching the final JSON Intermediate Representation (IR) telemetry.

## Base Syntax

```bash
galaxyscope [target_path] [options]
```

* **`target_path`**: The absolute or relative path to the local repository directory, ZIP archive, or individual file you wish to analyze.



## Global Execution Flags

The pipeline's behavior can be heavily modified at runtime to optimize for speed, security, or compliance.

### Security & Physics Tuning
* **`--paranoid`**
  * **Action:** Drops the threshold parameters in the Biaxial Security Lens and increases the multiplier for entropy and structural drift.
  * **Use Case:** Mandatory for auditing third-party vendor code or supply-chain injections where malicious evasion is highly probable.
* **`--airgap`**
  * **Action:** Physically disables the `llm_recorder.py`, `ai_appsec_sensor.py`, and any sub-modules requiring external network requests.
  * **Use Case:** Enterprise compliance mode. Guarantees 100% offline execution.

### Architectural Routing
* **`--legacy`**
  * **Action:** Forces the engine to route the payload through the Legacy Modernization spokes (COBOL Refractor, JCL Forge, DAG Architect).
  * **Use Case:** Explicitly processing mainframe payloads that might otherwise be misclassified as generic text by the Language Lens.
* **`--out [path]`**
  * **Action:** Redirects the generated `_galaxy.json`, SQLite databases, and audit reports to a specific directory instead of the repository root.

---

## Environment Variables

For automated CI/CD pipelines, GalaxyScope relies on the following environment variables to configure its external integrations and compute boundaries.

| Variable | Required | Description |
| :--- | :--- | :--- |
| `GITGALAXY_LLM_KEY` | **No** | The API key (OpenAI/Anthropic) required for the `llm_recorder` and Autonomous Agent Ticket generators. Ignored if `--airgap` is passed. |
| `GITGALAXY_WORKERS` | **No** | Number of parallel CPU threads to dedicate to the static analysis engine. Defaults to `os.cpu_count() - 1`. |
| `GITGALAXY_RAM_LIMIT_MB`| **No** | Forces the IR State Manager to drop from RAM to SQLite disk-storage early if the host machine has strict memory limits. |

---

## Deterministic Exit Codes

GalaxyScope utilizes strict exit codes to allow CI/CD pipelines to autonomously block pull requests based on architectural or security failures.

* **`0` (Success):** The repository was successfully mapped, and the resulting `_galaxy.json` was generated without critical warnings.
* **`1` (Fatal Error):** The engine encountered a catastrophic runtime failure (e.g., target directory not found, insufficient read permissions, out of disk space).
* **`3` (Security Breach):** The Biaxial Security Lens detected a critical threat mass (e.g., Injection Surface, Obscured Payload, or Hardcoded Secret leak). The pipeline is halted and the repository should be quarantined.
* **`4` (Architectural Deadlock):** The DAG Architect detected an unresolvable cyclic dependency (e.g., File A blocks File B, which blocks File A) preventing a topological sort.

---

## Pipeline Integration Example (GitHub Actions)

GalaxyScope is designed to run seamlessly in standard CI/CD pipelines. Because it evaluates raw static text, it does not require a complex build environment to execute.

```yaml
name: GitGalaxy Structural Audit
on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        
      - name: Install GitGalaxy
        run: pip install gitgalaxy
        
      - name: Execute GalaxyScope (Paranoid Mode)
        run: galaxyscope ./ --paranoid --airgap --out ./gitgalaxy_reports/
        
      - name: Upload Telemetry Artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: gitgalaxy-telemetry
          path: ./gitgalaxy_reports/
```

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
