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
