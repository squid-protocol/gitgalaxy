<div align="center">

# CICS to Java

### Turn a CICS and batch COBOL estate into a compiling Spring Boot project, and prove every ported program against the original.

`cobol-to-java` reads a mainframe estate with no model, generates the Spring Boot skeleton from
facts the engine verified, translates each program's business logic into deterministic Java
(`det-port`) or hands a scoped ticket to a porter you choose, and proves each port byte for
byte against the original COBOL under GnuCOBOL. Anything the translator cannot handle becomes a
named `Hole` or an explicit refusal citing the IBM manual—never a guess. Every port ships with
its machine-checked evidence record, and a person approves every port.

[![CICS to Java: where we stand](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/generated/docs/language_status/progress.svg)](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md)

**Current numbers** (the evidence ladder, the CICS commands modelled, the mutation kill rate, the crucibles and the
era table) are generated from the repo's own artifacts, each with its source and the commit it was rendered from, on
the [progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md) (#5280). This README keeps prose only, so it cannot drift. Levels are evidence levels,
and the oracle is GnuCOBOL plus IBM documentation, not z/OS.

Targets: Java 17 and 21, Maven and Gradle, five databases
([target matrix](#choosing-the-java-you-get-the-target-config); compiling is not equivalence).

<a href="#quickstart"><strong>Quickstart</strong></a> ·
<a href="#pick-your-front-door"><strong>Front door</strong></a> ·
<a href="#what-you-ask-what-you-get"><strong>Ask / get</strong></a> ·
<a href="#the-pipeline"><strong>Pipeline</strong></a> ·
<a href="#coverage-across-cics-eras"><strong>CICS eras</strong></a> ·
<a href="#one-cics-command-spec-both-runtimes"><strong>CICS spec</strong></a> ·
<a href="#evidence-ladders-and-where-it-stands"><strong>Evidence</strong></a> ·
<a href="#where-the-journey-stands"><strong>Journey</strong></a> ·
<a href="#the-forges"><strong>Forges</strong></a> ·
<a href="#choosing-the-java-you-get-the-target-config"><strong>Target config</strong></a> ·
<a href="#limits"><strong>Limits</strong></a>

</div>

---

<a id="quickstart"></a>

## Quickstart

```sh
# 0. Assess an estate offline (read-only, zero customer source text in the report)
gitgalaxy assess /path/to/estate --out readiness.json

# 1. Extract verified facts and generate the clean-room staging directory
cobol-refractor /path/to/estate --scan

# 2. Generate the Spring Boot project, migration worklist, and porting tickets
cobol-to-java <staging-dir> [--config modernize.yaml]

# 3. Port a program (deterministic translator with no model, or a model/human backend)
python -m gitgalaxy.tools.cobol_to_java.port_runner run <project> \
    --ticket COBIL00C --backend det --source-root /path/to/estate --style structured --typed

# 4. Prove equivalence against GnuCOBOL + CICS/Db2/LE models (normal + injected faults)
python -m gitgalaxy.tools.cobol_to_java.port_runner prove <project> --ticket COBIL00C

# 5. A person reviews the evidence record and approves or rejects
python -m gitgalaxy.tools.cobol_to_java.port_runner review <project> --ticket COBIL00C
```

Everything runs locally and offline. `gitgalaxy assess` ([`gitgalaxy/tools/readiness/`](../readiness/README.md)) enforces an offline socket guard and emits a schema-validated readiness report with zero source text or identifier leakage.

---

<a id="pick-your-front-door"></a>

## Pick your front door

| If you want to... | Start here |
|---|---|
| **Check how ready an estate is** without exfiltrating source code | [Offline readiness assessment (`gitgalaxy assess`) ↓](#what-you-ask-what-you-get) and [Coverage across CICS eras ↓](#coverage-across-cics-eras) |
| **Translate COBOL and CICS deterministically** with no LLM in the loop | [The pipeline ↓](#the-pipeline) and [Deterministic translation (`det/`) ↓](#deterministic-translation-det-and-cobolrt) |
| **Refactor a proven port for readability** with a model, gated on proof | [Step 3: Port and refine ↓](#the-pipeline) and [`det_port_design.md`](../../../docs/language_status/det_port_design.md) |
| **See which CICS commands, BMS maps, Db2 SQL, and macro tables work** | [One CICS command spec, both runtimes ↓](#one-cics-command-spec-both-runtimes) |
| **Audit the proof and mutation numbers** on the public estates | [Evidence ladders and where it stands ↓](#evidence-ladders-and-where-it-stands) |
| **Customize the generated Spring Boot stack** (Java 17/21, Gradle/Maven, DBs) | [Choosing the Java you get ↓](#choosing-the-java-you-get-the-target-config) |
| **Understand what the oracle does *not* prove** | [Limits ↓](#limits) and the [oracle-assumptions register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md) |

---

<a id="what-you-ask-what-you-get"></a>

## What you ask, what you get

| You ask | `cobol-to-java` gives you |
|---|---|
| *How much of our estate will translate today, and what blocks the rest?* | `gitgalaxy assess` tags every program by its [CICS era](#coverage-across-cics-eras), counts whole translations vs. holes, and ranks the exact gap rules to land first ([`readiness/`](../readiness/README.md)). |
| *Can we share a blocker report without leaking proprietary names or literals?* | `gitgalaxy assess --redact` (and the blocker report tool, `#5054`) emits keyed-hash labels verified by a zero-leakage schema check. |
| *How do you translate business logic without an LLM hallucinating rules?* | [`det/`](det/) lowers each COBOL and `EXEC CICS` statement into calls against [`cobolrt`](det/cobolrt/), a pure Java 17 runtime that preserves byte storage, `REDEFINES`, zoned/COMP-3 signs, EBCDIC collation, and `PERFORM THRU` control flow ([design](../../../docs/language_status/det_port_design.md)). |
| *What happens when a program hits an unsupported CICS option or verb?* | The CICS spec ([`gitgalaxy/standards/cics/`](../../standards/cics/README.md)) refuses it by name with an IBM manual citation, or emits an explicit `throw new Hole(...)` counted in the report. Nothing is silently stubbed. |
| *How do you know the Java behaves like the COBOL?* | [`equivalence.py`](../../../tests/tools/equivalence.py) runs the COBOL under GnuCOBOL and the Java on the JVM across normal and fault-injected scenarios, comparing every output file, `DISPLAY`, BMS screen, `COMMAREA`, container, queue, and Db2 table row ([proofs](#the-pipeline)). |
| *What about CICS system macro tables (`DFHSIT`, `DFHPCT`, `DFHFCT`, ...)?* | Macro table parsers extract CSD and assembler macro definitions (`DFHSIT`, `DFHPCT`, `DFHPPT`, `DFHFCT`, `DFHDCT`) into structured resource metadata and refuse obsolete telecommunication macros (`DFHTCT TYPE=LINE/SDSCI`, `DFHMCT TYPE=RECORD`) with IBM citations (`#5120`, `#5154`). |
| *What if we want idiomatic Java instead of byte-array runtime calls?* | `--style structured --typed` promotes fields to native Java types where safe, and `port_runner refine` lets your model rewrite one method at a time—keeping the rewrite only if the full equivalence proof stays green. |

---

<a id="the-pipeline"></a>

## The pipeline

1. **Facts (`cobol-refractor --scan`).** Stages the estate and records what the engine verified per
   program: record layouts (copybooks, `REDEFINES`, `OCCURS`, `88`-level conditions), datasets and JCL
   steps, CICS commands and `COMMAREA`s, channels and containers, `CALL` / `LINK` / `XCTL` targets,
   DB2 tables, BMS maps, and CICS macro tables. The extraction tools live in
   [`../cobol_to_cobol/`](../cobol_to_cobol/README.md).
2. **Skeleton (`cobol-to-java`).** Builds the Spring Boot project from those facts, one forge per
   kind of fact ([The forges ↓](#the-forges)). Where a fact is missing, or two facts disagree, it
   writes an item in the migration worklist (`migration_worklist.md`). It never guesses. Each
   program with business logic gets a porting ticket (`ai_agent_jobs/<PROGRAM>_port_ticket.md`).
3. **Port (`port_runner run` / `refine` / `submit`).** Sends a ticket to a backend:
   - **The deterministic translator** (`--backend det --source-root ESTATE [--style structured] [--typed]`):
     no model; translates the statements of the burned estates into calls against
     `cobolrt`.
   - **Model-assisted readability refinement** (`port_runner refine`): rewrites a proven det port one
     method at a time, running the equivalence proof after each method and reverting any rewrite that
     changes behaviour (on CardDemo's `COACTUPC`, every method rewrite was kept only because the proof still passed).
   - **A person or a model the customer chooses** ([the porting loop](../../../docs/language_status/porting_loop.md)):
     checked by [`cobol_to_java_guardrail.py`](cobol_to_java_guardrail.py) against the generated
     project's inventory so it cannot invent endpoints, repositories, or unverified record fields,
     or compare a String field with `compareTo` / `equals` instead of `CobolCompare` (`collation`, #4035).
4. **Prove (`port_runner prove`).** Runs the equivalence harness
   ([`tests/tools/equivalence.py`](../../../tests/tools/equivalence.py)): the COBOL under GnuCOBOL
   and the port on the JVM, with identical inputs. What must match byte for byte, per case kind:
   - **Batch:** every output record, field by field; `RETURN-CODE` or abend; every `DISPLAY` line
     (`SYSOUT`, formatted as IBM COBOL writes it).
   - **CICS:** every task event in order—each `SEND MAP` (text, attribute bytes, extended colour,
     highlight, cursor position, and options), `SEND TEXT`, `RECEIVE MAP`, `CONVERSE`, TS/TD queue
     writes, channel/container contents (including CCSID conversions), named counters, `POST`/`WAIT`,
     `RETURN` or `XCTL` with its `COMMAREA` or channel, and abend codes.
   - **CALL / LINK:** every `USING` item after each `CALL`, `RETURN-CODE`, `LINK`ed `COMMAREA` or
     channel mutations, and multi-program tasks ported and proven together.
   - **Db2:** every compared table, row by row, after each run and after `SYNCPOINT` / `SYNCPOINT ROLLBACK`
     or abend backout, with both sides running SQL against a real IBM Db2 Community Edition container
     ([`tests/tools/equivalence_db2.py`](../../../tests/tools/equivalence_db2.py)).
   - **Fault plans:** file statuses and CICS conditions (`NOTFND`, `DUPKEY`, `INVREQ`, `LENGERR`,
     `ENDFILE`, `ENQBUSY`, `PGMIDERR`, ...) injected on both sides at the same statement.
5. **Review (`port_runner review`).** A person inspects the evidence record and approves or rejects
   each port. No tool marks a port approved.

---

<a id="deterministic-translation-det-and-cobolrt"></a>

## Deterministic translation (`det/` and `cobolrt`)

The deterministic translator ([`gitgalaxy/tools/cobol_to_java/det/`](det/)) compiles COBOL + CICS +
embedded SQL into a Spring service without calling an LLM ([full design and runtime contract](../../../docs/language_status/det_port_design.md)):

| Module | Role |
|---|---|
| [`det/program.py`](det/program.py), [`det/gen.py`](det/gen.py) | Parses program structure, computes `WORKING-STORAGE` / `LINKAGE` / `FD` / BMS map initial byte images (`Storage.image`), drops unused `Field` views, and emits the Java class |
| [`det/layout.py`](det/layout.py), [`det/expr.py`](det/expr.py), [`det/stmt.py`](det/stmt.py) | Exact byte offsets, `REDEFINES` overlays, `OCCURS DEPENDING ON`, `88`-level condition methods, arithmetic, `MOVE`, `STRING`/`UNSTRING`/`INSPECT`, and `PERFORM THRU` dispatch |
| [`det/cics.py`](det/cics.py), [`det/cvda.py`](det/cvda.py) | Lowers `EXEC CICS` commands, `HANDLE CONDITION / AID / ABEND` tables, `RESP`/`RESP2`, BMS map marshalling, channels/containers, files, queues, counters, web/document APIs, and `SYNCPOINT` |
| [`det/bll.py`](det/bll.py), [`det/osvs.py`](det/osvs.py) | OS/VS COBOL `BLL` cell pointer aliasing, chained BLL cells, `SET cell TO NULL` on `MOVE ZERO / LOW-VALUES`, and `LANGLVL(1)` / `CMPR2` rules |
| [`det/sql.py`](det/sql.py), [`det/dyncall.py`](det/dyncall.py), [`det/hfp.py`](det/hfp.py) | Embedded `EXEC SQL` (`SELECT`, cursors, host variables, `SQLCODE`), dynamic `CALL` resolution, and hexadecimal floating-point (`HFP`) rules |
| [`det/dli.py`](det/dli.py), [`det/mq.py`](det/mq.py) | IMS DL/I: batch `CALL 'CBLTDLI'` under `ENTRY 'DLITCBL'` and, under CICS, `EXEC DLI` (`#4893`); IBM MQ: `MQOPEN`/`MQGET`/`MQPUT`/`MQPUT1`/`MQCLOSE` from a CICS program (`#4892`). Each runs on a modelled runtime with a COBOL-side twin; anything else is a named hole |
| [`det/dfsort.py`](det/dfsort.py) | DFSORT step cards (`SORT FIELDS`, `OUTREC FIELDS`/`BUILD`) lowered to a COBOL `SORT` program and proven like any other (`#4268`) |
| [`det/hlasm.py`](det/hlasm.py) | Command-level CICS assembler (`DFHEIENT`) lowered to a COBOL program inside a named subset, then translated like COBOL; outside the subset the program is refused whole, by name ([design](../../../docs/language_status/hlasm_cics_design.md), `#5859`) |
| [`det/refine.py`](det/refine.py) | Method-by-method LLM readability refactoring gated on the equivalence proof |
| [`det/cobolrt/`](det/cobolrt/) | Plain Java 17 runtime (`Storage`, `Field`, `Cobol`, `DetCics`, `CicsSpec`, `CobolSql`, `PerformDispatcher`) with zero Spring dependency |

---

<a id="coverage-across-cics-eras"></a>

## Coverage across CICS eras

Real mainframe estates are layered across five decades of IBM compilers and CICS releases. The
readiness scanner ([`gitgalaxy/tools/readiness/era_tags.py`](../readiness/era_tags.py)) tags every
program and copybook by the concrete constructs ("tells") it uses—never by file dates—and detects
**mixed-era** programs (such as a 1980s `HANDLE CONDITION` / `BLL` program with a 2010s `PUT CONTAINER`
call bolted on).

| Era | IBM Stack & Period | Source Tells Detected (`era_tags.py`) | Burned-estate status | What Works Today vs. Named Refusals |
|---|---|---|---|---|
| **Era 0** | **CICS Macro Level** *(Pre-CICS/ESA 3.2)* | `DFHxx TYPE=` macro calls (`dfh-macro-call`), `DFHCSADS` / `DFHTCADS` (`csa-tca-dsect`) | **Application code refused by design** (`#5121`); **macro tables parsed** (`#5120`, `#5154`) | Macro-level application code is refused up front. Command-level assembler (`DFHEIENT`) translates through the HLASM lowering when it stays inside its subset (`#5859`, the zECS programs); other assembler is refused by name. System macro tables (`DFHSIT`, `DFHPCT`, `DFHPPT`, `DFHFCT`, `DFHDCT`) are extracted; obsolete `DFHTCT LINE/SDSCI` & `DFHMCT RECORD` are refused with IBM cites. |
| **Era 1** | **Command Level + OS/VS COBOL** | `BLL` cells (`bll-cells`), `SERVICE RELOAD`, `HANDLE CONDITION / AID / ABEND`, `CALL 'CBLTDLI'` / `EXEC DLI`, `LANGLVL(1)` | HANDLE + BLL programs and the IMS DL/I programs (`#4893`); level counts on the progress page | `HANDLE CONDITION/AID/ABEND`, `PUSH/POP HANDLE`, and chained `BLL` cells (`#5119`) are proven at L3/L4. IMS DL/I (`CBLTDLI`, `EXEC DLI`, `ENTRY 'DLITCBL'`) is actively landing (`#4893`, `#5233`). |
| **Era 2** | **COBOL II / COBOL 85 + CICS/MVS & Db2** | `RESP` / `RESP2`, `EXEC SQL`, `ADDRESS OF`, `SET ADDRESS`, `LINK SYSID` (DPL), `CMPR2`, `LANGLVL(2)` | Level counts on the progress page (Eras table) | Full VSAM file control (including `UPDATE TOKEN` and `RESP2`), BMS 3270 maps, `LINK`/`XCTL`/`RETURN`, TS/TD queues (`SET/INQUIRE TDQUEUE`), `GETMAIN`/`FREEMAIN` + `SET ADDRESS OF`, `ENQ`/`DEQ`, `START`/`RETRIEVE`, `POST`/`WAIT`, and live Db2 `EXEC SQL`. |
| **Era 3** | **LE / COBOL for OS/390 + IBM MQ** | `CALL 'CEExxxx'` (`le-callable`), `CALL 'MQOPEN/GET/PUT...'` (`mq-call`), `EXCI` (`DFHXCIS`), 3270 Bridge (`DFHBR*`) | LE-callable programs and the MQ programs (`#4892`); level counts on the progress page | LE date/time and abend services (`CEEDAYS`, `CEELOCT`, `CEE3ABD`) are proven; custom condition handlers (`CEEHDLR`/`CEEHDLU`) are refused, and so are the services a handler calls (`CEEMGET`, `CEESGL`, `CEENCOD`, `CEEMRCE`, `CEE3SRP`); the handler program's `SET ADDRESS OF ... TO token` is the `pointers` refusal (#5042) and its `SET RESUME TO TRUE` translates. MQI queue calls + CICS UOW backout are landing in `#4892`. |
| **Era 4** | **Enterprise COBOL + Modern CICS TS** | `PUT/GET CONTAINER` & `CHANNEL`, `EXEC CICS WEB` / `SOAPFAULT`, `RUN TRANSID` / `FETCH` (`async`), `COUNTER` / `DCOUNTER`, `JSON/XML PARSE`, `ARITH(EXTEND)` | Level counts on the progress page (Eras table) | Channels & containers (including `FROMCCSID` / `INTOCCSID` / `CONVERTST` code-page conversion, `#4270`), async `RUN TRANSID`/`FETCH CHILD`, named counters (`COUNTER`/`DCOUNTER` + `REWIND`/`WRAP`), `WEB` HTTP & `DOCUMENT CREATE/RETRIEVE` are proven. `SOAPFAULT CREATE` and `ARITH(EXTEND)` float exponentiation are open gap rules. |

---

<a id="one-cics-command-spec-both-runtimes"></a>

## One CICS command spec, both runtimes

Every `EXEC CICS` command is governed by a single declarative specification in
[`gitgalaxy/standards/cics/`](../../standards/cics/README.md) ([design](../../../docs/language_status/cics_command_spec.md),
[live status](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md)).
From that one source of truth, the build generates both the Java runtime tables
([`CicsSpec.java`](CicsSpec.java)) and the C header for the GnuCOBOL CICS stub
(`tests/equivalence/cics/ggcics_spec.h`), so the Java port and the COBOL oracle cannot drift on
`DFHRESP` codes, `EIBFN` bytes, abend codes, or refused options.

The spec tracks every CICS command by name (counts: the progress page):
- **Full commands** modelled in both the deterministic translator and the CICS stub runtime:
  - **File control (VSAM):** `READ`, `WRITE`, `REWRITE`, `DELETE`, `UNLOCK`, `STARTBR`, `READNEXT`, `READPREV`, `ENDBR`, `RESETBR` (including `GENERIC`, `KEYLENGTH`, `UPDATE TOKEN`, `RBA`/`RRN`, and exact `NOTFND` / `DUPKEY` / `INVREQ` / `LENGERR` `RESP2` semantics).
  - **Terminal & BMS 3270:** `SEND MAP`, `RECEIVE MAP`, `SEND TEXT`, `SEND CONTROL`, `SEND`, `RECEIVE`, `CONVERSE`, `ISSUE ERASEAUP`.
  - **Program, task & storage control:** `LINK`, `XCTL`, `RETURN`, `LOAD`, `RELEASE`, `ABEND`, `SYNCPOINT`, `SYNCPOINT ROLLBACK`, `GETMAIN`, `FREEMAIN`, `ASSIGN`, `ADDRESS`, `ADDRESS SET`, `ENQ`, `DEQ`, `ENTER TRACENUM`, `SUSPEND`.
  - **Channels & containers:** `PUT CONTAINER`, `GET CONTAINER`, `MOVE CONTAINER`, `DELETE CONTAINER`, `STARTBROWSE CONTAINER`, `GETNEXT CONTAINER`, `ENDBROWSE CONTAINER`, `DELETE CHANNEL`, `QUERY CHANNEL` (with `BIT`/`CHAR` mode and `FROMCCSID`/`INTOCCSID`/`CONVERTST` code-page conversion).
  - **Interval control, events & async:** `ASKTIME`, `FORMATTIME`, `DELAY`, `POST`, `WAIT EVENT`, `START`, `RETRIEVE`, `CANCEL`, `RUN TRANSID`, `FETCH CHILD`, `FETCH ANY`, `FREE CHILD`.
  - **Queues & named counters:** `WRITEQ TS`, `READQ TS`, `DELETEQ TS`, `WRITEQ TD`, `READQ TD`, `DELETEQ TD`, `INQUIRE TDQUEUE`, `SET TDQUEUE`, `DEFINE COUNTER`/`DCOUNTER`, `GET COUNTER`/`DCOUNTER`, `QUERY COUNTER`/`DCOUNTER`, `UPDATE COUNTER`/`DCOUNTER`, `REWIND COUNTER`/`DCOUNTER`, `DELETE COUNTER`/`DCOUNTER`.
  - **Web, HTTP & documents:** `DOCUMENT CREATE`, `DOCUMENT INSERT`, `DOCUMENT SET`, `DOCUMENT RETRIEVE`, `WEB OPEN`, `WEB CONVERSE`, `WEB SEND`, `WEB RECEIVE`, `WEB CLOSE`, `WEB PARSE URL`, `WEB EXTRACT`, `WEB READ HTTPHEADER`, `WEB WRITE HTTPHEADER`, `WEB STARTBROWSE/READNEXT/ENDBROWSE HTTPHEADER`, `EXTRACT WEB`, `EXTRACT TCPIP`.
  - **System & resource inquiry:** `INQUIRE FILE`, `SET FILE`, `INQUIRE PROGRAM`, `INQUIRE TRANSACTION`, `INQUIRE SYSTEM`, `INQUIRE APPKEY`, `CHANGE PASSWORD`, `VERIFY PASSWORD`, `SIGNON`, `SIGNOFF`, `BIF DEEDIT`.
- **Engine-only commands** recognized for structural extraction.
- **Name-only commands** explicitly refused by name with a diagnostic rather than silently ignored.

---

<a id="evidence-ladders-and-where-it-stands"></a>

## Evidence ladders and where it stands

GitGalaxy tracks two complementary evidence ladders ([`definition_of_done.md`](../../../docs/language_status/definition_of_done.md)):

1. **The `L0-L5` Det-Translator Ladder** ([`evidence_report.py`](../../../tests/tools/evidence_report.py), published on the [`generated` branch](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/evidence_report/README.md)): measures the **deterministic translator (`det`)** across every program of the burned estates.
2. **The `E0-E4` Evidence-Record Ladder** ([`estate_evidence.py`](../../../tests/tools/estate_evidence.py), [per-program records](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/evidence/README.md)): rolls up the committed `evidence.json` records.

<a id="measuring-the-proof-coverage-and-mutation"></a>

The counts at each level, per estate and in total, the mutation kill rate ([`mutation_testing.md`](../../../docs/language_status/mutation_testing.md)),
the crucibles and the era table are generated, not written here: see the [progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md). Each number there names the
artifact it was read from and the commit it was rendered at.

---

<a id="where-the-journey-stands"></a>

## Where the journey stands (snapshot, 2026-10-29)

This is a map of a typical CICS estate against what GitGalaxy covers, so the evidence numbers above can be read in
proportion. It is a written judgment, dated; the measured counts stay on the
[progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md).

Being useful on a CICS estate takes three jobs, and they are at very different points:

1. **Scan**: inventory every member and map how they connect. Broad, shallow per item. Mostly in place for the
   common mainframe languages.
2. **Prove**: show what each program does, by evidence level. Narrow and deep. The method works and is trusted on
   the burned estates, which are small public samples the translator was built against (development results,
   not a blind trial; see [Limits](#limits)).
3. **Run the system around the programs**: the batch, file, messaging and database runtimes programs depend on (the
   Open World epics [#4890](https://github.com/squid-protocol/gitgalaxy/issues/4890)-[#4894](https://github.com/squid-protocol/gitgalaxy/issues/4894)).
   Started in places; most of the remaining work is here.

| Part of the estate | Scan | Prove / translate |
|---|---|---|
| COBOL online programs (CICS) | In place | The deepest work: most burned-estate programs are on the L1-L4 ladder |
| COBOL batch programs | In place | Translated and proven per program; the batch world around them is partial (rows below) |
| BMS screens | In place, screen fields included | Proven (screen text, attributes, cursor) |
| Embedded Db2 SQL | In place | Proven against Db2 Community Edition, not Db2 for z/OS |
| Copybooks | In place | In place; IBM's own copybooks are written stand-ins, never shipped |
| JCL and PROCs | In place | Step flow, return codes, DD binding and restart are open ([#4891](https://github.com/squid-protocol/gitgalaxy/issues/4891)) |
| Sort and utilities (DFSORT, IDCAMS, IEBGENER, GDGs) | Partial | DFSORT step cards and COBOL `SORT` translate and are proven; the other utilities are open ([#4890](https://github.com/squid-protocol/gitgalaxy/issues/4890), [#4268](https://github.com/squid-protocol/gitgalaxy/issues/4268)) |
| VSAM | In place | KSDS file control (keyed I/O, browses, `RESP2`; spec above); ESDS, RRDS and alternate indexes are open ([#4894](https://github.com/squid-protocol/gitgalaxy/issues/4894)) |
| IMS DL/I | Signals, PSB/DBD extraction | Batch DL/I calls and `EXEC DLI` translate on a modelled runtime; IMS TM / MFS are open ([#4893](https://github.com/squid-protocol/gitgalaxy/issues/4893)) |
| IBM MQ | Signals | The core MQI calls from CICS programs translate; batch MQ and the rest of the MQI are open ([#4892](https://github.com/squid-protocol/gitgalaxy/issues/4892)) |
| Assembler (HLASM) | Basics: structure, `EXEC CICS`, COPY, risk signals; only `=V(name)` calls become call-graph edges, and no large real-file probe has run ([status](../../../docs/language_status/hlasm.md)) | Command-level CICS assembler inside a narrow subset (the zECS programs); arithmetic, packed decimal and most addressing forms are refused |
| CICS resource definitions (CSD) | Profile in place | Not used by the proofs yet |
| PL/I, REXX, Easytrieve | Profiles in place | Not translated |
| Language Environment services, EBCDIC, hex float | n/a | Modelled where IBM documents them; where IBM is silent, an owner-stated assumption in the [register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md), else refused |
| Scheduler definitions, RACF, CICS exits and system tables, SMP/E | System macro tables parsed; the rest not covered | Not covered ([#4514](https://github.com/squid-protocol/gitgalaxy/issues/4514)) |

**What comes next, in order of impact.** Finish the L1-L4 ladder on the burned estates, which completes the proof
of the method. Then the batch runtimes, JCL execution and the utilities first, since most production work runs in
batch. The last stretch, calibration against real z/OS behaviour and the rare constructs a production estate holds,
needs a real estate ([#4050](https://github.com/squid-protocol/gitgalaxy/issues/4050),
[fresh-estate trials](../../../docs/language_status/fresh_estate_trials.md)); public samples cannot supply it.

---

<a id="the-forges"></a>

## The forges

| Module | Generates from the verified facts |
|---|---|
| [`cobol_to_java_spring_forge.py`](cobol_to_java_spring_forge.py) | JPA entities and DTOs from record layouts |
| [`cobol_to_java_repository_forge.py`](cobol_to_java_repository_forge.py) | Spring Data repositories for VSAM files |
| [`cobol_to_java_db2_forge.py`](cobol_to_java_db2_forge.py) | JDBC repositories for embedded DB2 |
| [`cobol_to_java_batch_forge.py`](cobol_to_java_batch_forge.py) | Spring Batch jobs from JCL, and the batch runtime: `CobolFiles` (`FILE STATUS` per I/O statement), `CobolAbend`, `Sysout` (`DISPLAY`) |
| [`cobol_to_java_transaction_forge.py`](cobol_to_java_transaction_forge.py) | REST endpoints for CICS transactions, and `CicsTask`: a task's commands as calls |
| [`cobol_to_java_screen_forge.py`](cobol_to_java_screen_forge.py) | BMS maps as view models and web views |
| [`cobol_to_java_call_forge.py`](cobol_to_java_call_forge.py) | `CALL` / `LINK` / `XCTL` as service-to-service calls (`CobolRef` for `BY REFERENCE`) |
| [`cobol_to_java_messaging_forge.py`](cobol_to_java_messaging_forge.py) | TS / TD queues and IBM MQ as messaging ports |
| [`cobol_to_java_uow_forge.py`](cobol_to_java_uow_forge.py) | Units of work as `@Transactional`, handlers as exception mapping |
| [`cobol_to_java_compare_forge.py`](cobol_to_java_compare_forge.py) | `CobolCompare`: alphanumeric comparison in the program's collating sequence |
| [`cobol_to_java_decoder_forge.py`](cobol_to_java_decoder_forge.py) | The EBCDIC, zoned and `COMP-3` decoder utility (record fields themselves go through the generated `CobolRecords`) |
| [`cobol_to_java_service_forge.py`](cobol_to_java_service_forge.py), [`cobol_to_java_api_contract_forge.py`](cobol_to_java_api_contract_forge.py) | Service classes (the port's home) and API contracts |
| [`cobol_to_java_build_forge.py`](cobol_to_java_build_forge.py), [`cobol_to_java_test_forge.py`](cobol_to_java_test_forge.py) | The Maven / Gradle build and the generated tests |
| [`cobol_to_java_skeleton_forges.py`](cobol_to_java_skeleton_forges.py), [`cobol_to_java_common.py`](cobol_to_java_common.py) | The skeleton-driven forges as one pipeline, and their shared pieces |
| [`cobol_to_java_worklist.py`](cobol_to_java_worklist.py) | The migration worklist: every fact the generators refused to guess |
| [`cobol_to_java_port_tickets.py`](cobol_to_java_port_tickets.py) | The porting tickets and their rules |
| [`port_runner.py`](port_runner.py), [`cobol_to_java_guardrail.py`](cobol_to_java_guardrail.py), [`proof_reach.py`](proof_reach.py) | The porting loop's runner (`run` / `submit` / `prove` / `review` / `status`), the inventory guardrail, and proof reachability verification |
| [`java_target.py`](java_target.py) | The target config (below) |

The generated skeleton alone is not a port. On the
[CICS crucible](../../../docs/language_status/cics_crucible.md) it compiles for all cases, but
its unported skeleton services pass no scenario. The ported ones pass them all.

---

<a id="choosing-the-java-you-get-the-target-config"></a>

## Choosing the Java you get: the target config

`cobol-to-java` writes Java 17 / Spring Boot 3.2.4 / Maven / PostgreSQL / Lombok by default. A
YAML (or JSON) config picks something else. GitGalaxy reads it with its own YAML reader, so
PyYAML is not needed:

```sh
cobol-to-java --init-config modernize.yaml          # an annotated file with every option and its default
cobol-to-java <staging dir> --config modernize.yaml
```

| Section | Options |
|---|---|
| `project` | `package`, `group_id`, `artifact_id`, `version`, `description`, `header_file` |
| `java` | `version` (`17`, `21`), `build_tool` (`maven`, `gradle`), `data_classes` (`lombok`, `plain`), `dto_style` (`class`, `record`) |
| `spring_boot` | `version` (any `3.x.y`) |
| `database` | `engine` (`postgresql`, `db2`, `oracle`, `mysql`, `h2`), `ddl_auto`, `username`, `show_sql` (no password: set `SPRING_DATASOURCE_PASSWORD` at runtime) |
| `features` | `rest_controllers`, `services`, `batch`, `ebcdic_decoder`, `mock_services`, `agent_tickets` |

Every key is validated. An unknown key or an unsupported value stops the run with an error naming
it. Explicit `--pkg` / `--header` flags override the file. Without `--config` the output is
unchanged. Every supported combination is compile-checked by
[`tests/tools/java_target_matrix.py`](../../../tests/tools/java_target_matrix.py), which generates
CardDemo under every supported config and runs the real Maven / Gradle build.

---

<a id="limits"></a>

## Limits

- **The oracle is GnuCOBOL, not IBM z/OS.** Every equivalence proof compares the Java port with the
  COBOL program compiled by `cobc (GnuCOBOL) 3.1.2.0` plus our CICS stub (`tests/equivalence/cics/ggcics.c`),
  IBM Language Environment services modelled only where IBM documents them (`tests/equivalence/le/`),
  and Db2 Community Edition for Linux standing in for Db2 for z/OS. Anything IBM leaves undocumented
  is refused, not guessed. Every known or suspected difference from z/OS, and whether a proven
  program reaches it, is recorded in the
  [oracle-assumptions register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md)
  (for example `C9`: a `POINTER` is 8 bytes on 64-bit Linux vs. 4 bytes on 31-bit z/OS; `D1`: text
  compares in ASCII order unless routed through `CobolCompare`). Proving against captured z/OS
  mainframe traces is [#4050](https://github.com/squid-protocol/gitgalaxy/issues/4050).
- **These are burned estates.** The burned estates and the CICS crucible are public, and the
  translator and runtime were built against them, so their scores are development results, not
  blind-estate results. The protocol for a blind first-contact trial is in
  [`fresh_estate_trials.md`](../../../docs/language_status/fresh_estate_trials.md).
- **"Proven" covers the paths the scenarios execute, not all possible inputs.** Read every equivalence
  claim alongside its paragraph coverage (`L3`), net branch coverage (`L4`), and mutation score.
  Direct mutation testing of `det`-generated ports (`L5`) is tracked in
  [#4628](https://github.com/squid-protocol/gitgalaxy/issues/4628).
- **Callee holes cap the caller at `L1` / `E1`.** If a program `LINK`s or `CALL`s a target that still
  has a hole (or lacks an executed-equivalent record), the caller cannot reach `L2` / `E2` until the
  callee is closed ([#4803](https://github.com/squid-protocol/gitgalaxy/issues/4803)).
- **Translating the code is not migrating the system.** Data migration and reconciliation, JCL job
  scheduling, external partner interfaces, batch window performance, RACF/CICS security rules, and
  cutover orchestration are not measured ([#4514](https://github.com/squid-protocol/gitgalaxy/issues/4514)).
- **A person approves every port.**

---

## Explore further

| Resource | What it contains |
|---|---|
| [Evidence reports (`generated` branch)](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/evidence_report/README.md) | Live `L0–L5` per-program scorecards across all the burned estates, refreshed on every push to `main` |
| [Per-program evidence records (`generated` branch)](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/evidence/README.md) | Individual proof, coverage, and mutation certificates (`E0–E4`) |
| [Definition of done](../../../docs/language_status/definition_of_done.md) | The charter defining `L0–L5`, `E0–E4`, agreed refusals, and estate completion |
| [Deterministic port design (`det_port_design.md`)](../../../docs/language_status/det_port_design.md) | Architecture of `det/`, `cobolrt`, `--style structured`, `--typed`, and `det_refine` |
| [CICS command spec (`cics_command_spec.md`)](../../../docs/language_status/cics_command_spec.md) · [Live spec status](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md) | How the 257 CICS commands are specified once and compiled into both Java and C runtimes |
| [Oracle assumptions register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md) | Every `MATCHED`, `ASSUMED`, `DIFFERS`, and `REFUSED` rule between our oracle and IBM z/OS |
| [CICS crucible](../../../docs/language_status/cics_crucible.md) · [Mutation testing](../../../docs/language_status/mutation_testing.md) · [Porting loop](../../../docs/language_status/porting_loop.md) | The CICS trap corpus, mutation testing methodology, and the feedback loop for model/human ports |
| [Offline readiness scanner (`gitgalaxy/tools/readiness`)](../readiness/README.md) | `gitgalaxy assess`, CICS era tagging (`era_tags.py`), and zero-leakage schema validation |
| [Mainframe structural extraction (`cobol_to_cobol`)](../cobol_to_cobol/README.md) | `cobol-refractor`, dead-code reaper, DAG architect, EBCDIC unpacker, and JCL/DDL forges |
| [Mainframe test suite (`tests/cobol_mainframe`)](../../../tests/cobol_mainframe/readme.md) | How the extraction, compilation matrix, equivalence, and ratchets are tested in CI |
