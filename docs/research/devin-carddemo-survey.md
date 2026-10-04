---
description: "*Phase 1 of a benchmark. We read, built and scanned these ports; none has been run through our equivalence harness yet. Surveyed 2026-10-02.*"
---
# Devin's CardDemo ports: a survey before benchmarking

*Phase 1 of a benchmark. We read, built and scanned these ports; none has been run through our equivalence harness yet. Surveyed 2026-10-02.*

## What this is

Two public workshop repositories hold dozens of COBOL→Java ports of AWS CardDemo written by Devin, Cognition's coding agent:
- [Cognition-Partner-Workshops/uc-legacy-modernization-cobol-to-java](https://github.com/Cognition-Partner-Workshops/uc-legacy-modernization-cobol-to-java)
- [codev-workshops/uc-legacy-modernization-cobol-to-java](https://github.com/codev-workshops/uc-legacy-modernization-cobol-to-java)

Both are Apache-2.0, and both describe the lab as *"Migrate COBOL batch programs to Java 17+ with parity tests"*. Main holds only CardDemo itself; each run's Java sits on its own branch, mostly with an open or closed PR. All 240 PRs in the first repository, and 14 of the 17 in the second, were opened by the Devin integration, between March and September 2026.

These are workshop exercises. Many sessions were deliberately partial, or asked for a re-imagining rather than a port, so we judge each one against what it set out to do. The full per-branch record, with commit SHAs, is in [`devin-carddemo-inventory.json`](devin-carddemo-inventory.json). We pin each branch by commit and do not vendor its code.

This survey belongs with the LGACDB01 comparison in [`lgacdb01-four-way.md`](lgacdb01-four-way.md). The question is the same, with many more data points: *other tools translated the programs we translated, so how do the results compare?*

## 1. Inventory

**67 branches contain Java**: 63 in the Cognition repository and 4 in the codev one.

| Style | Branches |
|---|---|
| Plain Java port of one or a few batch programs | 38 |
| Spring Boot app re-imagining CardDemo (REST, JPA, often a React front end) | 24 |
| Spring Boot microservices | 3 |
| Spring Batch | 1 |
| Not CardDemo (a SuiteCRM migration on the same repo) | 1 |

**Programs, by number of branches that port or substantially address them** (a branch can cover several):

| Program | Branches | Notes |
|---|---|---|
| CBACT01C (account file reader) | 33 | The lab's main target. 28 are distinct port attempts. |
| CBACT04C (interest calculation) | 14 | Mostly inside larger apps. Two plain ports: the eval arms. |
| CBTRN02C (transaction posting) | 13 | The same pattern as CBACT04C. |
| CBSTM03A/B (statements) | 11 / 4 | One GnuCOBOL-referenced parity port (#235). |
| Online CICS programs (COSGN00C, COUSR0xC, COMEN01C, COACT*, COCRD*, COTRN0xC, COBIL00C, CORPT00C) | 6–15 each | Always as REST or Spring re-imaginings, never as CICS-faithful ports. |
| CBTRN03C, CBCUS01C, CBACT02C/03C, CBTRN01C, CBEXPORT/IMPORT, CSUTLDTC | 2–5 each | Only inside larger apps. |

**Builds.** We built every branch with Maven 3.8.7, or with `javac` where there is no build file.
- **57** built as shipped with JDK 17.
- **9** built after an environment change:
  - 5 target Java 21, so they needed a JDK 21. This machine had only the Java 21 runtime, so we used a portable Temurin 21.
  - 4 set `maven.compiler.release=17`, but rely on a newer Maven's compiler-plugin default, so they needed an explicit compiler level.
- **1** failed: the SuiteCRM branch, which is not CardDemo.

So every CardDemo port builds.

## 2. Their method compared with ours

**What the agents were asked.** Every session got the lab brief (port the batch programs to Java 17+ with parity tests), plus a per-session prompt. That prompt is quoted in some PRs and visible in the branch names: "cbact01c-java-migration", "golden-master", "modernization-blueprint", "wave2-through-wave5". Some sessions were planning-only (blueprints, estate analysis, test-harness design), and those produced no Java.

**How parity was established**, as each PR describes it (classified from PR text):

| Parity method | Branches with Java |
|---|---|
| Unit tests against values derived by hand from the COBOL source | 57 |
| No parity claim | 5 |
| GnuCOBOL run as the reference, outputs diffed byte for byte | 2 (#229 CBACT01C, #235 CBSTM03A) |
| An external golden-output harness (`compare.py` over goldens produced under a frozen clock) | 2 (the `eval/` arms) |
| An independent Python oracle that computes the expected bytes | 1 (codev #14) |

Many PRs say plainly that they had no COBOL reference. For example, #127: *"No golden-file comparison against actual COBOL output exists — tests verify internal consistency and business rule application, not byte-level equivalence."* #160 says its "identical results" guarantee *"is based on code analysis"*.

**The method converged on ours over time.** Lined up by date, the CBACT01C attempts move:
- **March:** pipe-delimited output, no baseline;
- **April to June:** fixed-width text, with COMP-3 written as readable digits;
- **July to September:** EBCDIC input, real packed-decimal bytes and a byte-for-byte reference. That is #229 against GnuCOBOL with `-fsign=EBCDIC`, codev #14 against a derived oracle, and the eval arms against a golden harness.

#229's report reads: *"OUTFILE: IDENTICAL (5350 bytes) … PARITY PASSED: Java output matches COBOL byte for byte."*

**The two `eval/` arms are a controlled experiment.** Both were dated 2026-09-24 and port CBACT01C, CBACT04C and CBTRN02C as plain Java 21 with a `--dd NAME=path` launcher.
- **Arm A** worked from the COBOL alone: *"written from the COBOL sources, copybooks, JCL and the golden-output harness only"*.
- **Arm B** also had AWS Transform's analysis of the code.

Both report `SUMMARY: 19/19 files match` over 4 scenarios against the external harness. That harness, with its `compare.py`, fixtures and goldens, is not in the repository.

| | Devin (most runs) | Devin (later runs: #229, eval arms, codev #14) | GitGalaxy |
|---|---|---|---|
| Starting point | COBOL source plus a prompt | Same, plus a golden harness or GnuCOBOL | A GitGalaxy scan, then a generated scaffold, then a port (deterministic or model-written) |
| Expected output | Derived by hand from reading the COBOL | From running the COBOL (GnuCOBOL, or a harness built by running it), or an independent oracle | From running the COBOL under GnuCOBOL, with a CICS model and real Db2 where needed |
| Comparison | Unit-test assertions | Files byte for byte | Every output record, field by field per the copybook, decimals exact. CICS events, COMMAREA and Db2 tables too |
| Scenarios | Sample data, plus hand-made edge cases | 1–4 scenarios | Recorded scenarios plus fault injection. Batch cases run 7–29 times (below) |
| Who checks | The same agent session | The same session, against a reference it did not write | A harness separate from the port, plus a published register of where GnuCOBOL may differ from z/OS |

Two differences in scope matter for phase 2:
- **Assembler calls.** CBACT01C CALLs the assembler routine COBDATFT. Our harness refuses that: *"Blocked, with no faithful run possible yet"* (README). #229 instead wrote *"a small COBOL stand-in for the COBDATFT assembler routine"*. Their run, as written, rests on a model of COBDATFT that someone has to check; ours has no CBACT01C proof at all.
- **Control-block pointers.** CBSTM03A dereferences mainframe control blocks (PSA, TCB, TIOT). #234 reports that GnuCOBOL segfaults on it. #235 removed that linkage (*"verbatim copy … except for the removal of the mainframe PSA/TCB/TIOT control-block linkage"*) and then ran GnuCOBOL as the reference. We have no CBSTM03A case.

## 3. Structure and execution

**A typical plain port** reads the CardDemo data file:
- most often the ASCII rendering, `app/data/ASCII/acctdata.txt` (fixed-width text with EBCDIC-style overpunch signs);
- in the later runs, the EBCDIC file `app/data/EBCDIC/AWS.M2.CARDDEMO.ACCTDATA.PS`, read with charset IBM037.

It parses each 300-byte record at offsets taken from copybook CVACT01Y and writes the three outputs CBACT01C writes: OUTFILE, ARRYFILE and VBRCFILE.

Every port models COBOL numbers as `BigDecimal` or as integer cents. None uses `double`.

**The 26 distinct plain CBACT01C ports** (excluding the eval arms and two partial pieces) differ in their output contract:

| Output | Ports | Comparable to COBOL's records? |
|---|---|---|
| Fixed records with real packed-decimal (COMP-3) bytes | 6 | Yes, byte for byte |
| Fixed-width text with COMP-3 fields written as readable digits | 8 | Field by field, after decoding |
| Pipe-delimited text | 12 | Field values only. The record layout is a different contract |

The input split is 19 reading ASCII text and 7 reading EBCDIC.

Things the ports handled with care:
- **Zoned overpunch signs.** These are decoded in every port. codev #12 caught a factor-of-10 error in its own brief's examples.
- **Variable-length VBRCFILE records** with RDWs.
- **COBDATFT's date reformatting.**
- **The "2525.00 when debit is zero" quirk.**

The codev series also noticed that the ASCII and EBCDIC sample files differ in one record: *"Record 49 … has `ACCT-ADDR-ZIP = "ZEROAPR   "` in the EBCDIC file but `"A000000000"` in `acctdata.txt`"*.

**How our harness runs a batch case**, for comparison (`tests/tools/equivalence.py`):
- **Inputs:** the corpus's ASCII data files become fixed-length records. Indexed (KSDS) inputs are loaded into GnuCOBOL's BDB files, keyed like the program's SELECT.
- **Run:** under a driver that passes the JCL PARM through LINKAGE, with `COB_CURRENT_DATE` pinning the clock. Compiled `-std=ibm -fsign=EBCDIC`.
- **Outputs:** each is unloaded to fixed-length records, the I-O KSDS ones in key order, and compared field by field against the Java side.

This is close to the eval arms' harness: fixed records from ASCII fixtures, a frozen clock (theirs is libfaketime), PARM handling, and KSDS rewritten in key order. Two differences: we inject faults, and our expected outputs always come from running the COBOL.

## 4. GitGalaxy scan

Each port was scanned on its own with plain `galaxyscope` (main after #4178), main sources only, tests excluded. Nothing was excluded by the scanner.

**CBACT01C: COBOL against 28 Devin attempts**

| | Code lines | Functions | Branches | Max function complexity | I/O signals | Tokens |
|---|---|---|---|---|---|---|
| COBOL CBACT01C | 358 | 16 paragraphs | 41 | 8 | 14 | 4,700 |
| Devin attempts, median | 400 | 32 | 34 | 10 | 20 | 6,205 |
| Devin attempts, range | 187–1,792 | 11–270 | 19–131 | 8–26 | 8–29 | 2,910–17,701 |

The smallest, #229, is one 187-line file. The largest (`setup-java-build`, 1,792 lines) carries other modules too.

**CBACT04C and CBTRN02C: COBOL, our two ports, and the two eval arms**

| | Code lines | Functions | Branches | Max function complexity | Tokens |
|---|---|---|---|---|---|
| COBOL CBACT04C + CBTRN02C | 1,171 | 48 | 186 | 8 | 14,627 |
| Our det ports (2 files) | 2,271 | 78 | 270 | 29 | 46,159 |
| Our model ports (2 files) | 567 | 41 | 49 | 9 | 9,879 |
| Devin eval arm A (3 programs, shared library) | 1,202 | 174 | 68 | 9 | 12,677 |
| Devin eval arm B (3 programs, shared library) | 1,161 | 133 | 74 | 9 | 14,476 |

The eval arms port CBACT01C too, so their totals cover three programs against our two. Read the rows as shapes, not as a contest:
- Devin's arms and our model ports land at or below COBOL size.
- Our det ports are about ×1.9 the COBOL here, milder than the ×4 on CICS programs.

## 5. Phase 2: what can be judged, and how

Our proven batch cases that overlap with Devin's ports:

| Our case | Program | Our proof |
|---|---|---|
| carddemo-intcalc | CBACT04C | 20 runs; 22/22 paragraphs, 85/86 branches |
| carddemo-posttran | CBTRN02C | 29 runs; 26/26 paragraphs, 95/96 branches |
| carddemo-trnrpt | CBTRN03C | 25 runs; 81/82 branches |
| carddemo-readcust / readcard / readxref | CBCUS01C / CBACT02C / CBACT03C | 7 runs each; 21/22 branches |
| carddemo-dailyval | CBTRN01C | 21 runs; 65/66 branches |

Ranked candidates, value against effort:

1. **Eval arms A and B, on CBACT04C and CBTRN02C, against intcalc and posttran.** High value, low effort.
   - **Adapter:** their launcher already takes `--dd NAME=path` for headerless fixed-length records, the same form our harness feeds GnuCOBOL. It also takes `--parm`, and `--now` for our pinned clock.
   - **Comparison:** run their jar on every one of our runs, base and fault scenarios, then compare outputs with our field-by-field comparator. Fully byte-comparable.
   - **Payoff:** a controlled A/B (with and without AWS Transform analysis) measured on 20 and 29 runs, against their own 4 scenarios.
2. **CBACT01C, all 26 attempts plus the eval arms.** Highest number of independent attempts; medium effort.
   - **Prerequisite:** our harness needs a CBACT01C case with a COBDATFT model, added to `oracle_assumptions.md` as an explicit assumption.
   - **Then:** 9 ports are byte-comparable (6 with packed bytes, plus #229 and the two arms). 8 can be compared field by field after decoding their text output. The 12 pipe-delimited ports changed the output contract, so we can judge only their field values.
3. **Batch jobs inside the Spring Boot re-imaginings.** Partial, high effort. For example, #239 runs POSTTRAN → INTCALC → TRANREPT → CREASTMT on PostgreSQL. We would need to export their tables back to records before comparing.
4. **CBSTM03A** (#235 and its children). We would first need our own case, with the PSA/TCB/TIOT linkage handled and declared. #235's GnuCOBOL-referenced 50/50 result could then be checked independently.
5. **Online CICS programs.** Devin's are REST re-imaginings, so CICS events, BMS maps and COMMAREA contracts have no counterpart. Not comparable to our CICS proofs; we record them here and stop.

## Notes on method

- **Branch classification is heuristic.** It is drawn from file contents and PR text, so read program, style and parity labels as approximate. The JSON keeps the evidence fields.
- **A PR's parity claim is the PR's own.** Phase 2 is where we test such claims.
- **Fixed environment.** Builds and scans ran on this machine (Ubuntu 24.04, Maven 3.8.7, JDK 17, plus Temurin 21 where a branch targets Java 21).
