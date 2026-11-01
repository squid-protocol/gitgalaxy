<div align="center">

# Offline Readiness Scanner (`gitgalaxy assess`)

### Measure how much of a CICS and COBOL estate translates today—offline, read-only, and with zero customer source text in the report.

`gitgalaxy/tools/readiness/` powers `gitgalaxy assess`: the front-door assessment command a customer
runs on their own machine before any migration work begins. It installs a process-wide network
socket guard before touching the disk, reads the estate in read-only mode using a temporary working
directory outside the estate, inventories every program's COBOL, CICS, SQL, and copybook features,
tags each program by its CICS era from concrete source tells, and validates the output against a
strict allowlist schema that rejects any leaked source text or unredacted identifier.

<table>
<tr>
<td align="center" width="190"><h2>0 bytes</h2></td>
<td align="center" width="190"><h2>5 eras</h2></td>
<td align="center" width="190"><h2>25 tells</h2></td>
<td align="center" width="190"><h2>100%</h2></td>
</tr>
<tr>
<td align="center" valign="top"><sub><strong>network &amp; source text exfiltration</strong><br />socket guard + allowlist schema projection<br /><em><a href="#privacy-and-the-zero-leakage-contract">offline guard</a> · exit 3 on schema violation</em></sub></td>
<td align="center" valign="top"><sub><strong>CICS &amp; COBOL eras classified</strong><br />Era 0 macro level through Era 4 Enterprise COBOL<br /><em><a href="#cics-era-tagging-era_tagspy">era model</a> · detects mixed-era code</em></sub></td>
<td align="center" valign="top"><sub><strong>source &amp; copybook tells tracked</strong><br />each backed by an IBM manual or release citation<br /><em><a href="#cics-era-tagging-era_tagspy">the 25 tells</a> · copy-expanded pass</em></sub></td>
<td align="center" valign="top"><sub><strong>local, air-gapped execution</strong><br />no Docker, no Db2 container, no JDK required<br /><em><a href="#quickstart">quickstart</a> · uses the Python det parser</em></sub></td>
</tr>
</table>

<a href="#quickstart"><strong>Quickstart</strong></a> ·
<a href="#what-you-ask-what-you-get"><strong>Ask / get</strong></a> ·
<a href="#privacy-and-the-zero-leakage-contract"><strong>Zero-leakage contract</strong></a> ·
<a href="#cics-era-tagging-era_tagspy"><strong>CICS eras &amp; tells</strong></a> ·
<a href="#modules"><strong>Modules</strong></a> ·
<a href="#limits"><strong>Limits</strong></a>

</div>

---

<a id="quickstart"></a>

## Quickstart

```sh
# Run an offline, read-only assessment of a COBOL / CICS / BMS estate
gitgalaxy assess /path/to/estate --out readiness.json

# Supply estate compiler / LE / Db2 / CICS options (#4704)
gitgalaxy assess /path/to/estate --options estate_options.json --out readiness.json

# Redact all program and copybook names into keyed HMAC/SHA-256 labels
gitgalaxy assess /path/to/estate --redact --redact-key-file my.key --out readiness_redacted.json

# Tag individual COBOL programs by era directly from the CLI
python -m gitgalaxy.tools.readiness.era_tags /path/to/estate/cbl/*.cbl
```

`gitgalaxy assess` needs no Docker daemon, no Db2 instance, and no Java toolchain—it parses COBOL
and `EXEC CICS` directly in Python (`pip install "gitgalaxy[translator]"`).

---

<a id="what-you-ask-what-you-get"></a>

## What you ask, what you get

| You ask | `gitgalaxy assess` gives you |
|---|---|
| *Can we run this on an air-gapped or restricted machine?* | [`offline.py`](offline.py) monkey-patches `socket.socket` and blocks outbound network calls before the estate directory is opened. |
| *Will it write `.sqlite` or temp files into our source tree?* | Never. All intermediate scan databases and generated BMS copybooks live in a temporary directory outside the estate and are deleted on exit; passing `--out` inside the estate directory is rejected with exit code `2`. |
| *Could a parser error or refusal message accidentally include a line of our COBOL source or a customer literal?* | No. [`schema.py`](schema.py) projects the raw inventory through a closed vocabulary allowlist (COBOL verbs, [`gitgalaxy/standards/cics`](../../standards/cics/README.md) command/option names, SQL clauses, and compiler options) and validates the result before writing a single byte to disk. |
| *What if even our 8-character program and copybook names are confidential?* | `--redact` hashes every member and copybook name with a 32-byte key (`--redact-key-file` for repeatable labels across runs, or a fresh random key per run for unlinkable labels). |
| *What eras of COBOL and CICS are in our repository, including hidden inside copybooks?* | [`era_tags.py`](era_tags.py) scans both the program text and its resolved copybooks across 25 constructs (`Era 0` macro level through `Era 4` Enterprise COBOL), flagging `mixed`-era layered code and `via_copybook` tells. |

---

<a id="privacy-and-the-zero-leakage-contract"></a>

## Privacy and the zero-leakage contract

Enterprise mainframe source contains proprietary data names, account formats, and internal system
identifiers. `gitgalaxy assess` enforces four independent barriers so the resulting JSON report can
be reviewed by security teams and shared safely:

1. **Pre-read network lock ([`offline.py`](offline.py)):** `offline.install()` replaces socket creation and network connection hooks before any file in the estate is read.
2. **Read-only estate boundary ([`assess.py`](assess.py)):** Verifies that neither `TMPDIR` nor `--out` resolves inside the estate directory.
3. **Closed-vocabulary projection ([`schema.py`](schema.py)):** `schema.project()` strips all source lines, variable names, paragraph names, literals, and file paths, retaining only structural counts and vocabulary tokens known to the engine and the [CICS command spec](../../standards/cics/README.md).
4. **Pre-write schema & leak gate ([`schema.py`](schema.py)):** `schema.validate()` checks the projected report against the JSON schema and vocabulary rules. If any check fails, nothing is written and `gitgalaxy assess` exits with code `3`.

---

<a id="cics-era-tagging-era_tagspy"></a>

## CICS era tagging (`era_tags.py`)

Mainframe dates in file headers lie; constructs in the code do not. [`era_tags.py`](era_tags.py)
determines a program's era from **25 syntactic tells** across six scopes (`asm`, `raw`, `code`, `bll`,
`cics`, and `cbl` option cards), checking both the program text and the copybooks its `COPY`
statements resolve:

| Era | Label | Tells (`TELLS` in `era_tags.py`) | Period-Bound vs. Floor |
|---|---|---|---|
| **0** | **CICS macro level** | `dfh-macro-call` (`DFHxx TYPE=`), `csa-tca-dsect` (`DFHCSADS` / `DFHTCADS`) | **Period-bound** (support dropped in CICS/ESA 3.2, 1991) |
| **1** | **Command level, OS/VS COBOL** | `bll-cells`, `bll-cell-list` (a FILLER-led fullword list a `SET()` names), `service-reload`, `handle-condition` (`HANDLE CONDITION/AID/ABEND`), `dli` (`CBLTDLI` / `EXEC DLI`), `langlvl-1` | **Period-bound** |
| **2** | **COBOL II / COBOL 85** | `address-of`, `set-address`, `resp` (`RESP`/`RESP2`), `exec-sql`, `dpl-link-sysid` (`LINK SYSID`), `cmpr2`, `langlvl-2` | `cmpr2` & `langlvl-2` period-bound; `resp`, `exec-sql`, `address-of` are floors |
| **3** | **LE / COBOL for OS/390** | `mq-call` (`MQOPEN`/`GET`/`PUT`/...), `exci` (`DFHXCIS`), `bridge-3270` (`DFHBR*`), `le-callable` (`CALL 'CEExxxx'`) | Floors |
| **4** | **Enterprise COBOL & Modern CICS TS** | `channel-container`, `web-soap` (`EXEC CICS WEB` / `SOAPFAULT` / `INVOKE SERVICE`), `json-xml` (`JSON`/`XML PARSE`/`GENERATE`), `async` (`RUN TRANSID` / `FETCH`), `named-counter` (`COUNTER`/`DCOUNTER`), `arith-extend` | Floors |

- **`era`**: the highest era reached by any tell in the program or its resolved copybooks.
- **`earliest`**: the oldest period-bound tell (`PERIOD_BOUND`).
- **`mixed`**: `True` when `earliest < era`—identifying layered legacy code (for example, an Era 1 `HANDLE CONDITION` program modified in Era 2 with `RESP` and `EXEC SQL`, or in Era 4 with `EXEC CICS WEB`).
- **`program_era` & `via_copybook`**: recorded whenever a copybook raises a program's era above what its own source text shows.
- **`copybook_skipped`**: the reason code on a tag whose copybook pass was refused or cut short (#5195); a tell in a copybook may be missing from that tag.

---

<a id="modules"></a>

## Modules

| Module | Role |
|---|---|
| [`assess.py`](assess.py) | CLI entry point (`gitgalaxy assess`), argument validation, read-only directory checks, and exit codes (`0` ok, `2` usage, `3` schema violation) |
| [`offline.py`](offline.py) | Process-wide socket guard and `guarded_scan` wrapper |
| [`inventory.py`](inventory.py) | Scans the estate, generates temporary BMS copybooks, runs the `det` parser and CICS census over every member, and collects per-program features and refusals |
| [`era_tags.py`](era_tags.py) | Tags programs and copybooks across `Era 0`–`Era 4` with IBM manual citations (`CITE`) |
| [`schema.py`](schema.py) | Closed-vocabulary projection, keyed-hash `--redact` anonymization, and pre-write schema validation |

---

<a id="limits"></a>

## Limits

- **Readiness is static inventory, not runtime proof.** `gitgalaxy assess` tells you which programs translate whole (`L1`) and which rules block the rest (`L0`); reaching `L2–L4` requires running the equivalence harness ([`cobol-to-java`](../cobol_to_java/README.md)) against test scenarios.
- **`--jcl` reads only what the JCL states:** `gitgalaxy assess --jcl` takes the compile `PARM`s from your JCL (#5710); where compile steps disagree it keeps only the options all of them agree on and names the rest on standard error. It cannot be combined with `--options FILE` (`estate_options.json`, #4704); see [`docs/assess.md`](../../../docs/assess.md).
- **Assembler is era-tagged, not translated, here:** `gitgalaxy assess` tags assembler members by era (`eras.assembler`) but does not run the HLASM lowering, so a command-level CICS assembler program inside the lowering's subset is not counted as translating whole. The det survey ([`tests/tools/det_survey.py`](../../../tests/tools/det_survey.py)) does lower it (#5859), so the two can differ on such a program.
- **Non-burned estates report counts only in committed fixtures:** To keep unburned estates blind for first-contact trials, [`tests/tools/era_distribution.py`](../../../tests/tools/era_distribution.py) commits only aggregate era and tell counts (`tests/fixtures/era_distribution/summary.json`), never per-program rows.

---

## Explore further

| Resource | What it contains |
|---|---|
| [CICS to Java (`cobol_to_java/README.md`)](../cobol_to_java/README.md) | Full translation and equivalence pipeline, era coverage table, and `L0–L5` / `E0–E4` scorecards |
| [Feature inventory & support matrix (`feature_inventory.md`)](../../../docs/language_status/feature_inventory.md) | How `inventory.py`, `era_tags.py`, `support_matrix.py`, and `readiness_report.py` fit together |
| [CICS command spec (`standards/cics/README.md`)](../../standards/cics/README.md) | The closed CICS command and option vocabulary imported by `schema.py` |
| [Estate intake checklist (`estate_intake.md`)](../../../docs/language_status/estate_intake.md) | The compiler, LE, Db2, and CICS option checklist (`--options`) |
