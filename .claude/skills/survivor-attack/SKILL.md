---
name: survivor-attack
description: Work surviving det-port mutants by attacking them first -- rank the likeliest wrong verdicts, let the port settle what its text can, get one mutant's packet, try inputs on the real COBOL oracle, keep what kills, and state a verdict only for what held. Use for any L5, mutation survivor or `det_mutation.py state` work, and before writing `equivalent` or `unreachable`.
---

A survivor means no test tells the mutant from the port. Start from "the tests are too weak", not "the mutant is harmless".
The job is to make the tests harder. A verdict is what is left when the attack fails.

**Why this exists.** A confident reason is cheap and an input is not, so reasons alone drift toward "harmless". Spot
checks have found stated verdicts that a new input killed. A confident reason is not evidence.

## The loop

Work in a directory outside the repo. Every proof goes through `tests/tools/box/heavy-run.sh`.

```bash
python tests/tools/survivor_attack.py next CASE --limit 20           # the likeliest wrong verdicts first
python tests/tools/survivor_attack.py facts CASE --work DIR          # what the port's text and the COBOL settle, no proof
python tests/tools/survivor_attack.py packet CASE ID --work DIR      # the Java, the COBOL's path, hints, the input format
python tests/tools/survivor_attack.py try CASE ID,ID --inputs I.json --work DIR
python tests/tools/det_mutation.py state CASE TRIAGE.json --attempts DIR/attempts.json
python tests/tools/survivor_attack.py lint [CASE ...]                # committed reasons `state` would refuse today
```

1. `facts`. It settles code no entry point of the program reaches, and constants nothing reads. With the `solver` extra
   it also settles an `unreachable` verdict whose reason says a paragraph is never reached when `branch_solver.py`
   finds no input that enters it, and prints the stated reasons it questions (an input does enter the paragraph).
   A questioned reason is read and attacked, never dropped on the solver's word. It also settles a mutant of a Field
   declaration (`fNN_X = Field.kind(s_REC, offset, length ...)`) when `branch_solver.py fields` finds no reachable
   statement that uses X (`solver-unread`: the accessor never runs). Believe `facts` only for that.
2. Take the rest in `next` order. Read the packet, then read the COBOL: the Java is one reading of it.
3. Write inputs that make the original and the mutant differ, aimed at the first place they diverge. Aim one input at
   several mutants when you can: `try` proves the port once.
4. Act on what `try` says:

| Result | What it means | Do this |
|---|---|---|
| `killed` | The input tells them apart | Add the input to `tests/equivalence/<case>/case.json` and keep it |
| `survived` | This input did not | Try the next idea: at least two different ones before giving up |
| `port-differs` | **The port is not equal to the COBOL** | Stop. This is a real finding: report it |
| `refused` | The oracle would not run it | No information. Read why, change the input |
| `stillborn` | The mutant does not compile | It is not a mutant. Move on |

5. Only then state a verdict, with the attempts file.

## The verdicts

| Verdict | Means | Counts as accounted |
|---|---|---|
| `equivalent` | No input of the program can make it show anything different | Yes |
| `unreachable` | No input **of the program** gets there | Yes |
| `case-gap` | An input the case lacks would kill it | **No: open** |
| `harness-gap` | Behaviour changes where the proof does not compare | **No: open** |

**An open gap is a good result.** It says exactly what the proof misses. Stating `case-gap` when you could not kill a
mutant in the time you had is honest. Stating `equivalent` to get the program to L5 is not. Never choose a verdict to
reach a level. If a program does not reach L5, report that.

## What does not make a reason

`det_mutation.py state` refuses the first of these (`survivor_attack.py lint` lists committed reasons it would refuse
today: re-attack those). The rest it cannot see, so they are on you.

- **What the tests do.** "Never called by the test runner", "the harness passes a DTO", "no scenario reaches it". Those
  are the definition of `case-gap` and `harness-gap`.
- **The caller you can see.** Programs are entered in more ways than this case shows. "Top-level, no link area" fails
  when another program XCTLs there with a COMMAREA.
- **A value you assume is fixed.** A text that looks impossible may be an install-time value, such as a URIMAP path.
- **"The next statement overwrites it", unread.** Check every path. A deleted EIBRESP store left the old NORMAL in place,
  and a later IF read it.
- **Reasons copied across many lines.** Each mutant gets its own reason. The same text on 100 survivors is 100 unchecked
  claims unless `facts` settled them.

## The usual kills

| Line looks like | Try |
|---|---|
| A response store (`EIBRESP`, `respond`) | Plan a `faults` entry, then find the later IF on the value |
| COMMAREA bytes (`linkArea`, `caBack`) | A `{"hex": ...}` field value; a longer or shorter area; entry from another program |
| A length or limit | Exactly the limit, one over, empty |
| A text scan (`tally`, `inspect`) | A value holding the searched text; install values are inputs too |
| A condition | The boundary value where the two branches split |

## After a kill

Add the input to the case, then re-run the ledger with `det_mutation.py run CASE --work DIR --sample 0`, because a changed
case re-judges its survivors. A stated verdict the new input kills makes `check` fail: remove that entry, the claim was wrong.

- Hand-pruning a `det_mutation_survivors` file stales the ledger: run `det_mutation.py refresh CASE --work <run dir>` after (#8043).
- `survivor_attack.py facts` re-settles only what main already states: check the ledger before counting it as yield (#8047).
- Check main first (`git fetch`, `git log HEAD..origin/main`) before redoing a slice a handoff calls "never pushed": #7955's redo duplicated #8007.
- A derived pattern like `s_{storage}` is vacuous when the captured storage name already starts with `s_`; detector test snippets need `public` methods, else a private uncalled method settles as `no-entry-path` first (#7955).

## Batch cases

A batch case is one job step, so `try` changes that step instead of adding scenarios. `packet` prints the input
datasets with their layouts and first records, the `@generate` fields, SYSIN / PARM, and a fault plan to copy. Each
input in INPUTS.json has a `name`, a `why`, and exactly one of:

| Key | What it changes |
|---|---|
| `"dataset": DD, "based_on": N, "set": {FIELD: value}` | Appends a copy of record N with those DISPLAY fields changed (a keyed file needs a new key) |
| `"generate": {DD: {"fields": {FIELD: {"values": [...]}}, "records": N}}` | Replaces those fields' generator specs on a `@generate` dataset (binary records, as PAUDBLOD's) |
| `"sysin": "..."` / `"parm": "..."` | Replaces SYSIN / PARM (one of each per `try`) |
| `"fault": {"plan": [{"dd": DD, "op": "READ", "nth": 1, "status": "NN"}]}` | Runs a fault run beside the main run |

All the inputs of one `try` go into the same run. A record that makes the step ABEND early hides everything after it:
aim at paths the run continues through, and use a `fault` for an error path. The kill is kept by copying the record,
SYSIN or fault from the trial case `try` prints into `tests/equivalence/<case>/case.json`.

## What `check` refuses in a PR

`det_mutation.py stale-check --vs origin/main` (a PR gate) refuses, for the survivor entries a PR writes:

- An `equivalent` / `unreachable` verdict with no attack on record.
- **One reason on many lines.** The same wording (numbers, quoted code and method names aside) on more than 10 Java
  lines of a case, unless each entry has an attack or a `facts` settlement in `tried`. `state --attempts` now records
  the attack for a `case-gap` too, so an honest "these inputs did not separate it" is kept.
- **"Unexercised" on code the proof runs.** A `case-gap` / `harness-gap` saying the code is not exercised or not reached
  when the ledger says the proof covers every paragraph. A survivor on code that runs means the proof does not compare
  some output, or no input separates the two: name which. A claim about one branch stands while branches are left
  uncovered, if it names the branch.

**An unstated survivor is already open.** You do not owe a reason for a survivor you did not attack. Leave it out of
the survivor file rather than writing a stock sentence for it.

## Report

Say how many mutants you attacked, how many died, which inputs you added, and what stayed open. Kills are the result.
A PR that only adds verdicts and no input needs a reason in its body why no attack worked. When a run changes a
program's L5 (a sample replaced by a full run, a verdict withdrawn), say so in the PR's first line.
