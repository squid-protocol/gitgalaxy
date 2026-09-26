# COBOL to Java: the porting loop

GitGalaxy's COBOL-to-Java conversion generates the structure of the Java system: entities with
their record codecs, repositories, DTOs, the batch runtime, the job flow and a service per program,
for the target stack you configure (Java and Spring Boot versions, database, integration, UI). The
business logic of each program's PROCEDURE DIVISION is not guessed at. It becomes a **porting
ticket**, and the porting loop gets each ticket done with the model you choose and a person who
approves the result. The equivalence harness proves each port.

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
