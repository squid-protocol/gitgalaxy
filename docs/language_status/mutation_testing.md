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
  By default each run is a fresh JVM: no state crosses runs.
- `--one-jvm` (the default of `mutation.py run` in fast mode since 2026-10-20, `--no-one-jvm` opts out; opt-in on `equivalence.py run`): the default, fault and entry runs of a batch
  proof share one session JVM (`EquivalenceMain --session`; one run per stdin line, the exit status in a
  `@@EQUIVALENCE-RUN-DONE@@` marker). Python compares each run before sending the next, so `--first-difference`
  still stops early. The generated test class carries `@DirtiesContext`, so each run gets a fresh Spring context
  and in-memory database. Other environments (locale and time zone are fixed in a `static {}` block) and Db2 and
  IMS cases keep a JVM per run. A call proof is one run, so its session saves no JVM start (the flag only keeps the
  runners uniform); a CICS proof shares one session between its task run and its facade run. Static state in the port or
  the det runtime that outlives a run is the risk, which is why the flag stays opt-in.

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
~190 s); `--one-jvm` removes the per-run JVM start.

**Validation of `--one-jvm` (2026-10-18).** One batch case, carddemo-intcalc (CBACT04C, 19 faults), the same 12
mutants (2 stillborn, 10 proofs) in `--full`, fast and `--one-jvm`: **12 of 12 agree** in both comparisons (7
killed, 3 survived: Cbact04cService.java:253, :273, :303). Proof time summed over mutants: full 1,039 s, fast
249 s, fast+one-jvm 71 s (wall time of the run: 618 s, 249 s, 161 s). Not yet validated: a larger sample, a case
with entry runs, so fast mode stays the default.

**Validation of `--one-jvm` on the call and CICS runners (2026-10-18).** 12 mutants each (`--sample 12 --seed 1`),
`mutation.py compare` against the same mutants in `--full` and in fast mode: carddemo-dateutil (CSUTLDTC, call)
and carddemo-menu (COMEN01C, CICS with facades) **12 of 12 agree** in both comparisons. Proof seconds summed:
dateutil full 128, fast 77, fast+one-jvm 71; menu full 460, fast 413, fast+one-jvm 390. A small sample; the
default stays fast mode.

**Larger validation of `--one-jvm` (2026-10-19).** `--sample N --seed 2` in `--full`, then the same mutants in fast
mode and `--one-jvm`, judged by `mutation.py compare` (now a gate: `--require-agree N` exits 1 unless N mutants
were judged by both and none differ; it also reports per-operator disagreements and the survivors' proof seconds):

| case | mutants judged by both | agree | killed / survived / stillborn | proof s, full -> fast -> one-jvm | survivors' proof s, full -> fast -> one-jvm |
|---|---|---|---|---|---|
| carddemo-intcalc (CBACT04C, batch, 19 faults) | 40 | 40 | 29 / 7 / 4 | 5,353 -> 924 -> 318 | 894 -> 606 -> 113 |
| carddemo-menu (COMEN01C, CICS with facades) | 30 | 30 | 19 / 9 / 2 | 1,001 -> 506 -> 349 | 309 -> 179 -> 116 |

**70 of 70 agree** in both comparisons, every operator (intcalc: ROR, CON, LIT, NEG, COR, DEL, BDM, AOR, 0 differ).
A survivor costs about 1/8 (intcalc) to 1/3 (menu) of its `--full` proof. Not validated, so fast mode stays the
default: **a case with entry runs.** No committed port has an entry method (`executeX`) and no committed `case.json`
has `entries`; a candidate `entries` case on carddemo-readcard fails to build against the committed port (no
`executeCbact02c`), so entry runs in a session JVM are covered by unit tests only. The call runner was validated on
12 mutants (above), not on this larger sample.

**`--one-jvm` on a call, a second batch and a second CICS port (2026-10-20, #4047).** `--sample N --seed 2` in
`--full`, then the same mutants in fast mode and `--one-jvm`, judged by `mutation.py compare --require-agree N`:

| case | judged by both | `--full` vs fast | `--full` vs `--one-jvm` | fast vs `--one-jvm` |
|---|---|---|---|---|
| carddemo-dateutil (CSUTLDTC, call) | 40 | 40 agree | 40 agree | 40 agree |
| carddemo-posttran (CBTRN02C, batch, 29 runs) | 30 | 22 agree, 8 differ | 22 agree, 8 differ | 30 agree |
| carddemo-cardlist (COCRDLIC, CICS) | 30 | 12 agree, 18 differ | not finished | not run |

dateutil: proof seconds full 673, fast 386, `--one-jvm` 374 (survivors 174 -> 104 -> 93). The call runner is now
validated on 40 mutants, every operator. **`--one-jvm` stays opt-in:** posttran and cardlist disagree with `--full`
in plain fast mode too, so the cause is not the session JVM (fast and `--one-jvm` give the same 30 verdicts on posttran).
The disagreements, re-run in `--full` with a 2,400 s limit (so not a timeout): 7 mutants that `--full` calls
*survived* and fast calls *killed* (posttran 2, cardlist 5), plus 6 `--full` and 13 fast `no report (exit 1)` errors
(infrastructure, not verdicts). posttran fast kills all 28 judged mutants, each by the fault run `open-dalytran`:
`faults fired differ: COBOL ['DALYTRAN OPEN 1 35', 'DALYTRAN OPEN 1 35'], Java ['DALYTRAN OPEN 1 35']`. The kept
baseline's COBOL `FAULTS` file lists a file fault twice (the fault fires at two hooks); under `--reuse` the mutant's
Java side lists it once, where `--full` lists it twice. A CON mutant killed by an OPEN fault is a false kill: fast mode
overstates the score on posttran. Not yet found why the reused project's Java side fires once. Until fast mode agrees with
`--full` on posttran and cardlist, `--one-jvm` is not made the default.

**Re-run after the fault-log fix, fresh sample, `--jobs` 1 vs 2 (2026-10-20, #4047, on #5748).** #5748 removes the stale
`work/FAULTS` file before a fault step that is not reused; that was the false `faults fired differ` kill on posttran.
`--sample 20 --seed 3` in `--full` (`--jobs 1`), then the same mutants in fast mode at `--jobs 1` and `--jobs 2`, judged by
`mutation.py compare`:

| case | judged by both | `--full` vs fast `--jobs 1` | `--full` vs fast `--jobs 2` | fast `--jobs 1` vs `--jobs 2` | killed / survived / stillborn | proof s, full -> fast 1 -> fast 2 |
|---|---|---|---|---|---|---|
| carddemo-cardlist (COCRDLIC, CICS) | 20 | 20 agree | 20 agree | 20 agree | 16 / 2 / 2 | 558 -> 272 -> 199 |
| carddemo-posttran (CBTRN02C, batch) | 20 | 20 agree | 20 agree | 20 agree | 13 / 3 / 4 | 2,207 -> 405 -> 461 |

No `no report` errors. **bbd92e25af** (COCRDLIC, `CocrdlicService.java:997`, RET `return false;` -> `return true;`): the
earlier seed-2 batch killed it in fast mode (by the fault runs `readnext-io-error-on-the-look-ahead`,
`readprev-io-error-first`, `readprev-io-error-mid-page`, events equal, "differs"), while it survives alone in fast mode and in
`--full`. The whole seed-2 cardlist batch (30 mutants, judged against the old `--full` reference) was re-run in fast mode at
`--jobs 2` and `--jobs 1`: **30 of 30 agree both times and bbd92e25af survives both times**. So `--jobs 2` sharing the reused
baseline is not shown to be the cause (it is not reproduced at `--jobs 2`), and the one earlier kill is not reproduced with
the fault-log fix; its cause is not identified, only that it has not come back in 2 re-runs. Fast mode now agrees
with `--full` on posttran and cardlist (20 fresh mutants each, plus the 30 seed-2 cardlist mutants), at both `--jobs` values;
dateutil agreed before. Not validated: `--one-jvm` on these two cases after the fix (fast and `--one-jvm` agreed on posttran
before it), entry runs, and samples above 40. `--one-jvm` therefore stays opt-in until it is compared on the fixed code.

**`--one-jvm` on the fixed code, and the default (2026-10-20, #4047).** The same fresh `--sample 20 --seed 3` mutants
as above, `--one-jvm` (`--jobs 1`) judged by `mutation.py compare` against the `--full` reference and against fast
`--jobs 1`:

| case | `--full` vs `--one-jvm` | fast vs `--one-jvm` | proof s, full -> fast -> one-jvm | survivors' proof s, full -> fast -> one-jvm |
|---|---|---|---|---|
| carddemo-cardlist (COCRDLIC, CICS) | 20 of 20 agree | 20 of 20 agree | 558 -> 272 -> 123 | 52 -> 33 -> 14 |
| carddemo-posttran (CBTRN02C, batch) | 20 of 20 agree | 20 of 20 agree | 2,207 -> 405 -> 118 | 421 -> 305 -> 45 |

Every operator present agreed. With the earlier agreements (intcalc 40 and menu 30 and dateutil 40 of 40, and the
12-mutant checks) `--one-jvm` has agreed with `--full` on every burned-estate case sampled, so `mutation.py run` now
uses it in fast mode (`--full` does not; `--no-one-jvm` gives a JVM per run; `--record` uses it too). Not validated:
a case with entry runs (no burned committed port has one; unit tests only), the 17 crucible ports run through
`mutation_crucible.py`, samples above 40. Db2 and IMS cases still get a JVM per run. If a `compare` against
`--full` ever disagrees on a new case, rerun with `--no-one-jvm` first.

**Four more burned cases, and a fast-mode defect they found (2026-10-20, #4047).** `--sample N --seed 7` in `--full`
(`--jobs 1`), then the same mutants in fast mode with the session JVM (the default) and, where stated, without it,
judged by `mutation.py compare --require-agree N`:

| case | judged by both | `--full` vs `--one-jvm` | fast (JVM per run) vs `--one-jvm` | killed / survived / stillborn | proof s, full -> one-jvm |
|---|---|---|---|---|---|
| genapp-lgicdb01 (LGICDB01, CICS + Db2) | 20 | 20 agree | 20 agree | 6 / 11 / 3 | 582 -> 455 |
| carddemo-tranlist (COTRN00C, CICS) | 20 | 20 agree | 20 agree | 13 / 6 / 1 | 362 -> 187 |
| carddemo-trnrpt (CBTRN03C, batch) | 12 | 12 agree | 12 agree | 8 / 2 / 2 | 1,827 -> 153 |
| cbsa-inqacc (INQACC, CICS + Db2, LINKs ABNDPROC), before the fix | 20 | **11 agree, 9 differ** | 20 agree | 8 / 9 / 3 (`--full`) | 551 -> 394 |
| cbsa-inqacc, after the fix | 20 | 20 agree | (fast vs `--full`: 20 agree) | 8 / 9 / 3 | 551 -> 775 (run beside another proof) |
| genapp-lgapvs01 (LGAPVS01, LINKs LGSTSQ), after the fix | 15 | 15 agree | not run | 6 / 6 / 3 | 317 -> 105 |

**The defect was fast mode, not the session JVM** (fast with a JVM per run gave the same 17 kills). Nine mutants that
`--full` calls survived died in fast mode with `Hole: CICS file ABNDFILE: the program names no file the generated
project stores`, thrown from the LINKed ABNDPROC. The proof translates a LINKed program (`"programs"` in `case.json`)
from the generated stub in the project; on `--reuse` that file was already the earlier run's translation, so the new
translation had no file stores. `--reuse` now carries the earlier run's `generated_before_overlay` (the stubs) and
`linked_programs` translates from it. Fast mode was therefore **not** agreeing with `--full` on a case whose proof
LINKs a det-translated program, and its score overstated the kills: the committed cbsa-inqacc score (131 killed, 0
survived of 150) was recorded before this fix.

**Re-recorded (2026-10-21, #4047).** The scored cases with a det-translated LINKed program are exactly five (the five
below; the other 38 scored cases have no `"programs"`), each re-run with `--sample 150 --seed 0 --jobs 2 --record`
on the fixed code. cbsa-inqacc fell from 131 killed / 0 survived to **63 killed / 68 survived** (43 case gaps: no
scenario declares a SQL or CICS fault, so the abend path and the ABNDPROC record are never run; 11 equivalent; 14
unreachable: widths beyond the DB2 column, and the facade entry no proof calls). The four GenApp cases did not move except genapp-lgupdb01 (67 -> 68 killed).

**The 17 crucible ports get a fast mode (2026-10-21, #4047).** `mutation_crucible.py` already ran every scenario of a
side in one JVM (`mvn test`, one JVM per side); what each mutant repeated was the refactor and cobol-to-java generate.
Fast mode (the default; `--full` opts out) generates the case's Java project once, in the baseline proof, and each mutant
copies it (without `target/`), lays its overlay and compiles (`cics_crucible.py --forge-cache`). Both sides still run
every scenario, so `killed_by` is the same. `mutation_crucible.py compare A B --require-agree N` judges two runs.
`--sample 24 --seed 2`, `--full` then fast, `--jobs 2`:

| port | judged by both | agree | proof s, full -> fast | survivors' proof s, full -> fast |
|---|---|---|---|---|
| ca-link-lengths / CASUB | 24 | 24 | 397 -> 292 | 165 -> 122 |
| gt-start-retrieve / GTSTART | 24 | 24 | 342 -> 335 | 101 -> 95 |
| hx-extended-cursor / HXEXT | 24 | 24 | 371 -> 308 | 115 -> 93 |

72 of 72 agree, every operator present (AOR, COR, CON, DEL, LIT, NEG, RET, ROR). The saving is modest (2-26%): a crucible
proof is mostly the two Maven runs, not the 12-14 s generate.

**The other 14 crucible ports (2026-10-21, #4047).** The same `--sample 24 --seed 2 --jobs 2`, `--full` then fast, each
pair judged by `mutation_crucible.py compare --require-agree 10` (the box was otherwise idle):

| port | judged by both | agree | proof s, full -> fast | survivors' proof s, full -> fast |
|---|---|---|---|---|
| ca-link-lengths / CALINK | 24 | 24 | 686 -> 283 | 118 -> 47 |
| ca-xctl-versions / CAXA | 24 | 24 | 639 -> 240 | 222 -> 89 |
| ca-xctl-versions / CAXB | 24 | 24 | 669 -> 257 | 282 -> 111 |
| gt-terminal-coalesce / GTSHOW | 24 | 24 | 626 -> 246 | 186 -> 78 |
| gt-terminal-coalesce / GTTERM | 24 | 24 | 643 -> 250 | 166 -> 69 |
| gt-start-retrieve / GTWORK | 24 | 24 | 745 -> 372 | 85 -> 33 |
| hc-abend-link / HCMAIN | 24 | 24 | 721 -> 314 | 397 -> 170 |
| hc-perform-range / HCQREAD | 24 | 24 | 660 -> 250 | 262 -> 110 |
| hc-abend-link / HCSUB | 24 | 24 | 1118 -> 592 | 296 -> 160 |
| hx-attr-bytes / HXATTR | 24 | 24 | 664 -> 289 | 111 -> 51 |
| pc-wizard / PCCONF | 24 | 24 | 746 -> 301 | 340 -> 142 |
| pc-aid-menu / PCDETL | 24 | 24 | 692 -> 328 | 260 -> 123 |
| pc-aid-menu / PCMENU | 24 | 24 | 667 -> 276 | 280 -> 119 |
| pc-wizard / PCWIZ | 24 | 24 | 726 -> 281 | 212 -> 83 |

**336 of 336 agree** (every operator present: AOR, BDM, CON, COR, DEL, LIT, NEG, RET, ROR); with the three above, 408 of 408
on 17 of the 21 scored crucible programs. Proof time over the 14: 10,003 s -> 4,278 s (57% less; the saving is larger than the
2-26% above because those three ran beside other proofs). The four PCIMM ports (PCIMMA/B/L/S, whose runtime mutants
are left out of the sample) and larger samples follow; entry runs (no burned port has any) are not validated.

**The PCIMM ports and samples above 24 (2026-10-21, #4047).** The PCIMM ports with `--sample 24 --seed 2 --jobs 2`; the
larger samples with `--seed 5` (crucible) and `--seed 9` (burned), `--full` then fast (the session JVM for the burned case),
judged by `compare --require-agree`:

| port / case | judged by both | agree | proof s, full -> fast | survivors' proof s, full -> fast |
|---|---|---|---|---|
| pc-return-immediate / PCIMMA | 24 | 24 | 334 -> 279 | 210 -> 175 |
| pc-return-immediate / PCIMMB | 24 | 24 | 327 -> 278 | 230 -> 199 |
| pc-return-immediate / PCIMML | 24 | 24 | 326 -> 295 | 246 -> 222 |
| pc-return-immediate / PCIMMS | 24 | 24 | 356 -> 281 | 234 -> 186 |
| ca-link-lengths / CASUB (`--sample 80`: all 40 mutants) | 40 | 40 | 559 -> 491 | 202 -> 172 |
| hc-abend-link / HCSUB (`--sample 80`) | 80 | 80 | 1,279 -> 1,010 | 553 -> 432 |
| carddemo-tranlist (COTRN00C, CICS, `--sample 80`) | 80 | 80 | 1,988 -> 1,248 | 461 -> 219 |

**296 of 296 agree**, no `no report` errors, every operator present (AOR, BDM, COR, CON, DEL, LIT, NEG, RET, ROR). With the
earlier tables, fast mode has agreed with `--full` on all 21 scored crucible programs.

**Samples above 80 (2026-10-21, #4047).** `--sample N --seed 11 --jobs 2`, `--full` then fast (the session JVM), judged by
`mutation.py compare --require-agree`:

| case | judged by both | agree | killed / survived / stillborn | proof s, full -> fast | survivors' proof s, full -> fast |
|---|---|---|---|---|---|
| carddemo-tranlist (COTRN00C, CICS, `--sample 160`) | 160 | 160 | 108 / 45 / 7 (4 of the killed by timeout) | 4,201 -> 2,604 | 915 -> 411 |
| carddemo-menu (COMEN01C, CICS, `--sample 120`) | 120 | 120 | 72 / 39 / 9 (1 of the killed by timeout) | 2,067 -> 1,479 | 646 -> 423 |

**280 of 280 agree**, the same verdict counts in both modes, every operator the cases have (tranlist: AOR, BDM, CON, COR, DEL,
LIT, NEG, RET, ROR; menu: AOR, CON, COR, DEL, LIT, NEG, ROR). A survivor costs about 45% (tranlist) to 65% (menu) of its
`--full` proof. With the earlier tables the largest burned sample judged is 160.

**Entry runs have nothing burned to be validated on.** No committed `tests/equivalence/*/case.json` has `entries`;
`test_mutation_one_jvm_scope_4047.py` fails the day one does, so that case is compared against `--full` (and recorded
here) before the default covers it. Entry runs stay covered by unit tests. Db2 and IMS cases always use a JVM per run.

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
- The last table (generated with the others) gives each port's caught / judged per operator; `-` means the port had no judged mutant of that operator.
- **Raw score** = caught / (caught + survived). **Without equivalent + unreachable** drops the survivors that
  no input can make observable. Case gaps and harness gaps stay in the denominator: they are real weaknesses of
  the proof. Stillborn mutants (javac refused them) count for nothing; a timeout counts as caught.
- Every survivor was triaged by a model reading the port, the COBOL, the case and the harness, and a sample of
  the "equivalent" and "unreachable" verdicts was checked by hand (for example: COMEN01C's header fields are
  rewritten by `populateHeaderInfo` before every SEND; COACTVWC's `dispatchCdemoToProgramL349` has no caller;
  the CEEDAYS model never returns 0x09CD, so CSUTLDTC's invalid-era branch cannot run). The verdicts are
  judgements, kept with their reasons in the results file.
- The three GenApp ports (LGAPVS01, LGICDB01, LGUPDB01) were re-run on the current port, case and harness and each
  survivor read (#4047): most are harness gaps (the error-message text is judged only through the refused WRITEQ,
  X6 #4050, or the statement needs a Db2 fault the harness cannot inject); the case gaps are the absent-policy and
  zero-row motor update scenarios and an LGUPVS01 failure.
- LGICDB01 re-run after #6882 (SELECT through `DetSql`, three `sql_faults` scenarios; seed 0, 150 of 196 mutants):
  94 caught, 42 survived, 14 stillborn (was 51 / 79 / 20). The 42: 15 harness gaps (the LGSTSQ LINK-failure arms, the
  error-message text behind X6, the too-short COMMAREA check), 14 equivalent, 11 unreachable (facade entry, no
  COMMAREA), 2 case gaps (a NULL column read, SQLCODE read as 8 bytes needs a fault with a message token).
- INQACC and LGICDB01 re-run on their det ports (#6692; seed 0, 150 mutants each). INQACC: 68 caught, 78 survived, 4
  stillborn of 2413 mutants; LGICDB01: 40 caught, 100 survived, 10 stillborn of 1363 (the model-port record was 94 / 42
  / 14, a different sample of a different file, so the two are not a before/after).
  INQACC survivors: 72 case gaps, 5 unreachable, 1 equivalent; LGICDB01: 86 case gaps, 8 harness gaps, 4 unreachable,
  2 equivalent. The unreachable ones are code no proof runs (the facade's `lastLinkBytes` assignments and accessor,
  ABNDPROC's `abended()` level test, `paragraph()` throw and `runProgram()`). The 8 harness gaps are LGSTSQ's terminal
  RECEIVE arm, which this case reaches only as a LINK target. The case gaps are read, not measured: most sit in the
  translator's initial-state image constants, COMMAREA sizing and write-back, PERFORM bookkeeping and DTO null arms, which
  no scenario of these two cases drives differently. One INQACC survivor (the SORTCODE field's decimal scale, `daa60daa89`)
  is unexplained and is listed as a follow-up, not ruled out.
- UPDACC on generated Db2 rows (cbsa-updacc-generated, #4507, all 139 mutants run, seed 0): 103 killed, 36 survived
  (7 harness gaps, 17 equivalent, 12 unreachable). The seven harness gaps are the `-904` UPDATE-failure arm: a
  `sql_faults` scenario was tried and the proof refuses it ("no SQL fault hook in UPDACC": the model-written port
  reaches Db2 through JDBC, not `cobolrt.sql.DetSql`), so the scenario was not kept. A det-translated UPDACC takes the
  fault: `cbsa-updacc-faults` (no `port/`, the hand case's DDL and seed) injects `-904`, `-913` and `-803` on the UPDATE
  (line 278) and `-904` / `-913` on the SELECT (line 191), and `det_port.py run` proves it on 10 scenarios covering
  7/7 paragraphs and 6/6 branches. The seven stay recorded as harness gaps of the model port (its mutants are not
  re-run against the det case); the det-port fault case is where that arm is judged.
- UPDACC on the hand case (cbsa-updacc, #4049, all 139 mutants run, seed 0): 95 killed -> 103, 15 case gaps -> 0. Eight
  seed rows with a single NULL each (EYECATCHER, CUSTOMER_NUMBER, NEXT_STATEMENT, AVAILABLE / ACTUAL balance, ACCOUNT_TYPE,
  INTEREST_RATE, OVERDRAFT_LIMIT) and a `null-*` scenario per row kill the seven `&&` / `||` mutants of the -305 test (the
  old seed's only NULL, ACCOUNT_LAST_STATEMENT, hid them); the eyecatcher one was already killed by the earlier
  eyecatcher scenarios. The `-904` arms of the SELECT and UPDATE are `harness-gap` (7), as in cbsa-updacc-generated, and the
  six `handleLink(request, area)` mutants are `unreachable` (no proof calls it: the harness enters through the one-parameter
  `handleLink(request)` and no caller LINKs with LENGTH). Stop reason: no case gap left.

<!-- mutation-scores -->
| port | harness | mutants run / all | raw score | without equivalent + unreachable | survivors: case gap / harness gap / equivalent / unreachable / untriaged |
|---|---|---|---|---|---|
| COACTVWC (carddemo-acctview) | equivalence | 150/446 | 119/137 (87%) | 119/119 (100%) | 0 / 0 / 12 / 6 / 0 |
| COACTVWC (carddemo-acctview-generated) | equivalence | 150/427 | 109/137 (80%) | 109/109 (100%) | 0 / 0 / 16 / 12 / 0 |
| COADM01C (carddemo-adminmenu) | equivalence | 100/340 | 63/95 (66%) | 63/63 (100%) | 0 / 0 / 29 / 3 / 0 |
| COADM01C (carddemo-adminmenu-generated) | equivalence | 150/340 | 97/145 (67%) | 97/97 (100%) | 0 / 0 / 43 / 5 / 0 |
| COBIL00C (carddemo-billpay) | equivalence | 100/529 | 66/86 (77%) | 66/70 (94%) | 4 / 0 / 12 / 4 / 0 |
| COBIL00C (carddemo-billpay-generated) | equivalence | 150/530 | 104/136 (76%) | 104/104 (100%) | 0 / 0 / 17 / 15 / 0 |
| COCRDLIC (carddemo-cardlist) | equivalence | 100/1034 | 82/94 (87%) | 82/82 (100%) | 0 / 0 / 12 / 0 / 0 |
| COCRDSLC (carddemo-cardview) | equivalence | 100/503 | 60/91 (66%) | 60/65 (92%) | 4 / 1 / 22 / 4 / 0 |
| CBTRN01C (carddemo-dailyval) | equivalence | 100/241 | 63/96 (66%) | 63/71 (89%) | 8 / 0 / 10 / 15 / 0 |
| CSUTLDTC (carddemo-dateutil) | equivalence | 276/276 | 197/260 (76%) | 197/197 (100%) | 0 / 0 / 13 / 50 / 0 |
| CBACT04C (carddemo-intcalc) | equivalence | 100/170 | 70/86 (81%) | 70/77 (91%) | 6 / 1 / 9 / 0 / 0 |
| COMEN01C (carddemo-menu) | equivalence | 150/340 | 87/139 (63%) | 87/87 (100%) | 0 / 0 / 35 / 17 / 0 |
| COMEN01C (carddemo-menu-generated) | equivalence | 150/340 | 87/139 (63%) | 87/88 (99%) | 0 / 1 / 35 / 16 / 0 |
| CBTRN02C (carddemo-posttran) | equivalence | 100/263 | 76/85 (89%) | 76/80 (95%) | 3 / 1 / 5 / 0 / 0 |
| CBACT02C (carddemo-readcard) | equivalence | 91/91 | 69/83 (83%) | 69/73 (95%) | 4 / 0 / 10 / 0 / 0 |
| CBCUS01C (carddemo-readcust) | equivalence | 83/83 | 63/74 (85%) | 63/70 (90%) | 7 / 0 / 4 / 0 / 0 |
| CBACT03C (carddemo-readxref) | equivalence | 90/90 | 69/83 (83%) | 69/77 (90%) | 8 / 0 / 6 / 0 / 0 |
| CORPT00C (carddemo-report) | equivalence | 100/642 | 59/87 (68%) | 59/60 (98%) | 0 / 0 / 16 / 11 / 0 + 1 declared |
| COSGN00C (carddemo-signon) | equivalence | 100/196 | 67/99 (68%) | 67/72 (93%) | 5 / 0 / 25 / 2 / 0 |
| COSGN00C (carddemo-signon-generated) | equivalence | 150/202 | 99/149 (66%) | 99/99 (100%) | 0 / 0 / 42 / 8 / 0 |
| COTRN02C (carddemo-tranadd) | equivalence | 100/770 | 70/91 (77%) | 70/73 (96%) | 3 / 0 / 10 / 8 / 0 |
| COTRN00C (carddemo-tranlist) | equivalence | 100/697 | 66/91 (73%) | 66/79 (84%) | 13 / 0 / 5 / 7 / 0 |
| COTRN01C (carddemo-tranview) | equivalence | 100/314 | 67/100 (67%) | 67/67 (100%) | 0 / 0 / 25 / 8 / 0 |
| COTRN01C (carddemo-tranview-generated) | equivalence | 150/314 | 92/150 (61%) | 92/92 (100%) | 0 / 0 / 48 / 10 / 0 |
| CBTRN03C (carddemo-trnrpt) | equivalence | 100/408 | 68/86 (79%) | 68/79 (86%) | 8 / 3 / 7 / 0 / 0 |
| COUSR01C (carddemo-useradd) | equivalence | 100/272 | 63/98 (64%) | 63/64 (98%) | 0 / 1 / 27 / 7 / 0 |
| COUSR03C (carddemo-userdel) | equivalence | 100/340 | 67/87 (77%) | 67/67 (100%) | 0 / 0 / 17 / 3 / 0 |
| COUSR00C (carddemo-userlist) | equivalence | 512/512 | 381/507 (75%) | 381/381 (100%) | 0 / 0 / 55 / 71 / 0 |
| COUSR02C (carddemo-userupd) | equivalence | 100/481 | 57/82 (70%) | 57/59 (97%) | 2 / 0 / 14 / 9 / 0 |
| INQACC (cbsa-inqacc) | equivalence | 150/2413 | 68/146 (47%) | 68/140 (49%) | 72 / 0 / 1 / 5 / 0 |
| UPDACC (cbsa-updacc) | equivalence | 139/139 | 103/139 (74%) | 103/110 (94%) | 0 / 7 / 17 / 12 / 0 |
| UPDACC (cbsa-updacc-generated) | equivalence | 139/139 | 103/139 (74%) | 103/110 (94%) | 0 / 7 / 17 / 12 / 0 |
| LGAPDB01 (genapp-lgapdb01) | equivalence | 150/444 | 58/137 (42%) | 58/129 (45%) | 71 / 0 / 1 / 7 / 0 |
| LGAPVS01 (genapp-lgapvs01) | equivalence | 150/184 | 72/125 (58%) | 72/113 (64%) | 0 / 41 / 1 / 11 / 0 |
| LGICDB01 (genapp-lgicdb01) | equivalence | 150/1363 | 40/140 (29%) | 40/134 (30%) | 86 / 8 / 2 / 4 / 0 |
| LGSTSQ (genapp-lgstsq) | equivalence | 89/89 | 25/78 (32%) | 25/69 (36%) | 43 / 1 / 1 / 8 / 0 |
| LGUPDB01 (genapp-lgupdb01) | equivalence | 150/403 | 68/140 (49%) | 68/120 (57%) | 6 / 46 / 5 / 15 / 0 |
| LGUPVS01 (genapp-lgupvs01) | equivalence | 150/160 | 66/119 (55%) | 66/100 (66%) | 0 / 34 / 4 / 15 / 0 |
| CALINK (ca-link-lengths) | crucible | 24/168 | 15/22 (68%) | 15/15 (100%) | 0 / 0 / 5 / 2 / 0 |
| CASUB (ca-link-lengths) | crucible | 24/40 | 16/24 (67%) | 16/16 (100%) | 0 / 0 / 7 / 1 / 0 |
| CAXA (ca-xctl-versions) | crucible | 24/78 | 16/21 (76%) | 16/16 (100%) | 0 / 0 / 3 / 2 / 0 |
| CAXB (ca-xctl-versions) | crucible | 24/142 | 20/23 (87%) | 20/20 (100%) | 0 / 0 / 2 / 1 / 0 |
| GTSTART (gt-start-retrieve) | crucible | 24/91 | 19/22 (86%) | 19/19 (100%) | 0 / 0 / 3 / 0 / 0 |
| GTWORK (gt-start-retrieve) | crucible | 24/87 | 20/21 (95%) | 20/20 (100%) | 0 / 0 / 0 / 1 / 0 |
| GTSHOW (gt-terminal-coalesce) | crucible | 24/69 | 17/23 (74%) | 17/17 (100%) | 0 / 0 / 5 / 1 / 0 |
| GTTERM (gt-terminal-coalesce) | crucible | 24/88 | 17/21 (81%) | 17/17 (100%) | 0 / 0 / 3 / 1 / 0 |
| HCMAIN (hc-abend-link) | crucible | 24/176 | 14/23 (61%) | 14/14 (100%) | 0 / 0 / 4 / 5 / 0 |
| HCSUB (hc-abend-link) | crucible | 24/85 | 18/24 (75%) | 18/18 (100%) | 0 / 0 / 3 / 3 / 0 |
| HCQREAD (hc-perform-range) | crucible | 24/204 | 14/21 (67%) | 14/14 (100%) | 0 / 0 / 4 / 3 / 0 |
| HXATTR (hx-attr-bytes) | crucible | 24/143 | 17/22 (77%) | 17/17 (100%) | 0 / 0 / 5 / 0 / 0 |
| HXEXT (hx-extended-cursor) | crucible | 24/108 | 20/23 (87%) | 20/20 (100%) | 0 / 0 / 1 / 2 / 0 |
| PCDETL (pc-aid-menu) | crucible | 24/63 | 15/24 (62%) | 15/15 (100%) | 0 / 0 / 9 / 0 / 0 |
| PCMENU (pc-aid-menu) | crucible | 24/137 | 16/24 (67%) | 16/16 (100%) | 0 / 0 / 6 / 2 / 0 |
| PCIMMA (pc-return-immediate) | crucible | 24/394 | 6/22 (27%) | 6/16 (38%) | 10 / 0 / 5 / 1 / 0 |
| PCIMMB (pc-return-immediate) | crucible | 24/283 | 11/23 (48%) | 11/18 (61%) | 7 / 0 / 5 / 0 / 0 |
| PCIMML (pc-return-immediate) | crucible | 24/282 | 9/23 (39%) | 9/19 (47%) | 10 / 0 / 3 / 1 / 0 |
| PCIMMS (pc-return-immediate) | crucible | 24/198 | 8/24 (33%) | 8/16 (50%) | 8 / 0 / 7 / 1 / 0 |
| PCCONF (pc-wizard) | crucible | 24/838 | 15/23 (65%) | 15/15 (100%) | 0 / 0 / 4 / 4 / 0 |
| PCWIZ (pc-wizard) | crucible | 24/146 | 16/23 (70%) | 16/16 (100%) | 0 / 0 / 4 / 3 / 0 |
| **all crucible** | | 504 run | **319/476 (67%)** | **319/354 (90%)** | 35 / 0 / 88 / 34 / 0 |
| **all equivalence** | | 5119 run | **3240/4756 (68%)** | **3240/3746 (86%)** | 353 / 152 / 630 / 380 / 0 + 1 declared |
| **all estate** | | 5623 run | **3559/5232 (68%)** | **3559/4100 (87%)** | 388 / 152 / 718 / 414 / 0 + 1 declared |

| operator | caught / judged | without equivalent + unreachable |
|---|---|---|
| AOR | 254/318 (80%) | 254/286 (89%) |
| BDM | 28/54 (52%) | 28/31 (90%) |
| CON | 471/1061 (44%) | 471/586 (80%) |
| COR | 230/354 (65%) | 230/264 (87%) |
| DEL | 613/885 (69%) | 613/706 (87%) |
| LIT | 724/990 (73%) | 724/825 (88%) |
| NEG | 616/707 (87%) | 616/673 (92%) |
| RET | 49/82 (60%) | 49/70 (70%) |
| ROR | 574/781 (73%) | 574/659 (87%) |

| port | AOR | BDM | CON | COR | DEL | LIT | NEG | RET | ROR |
|---|---|---|---|---|---|---|---|---|---|
| COACTVWC (carddemo-acctview) | 7/9 | 0/1 | 14/22 | 18/21 | 19/21 | 20/21 | 21/21 | - | 20/21 |
| COACTVWC (carddemo-acctview-generated) | 6/9 | 0/1 | 14/22 | 17/21 | 16/21 | 16/21 | 20/21 | - | 20/21 |
| COADM01C (carddemo-adminmenu) | 8/8 | - | 2/14 | 6/8 | 8/16 | 7/15 | 15/15 | 4/4 | 13/15 |
| COADM01C (carddemo-adminmenu-generated) | 8/8 | - | 4/24 | 6/8 | 14/26 | 14/25 | 25/25 | 4/4 | 22/25 |
| COBIL00C (carddemo-billpay) | 4/5 | 1/3 | 5/13 | 9/12 | 10/12 | 12/13 | 12/13 | 2/2 | 11/13 |
| COBIL00C (carddemo-billpay-generated) | 5/6 | 1/3 | 9/23 | 9/12 | 17/22 | 21/23 | 22/23 | 2/2 | 18/22 |
| COCRDLIC (carddemo-cardlist) | 8/8 | - | 9/13 | 11/13 | 10/13 | 12/13 | 13/13 | 8/9 | 11/12 |
| COCRDSLC (carddemo-cardview) | 4/5 | - | 3/14 | 10/14 | 6/14 | 9/14 | 13/14 | 2/2 | 13/14 |
| CBTRN01C (carddemo-dailyval) | 3/6 | - | 11/16 | 3/12 | 9/15 | 12/16 | 12/16 | - | 13/15 |
| CSUTLDTC (carddemo-dateutil) | 17/18 | - | 42/72 | 9/15 | 11/11 | 30/38 | 38/39 | - | 50/67 |
| CBACT04C (carddemo-intcalc) | 3/4 | 4/6 | 13/21 | 1/2 | 13/17 | 20/20 | 10/10 | - | 6/6 |
| COMEN01C (carddemo-menu) | 13/14 | - | 6/21 | 6/10 | 20/24 | 12/24 | 16/23 | - | 14/23 |
| COMEN01C (carddemo-menu-generated) | 13/14 | - | 6/21 | 6/10 | 20/24 | 12/24 | 16/23 | - | 14/23 |
| CBTRN02C (carddemo-posttran) | 6/6 | 6/8 | 14/15 | 2/4 | 10/11 | 13/14 | 13/13 | - | 12/14 |
| CBACT02C (carddemo-readcard) | - | - | 17/23 | 1/3 | 9/11 | 22/25 | 12/12 | - | 8/9 |
| CBCUS01C (carddemo-readcust) | - | - | 12/13 | 1/4 | 8/8 | 23/27 | 10/10 | - | 9/12 |
| CBACT03C (carddemo-readxref) | - | - | 16/19 | 1/4 | 9/9 | 22/27 | 10/10 | - | 11/14 |
| CORPT00C (carddemo-report) | 3/3 | 0/1 | 1/11 | 10/13 | 7/13 | 12/13 | 13/13 | 4/7 | 9/13 |
| COSGN00C (carddemo-signon) | 2/2 | - | 3/20 | 3/4 | 12/20 | 18/20 | 15/16 | - | 14/17 |
| COSGN00C (carddemo-signon-generated) | 2/2 | - | 6/36 | 4/5 | 23/36 | 31/35 | 16/16 | - | 17/19 |
| COTRN02C (carddemo-tranadd) | 7/7 | 5/7 | 4/12 | 9/12 | 8/12 | 11/12 | 11/11 | 4/7 | 11/11 |
| COTRN00C (carddemo-tranlist) | 6/9 | - | 10/14 | 8/14 | 11/13 | 10/14 | 11/11 | 2/3 | 8/13 |
| COTRN01C (carddemo-tranview) | 1/1 | - | 2/24 | 2/3 | 21/24 | 19/24 | 17/17 | - | 5/7 |
| COTRN01C (carddemo-tranview-generated) | 1/1 | - | 3/43 | 2/3 | 34/43 | 30/36 | 17/17 | - | 5/7 |
| CBTRN03C (carddemo-trnrpt) | 2/2 | 5/7 | 9/14 | 1/7 | 14/14 | 13/14 | 12/14 | - | 12/14 |
| COUSR01C (carddemo-useradd) | 1/1 | - | 1/21 | 3/6 | 16/20 | 16/20 | 10/10 | - | 16/20 |
| COUSR03C (carddemo-userdel) | 0/1 | - | 6/17 | 2/4 | 14/17 | 14/16 | 16/16 | - | 15/16 |
| COUSR00C (carddemo-userlist) | 12/12 | - | 51/124 | 28/38 | 113/126 | 76/95 | 49/51 | - | 52/61 |
| COUSR02C (carddemo-userupd) | 1/1 | - | 3/16 | 3/5 | 11/16 | 14/16 | 13/13 | - | 12/15 |
| INQACC (cbsa-inqacc) | 22/23 | - | 7/24 | 3/7 | 5/24 | 9/24 | 11/21 | - | 11/23 |
| UPDACC (cbsa-updacc) | 4/4 | 0/3 | 17/30 | 10/11 | 17/28 | 28/34 | 8/8 | - | 19/21 |
| UPDACC (cbsa-updacc-generated) | 4/4 | 0/3 | 17/30 | 10/11 | 17/28 | 28/34 | 8/8 | - | 19/21 |
| LGAPDB01 (genapp-lgapdb01) | 5/13 | - | 8/23 | 0/2 | 7/21 | 12/23 | 13/23 | 2/10 | 11/22 |
| LGAPVS01 (genapp-lgapvs01) | 14/16 | - | 25/41 | 0/1 | 6/11 | 12/28 | 6/9 | - | 9/19 |
| LGICDB01 (genapp-lgicdb01) | 6/17 | 2/4 | 9/24 | 1/4 | 5/24 | 4/24 | 6/20 | - | 7/23 |
| LGSTSQ (genapp-lgstsq) | 1/5 | - | 1/21 | 0/1 | 5/11 | 10/21 | 5/6 | - | 3/13 |
| LGUPDB01 (genapp-lgupdb01) | 11/12 | - | 11/22 | 0/2 | 5/22 | 12/22 | 14/22 | 3/17 | 12/21 |
| LGUPVS01 (genapp-lgupvs01) | 14/14 | - | 29/44 | 0/1 | 4/10 | 10/31 | 7/10 | - | 2/9 |
| CALINK (ca-link-lengths) | 2/2 | - | 1/4 | 0/1 | 2/4 | 3/3 | 3/3 | 2/2 | 2/3 |
| CASUB (ca-link-lengths) | - | - | 2/5 | - | 3/5 | 4/5 | 4/5 | - | 3/4 |
| CAXA (ca-xctl-versions) | 1/1 | - | 3/4 | - | 3/4 | 2/4 | 4/4 | - | 3/4 |
| CAXB (ca-xctl-versions) | 2/3 | 1/3 | 4/4 | 1/1 | 3/3 | 3/3 | 3/3 | - | 3/3 |
| GTSTART (gt-start-retrieve) | 1/1 | - | 3/4 | 1/1 | 3/4 | 2/2 | 4/4 | 2/2 | 3/4 |
| GTWORK (gt-start-retrieve) | 1/1 | - | 4/4 | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 |
| GTSHOW (gt-terminal-coalesce) | 3/4 | - | 3/4 | 0/1 | 3/3 | 3/4 | 3/4 | - | 2/3 |
| GTTERM (gt-terminal-coalesce) | 1/1 | - | 3/4 | - | 4/4 | 3/4 | 3/3 | 2/2 | 1/3 |
| HCMAIN (hc-abend-link) | 1/3 | - | 2/4 | 2/4 | 2/3 | 3/3 | 2/3 | - | 2/3 |
| HCSUB (hc-abend-link) | 3/3 | - | 3/5 | - | 3/4 | 3/4 | 3/4 | - | 3/4 |
| HCQREAD (hc-perform-range) | 1/1 | - | 0/3 | 1/2 | 3/3 | 2/3 | 3/3 | 1/3 | 3/3 |
| HXATTR (hx-attr-bytes) | 2/2 | - | 4/4 | 1/1 | 0/4 | 4/4 | 4/4 | - | 2/3 |
| HXEXT (hx-extended-cursor) | 2/2 | - | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| PCDETL (pc-aid-menu) | 1/1 | - | 4/5 | 1/2 | 2/4 | 4/4 | 2/4 | - | 1/4 |
| PCMENU (pc-aid-menu) | 4/4 | - | 0/4 | 1/3 | 3/4 | 3/3 | 2/3 | - | 3/3 |
| PCIMMA (pc-return-immediate) | 0/3 | - | 0/4 | - | 1/4 | 3/4 | 2/3 | - | 0/4 |
| PCIMMB (pc-return-immediate) | 1/3 | - | 4/4 | 0/1 | 1/4 | 2/4 | 2/4 | - | 1/3 |
| PCIMML (pc-return-immediate) | 0/3 | - | 3/4 | 0/1 | 3/4 | 1/4 | 2/4 | - | 0/3 |
| PCIMMS (pc-return-immediate) | 0/4 | - | 3/4 | - | 0/4 | 1/4 | 2/4 | - | 2/4 |
| PCCONF (pc-wizard) | 2/3 | 2/2 | 0/3 | 2/3 | 2/3 | 3/3 | 3/3 | - | 1/3 |
| PCWIZ (pc-wizard) | 2/3 | 1/2 | 2/4 | 2/2 | 3/3 | 3/3 | 3/3 | - | 0/3 |
<!-- /mutation-scores -->

Run on gitgalaxy `416fb6420` (2026-10-03): CSUTLDTC all 217 mutants; COMEN01C and COACTVWC 150 each (seed 0);
the 17 crucible ports 24 each (seed 0, cics-crucible v0.2.0). The three batch cases (CBACT04C, CBTRN02C,
CBTRN03C) were not re-run here; their seed-1 raw scores are in the table above this section.

#4047 added six CardDemo CICS ports (signon, tranview, userlist, useradd, userdel, adminmenu; 100 mutants each, seed 0,
`--jobs 3`). Their 73 case gaps repeat across the six: no scenario sets EIBCALEN (`task.eibcalen()` is null), sends a
short COMMAREA, abends the program, answers a failed XCTL, or sends a blank to-program; userlist also lacks a short
last page after a full one. 8 more survivors are unreachable (the program name in `region.run` / `region.linked`).
The 126 equivalent verdicts rest on one assumption not yet independently checked: the COMMAREA/screen DTO codec pads
and truncates each field to its declared width, so a width off by one, or NUL for space, changes no compared byte.

#4049 re-ran adminmenu, useradd, userdel and tranview (100 mutants each, seed 0, `mutation.py run --record`) against the
scenarios #5387 added, and the rows above are now these runs. The four ports were regenerated since `bcb4f6f82`, so the
mutant set moved (COADM01C 334 -> 340 mutants, COTRN01C 308 -> 314, COUSR01C 266 -> 272, COUSR03C 334 -> 340); the old
verdicts were carried to a new survivor only where its operator, file and mutated text matched exactly one old survivor
(60 carried), plus 19 facade `lastLinkBytes` / `region.run` / `region.linked` mutants triaged unreachable as in the other
CardDemo ports. Score before -> after (raw / adjusted): COADM01C 56% / 77% -> 55% / 78%, COTRN01C 63% / 93% -> 66% / 99%,
COUSR01C 66% / 89% -> 61% / 88%, COUSR03C 72% / 89% -> 71% / 87%. The 60 new survivors (COADM01C 23, COTRN01C 17,
COUSR01C 10, COUSR03C 10) were then triaged by reading the port: widths on `fld` / `pad` / `fit`, fills overwritten before
the SEND MAP and dropped NUL/space fields are equivalent; one is unreachable (COADM01C's "not installed" branch); the rest
are new case gaps (commarea fields no scenario populates, the one-digit option, the NOTFND branch of COUSR03C). Of the 37 case gaps the scenarios targeted, 12 are killed (adminmenu
6, tranview 3, userdel 2, useradd 1), 15 still survive (COADM01C's service lines 241, 344, 368, 373 and 374, COUSR01C's
136, 228, 245 and 259, COUSR03C's 200, 206 and 469) and 10 are gone with the code they sat in. Slice 2 (#4049) added 10 scenarios to the four cases (adminmenu 3, useradd 3, userdel 3, tranview 1) and re-judged:
raw score before -> after COADM01C 55% -> 63% (15 -> 7 case gaps), COUSR01C 61% -> 63% (8 -> 6), COUSR03C 71% -> 77%
(9 -> 4), COTRN01C 66% -> 66% (1 -> 1, the round killed nothing, so tranview stops here). 15 more mutants are killed and
18 case gaps remain, with no verdict reasoned yet; the owner's target score is still pending. Stop rule for the
strengthening loop: stop at the target score (owner decision pending) or when a round of proposals kills no survivor,
and record the reason here.

Slice 3 (#4049) judged the last 18 case gaps of the four ports by reading the code, then re-ran them (100 mutants, seed
0). Five are killed by three new inputs: useradd's two `commarea_length` scenarios (EIBCALEN 147 and 150, `49cc911a42`),
adminmenu's `no-commarea-xctl-fails` (a blank COMMAREA reaches the output only on EIBCALEN 0 plus a failed XCTL:
`d64aeec2fa`, `e86bcf12d8`, `04d5116c0f`) and tranview's empty id with a process date (`cf097d68e1`). Twelve are not case
gaps: ten equivalent (dead guards, dead stores, a width the codec truncates, `' '` and `'X'` both reading 0), one
unreachable (useradd `e9539ec3ad` needs a COMMAREA with EIBCALEN 0) and one harness gap (useradd `ccaa395318`: the case now
states `"maps"`, so the COBOL side abends ABM0 on a wrong mapset, but the java-facade run does not compare the mapset a
Java `sendMap` names, so the wrong literal still survives). Raw score COADM01C 63% -> 66%, COTRN01C 66% -> 67%, COUSR01C
63% -> 64%, COUSR03C 77% (unchanged: its four gaps were all dead code). Stop rule met for these four ports: no case gap is
left, and the one open survivor needs a harness change, not a proposal.

#4047 then added seven more CardDemo CICS ports (billpay, cardlist, cardview, report, tranadd, tranlist, userupd; 100
mutants each, seed 0). Their case gaps repeat the six ports': no EIBCALEN, a short or blank COMMAREA, non-blank
COMMAREA fields, a failed XCTL, bad-format amount and date inputs, and rounding with fractional amounts; tranlist's
cases also need `"maps"` in case.json. 31 survivors are unreachable (the facade's byte-carrying handleLink,
lastLinkBytes() and the program name in `region.run` / `region.linked`). cardlist's 16 scenarios are refused by
the oracle (register X8), so its score rests on the others (the 30 of the first 46, 46 since #5401: see the cardlist paragraph below). One harness gap, closed in #5401: cardview (0173a35c74) changes SEND TEXT
options, and the harness compared SEND TEXT by text only; it now compares the forwarded options (ERASE, FREEKB, ALARM,
WAIT, LAST). The score is not re-run. #5401 added `commarea_length` scenarios (EIBCALEN stated, X23): userupd 185 and 186, report 146 and 153, tranlist
`enter-short-commarea` (160 of 218), billpay and tranadd 200 and 201 (of 218, both past the numeric page number). Lengths that cut a numeric field, or leave one blank, are not used: a blank
PIC 9 is IBM-undefined and the oracle and the port read it differently (pf7/pf8 at 160 on tranlist, userupd at 160 to
184, report below 146). All 77 case-gap survivors of the seven ports were judged again against these cases (2026-10-19, `mutation.py run --only`, no re-sample): 19 more are killed (billpay 2, report 3, tranlist 4, userupd 10). The 12 EIBCALEN survivors that remain are re-triaged **unreachable**: EIBCALEN 0 with a COMMAREA present (COBIL00C 57484857ed, COTRN02C f92dd6e996, COUSR02C d0e975d5b4: `commarea_length` is 1 to the record, IBM leaves DFHCOMMAREA unaddressable), a null COMMAREA DTO (COCRDSLC 764873c268), and the lengths that leave a numeric field blank (CORPT00C below 12, 24 and 130, COUSR02C 160, 169, 176 and 184, COTRN00C 3c413ab7f0). Still open: cardview and cardlist: both move `DFHCOMMAREA` past the shared 160 bytes, so the oracle refuses every short length (X23: 159, 160 and 171 on cardview, 159, 160 and 413 on cardlist), and each states only its whole COMMAREA (`full-commarea-length`, 172 and 414 bytes). The "no scenario sets EIBCALEN" item of #5401 is closed: `test_carddemo_eibcalen_scenarios_5401.py` pins that all seven cases state it.

#4628 slice 3 (COADM01C, COBIL00C; the det-port ledger re-run on the same seed): new scenarios `pf4-other-key` and `invalid-key-unread-option-field` (adminmenu), `decline-lowercase-n` and `full-commarea-carried` (billpay) kill 4 mutants. COBIL00C reaches 0 open (9 triaged: 7 equivalent, 2 unreachable). COADM01C keeps 7 open: six are the short-COMMAREA conversion (`exactCommarea`, lines 546, 697, 699), which needs a `commarea_length` scenario the model port cannot take (X23: its DTO holds the whole record and cannot see the cut tail, so such a scenario fails the proof); one is the final RETURN's COMMAREA length (harness-gap: the scenario ends at the RETURN, so EIBCALEN of the next task is not observed). COTRN02C (35 open then) was the remaining slice: see "COTRN02C reaches L5" below.

#4049 slice 2 (COUSR00C, 2026-10-22): the hand port was run as a full enumeration (510 mutants, not the earlier 100-mutant sample), and its 136 first-pass survivors were read one by one. Eight new scenarios (`short-commarea-187`, `enter-lists-with-eleven-left`, `enter-lists-only-the-last-user`, `select-two-rows-first-wins`, `rows-sent-back-pf8-readnext-io-error`, `rows-sent-back-pf7-readprev-io-error`, `pf8-with-low-values-last-id`, `select-row-with-no-id-received`) kill 8 survivors that were true case gaps, and two of them exposed real defects in the hand port, both fixed in this slice: `normalize` kept all of a field the COMMAREA ends inside (COBOL keeps only `EIBCALEN - offset` bytes), and a map field the terminal did not send arrived blank where COBOL has LOW-VALUES. After the final full re-run: 377 killed, 128 survived, 5 stillborn, 0 case gaps; raw 377/505 (75%), adjusted 377/379 (99%). The 128 survivors are 55 equivalent (fixed-width fits, dead stores after the last SEND, bounds a surrounding test already enforces), 71 unreachable (the X23 short-COMMAREA offsets and numeric tests, the ENDBR condition table, facade code no proof runs including the `lastAnswerBytes` assignment, range guards `idx` never leaves) and 2 harness gaps (the `return`s after an XCTL/abend, whose later commands the harness does not observe). Stop rule for the strengthening loop: stop at the target score (owner decision pending) or when a round of proposals kills no survivor. Met for COUSR00C: no case gap is left, and the two open survivors need a harness change, not a scenario. Sibling gaps: the other menu-family cases (see remaining slices on #4049), IOERR has no oracle abend code (`abendOn` defaults to INVREQ), failed-XCTL and blank-id key gaps.

#4049 slice 3 (COUSR00C, 2026-10-23): the failed-XCTL gap slice 2 listed is closed. COUSR00C has three XCTL sites (a `U` selection to COUSR02C, a `D`/`d` selection to COUSR03C, and `RETURN-TO-PREV-SCREEN`, reached by PF3 to COADM01C and, with no COMMAREA, aimed at COSGN00C) and none had a scenario where it answers PGMIDERR (RESP2 3; the source has no RESP, so CICS abends the task). Four scenarios state it (`pf3-xctl-fails`, `select-update-xctl-fails`, `select-delete-xctl-fails`, `no-commarea-xctl-to-signon-fails`), pinned by `test_carddemo_failed_xctl_5401.py`, which now counts the program's XCTL sites in the corpus source. Proof: 59 scenarios equal between GnuCOBOL and the port, 16/16 paragraphs and 95/100 branches (unchanged: the XCTL branches were already covered, the new runs add the abend outcome). The full 510-mutant re-run gives the same score (377 caught, 128 survived, 0 case gaps; raw 75%, adjusted 99%): the scenarios kill no existing survivor, because the `return`s after an XCTL stay the two harness gaps. With the checklist's other named scenarios (short last page, PF7 at top, blank-id selection, ENDBR) already stated, the COUSR00C item is complete. The det-port mutation ledger was re-run (the port had moved on main): the scenarios kill the recorded XCTL-failure case gap (`4e3abb66a8`, dropped from the survivors file); 27 survivors from the port's drift are still unaccounted, open rather than guessed at. Sibling gaps: IOERR has no oracle abend code (`abendOn` defaults to INVREQ), and the blank-id key variants beyond `select-row-with-no-id-received`.

**COMMAREA field survivors** (#5401, 2026-10-20). Three case-gap survivors needed an input COMMAREA field no scenario set, and each is now killed
(`mutation.py run --only`, no re-sample): cardview `enter-carried-to-tranid` (non-blank `CDEMO-TO-TRANID`, echoed by the RETURN COMMAREA, `6d63a520f9`),
tranlist `select-with-carried-to-tranid` (non-blank `CDEMO-TO-TRANID` on a select, so the XCTL COMMAREA shows the ninth FROM-PROGRAM byte spilling over it,
`bdeaa77fbe`) and tranadd `pf3-low-values-from-program` (LOW-VALUES `CDEMO-FROM-PROGRAM`, which COBOL reads as blank, `e31af14845`). GnuCOBOL and the port agree on all
three; the scores are not re-run. `test_carddemo_commarea_fields_5401.py` pins them. billpay `first-entry-with-long-selected-account` (`CDEMO-CB00-TRN-SELECTED` of 12 characters, which the MOVE truncates to 11, `d3458d6107`) is added the same way. cardlist `pf8-next-page-carries-return-flag` (a non-blank `WS-RETURN-FLAG`, `62c41cc4a8`) and `pf3-from-menu-stale-first-card-faulting-carddat` (a menu entry whose
stale first card account id must come back 0 when the first READNEXT faults, `6fef123a15`) need no refused scenario, so the X8 refusals never blocked them: both mutants differ
(`commarea.WS-RETURN-FLAG` 1 vs None, `commarea.WS-CA-FIRST-CARD-ACCT-ID` 0 vs 41), and the case is proven on 33 scenarios, 36/36 paragraphs, 136/149 branches. No survivor of the item is open.

**Cardlist survivors behind the X8 refusals** (#5401, 2026-10-23). The 16 refused scenarios are all ENTERs with nothing selected: COCRDLIC line 518 subscripts `VIEW-REQUESTED-ON(I-SELECTED)` with `I-SELECTED` = 0, and the oracle's `EC-BOUND-SUBSCRIPT` refuses it by name (register X8, an owner decision: no scenario is allowed past the bounds). A PF key skips line 518, so each survivor the refusals left open is stated under one. Of the five cardlist case gaps still open, two were already killed by scenarios added since the score was recorded (`103529adf5` by `pf8-back-from-card-view-keeps-the-selected-ids`, `0e7e448057` by `pf3-from-menu-stale-first-card-faulting-carddat`). Four new scenarios kill the other three: `pf8-with-all-zeros-account-filter` (`1761ccd4aa`, `d9ff5e4dbc`), `pf8-with-all-zeros-card-filter` (`d9ff5e4dbc`), and `pf8-endbr-invreq` / `pf7-endbr-invreq` (`fc564b048f`; the source has no RESP on its ENDBR, so INVREQ abends the task). GnuCOBOL and the port agree on all four. The case is proven on 46 scenarios (36/36 paragraphs, 147/149 branches), and the 100-mutant sample (seed 0) is re-run: 82 caught, 12 survived (all equivalent), 6 stillborn, 0 case gaps; raw 82/94 (87%), adjusted 82/82. The 16 refusals stay: no PF-key form reaches what they would have shown (the ENTER paths themselves, e.g. the empty-selection test of line 518, are unobserved by any proof). `test_carddemo_cardlist_mutation_survivors_5401.py` pins the scenarios.

**Failed XCTL survivors** (#5401, 2026-10-21). A case with an XCTL site had no scenario where the XCTL answers a non-NORMAL condition. The source has no RESP, so
CICS abends the task (PGMIDERR, RESP2 3), the shape billpay, tranadd and cardview already state (`pf3-xctl-fails`). Added: tranlist `select-xctl-fails` (XCTL COTRN01C) and
`pf3-xctl-fails` (XCTL COMEN01C), report `pf3-xctl-fails` (CORPT00C's one XCTL, COMEN01C) and userupd `pf3-saves-then-xctl-fails` (the update saved first, then XCTL COADM01C).
GnuCOBOL and the port agree on all four. tranlist `9e54fb034b` (the `abendOnCondition` after the XCTL, `Cotrn00cService.java:522`) is killed by both tranlist scenarios; the case
is re-judged with `mutation.py run --only` (no re-sample), which also records `bdeaa77fbe` as killed (the score had not been re-run for it): COTRN00C 66/91 killed.
`test_carddemo_failed_xctl_5401.py` pins the four scenarios. cardlist (COCRDLIC) states one per XCTL site (lines 402, 538, 566; #5819), so the item is closed: the test also
counts the XCTL sites in each of the seven sources and requires a faulted-XCTL scenario for each. The cardlist score was re-run in the next paragraph.

**Bad-format amount and date survivors** (#5401, 2026-10-21). COTRN02C validates the amount with four clauses (sign byte, digits 2-9, the point, cents) and each date with
five (year, `-`, month, `-`, day), and the case had one all-bad value per field, which fails the first clause and leaves a mutant of any later one alive. tranadd now
states one scenario per clause with only that byte bad: 6 amount (`amount-bad-sign-good-digits`, first and last digit, point, cents tens and units) and 5 each for the
original and the processing date (`orig-date-*`, `proc-date-*`). report states `custom-end-month-single-digit` (EDTMMI `6`, which NUMVAL-C rebuilds as `06`). GnuCOBOL and the
port agree on all 12: tranadd is proven on 74 scenarios (72/75 branches), report on 30 (52/59). The seven survivors are killed in a re-run of the same sample (seed 0, 100
mutants): tranadd `18030c6651`, `d06e6adeed`, `b72db7485f` (the mutated Java crashes on the amount, so the harness records `java`), `327311d5b9`, `1cee2b8e8a`, `b7fd450d80`, and report
`70523f5c3d`. The scores are not recorded. Left: tranadd `eea78d1ed0` (a character with no cp037 encoding in the amount sign or a date separator; the oracle may not carry it).
`test_carddemo_bad_format_5401.py` pins that each scenario breaks exactly one byte.

**Rounding with fractional amounts** (#5401, 2026-10-21). COTRN02C moves NUMVAL-C of the amount into `S9(9)V99` and the port truncates it (`RoundingMode.DOWN`); every
tranadd amount had cents below .50, so a `HALF_UP` mutant of the integer part could not show. tranadd now states `amount-fraction-above-half` (`+00000123.75`),
`amount-fraction-at-half` (.50), `amount-fraction-nines` (.99) and `amount-negative-fraction-above-half` (`-00000123.75`). GnuCOBOL and the port agree on all four:
tranadd is proven on 78 scenarios (72/75 branches), and the deterministic port on the same 78. In a re-run of the same sample (seed 0, 100 mutants) `35957e9be4` and
`77da652333` are killed; the scores are not recorded. `test_carddemo_fractional_5401.py` pins the cents (below, at and above half) and both signs. Left: report
`d2fca7d77a` (`unsignedDigits`, `HALF_UP`). A fractional date part (`SDTDDI` `.9`) kills it on the model port, but the case is not provable: GnuCOBOL truncates
NUMVAL-C into `PIC 99` (00, the date is refused) while IBM rounds a float-mode store (01, register C6, `RT-HFP-FLOAT-STATEMENT-STORE`), which the deterministic port follows, so the
det sweep of carddemo-report fails on it. The scenario is not committed. The mutant is a real IBM difference, not an equivalent one: the model port's `DOWN` follows the oracle.
billpay `868815f4c6` and `29f0e18174` (a balance of 1,000,000.00 or more) are a different mechanism and stay open.

**Wide balances on billpay** (#5401, 2026-10-22). Every CardDemo account is below 1,000,000.00, so billpay never showed a wide amount or the tenth integer digit
that COBIL00C's MOVE of `ACCT-CURR-BAL` (`S9(10)V99`) into `TRAN-AMT` (`S9(9)V99`) drops. The case appends two synthetic accounts and their card xref rows
(`acctdata-5401.txt`, `cardxref-5401.txt`): `00000099998` at 1,234,567.89 (`pay-balance-over-one-million`) and `00000099997` at 1,234,567,890.12
(`pay-balance-ten-integer-digits`, TRAN-AMT keeps 234,567,890.12). GnuCOBOL and the port agree on both: billpay is proven on 35 scenarios (46/48 branches).
The two survivors that named this gap, `868815f4c6` and `29f0e18174`, were judged on the port before #5844 changed `store()` to count integer digits; their ids no longer exist.
Against the current port the same mutants (`store(.., 9, 3)` at line 542, `store(.., 10, 3)` at 552; ids `84cb7729f6`, `95f2f0cf57`) change only the scale of a
value that the setter writes at scale 2, so they survive the new scenarios and are equivalent, not case gaps. The digit-count mutants the new account does reach:
`d5264128d1` (`store(bal, 10, 2)` at 542) is killed by the ten-integer-digit scenario; `2f50a14acd` (`store(.., 11, 2)` at 552) survives and is unreachable
(balance minus amount is at most 1,000,000,000.00, 10 digits). The scores are not re-run, and `mutation_scores.json` is not edited.
`test_carddemo_wide_balance_5401.py` pins the accounts, the xref rows and the scenarios.

**Mapset on tranlist** (#5401, 2026-10-23). COTRN00C sends and receives map `COTRN0A` of mapset `COTRN00`, and `carddemo-tranlist/case.json` stated no `"maps"`, so the stub
did not check the mapset on the COBOL side. The survivors that named this gap, `31b9d4be47` (the ERASE SEND MAP at line 537) and `16f2ecb581` (the no-ERASE SEND MAP at 539),
were judged before #5862 made the comparator compare the MAPSET of a SEND / RECEIVE MAP: re-run with `mutation.py run --only` (seed 0) against the case as it stood on main
(`--case-file`), both are already killed (`mapset` differs, `COTRN00` against `XOTRN00`), so they were never a case gap any more and the useradd harness gap
(`ccaa395318`) is closed the same way. The case now also states `"maps": {"COTRN0A": {"mapset": "COTRN00"}}`, the form `carddemo-useradd` uses, so a SEND MAP or RECEIVE MAP
for a map its mapset does not hold abends ABM0 on the COBOL side too; tranlist is still proven on 36 scenarios (96/101 branches). The scores are not re-run, and
`mutation_scores.json` is not edited.
`test_carddemo_tranlist_maps_5401.py` pins the stated map and mapset.

#4047 then scored six CardDemo batch ports (readxref, readcust, dailyval, intcalc, posttran, trnrpt; seed 0, up to 100
mutants each, `--jobs 3`, fast mode). These rows are seed 0 and differ from the older seed-1 CBACT04C, CBTRN02C and
CBTRN03C figures above. The case gaps repeat across the six: `displayIoStatus` takes a numeric test on both status bytes,
and the fault plans only run 35, 30, 10, 97 and 9A, so a status such as `3A` or `39` is never shown; the boundary values
(a credit limit equal to the cycle balance, a DATEPARM byte 22) and a balance of ten integer digits are also missing.
dailyval's 15 unreachable survivors sit in the dataset-file fallback and in repository discovery, which the generated
project never needs. Five harness gaps (intcalc 1, posttran 1, trnrpt 3): the harness hands the port an output directory that
already exists, so creating it or truncating the report is not compared. readcard (CBACT02C) is scored in #5402.

What the triage found:

- **One harness gap (SEND TEXT options, COCRDSLC).** Otherwise no survivor changes an output that the proof runs but does not compare. The two found
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
    #4049 (Julian slice): the port had no `DDD` token (it answered `YYYYDDD` as a bad picture string where the model
    answers a date), so a `YYYYDDD` call would have failed the proof. The port now has one and the case gained 18 Julian
    calls (day 000, 365, 366 in leap 2024 / 2000 and non-leap 2023 / 1900, 367, a non-digit in the day and in the year,
    the Lilian boundary 1582 day 287 / 288, 9999 day 365, year 0000, `DDDYYYY`, `YYYY-DDD`), every one on a picture the
    model documents; pictures it does not (a month with DDD, month names, `YY`) stay refused (exit 98). Re-run
    (`mutation.py run carddemo-dateutil --record`, seed 0, all 276 mutants, 659 s): raw / adjusted 74% / 100% -> 76% /
    100%, 145/195 -> 197/260 caught. The 38 new survivors were triaged by reading the port: 0 case gaps (the mutated
    Julian guards all need a repeated token or DDD beside MM / DD, which the oracle refuses; year `<= 1` is the same 2513
    as the Lilian check; the sentinels are equivalent). Stop rule met: no proposal kills a remaining survivor.
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

Re-run 2026-10-05 on gitgalaxy `d69a63419` (after #4343 regenerated the crucible ports' facades): the 13 crucible ports
other than PCCONF, PCWIZ, PCMENU and PCDETL (#4427 changed those; #4443 re-ran them, below), 24 mutants each,
seed 0, cics-crucible v0.2.0. The table rows above are these runs. 205 caught of 291 judged (70%); 86 survivors: 34 case gaps (19 fault-reachable,
which need the fault plan the crucible lacks), 0 harness gaps, 35 equivalent, 17 unreachable, none untriaged.
`mutation_crucible.py` now proves each mutant on the java-ported and the java-facade side: the first run used
java-ported alone, which never runs a facade body (`handleTransaction`, `handleLink`), and four mutants inside one
(CASUB, CAXB, GTSTART, GTWORK) survived for that reason; the java-facade side kills them.

Re-run 2026-10-17 (#4443): the four PC* ports (seed 0, 24 mutants each, strengthened scenarios on). 62 caught of 94
judged: PCDETL 15/9, PCMENU 16/8, PCCONF 15/8, PCWIZ 16/7 (killed/survived; PCCONF and PCWIZ one stillborn each). The 36
first-run survivors included 6 case gaps; four new scenarios (`enter-sends-no-data`, `amount-not-numeric`, `name-erased`, `amount-erased`)
killed 4 of the 6 case gaps; the other two were re-triaged (PCCONF's `to >= 0` is equivalent, its commarea-length
mutant unreachable). 0 case gaps and 0 harness gaps remain: 23 equivalent, 9 unreachable.

Re-run 2026-10-18 (#4443): CAXB's four case gaps against the new strengthened scenario `visits-past-nine` (ten CA03 turns,
so the 80-byte area carries V2-VISITS 0010): 1 of 4 killed (the digit accumulation in `overlayVisits`), CAXB is now 18/5.
The other three were reached by a harness change, not a cics-crucible release: a typed-transid step in a strengthened scenario
may carry `commarea: {"hex", "length"}` (cics_crucible.py `step_commarea`, `seeded_step`), so CA03 is entered directly with
an area of its own and an EIBCALEN of 8, 22 or 80. Three scenarios (`direct-8-byte-area`, `direct-22-byte-area`,
`direct-negative-balance`), their logs derived from the COBOL, killed two of the three (the packed-balance partial overlay and
the negative balance); the third, `* 10000` for `% 10000` on the destination of `overlayVisits`, is equivalent
(WS-V2's V2-VISITS is zero after INITIALIZE, so the destination digits are always 0000). CAXB is now 20/3 with 0 case gaps.
This landed in #5505, so the "needs a cics-crucible CAXA mode" wording in #5490 and #5491 is superseded: no release or pin bump was needed.
Re-checked 2026-10-22 (#5491, XCTL length 21-24): a fresh `mutation_crucible.py run --only ca-xctl-versions/CAXB --sample 24 --seed 0 --strengthened`
gives 20/23 caught, and mutant `496bab0daf` (NEG `k == 0` -> `!(k == 0)`, `CaxbService.java:231`) is `killed`, `killed_by`
`direct-22-byte-area`: the 22-byte area (EIBCALEN 22) is the one that reaches that branch.
Re-checked 2026-10-22 (#5491, negative balance): the same run (20/23 caught, `--seed 0`) has mutant `5b1e4d4e31`
(BDM `unscaled.signum() < 0 ? kept.negate() : kept` -> `kept : kept`, `CaxbService.java:248`) `killed`, `killed_by`
`direct-negative-balance`: its V2-BALANCE of -12345.67 is the one value that takes the negate branch. No CAXA mode was needed.

Spot-check 2026-10-22 (#4443): 22 of the 45 equivalent verdicts on the 13 re-run ports were re-read against the port source; all hold, no new case. The sample and its caveats: [mutation_equivalent_spot_check.md](mutation_equivalent_spot_check.md).

Checked 2026-10-23 (#4443, READ ... INTO LENGTH -> LENGERR, #4436 / #4453): no cics-crucible release carries the scenario yet, so there is no
branch to mutate. v0.9.0 is the latest release and tag. Its only keyed READ ... INTO LENGTH case, `hc-file-unlock` (HCUNLK), reads with
LENGTH(16), the record's own length, and its NOTES say LENGERR (RESP2 10 / 13) "is not provoked". The one burned crucible port near it,
`hc-perform-range` (HCQREAD), reads TS queues. GenApp LGUCVS01 / LGUPVS01 model the LENGTH (X14) but refuse LENGERR on READ UPDATE by name.
What closes the item: a cics-crucible case with a non-UPDATE keyed READ INTO whose LENGTH is below the record's length (RESP LENGERR, RESP2
11, INTO truncated, LENGTH set back to the record's length), a release, the pin bump with its re-baseline, a port, and a mutation run
on that branch that kills a mutant of the truncation or the set-back.

A score is quoted with its case and seed, never alone. Every survivor is triaged as a case gap, a
harness gap, an equivalent mutant (with the reason) or dead code.

## The byte overload's mutants (#4965)

Every region facade has `handleTransaction(.., byte[])`: `lastAnswerBytes = task.returnedBytes();` after the task ran,
and a `lastAnswerBytes()` accessor. The harness and the CICS crucible compare the accessor with the bytes the task's
RETURN passed on. Those bytes exist only for a port that RETURNs through `returnTransid(.., byte[])` (the
deterministic port, #4817). A model-written port RETURNs through the DTO-only form, so `returnedBytes()` is null on
every path: the deleted assignment is an **equivalent** mutant there, whatever the program does with a COMMAREA (PCWIZ,
PCCONF, PCMENU, PCDETL and COMEN01C all RETURN one and none of them carries bytes). The accessor's inverted test dies
on any port that RETURNs with a COMMAREA.

`python tests/tools/mutation_bytes.py run CASE --work DIR [--det-work DETDIR]` proves exactly those two mutants on the
committed port and on the deterministic port. COMEN01C (`carddemo-menu`, RETURN TRANSID with a COMMAREA, 91/91
statements translated), measured 2026-10-13:

| port | deleted assignment | inverted accessor |
|---|---|---|
| committed (model, DTO-only RETURN) | survives: equivalent | killed |
| deterministic (byte-carrying RETURN) | killed | killed |

The crucible's java-facade side now checks the same thing the equivalence harness does: the bytes the accessor answers
are the bytes the task's RETURN passed on (`Arrays.equals(answered, task.returnedBytes())`); before, a null answer fell
back to the DTO's bytes and was never seen. The crucible cannot yet take a deterministic port's bytes: they are in the
runtime's ASCII page and the crucible's expected logs are EBCDIC (a `PC-STEP` of `X'31'` against `X'F1'`), so the
crucible ports stay model-written and the byte path is proven on the equivalence side.

## Det ports: evidence level L5 (#4628)

The evidence ladder's top level (owner decision on #4601) is **L5 = L4 + every surviving mutant of the det port
accounted for**. The scores above are of the committed model / hand ports; L5 is about the port the deterministic
translator writes, so `tests/tools/det_mutation.py` runs `mutation.py` on it:

```sh
python tests/tools/det_mutation.py run CASE... --work DIR --sample 150 --jobs 3   # translate, mutate, record
python tests/tools/det_mutation.py table                     # per program: the PR / report table
python tests/tools/det_mutation.py survivors [CASE]          # every survivor with its stated verdict
python tests/tools/det_mutation.py state CASE TRIAGE.json    # {id: {verdict, reason}} -> the reviewed list
python tests/tools/det_mutation.py check                     # the claims against the ledger
python tests/tools/det_mutation.py refresh --work DIR        # an input moved: same port bytes carry the verdicts (#5862)
```

- **What is mutated.** `det_port.py run --translate-only`'s port, its `service/*.java` only: the translated
  program, never the cobolrt runtime (`test_cobolrt.py` checks that against GnuCOBOL). The entry points the case's
  kind never calls are out of scope (a CICS program's `runProgram` / `runBatch`); everything else the translator
  writes into the service is in: storage images, field declarations, the COMMAREA mapping, the PERFORM machinery,
  condition handling, the paragraphs. The same operators, fast mode and seeded sample (`--sample 150`, seed 0) as
  above; `mutation.py run --port DIR --files GLOB` is the hook.
- **The ledger**, `tests/equivalence/det_mutation/<CASE>.json`, is written only by the tool: per case the counts, every
  judged mutant's verdict, the survivors in full, and the fingerprints of the det port's files, the case, the
  corpus pin, the reviewed survivor list, and the Java generator, harness and oracle. **Fresh (#5862, owner
  2026-10-23)** means the case, the corpus pin and the survivor list match the tree and `refresh` has not found the
  det port's bytes (the generated `.java` files) moved. The generator, harness and
  oracle fingerprints are whole-tree hashes: their drift alone does not stale an entry, it is recorded (`drifted`,
  shown by `describe` and `stale-check`). Because `status` cannot translate, a port that a translator change moved is
  only found when `refresh` runs (the nightly Evidence Refresh lane): it then marks the entry stale (`port_moved`)
  until `run` records the new port. `refresh` re-translates any entry that is stale or drifted and, when the port
  bytes did not change, renews it: info drift only needs no re-run; a case / corpus / survivor-list move re-runs
  only the recorded survivors (same seed, mode and scope) and carries the rest. A survivor that now dies drops out
  (a stated `equivalent` / `unreachable` one is a wrong claim: exit 1); one still surviving with the same Java line
  keeps its stated verdict. Mutants killed before are not re-proven, so a case weakened since would not show. The
  entry records `refreshed` (the earlier date, the survivors re-run, the inputs that moved).
- **The reviewed survivor list**, `tests/equivalence/det_mutation_survivors/<CASE>.json` (the #4602 pattern): each survivor
  stated `equivalent` (the change cannot alter what the program shows) or `unreachable` (no input gets there), with
  the Java change and the reason, proposed in a PR and reviewed by the owner. Two more verdicts record a triaged
  survivor that is NOT accounted for: `case-gap` (an input the case lacks would kill it: strengthen the case) and
  `harness-gap` (the proof runs the difference but does not compare it). A run that kills a stated `equivalent` /
  `unreachable` mutant fails (`record` exits 1, `check` fails): the claim was wrong.
- **L5** for a program: its entry is fresh, nothing is pending or in error, no claim is refuted and every survivor
  of the sample has an accounted-for verdict. The raw score is always printed beside the level.
  `det_mutation.status(case, program)` is the evidence report's hook (#4603); `describe(status)` its one line.
- A sample is a sample: L5 says every survivor **of the 150 judged** is accounted for, at that seed.

**First ledgers (#4628 slice 2, 2026-10-18).** Neither program reaches L5 yet: the `unaccounted` survivors are `case-gap` / `harness-gap`, never loosened to equivalent.

| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / unreachable | unaccounted | raw score | L5 |
|---|---|---|---|---|---|---|---|---|
| COSGN00C (carddemo-signon) | 150/1140 (seed 0) | 70 | 75 | 5 | 70 | 5 | 70/145 (48%) | no |
| UPDCUST (cbsa-updcust) | 150/716 (seed 0) | 68 | 73 | 9 | 41 | 32 | 68/141 (48%) | no |
| COADM01C (carddemo-adminmenu) | 150/1382 (seed 0) | 79 | 66 | 5 | 59 | 7 | 79/145 (54%) | no |
| COBIL00C (carddemo-billpay) | 150/1656 (seed 0) | 95 | 52 | 3 | 52 | 0 | 95/147 (65%) | yes |
| COTRN02C (carddemo-tranadd) | 150/2435 (seed 0) | 90 | 58 | 2 | 23 | 35 | 90/148 (61%) | no |
| COCRDSLC (carddemo-cardview) | 150/2184 (seed 0) | 72 | 74 | 4 | 33 | 41 | 72/146 (49%) | no |
| COTRN01C (carddemo-tranview) | 150/1469 (seed 0) | 91 | 56 | 3 | 53 | 3 | 91/147 (62%) | no |
| COTRN00C (carddemo-tranlist) | 150/2827 (seed 0) | 91 | 57 | 2 | 21 | 36 | 91/148 (61%) | no |

**The crucible now has a byte-path scenario (#4965).** #5053 made the comparison page-aware, so the deterministic port
of PCWIZ (and PCCONF, the program it LINKs/XCTLs to: 39/39 and 47/47 statements, no holes) is committed under
`tests/cics_crucible/det-ports/pc-wizard` (not `ports/`: it is no model port, no provenance; `tests/tools/cics_crucible_det.py`
regenerates it and lays the runtime beside it). `cics_crucible.py --cases pc-wizard --sides java-facade --ports <dir>`
passes 6/6 on it with real `lastAnswerBytes()` (PCWIZ RETURNs TRANSID PC02/PC03 with a 30-byte COMMAREA). Deleting
`lastAnswerBytes = task.returnedBytes();` from it fails 6/6 ("lastAnswerBytes() of PCWIZ is not the bytes its RETURN
passes on"). Measured 2026-10-17; `test_det_port_bytes_4965.py` runs both under `EQUIVALENCE_E2E=1`.

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

**#4628 slice 3 closes (2026-10-21).** COADM01C and COTRN02C each had one `harness-gap` survivor left: the final RETURN's COMMAREA
length (160 -> 161, 218 -> 219). The proof ends at the RETURN and compares no length. Both are stated `equivalent` from the
program's own reads, proposed for owner review: the RETURN re-enters the same program, which uses EIBCALEN only in `IF EIBCALEN = 0`
and in `MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA` (a 160- / 218-byte target truncates the extra byte). Unaccounted
before -> after: COADM01C 1 -> 0, COTRN02C 1 -> 0, COBIL00C 0; all three reach L5 (`det_mutation.py table`). Still open as a sibling
gap: the harness compares no RETURN COMMAREA length for any det port.

**#4628 slice 4 (2026-10-21): COTRN00C reaches L5 with no new scenario.** The committed ledger predated the later `carddemo-tranlist`
scenarios (#5401 and after) and the translator changes since. Re-measured at current main (seed 0, sample 150, fast mode): 148 killed,
0 survived, 2 stillborn, 0 unaccounted. The 21 survivors stated `equivalent` / `unreachable` before are all killed by the current case, so
their claims were refuted and removed from `det_mutation_survivors/carddemo-tranlist.json`, which now lists none. The 36 other survivors of the old
ledger were re-run by id against the current case first: 36 of 36 killed. Slice 4's other programs stay open: COCRDSLC (carddemo-cardview,
41 unaccounted) and COTRN01C (carddemo-tranview, 3 `harness-gap`).

**#4628 slice 5 (2026-10-24, #5862): COTRN02C reaches L5 with no new scenario.** The ledger listed 27 unaccounted survivors after #6232 removed
42 wrong claims (the issue text said one). Each was read against the translated port and `COTRN02C.cbl`; all 27 are stated, none killed: 15 `equivalent`
and 12 `unreachable`. They are harness plumbing the program never reads (it reads only EIBAID and EIBCALEN of the EIB, has no HANDLE, and reads
DFHCOMMAREA only as `DFHCOMMAREA(1:EIBCALEN)`, so the area restored at the end of a terminal task is unobservable), LINK-area code (no CardDemo
program LINKs COTRN02C) and PERFORM bookkeeping (every PERFORM names one paragraph), dead stores and guards behind `SEND-TRNADD-SCREEN`, which
always ends in RETURN (`WS-ERR-FLG` is read only on a fresh task, where it is `N`), the amount's width (the format check bounds it below 10^8)
and the final RETURN's COMMAREA length (218 -> 219, the same reasoning as COADM01C above). All are proposed for owner review. Unaccounted
before -> after: 27 -> 0 (`det_mutation.py table`). Same class, still open: COTRN00C (carddemo-tranlist, 55), CBSTM03A (53), COUSR00C (37),
COSGN00C (5), COUSR03C (1) and the CBSA ports ABNDPROC (34), UPDCUST (32), UPDACC (29), ACCTCTRL (21), GETCOMPY (19) and GETSCODE (19).

**#4628 slice 4 closes (2026-10-21): COCRDSLC and COTRN01C reach L5 with no new scenario.** Both ledgers predated the later scenarios and
translator changes (`det_mutation.py refresh` reported "the det port changed"), so each was re-run from scratch at current main (seed 0,
sample 150, fast mode). COCRDSLC (carddemo-cardview): 146 killed, 0 survived, 4 stillborn (before: 72 killed, 74 survived, 41 unaccounted).
COTRN01C (carddemo-tranview): 147 killed, 0 survived, 3 stillborn (before: 91 killed, 56 survived, 3 `harness-gap`). The 33 + 53 survivors
stated `equivalent` / `unreachable` before were all killed by the current cases, so those claims were refuted and removed from
`det_mutation_survivors/`, which now lists none for either case; the three COTRN01C `harness-gap` survivors are killed too. All three slice-4
programs (with COTRN00C, #5921) are at L5 (`det_mutation.py table`). The score is a seeded sample (150 of 2,184 / 1,469 in scope), not the
whole mutant set.

**#5863 L5 sweep, asynccc estate (2026-10-21): all 10 ports reach L5 with no survivor.** The ten `cics-async-api-credit-card-application-example`
L4 ports had no ledger. Each was run as a full enumeration (`det_mutation.py run ... --sample 0`, seed 0, fast mode, JDK 17), so the
score is every in-scope mutant, not a sample. Every judged mutant was killed by the existing case: 0 survived, 0 timed out, 0 unaccounted, so
no `det_mutation_survivors/` file and no new scenario was needed. The stillborn mutants (do not compile) are
6 per program (18 for CSSTATUS, 50 for SEQPNT and ASYNCPNT).

| program (case) | mutants run / in scope | killed | survived | stillborn | raw score | L5 |
|---|---|---|---|---|---|---|
| GETPOL (asynccc-getpol) | 168/168 | 162 | 0 | 6 | 162/162 (100%) | yes |
| GETSPND (asynccc-getspnd) | 168/168 | 162 | 0 | 6 | 162/162 (100%) | yes |
| UPDCSDB (asynccc-updcsdb) | 189/189 | 183 | 0 | 6 | 183/183 (100%) | yes |
| GETNAME (asynccc-getname) | 208/208 | 202 | 0 | 6 | 202/202 (100%) | yes |
| CRDTCHK (asynccc-crdtchk) | 223/223 | 217 | 0 | 6 | 217/217 (100%) | yes |
| CSSTATS2 (asynccc-csstats2) | 246/246 | 240 | 0 | 6 | 240/240 (100%) | yes |
| CSSTATUS (asynccc-csstatus) | 576/576 | 558 | 0 | 18 | 558/558 (100%) | yes |
| GETADDR (asynccc-getaddr) | 234/234 | 228 | 0 | 6 | 228/228 (100%) | yes |
| SEQPNT (asynccc-seqpnt) | 1889/1889 | 1839 | 0 | 50 | 1839/1839 (100%) | yes |
| ASYNCPNT (asynccc-asyncpnt) | 2042/2042 | 1992 | 0 | 50 | 1992/1992 (100%) | yes |

An earlier default-sample run (150 per port) gave the same result, so the full enumeration confirms it.

**#5856 CBSTM03A (2026-10-22): measured, not yet L5.** The CBSTM03A det batch port (`carddemo-cbstm03a`, with its CBSTM03B callee) had no ledger.
A full enumeration (`det_mutation.py run ... --sample 0`, seed 0, fast mode, JDK 17; 123 min at 3 jobs) judged 3,126 in-scope mutants: 1,039 killed,
2,078 survived, 9 timed out, 55 stillborn (raw score 1,048/3,126, 34%, with the timeouts counted as kills). The ledger is committed with every survivor unaccounted, so the
case is **not L5**. The survivors cluster where the case does not look: roughly 545 sit in the service's base64 initial-image constants (lines 100-600 of
`Cbstm03aService.java`, whose bytes the run overwrites or never reads), and the rest are the paragraphs of a case that covers 23/25 paragraphs and 0/46 branches
(one job, three TRNX rows). Closing it needs scenarios that reach the branches (empty and multi-card XREF, a missing ACCT/CUST key, a TRNX
page break) and a reviewed `equivalent` / `unreachable` list for the image constants; both are follow-ups, not part of this slice.

**#5863 L5 sweep, CBSA estate (2026-10-22): no program reaches L5 yet.** The four `cics-banking-sample-application-cbsa` ports
(GETCOMPY, GETSCODE, ACCTCTRL, UPDACC; ABNDPROC is #4628 slice 6) were run as full enumerations (`det_mutation.py run ... --sample 0`,
seed 0, fast mode, JDK 17), so each score is every in-scope mutant. Unlike asynccc these programs carry a COMMAREA, so the generated
COMMAREA scaffolding (typed DTO in/out, link-area bytes, `exactCommarea`, `commarea_length`) is mutated too, and many of its mutants
survive. GETCOMPY and GETSCODE are triaged in `tests/equivalence/det_mutation_survivors/` (#5863 slice 2): every survivor has a
verdict. 119 each are stated equivalent or unreachable, each with its reason; 32 are open `case-gap` (20) / `harness-gap` (12), by
the same reasoning as `cbsa-updcust`. The cases gained `no-commarea`, `eibcalen-zero`, `eibcalen-short`, `eibcalen-full` and a
caller-value-longer-than-the-field scenario (kills: see the table); a link area longer than the record cannot be
stated (register X10), so the `beyond` mutants are `harness-gap`. ACCTCTRL and UPDACC (Db2) are triaged the same way (#5863 slice 3):
ACCTCTRL gained 7 scenarios (165 -> 184 killed) and 228 of its 308 survivors are stated (160 equivalent, 68 unreachable), 45 open
`case-gap` and 35 open `harness-gap`; UPDACC gained 3 scenarios (293 -> 304 killed) and 256 of its 384 survivors are stated (181
equivalent, 75 unreachable), 77 open `case-gap` and 51 open `harness-gap`. #4049 then gave it six `dto-entry-*` scenarios (the typed
DTO alone, so the link-area bytes cannot overwrite what `in_` maps; one is a failing run whose caller fields are all non-zero): 304 -> 394
killed, every `case-gap` closed (63 of the 77 killed or restated, 9 stated equivalent: a width or null test on a field the program
overwrites, `COMM-SCODE` and `COMM-SUCCESS`), and 29 open `harness-gap`. A scenario with EIBCALEN 98 was tried and the java-facade side
refuses it, so the `caWhole` mutants are `harness-gap` too. Its no-COMMAREA and short-EIBCALEN scenarios are left out: they
fail the java-facade side of the proof, so the cut-COMMAREA path stays a `case-gap`. The open ones are the typed-DTO `in_` / `fill_` paths (the
harness replaces the DTO with the link-area bytes), the `byte[]` COMMAREA entry, `handleLink(request, area)` (no caller LINKs with
LENGTH) and `beyond` (X10).

| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / unreachable | unaccounted | raw score | L5 |
|---|---|---|---|---|---|---|---|---|
| GETCOMPY (cbsa-getcompy) | 220/220 | 60 | 146 | 14 | 127 | 19 | 60/206 (29%) | no |
| GETSCODE (cbsa-getscode) | 227/227 | 67 | 146 | 14 | 127 | 19 | 67/213 (31%) | no |
| ACCTCTRL (cbsa-acctctrl) | 517/517 | 203 | 289 | 25 | 268 | 21 | 203/492 (41%) | no |
| UPDACC (cbsa-updacc) | 713/713 | 394 | 294 | 25 | 265 | 29 | 394/688 (57%) | no |

**#5863 slice 4 (GETCOMPY, typed-DTO entry):** a scenario may state `"dto_entry": true`: the port is given the typed DTO alone, without the link-area bytes that otherwise overwrite every field `in_` maps, and a LINKed port that took the bytes now has the DTO it gave back compared beside them (`commarea.dto.<field>` in `compare_events`). GETCOMPY gained two such scenarios (55 -> 60 killed: the five `fill_` mutants of the DTO write-back). The `in_` mutants still survive and are now stated `equivalent`: the program's one MOVE overwrites the whole field `in_` fills. 19 stay open, all on the `byte[]` COMMAREA entry, `handleLink(request, area)` and `beyond` (X10). ACCTCTRL took the same 10 scenarios in #5863 slice 6 (184 -> 203 killed; 268 of 289 survivors stated, 15 open `case-gap`, 6 open `harness-gap`). UPDACC takes them in the next slice.

**#5863 slice 5 (GETSCODE):** three `dto_entry` scenarios (blank, a caller's digits, letters). 62 -> 67 killed: the `fill_` write-back mutants. The six `in_` mutants are stated `equivalent` (the one MOVE overwrites the whole 6-byte field), `base - 0` is `base + 0`, and the `fill_` in the never-called `out_` helper is `unreachable`. 19 stay open, all on the `byte[]` COMMAREA entry, `handleLink(request, area)` and `beyond` (X10).

The "unaccounted" column includes the open `case-gap` / `harness-gap` rows, which block L5 until a scenario or the harness covers them.

**#4628 slice 5 (2026-10-22): COUSR01C and COUSR02C reach L5; COUSR03C has one open `harness-gap`.** First det-port ledgers for the
three CardDemo user-admin ports (150 mutants each, seed 0, fast mode, JDK 17). New scenarios kill survivors: `header-fields-sent-back`
(COUSR03C: a received TRNNAME), `pf3-returns-to-menu-caller` and `pf5-updates-short-user-id` (COUSR02C, plus the OPS record in its
`usrsec.txt`), and the COUSR01C additions. Every survivor has a stated reason in `det_mutation_survivors/carddemo-user*.json`; the
verdicts are proposals for owner review. The byte[] COMMAREA entry (`cb.length > s_DFHCOMMAREA.bytes.length`,
`cx(task, cb.length)`; 2 / 1 / 3 in useradd / userupd / userdel) is re-stated `unreachable` (follow-up, same reason as COADM01C and COUSR00C: no
CardDemo program LINKs these XCTL-only programs, so the area is always the typed DTO). The one open survivor is COUSR03C's first-entry
`MOVE LOW-VALUES TO COUSR3AO`, whose spaces-versus-low-values difference the proof strips (#4635).

| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / unreachable | unaccounted | raw score | L5 |
|---|---|---|---|---|---|---|---|---|
| COUSR01C (carddemo-useradd) | 150/1214 | 91 | 56 | 3 | 56 | 0 | 91/147 (62%) | yes |
| COUSR02C (carddemo-userupd) | 150/1404 | 96 | 48 | 6 | 48 | 0 | 96/144 (67%) | yes |
| COUSR03C (carddemo-userdel) | 150/1302 | 84 | 58 | 8 | 57 | 1 | 84/142 (59%) | no |

**#4628 slice 6 (2026-10-22): COUSR00C and ABNDPROC measured; neither reaches L5.** First det-port ledgers (150 mutants each, seed 0,
fast mode, JDK 17). COUSR00C: ten new scenarios (`full-commarea-carried`, the `rows-sent-back-*` family that re-enters with a
full page of rows, `select-in-an-empty-row`, `pf7-back-to-the-top-exactly` and others) took the proof to 42 scenarios, 16/16
paragraphs, 95/100 branches, and the survivors to 39 (37 stated, 2 `case-gap`: the XCTL-failure branch needs a CSD without
COUSR02C/COUSR03C, and the first-record branch needs a USRSEC key that sorts below X'40'). Every stated survivor has its reason in
`det_mutation_survivors/carddemo-userlist.json`; the verdicts are proposals for owner review. ABNDPROC is measured, not yet
strengthened: 96 survivors, 62 stated (45 equivalent, 17 unreachable), 30 `harness-gap` and 4 `case-gap` open. One of the
`harness-gap` rows is a real comparison gap: the Java COMMAREA event of a LINKed ABNDPROC carries "CBSAAPPLO" under a mutant that
reads ABND-APPLID as 9 bytes, yet the proof reports 2/2 events equal, because the proof does not compare the DTO copy that
`fill_` stores.

| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / unreachable | unaccounted | raw score | L5 |
|---|---|---|---|---|---|---|---|---|
| COUSR00C (carddemo-userlist) | 150/2828 | 136 | 11 | 3 | 10 | 1 | 136/147 (93%) | no |
| ABNDPROC (cbsa-abndproc) | 150/453 | 45 | 96 | 9 | 62 | 34 | 45/141 (32%) | no |
