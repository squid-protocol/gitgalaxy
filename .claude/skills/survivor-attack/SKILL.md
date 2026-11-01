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
python tests/tools/survivor_attack.py facts CASE --work DIR          # what the port's text settles, no proof needed
python tests/tools/survivor_attack.py packet CASE ID --work DIR      # the Java, the COBOL's path, hints, the input format
python tests/tools/survivor_attack.py try CASE ID,ID --inputs I.json --work DIR
python tests/tools/det_mutation.py state CASE TRIAGE.json --attempts DIR/attempts.json
```

1. `facts`. It settles code no entry point of the program reaches, and constants nothing reads. Believe it only for that.
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

`det_mutation.py state` refuses the first of these. The rest it cannot see, so they are on you.

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

Batch cases are not handled by `try` yet: use `tests/tools/strengthen.py run CASE --work DIR --mutation MDIR`.

## Report

Say how many mutants you attacked, how many died, which inputs you added, and what stayed open. Kills are the result.
A PR that only adds verdicts and no input needs a reason in its body why no attack worked.
