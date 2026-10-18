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
| COACTVWC (carddemo-acctview) | equivalence | 150/328 | 105/129 (81%) | 105/113 (93%) | 8 / 0 / 16 / 0 / 0 |
| COADM01C (carddemo-adminmenu) | equivalence | 100/334 | 53/95 (56%) | 53/69 (77%) | 16 / 0 / 26 / 0 / 0 |
| COBIL00C (carddemo-billpay) | equivalence | 100/529 | 64/86 (74%) | 64/71 (90%) | 7 / 0 / 12 / 3 / 0 |
| COCRDLIC (carddemo-cardlist) | equivalence | 100/1034 | 75/94 (80%) | 75/82 (91%) | 7 / 0 / 12 / 0 / 0 |
| COCRDSLC (carddemo-cardview) | equivalence | 100/503 | 60/91 (66%) | 60/66 (91%) | 5 / 1 / 22 / 3 / 0 |
| CSUTLDTC (carddemo-dateutil) | equivalence | 211/211 | 145/195 (74%) | 145/145 (100%) | 0 / 0 / 10 / 40 / 0 |
| COMEN01C (carddemo-menu) | equivalence | 150/331 | 86/136 (63%) | 86/93 (92%) | 7 / 0 / 36 / 7 / 0 |
| CORPT00C (carddemo-report) | equivalence | 100/642 | 55/87 (63%) | 55/63 (87%) | 8 / 0 / 16 / 8 / 0 |
| COSGN00C (carddemo-signon) | equivalence | 100/196 | 67/99 (68%) | 67/72 (93%) | 5 / 0 / 25 / 2 / 0 |
| COTRN02C (carddemo-tranadd) | equivalence | 100/770 | 61/91 (67%) | 61/74 (82%) | 13 / 0 / 10 / 7 / 0 |
| COTRN00C (carddemo-tranlist) | equivalence | 100/697 | 60/91 (66%) | 60/80 (75%) | 20 / 0 / 5 / 6 / 0 |
| COTRN01C (carddemo-tranview) | equivalence | 100/308 | 63/100 (63%) | 63/68 (93%) | 5 / 0 / 29 / 3 / 0 |
| COUSR01C (carddemo-useradd) | equivalence | 100/266 | 64/97 (66%) | 64/72 (89%) | 8 / 0 / 23 / 2 / 0 |
| COUSR03C (carddemo-userdel) | equivalence | 100/334 | 62/86 (72%) | 62/70 (89%) | 8 / 0 / 15 / 1 / 0 |
| COUSR00C (carddemo-userlist) | equivalence | 100/493 | 69/100 (69%) | 69/92 (75%) | 23 / 0 / 8 / 0 / 0 |
| COUSR02C (carddemo-userupd) | equivalence | 100/481 | 47/82 (57%) | 47/64 (73%) | 17 / 0 / 14 / 4 / 0 |
| INQACC (cbsa-inqacc) | equivalence | 150/464 | 131/131 (100%) | 131/131 (100%) | 0 / 0 / 0 / 0 / 0 |
| UPDACC (cbsa-updacc) | equivalence | 133/133 | 95/133 (71%) | 95/133 (71%) | 38 / 0 / 0 / 0 / 0 |
| LGAPVS01 (genapp-lgapvs01) | equivalence | 150/178 | 70/121 (58%) | 70/119 (59%) | 49 / 0 / 0 / 2 / 0 |
| LGICDB01 (genapp-lgicdb01) | equivalence | 150/195 | 49/130 (38%) | 49/127 (39%) | 78 / 0 / 0 / 3 / 0 |
| LGUPDB01 (genapp-lgupdb01) | equivalence | 150/397 | 76/138 (55%) | 76/137 (55%) | 61 / 0 / 0 / 1 / 0 |
| CALINK (ca-link-lengths) | crucible | 24/168 | 15/22 (68%) | 15/15 (100%) | 0 / 0 / 5 / 2 / 0 |
| CASUB (ca-link-lengths) | crucible | 24/40 | 16/24 (67%) | 16/16 (100%) | 0 / 0 / 7 / 1 / 0 |
| CAXA (ca-xctl-versions) | crucible | 24/78 | 16/21 (76%) | 16/16 (100%) | 0 / 0 / 3 / 2 / 0 |
| CAXB (ca-xctl-versions) | crucible | 24/142 | 17/23 (74%) | 17/21 (81%) | 4 / 0 / 1 / 1 / 0 |
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
| **all crucible** | | 504 run | **316/476 (66%)** | **316/355 (89%)** | 39 / 0 / 87 / 34 / 0 |
| **all equivalence** | | 2544 run | **1557/2312 (67%)** | **1557/1941 (80%)** | 383 / 1 / 279 / 92 / 0 |
| **all estate** | | 3048 run | **1873/2788 (67%)** | **1873/2296 (82%)** | 422 / 1 / 366 / 126 / 0 |

| operator | caught / judged | without equivalent + unreachable |
|---|---|---|
| AOR | 143/180 (79%) | 143/160 (89%) |
| BDM | 9/24 (38%) | 9/16 (56%) |
| CON | 228/533 (43%) | 228/316 (72%) |
| COR | 119/191 (62%) | 119/162 (73%) |
| DEL | 273/436 (63%) | 273/360 (76%) |
| LIT | 376/496 (76%) | 376/432 (87%) |
| NEG | 354/405 (87%) | 354/387 (91%) |
| RET | 56/89 (63%) | 56/79 (71%) |
| ROR | 315/434 (73%) | 315/384 (82%) |
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

#4047 then added seven more CardDemo CICS ports (billpay, cardlist, cardview, report, tranadd, tranlist, userupd; 100
mutants each, seed 0). Their case gaps repeat the six ports': no EIBCALEN, a short or blank COMMAREA, non-blank
COMMAREA fields, a failed XCTL, bad-format amount and date inputs, and rounding with fractional amounts; tranlist's
cases also need `"maps"` in case.json. 31 survivors are unreachable (the facade's byte-carrying handleLink,
lastLinkBytes() and the program name in `region.run` / `region.linked`). cardlist's 16 of 46 scenarios are refused by
the oracle (register X8), so its score rests on the other 30. One harness gap: cardview (0173a35c74) changes SEND TEXT
options, and the equivalence harness compares SEND TEXT by text only.

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
