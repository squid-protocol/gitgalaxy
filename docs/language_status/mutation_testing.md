# Mutation testing of the proven ports (#4047)

A proof says a port and its COBOL program agree on the case's runs. It proves only what those runs look at.
Mutation testing measures that: `tests/tools/mutation.py` breaks a proven port one small change at a time and
proves each broken port ("mutant") with the same harness. A mutant the proof still calls proven **survived**.
It is either an equivalent mutant (the change means nothing) or a place the case never looks: a port could be
wrong there and still be "proven". Part of epic #4055 (the product is the proof).

```sh
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 PATH=$JAVA_HOME/bin:$PATH
export GITGALAXY_MAINFRAME_CORPORA=/nvme-data/projects/gitgalaxy/.mainframe_corpora
python tests/tools/mutation.py list carddemo-trnrpt                       # the mutants, by operator
python tests/tools/mutation.py run carddemo-trnrpt --work DIR --sample 150 --jobs 3
python tests/tools/mutation.py run carddemo-trnrpt --work REF --sample 10 --seed 1 --full   # the slow reference
python tests/tools/mutation.py compare REF DIR                            # do the verdicts agree?
```

## Operators

| op | change |
|---|---|
| ROR | `<` `<=` `>` `>=` `==` `!=` swapped for a neighbour |
| COR | `&&` for `\|\|` and back |
| NEG | a whole `if` / `while` condition negated |
| AOR | `+ - * / %` swapped; `++` / `--`, `+=` / `-=` |
| BDM | BigDecimal `add` / `subtract` / `multiply` / `negate`, the rounding mode |
| CON | an integer constant: 0 -> 1, n -> n + 1 (hex stays hex) |
| LIT | a string or char literal's first character |
| RET | `return true` / `return false` |
| DEL | an expression statement, `break` or `continue` deleted |

Never mutated: comments, imports, annotations, logging calls. A mutant `javac` refuses against the baseline's
classpath is **stillborn**: the compiler caught it, not the proof, so it counts for nothing.

## Fast mode, and why it can be trusted

A from-scratch proof per mutant redoes the COBOL runs and regenerates the whole estate (TRNRPT: ~150 s idle,
~280 s under load), although only the port changed. The default fast mode:

- `equivalence.py run --reuse BASELINE`. Each COBOL step whose `run.sh` is byte-identical to the baseline's
  takes the baseline's outputs; a differing step refuses. The generated project is the baseline's, re-overlaid
  with the port (the same files, or it refuses), and only the port's files are compiled, with the pom's javac
  options (`-g -parameters --release 17`).
- `--first-difference`: a batch proof stops at the first run that differs. The verdict is the same; the report
  names only that run.
- When the build is current (the main classes from the port, the test classes from this very test source), the
  test runs in a plain JVM through the JUnit Platform launcher surefire itself uses. Otherwise it goes to Maven.
  Each run is still a fresh JVM: no state crosses runs.

**Validation (2026-09-30).** `mutation.py compare` of fast mode against `--full` on the same mutants. **386 of
386 agree, 0 differ** (355 proofs plus 31 stillborn):

| case | kind | mutants judged by both | agree | proof time, full -> fast |
|---|---|---|---|---|
| carddemo-dateutil (CSUTLDTC) | call | 206 | 206 | 9,984 s -> 2,606 s |
| carddemo-menu (COMEN01C) | cics | 150 | 150 | 9,194 s -> 3,640 s |
| carddemo-trnrpt (CBTRN03C) | batch, 24 faults | 10 | 10 | 3,496 s -> 1,712 s |
| carddemo-posttran (CBTRN02C) | batch, 28 faults | 10 | 10 | 2,670 s -> 609 s |
| carddemo-intcalc (CBACT04C) | batch, 19 faults | 10 | 10 | 1,323 s -> 427 s |

The times are summed over mutants, on a machine at load 17-21 (the fast runs were under heavier load). A mutant
the normal run kills costs ~10-15 s instead of ~280 s. A survivor must still pass every run (TRNRPT: 25 JVMs,
~190 s); running all of a proof's runs in one JVM is the next step, only if it still agrees with `--full`.

## Scores

After #4056 (SYSOUT compared) and #4053 (SEND MAP attributes compared), on 2026-10-01:

| case | mutants run | caught | score |
|---|---|---|---|
| CSUTLDTC (call; all 217 mutants) | 206 (16 stillborn) | 131/190 | 69% |
| COMEN01C (CICS; 150 of 407, seed 0) | 150 (15 stillborn) | 77/135 | 57% |
| CBACT04C (batch; 40, seed 1) | 40 (5 stillborn) | 30/35 | 86% |
| CBTRN02C (batch; 40, seed 1) | 40 (8 stillborn) | 25/32 | 78% |
| CBTRN03C (batch; 40, seed 1) | 40 (3 stillborn) | 26/37 | 70% |

These scores are raw: equivalent mutants are not removed. NEG (a whole condition negated) is caught
almost always, so the main logic is pinned. Before the two fixes, a 10-mutant batch sample scored
38-75%, and the menu caught 75 of the same 135. The menu mutants that #4053 kills now are the
deleted `errmsgColor = DFHRED` and a changed message literal. The job-log mutants #4056 kills now
are a changed `ERROR OPENING ...` literal and a deleted `displayIoStatus`.

What still survives:

1. **Paths the case never runs.** CSUTLDTC's proof covers 4 of 10 COBOL branches (#4023); its
   survivors sit in the CEEDAYS error-feedback branches. COMEN01C has menu options and user types
   that no scenario picks. In the batch cases, boundaries go untested: an expiry date equal to the
   transaction date, and a non-numeric file status. The fix is case data, generated by the
   test-strengthening loop (#4049), with the COBOL deciding the expected result.
2. **Equivalent mutants.** For example, `setScale(2, HALF_UP)` instead of `DOWN` on a value
   already at scale 2, or an initial value overwritten before use. Triage marks them, with the
   reason.
3. **Defensive code** the COBOL has no counterpart for, such as a check that a file exists before
   it is opened.

The two harness gaps found earlier are closed: screen attributes (#4053) and DISPLAY / SYSOUT
(#4056).

A score is quoted with its case and seed, never alone. Every survivor is triaged as a case gap, a
harness gap, an equivalent mutant (with the reason) or dead code.

## The test-strengthening loop (#4049)

`tests/tools/strengthen.py run <case> --work DIR --mutation MDIR` gives a model the case's uncovered COBOL
branches, with the source around each one, and the surviving mutants as hints. It asks for new **inputs only**:
CALL arguments, or CICS scenarios. Each proposal is proven on its own. The COBOL decides the expected result, an IBM
service model may refuse it, and the port is equal on it or not. The useful proposals go into
`DIR/candidate_case.json` for a person to review. The surviving mutants are then judged again, against the case
plus the new inputs the port is equal on. Batch cases are not supported yet.

First runs (2026-10-01, claude-sonnet-5-5, 2 rounds each):

- **CSUTLDTC: 4/10 branches, unchanged.** The model concluded, correctly, that the 6 missing `EVALUATE` outcomes
  cannot be reached. Five need CEEDAYS behaviour IBM does not document: eras, other pictures, month 13. Our model
  refuses those, and it refused the proposals that tried. "Insufficient data" cannot happen either: the program
  always passes 10-byte strings. The loop also found three blank-padded dates where the model-written port answers
  2507 (insufficient data) and our CEEDAYS model 2520 (non-numeric). Either the port or the model is wrong, and only
  a z/OS run settles it (#4050). Those inputs are not in the committed case.
- **COMEN01C: 28/33 branches, unchanged.** The model concluded that the 5 gaps cannot be reached through CardDemo's
  fixed menu table, and this was verified in `COMEN02Y`: all 11 options have user type `U`, none is a `DUMMY`
  program, and the option count is a constant 11.

So on these two cases the survivors in the uncovered branches sit in code that no input reaches, given the
program's own data or the oracle's limits. The raw mutation scores understate the proofs there. The batch cases'
survivors are boundaries that input records can reach, which is the loop's next kind.
