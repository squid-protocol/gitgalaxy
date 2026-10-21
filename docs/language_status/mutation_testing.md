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

<!-- mutation-scores -->
| port | harness | mutants run / all | raw score | without equivalent + unreachable | survivors: case gap / harness gap / equivalent / unreachable / untriaged |
|---|---|---|---|---|---|
| COACTVWC (carddemo-acctview) | equivalence | 150/328 | 105/129 (81%) | 105/113 (93%) | 8 / 0 / 16 / 0 / 0 |
| COACTVWC (carddemo-acctview-generated) | equivalence | 150/427 | 109/137 (80%) | 109/109 (100%) | 0 / 0 / 16 / 12 / 0 |
| COADM01C (carddemo-adminmenu) | equivalence | 100/340 | 63/95 (66%) | 63/63 (100%) | 0 / 0 / 29 / 3 / 0 |
| COADM01C (carddemo-adminmenu-generated) | equivalence | 150/340 | 97/145 (67%) | 97/97 (100%) | 0 / 0 / 43 / 5 / 0 |
| COBIL00C (carddemo-billpay) | equivalence | 100/529 | 66/86 (77%) | 66/70 (94%) | 4 / 0 / 12 / 4 / 0 |
| COBIL00C (carddemo-billpay-generated) | equivalence | 150/530 | 104/136 (76%) | 104/104 (100%) | 0 / 0 / 17 / 15 / 0 |
| COCRDLIC (carddemo-cardlist) | equivalence | 100/1034 | 75/94 (80%) | 75/82 (91%) | 7 / 0 / 12 / 0 / 0 |
| COCRDSLC (carddemo-cardview) | equivalence | 100/503 | 60/91 (66%) | 60/65 (92%) | 4 / 1 / 22 / 4 / 0 |
| CBTRN01C (carddemo-dailyval) | equivalence | 100/241 | 63/96 (66%) | 63/71 (89%) | 8 / 0 / 10 / 15 / 0 |
| CSUTLDTC (carddemo-dateutil) | equivalence | 211/211 | 145/195 (74%) | 145/145 (100%) | 0 / 0 / 10 / 40 / 0 |
| CBACT04C (carddemo-intcalc) | equivalence | 100/170 | 70/86 (81%) | 70/77 (91%) | 6 / 1 / 9 / 0 / 0 |
| COMEN01C (carddemo-menu) | equivalence | 150/331 | 86/136 (63%) | 86/93 (92%) | 7 / 0 / 36 / 7 / 0 |
| COMEN01C (carddemo-menu-generated) | equivalence | 150/340 | 87/139 (63%) | 87/88 (99%) | 0 / 1 / 35 / 16 / 0 |
| CBTRN02C (carddemo-posttran) | equivalence | 100/263 | 76/85 (89%) | 76/80 (95%) | 3 / 1 / 5 / 0 / 0 |
| CBACT02C (carddemo-readcard) | equivalence | 91/91 | 69/83 (83%) | 69/73 (95%) | 4 / 0 / 10 / 0 / 0 |
| CBCUS01C (carddemo-readcust) | equivalence | 83/83 | 63/74 (85%) | 63/70 (90%) | 7 / 0 / 4 / 0 / 0 |
| CBACT03C (carddemo-readxref) | equivalence | 90/90 | 69/83 (83%) | 69/77 (90%) | 8 / 0 / 6 / 0 / 0 |
| CORPT00C (carddemo-report) | equivalence | 100/642 | 58/87 (67%) | 58/60 (97%) | 2 / 0 / 16 / 11 / 0 |
| COSGN00C (carddemo-signon) | equivalence | 100/196 | 67/99 (68%) | 67/72 (93%) | 5 / 0 / 25 / 2 / 0 |
| COSGN00C (carddemo-signon-generated) | equivalence | 150/202 | 99/149 (66%) | 99/99 (100%) | 0 / 0 / 42 / 8 / 0 |
| COTRN02C (carddemo-tranadd) | equivalence | 100/770 | 61/91 (67%) | 61/73 (84%) | 12 / 0 / 10 / 8 / 0 |
| COTRN00C (carddemo-tranlist) | equivalence | 100/697 | 66/91 (73%) | 66/79 (84%) | 13 / 0 / 5 / 7 / 0 |
| COTRN01C (carddemo-tranview) | equivalence | 100/314 | 67/100 (67%) | 67/67 (100%) | 0 / 0 / 25 / 8 / 0 |
| COTRN01C (carddemo-tranview-generated) | equivalence | 150/314 | 91/150 (61%) | 91/92 (99%) | 0 / 1 / 48 / 10 / 0 |
| CBTRN03C (carddemo-trnrpt) | equivalence | 100/408 | 68/86 (79%) | 68/79 (86%) | 8 / 3 / 7 / 0 / 0 |
| COUSR01C (carddemo-useradd) | equivalence | 100/272 | 63/98 (64%) | 63/64 (98%) | 0 / 1 / 27 / 7 / 0 |
| COUSR03C (carddemo-userdel) | equivalence | 100/340 | 67/87 (77%) | 67/67 (100%) | 0 / 0 / 17 / 3 / 0 |
| COUSR00C (carddemo-userlist) | equivalence | 100/493 | 69/100 (69%) | 69/92 (75%) | 23 / 0 / 8 / 0 / 0 |
| COUSR02C (carddemo-userupd) | equivalence | 100/481 | 57/82 (70%) | 57/59 (97%) | 2 / 0 / 14 / 9 / 0 |
| INQACC (cbsa-inqacc) | equivalence | 150/470 | 63/131 (48%) | 63/106 (59%) | 43 / 0 / 11 / 14 / 0 |
| UPDACC (cbsa-updacc) | equivalence | 133/133 | 95/133 (71%) | 95/110 (86%) | 15 / 0 / 17 / 6 / 0 |
| LGAPDB01 (genapp-lgapdb01) | equivalence | 150/444 | 58/137 (42%) | 58/129 (45%) | 71 / 0 / 1 / 7 / 0 |
| LGAPVS01 (genapp-lgapvs01) | equivalence | 150/184 | 72/125 (58%) | 72/113 (64%) | 0 / 41 / 1 / 11 / 0 |
| LGICDB01 (genapp-lgicdb01) | equivalence | 150/201 | 51/130 (39%) | 51/107 (48%) | 1 / 55 / 8 / 15 / 0 |
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
| **all equivalence** | | 4497 run | **2738/4103 (67%)** | **2738/3234 (85%)** | 310 / 186 / 584 / 285 / 0 |
| **all estate** | | 5001 run | **3057/4579 (67%)** | **3057/3588 (85%)** | 345 / 186 / 672 / 319 / 0 |

| operator | caught / judged | without equivalent + unreachable |
|---|---|---|
| AOR | 216/272 (79%) | 216/242 (89%) |
| BDM | 25/49 (51%) | 25/28 (89%) |
| CON | 385/903 (43%) | 385/501 (77%) |
| COR | 172/298 (58%) | 172/229 (75%) |
| DEL | 485/737 (66%) | 485/570 (85%) |
| LIT | 640/873 (73%) | 640/723 (89%) |
| NEG | 573/654 (88%) | 573/621 (92%) |
| RET | 56/105 (53%) | 56/93 (60%) |
| ROR | 505/688 (73%) | 505/581 (87%) |

| port | AOR | BDM | CON | COR | DEL | LIT | NEG | RET | ROR |
|---|---|---|---|---|---|---|---|---|---|
| COACTVWC (carddemo-acctview) | 3/3 | 0/1 | 11/24 | 8/9 | 19/23 | 20/23 | 22/23 | - | 22/23 |
| COACTVWC (carddemo-acctview-generated) | 6/9 | 0/1 | 14/22 | 17/21 | 16/21 | 16/21 | 20/21 | - | 20/21 |
| COADM01C (carddemo-adminmenu) | 8/8 | - | 2/14 | 6/8 | 8/16 | 7/15 | 15/15 | 4/4 | 13/15 |
| COADM01C (carddemo-adminmenu-generated) | 8/8 | - | 4/24 | 6/8 | 14/26 | 14/25 | 25/25 | 4/4 | 22/25 |
| COBIL00C (carddemo-billpay) | 4/5 | 1/3 | 5/13 | 9/12 | 10/12 | 12/13 | 12/13 | 2/2 | 11/13 |
| COBIL00C (carddemo-billpay-generated) | 5/6 | 1/3 | 9/23 | 9/12 | 17/22 | 21/23 | 22/23 | 2/2 | 18/22 |
| COCRDLIC (carddemo-cardlist) | 8/8 | - | 8/13 | 10/13 | 7/13 | 12/13 | 13/13 | 6/9 | 11/12 |
| COCRDSLC (carddemo-cardview) | 4/5 | - | 3/14 | 10/14 | 6/14 | 9/14 | 13/14 | 2/2 | 13/14 |
| CBTRN01C (carddemo-dailyval) | 3/6 | - | 11/16 | 3/12 | 9/15 | 12/16 | 12/16 | - | 13/15 |
| CSUTLDTC (carddemo-dateutil) | 13/15 | - | 28/51 | 4/8 | 9/10 | 27/35 | 31/32 | - | 33/44 |
| CBACT04C (carddemo-intcalc) | 3/4 | 4/6 | 13/21 | 1/2 | 13/17 | 20/20 | 10/10 | - | 6/6 |
| COMEN01C (carddemo-menu) | 13/14 | - | 7/20 | 6/9 | 14/22 | 15/24 | 16/23 | - | 15/24 |
| COMEN01C (carddemo-menu-generated) | 13/14 | - | 6/21 | 6/10 | 20/24 | 12/24 | 16/23 | - | 14/23 |
| CBTRN02C (carddemo-posttran) | 6/6 | 6/8 | 14/15 | 2/4 | 10/11 | 13/14 | 13/13 | - | 12/14 |
| CBACT02C (carddemo-readcard) | - | - | 17/23 | 1/3 | 9/11 | 22/25 | 12/12 | - | 8/9 |
| CBCUS01C (carddemo-readcust) | - | - | 12/13 | 1/4 | 8/8 | 23/27 | 10/10 | - | 9/12 |
| CBACT03C (carddemo-readxref) | - | - | 16/19 | 1/4 | 9/9 | 22/27 | 10/10 | - | 11/14 |
| CORPT00C (carddemo-report) | 3/3 | 0/1 | 1/11 | 10/13 | 6/13 | 12/13 | 13/13 | 4/7 | 9/13 |
| COSGN00C (carddemo-signon) | 2/2 | - | 3/20 | 3/4 | 12/20 | 18/20 | 15/16 | - | 14/17 |
| COSGN00C (carddemo-signon-generated) | 2/2 | - | 6/36 | 4/5 | 23/36 | 31/35 | 16/16 | - | 17/19 |
| COTRN02C (carddemo-tranadd) | 7/7 | 3/7 | 1/12 | 5/12 | 8/12 | 11/12 | 11/11 | 4/7 | 11/11 |
| COTRN00C (carddemo-tranlist) | 6/9 | - | 10/14 | 8/14 | 11/13 | 10/14 | 11/11 | 2/3 | 8/13 |
| COTRN01C (carddemo-tranview) | 1/1 | - | 2/24 | 2/3 | 21/24 | 19/24 | 17/17 | - | 5/7 |
| COTRN01C (carddemo-tranview-generated) | 1/1 | - | 3/43 | 2/3 | 33/43 | 30/36 | 17/17 | - | 5/7 |
| CBTRN03C (carddemo-trnrpt) | 2/2 | 5/7 | 9/14 | 1/7 | 14/14 | 13/14 | 12/14 | - | 12/14 |
| COUSR01C (carddemo-useradd) | 1/1 | - | 1/21 | 3/6 | 16/20 | 16/20 | 10/10 | - | 16/20 |
| COUSR03C (carddemo-userdel) | 0/1 | - | 6/17 | 2/4 | 14/17 | 14/16 | 16/16 | - | 15/16 |
| COUSR00C (carddemo-userlist) | 9/11 | - | 5/15 | 8/15 | 10/15 | 13/15 | 14/15 | - | 10/14 |
| COUSR02C (carddemo-userupd) | 1/1 | - | 3/16 | 3/5 | 11/16 | 14/16 | 13/13 | - | 12/15 |
| INQACC (cbsa-inqacc) | 3/3 | 1/2 | 4/21 | 2/5 | 10/21 | 6/21 | 14/21 | 8/16 | 15/21 |
| UPDACC (cbsa-updacc) | 4/4 | 0/3 | 17/30 | 3/10 | 16/27 | 28/32 | 8/8 | - | 19/19 |
| LGAPDB01 (genapp-lgapdb01) | 5/13 | - | 8/23 | 0/2 | 7/21 | 12/23 | 13/23 | 2/10 | 11/22 |
| LGAPVS01 (genapp-lgapvs01) | 14/16 | - | 25/41 | 0/1 | 6/11 | 12/28 | 6/9 | - | 9/19 |
| LGICDB01 (genapp-lgicdb01) | 2/5 | - | 9/28 | 1/5 | 6/20 | 14/27 | 9/16 | 1/7 | 9/22 |
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
lastLinkBytes() and the program name in `region.run` / `region.linked`). cardlist's 16 of 46 scenarios are refused by
the oracle (register X8), so its score rests on the other 30. One harness gap, closed in #5401: cardview (0173a35c74) changes SEND TEXT
options, and the harness compared SEND TEXT by text only; it now compares the forwarded options (ERASE, FREEKB, ALARM,
WAIT, LAST). The score is not re-run. #5401 added `commarea_length` scenarios (EIBCALEN stated, X23): userupd 185 and 186, report 146 and 153, tranlist
`enter-short-commarea` (160 of 218), billpay and tranadd 200 and 201 (of 218, both past the numeric page number). Lengths that cut a numeric field, or leave one blank, are not used: a blank
PIC 9 is IBM-undefined and the oracle and the port read it differently (pf7/pf8 at 160 on tranlist, userupd at 160 to
184, report below 146). All 77 case-gap survivors of the seven ports were judged again against these cases (2026-10-19, `mutation.py run --only`, no re-sample): 19 more are killed (billpay 2, report 3, tranlist 4, userupd 10). The 12 EIBCALEN survivors that remain are re-triaged **unreachable**: EIBCALEN 0 with a COMMAREA present (COBIL00C 57484857ed, COTRN02C f92dd6e996, COUSR02C d0e975d5b4: `commarea_length` is 1 to the record, IBM leaves DFHCOMMAREA unaddressable), a null COMMAREA DTO (COCRDSLC 764873c268), and the lengths that leave a numeric field blank (CORPT00C below 12, 24 and 130, COUSR02C 160, 169, 176 and 184, COTRN00C 3c413ab7f0). Still open: cardview and cardlist: both move `DFHCOMMAREA` past the shared 160 bytes, so the oracle refuses every short length (X23: 159, 160 and 171 on cardview, 159, 160 and 413 on cardlist), and each states only its whole COMMAREA (`full-commarea-length`, 172 and 414 bytes). The "no scenario sets EIBCALEN" item of #5401 is closed: `test_carddemo_eibcalen_scenarios_5401.py` pins that all seven cases state it.

#4628 slice 3 (COADM01C, COBIL00C; the det-port ledger re-run on the same seed): new scenarios `pf4-other-key` and `invalid-key-unread-option-field` (adminmenu), `decline-lowercase-n` and `full-commarea-carried` (billpay) kill 4 mutants. COBIL00C reaches 0 open (9 triaged: 7 equivalent, 2 unreachable). COADM01C keeps 7 open: six are the short-COMMAREA conversion (`exactCommarea`, lines 546, 697, 699), which needs a `commarea_length` scenario the model port cannot take (X23: its DTO holds the whole record and cannot see the cut tail, so such a scenario fails the proof); one is the final RETURN's COMMAREA length (harness-gap: the scenario ends at the RETURN, so EIBCALEN of the next task is not observed). COTRN02C (35 open) is the remaining slice.

**COMMAREA field survivors** (#5401, 2026-10-20). Three case-gap survivors needed an input COMMAREA field no scenario set, and each is now killed
(`mutation.py run --only`, no re-sample): cardview `enter-carried-to-tranid` (non-blank `CDEMO-TO-TRANID`, echoed by the RETURN COMMAREA, `6d63a520f9`),
tranlist `select-with-carried-to-tranid` (non-blank `CDEMO-TO-TRANID` on a select, so the XCTL COMMAREA shows the ninth FROM-PROGRAM byte spilling over it,
`bdeaa77fbe`) and tranadd `pf3-low-values-from-program` (LOW-VALUES `CDEMO-FROM-PROGRAM`, which COBOL reads as blank, `e31af14845`). GnuCOBOL and the port agree on all
three; the scores are not re-run. `test_carddemo_commarea_fields_5401.py` pins them. billpay `first-entry-with-long-selected-account` (`CDEMO-CB00-TRN-SELECTED` of 12 characters, which the MOVE truncates to 11, `d3458d6107`) is added the same way. cardlist `pf8-next-page-carries-return-flag` (a non-blank `WS-RETURN-FLAG`, `62c41cc4a8`) and `pf3-from-menu-stale-first-card-faulting-carddat` (a menu entry whose
stale first card account id must come back 0 when the first READNEXT faults, `6fef123a15`) need no refused scenario, so the X8 refusals never blocked them: both mutants differ
(`commarea.WS-RETURN-FLAG` 1 vs None, `commarea.WS-CA-FIRST-CARD-ACCT-ID` 0 vs 41), and the case is proven on 33 scenarios, 36/36 paragraphs, 136/149 branches. No survivor of the item is open.

**Failed XCTL survivors** (#5401, 2026-10-21). A case with an XCTL site had no scenario where the XCTL answers a non-NORMAL condition. The source has no RESP, so
CICS abends the task (PGMIDERR, RESP2 3), the shape billpay, tranadd and cardview already state (`pf3-xctl-fails`). Added: tranlist `select-xctl-fails` (XCTL COTRN01C) and
`pf3-xctl-fails` (XCTL COMEN01C), report `pf3-xctl-fails` (CORPT00C's one XCTL, COMEN01C) and userupd `pf3-saves-then-xctl-fails` (the update saved first, then XCTL COADM01C).
GnuCOBOL and the port agree on all four. tranlist `9e54fb034b` (the `abendOnCondition` after the XCTL, `Cotrn00cService.java:522`) is killed by both tranlist scenarios; the case
is re-judged with `mutation.py run --only` (no re-sample), which also records `bdeaa77fbe` as killed (the score had not been re-run for it): COTRN00C 66/91 killed.
`test_carddemo_failed_xctl_5401.py` pins the four scenarios. cardlist (COCRDLIC) states one per XCTL site (lines 402, 538, 566; #5819), so the item is closed: the test also
counts the XCTL sites in each of the seven sources and requires a faulted-XCTL scenario for each. The cardlist score is not re-run (16 of its 46 scenarios are refused by the oracle, X8).

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
python tests/tools/det_mutation.py refresh --work DIR        # the generator moved: same port bytes renew the entry
```

- **What is mutated.** `det_port.py run --translate-only`'s port, its `service/*.java` only: the translated
  program, never the cobolrt runtime (`test_cobolrt.py` checks that against GnuCOBOL). The entry points the case's
  kind never calls are out of scope (a CICS program's `runProgram` / `runBatch`); everything else the translator
  writes into the service is in: storage images, field declarations, the COMMAREA mapping, the PERFORM machinery,
  condition handling, the paragraphs. The same operators, fast mode and seeded sample (`--sample 150`, seed 0) as
  above; `mutation.py run --port DIR --files GLOB` is the hook.
- **The ledger**, `tests/equivalence/det_mutation/<CASE>.json`, is written only by the tool: per case the counts, every
  judged mutant's verdict, the survivors in full, and the fingerprints of the det port's files, the case, the
  corpus pin, the harness, the oracle and the Java generator (the stand-in for the port a reader can check without
  translating). Any fingerprint that moved makes the entry unknown; `refresh` re-translates and renews an entry whose
  port bytes did not change.
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
