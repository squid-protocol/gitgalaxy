# COBOL → Java translation, observed: one harness, one scanner, many translators

*An observational, post-hoc study. Draft for review, 2026-10-03.*

## Abstract

GitGalaxy's author built a deterministic COBOL→Java translator ("det port") and an equivalence harness that proves a translation behaves like its COBOL. The harness compares output byte for byte against an executed reference, with fault injection. Afterwards, we looked at what others had published for the same public programs (AWS CardDemo, IBM GenApp):
- IBM's research artifact for WCA4Z;
- 67 branches of Devin workshop ports;
- a commercial literal translator (SENTINEL IDE);
- an LLM-driven re-architecture (lasserre-consulting);
- an evidence-first modernization factory (Lightyear);
- an academic API-recovery study.

We measured all of them with the same two instruments: the equivalence harness, where their code could run, and GitGalaxy's structural scanner, everywhere. The data supports a small number of statements:
1. **Translations fall on a structural spectrum** the scanner can place without running anything: literal at byte level → literal with text I/O → restructured → re-architected.
2. **Literal translation has a structural signature, whoever does it.** Function, branch and mutation counts keep their rank order from COBOL (ρ 0.83–0.97) for two independent literal translators, and that signature disappears in restructured ports.
3. **Size depends on representation, not on literalness.** One literal translator is 0.44× the COBOL's size; ours is ×3.8.
4. **Behaviour and structure are separable, in both directions.** Restructured ports (Devin's eval arms, Lightyear) matched the COBOL byte for byte on base runs while sharing little of its structure. A structure-preserving port (SENTINEL) failed on two programs through record-layout errors. Its literal structure did keep the error paths' shape: 10 of 11 abend codes matched on a missing file, where the restructured ports matched none.
5. **On CBACT01C, 1 of 8 distinct byte-comparable Devin attempts proved end to end.** It was built around an independent oracle, and converged on roughly the det port's size. 4 more wrote every data file byte for byte (default locales), 1 was partial, and 1 crashed.
6. **What differs most is verifiability:**
   - a deterministic translator gives the same code every run, while 26 agent sessions on one program share under a fifth of their class names;
   - error paths centralised into a framework could not be exercised by our harness, while literal ports keep them drivable.
7. **Validation practice across the field ranges widely,** from none, through self-written tests, to executed references. Only executed comparison settled any question here.

The study is uncontrolled and small. We list what it cannot establish (§11) and threats to its validity (§12).

## 1. Positioning: blameless and post hoc

- **What this is:** I built something, noticed others had built things for the same public programs, and measured them all the same way, afterwards. Nobody was asked to take part, and most subjects are workshop exercises, research prototypes or demos. Each is judged against what it attempted.
- **Player and referee.** The author of the translator also built the instruments. Our mitigations:
  - **open, pinned tooling:** every artifact is fetched at a recorded commit, and every adapter is committed separately;
  - **a public register of the oracle's limits** (`docs/language_status/oracle_assumptions.md`);
  - **the referee's verdicts went against its author too.** It found bugs in our own det port: a LINK COMMAREA overread (#4181), and a typed contract DTO that dropped unnamed bytes (ERROR-MSG's date under FILLER). Both are fixed in #4200, and LGSTSQ's COMMAREA now matches byte for byte and corrected our own published figures (det size ×5 → ×4.2; the "model-port TODOs" were mostly our generator's scaffold, #4179). It also passed Devin's best ports on base runs.
- **The axis is not "LLM vs deterministic".** Several commercial translators are rule-based (AWS Blu Age / AWS Transform's refactor engine, SoftwareMining, Heirloom, Micro Focus), and an LLM can write literal code. The axes that matter in the data are **how much COBOL structure is kept** and **how equivalence is established**.

## 2. Subjects

| Subject | Translator | Programs | Pinned at | Licence |
|---|---|---|---|---|
| Det ports | GitGalaxy deterministic translator | 49 of 51 cases proven (CardDemo 28, CBSA 8, GenApp 13 programs; 17 Db2 cases) | main | repo licence |
| Model ports | claude-sonnet-5-5 in the porting loop | 23 committed (+3 in review, #4187) | main | estate licences |
| IBM WCA4Z | LLM, IBM research artifact (2024) | GenApp LGACDB01, one paragraph | `sandeephans/validation-c2j@967d00b` | none stated |
| Devin | Agent, workshop labs (Mar–Sep 2026) | 67 branches; CBACT01C ×26 distinct (9 byte-comparable runs harnessed); eval arms A/B on CBACT01C, CBACT04C, CBTRN02C | inventory JSON (per-branch SHAs) | Apache-2.0 |
| SENTINEL IDE (NOAH Labs) | Commercial tool, "1:1 mapping of COBOL programs to Java classes" | all CardDemo, including the IMS/MQ extension | `noahlabsai/aws-mainframe-modernization-carddemo-JAVA@47af18641ee6` | README badge says Apache-2.0; no LICENSE file |
| lasserre-consulting | LLM agent (Claude Sonnet), re-architecture to Spring/JPA/Batch/JMS | all CardDemo | `@bcdb72316291` | none |
| Lightyear | Evidence-first "dark factory" | CBACT04C, COACTVWC, a PL/I authorization | `howardweale/lightyear-carddemo-modernization@e24d77822f70` | none |
| viniman27 | Academic study, not a port | API recovery on CBTRN02C, CBACT04C, CBTRN03C | 2026-09-16 | none |
| xavierxmorris | Read-only .NET slice, not a port | data display only | `@836a2bd95306` | Apache-2.0 |

Three further repositories in the sweep were empty or stubs. Repositories without a licence are measured, never redistributed, and quoted only in short excerpts.

## 3. Instruments

**Equivalence harness.** GnuCOBOL 3 (IBM dialect, EBCDIC signs, TRUNC(STD)), a CICS model, and IBM Db2 Community Edition through our precompiler stub. It compares events, the COMMAREA, datasets and tables byte for byte, with per-scenario fault injection (file statuses, CICS conditions). How the reference may differ from z/OS is registered in `oracle_assumptions.md` (e.g. C9 pointer width, D1 collation, X6 refused WRITEQ, M2 no SQL fault injection). The CBACT01C case (#4198) added four entries:
- **A1:** CardDemo's COBDATFT assembler routine, translated instruction for instruction; load-module-dependent paths refused.
- **C10:** a scoped, counted tolerance for INITIALIZE/VALUE ZERO zoned items (GnuCOBOL's unsigned F zone against z/OS's C sign). The bytes are reported, never hidden.
- **L3:** WORKING-STORAGE with no VALUE (GnuCOBOL's spaces, against LE's STORAGE option).
- **F3:** variable-length (RECFM=VB) records, compared by content, not by z/OS RDW. Third-party code runs unmodified behind a thin, separately committed adapter (`ibm_wca4z_port.py`, `devin_port.py`).

**SQL fault injection** (#4200; fixes #4173 and #4181):
- **How faults are planned:** a fault plan keyed by `PROGRAM:LINE`, applied identically by the COBOL precompiler stub and by the Java side's DetSql.
- **Automatic enumeration:** −803 on INSERT; +100 on SELECT INTO; −913 on UPDATE, DELETE, OPEN and FETCH.
- **What can't be judged in full:**
  - a fault run that LINKs to a program the case doesn't run is judged up to the LINK;
  - runs that reach a translator hole, and model ports with no injection seam, are recorded as "not judged".
- **Register updates:**
  - M2 is now MATCHED, with the SQLCA contents assumed;
  - X6 gains the judged-up-to-LINK rule;
  - new X10: COMMAREA bytes past the caller's record;
  - new X11: GenApp's ABSTIME in S9(8) COMP dates errors 01011900 on both sides.

**GitGalaxy scanner.** It reads COBOL and Java on the same axes: functions, branch points, state mutations, I/O, IPC, size and tokens, complexity, debt. This work found and fixed scanner defects, and the readings here are after the fixes where stated:
- Java `?`/`:` overcounted as branches (#4170, fixed in #4178);
- cobolrt calls not seen as I/O (#4163);
- det ports excluded as generated noise (#4164).

Still open:
- commented-out statements not counted (#4171);
- compound JDK I/O classes not counted (#4191, fixed in #4193). Translator-specific runtime facades remain unrecognised, apart from our own cobolrt (#4163).

**Contracts.** Port invariance (#4167) asserts rank agreement for the readings that should survive literal translation. The parity bands (#4162) predict a det port's methods and branches from its COBOL.

## 4. Observation A: structure survives literal translation

COBOL against the det port, 49 programs, tie-corrected Spearman ρ (#4167, after #4178):

| Reading | ρ | Notes |
|---|---|---|
| Functions / paragraphs | 0.94 | per estate 0.97 / 0.98 / 0.88 |
| Branch points | 0.86 | 0.83 before the #4178 fix |
| State mutations | 0.76 | |
| I/O | 0.87 | 0.24 before #4163 |
| IPC (LINK/XCTL/RETURN) | 0.84 | |
| Size, tokens, risk scores, archetype | not invariant | documented as free to change |

**A second, independent literal translator shows the same signature.** SENTINEL IDE, against the same 28 CardDemo programs:

| Reading (COBOL vs port) | ρ SENTINEL | ρ det | Median size against COBOL: SENTINEL | Median size against COBOL: det |
|---|---|---|---|---|
| Functions | 0.88 | 0.97 | 1.28 | 2.47 |
| Branches | 0.91 | 0.83 | 0.75 | 2.67 |
| Mutations | 0.89 | 0.84 | 0.88 | 3.65 |
| Code lines | 0.89 | 0.74 | 0.51 | 3.85 |
| Tokens | 0.93 | 0.81 | 0.52 | 7.29 |
| I/O | 0.07 ‖ | 0.90 | — | 0.75 |

‖ After #4193 (which fixed #4191). Java I/O now counts the call that opens a resource: `new FileInputStream`/`FileOutputStream`/`FileReader`/`FileWriter`/`RandomAccessFile`, `PrintWriter`/`PrintStream` on a path literal, and `FileChannel.open`. Decorators such as `BufferedReader` don't count, so a nested chain counts once. SENTINEL's I/O total across its 28 classes rose from 26 to 43 (CBTRN02C 2 → 10, CBACT04C 0 → 6). Its COBOL-vs-port I/O ρ moved only from −0.01 to 0.07. Our det, model, Devin and lasserre readings, and the port-invariance I/O ρ (0.871), are unchanged.

**A finding about the instrument.** 14 of SENTINEL's classes do their I/O through SENTINEL's own runtime facade (`xrefFile.read(`, `fileIO.rewrite(`, `screenIO.sendMap(`). The scanner can't safely anchor on those names without matching ordinary Java. Our det ports' I/O agreement (0.24 → 0.87) likewise came only after the scanner was taught our runtime's vocabulary (#4163). So for a third-party port, the I/O ρ measures how well the scanner recognises that translator's runtime as much as it measures structure. SENTINEL's structural evidence rests on functions, branches and mutations (ρ 0.88–0.91), which don't depend on runtime vocabulary.

## 5. Observation B: a structural spectrum, readable without execution

Whole CardDemo estate (28 programs where available):

| Strategy | Example | Code lines | Branches | I/O | Size against COBOL |
|---|---|---|---|---|---|
| COBOL | — | 17,279 | 2,336 | 187 | 1 |
| Literal, byte-level storage | det | 64,899 † | 6,328 | 124 | ≈3.8 † |
| Literal, text I/O | SENTINEL | 7,630 | 1,469 | 43 ‡ | 0.44 |
| Re-architected (Spring/JPA/Batch/JMS) | lasserre | 1,137 | 34 | 30 | 0.07 |

† Measured on det copies with long lines rewrapped for scanning, which inflates line counts by a median of ~19% (wiki 05-18). Branch and token readings are unaffected.
‡ After #4193. Still an undercount: 14 classes do I/O through SENTINEL's own runtime facade, which the scanner doesn't recognise (§4).

Program classes for CBACT04C and CBTRN02C, where we have each strategy (lines / branches / I/O / mutations):

| | COBOL | Det | Model (ours) | Devin A | Devin B | Lightyear |
|---|---|---|---|---|---|---|
| CBACT04C | 552 / 86 / 13 / 111 | 1,076 / 127 / 12 / 169 | 251 / 16 / 7 / 40 | 153 / 12 / 1 / 26 | 155 / 14 / 2 / 9 | 260 / 11 / 13 / 24 (service + tasklet) |
| CBTRN02C | 619 / 100 / 16 / 136 | 1,195 / 143 / 15 / 179 | 316 / 33 / 11 / 38 | 166 / 14 / 2 / 32 | 170 / 13 / 2 / 9 | — |

In Devin's projects, 60–80% of code lines sit in a shared framework of record codecs, file classes and `Abend`. Project-wide I/O is 39 for each arm.

**What the scan separates:**
- **Literal ports** keep paragraph-level structure: det and SENTINEL, ρ 0.83–0.97.
- **Restructured ports** keep the data contract and roughly the I/O count, but relocate control flow. Devin moves it into a framework; Lightyear into a service + tasklet + codec.
- **Re-architected ports** replace the program boundary altogether.

**Size is a property of representation, not of literalness.** Two literal translators differ by ~9× in size: det stores COBOL data as byte images with typed accessors, while SENTINEL uses native Java fields and text I/O. The construct map (#4169) locates the det port's growth outside the translated logic: paragraph methods are 1.33× the COBOL; storage field declarations are 28% of det function lines, entry points 11%, dispatch 6%, DTO bridges 4%. Screen I/O is the outlier: 42 SEND/RECEIVE MAP paragraphs carry 34% of paragraph growth, and the model's code there is 0.15× the det port's.

## 6. Observation C: behaviour, where we could run it

| Subject | Program | Scenarios | Result | Notes |
|---|---|---|---|---|
| Det ports | 49 of 51 cases | 7–29 runs per batch case, with fault injection; 705 scenarios across the 50-case sweep, before CBACT01C (13 runs) was added | proven | 2 not proven on purpose (#4085, D1). Coverage modest on some CICS/Db2 programs (LGACDB01 6/14 → 8/14 with SQL faults, §6.0) |
| Model ports | 23 committed | per case, with faults | proven | 3 more pending review (#4187). INQACC, XFRFUN and LGUPDB01 unprovable through the harness gap #4188 |
| IBM WCA4Z | LGACDB01 INSERT-CUSTOMER, in our det task | 4 | **not equivalent on any** | Db2 −4461: DATEOFBIRTH never bound (`// ps.setDate(4, …)`); failure swallowed (`// caReturnCode = 90;`). The published JUnit doesn't compile against the published Java, and the recorded run is 2 skipped passes / 2 failures, against the 4/4 reported. Their test 2 asserts DATEOFBIRTH and would likely flag the defect if it ran. The artifacts may come from a different version |
| Devin arm A (COBOL only) | CBACT04C / CBTRN02C | base run, 6 JVM environments each | equal in default/tr/de/hi; differs in ar-EG/th-TH | `String.format` without a locale writes non-ASCII digits (`BatchContext:45`, `Cbact04c:156`, `Cbtrn02c:42,119`) |
| Devin arm B (+ AWS Transform analysis) | CBACT04C / CBTRN02C | same | CBACT04C as A; CBTRN02C equal in all 6 | one locale defect (`Cbact04c:67`) |
| Lightyear | CBACT04C (intcalc) | base run, 6 JVM environments | **data equal** in default/tr/de/hi (ACCTFILE 52/52, TRANSACT 53/53, RC 0); ar-EG and th-TH differ | Locale defect: `String.format` without a locale (`ZonedDecimal.java:47`, `InterestCalculationService.java:94`). Prints no job log, by design. This is the first observation of the equivalence its README calls "unobserved" |
| SENTINEL | CBACT02C, CBACT03C, CBCUS01C | base run | job log differs (records logged as Java `toString()`, e.g. `CVACT02Y{cardNum=…}`) | These cases compare only the job log, so there's no data verdict |
| SENTINEL | CBACT04C (intcalc) | base run | **differs**: abends U0999 on the first account (COBOL: RC 0) | `XREF-ACCT-ID` read at `substring(16, 27)`; CVACT03Y puts it at offset 25. Every cross-reference lookup fails (status 23) |
| SENTINEL | CBTRN02C (posttran) | base run | **differs in every output**: all 305 transactions rejected (COBOL: 264 posted, 41 rejected, RC 4) | `DALYTRAN-AMT` (S9(09)V99, 11 bytes) read as 12, shifting every later field by one. Also: the same XREF offset; 361-byte reject lines against a 430-byte record; a 26-byte TCATBALF key against 17; the TCATBALF open check skipped |

**Not run, with reasons:**
- SENTINEL CBTRN01C and CBTRN03C: built on reader/writer interfaces with no shipped implementation.
- SENTINEL COBTUPDT: JPA against its own Db2 schema; not attempted.
- Lightyear COACTVWC: a read-only lookup with no CICS task to compare.

SENTINEL's full project does not compile as shipped (18 errors in 3 files the programs don't use), so only the five program classes were compiled.

**Adapter** (`docs/research/third-party-ports-harness.md`, #4194):
- text lines in and out; fixed records rejoined; wrong-length lines flagged, never padded;
- Lightyear driven by its own jar and `--carddemo.*` properties;
- SENTINEL driven by calling each program's `execute()`, as its unit tests do;
- logging reduced to messages; `ABCODE n` mapped to `Unnnn`.

### 6.0 Db2 branch coverage with SQL fault injection

SQL fault injection (#4200) raised branch coverage on every Db2 case, with no new non-proofs:

| Case program | Before | After |
|---|---|---|
| LGACDB01 | 6/14 | 8/14 |
| LGACDB02 | 4/10 | 5/10 |
| LGAPDB01 | 13/31 | 17/31 |
| LGDPDB01 | 5/12 | 6/12 |
| LGIPDB01 | 46/74 | 48/74 |
| LGUCDB01 | 2/10 | 4/10 |
| LGUPDB01 | 17/38 | 26/38 |
| CBSA DBCRFUN | 22/35 | 25/35 |
| CBSA DELACC | 10/14 | 13/14 |
| CBSA INQACC | 13/25 | 15/25 |
| CBSA UPDACC | 5/6 | 6/6 |
| CBSA XFRFUN | 44/81 | 46/81 |
| CardDemo COBTUPDT | 14/20 | 16/20 |
| CardDemo COTRTUPC | 124/166 | 126/166 |

The gains are modest on most programs. Many remaining branches depend on inputs, not on SQL results, which is the gap path-driven scenario generation (#4175) addresses.

### 6.1 CBACT01C: nine Devin runs on one program

Case `carddemo-readacct` (#4198, `docs/research/devin-cbact01c-harness.md`). CBACT01C writes three files per account: OUTFILE (with a COMP-3 field and a COBDATFT-reformatted date), ARRYFILE and VBRCFILE (variable-length). Our det port proves on it: 13 runs with faults, 16/16 paragraphs, 41/44 branches. The Devin ports were run on base runs, under 6 locales.

| Port | Data (OUTFILE, ARRYFILE, VBRCFILE, RC) | Job log | Verdict | Cause of differences |
|---|---|---|---|---|
| codev #13 / #14 (identical Java) | equal, all 6 | equal, all 6 | **proven** | — |
| eval arm A | equal, all 6 | differs | data equal | signed numbers shown with a trailing sign (`000000019400+`) where the COBOL shows the overpunch (`00000001940{`) |
| eval arm B | equal, all 6 | differs | data equal | as arm A |
| #229 (ran GnuCOBOL itself) | equal, all 6 | differs | data equal | edited numbers in the log (`+0000000194.00`) |
| #168 | equal, all 6 | differs | data equal | logs whole raw records instead of the program's field lines |
| #214 | equal in 4; differs under ar-EG/th-TH | differs | data equal (default locales) | `String.format` without a locale (`CobolFieldParser.java:94`) |
| #167 | OUTFILE/ARRYFILE equal in 4; **VBRCFILE unframed** | differs | partial | VB records written back to back with no length; locale defect |
| #220 | none written | none | **crashes** (RC 1) | `new BigDecimal(...)` on a field holding the overpunched sign `{` (`AccountRecord.java:87`) |

Every Devin port reaches 24/44 branches on the base run; none has a seam for the case's fault runs. Log differences are counted because a program's DISPLAY lines are part of its observable behaviour. Under C10, unsigned INITIALIZE zeros in ARRYFILE (100 bytes per run) are counted and reported.

**Coverage asymmetry.** The third-party ports have no hook for injecting file statuses, so they were judged on base runs, plus the missing-file runs in §8. Base runs cover 49/86 (CBACT04C), 55/96 (CBTRN02C) and 13/22 branches, against 85/86 and 95/96 for our ports' fault-injected proofs.

**Our own failures, found by the same harness:**
- **#4181:** the det port marshalled `LINK LGSTSQ COMMAREA(ERROR-MSG)` past its 71 bytes, on an error path none of our proofs reached. A second bug sat beside it: the typed contract DTO dropped unnamed bytes (ERROR-MSG's date under FILLER). Both were found once SQL faults reached the path, and both are fixed (#4200).
- **Variable-length records:** the det translator had been writing CBACT01C's VB records as 80-byte ones (found while building the CBACT01C case; WIP branch).

## 7. Observation D: reproducibility and variance

**Det.** CBACT01C translated three times with the cache off gave byte-identical output: 14 Java files, hash `3b934c219c4d9c3c`.

**Devin**, 26 distinct CBACT01C attempts from one source and one lab brief (whole project):

| Reading | Min | Median | Max | Max ÷ min | CV |
|---|---|---|---|---|---|
| Java files | 1 | 8 | 20 | 20× | 0.42 |
| Code lines | 187 | 396 | 970 | 5.2× | 0.39 |
| Functions | 11 | 30 | 101 | 9.2× | 0.59 |
| Branches | 19 | 32 | 88 | 4.6× | 0.47 |
| Mutations | 16 | 33 | 81 | 5.1× | 0.47 |
| Max function complexity | 8 | 10 | 26 | 3.2× | 0.43 |
| I/O | 13 | 20 | 29 | 2.2× | 0.19 |

**How the attempts differ:**
- **Class names:** the median pairwise overlap (Jaccard) is 0.18, and 24 of the 325 pairs share none. There are 67 distinct names across attempts.
- **Input and output design:** there are 5 designs (ASCII→pipe-delimited 9, ASCII→fixed-width 8, EBCDIC→packed 4, EBCDIC→pipe-delimited 3, other 2). Only the 4 EBCDIC→packed attempts write output comparable byte for byte.

**What stays stable is what the COBOL fixes:** the I/O count (CV 0.19), and the copybook's record layout (`AccountRecord` appears in 25 of 26 attempts).

**Structure against verdict (CBACT01C, medians; tiny groups, indicative only):**

| Group | n | Files | Code lines | Functions | Branches | Codec roles present |
|---|---|---|---|---|---|---|
| Byte-proven (codev) | 1 distinct | 20 | 970 | 101 | 88 | charset, packed, zoned, record codec |
| Data equal, log differs (#229, #168, #214) | 3 | 6 | 406 | 29 | 33 | in 1 of 3 |
| Partial (#167) | 1 | 6 | 403 | 22 | 36 | record codec |
| Crash (#220) | 1 | 7 | 541 | 92 | 42 | none |
| Text output, not byte-comparable by design | 19 | 9 | 371 | 30 | 29 | zoned in 5, record codec in 1 |
| Det service (for reference) | — | 14 | 1,047 lines in the service | — | — | the cobolrt runtime |

**What this lets us note:**
- **The only fully proven attempt converged on det-like size** (970 lines, against the det service's 1,047). It carries the only complete codec kit, and it was built around an independent oracle (a Python program deriving the expected bytes).
- **Every attempt that used GnuCOBOL or a golden harness** (#229, the eval arms) got its data files right.
- **Size alone doesn't predict correctness.** The crashing attempt is the second-largest by functions.
- **Structure doesn't separate "data equal" from "partial".** #167 and #168 are near-identical in size and shape. One frames its VB records and one doesn't, a byte-level property only execution reveals.

**Convergent re-invention.** Later Devin ports each rebuild the same runtime kit under new names (A: `Packed`/`Zoned`/`FixedRecord`/`KeyedFile`; B: `PackedDecimal`/`ZonedDecimal`/`RecordArea`/`FixedFile`; codev: `PackedDecimalCodec`/`FixedRecordReader`). Name-based role counts across 37 plain ports:

| Role | Ports |
|---|---|
| Zoned decimal | 13 |
| Fixed-record handling | 11 |
| Packed decimal | 6 |
| Abend | 5 |
| Charset | 3 |
| Keyed file | 2 |
| File status | 2 |

This detection is by class name only; functional equivalence of the kits is not established.

## 8. Observation E: validation practice

**Across the field:**

| Subject | How correctness is established |
|---|---|
| SENTINEL | No parity claim found |
| lasserre | "Shadow mode" comparator that normalises output (`stripTrailing`, leading zeros removed) before comparing. A lossy check |
| Lightyear | Signed evidence receipts; native equivalence explicitly "unobserved" |
| Devin (57/67 branches) | Unit tests against values the same agent worked out from reading the COBOL |
| Devin (5/67) | GnuCOBOL reference, golden harness, or an independent oracle |
| viniman27 | 12,700 executions of the unmodified COBOL under GnuCOBOL 3.2 behind HTTP facades; recovered contracts tested by LLM scenarios, fuzzing, model-based tests and replay |
| IBM WCA4Z | Symbolic-execution test generation on z/OS, replayed as mocked JUnit (paragraph scope) |
| Ours | Executed GnuCOBOL/CICS/Db2 reference, whole program, byte-level comparison, fault injection |

**Over time (Devin):**

| Months (2026) | Parity method |
|---|---|
| March–June | Hand-derived unit tests only (47/47) |
| July–August | First GnuCOBOL references |
| September | Golden harnesses (2), Python oracle (1) |

Independently, the workshop practice moved toward executed references.

**Error paths: collapsed and unexercised, not proven absent.** COBOL CBACT04C has 108 file-status and abend references.
- **Devin arm A** keeps `ERROR READING …`/`ERROR WRITING …` and `Abend(999)`, but has no file-status codes (Java `IOException` instead) and no `ERROR OPENING …` messages.
- **SENTINEL** keeps both the status codes (`"35"` on a missing file) and the messages.

**The external-fault experiment** (#4194). With no I/O seam to inject a status, a missing input file stands in for the COBOL's status-35 OPEN fault. In every run, the COBOL displays its specific `ERROR OPENING …` message and `FILE STATUS IS: NNNN0035`, then abends U0999.

| Port | Runs matching the COBOL | What the port does instead |
|---|---|---|
| SENTINEL | 10 of 11 abend codes match | Several messages worded or spaced differently. With TCATBALF absent, CBTRN02C treats it as empty and finishes normally (it opens the file only `if (f.exists())`) |
| Lightyear | 0 of 4 | The job ends FAILED and publishes nothing, but the process **exits 0** (Spring Boot's default for a failed batch job). A scheduler reading the return code would see success |
| Devin arm A | 0 of 8 | Exits 12, prints the path on stderr; no `ERROR OPENING` message, no status |
| Devin arm B | 0 of 8 | Exits 1 with a Java stack trace |

The structural observation (error handling collapsed into a framework) becomes measured behaviour: the restructured ports still detect the failure, but report it differently from the COBOL, in code, message and status.

**Caveats.**
- On z/OS a missing DD usually fails at job-step allocation, before OPEN.
- A missing file exercises only one fault class; truncated records and duplicate keys are not yet run.
- GnuCOBOL is the reference.
- Lightyear's own comparator was not used.

## 9. Pros and cons by strategy

| Strategy (examples) | Pros | Cons |
|---|---|---|
| **Literal, byte-level (det)** | Path-by-path verifiable (fault injection reaches 85/86, 95/96 branches); reproducible byte for byte; paragraph lineage keeps runbooks, abend codes and audit trails; regenerate-and-diff on COBOL change | ×3.8 size (×4.2 as emitted, by file median); COBOL-shaped Java; depends on the cobolrt runtime; coverage limited by hand-written scenarios (SQL faults now injected, #4200; input-driven branches still unreached, #4175) |
| **Literal, native fields (SENTINEL)** | Keeps structure (ρ 0.88–0.91) at 0.44× size; keeps file-status codes and error messages, and matches 10 of 11 missing-file abend codes | Two record-offset errors broke CBACT04C and CBTRN02C on base runs; records logged as Java objects; no parity claim found; the project doesn't compile as shipped; reproducibility unknown |
| **Model-written under proof (our loop)** | Idiomatic; near-COBOL size (×1.09); proven on its scenarios | Not reproducible; leftover scaffold TODOs (#4179); LINKed-program harness gap (#4188) |
| **Agent-restructured (Devin, Lightyear)** | Idiomatic, small program classes; base-run data equal to the COBOL in default locales (Devin's eval arms, Lightyear CBACT04C) | Each session a new codebase (Jaccard 0.18); failure behaviour diverges (exit 0 on a failed job, generic exit codes, stack traces); no fault seam; mostly self-written tests (Devin); the same locale defect in all three |
| **Re-architected (lasserre)** | Smallest (×0.07); modern platform services (JPA, Batch, JMS) | Program boundaries and output contracts replaced; equivalence checked only through lossy normalisation |
| **Research artifact (IBM WCA4Z, 2024)** | Path-complete test generation (a capability we lack, #4175); real z/OS reference | Paragraph scope; mocked resources; published artifacts inconsistent with the reported result; failed against real Db2 |

**Maintenance and onboarding (an argument, not a measurement).** A literal port keeps the map an organisation already has: paragraph names, error messages, abend codes. A restructured port starts each team on a new design, and our variance data shows each agent session produces a different one. The counterweight: teams that will never read the COBOL may prefer idiomatic code. The data supports a sequence (literal and proven first, then restructured under proof), not a winner.

## 10. Translation strategies compared, and what each teaches

### 10.1 Side by side

| | Det (GitGalaxy) | SENTINEL IDE | Devin (workshops) | Lightyear | lasserre | IBM WCA4Z (2024 artifact) |
|---|---|---|---|---|---|---|
| Unit of translation | Statement | Paragraph → method | Per-session redesign | Service + batch step | Whole-application re-architecture | Single paragraph |
| Structure | COBOL's paragraphs and control flow, kept | Paragraphs kept (`perform<Paragraph>()`) | Program class plus a re-invented runtime framework | Service, tasklet and codec | Spring REST/Batch/JMS/JPA modules | One method; program flow not translated |
| Data representation | Byte-exact storage images (EBCDIC, packed, zoned) | Native typed fields; UTF-8 text I/O | Varied (5 input/output designs across 26 CBACT01C attempts) | Record codecs (`CardDemoRecordCodec`, `ZonedDecimal`) | PostgreSQL entities (JPA) | Generated record classes |
| Size against COBOL | ×4.2 as emitted (file median) | ×0.44 (estate) | Small program classes plus a framework (60–80% of project lines) | ≈×0.5 for CBACT04C (260 / 552 lines) | ×0.07 (estate) | n.a. (one paragraph) |
| Correctness claim | Per-program executed byte-level proof, with fault injection | None found | Mostly self-written tests from reading the COBOL (57/67) | Equivalence "unobserved"; signed evidence receipts | Lossy "shadow mode" comparator | Generated path tests, run on z/OS; Java side mocked |
| Observed here (base runs) | 49/51 cases proven | CBACT04C and CBTRN02C differ (record offsets) | Eval arms: data equal (locale defect); CBACT01C: 1 proven, 4 data equal, 1 partial, 1 crash | CBACT04C data equal (locale defect) | Not run | LGACDB01 not equivalent |
| Reproducibility | Byte-identical across runs | Unknown | Divergent across sessions (class-name Jaccard 0.18) | Unknown | Unknown | Unknown |
| Error paths (missing input file) | Kept, and fault-tested | Kept: 10/11 abend codes match; some messages differ; one missing file treated as empty | Collapsed: 0/16 match (exit 12 or 1, no status) | Detected but exits 0: 0/4 match | Mapped onto Spring Batch exit statuses and exceptions; COBOL status codes and messages not kept | Commented out (`// caReturnCode = 90;`) |

Sources: §2–§8; Lightyear and lasserre readings from this study's scans at the pinned commits.

### 10.2 What each approach teaches

These are observations about what each approach shows is possible or costly, not verdicts on its authors.

- **SENTINEL:** literal structure need not be large. Native typed values give ×0.44 the COBOL's size while keeping paragraphs and error paths. Size follows representation, not literalness.
- **IBM WCA4Z:** path-driven test generation addresses the coverage gap that hand-written scenarios leave. Our LGACDB01 proof reaches 8 of 14 branches, even with SQL fault injection (6 before); their method reports full path coverage of its unit.
- **Lightyear:** evidence can be reported as signed receipts, with an explicit "unobserved" scope where equivalence hasn't been checked. That's an honest way to say what is and isn't known.
- **viniman27:** scenario volume. 12,700 GnuCOBOL executions dwarf the 7–29 runs per case used here.
- **Devin:** the cost of redesigning in each session shows up as variance between attempts and a runtime re-invented each time. The workshop's own practice nonetheless converged on GnuCOBOL references and byte parity.
- **Across SENTINEL, Lightyear and Devin, three lessons from execution:**
  - Literal structure didn't guarantee correct data. SENTINEL kept the structure and the shape of its error paths best, yet two record-offset errors broke CBACT04C and CBTRN02C. Being structure-preserving and being layout-correct are separate properties: the scanner sees the first, and only execution sees the second.
  - The restructured ports got base-run data right in default locales, but their failure behaviour diverges.
  - The same locale defect (`String.format` without a locale) appeared independently in Lightyear and in both Devin arms.
- **Only executed comparison distinguished these outcomes.** Neither the structural scan nor the ports' own validation did. That's the paper's core observation.
- **lasserre:** the endpoint many organisations want (a modern platform architecture), and what's at risk when it is reached without an executed oracle.

### 10.3 Synthesis

Every approach trades three things: **fidelity** to the COBOL's structure and bytes, the **form** of the resulting Java, and how far its correctness can be **verified**. No subject here maximises all three.

**The author's roadmap (a plan, not a finding).** For the det translator, these lessons suggest:
- a typed-value representation layer, aiming at SENTINEL's size while keeping byte-level proof;
- path-driven scenario generation (#4175), building on the SQL fault injection now in place (#4200);
- per-program proof certificates, in the spirit of Lightyear's receipts;
- an open harness any translator can be run through, as was done here for IBM's and Devin's code.

## 11. What the data lets us state, and what it doesn't

**Supported:**
1. One scanner places translations on a structural spectrum without executing them (§5).
2. Paragraph-level structural rank agreement is a signature of literal translation, seen in two independent literal translators and absent in restructured ones (§4, §5).
3. Translation size is driven by data representation more than by structural fidelity (§5).
4. Byte-level base-run equivalence is reachable by restructured ports (Devin's eval arms, Lightyear CBACT04C), while a structure-preserving port (SENTINEL) can still fail on record layout (§6).
5. Structural fidelity, layout correctness and failure behaviour are separable properties. The scanner measures the first; only execution measured the other two (§6, §8).
6. On a missing input file, the restructured ports detect the failure but report it differently from the COBOL (exit 0, generic codes, stack traces), while the literal port mostly matches its abend codes (§8).
7. The published IBM LGACDB01 artifact is not equivalent to its COBOL against real Db2 (§6).
8. Repeated agent sessions on one program produce structurally divergent code, while the deterministic translator is reproducible (§7).
9. On CBACT01C, the one Devin attempt proven end to end was built around an independent oracle, and every attempt that ran GnuCOBOL or a golden harness wrote correct data. Execution-based validation in the source process went with correct output, in this small sample (§6.1, §7).
10. Validation practice in public work varies widely and is mostly not execution-based (§8).

**Not supported:**
- that any translator or strategy is better overall;
- generalisation beyond these programs, estates and snapshots;
- that any port's error paths are wrong beyond the one fault class run (a missing input file);
- that literal translators in general carry layout errors (one translator, two programs);
- that our reference is z/OS-exact;
- that commercial products today behave like these public artifacts.

## 12. Threats to validity

- **Selection:** public artifacts only, many of them workshop or demo code; programs chosen where we already had cases; few programs per translator.
- **Instrument:**
  - scanner defects, found and fixed (#4163, #4164, #4178, #4193) or still open (#4171). I/O readings for third-party ports depend on the scanner recognising each translator's runtime vocabulary (§4);
  - name-based framework detection;
  - rewrapped det copies inflate line counts (†).
- **Oracle:** GnuCOBOL, our CICS model and Db2 LUW stand in for z/OS (`oracle_assumptions.md`, e.g. C9, D1, C10, X6, M2).
- **Coverage:** hand-written scenarios; SQL faults are injected (#4200), but input-driven branches remain unreached (#4175); third-party ports judged on base runs (49/86, 55/96, 13/22 branches) plus one external fault class (a missing file, which on z/OS usually fails at allocation rather than OPEN).
- **Adapters:** thin and committed separately, but written by us.
- **Versions:** IBM's artifact dates from 2024 and may not match its paper's evaluation; Devin's branches span six months; snapshots are pinned.
- **Authorship:** the translator's author designed the instruments (§1).

## 13. Follow-ups

**Issues:**
- Done: #4170 (fixed in #4178), #4191 (#4193), #4173 and #4181 (#4200).
- Open: #4171, #4172, #4174, #4175, #4179, #4188.

**Next:**
- the survey's 8 fixed-width CBACT01C ports, as a field-by-field tier;
- more external fault classes (truncated records, duplicate keys) for all third-party ports; SENTINEL CBTRN01C/CBTRN03C, which need shipped reader implementations;
- add viniman27's 12,700 inputs as scenarios (licence permitting);
- a z/OS cross-check of the oracle;
- more estates: NIST CCVS85, IBM DBB MortgageApplication, Galasa SimBank;
- invite authors and vendors to run their ports through the harness.

## 14. Reproduction

```sh
# environment: .claude/skills/det-port/SKILL.md
python tests/tools/proof_sweep.py --work <scratch> --jobs 4          # det + model proofs
python tests/tools/det_port.py run carddemo-intcalc --faults all --work <scratch>
python tests/tools/ibm_wca4z_port.py --work <scratch> --junit        # IBM LGACDB01 (fetches @967d00b)
python tests/tools/devin_port.py ...                                 # Devin eval arms (see devin-carddemo-harness.md)
python -m gitgalaxy.galaxyscope <tree>                               # structural readings; one tree per form
```

Pinned third-party commits are in §2 and `devin-carddemo-inventory.json`.

## References

- Kumar et al., *Automated Validation of COBOL to Java Transformation*, ASE 2024, arXiv:2506.10999.
- Hans et al., *Automated Testing of COBOL to Java Transformation*, arXiv:2504.10548.
- Froimovich et al., *Quality Evaluation of COBOL to Java Code Transformation*, arXiv:2507.23356.
- AWS CardDemo; IBM GenApp; IBM CBSA (public sample applications).
- Case studies and records in this repository:
  - `docs/research/lgacdb01-four-way.md`
  - `docs/research/devin-carddemo-survey.md`
  - `docs/research/devin-carddemo-harness.md`
  - `docs/research/third-party-ports-harness.md`
  - `docs/research/devin-cbact01c-harness.md`
  - `docs/language_status/ibm_wca4z_lgacdb01.md`
  - `docs/language_status/construct_correspondence.md`
  - `docs/wiki/05-18-cobol-java-scan-parity.md`
  - `docs/port_invariance_contract.md`
