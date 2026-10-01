---
name: porting-loop
description: Run and diagnose the automated COBOL->Java porting loop on equivalence cases -- a model ports a program from its porting ticket, the equivalence harness proves the port (every output, CICS event or CALL, and every injected fault run), and a failed proof's findings go back as the next attempt's feedback. Covers tests/tools/porting_loop.py, port_runner, building a case the loop can be measured on (batch / cics / call kinds, fault runs, coverage), reading a failure and deciding whose it is (model, ticket, generator, harness, case), committing a proven port with provenance, and the environment traps. Use when the user says "run the porting loop / port <program> automatically", "stress-test the loop", "why did attempt N fail", "add an equivalence case for <program>", or works on #3753 / the #4023 follow-ups. Not for fresh-estate trials that count (tests/tools/trial.py: first-try numbers are frozen at `trial start`), nor for hand-porting.
---

The loop: `port_runner run` → a model's proposed port → `port_runner prove` (`equivalence.py run <case> --port`) →
on failure, `run --feedback` with the proof's findings, and repeat. `tests/tools/porting_loop.py` drives it for one
case and writes `loop.md` / `loop.json` in its work directory. What happened so far, and every lesson behind the
rules below: `docs/language_status/porting_loop.md` (read it first).

## Run it

```sh
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 PATH=$JAVA_HOME/bin:$PATH        # the default JDK 21 has no javac
export GITGALAXY_MAINFRAME_CORPORA=/nvme-data/projects/gitgalaxy/.mainframe_corpora  # the pinned corpora cache
python tests/tools/porting_loop.py run carddemo-trnrpt --work <scratch>/loop-trnrpt --attempts 4 [--faults all]
```

- **Model.** The default backend is Claude Code headless (`claude -p --tools ''`, no MCP, no slash commands, run
  inside the attempt's own directory). The model sees only the ticket's prompt, never this repository or its hand
  ports. Check it with a probe prompt ("list the tools you can call") if you change the command. `--model` picks the
  model; `--backend-command` takes any other CLI (e.g. `agy` for Gemini: check its quota first).
- **Cost.** A loop takes 3-10 min; each proof regenerates the whole project (refract + generate + mvn). Run 2-3 loops
  in parallel at most. Each writes under its own `--work`.
- **Contamination.** CardDemo, CBSA and the crucible are **development data**: their numbers measure the loop and
  our tooling, not a model. They are public, so a model may have seen them. Never quote them as first-try rates. A
  fresh estate goes through `trial.py` (NO porting before `trial start`).
- **Never edit the generator mid-run.** Every proof regenerates the project with the *current* generator, so an
  edit to `gitgalaxy/tools/cobol_to_java/*` changes the experiment under a running loop. Wait, or use another
  worktree.

## Read a failure: whose is it?

`attempts/NNN_proof/report.json` → `feedback` is exactly what the next attempt sees. Decide the owner before
retrying:

| symptom | owner | example (fixed) |
|---|---|---|
| compile error on a generated API | **ticket / prompt**: the class isn't in the prompt, or a rule misstates it | `CobolFiles` missing from `_RUNTIME_HELPERS` |
| every attempt fails the same way in ~30 s | **harness** (the generated test, the case) | `StandardCharsets` import missing from the CALL test |
| NPE / wrong value inside runtime the rules mandate | **harness / runtime** | CICS test never called `withClock`, so `task.now()` was null |
| no correct port can exist | **generator** | `void handleCall(String…)` could not return BY REFERENCE results |
| one fault run differs | usually **model**, but ask whether a rule should say it | KSDS WRITE of an existing key must be 22 → `writeKeyed` + rule |
| COBOL side itself fails / refuses | **case / model of an IBM service** | CEEDAYS "picture not modelled" |

Fix ours in the ticket rules, the generator or the harness, then **re-run the loop from scratch**. Never hand-edit a
model's port to make it pass. A rule is added only for a real mainframe semantic (22 / 23, record copies, silent READ
errors), not to smuggle in a specific answer.

## Build a case the loop can be measured on

- **Kinds.** `batch` (datasets + DDs), `cics` (scenarios: COMMAREA, key, screen input), `call` (a CALLed
  subprogram: `using` items + `calls`; `tests/tools/equivalence_call.py`).
- **Faults are what make a proof mean something.**
  - Batch: `"faults": [{name, plan: [{dd, op, nth, status}], why}]` (file statuses via `ggfault.c` / `CobolFiles`).
  - CICS: a scenario's `"faults": [{cmd: READ|INQUIRE, file|program, resp}]`.
  - Cover every OPEN / CLOSE, each file's I/O errors, the "not found" paths, and the program's *silent* paths (a
    READ error nobody tests). Each `why` cites IBM's file status or RESP documentation.
- **Coverage tells you what the proof did not test.** `report.json` → `coverage` (#4023). Live code no run reached
  is where a port can be wrong and still "proven". Close it with case data or a fault, e.g. TRNRPT's last record
  sits out of the date range so `NEXT SENTENCE` is proven.
- **An IBM service GnuCOBOL lacks** (LE: `tests/equivalence/le/`) is modelled only where IBM documents it. It must
  *refuse* (exit 98, "not modelled") what the docs don't settle, and no call may rest on it. CEEDAYS refuses a month
  outside 1-12 (2508 or 2517?) and non-`YYYY-MM-DD` pictures.
- **Commit** `case.json` (the `.gitignore` admits `tests/equivalence/*/case.json`), the corpus's LICENSE / NOTICE,
  derived data with a note saying how it was derived, and the proven port **unedited** with
  `port/provenance.json` (model, attempt, ticket hash). Add an `EQUIVALENCE_E2E` test that proves it.

## Environment traps

- `pkill -f <pattern>` also matches the background shell whose command line holds the pattern. It killed a sibling
  loop once. Kill by PID from `pgrep -fa`.
- A reused `--keep` directory carries state (the crucible's TS queues). Use a fresh one per run.
- `gh pr edit` and `gh issue view` can fail on the Projects-classic GraphQL error. Use `gh api` (REST) instead.
- Merging is blocked by the auto-mode permission check even with approval in chat. Ask Joe to merge, or to add a
  permission rule.
- A stray `claude -p` run leaves an empty project dir under `~/.claude/projects/` named after its work dir. Safe to
  delete.

## After a run

1. Record per attempt: verdict, owner of the failure, and the fix PR.
2. Commit the proven port with provenance.
3. Update `docs/language_status/porting_loop.md`.

"Proven" is always "proven on these runs, covering X/Y paragraphs and A/B branches". A person still reviews the port
(`port_runner review`) and approves; never approve on Joe's behalf.

## How much does "proven" check? Mutation testing

`tests/tools/mutation.py run <case> --work DIR [--sample N] [--jobs 3]` breaks the proven port one small change at
a time and re-proves each mutant (fast mode: `--reuse` + `--first-difference`, validated 386/386 against
`--full`). Read `docs/language_status/mutation_testing.md` first. Triage every survivor:

- **case gap**: add data, a scenario or a fault (the COBOL decides the expected result);
- **harness gap**: the comparison doesn't look there (screen attributes #4053, SYSOUT #4056);
- **equivalent**: the change cannot alter behaviour; say why;
- **dead code** in the port.

Quote a mutation score with its case, sample and seed, never alone.
