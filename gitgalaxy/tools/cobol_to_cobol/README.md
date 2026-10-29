<div align="center">

# Mainframe Fact Extraction & Structural Slicing (`cobol_to_cobol`)

### Extract verified record layouts, CICS resource graphs, dead-code boundaries, and JCL topologies before touching a line of Java.

`cobol_to_cobol` is the fact-extraction and pre-migration stage of GitGalaxy's mainframe pipeline.
Before [`cobol-to-java`](../cobol_to_java/README.md) generates a Spring Boot project or translates
a program, the tools in this directory stage the estate (`cobol-refractor --scan`), join the
engine's structural graph (`GalaxyIR`) with copybook-expanded record layouts, map CICS transaction
and resource boundaries, identify unreachable paragraphs, and emit clean PostgreSQL schemas and
least-privilege JCLs. Where a fact cannot be verified from source, it is recorded as an explicit
gap—never guessed.

<table>
<tr>
<td align="center" width="190"><h2>7</h2></td>
<td align="center" width="190"><h2>0</h2></td>
<td align="center" width="190"><h2>12</h2></td>
<td align="center" width="190"><h2>live</h2></td>
</tr>
<tr>
<td align="center" valign="top"><sub><strong>mainframe fact channels</strong><br />calls, CICS, UOW, DB2/IMS/MQ, layouts, JCL, BMS<br /><em><a href="#the-fact-channels-and-galaxyir">fact channels</a> · cross-checked in CI</em></sub></td>
<td align="center" valign="top"><sub><strong>unexplained differential deltas</strong><br />on keyed corpora (<code>cbsa</code>, <code>zopeneditor</code>)<br /><em><a href="#accuracy-and-differential-verification">differential gate</a> · vs answer keys</em></sub></td>
<td align="center" valign="top"><sub><strong>CICS macro table families parsed</strong><br /><code>DFHSIT</code>, <code>PCT</code>, <code>PPT</code>, <code>FCT</code>, <code>DCT</code>, <code>TST</code> and six more<br /><em><a href="#cics-transaction-and-resource-extraction">resource reader</a> · + CSD</em></sub></td>
<td align="center" valign="top"><sub><strong>programs staged per burned estate</strong><br />counted on the <a href="https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md">progress page</a>, feeding <code>cobol-to-java</code> &amp; <code>det</code><br /><em><a href="../cobol_to_java/README.md">translator</a> · burned estates</em></sub></td>
</tr>
</table>

<a href="#quickstart"><strong>Quickstart</strong></a> ·
<a href="#pick-your-front-door"><strong>Front door</strong></a> ·
<a href="#what-you-ask-what-you-get"><strong>Ask / get</strong></a> ·
<a href="#the-fact-channels-and-galaxyir"><strong>Fact channels</strong></a> ·
<a href="#the-extractors-and-forges"><strong>Modules</strong></a> ·
<a href="#what-a-staging-run-produces"><strong>Outputs</strong></a> ·
<a href="#accuracy-and-differential-verification"><strong>Verification</strong></a> ·
<a href="#limits"><strong>Limits</strong></a>

</div>

---

<a id="quickstart"></a>

## Quickstart

```sh
# Run the full orchestrator and join with the GitGalaxy engine's GalaxyIR fact store
cobol-refractor /path/to/estate --scan

# Or run a read-only, offline readiness assessment first (zero source text in the report)
gitgalaxy assess /path/to/estate --out readiness.json

# Hand the staged clean-room directory to the Spring Boot / det-port generator
cobol-to-java <estate>_gitgalaxy_clean_<timestamp>
```

Everything runs locally with no compiler or mainframe emulator required. On large estates,
`cobol-refractor` switches its intermediate state store to disk-backed SQLite so memory usage stays
bounded.

---

<a id="pick-your-front-door"></a>

## Pick your front door

| If you want to... | Start here |
|---|---|
| **Stage an estate for `cobol-to-java`** with verified layouts, CICS maps, and JCL steps | [Quickstart ↑](#quickstart) and [What a staging run produces ↓](#what-a-staging-run-produces) |
| **Inspect the CICS transaction, CSD, and macro-table facts** extracted from an estate | [CICS transaction and resource extraction ↓](#cics-transaction-and-resource-extraction) |
| **Find unreachable paragraphs and unused working-storage items** | [`cobol_graveyard_finder.py` ↓](#the-extractors-and-forges) |
| **Generate PostgreSQL DDL schemas** from COBOL `PIC`, `REDEFINES`, and `COMP-3` layouts | [`cobol_schema_forge.py` ↓](#the-extractors-and-forges) |
| **Audit or generate JCL job streams** and topological step dependencies | [`cobol_dag_architect.py` and `cobol_jcl_forge.py` ↓](#the-extractors-and-forges) |
| **Check how these facts are verified** against hand-curated answer keys | [Accuracy and differential verification ↓](#accuracy-and-differential-verification) |

---

<a id="what-you-ask-what-you-get"></a>

## What you ask, what you get

| You ask | `cobol_to_cobol` gives you |
|---|---|
| *Which transactions run which programs, BMS maps, and VSAM files?* | [`cics_transaction_reader.py`](cics_transaction_reader.py) and [`engine_sourcing.py`](engine_sourcing.py) join CSD definitions, assembler macro tables (`DFHPCT`, `DFHPPT`, `DFHFCT`, `DFHDCT`, `DFHSIT`), `EXEC CICS` commands, and BMS `.bms` mapsets into one resource graph. |
| *How are copybooks, `REDEFINES`, and `OCCURS` resolved without a compiler?* | [`skeleton_export.py`](skeleton_export.py) and [`galaxy_ir.py`](galaxy_ir.py) expand copybooks (including `COPY ... REPLACING`), compute exact byte offsets and storage lengths, and export the verified skeleton consumed by [`cobol-to-java`](../cobol_to_java/README.md). |
| *Which paragraphs and variables are dead code?* | [`cobol_graveyard_finder.py`](cobol_graveyard_finder.py) builds the intra-program `PERFORM` / `GO TO` reachability graph after copybook expansion and reports unreachable paragraphs and unreferenced variables. |
| *In what order do batch jobs and programs depend on shared datasets?* | [`cobol_dag_architect.py`](cobol_dag_architect.py) traces JCL `DD` dataset bindings and COBOL `SELECT` / `FD` I/O modes (`INPUT`, `OUTPUT`, `I-O`, `EXTEND`) into a topological execution DAG. |
| *What constructs in a program require special runtime handling?* | [`cobol_system_limits_reporter.py`](cobol_system_limits_reporter.py) flags control-flow and pointer constructs (`ALTER`, `HANDLE CONDITION`, dynamic calls, table bounds) with comment-shielding so commented-out code is ignored. |
| *How do we unpack binary EBCDIC and `COMP-3` datasets for testing?* | [`cobol_etl_unpacker.py`](cobol_etl_unpacker.py) decodes zoned decimal, overpunched signs, and packed decimal (`COMP-3`) byte streams against the extracted record layout. |
| *What about PL/I programs in a mixed mainframe estate?* | [`pli_mapping.py`](pli_mapping.py) maps PL/I procedures, `DCL` structures, and CICS/SQL calls into the same `GalaxyIR` fact store. |

---

<a id="the-fact-channels-and-galaxyir"></a>

## The fact channels and `GalaxyIR`

When run with `--scan`, `cobol-refractor` populates [`galaxy_ir.py`](galaxy_ir.py) and exports a
verified skeleton ([`skeleton_export.py`](skeleton_export.py)) across seven mainframe fact channels
([`cics_mainframe_facts.md`](../../../docs/language_status/cics_mainframe_facts.md)):

1. **Program & call graph:** `PROGRAM-ID`, static and dynamic `CALL` targets, `USING` parameter modes (`BY REFERENCE`, `BY CONTENT`, `BY VALUE`), CICS `LINK` and `XCTL` edges, and `RETURN TRANSID` next-transaction routing.
2. **Record layouts & copybooks:** `01`–`49`, `66` (`RENAMES`), `77`, and `88` condition items; `PIC` clauses, `USAGE` (`BINARY`/`COMP`, `COMP-3`, `COMP-1`/`COMP-2`, `POINTER`), `REDEFINES`, `OCCURS [DEPENDING ON]`, `SIGN LEADING/TRAILING SEPARATE`, and `SYNCHRONIZED` slack bytes.
3. **CICS transactions & resources (`cics_transaction_reader.py`):** CSD (`DEFINE TRANSACTION`, `PROGRAM`, `FILE`, `MAPSET`, `TDQUEUE`, `TSMODEL`) and assembler macro tables (`DFHSIT`, `PCT`, `PPT`, `FCT`, `DCT`, `TST`, `SRT`, `JCT`, `TCT`, `MCT`, `PLT` and DB2's `DSNCRCT`, read by [`core/cics_macro_tables.py`](../../core/cics_macro_tables.py)), matched against each program's `EXEC CICS` operations.
4. **BMS screen maps:** `.bms` `DFHMSD` / `DFHMDI` / `DFHMDF` macros parsed into field coordinates, lengths, attributes (`ASKIP`, `UNPROT`, `NUM`, `BRT`, `DRK`, `IC`, `FSET`), extended colours, and generated symbolic map layouts (`I`/`O`/`L`/`F`/`A` subfields).
5. **Units of work & recovery:** `SYNCPOINT`, `SYNCPOINT ROLLBACK`, `HANDLE ABEND`, and transactional write sets across VSAM, Db2, TS/TD queues, and MQ.
6. **Data stores (VSAM, Db2, IMS DL/I, IBM MQ):** `SELECT ... ASSIGN` to JCL `DD` dataset bindings, `EXEC SQL` tables/cursors/host variables, `CALL 'CBLTDLI'` / `EXEC DLI` PCBs, and `MQOPEN`/`MQGET`/`MQPUT`/`MQCLOSE` queue operations.
7. **Completeness & provenance (`completeness_report.py`):** Every extracted fact carries its source file and line number; missing copybooks, unresolved dynamic calls, and unmapped options are itemized explicitly.

---

<a id="cics-transaction-and-resource-extraction"></a>

### CICS transaction and resource extraction

Mainframe estates declare their CICS topology in two places: modern CSD dumps (`DFHCSDUP` text) and
legacy assembler macro tables. [`cics_transaction_reader.py`](cics_transaction_reader.py) reads the CSD; the engine's
[`core/cics_macro_tables.py`](../../core/cics_macro_tables.py) reads the macro tables, and `GalaxyIR.job_macro_tables` joins a member's tables to its job step:

- **CSD definitions:** `DEFINE TRANSACTION`, `DEFINE PROGRAM`, `DEFINE FILE`, `DEFINE MAPSET`, `DEFINE TDQUEUE`, `DEFINE URIMAP`, `DEFINE WEBSERVICE`.
- **Assembler macro tables (`#5120`, `#5154`):**
  - `DFHSIT`: system initialization parameters (including `SUFFIX` and separate `SYSIN` member joins).
  - `DFHPCT` & `DFHPPT`: transaction-to-program and program processing table entries.
  - `DFHFCT`: file control table entries (dataset bindings, key lengths, service requests).
  - `DFHDCT`: destination control table entries (intrapartition and extrapartition transient data queues, including `TYPE=SDSCI` data sets).
  - `DFHTST`, `DFHSRT`, `DFHJCT`, `DFHTCT`, `DFHMCT`, `DFHPLT` and DB2's `DSNCRCT` (`#6918`): temporary storage, system recovery, journals, terminals, monitoring, program lists and the DB2 resource control table.
  - Every operand is read with its IBM manual citation; what the manuals do not define, and installed CEDA / CEMT state, is refused by name rather than guessed.

---

<a id="the-extractors-and-forges"></a>

## The extractors and forges

| Module | Role |
|---|---|
| [`galaxy_ir.py`](galaxy_ir.py), [`engine_sourcing.py`](engine_sourcing.py), [`skeleton_export.py`](skeleton_export.py) | Intermediate representation, engine-DB fact join, and verified skeleton export for `cobol-to-java` |
| [`cics_transaction_reader.py`](cics_transaction_reader.py) | Extracts CICS transactions, programs, files, queues, CSD definitions (the assembler macro tables come from `core/cics_macro_tables.py`) |
| [`completeness_report.py`](completeness_report.py) | Audits fact completeness across an estate and lists missing copybooks or unresolved targets |
| [`cobol_graveyard_finder.py`](cobol_graveyard_finder.py) | Expands local copybooks and computes unreachable paragraphs and unused variables |
| [`cobol_dag_architect.py`](cobol_dag_architect.py) | Builds the dataset and job execution DAG from JCL `DD`s and COBOL `SELECT` clauses |
| [`cobol_microservice_slicer.py`](cobol_microservice_slicer.py) | Traces multi-pass variable data-flow lineage to isolate sliceable business logic |
| [`cobol_schema_forge.py`](cobol_schema_forge.py) | Generates PostgreSQL DDL schemas from COBOL record layouts, `PIC` types, and `REDEFINES` |
| [`cobol_etl_unpacker.py`](cobol_etl_unpacker.py) | Unpacks binary EBCDIC and `COMP-3` packed-decimal files into CSV/JSON using verified record layouts |
| [`cobol_jcl_forge.py`](cobol_jcl_forge.py), [`cobol_jcl_auditor.py`](cobol_jcl_auditor.py) | Generates least-privilege JCL definitions from program I/O facts and audits existing JCLs for over-permissioned `DISP` bindings |
| [`cobol_compiler_forge.py`](cobol_compiler_forge.py), [`cobol_lexical_patcher.py`](cobol_lexical_patcher.py) | Detects COBOL-74 vs. COBOL-85 dialect tells, normalizes syntax traps (such as `NEXT SENTENCE`), and emits build JCL |
| [`cobol_system_limits_reporter.py`](cobol_system_limits_reporter.py) | Flags control-flow and runtime constructs (`ALTER`, `HANDLE CONDITION`, table bounds) |
| [`cobol_agent_task_forge.py`](cobol_agent_task_forge.py) | Packages isolated structural findings into scoped JSON task tickets |
| [`pli_mapping.py`](pli_mapping.py) | Maps PL/I source facts into the shared `GalaxyIR` model |

---

<a id="what-a-staging-run-produces"></a>

## What a staging run produces

Running `cobol-refractor <estate> --scan` writes a `<estate>_gitgalaxy_clean_<timestamp>` directory containing:

| Path | Contents |
|---|---|
| `skeleton.json` / `04_ir_state_dumps/` | The verified `GalaxyIR` skeleton consumed by `cobol-to-java` (programs, layouts, CICS commands, BMS maps, JCL steps, DB2 tables, macro tables) |
| `01_zero_trust_jcls/` | Generated least-privilege JCL job definitions scoped to the files each program actually reads or writes |
| `02_cloud_schemas/` | PostgreSQL `.sql` and `.json` schema definitions derived from `FD` and `WORKING-STORAGE` record layouts |
| `03_audit_reports/` | Dead-code reduction counts, JCL audit diffs, and system-limits reports |
| `05_microservice_slices/` | Isolated variable taint-tracking slices per target field |
| `06_ai_agent_jobs/` | Scoped JSON task manifests |

---

<a id="accuracy-and-differential-verification"></a>

## Accuracy and differential verification

Every extractor in this directory is tested against both synthetic edge-case fixtures and pinned real mainframe corpora ([`tests/cobol_mainframe/readme.md`](../../../tests/cobol_mainframe/readme.md)):

- **Hand-curated answer keys (`tests/cobol_mainframe/answer_key/`):** Independent ground-truth inventories for `zopeneditor-sample` and `cics-banking-sample-application-cbsa` (`July2024Refresh`).
- **Differential gate (`tests/tools/refraction_differential.py`):** Compares every field extracted by the `cobol_to_cobol` forges against the main GitGalaxy engine DB and adjudicates discrepancies against the answer keys. Both keyed corpora maintain **0 unexplained deltas** in CI (`test_refraction_differential.py`).
- **Fact cross-check gate (`test_fact_crosscheck.py`):** Verifies that the facts exported in `skeleton.json` match the `det` parser's view of every program across the burned estates (`fact_crosscheck_ledger.json`).
- **Snapshot regression (`test_refraction_snapshot.py`):** Diffs the full generated clean-room output on committed corpus excerpts (`tests/cobol_mainframe/refraction_excerpts/`) on every PR.
- **ReDoS linear-time sweep (`test_tool_regex_redos.py`):** Benchmarks every regular expression in `cobol_to_cobol` and `cobol_to_java` to ensure no pattern exhibits superlinear backtracking on malformed or adversarial COBOL lines.

---

<a id="limits"></a>

## Limits

- **Static extraction sees only what is in the corpus.** If a copybook, BMS mapset, CSD file, or JCL member is missing from the directory handed to `cobol-refractor`, the dependent layout or dataset binding cannot be resolved and is recorded as a missing input in the worklist.
- **Dynamic `CALL variable` targets** cannot be resolved statically unless the variable's literal values are visible in `WORKING-STORAGE` or `MOVE` statements; runtime dynamic call resolution is handled downstream by [`det/dyncall.py`](../cobol_to_java/det/dyncall.py).
- **Columns 73–80 sequence area:** Fixed-format COBOL files carry sequence numbers or change tags in columns 73–80; the extractors strip columns 1–6 and 73–80 on fixed-format files (see `#3244` for historical forge edge cases recorded in `refraction_differential_baseline.json`).
- **Extraction is not proof.** Extracting a clean schema or call graph does not prove that a translated Java program behaves identically to the COBOL; runtime equivalence proof is the job of [`cobol-to-java`](../cobol_to_java/README.md) and [`tests/tools/equivalence.py`](../../../tests/tools/equivalence.py).

---

## Explore further

| Resource | What it contains |
|---|---|
| [CICS to Java (`cobol_to_java/README.md`)](../cobol_to_java/README.md) | The downstream Spring Boot generator, `det` translator, CICS command spec, and equivalence proof harness |
| [Offline readiness scanner (`readiness/README.md`)](../readiness/README.md) | `gitgalaxy assess`, CICS era tagging (`era_tags.py`), and zero-leakage schema validation |
| [Mainframe fact channels (`cics_mainframe_facts.md`)](../../../docs/language_status/cics_mainframe_facts.md) | Verification tiers and completeness scores for each mainframe fact channel |
| [Mainframe test suite (`tests/cobol_mainframe/readme.md`)](../../../tests/cobol_mainframe/readme.md) | The 5,070-test verification suite covering extraction, translation, and equivalence |
| [Root GitGalaxy README](../../../README.md) | Overview of the polyglot scanner and the CICS-to-Java pipeline |