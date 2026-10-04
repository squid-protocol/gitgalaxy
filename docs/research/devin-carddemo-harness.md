# Devin's CardDemo ports through our equivalence harness

*Phase 2 of the Devin benchmark (phase 1: [`devin-carddemo-survey.md`](devin-carddemo-survey.md)). Run 2026-10-02 with `tests/tools/devin_port.py`. **Partial:** this covers item 1 of the plan, the two `eval/` arms on CBACT04C and CBTRN02C. CBACT01C across all its ports (item 2) is deferred; it needs a new case and a model of the assembler routine COBDATFT.*

## What was run

The two `eval/` branches are one controlled experiment: the same Devin task, with and without AWS Transform's analysis of the code. Both port CBACT01C, CBACT04C and CBTRN02C to plain Java 21 and report `19/19 files match` against their own golden harness, over 4 scenarios.

| Arm | Branch @ commit | Given |
|---|---|---|
| A | `eval/devin-arm-a-raw-cobol` @ `19dd9f2` | the COBOL sources, copybooks, JCL and a golden-output harness |
| B | `eval/devin-arm-b-cobol-plus-atx-analysis` @ `ef9aa4f` | the same, plus AWS Transform's analysis of the code |

We ran each arm's CBACT04C on our case `carddemo-intcalc`, and its CBTRN02C on `carddemo-posttran`. Both cases are proven for our own det and model ports.

**The judge** is the harness's normal comparison, `equivalence.compare_run`, against what GnuCOBOL produced from the same inputs: RETURN-CODE or ABEND, every compared data set field by field per its copybook (decimals exact, other bytes byte for byte), and SYSOUT line by line.

**Under every JVM environment.** Each run repeats under the 6 JVM environments the harness proves our ports under (#3821): default (en-US/UTC), turkish, arabic, thai, german and hindi. Each sets the JVM default locale and time zone.

**The adapter.** It is `tests/tools/devin_port.py` and `tests/tools/devin/adapter`; nothing of theirs is changed or committed. It:
- passes each input data set as the fixed-length records GnuCOBOL reads (a KSDS in key order), bound to the port's own `--dd NAME=path` options;
- passes the case's JCL PARM through `--parm`, and its frozen clock through `--now`, in each arm's own format;
- sets the locale and time zone (`EnvLauncher`), then calls the arm's unmodified main class: `carddemo.batch.Main` for A, `carddemo.Main` for B;
- reads an abend the way each arm reports it: A prints `CEE3ABD: USER ABEND U999`, and B exits with status 999 & 0xFF.

No base run abended, so the abend mapping was never exercised here.

**Not applied: the cases' fault runs** (19 for intcalc, 28 for posttran). They inject FILE STATUS values at the program's own I/O statements through the I/O layer our ports call. These ports have their own I/O code and no such hook, and adding one would mean changing their code. So each arm is judged on the case's **base run only**. That run covers:

| Case | Base run covers | With the fault runs (our ports' proof) |
|---|---|---|
| intcalc (CBACT04C) | 20/22 paragraphs, 49/86 branches | 22/22, 85/86 |
| posttran (CBTRN02C) | 24/26 paragraphs, 55/96 branches | 26/26, 95/96 |

## Results

| Arm | Program on case | default | turkish | german | hindi | arabic | thai |
|---|---|---|---|---|---|---|---|
| A | CBACT04C on intcalc | equal | equal | equal | equal | **differs** | **differs** |
| A | CBTRN02C on posttran | equal | equal | equal | equal | **differs** | **differs** |
| B | CBACT04C on intcalc | equal | equal | equal | equal | **differs** | **differs** |
| B | CBTRN02C on posttran | equal | equal | equal | equal | equal | equal |

**In the default environment, both arms match GnuCOBOL on both programs:**
- intcalc: ACCTFILE 52/52 records, TRANSACT 53/53, SYSOUT 156/156 lines, RETURN-CODE 0;
- posttran: ACCTFILE 50/50, TCATBALF 100/100, TRANFILE 264/264, DALYREJS 41/41, SYSOUT 54/54, RETURN-CODE 4.

That is a stronger result than their own 4-scenario harness gives. The cases' input data include the extreme and rounding records added by our test-strengthening loop (#4049): ±999,999,999.99 balances, half-cent interest, and zero rates. So it holds beyond the scenarios the arms were written against.

**Under the Arabic and Thai locales, three of the four ports differ.** Every TRAN-ID and timestamp ends in `??????`:

| Arm | Case | Data set | Record 1, field | COBOL | Java |
|---|---|---|---|---|---|
| A | intcalc | TRANSACT | TRAN-ID | `2022071800000001` | `2022071800??????` |
| A | posttran | TRANFILE | TRAN-PROC-TS | `2022-07-18-10.30.15.000000` | `2022-07-18-10.30.15.??????` |
| B | intcalc | TRANSACT | TRAN-ID | `2022071800000001` | `2022071800??????` |

**Root cause: `String.format` without an explicit locale.** It formats digits in the JVM's default locale, so under `ar-EG` it writes Arabic-Indic digits and under `th-TH-u-nu-thai` Thai digits. Neither can be written in the record's single-byte encoding, so each becomes `?`. The calls:
- **Arm A:** `BatchContext.java:45` writes the timestamps' microseconds: `String.format("%06d", hundredths)`. `Cbact04c.java:156` writes TRAN-ID: `String.format("%06d", tranIdSuffix)`. `Cbtrn02c.java:119-120` writes the two SYSOUT counts (`%09d`), which is why posttran's SYSOUT also differs on 2 of its 54 lines. `Cbtrn02c.java:42` writes the reject reason (`%04d`), which is why DALYREJS differs on all 41 records.
- **Arm B:** `Cbact04c.java:67` writes TRAN-ID: `String.format("%06d", suffix)`. Arm B builds its posttran timestamps without `String.format`, so its CBTRN02C is equal in every environment.

**The fix in either arm is one argument**, `String.format(Locale.ROOT, ...)`. Our own ports are held to the same rule: the harness proves them in these environments, so a port that formats in the default locale does not prove.

## With and without AWS Transform

On these two programs the arms are indistinguishable in the default environment: both match.

The only difference is the locale defect: arm A has it in both programs, arm B only in CBACT04C. That is one formatting call in two code bases, not evidence about AWS Transform's analysis either way. The arms' own report of 4 scenarios each, and ours of one base run times six environments, are both too few for that question.

## Caveats

- **Base run only.** Each arm was judged on one base run per case, under six environments. It covers 49/86 and 55/96 of the COBOL's branches; our ports' proofs, with fault runs, cover 85/86 and 95/96. Error-path behaviour, which is mostly what the fault runs exercise, was not compared.
- **Our reference is GnuCOBOL with a CICS and file model, not z/OS**: see [`oracle_assumptions.md`](../language_status/oracle_assumptions.md). The arms' own golden harness was GnuCOBOL too. Our SYSOUT models IBM's DISPLAY text (C8), and both arms' SYSOUT matched it on these two programs.
- **Builds:** both arms target Java 21 and were built with a portable Temurin 21 (`mvn package`, tests skipped). Nothing in their code was changed.

## Still to do (item 2, deferred)

- A CBACT01C case, with a model of COBDATFT from its assembler source (`app/asm/COBDATFT.asm`), declared in the oracle register.
- The nine byte-comparable CBACT01C ports: six that write packed fields, #229, and these two arms.
- The fixed-width text ports, field by field after decoding.

Work in progress is on the branch `wip/devin-cbact01c-cobdatft`.
