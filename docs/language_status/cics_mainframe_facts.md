# CICS / mainframe system facts — what GitGalaxy extracts, and how sure we are

Snapshot 2026-09-25, against `main` at the close of epics
[#3445](https://github.com/squid-protocol/gitgalaxy/issues/3445) (mainframe fact channels) and
[#3489](https://github.com/squid-protocol/gitgalaxy/issues/3489) (CICS estate gaps), refreshed after
the follow-ups [#3575](https://github.com/squid-protocol/gitgalaxy/issues/3575) to
[#3578](https://github.com/squid-protocol/gitgalaxy/issues/3578), which censused every field that
was still draft. Numbers are from
`tests/cobol_mainframe/ground_truth_ledger.json` and `tests/cobol_mainframe/test_completeness.py`.
Re-run the commands in §7 before quoting them if this page looks old.

The per-language docs (`cobol.md`, `pli.md`, `hlasm.md`, `jcl.md`, `db2_sql.md`, `java.md`) describe
the **structural signals**: counts such as "this file does I/O". This page describes the **facts**:
named relations such as "program A LINKs to B with COMMAREA X", "transaction T runs program P", and
"field F flows into column C". Together they make up the CICS "architectural skeleton". BMS and CSD
have no structural doc of their own, so their coverage is described here.

## 1. The honest summary

- **For a typical command-level CICS application, most of the skeleton is extracted and
  checked.** The checked facts are:
  - program-to-program transfers, including data-driven targets and remote (SYSID) calls;
  - COMMAREA and channel/container contracts;
  - file, queue, map, container, web and service operations;
  - transactions;
  - async tasks;
  - units of work and error handlers;
  - DB2, IMS and MQ access;
  - screens;
  - field-level data movement.
- **"Checked" means agreement with an answer key**, and the key is only as good as its corpus. There
  are six public sample corpora (§3). They are clean, mostly IBM or AWS demo code, and the engine was
  developed against the same corpora. A production estate will have dialect quirks none of them
  show. The last corpus added, navikt/DSF, needed several engine fixes of that kind. Expect the first
  real estate to do the same.
- **The reviewers are LLMs, not people.** "Cross-verified" means blind LLM reviewers, given only the
  source and a written contract, independently agreed with the key (§2). That is much stronger than
  "our tests pass". It is weaker than a mainframe engineer's sign-off, which no field has yet.
- **Where a value is decided only at runtime, it stays unresolved.** A program name read from a file
  or table is recorded as a named, unresolved gap, never guessed. A missing input, such as JCL, the
  CSD or BMS source, lowers the completeness score (§5). It does not produce wrong facts.

## 2. What the verification tiers mean

Every field in the ledger carries one tier per corpus. The ledger is a CI gate: every PR re-scans
the corpora, and a new mismatch fails the build.

| tier | what stands behind it |
|---|---|
| **cross_verified** (X) | The answer key was drafted by a **separately written reader**. It lives in `tests/tools/cobol_answer_key.py` and shares no code with the engine. Blind LLM reviewers then re-read **every** file in scope from the source and a written contract, and every disagreement was ruled on with a written reason. |
| **sample_verified** (S) | As above, but reviewers read a seeded, stratified **sample**, because the field has thousands of facts. The ledger records the sample size, the disagreements and a 95% upper bound on the key's error rate. |
| **draft** (d) | Only the two independent readers agree, the engine and the key's reader. No blind review has happened. Two readers written separately rarely share a mistake, but it can happen. Treat draft as unconfirmed. |

**Oracle instead of reviewers.** Where the corpus carries IBM's own generated output, that output is
the check. CardDemo's symbolic maps are compared unit for unit with the DFHMAPS copybooks checked
into its `cpy-bms` (`cobol_answer_key.py verify-symbolic`), and they are marked cross_verified on
that basis.

**The censuses find real errors.** Every census compares whole rows, not just the names the ledger
compares. In #3575 to #3578 they found:
- an engine defect: PL/I operands continued past a sequence field lost their names;
- a key defect: 1,229 record lines fell early, while the engine had them right;
- three ambiguities in the reviewer brief, each fixed and written down.

A sampled field's recorded error bound counts every key error the census found **before** the fix.
It bounds the key as it was drafted, not as it is now.

The engine agrees with the key on **every fact of every field on every corpus** (100% precision and
recall), with one deliberate exception. The engine's "dead" flag means *unreferenced by name*. That
is a different question from reachability, so it differs from the key's reachability answer by
design ([unreferenced_by_name_contract.md](../unreferenced_by_name_contract.md)). The modernization
forge, which answers reachability, matches the key 100%.

## 3. The six keyed corpora

| corpus | what it exercises |
|---|---|
| **aws-mainframe-modernization-carddemo** | COBOL CICS + batch, BMS, JCL, VSAM, DB2, IMS DL/I, MQ, CSD |
| **cics-banking-sample-application-cbsa** | COBOL CICS, channels/containers, async API, DB2, JCICS (Java) |
| **cics-genapp** | COBOL CICS, remote programs (SYSID / DPL), web-services assistant JCL, DB2 |
| **zopeneditor-sample** | small COBOL + PL/I batch sample |
| **zecs** | COBOL + HLASM CICS: a hand-written HTTP key/value service (EXEC CICS WEB) |
| **dsf** (navikt/DSF) | 1,473 PL/I CICS programs, 7 COBOL: a real Norwegian estate, fixed-format, national characters |

## 4. Coverage and verification by language

Counts are key facts. They read "X 107" for 107 cross-verified facts, with corpora in the
column order of §3.

### COBOL: the deepest coverage

| fact | CardDemo | CBSA | GENAPP | zOE | zECS | DSF |
|---|---|---|---|---|---|---|
| program units / PROGRAM-ID | X 870 / 44 | X 680 / 31 | X 157 / 31 | X 58 / 5 | X 216 / 5 | X 51 / 7 |
| call targets (CALL / LINK / XCTL) | X 37 | X 45 | X 51 | X 3 | X 3 | X 3 |
| data-driven call targets | X 89 | X 124 | X 13 | X 3 | X 3 | – |
| copybook resolution | X 253 | X 114 | X 35 | X 14 | X 6 | – |
| CICS resource operations (file / queue / map / container / channel / web) | X 107 | X 75 | X 94 | – | X 61 | – |
| CICS task control / async children | X 3 / – | X 24 / 5 | X 5 / 1 | – | X 7 / – | – |
| units of work, handlers, RESP checks | X 128 | X 245 | X 216 | X 8 | X 134 | – |
| DB2 table access | X 13 | X 24 | X 21 | – | – | – |
| IMS DL/I calls / segment access / PSB check | X 35 / 20 / 14 | – | – | – | – | – |
| MQ calls | X 22 | – | – | – | – | – |
| online→batch job submission | X 3 | – | – | – | – | – |
| FILE-CONTROL / CALL USING | X 54 / 71 | X 1 / 22 | – | X 12 / 5 | – / X 1 | X 22 / 4 |
| field-level data moves (MOVE / COMPUTE / …) | S 5,183 | S 5,182 | S 1,378 | S 323 | S 377 | S 140 |
| file I/O moves (READ INTO / WRITE FROM / ACCEPT) | X 146 | – | – | X 63 | – | X 38 |
| record layouts (each program's own DATA DIVISION items: line, level, PIC, USAGE, OCCURS, REDEFINES) | S 1,839 | S 1,851 | S 879 | S 163 | S 449 | S 294 |

**Not verified anywhere:** TD-queue trigger starts. The channel exists, but no keyed corpus defines
one, so it has never met real code.

**Not keyed at all: copybook record layouts.** The "record layouts" row covers the items written in
each program's own DATA DIVISION. `COPY` members are not expanded, and copybook files are not keyed.
The layouts modernization output depends on mostly live in copybooks, so they have no independent
check yet ([#3602](https://github.com/squid-protocol/gitgalaxy/issues/3602)).

### PL/I

- **Call sites**, meaning EXEC CICS transfers and external CALLs: S 8,012 (DSF) and S 2 (zOE).
- **Data moves:** S 1,560 (DSF) and S 97 (zOE).
- **Units of work:** ON / REVERT / SIGNAL plus the CICS commands, S 1,761 (DSF).
- **DECLARE structures:** d 113 (zOE).
- **CICS resource and task operations:** S 3,251 / 167 (DSF). The answer key reads PL/I too
  (#3577). A sampled census of 34 files and 363 facts found 0 disagreements. The same check found
  and fixed an engine defect: an operand continued past a sequence field lost its name.
- DSF is the only CICS PL/I corpus, one estate written in one house style. Treat PL/I CICS as
  sampled and single-sourced.

### HLASM (command-level `EXEC CICS` in assembler)

- zECS's assembler programs are covered inside zECS's counts for CICS resources, task control and
  units of work, all X. RESP checks written as `OC` / `CLC` count too.
- CardDemo's IMS PSB / DBD macros and `DFSRRC00` region steps: X 39.
- **Macro-level CICS** (`DFHPC`, `DFHFC`, … — the pre-command-level style) is **not supported**,
  and no work is planned.

### JCL

- **Job flow** (steps, COND / IF, PROC expansion, DISP, GDG): X on five corpora
  (558 / 410 / 253 / 138 / 261). DSF ships no JCL.
- **DD names and input / output datasets:** X.
- **VSAM `DEFINE CLUSTER`:** X on CardDemo, CBSA and GENAPP.
- **Web-services assistant steps** (DFHLS2WS / DFHWS2LS / …): X 18, on GENAPP only.
- **PROC / SET symbol resolution of DSNs:** X on zopeneditor-sample (every member), S on CardDemo,
  CBSA, GENAPP and zECS. zECS's JCL is all literal, so its sample is thin.
  **Override DDs** (`//PROCSTEP.DD DD`) are **out of scope** on both sides. An override carries the
  PROC step's effective dataset, and today it is not recorded.
- **Cross-job order** comes from the scheduler (CA-7, Control-M, TWS), not from source. The engine
  cannot see it and the completeness report asks for it.

### BMS (no structural doc)

- **Screen fields:** S on CardDemo (1,208) and CBSA (371), X on GENAPP (286, its one BMS source in
  full).
- **COBOL symbolic maps generated from BMS:** X on CardDemo, where all 21 mapsets (5,307 layout
  units) match IBM's own generated copybooks. They stay d on CBSA and GENAPP, which ship no generated
  copybooks to check against.

### CSD (no structural doc)

- **Resource definitions of every type:** X on CardDemo, CBSA, GENAPP and zECS (457 definitions,
  every deck in full).
- **The transaction → program map that joins the CSD to the code:** X on CardDemo, CBSA, GENAPP
  and zECS. It is derived by joining the censused TRANSACTION → PROGRAM rows to the cross-verified
  PROGRAM-IDs.
- **Remote definitions** (REMOTESYSTEM / REMOTENAME) are joined for SYSID / DPL topology. They are
  proven on GENAPP only (23 remote programs), and are not keyed.

### DB2 SQL (embedded)

- **Table access** (which program reads or writes which table): X on CardDemo, CBSA and GENAPP.
- **`DECLARE TABLE` / DCLGEN columns:** X on CardDemo and CBSA (55 columns, in full).

### Java (JCICS)

- `Program.link()` as call sites that join the COBOL call graph, plus file, queue and container
  operations: X 36, on CBSA only.

### Web / API

- **Provider and requester definitions:** X on GENAPP.
- **Program-side `EXEC CICS WEB`:** covered inside zECS's X 61.
- **`INVOKE SERVICE` and `TRANSFORM`** are extracted but **have never been seen in real code**. No
  public corpus uses them, so only unit tests cover them.

## 5. Estate completeness on the keyed corpora

`GalaxyIR.completeness()` runs on every mainframe scan. It appears as section 7 of the audit report
and as one line of the LLM brief. It scores how much of the skeleton resolved and names the missing
inputs. Here are the pinned values:

| corpus | score | what holds it back |
|---|---|---|
| cics-genapp | 99% | 6 of 101 program calls unresolved |
| carddemo | 90% | 17 of 82 program calls unresolved, 11 of 73 transaction checks fail, 6 of 17 batch programs have no JCL step |
| zopeneditor-sample | 89% | 47 of 374 data-flow operands unresolved; 2 PL/I mains (MACSAMP, PSAM1LIB) run by no JCL step |
| zecs | 88% | ECS001 and the assembler ZECSNC have no transaction in the repo's CSD; 1 of 3 program calls unresolved |
| cbsa | 80% | no JCL for its one batch program; 5 of 47 transaction checks and 8 of 150 program calls unresolved |
| dsf | 43% | ships **no BMS, no JCL and no CSD**: 2,421 map commands, 75 of 310 CICS programs and 128 batch mains cannot resolve |

The score is a coarse mean of channel ratios. Read the channels, not the number. DSF shows why: its
43% comes from missing inputs, not from the engine. With BMS, JCL and the CSD provided
([mainframe_ingestion_checklist.md](../mainframe_ingestion_checklist.md)), a complete estate should
score like GENAPP.

**Which programs the report scores (#3576).**
- **Transactions channel:** COBOL programs, PL/I main programs (a member with `PROC OPTIONS(MAIN)`,
  CICS when it or a member it `%INCLUDE`s issues CICS), and command-level assembler CICS programs.
- **Batch-entry channel:** COBOL and PL/I. A PL/I load module matches its JCL `EXEC PGM=` by member
  name. Assembler never counts as batch, because a CSECT is as often a link-edited subroutine.
- **Two scores went down when this landed:** zopeneditor and zECS. The engine didn't get worse; the
  report started counting programs it used to leave out.

## 6. What GitGalaxy cannot do, or has not proven

- **Macro-level CICS** (assembler or COBOL): not supported.
- **Runtime-only values:** a program, file or queue name read from data, or built from something
  other than a literal, `VALUE` or a `MOVE`d literal, is recorded as unresolved or ambiguous, with
  its candidates. It is never guessed. A name moved from another plain data-name is followed up to
  three MOVEs deep (#3578). A subscripted or qualified source is not followed.
- **Scheduler order, RACF / security definitions, SIT and region configuration, and load-module
  lists:** none of these are in source. The completeness report names them as inputs to request.
- **Proven on no real code:** `INVOKE SERVICE`, `TRANSFORM` and TD trigger starts.
- **Still draft:** symbolic maps on CBSA and GENAPP (no generated copybooks to check against), and
  PL/I DECLARE structures (zopeneditor-sample).
- **Not keyed at all:** copybook record layouts
  ([#3602](https://github.com/squid-protocol/gitgalaxy/issues/3602)).
- **Out of scope:** JCL override DDs.
- **Single-corpus fields:** IMS, MQ, online→batch submission, JCICS, web-service definitions and
  SYSID topology each rest on one corpus.
- **COBOL formats:** every measured corpus is fixed-format Enterprise COBOL. Free-format source and
  other vendors' extensions have not been measured.
- **Scale:** the largest keyed estate is DSF (1,480 files). Nothing has been measured at the size of
  a large production estate (tens of thousands of members).

## 7. Re-checking these numbers

```bash
python tests/tools/ground_truth_ledger.py check          # the scoreboard per corpus (engine / forge vs key, tiers)
python -m pytest tests/cobol_mainframe/test_completeness.py   # the pinned completeness per corpus
python tests/tools/cross_verify_sections.py coverage --corpus <name> --suite <suite>   # census coverage
```

Corpora are fetched with `python tests/tools/mainframe_corpus.py fetch`. The `mainframe-ground-truth`
skill describes how a field moves from draft to cross_verified.
