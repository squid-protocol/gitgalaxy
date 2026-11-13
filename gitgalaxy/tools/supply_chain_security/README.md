# GitGalaxy Security: Supply Chain & CI/CD Defense Suite

This directory contains the CI/CD gating mechanisms, pre-commit hooks, and dependency validation engines for the GitGalaxy architecture. 

Software Composition Analysis (SCA) tools typically work from manifests: they read `package.json` or `requirements.txt` and look the declared versions up in CVE databases. The tools here instead read the repository's own source and files with GitGalaxy's structural signature engine. They do not replace an SCA tool, and no comparison against one has been run.

> **Known bug (#8428): the standalone `supply-chain-firewall` CLI, and `tool: supply-chain-firewall` in the GitHub Action, currently never block on real scan output.** The CLI loads the audit JSON and hands its file entries to the gate, which reads `raw_imports` and `risk_vector`; the audit JSON has neither key, so every import check and the risk gate are skipped and the run exits 0. The engine-internal call (`galaxyscope.py`, `run_firewall_audit(repository_graph, ...)`) receives the in-memory graph and does evaluate imports and risk; its result is recorded in the scan summary (`ecosystem_audits.firewall`) and does not fail the scan. Further enforcement gaps are tracked in #8432.

---

## What each tool checks

### 1. Supply Chain Firewall (`supply_chain_firewall.py`)
The firewall gates the repository's **own** files. `node_modules`, `venv`, `.venv`, `vendor` and `third_party` are excluded by the default scan config (`gitgalaxy/standards/gitgalaxy_config.py`), so installed dependency code is not read. For each scanned file it checks two things:

* **Imports.** Each import in the file is reduced to its root package and compared with the config lists. Audit mode (default) blocks packages in `BLACKLISTED_IMPORTS`; strict mode (`STRICT_IMPORT_MODE = True`) also blocks anything not in `APPROVED_IMPORTS`. `BLACKLISTED_IMPORTS` ships empty, so audit mode blocks nothing until you add entries. When the engine passes a manifest alias map, an aliased package is resolved to its true name before the blacklist check (tested in `test_alias_spoofing_detection`; engine path only, and it needs a blacklist entry to block anything).
* **One behavioural score.** The gate reads a single risk vector, `secrets_risk`, from the scores the engine already computed (`_FIREWALL_RISK_MAP`), and flags the file when the score reaches 50. The score is multiplied by 10 for files named setup.py, `build.rs`, `preinstall.js` or `postinstall.js`. A network-centrality multiplier exists but is off unless `FIREWALL_NETWORK_WEIGHTING = True`.

What it does **not** do: it does not detect network requests, typosquatting, I/O hooks or install-time hooks; it does not parse `package.json` scripts (`.json` files are skipped before the gate, so `package.json` never gets the 10x multiplier); and it skips any file whose path contains `/test/` or `/tests/`, or whose name contains `test_` or `_test` (a substring match, #8432). The engine's typosquat check only logs and counts.

### 2. Vault Sentinel (`vault_sentinel.py`)
Two tiers. Tier 0 fails a file by its name alone (for example `.pem`, `id_rsa`, `.env`). Tier 1 reads file content and reports `hardcoded_secrets` matches (cloud keys, tokens, private keys, passwords) plus the extra patterns in `vault_sentinel.py`'s `EXTRA_SECRETS`. Both tiers are tested on planted inputs (`test_vault_sentinel_control.py`); there is no measured recall on real leaks.

### 3. X-Ray / Binary Anomaly Detector (`binary_anomaly_detector.py`)
Checks files for byte-level anomalies:

* **Magic-byte mismatch:** a file whose first bytes do not match its extension (for example an executable named `logo.png`).
* **Embedded execution headers** in the first 8 KB: ELF, Mach-O, WebAssembly and `#!/bin/` anywhere; `MZ` only at offset 0. A `#!/bin/` shebang in a `.sh`/`.bash`/`.zsh`/`.command` file is exempt.
* **Entropy, three thresholds with different scopes:** string literals in the first 8 KB, Shannon entropy above 4.8; the first 8 KB read as raw bytes (`scan_binary`), above 7.95; long encoded runs (256+ characters) anywhere in a text file, above 5.0 (`DENSE_RUN_ENTROPY`). Files with an extension in `XRAY_BYPASS_EXTENSIONS` (by default `.json`, `.gz`, `.zip`, `.tar`, `.png`, `.jpg`, `.jpeg`, `.ico`, `.yml`) get the magic-byte check only.
* **Repeated indexed XOR:** three or more `buf[i] ^= k;` statements.

These checks are tested on planted inputs (`test_xray_control.py`, `test_disguised_executable_4126.py`); there is no measured detection rate on real malware. Images are checked only for a matching header; steganography is not detected.

### 4. Manifest Auditor (`manifest_parser.py`, in `gitgalaxy/security/`)
Parses NPM and PyPI manifests into a resolution map, normalizes aliases to their upstream package names, and flags direct-URI resolutions and insecure registry settings (for example `ngrok` hosts in `pip.conf`). The alias map is passed to the engine-internal firewall. The flags it writes are not read by the firewall or any other gate; they are logged only (#8432).

---

## Memory and file size (X-Ray)

X-Ray reads the first 8 KB of every file for the header, XOR and string-entropy checks. The dense-run check then reads the **whole** file when it is text (no NUL byte in the first 8 KB) and no larger than 5 MB (`MAX_DENSE_SCAN_BYTES`); this is how a payload past the first 8 KB is caught (`test_a_large_payload_after_the_first_8_kb_fails`). Binary files and text files over 5 MB are only read up to 8 KB, so anything past that point in them is not examined.

---

## Historical showcase runs

The runs below were made on 2026-04-22. No command, config or output artifact was committed for them, and they have not been re-run against the current code. Treat them as historical, not as reproducible results. An earlier firewall showcase on Terraform was removed: with the bug above, the current CLI cannot produce its output.

#### Vault Sentinel on tRPC
The sentinel evaluated 871 files, scanned the content of 695 of them in **0.53 seconds**, and reported 7 environment files and one hardcoded API key. *Single run, measured 2026-04-22; not a current or average figure, and not reproducible from a committed artifact.*

![Vault Sentinel Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/vault_sentinel_scan.gif)

#### X-Ray on pwntools
pwntools ships compiled binaries and shellcode. The detector processed 95 files at **2,825 files per second** and reported 13 embedded `ELF` headers. *Single run, measured 2026-04-22; not a current or average figure, and not reproducible from a committed artifact.*

![Binary Anomaly Detector Demo](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/xray_inspector_scan.gif)

~~~text
===========================================================================
 BINARY ANOMALY DETECTOR: SCAN SUMMARY
===========================================================================
 Files Evaluated    : 95
 Files Deep Scanned : 95
 Time Elapsed       : 0.03 seconds
 Scan Velocity      : 2,825 files/sec
---------------------------------------------------------------------------
 Anomalies Detected : 13
---------------------------------------------------------------------------
 [BLOCKING ACTION] 13 structural anomalies detected. Failing pipeline.
~~~

---

## CI/CD & Pre-Commit Integration

Vault Sentinel and X-Ray exit 1 on a finding, so they can fail a commit hook or a CI step. The firewall CLI does too in principle, but see the known bug above (#8428).

**Local Pre-Commit Hook Integration:**
To run the Vault Sentinel automatically before every commit, add this configuration to your `.pre-commit-config.yaml` file:

~~~yaml
repos:
  - repo: local
    hooks:
      - id: gitgalaxy-vault-sentinel
        name: GitGalaxy Vault Sentinel
        entry: vault-sentinel .
        language: system
        pass_filenames: false
        always_run: true
~~~

(`vault-sentinel` takes one target, a directory or a file, so the hook scans the repository root rather than receiving the staged file list.)

**GitHub Actions Integration:**
The tools can run through the [GitGalaxy GitHub Action](https://github.com/marketplace/actions/gitgalaxy-scanner). The example below runs the firewall step; until #8428 is fixed it will not block.

~~~yaml
name: GitGalaxy Zero-Trust Audit
on: [pull_request]

jobs:
  gitgalaxy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run GitGalaxy Supply Chain Firewall
        uses: squid-protocol/gitgalaxy@v2.0.7
        with:
          tool: 'supply-chain-firewall'
~~~

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Security is the threat inference and enforcement layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.