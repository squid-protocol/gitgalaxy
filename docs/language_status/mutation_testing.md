---
description: "A proof says a port and its COBOL program agree on the case's runs. It proves only what those runs look at."
---
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

### Every survivor triaged (2026-10-03)

The table below is generated from the committed results file, `docs/language_status/mutation_scores.json`
(per port: the commit the mutants ran on, the seed, per-operator killed / survived / stillborn counts, and every
survivor with its verdict and reason). Re-render it with `python tests/tools/mutation_scores.py table`; rebuild
it from run directories with `mutation_scores.py build --runs DIR... --triage T.json... --commit SHA` (an earlier
results file is accepted as a triage input, so a re-run keeps the verdicts of mutants it judged before).

- **Equivalence cases** run with `mutation.py` (fast mode). **Crucible ports** run with
  `tests/tools/mutation_crucible.py`: the same mutants and seeded sample, each proven by the crucible runner's
  java-ported side against the hand-written expected event logs (#4024), `--jobs` at a time.
- **Raw score** = caught / (caught + survived). **Without equivalent + unreachable** drops the survivors that
  no input can make observable. Case gaps and harness gaps stay in the denominator: they are real weaknesses of
  the proof. Stillborn mutants (javac refused them) count for nothing; a timeout counts as caught.
- Every survivor was triaged by a model reading the port, the COBOL, the case and the harness, and a sample of
  the "equivalent" and "unreachable" verdicts was checked by hand (for example: COMEN01C's header fields are
  rewritten by `populateHeaderInfo` before every SEND; COACTVWC's `dispatchCdemoToProgramL349` has no caller;
  the CEEDAYS model never returns 0x09CD, so CSUTLDTC's invalid-era branch cannot run). The verdicts are
  judgements, kept with their reasons in the results file.

<!-- mutation-scores -->
| port | harness | mutants run / all | raw score | without equivalent + unreachable | survivors: case gap / harness gap / equivalent / unreachable / untriaged |
|---|---|---|---|---|---|
| COACTVWC (carddemo-acctview) | equivalence | 150/329 | 87/129 (67%) | 87/116 (75%) | 29 / 0 / 12 / 1 / 0 |
| CSUTLDTC (carddemo-dateutil) | equivalence | 217/217 | 135/201 (67%) | 135/145 (93%) | 10 / 0 / 12 / 44 / 0 |
| COMEN01C (carddemo-menu) | equivalence | 150/359 | 72/136 (53%) | 72/84 (86%) | 12 / 0 / 36 / 16 / 0 |
| CALINK (ca-link-lengths) | crucible | 24/165 | 19/22 (86%) | 19/21 (90%) | 2 / 0 / 1 / 0 / 0 |
| CASUB (ca-link-lengths) | crucible | 24/43 | 12/24 (50%) | 12/14 (86%) | 2 / 0 / 6 / 4 / 0 |
| CAXA (ca-xctl-versions) | crucible | 24/74 | 18/21 (86%) | 18/20 (90%) | 2 / 0 / 1 / 0 / 0 |
| CAXB (ca-xctl-versions) | crucible | 24/153 | 15/24 (62%) | 15/19 (79%) | 4 / 0 / 2 / 3 / 0 |
| GTSTART (gt-start-retrieve) | crucible | 24/87 | 14/22 (64%) | 14/18 (78%) | 4 / 0 / 4 / 0 / 0 |
| GTWORK (gt-start-retrieve) | crucible | 24/87 | 17/21 (81%) | 17/19 (89%) | 2 / 0 / 1 / 1 / 0 |
| GTSHOW (gt-terminal-coalesce) | crucible | 24/65 | 20/24 (83%) | 20/21 (95%) | 1 / 0 / 3 / 0 / 0 |
| GTTERM (gt-terminal-coalesce) | crucible | 24/84 | 13/21 (62%) | 13/19 (68%) | 6 / 0 / 1 / 1 / 0 |
| HCMAIN (hc-abend-link) | crucible | 24/196 | 12/24 (50%) | 12/14 (86%) | 2 / 0 / 4 / 6 / 0 |
| HCSUB (hc-abend-link) | crucible | 24/83 | 13/24 (54%) | 13/14 (93%) | 1 / 0 / 5 / 5 / 0 |
| HCQREAD (hc-perform-range) | crucible | 24/201 | 12/21 (57%) | 12/12 (100%) | 0 / 0 / 4 / 5 / 0 |
| HXATTR (hx-attr-bytes) | crucible | 24/152 | 10/20 (50%) | 10/10 (100%) | 0 / 0 / 7 / 3 / 0 |
| HXEXT (hx-extended-cursor) | crucible | 24/105 | 14/22 (64%) | 14/19 (74%) | 5 / 0 / 3 / 0 / 0 |
| PCDETL (pc-aid-menu) | crucible | 24/60 | 14/24 (58%) | 14/14 (100%) | 0 / 0 / 9 / 1 / 0 |
| PCMENU (pc-aid-menu) | crucible | 24/147 | 14/22 (64%) | 14/15 (93%) | 1 / 0 / 5 / 2 / 0 |
| PCCONF (pc-wizard) | crucible | 24/247 | 14/23 (61%) | 14/17 (82%) | 3 / 0 / 6 / 0 / 0 |
| PCWIZ (pc-wizard) | crucible | 24/177 | 11/21 (52%) | 11/16 (69%) | 5 / 0 / 3 / 2 / 0 |
| **all crucible** | | 408 run | **242/380 (64%)** | **242/282 (86%)** | 40 / 0 / 65 / 33 / 0 |
| **all equivalence** | | 517 run | **294/466 (63%)** | **294/345 (85%)** | 51 / 0 / 60 / 61 / 0 |
| **all estate** | | 925 run | **536/846 (63%)** | **536/627 (85%)** | 91 / 0 / 125 / 94 / 0 |

| operator | caught / judged | without equivalent + unreachable |
|---|---|---|
| AOR | 52/65 (80%) | 52/57 (91%) |
| BDM | 1/9 (11%) | 1/2 (50%) |
| CON | 80/167 (48%) | 80/94 (85%) |
| COR | 26/51 (51%) | 26/37 (70%) |
| DEL | 67/117 (57%) | 67/93 (72%) |
| LIT | 97/142 (68%) | 97/106 (92%) |
| NEG | 112/133 (84%) | 112/116 (97%) |
| RET | 8/17 (47%) | 8/13 (62%) |
| ROR | 93/145 (64%) | 93/109 (85%) |
<!-- /mutation-scores -->

Run on gitgalaxy `416fb6420` (2026-10-03): CSUTLDTC all 217 mutants; COMEN01C and COACTVWC 150 each (seed 0);
the 17 crucible ports 24 each (seed 0, cics-crucible v0.2.0). The three batch cases (CBACT04C, CBTRN02C,
CBTRN03C) were not re-run here; their seed-1 raw scores are in the table above this section.

What the triage found:

- **No harness gap.** No survivor changes an output that the proof runs but does not compare. The two found
  earlier (#4053 screen attributes, #4056 SYSOUT) are closed, and the crucible's event log records attributes,
  colour, highlight and cursor.
- **Case gaps (91)** are inputs the cases lack, and they are the test-strengthening loop's (#4049) work list:
  - COACTVWC: a blank or `*` account id; a commarea whose program part, last map or names are not blank; no
    commarea at all; PF3 from a caller other than the menu; an account with a group id, a blank SSN, or a balance of
    1,000,000 or more.
  - COMEN01C: options 9 and 10; option text below `0` (`1!`); a fault plan on the XCTL.
  - CSUTLDTC: a January date; day `00`; year `0000`; year `0001` with a bad day; a non-digit in the last two places.
    So not all of its remaining survivors sit behind undocumented CEEDAYS behaviour. These are valid inputs that the
    CEEDAYS model accepts, though the COBOL still decides their expected results.
  - Fault plans: 15 survivors across the estate are reached only when a CICS command raises a condition, for
    example a WRITEQ TS or an XCTL that fails, or a callee that abends. The crucible has no fault injection, so
    these are case gaps that need a fault plan. The other crucible gaps are scenarios it does not have, such as an
    empty NAME in pc-wizard, a six-character account with a non-digit in hx-extended-cursor, or a bare `CA02`.
- **Unreachable (94).** 57 are in code that no input reaches: CEEDAYS feedback codes the model never returns, the
  fixed COMEN02Y menu table, guards that make a later test impossible. **37 are port code that the proof never
  calls**: controller-style entry points (`executeX`, `handleLink`, `bridgeX`, `onAbendLnn`) and generated helpers
  that the model-written ports kept beside `runTask`. Nothing in the proof calls them, so nothing proves them. They
  are dead in the shipped Java as the harness drives it (#4255).
- **Equivalent (125).** These are mostly padding and truncation that the compare hides: `pad(x, 26)` on an X(25)
  field, a rounding mode on a value already at scale 2, or an initial value that is overwritten before it is read.

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

**Batch cases** (2026-10-01). A batch input is a fixed-width record. The model never writes one: it names an
existing record of an input dataset and the DISPLAY fields to change, and the record is encoded from the dataset's
layout. The tool finds that layout from the program itself: `SELECT … ASSIGN TO` gives the file, `READ … INTO` the
record, and the record's `01` is in a copybook or the program. Each round targets the surviving mutants, the
boundaries a batch proof misses, and judges them again afterwards. Every record shares one run, so a record that
makes the step abend (where the original data does not) is rejected: it would cut the run short for the rest.
Error paths are a fault plan's job. Results, 2 rounds each:

| program | branches | survivors killed | records added |
|---|---|---|---|
| CBTRN02C (POSTTRAN) | 94/96 -> **95/96** (the expired-account reject) | **2 of 7** (an expiry date equal to the transaction date, an off-by-one date slice) | 7 |
| CBACT04C (INTCALC) | 82/86 -> **85/86** (a zero rate, a later account forcing a rewrite) | 0 of 5 | 11 |
| CBTRN03C (TRNRPT) | 81/82 | 0 of 11 | 12 |

The survivors left are mostly equivalent: a rounding mode on a value already at its scale, a width the report
truncates anyway, and defensive file handling the COBOL has no counterpart for. Some sit in the status display of
non-numeric 9x file statuses, which only a fault plan reaches. Two are open: TRNRPT's account-total add/subtract and
its line counter. The strengthened cases are proven, and are `candidate_case.json` files for a person to review;
they are not committed.
