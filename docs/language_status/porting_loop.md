# The porting loop on CardDemo: what an unattended model proves, and what it taught us

The porting loop (#3753, `gitgalaxy.tools.cobol_to_java.port_runner`) gives a model one program's porting ticket.
The model writes the Java, and the equivalence harness (#3624) proves the Java against the original COBOL: every
output record, every CICS event or CALL result, and every injected fault (#4023 follow-up). A failed proof's findings
go back to the model for its next attempt. `tests/tools/porting_loop.py` drives it end to end on one case.

The measurements below are from Claude Sonnet 5.5, run headless (`claude -p`) with **no tools**, in an empty
directory. The model saw only the ticket's prompt, never this repository or its hand ports. CardDemo is
*development* data (its cases, tickets and generator were built against it), so these are not fresh-estate trial
numbers (`tests/tools/trial.py`). They measure the loop and our tooling.

## Results

| program | kind | proven on attempt | what the proof covers | time |
|---|---|---|---|---|
| CBACT04C (INTCALC) | batch, interest | **1** | 2 outputs, 19 fault runs | 5 min |
| CBTRN02C (POSTTRAN) | batch, posting | **1** | 4 outputs, 28 fault runs | 6 min |
| CBTRN03C (TRANREPT) | batch, report | **1** | 447 report lines, 24 fault runs | 6 min |
| COMEN01C (menu) | CICS | **1** | 11 scenarios (one with an injected PGMIDERR) | 4 min |
| CSUTLDTC | CALLed subprogram + LE service | **2** | 11 CALLs through CEEDAYS | 3 min |

Every committed port of a case that had none before (`tests/equivalence/<case>/port`) is the model's answer as the
loop stored it. Its `provenance.json` records the model, the attempt and the ticket hash.

**Re-run, 2026-10-01 (#4056).** When batch proofs began comparing DISPLAY / SYSOUT, the committed CBTRN03C port no
longer proved. It had logged its DISPLAYs, as the ticket then said to. A model's port is never hand-edited, so the
loop ran again from scratch on the new ticket. It was proven on attempt **2**: 447 report lines, 264 SYSOUT lines and
24 fault runs. Attempt 1 read the records as IBM037 instead of the data's ISO-8859-1. The ticket never states the
records' code page (#4060), and the SYSOUT feedback is what showed it.

## What each failure taught us, and what changed

Before the fixes, INTCALC and POSTTRAN each took 2 attempts, and the menu and CSUTLDTC did not prove at all. **No
first-attempt failure was the model misreading COBOL.** Each one was a gap in what we gave it, and each has its fix
in the same change:

1. **The ticket did not show the API the rules require.** The prompt lists the generated runtime a port may call,
   and it missed `CobolFiles` / `CobolAbend`. The file-status rule also read as if `read()` returned a status
   string. The model guessed the API, and the port did not compile. *Fix:* both classes are in the prompt, and the
   rule states each method's return type. INTCALC then proved on attempt 1.
2. **A KSDS WRITE is not `save()`.** POSTTRAN's only miss: a WRITE of an existing key must be status 22, but
   `repository.save()` silently overwrites. The model fixed it from the one failing fault run.
   *Fix:* `CobolFiles.writeKeyed` / `rewriteKeyed` (22 / 23) and a rule that says so. POSTTRAN then proved on
   attempt 1. The other POSTTRAN trap, JPA flushing a managed entity the COBOL never rewrote, the model avoided
   unprompted. The rule now spells it out anyway.
3. **The CICS harness never set the task's clock.** The rules tell a CICS port that the time is `task.now()`, but
   the equivalence test never called `withClock`, so a port that followed the rules hit a NullPointerException.
   The hand ports had used another clock, which hid it. *Fix:* the test sets the case's clock.
4. **The generated signature of a CALLed program could not be right.** `void handleCall(String, String, String)`
   has no way to hand back what COBOL returns through BY REFERENCE items, nor the RETURN-CODE. No port, by a
   person or a model, could be correct against it, and neither could its callers. *Fix:* the call forge gives a
   BY REFERENCE elementary item a `CobolRef<T>` and returns the RETURN-CODE (`int handleCall(...)`, and so
   `int call<Target>(...)`).
5. **The harness could not run it at all.** A CALLed subprogram has no datasets. The new case kind `call`
   (`tests/tools/equivalence_call.py`) drives it through its USING items and compares what comes back.
   `EXEC CICS INQUIRE PROGRAM` was not translated, so the menu was refused. It is now in the translator, the stub
   and `CicsTask.inquireProgram`, and can be injected like a file condition.
6. **Feedback has to name the failure.** Maven's tail is noise: stack frames, each compiler error twice, absolute
   paths. The proof now writes a `feedback` section: the first differing records field by field, each failing
   fault run with its plan and why, and compiler or test errors once each, with the port's own stack frames.
   Given that, every second attempt fixed exactly what failed.

## What the ports got right that nothing told them

- **CBTRN03C:** `NEXT SENTENCE` inside the report loop leaves the whole `PERFORM ... END-PERFORM.` sentence, so
  a transaction outside the date range ends the report without its grand totals. The last amount is also counted
  twice at end of file. Both are kept, and both are proven (the case's last record is out of range).
- **CSUTLDTC:** `MOVE WS-DATE-TO-TEST TO WS-DATE` copies the variable-length group *with its 2-byte binary length*,
  so every message's "TstDate" starts with bytes `00 0A`. The port reproduces it byte for byte.
- **COMEN01C:** options 0 and 12 are rejected and then still used as a subscript of the 11-entry table. That is
  storage beside the table in COBOL, and a Java `ArrayIndexOutOfBoundsException` if ported naively. The port
  handles it.

## Where an oracle ends

CSUTLDTC calls the Language Environment service CEEDAYS, which GnuCOBOL does not have. Its COBOL side runs against
`tests/equivalence/le/ceedays.c`, a model of IBM's documented behaviour. **A proof is only as good as that model**,
so it refuses what the documentation does not settle, and no call rests on a guess:

- Pictures other than `YYYY-MM-DD` (and its `/`, `.` forms) are refused, among them CardDemo's own `YYYYMMDD` in a
  10-byte field, where the trailing blanks' treatment is not modelled.
- A numeric month outside 1-12 is refused. The model's port answered CEE2EL (2517, month not recognized), the
  first CEEDAYS model CEE2EC (2508, date value not valid). IBM's documentation does not settle which, and the
  program itself tests for both. The call was removed rather than decided.

A run on real LE (z/OS) would settle both and let the model cover them.

## Also found

- #4037: a generated JPA entity used an SQL reserved word as a column name (`CURRENT-DATE` -> `current_date`), so
  its table is not created on H2.
- #4031: the engine's COBOL paragraph rule ignores paragraphs named `END-...` (found with #4026).

## Reproduce

```sh
JAVA_HOME=<a JDK 17> GITGALAXY_MAINFRAME_CORPORA=<the corpora cache> \
    python tests/tools/porting_loop.py run carddemo-trnrpt --work /tmp/loop-trnrpt --attempts 4
```

It writes `loop.md` / `loop.json` in the work directory, and port_runner's `port_log.jsonl` in the generated project.

### At scale

```sh
python tests/tools/porting_loop.py run-many carddemo-userlist carddemo-billpay ... --work-root /tmp/loops --jobs 6
python tests/tools/porting_loop.py adopt carddemo-userlist /tmp/loops/carddemo-userlist
```

- **run-many** runs the loops side by side, each in its own process and work directory. A loop mostly waits on the
  model (about 140 s per attempt for CardDemo's online programs), so concurrency is the main lever.
- **Each loop proves against a baseline.** While the model writes the first attempt, the loop proves the generated
  service itself (it fails: it is the stub). Every attempt then reuses that run's COBOL side and built project
  (`equivalence.py --reuse`): 13 s a proof instead of 45 for CardDemo's sign-on, regenerating nothing. A port that
  replaces other files than the generated service is proven in full.
- **adopt** copies a proven port into the case unchanged and writes `port/provenance.json` from the loop's own records
  (model, attempts, ticket hash, prompt tokens). It refuses a loop that did not prove.

Writing a case -- reading the program and choosing scenarios whose COMMAREA is the state the program itself leaves --
is now the slow part. It parallelises the same way: one agent per program drafts the case from the finished cases as
models and runs its COBOL side (`equivalence.py run <case> --cobol-only`); a person reviews it before it is committed.
