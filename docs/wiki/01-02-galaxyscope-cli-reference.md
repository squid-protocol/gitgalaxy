---
description: "> **Architecture: Hyper-Scale Static Analysis Wrapper**"
---
# GalaxyScope CLI Reference

> **Architecture: Hyper-Scale Static Analysis Wrapper**
>
> **Summary:** The `galaxyscope` Command Line Interface (CLI) is the primary entry point for the GitGalaxy blAST engine. It acts as the master orchestrator, initializing the physics engine, routing the target repository through the appropriate Language and Security Lenses, and dispatching the final JSON Intermediate Representation (IR) telemetry.

## The Contract

This page is the contract for the `galaxyscope` command. `blast` is the same program under a second name.

* Every flag, environment variable and exit code listed here does what its row says.
* The parser and this page must agree in both directions. `tests/test_cli_contract.py` fails on a listed flag the parser lacks, a parser flag this page omits, an exit code the code cannot produce, and a `galaxyscope` command in the docs that uses a flag the parser lacks. It also runs the example at the bottom of this page.
* Anything not listed is not promised. That includes log text, except the `BUILD FAILED:` prefix described under Exit Codes.
* Only the full flag spellings below are promised. The parser also accepts unambiguous abbreviations, such as `--out` for `--output`, but any new flag could make an abbreviation ambiguous, so scripts should not rely on them.

## Base Syntax

```bash
galaxyscope <target> [options]
```

* **`target`** (required): the path to a local repository directory, a ZIP archive, or a single file.

## Flags

### Output

| Flag | Promise |
| :--- | :--- |
| `-h`, `--help` | Prints usage and exits `0`. |
| `--output PATH` | Sets where reports go. A path that is an existing directory, or that has no file extension, is treated as a directory and created if needed; the name stem is `<target-name>_galaxy`. Any other path sets the stem: `--output out/scan.json` writes `out/scan_sarif.json` and so on. Without the flag, reports go to the current working directory, not the scanned repository. |
| `--debug` | Turns on debug-level logging on stderr. |

A default run writes seven reports:

| File | Contents | Written alone by |
| :--- | :--- | :--- |
| `<stem>_gpu.json` | The payload you drop into the [GitGalaxy.io](https://gitgalaxy.io) viewer | `--gpu-only` |
| `<stem>_master.db` | The SQLite database | `--db-only` |
| `<stem>_audit.json` | The forensic audit report | `--audit-only` |
| `<target-name>_galaxy_llm.md` | The architecture brief | `--llm-only` |
| `<target-name>_galaxy_graph.sqlite` | The graph database behind the brief | `--llm-only` |
| `<stem>_sarif.json` | SARIF results | `--sarif-only` |
| `<stem>_sbom.json` | CycloneDX SBOM | `--sbom-only` |

The two LLM files keep the target's name even when `--output` sets a stem. No file named plain `<stem>.json` is written.

### Recorder selection

| Flag | Promise |
| :--- | :--- |
| `--llm-only` | Runs only the LLM recorder. It writes a local brief and calls no model. |
| `--gpu-only` | Runs only the GPU recorder. |
| `--audit-only` | Runs only the audit recorder. |
| `--db-only` | Runs only the SQLite recorder. |
| `--sarif-only` | Runs only the SARIF exporter. |
| `--sbom-only` | Runs only the CycloneDX SBOM generator. |

Naming several of these runs each one named.

### CI gates

Gates are off by default. A gate that trips makes the scan exit `1` after every report has been written. A scan with no gate set never fails on what it found.

| Flag | Promise |
| :--- | :--- |
| `--fail-on-secrets` | Fails if any file has a hardcoded secret that is not marked as mitigated. |
| `--fail-on-malware` | Fails if ML threat inference flags a file. Inference needs `numpy`, `pandas` and `xgboost` (the `full` extra) and a model file, `gitgalaxy_malware_xgb_multiclass.json`, in `gitgalaxy/security/` or `gitgalaxy/utilities/`. The model does not ship with GitGalaxy. Without all of these the gate cannot fire, and the scan exits `0`. |
| `--max-risk-exposure N` | Fails if any file's highest risk vector is at or above `N` percent. `0.0` disables it. |
| `--max-systemic-threat N` | Fails if any file's structural magnitude times normalized blast radius is at or above `N`. `0.0` disables it. Limits set before #3112 must be re-tuned. |

**Gates run on an `--incremental` scan too.** A delta scan judges every file, unchanged ones included, with the same suppressions, so it fails on what a full scan fails on.

### Security and analysis

| Flag | Promise |
| :--- | :--- |
| `--paranoid` | Makes the `secrets_risk` vector more sensitive: its threshold drops from 3.0 to 0.5, its slope rises from 1.0 to 2.0, and the 2.0 cap on its carelessness amplifiers is lifted. No other vector or threshold changes. |
| `--ai-guardrails` | Enables Phase 5 (Zero-Trust AI Guardrails: `dev_agent_firewall.py` and `ai_appsec_sensor.py`). Off by default: without it the columns `agentic_isolation_risk`, `requires_hitl`, `hallucination_zone`, `silent_mutation_risk` and `appsec_god_mode` record `NULL` ("not evaluated"; `0` means "evaluated, no risk found") and no `GG-AGENT-GUARDRAIL` SARIF results are emitted. The engine never turns this on by itself. |
| `--shadow-patch-detected` | Declares that the payload hash changed without a version bump. When ML threat inference runs, every file with `file_impact` above 0.5 is forced to the Stealer / Trojan class at score 100, so `--fail-on-malware` then trips on it. |
| `--spec-alignment` | Measures and reports the Spec Alignment vector. Off by default; only useful if your code carries spec tags. |

### Mainframe and estate inputs

There is no mainframe switch: COBOL, JCL and related languages are detected like any other. The legacy tools (`cobol-refractor`, `cobol-to-java` and the forges) are separate commands.

| Flag | Promise |
| :--- | :--- |
| `--source-encoding CODEC` | Declares the estate's code page, tried after a BOM, UTF-16 and strict UTF-8 and before the cp1252 / Latin-1 guesses. Takes one codec, or comma-separated `GLOB=CODEC` pairs where the first match wins. An unknown codec exits `1` before any file is read. |
| `--copy-libraries FILE` | Reads a JSON or YAML file declaring each COPY library's directories and each program's search order. A bad file exits `1` before any file is read. |

### Delta scanning

| Flag | Promise |
| :--- | :--- |
| `--incremental DB_PATH` | Rehydrates from a baseline SQLite database and rescans only what `git diff` reports as changed. It writes only `<stem>_master.db`, and its output directory must already exist. If rehydration or the diff fails, it logs a warning and runs a full scan. |
| `--baseline COMMIT_SHA` | Picks the baseline commit for `--incremental`. Unset, the latest commit by date is used. Without `--incremental` it logs a warning and does nothing. |

### Dependency audit cache

The SBOM audit keeps a hash cache at `<target>/.gitgalaxy/dependency_cache.db` by default, so a scan writes that one directory inside the target. Use `--dependency-cache` or `--no-dependency-cache` to avoid it.

| Flag | Promise |
| :--- | :--- |
| `--dependency-cache DB_PATH` | Puts the cache at this path. |
| `--no-dependency-cache` | Turns the cache off and uses capped-sampling SBOM verification. |
| `--full-dependency-scan` | Ignores the per-package budget and verifies every dependency file this run. Has no effect in an exclusive mode that skips the SBOM. |
| `--dependency-scan-budget N` | Sets the most cache-miss files freshly scanned per package per run. Default 25. |

### Configuration and profiling

| Flag | Promise |
| :--- | :--- |
| `--config FILE` | Loads a YAML project config. Its `galaxyscope:` section can set any flag by name, such as `ai-guardrails: true`, and a value on the command line wins. The config is read only when this flag is passed: `.galaxyscope.yaml` is not discovered automatically. It needs the `yaml` extra. An unrecognized key exits `1`. A file that is missing, unreadable or not a YAML mapping, or a missing PyYAML, exits `1` before the scan: the file may hold your gates. |
| `--splicing-speed` | Profiles regex and file processing speeds, capped at 5000 files. |
| `--file-speed` | Profiles the phases of file processing. |

---

## Environment Variables

| Variable | Required | Promise |
| :--- | :--- | :--- |
| `GITGALAXY_LICENSE_KEY` | **No** | Your commercial key, or `COMMUNITY_FREE_TIER` for noncommercial use. Without a valid value the scan still runs, after a 5-second notice. Checked offline. May also be set in `~/.config/gitgalaxy/.env`. |
| `GALAXYSCOPE_MAX_WORKERS` | **No** | Extraction worker count. `1` forces a serial scan. Defaults to `os.cpu_count() - 1`, minimum 1. |
| `GG_JOB_CORES` | **No** | Worker count used when `GALAXYSCOPE_MAX_WORKERS` is unset, for a job holding a share of a shared machine. |
| `GITGALAXY_DISABLE_GIT_HISTORY` | **No** | `1` skips git history, so the history-based values are not measured. |
| `GITGALAXY_HISTORY_NOW` | **No** | Epoch seconds to use as "today" for the one-year history window, for reproducible fixtures. |
| `GITGALAXY_PREFETCH` | **No** | Read-ahead over the source files: `on`, `off`, or `auto` (the default). |
| `GITGALAXY_ASSESS_OFFLINE` | **No** | Internal. Set by `gitgalaxy assess` for its scan workers; not for direct use. |

The scan has no network client, so it needs no API key or offline switch: `--llm-only` and the guardrails run locally. `tests/test_cli_contract.py` fails if the engine imports one.

---

## Exit Codes

| Code | Meaning | When |
| :--- | :--- | :--- |
| `0` | The scan finished and no gate tripped. | Also returned for `--help`, and for a scan with findings but no gate set. |
| `1` | Fatal error, or a gate tripped. | A missing or unreadable target, a bad `--source-encoding` or `--copy-libraries`, a `--config` file that cannot be applied or holds an unrecognized key, or any engine failure. Also any gate under [CI gates](#ci-gates). |
| `2` | Bad command line. | An unknown flag, a missing `target`, or a bad flag value, reported by the argument parser before the scan starts. |

These are all the codes GalaxyScope sets. A few things to plan for:

* **Telling the two `1`s apart:** a gate logs one `BUILD FAILED:` line to stderr per failure, and its reports are complete. A fatal error logs `Critical failure during execution`, and reports may be missing.
* **`0` does not prove every report exists.** A failure inside the database, audit, LLM, SARIF or SBOM recorder is logged as an error and the scan still exits `0`. If a later step needs a report, check for the file.
* **Findings never change the exit code by themselves.** A scan only exits `1` on what it found if a gate is set.
* **Being killed** (Ctrl-C, a signal, out of memory) gives whatever code the OS or Python assigns. That is not part of this contract.

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
        run: galaxyscope ./ --paranoid --fail-on-secrets --output ./gitgalaxy_reports/
        
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
