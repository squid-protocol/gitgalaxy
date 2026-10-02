# COBOL to Java: the porting loop

GitGalaxy's COBOL-to-Java conversion generates the structure of the Java system: entities with
their record codecs, repositories, DTOs, the batch runtime, the job flow and a service per program,
for the target stack you configure (Java and Spring Boot versions, database, integration, UI). The
business logic of each program's PROCEDURE DIVISION is not guessed at. It becomes a **porting
ticket**, and the porting loop gets each ticket done with the model you choose and a person who
approves the result. The equivalence harness proves each port.

## Two ways to fill a ticket

| | combined method (default where the translator takes the program whole) | model-written port |
|---|---|---|
| who writes the behaviour | the deterministic translator ([det-port](language_status/det_port_design.md)): no model, the same port from the same source every time | your model, from the ticket |
| what the model does | rewrites one method at a time for a reader (`det_refine.py`); each rewrite is proven, else retried once with the proof's feedback, else reverted | writes the whole service; retried with the proof's feedback |
| first proof | before any model runs | after the model's attempt |
| a reviewer reads | a port proven at every step, each method's rewrite on record | a proven port |
| measured | 48 programs proven (2026-10-02): 27 of CardDemo, 8 of CBSA, 13 of GenApp, 17 cases of them on a real Db2. COACTUPC (4,236 lines, 66 GO TOs), which no model ported in one pass, has 109 of 109 methods refactored and proven ([benchmark](benchmarks/det-refine-coactupc/README.md)). COTRN02C is typed and refined, 19 of 19 methods ([benchmark](benchmarks/det-refine-cotrn02c/README.md)) | 23 CardDemo programs, the 17 crucible programs (below) |

**The combined method.** The translator settles what the program does, so the model's only freedom is how the code
reads. A rewrite that changes behaviour fails the proof and is undone, and the port is proven after every step.
Without a model, the port can still be made readable: structured style (named methods and fields) and typed state
(`String` / `long` / `BigDecimal` fields). Both are deterministic and proven the same way.

**A model-written port** stays the path for a program the translator leaves holes in: IMS (DL/I), MQ, pointer
arithmetic, ALTER, ENTRY, dynamic CALL, and the CICS commands the runtime does not model yet (the
[survey](language_status/det_survey.md) names each by line). Embedded SQL is no longer one of them: the translator
ports it and the harness proves it on IBM Db2 Community Edition ([Db2](language_status/det_port_design.md#db2-embedded-sql)).
Both paths use the steps below.

**What a proof rests on.** The oracle is GnuCOBOL with models of CICS and Language Environment, and a real Db2 for
Linux, not z/OS. Every known or suspected difference, and whether a proven program reaches it, is in the
[oracle-assumptions register](language_status/oracle_assumptions.md). After a change to the runtime, the harness or
an oracle model, `tests/tools/proof_sweep.py --work DIR` re-proves every det and model port.

For the combined method, the propose step is `port_runner run --backend det --source-root ESTATE [--typed]`, and
`port_runner refine` adds the model's pass over a proven port ([in port_runner](language_status/det_port_design.md#in-port_runner)).

## Why a loop and not a claim

Tools that say an LLM "converts" COBOL rarely show which programs were proven equivalent, or
who approved them. Here every step is on the record:

1. **Ticket** (`ai_agent_jobs/<KEY>_port_ticket.json` / `.md`, #3752). It carries the service to
   fill, the methods to port, the chosen stack, the numbered source and copybooks, the verified facts,
   the generated classes the port may use, the worklist items and the porting rules.
2. **Propose.** Your model, or a person, proposes a port:
   - `port_runner run --backend openai|anthropic|command` works with any OpenAI-compatible
     endpoint (a local vLLM or Ollama, Azure, a gateway), the Anthropic API, or any CLI.
   - `port_runner submit --by NAME` records a port a person wrote.

   Keys are read from an environment variable you name; they are never stored. The port is an
   overlay, so the generated sources stay untouched.
3. **Prove** (`port_runner prove`). The equivalence harness runs the original COBOL (GnuCOBOL,
   IBM dialect) and the port on the same inputs, then compares every output record field by field,
   along with the RETURN-CODE.
4. **Review** (`port_runner review --approve|--reject --by NAME`). A person decides. Nothing is
   accepted without one.
5. **Status** (`port_runner status`). It counts per ticket and per model what was proposed,
   proven, approved and rejected, from the append-only `ai_agent_jobs/ports/port_log.jsonl`.
   "Percent automated" is therefore evidence, not a marketing number.

You choose the model, the stack and the person who signs off.

## Measured: CardDemo batch, Gemini 3.1 Pro via the `command` backend

| program | round | result |
|---|---|---|
| CBACT04C (interest calculation) | 1 | ACCTFILE 50/50; TRANSACT failed: records written with newlines, system clock used |
| CBACT04C | 2 | did not run: its own overpunch decoder rejected `{` |
| CBACT04C | 3 | **proven**: ACCTFILE 50/50, TRANSACT 50/50, RETURN-CODE 0 = 0 |
| CBTRN02C (daily posting) | 1 | did not compile: guessed the dataset API |
| CBTRN02C | 3 | **proven**: ACCTFILE 50/50, TCATBALF 100/100, TRANFILE 262/262, DALYREJS 38/38, RETURN-CODE 4 = 4 |

Round 2 of CBTRN02C was a failure on our side: the harness never staged sequential input files.
Between rounds, each failure was traced to its cause and the fix went into the tickets, the
generator or the harness, not into a hand edit of the model's answer:

- fixed-length records with no line separators;
- the generated `MainframeClock`;
- the runtime sources in the prompt;
- numeric fields decoded only through `CobolRecords`.

Both ports named the original program's own defects in comments and preserved the behaviour, as
the rules ask. CBACT04C has an unreachable end-of-file branch; CBTRN02C's validation overwrites an
earlier failure reason. Both ports still await a person's review.

FILLER bytes are counted apart (`filler_differs`) rather than failed. No program can name a
FILLER, and after an `INITIALIZE` it holds whatever the runtime left in the record area. In the
CBTRN02C run, the 50 new TCATBALF records differ only there.

## CICS online programs (#3754)

An online program cannot run under GnuCOBOL as written, so the harness supplies what CICS would.

**The translator** (`tests/tools/equivalence_cics.py`) works per command, as IBM's does, never per
program:
- each `EXEC CICS` block becomes calls into a small stub runtime (`tests/equivalence/cics/ggcics.c`);
- `DFHRESP(...)` becomes its number;
- the EIB is a block the driver fills;
- `RETURN`, `XCTL` and `ABEND` end the task.

A command it does not model is refused by name, never skipped.

**The stub's file table comes from the engine's facts.** Each CICS file the program uses is traced
through the CSD `DEFINE FILE` to its DSNAME, then to the IDCAMS `DEFINE` that keys it. For CardDemo's
`CXACAIX`, that is a PATH, through its alternate index (`KEYS(11 25)`), over the card cross-reference
cluster.

**Each scenario is one task on both sides.** A scenario is a COMMAREA, the key pressed and the screen
input.
- On the COBOL side the program runs against the corpus's own data.
- On the Java side the generated service's `runTask(CicsTask)` runs with the same inputs.

The tasks' events are compared field by field: screen data fields, and every COMMAREA field through
the generated DTOs. Attribute bytes (colour, highlight) are not compared.

### Measured: CardDemo account view (COACTVWC, transaction CAVW)

| scenario | COBOL does | Java with the case's port |
|---|---|---|
| entry from the menu | sends the empty screen, RETURN CAVW | 2/2 events equal |
| view account 00000000001 | reads the xref (via the AIX), account and customer; sends them | 2/2 |
| account not on file | xref NOTFND (13); the error message | 2/2 |
| account not numeric | the validation message | 2/2 |
| PF3 | XCTL to COMEN01C with the COMMAREA | 1/1 |

That is 236 fields compared, 92 of them non-blank: balances in their edited PICTUREs, the SSN,
names, dates and messages, and the COMMAREA's ids and card number. The generated Java alone matches
0 of 9 events. The port is a hand translation, and it keeps two of CardDemo's own defects, each
commented:
- the check for "entered from the menu" reads the COMMAREA before it has been moved in;
- a missing account does not stop the customer read.

**Gemini 3.1 Pro on the same ticket did not produce a port.** Of three attempts, two returned
nothing and one returned a sketch that the harness proved 1 of 10 events equal. The ticket's prompt
is 268 KB: the program, its 15 copybooks and every generated class it touches. That is several
times the batch tickets Gemini ported. Fitting a large online program's ticket to a model's budget
is follow-up work; the harness shows where a port stands either way.

## Measured: CICS crucible, Claude via the `command` backend (#3989)

The [CICS crucible](language_status/cics_crucible.md) is 10 small adversarial CICS applications with
17 programs and 37 scenarios. Each scenario has an expected event log written by hand from IBM's
documentation. Every program's `runTask` was ported through this loop:

- **Model and backend.** Claude Opus 5.5 (`claude-opus-5-5`) through the `command` backend. The backend is
  Claude Code 2.1.285 in print mode, run from an empty directory with the prompt file on stdin:
  `claude -p --model claude-opus-5-5 --effort high --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --no-session-persistence --system-prompt "<answer the ticket as plain text>"`. The model has no tools,
  no MCP servers and no project context: it sees only the ticket.
- **Proof.** `port_runner prove --command "python tests/tools/cics_crucible.py --cases <case> --sides java-ported
  --ports <project>/ai_agent_jobs/ports --overlay {port_dir} --program <KEY> --report-dir {report_dir} ..."`.
  A program is proven when every scenario that runs it matches its expected log exactly. The case's other
  programs run with their latest ports, so the programs of one case are proven together.
- **Retries.** An attempt after a failed proof is `port_runner run --feedback`. It gets the proof's first
  divergence per failing scenario, the scenario's operator steps, the expected event at that point, what the
  port recorded, any compile errors, and the failed port itself.

Tickets were 47-93 KB: 11.8k-23.2k tokens counted as bytes / 4, and up to 30k with feedback. That is well
inside the #3863 budget. Every answer held one complete Java file. None came back empty.

| case | program | attempts to proof | what failed before the proof, and the fix (in gitgalaxy, never in the port) |
|---|---|---|---|
| ca-link-lengths | CALINK | 1 | first proof: harness. A callee's DTO names the caller's bytes differently, and a level-2 RETURN had no LINK LENGTH. Fixed in the harness; the same port was then proven |
| ca-link-lengths | CASUB | 1 | as CALINK |
| ca-xctl-versions | CAXA | 3 | 1: the sibling CAXB did not compile. 2: harness: a 10-byte block passed through an 80-byte DTO, and a `PIC X(32767)` COMMAREA with no DTO. Rule and harness now allow a String / byte[] area |
| ca-xctl-versions | CAXB | 2 | 1: imported `CobolEdit` from a package it invented. The generator emitted no CobolEdit / CobolRecords for a CICS estate without VSAM files, although the rules require them |
| gt-start-retrieve | GTSTART | 1 | |
| gt-start-retrieve | GTWORK | 1 | |
| gt-terminal-coalesce | GTSHOW | 2 | 1: `CicsTask` had no EIBTRMID. Now `task.termid()` |
| gt-terminal-coalesce | GTTERM | 2 | as GTSHOW |
| hc-abend-link | HCMAIN | 2 | 1: `CicsTask` did not model HANDLE ABEND's upward exit search across LINK levels. The two ports invented incompatible exception protocols, and an exception through a `@Transactional` service rolled the task back. Now `handleAbend` / `abend` / `abendOnCondition` / `abendExit`, plus a rule |
| hc-abend-link | HCSUB | 2 | as HCMAIN |
| hc-perform-range | HCQREAD | 1 | |
| hx-attr-bytes | HXATTR | 1 | first proof: harness. A DTO COMMAREA could not be compared with a text area. Fixed; the same port was then proven |
| hx-extended-cursor | HXEXT | 1 | |
| pc-aid-menu | PCDETL | 2 | 1: its own compile error, an ambiguous `sendMap(..., null)`. Fixed by the model from the feedback |
| pc-aid-menu | PCMENU | 2 | 1: the sibling PCDETL did not compile. Re-ported with it, never failed on its own |
| pc-wizard | PCCONF | 1 | |
| pc-wizard | PCWIZ | 1 | |

**All 17 programs are proven**, and the java-ported side passes all 37 cells:

- 9 at attempt 1. Three of those needed a harness fix before the unchanged port could be proven.
- 7 at attempt 2.
- 1 at attempt 3.

Every failure traced to something missing on our side, or to a sibling:

- the runtime: EIBTRMID, HANDLE ABEND across levels;
- the generator: the edit / numval helpers;
- the harness: comparing areas as bytes, the LINK LENGTH at RETURN, a COMMAREA with no DTO.

The only failure in a port's own code was PCDETL's ambiguous call, fixed from the feedback. The ports are
committed as the model returned them, with their provenance, under `tests/cics_crucible/ports/`. The
crucible runner's `java-ported` side re-proves them on every change.

None is approved. One thing for the reviewer: PCCONF formats its `ZZZ,ZZ9.99` amount by hand. Its ticket
predates the generator fix, so CobolEdit did not exist yet. The port is proven, but it breaks the CobolEdit
rule.
