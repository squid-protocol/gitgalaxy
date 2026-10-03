# COBOL → Java translation, observed: one harness, one scanner, many translators

*An observational, post-hoc study. Draft, 2026-10-03. Sections marked **pending** wait on in-flight work and are labelled with what they will add.*

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
4. **Behaviour and structure are separable.** A restructured port can match the COBOL byte for byte on base runs while sharing almost none of its structure.
5. **What differs most is verifiability:**
   - a deterministic translator gives the same code every run, while 26 agent sessions on one program share under a fifth of their class names;
   - error paths centralised into a framework could not be exercised by our harness, while literal ports keep them drivable.
6. **Validation practice across the field ranges widely,** from none, through self-written tests, to executed references. Only executed comparison settled any question here.

The study is uncontrolled and small. We list what it cannot establish (§9) and threats to its validity (§10).

## 1. Positioning: blameless and post hoc

- **What this is:** I built something, noticed others had built things for the same public programs, and measured them all the same way, afterwards. Nobody was asked to take part, and most subjects are workshop exercises, research prototypes or demos. Each is judged against what it attempted.
- **Player and referee.** The author of the translator also built the instruments. Our mitigations:
  - **open, pinned tooling:** every artifact is fetched at a recorded commit, and every adapter is committed separately;
  - **a public register of the oracle's limits** (`docs/language_status/oracle_assumptions.md`);
  - **the referee's verdicts went against its author too.** It found a bug in our own det port (#4181) and corrected our own published figures (det size ×5 → ×4.2; the "model-port TODOs" were mostly our generator's scaffold, #4179). It also passed Devin's best ports on base runs.
- **The axis is not "LLM vs deterministic".** Several commercial translators are rule-based (AWS Blu Age / AWS Transform's refactor engine, SoftwareMining, Heirloom, Micro Focus), and an LLM can write literal code. The axes that matter in the data are **how much COBOL structure is kept** and **how equivalence is established**.

## 2. Subjects

| Subject | Translator | Programs | Pinned at | Licence |
|---|---|---|---|---|
| Det ports | GitGalaxy deterministic translator | 48 of 50 cases proven (CardDemo 27, CBSA 8, GenApp 13 programs; 17 Db2 cases) | main | repo licence |
| Model ports | claude-sonnet-5-5 in the porting loop | 23 committed (+3 in review, #4187) | main | estate licences |
| IBM WCA4Z | LLM, IBM research artifact (2024) | GenApp LGACDB01, one paragraph | `sandeephans/validation-c2j@967d00b` | none stated |
| Devin | Agent, workshop labs (Mar–Sep 2026) | 67 branches; CBACT01C ×26 distinct; eval arms A/B on CBACT01C, CBACT04C, CBTRN02C | inventory JSON (per-branch SHAs) | Apache-2.0 |
| SENTINEL IDE (NOAH Labs) | Commercial tool, "1:1 mapping of COBOL programs to Java classes" | all CardDemo, including the IMS/MQ extension | `noahlabsai/aws-mainframe-modernization-carddemo-JAVA@47af18641ee6` | README badge says Apache-2.0; no LICENSE file |
| lasserre-consulting | LLM agent (Claude Sonnet), re-architecture to Spring/JPA/Batch/JMS | all CardDemo | `@bcdb72316291` | none |
| Lightyear | Evidence-first "dark factory" | CBACT04C, COACTVWC, a PL/I authorization | `howardweale/lightyear-carddemo-modernization@e24d77822f70` | none |
| viniman27 | Academic study, not a port | API recovery on CBTRN02C, CBACT04C, CBTRN03C | 2026-09-16 | none |
| xavierxmorris | Read-only .NET slice, not a port | data display only | `@836a2bd95306` | Apache-2.0 |

Three further repositories in the sweep were empty or stubs. Repositories without a licence are measured, never redistributed, and quoted only in short excerpts.

## 3. Instruments

**Equivalence harness.** GnuCOBOL 3 (IBM dialect, EBCDIC signs, TRUNC(STD)), a CICS model, and IBM Db2 Community Edition through our precompiler stub. It compares events, the COMMAREA, datasets and tables byte for byte, with per-scenario fault injection (file statuses, CICS conditions). How the reference may differ from z/OS is registered in `oracle_assumptions.md` (e.g. C9 pointer width, D1 collation, X6 refused WRITEQ, M2 no SQL fault injection). Third-party code runs unmodified behind a thin, separately committed adapter (`ibm_wca4z_port.py`, `devin_port.py`).

**GitGalaxy scanner.** It reads COBOL and Java on the same axes: functions, branch points, state mutations, I/O, IPC, size and tokens, complexity, debt. This work found and fixed scanner defects, and the readings here are after the fixes where stated:
- Java `?`/`:` overcounted as branches (#4170, fixed in #4178);
- cobolrt calls not seen as I/O (#4163);
- det ports excluded as generated noise (#4164).

Still open:
- commented-out statements not counted (#4171);
- compound JDK I/O classes (`FileInputStream`, `BufferedReader`) not counted (#4191; **pending**, agent N).

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
| I/O | — (reads 0; scanner gap #4191) | 0.90 | — | 0.75 |

**Pending (#4191, agent N):** SENTINEL's I/O ρ after the scanner recognises compound JDK I/O classes.

## 5. Observation B: a structural spectrum, readable without execution

Whole CardDemo estate (28 programs where available):

| Strategy | Example | Code lines | Branches | I/O | Size against COBOL |
|---|---|---|---|---|---|
| COBOL | — | 17,279 | 2,336 | 187 | 1 |
| Literal, byte-level storage | det | 64,899 † | 6,328 | 124 | ≈3.8 † |
| Literal, text I/O | SENTINEL | 7,630 | 1,469 | 26 ‡ | 0.44 |
| Re-architected (Spring/JPA/Batch/JMS) | lasserre | 1,137 | 34 | 30 | 0.07 |

† Measured on det copies with long lines rewrapped for scanning, which inflates line counts by a median of ~19% (wiki 05-18). Branch and token readings are unaffected.
‡ Undercounted (#4191).

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
| Det ports | 48 of 50 cases | 7–29 runs per batch case, with fault injection; 705 scenarios across the sweep | proven | 2 not proven on purpose (#4085, D1). Coverage modest on some CICS/Db2 programs (LGACDB01 6/14 branches) |
| Model ports | 23 committed | per case, with faults | proven | 3 more pending review (#4187). INQACC, XFRFUN and LGUPDB01 unprovable through the harness gap #4188 |
| IBM WCA4Z | LGACDB01 INSERT-CUSTOMER, in our det task | 4 | **not equivalent on any** | Db2 −4461: DATEOFBIRTH never bound (`// ps.setDate(4, …)`); failure swallowed (`// caReturnCode = 90;`). The published JUnit doesn't compile against the published Java, and the recorded run is 2 skipped passes / 2 failures, against the 4/4 reported. Their test 2 asserts DATEOFBIRTH and would likely flag the defect if it ran. The artifacts may come from a different version |
| Devin arm A (COBOL only) | CBACT04C / CBTRN02C | base run, 6 JVM environments each | equal in default/tr/de/hi; differs in ar-EG/th-TH | `String.format` without a locale writes non-ASCII digits (`BatchContext:45`, `Cbact04c:156`, `Cbtrn02c:42,119`) |
| Devin arm B (+ AWS Transform analysis) | CBACT04C / CBTRN02C | same | CBACT04C as A; CBTRN02C equal in all 6 | one locale defect (`Cbact04c:67`) |
| Lightyear | CBACT04C | **pending (agent M)** | — | Lightyear reports equivalence as "unobserved"; this would be the first observation |
| SENTINEL | CardDemo batch programs | **pending (agent M)** | — | UTF-8 text I/O, so probably a field-level, not byte-level, comparison |

**Coverage asymmetry.** Devin's ports have no hook for injecting file statuses, so they were judged on base runs only: 49/86 (CBACT04C) and 55/96 (CBTRN02C) branches, against 85/86 and 95/96 for our ports' fault-injected proofs.

**Our own failures, found by the same harness:**
- **#4181:** the det port marshals `LINK LGSTSQ COMMAREA(ERROR-MSG)` past its 71 bytes, on an error path none of our proofs reach.
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

**Pending (agent M):** the external-fault experiment, which creates failures from outside with no code hook (a missing input, a truncated record, a duplicate key). It will measure what each port actually does on those paths, against the COBOL.

## 9. Pros and cons by strategy

| Strategy (examples) | Pros | Cons |
|---|---|---|
| **Literal, byte-level (det)** | Path-by-path verifiable (fault injection reaches 85/86, 95/96 branches); reproducible byte for byte; paragraph lineage keeps runbooks, abend codes and audit trails; regenerate-and-diff on COBOL change | ×3.8 size (×4.2 as emitted, by file median); COBOL-shaped Java; depends on the cobolrt runtime; coverage limited by hand-written scenarios (SQL errors unreached, #4173) |
| **Literal, native fields (SENTINEL)** | Keeps structure (ρ 0.88–0.91) at 0.44× size; keeps file-status codes and error messages | Text I/O instead of record bytes (byte equivalence likely lost, pending); no parity claim found; reproducibility unknown |
| **Model-written under proof (our loop)** | Idiomatic; near-COBOL size (×1.09); proven on its scenarios | Not reproducible; leftover scaffold TODOs (#4179); LINKed-program harness gap (#4188) |
| **Agent-restructured (Devin, Lightyear)** | Idiomatic and small program classes; the best runs match base-run behaviour byte for byte (Devin eval arms) | Each session a new codebase (Jaccard 0.18); error handling centralised and not reachable by our fault injection; mostly self-written tests; locale defects |
| **Re-architected (lasserre)** | Smallest (×0.07); modern platform services (JPA, Batch, JMS) | Program boundaries and output contracts replaced; equivalence checked only through lossy normalisation |
| **Research artifact (IBM WCA4Z, 2024)** | Path-complete test generation (a capability we lack, #4175); real z/OS reference | Paragraph scope; mocked resources; published artifacts inconsistent with the reported result; failed against real Db2 |

**Maintenance and onboarding (an argument, not a measurement).** A literal port keeps the map an organisation already has: paragraph names, error messages, abend codes. A restructured port starts each team on a new design, and our variance data shows each agent session produces a different one. The counterweight: teams that will never read the COBOL may prefer idiomatic code. The data supports a sequence (literal and proven first, then restructured under proof), not a winner.

## 10. What the data lets us state, and what it doesn't

**Supported:**
1. One scanner places translations on a structural spectrum without executing them (§5).
2. Paragraph-level structural rank agreement is a signature of literal translation, seen in two independent literal translators and absent in restructured ones (§4, §5).
3. Translation size is driven by data representation more than by structural fidelity (§5).
4. Byte-level base-run equivalence is reachable by restructured ports (§6).
5. The published IBM LGACDB01 artifact is not equivalent to its COBOL against real Db2 (§6).
6. Repeated agent sessions on one program produce structurally divergent code, while the deterministic translator is reproducible (§7).
7. Validation practice in public work varies widely and is mostly not execution-based (§8).

**Not supported:**
- that any translator or strategy is better overall;
- generalisation beyond these programs, estates and snapshots;
- that restructured ports' error paths are wrong (they are unexercised, pending the fault experiment);
- that our reference is z/OS-exact;
- that commercial products today behave like these public artifacts.

## 11. Threats to validity

- **Selection:** public artifacts only, many of them workshop or demo code; programs chosen where we already had cases; few programs per translator.
- **Instrument:**
  - scanner defects, found and fixed (#4163, #4164, #4178) or still open (#4171, #4191);
  - name-based framework detection;
  - rewrapped det copies inflate line counts (†).
- **Oracle:** GnuCOBOL, our CICS model and Db2 LUW stand in for z/OS (`oracle_assumptions.md`, e.g. C9, D1, C10, X6, M2).
- **Coverage:** hand-written scenarios; no SQL fault injection (#4173); third-party ports judged on base runs only.
- **Adapters:** thin and committed separately, but written by us.
- **Versions:** IBM's artifact dates from 2024 and may not match its paper's evaluation; Devin's branches span six months; snapshots are pinned.
- **Authorship:** the translator's author designed the instruments (§1).

## 12. Follow-ups

**Issues:**
- #4170 (fixed), #4171, #4172, #4173, #4174, #4175, #4179, #4181, #4188, #4191.

**Pending in this study:**
- SENTINEL I/O after #4191;
- Lightyear CBACT04C and SENTINEL batch programs through the harness;
- the external-fault experiment.

**Next:**
- complete CBACT01C (COBDATFT model, register entries C10/L3/F3) and judge Devin's 9 byte-comparable CBACT01C ports;
- add viniman27's 12,700 inputs as scenarios (licence permitting);
- a z/OS cross-check of the oracle;
- more estates: NIST CCVS85, IBM DBB MortgageApplication, Galasa SimBank;
- invite authors and vendors to run their ports through the harness.

## 13. Reproduction

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
  - `docs/language_status/ibm_wca4z_lgacdb01.md`
  - `docs/language_status/construct_correspondence.md`
  - `docs/wiki/05-18-cobol-java-scan-parity.md`
  - `docs/port_invariance_contract.md`
