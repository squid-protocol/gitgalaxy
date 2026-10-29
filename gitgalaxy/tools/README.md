<div align="center">

# GitGalaxy Tools

### Standalone execution controllers for CICS-to-Java migration, offline estate readiness, supply-chain defense, API auditing, and log streaming.

`gitgalaxy/tools/` contains the operational tool suites built on top of the GitGalaxy engine.
Each package takes the structural facts extracted by the core scanner (or the deterministic COBOL/CICS
parser) and turns them into concrete engineering outputs: an offline mainframe readiness assessment,
a compiling Spring Boot project with byte-for-byte equivalence proofs against GnuCOBOL, a supply-chain
and secrets firewall, an OpenAPI vs. code route auditor, or a streaming PII log scanner.

<table>
<tr>
<td align="center" width="190"><h2>live</h2></td>
<td align="center" width="190"><h2>0 bytes</h2></td>
<td align="center" width="190"><h2>17 / 17</h2></td>
<td align="center" width="190"><h2>5 suites</h2></td>
</tr>
<tr>
<td align="center" valign="top"><sub><strong>CICS &amp; batch programs proven (L2+)</strong><br />counted on the <a href="https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md">progress page</a> · 6 burned estates<br /><em><a href="./cobol_to_java/README.md">cobol-to-java</a> · oracle is GnuCOBOL</em></sub></td>
<td align="center" valign="top"><sub><strong>source leaked by <code>gitgalaxy assess</code></strong><br />socket guard + closed-vocabulary schema<br /><em><a href="./readiness/README.md">readiness scanner</a> · offline &amp; read-only</em></sub></td>
<td align="center" valign="top"><sub><strong>Spring Boot target configs built</strong><br />Java 17 &amp; 21 · Maven &amp; Gradle · 5 DBs<br /><em><a href="./cobol_to_java/README.md#choosing-the-java-you-get-the-target-config">target matrix</a> · compiling ≠ proven</em></sub></td>
<td align="center" valign="top"><sub><strong>standalone CLI tool suites</strong><br />local CLI &amp; CI/CD GitHub Action<br /><em><a href="#pick-your-suite">the 5 suites</a> · zero-dep core</em></sub></td>
</tr>
</table>

<a href="#pick-your-suite"><strong>Suites</strong></a> ·
<a href="#mainframe-modernization-and-cics-to-java"><strong>CICS to Java</strong></a> ·
<a href="#security-network-and-log-auditing-suites"><strong>Security &amp; auditing</strong></a> ·
<a href="#running-from-the-cli-or-ci"><strong>CLI &amp; CI/CD</strong></a>

</div>

---

<a id="pick-your-suite"></a>

## Pick your suite

| Suite | Directory | Primary CLI / Entry Point | What it does |
|---|---|---|---|
| **CICS to Java & Proof Harness** | [`cobol_to_java/`](./cobol_to_java/README.md) | `cobol-to-java`, `port_runner` | Generates a Spring Boot project from verified facts, translates COBOL/CICS deterministically (`det-port`) or via porting tickets, and proves equivalence against GnuCOBOL + CICS/Db2/LE models. |
| **Offline Estate Readiness** | [`readiness/`](./readiness/README.md) | `gitgalaxy assess` | Runs an air-gapped, read-only assessment of a COBOL/CICS estate: tags programs across 5 CICS eras (`era_tags.py`), counts whole translations vs. holes, and validates zero source text leakage. |
| **Mainframe Fact Extraction** | [`cobol_to_cobol/`](./cobol_to_cobol/README.md) | `cobol-refractor` | Expands copybooks, extracts `GalaxyIR` record layouts, parses CSD and twelve CICS macro table families (`DFHSIT`, `PCT`, `PPT`, `FCT`, `DCT` and more), finds dead code, and generates PostgreSQL DDL & least-privilege JCL. |
| **Supply Chain & Secrets Defense** | [`supply_chain_security/`](./supply_chain_security/README.md) | `supply-chain-firewall`, `vault-sentinel`, `xray-inspector` | Audits dependency install graphs for network/RCE patterns, scans commits for exposed keys, and flags high-entropy binary anomalies. |
| **API Network Auditing** | [`network_auditing/`](./network_auditing/README.md) | `api-network-map` | Extracts inbound and outbound HTTP routing across web frameworks and diffs them against OpenAPI/Swagger specs to surface undocumented endpoints. |
| **Streaming Log & PII Scanning** | [`terabyte_log_scanning/`](./terabyte_log_scanning/README.md) | `pii-leak-hunter`, `terabyte-log-scanner` | Streams large log files in bounded memory to redact PII patterns and correlate runtime log traces with static repository files. |

---

<a id="mainframe-modernization-and-cics-to-java"></a>

## Mainframe modernization and CICS to Java

The mainframe toolchain spans three packages that run in sequence:

1. **Assess ([`readiness/`](./readiness/README.md)):** `gitgalaxy assess /path/to/estate` runs locally with an active socket guard, classifies every program across **Era 0** (CICS macro level) through **Era 4** (Enterprise COBOL channels, containers, web, and async APIs), and outputs a schema-validated JSON report with optional keyed-hash identifier redaction (`--redact`).
2. **Extract ([`cobol_to_cobol/`](./cobol_to_cobol/README.md)):** `cobol-refractor /path/to/estate --scan` joins the engine's structural database with copybook-expanded record layouts, BMS screen maps, JCL dataset bindings, and CICS CSD/macro tables into a verified `skeleton.json` staging directory.
3. **Translate & Prove ([`cobol_to_java/`](./cobol_to_java/README.md)):**
   - `cobol-to-java <staging-dir>` generates the Spring Boot skeleton (JPA/VSAM repositories, JDBC/Db2 repositories, Spring Batch jobs, REST controllers, BMS view models, and `migration_worklist.md` for any unverified fact).
   - `port_runner run --backend det` translates the business logic with **no model** into calls against `cobolrt` (guided by the [CICS command specification](../standards/cics/README.md)), or dispatches a scoped porting ticket to a model/human porter, with optional method-by-method LLM readability refinement (`port_runner refine`).
   - `port_runner prove` executes both the original COBOL (under GnuCOBOL + CICS/Db2/LE models) and the Java port across normal and fault-injected scenarios, recording paragraph coverage (`L3`), branch coverage (`L4`), and mutation kill rates in a machine-checked `evidence.json` certificate.

---

<a id="security-network-and-log-auditing-suites"></a>

## Security, network, and log auditing suites

- **[Supply Chain & CI/CD Defense](./supply_chain_security/README.md):**
  - `supply-chain-firewall`: inspects third-party packages for outbound network calls, typosquatting, and install-time execution hooks.
  - `vault-sentinel`: two-stage regex + Shannon entropy scanner for secrets and credentials.
  - `xray-inspector`: static binary header and entropy triage.
- **[API Network Auditing](./network_auditing/README.md):**
  - `api-network-map`: compares extracted controller routes (Spring, Express, FastAPI, Flask, Go, etc.) against committed OpenAPI/Swagger specifications.
- **[High-Velocity Log Streaming](./terabyte_log_scanning/README.md):**
  - `pii-leak-hunter` & `terabyte-log-scanner`: line-by-line streaming scanners for redacting sensitive tokens and mapping log events back to source files.

*(Note: the core AI AppSec Sensor and Dev Agent Firewall run inside the main analysis engine and live in [`gitgalaxy/security/`](../security/README.md).)*

---

<a id="running-from-the-cli-or-ci"></a>

## Running from the CLI or CI

### 1. Local CLI

Installing `gitgalaxy` registers the console scripts directly:

```sh
pip install gitgalaxy                     # zero-dependency core + CLI controllers
pip install "gitgalaxy[translator]"       # + tree-sitter-language-pack for CICS-to-Java & gitgalaxy assess

gitgalaxy assess ./estate --out readiness.json
cobol-refractor ./estate --scan
cobol-to-java ./estate_gitgalaxy_clean
vault-sentinel .
api-network-map ./src
pii-leak-hunter ./logs/app.log
```

### 2. GitHub Actions

```yaml
      - name: Run GitGalaxy Tool
        uses: squid-protocol/gitgalaxy@main
        with:
          tool: 'vault-sentinel'  # or: galaxyscope, supply-chain-firewall, xray-inspector, pii-leak-hunter, api-network-map
          target: '.'
```

---

## Explore further

| Resource | What it contains |
|---|---|
| [Root GitGalaxy README](../../README.md) | Overview of the scanner, speed benchmarks, accuracy validation, and CICS-to-Java summary |
| [CICS to Java (`cobol_to_java/README.md`)](./cobol_to_java/README.md) | Full pipeline, `det` translator, CICS era coverage, and `L0–L5` / `E0–E4` evidence scorecards |
| [Offline Readiness (`readiness/README.md`)](./readiness/README.md) | `gitgalaxy assess`, `era_tags.py`, and zero-leakage schema validation |
| [Mainframe Extraction (`cobol_to_cobol/README.md`)](./cobol_to_cobol/README.md) | `cobol-refractor`, `GalaxyIR`, dead-code reaper, and JCL/DDL forges |
| [CICS Command Spec (`../standards/cics/README.md`)](../standards/cics/README.md) | The CICS command specification and generated Java/C runtime tables |
| [GitGalaxy Standards (`../standards/README.md`)](../standards/README.md) | Language definitions, ReDoS bounds, and calibration constants |