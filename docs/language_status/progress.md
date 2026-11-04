# Progress

Generated from main at `52de459f3` by `tests/tools/progress_report.py` (#5280); do not edit. Every
denominator is fixed and every number names its source below. A level is an evidence level, never a bare
claim of correctness: the oracle is GnuCOBOL plus IBM documentation, not z/OS.

## 1. Burned-estate ladder

Fixed denominator: the 129 programs of the 6 burned estates. Source: docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch).

Reachable denominator: 126 programs (129 - 2 - 1). These programs stay in the fixed denominator and in the table; each is reported apart because its blocker is not a translator gap.

| Not reachable for a non-translator reason | Programs | Issue | Reason |
|---|---|---|---|
| source defect (source IBM rejects) | 2: `aws-mainframe-modernization-carddemo/app/cbl/CBEXPORT.cbl`, `aws-mainframe-modernization-carddemo/app/cbl/CBIMPORT.cbl` | #5866 | RECORD KEY names an item defined in WORKING-STORAGE, not in a record of the file; IBM requires it in a record description of that file (Enterprise COBOL Language Reference, RECORD KEY clause) |
| refused by design (owner ruling: outside what the port proves) | 1: `dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl` | #5106 | its 7 holes are Language Environment condition handling (CEEHDLR / CEEHDLU and the CEE3SRP recovery point, refused by the owner's 2026-10-21 ruling) and CICS web services (SOAPFAULT CREATE), which no oracle backs, plus procedure pointers (SET TO ENTRY) and national / DBCS text, breadth work no ladder program needs (#5042, #4664); owner ruling 2026-11-03: no model built on assumptions alone, the program stays at L0 |

Entries that no longer hold (the program is above L0): dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epsmpmt.cbl, zecs/Source/ZECS002.asm.

| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 2 | 0 | 0 | 0 | 41 | 1 | 42 (95.5%) | 42 (95.5%) | 1 |
| `cics-async-api-credit-card-application-example` | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 10 (100.0%) | 10 (100.0%) | 0 |
| `cics-banking-sample-application-cbsa` | 31 | 0 | 0 | 0 | 1 | 30 | 0 | 31 (100.0%) | 30 (96.8%) | 0 |
| `cics-genapp` | 31 | 0 | 0 | 0 | 0 | 31 | 0 | 31 (100.0%) | 31 (100.0%) | 0 |
| `dbb-mortgage-application` | 6 | 1 | 0 | 0 | 0 | 5 | 0 | 5 (83.3%) | 5 (83.3%) | 0 |
| `zecs` | 7 | 0 | 0 | 0 | 0 | 7 | 0 | 7 (100.0%) | 7 (100.0%) | 0 |
| **Total** | 129 | 3 | 0 | 0 | 1 | 124 | 1 | 126 (97.7%) | 125 (96.9%) | 1 |

L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 every
surviving translator mutant accounted for (`definition_of_done.md`).

Test estates, written to break the translator and so never in the denominator above:

| Test estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|---|---|
| `cics-crucible` | 85 | 0 | 1 | 2 | 0 | 82 | 0 |

## L5: what it rests on

L5 has no score bar: it needs every surviving mutant of the det port's sample accounted for, on current inputs.
*Ready* passes on its last measurement and waits for a refresh, so it is not L5. *Raw* is mutants caught of those
judged; *sample* is mutants judged of those the program has. Claims are the reviewed survivor statements.

| Estate | Programs | Measured | L5 | Ready | Raw caught | Sample | Equivalent | Unreachable |
|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 25 | 1 | 0 | 57.0% (3269 of 5731) | 23.8% (7239 of 30355) | 2081 | 250 |
| `cics-async-api-credit-card-application-example` | 10 | 10 | 0 | 0 | 94.4% (5737 of 6079) | 100.0% (6239 of 6239) | 272 | 70 |
| `cics-banking-sample-application-cbsa` | 31 | 6 | 0 | 0 | 48.8% (1334 of 2732) | 100.0% (2854 of 2854) | 894 | 375 |
| `cics-genapp` | 31 | 0 | 0 | 0 | not measured | not measured | 0 | 0 |
| `dbb-mortgage-application` | 6 | 2 | 0 | 0 | 52.7% (155 of 294) | 46.6% (300 of 644) | 0 | 0 |
| `zecs` | 7 | 4 | 0 | 0 | 46.7% (1169 of 2503) | 100.0% (2601 of 2601) | 869 | 373 |
| **Total** | 129 | 47 | 1 | 0 | 67.3% (11664 of 17339) | 45.0% (19233 of 42693) | 4116 | 1068 |

## Capability ledger

Counted from the code by `capability_ledger.py`. A blank denominator means no honest list exists to count against.
*Match* means IBM's documentation.

| Group | Capability | State | Count | What exists |
|---|---|---|---|---|
| COBOL language | Statements and data | Partial | 60 of 107 rules match IBM | statements, numerics, editing, functions, files |
| COBOL language | Runtime spec tables | Works | no denominator | 8 tables, 71 rules, 153 test vectors, 162 matrix cells (part of the rules above: depth, not extra rules) |
| CICS | Commands the estates use | Partial | 60 of 68 modelled on both runtimes | programs in the burned estates |
| CICS | All CICS commands | Partial | 107 of 257 modelled; the rest refused by name | every command IBM's reference lists |
| CICS | Command options | Partial | 954 of 1141 accepted | 187 refused by name |
| CICS | Macro resource tables | Reads only | no denominator | FCT, PCT, PPT, DCT, TST, SIT, SRT, JCT, TCT, MCT, PLT, DSNCRCT (12 tables read into the resource map; not run) |
| Data and messaging | Db2 embedded SQL | Partial | 12 of 14 rules match IBM | 8 verbs refused by name |
| Data and messaging | LE callable services | Partial | 12 of 19 rules match IBM | date, time and condition services |
| Data and messaging | VSAM KSDS | Works | no denominator | keyed read, write and browse, in 16 equivalence cases |
| Data and messaging | VSAM alternate index | Partial | no denominator | keyed access through a path |
| Data and messaging | VSAM ESDS | Partial | no denominator | browse by relative byte address under CICS |
| Data and messaging | VSAM RRDS | Refused | no denominator | relative record access (refused by name, not missing) |
| Data and messaging | IBM MQ | Partial | 5 of 25 calls modelled | 0 of 7 rules match IBM; CICS calls only |
| Data and messaging | IMS DL/I | Partial | 0 of 16 rules match IBM | calls run on our own model, so no rule matches yet |
| Batch | DFSORT | Partial | no denominator | SORT, MERGE, COPY, INCLUDE, OMIT, OUTREC; 4 key formats (2 proved sort cases) |
| Batch | IDCAMS, IEBGENER | Partial | no denominator | REPRO and plain copies; other commands refused |
| Batch | JCL jobs | Partial | no denominator | 1 multi-step job case (steps are wired by the case, not read from JCL) |
| Other languages | HLASM assembler | Partial | no denominator | 21 opcodes, the zECS subset |
| Other languages | BMS maps | Works | no denominator | SEND MAP, RECEIVE MAP |
| Other languages | PL/I | Nothing | no denominator | scanned, never translated (no translator code) |

z/OS: 0 of 191 rules measured. Register of named limits: 144 entries, 74 refuse by name.

## 2. Components

| Component | Measure | Denominator | Source |
|---|---|---|---|
| Translator | 126 programs translated whole | 129 burned programs | docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch) |
| CICS commands | 60 modelled on both runtimes | 68 commands a burned program uses (7 unlisted or unparsed forms, counted as not modelled) | docs/language_status/cics_spec_status.json (cics_spec_status.py) |
| COBOL runtime rules | 91 MATCHED, 23 DIFFERS, 63 ASSUMED, 14 REFUSED; 0 measured on z/OS | 191 rules | docs/language_status/cobolrt_rules.json |
| Mutation, hand ports (not the translator) | 3559 killed = 86.8% adjusted (68.0% raw) | 4100 adjusted, 5232 raw mutants over 59 ports | docs/language_status/mutation_scores.json |
| CICS crucible | 85 programs, 220 scenarios | pinned at `v0.12.0 (904e9877)` | tests/cics_crucible/coverage.json |
| Estate crucible | 88 of 90 horrors pass | pinned at `v0.6.0` | tests/estate_crucible/baseline.json |

CICS commands not modelled on both runtimes: `(unlisted) ASKTIME NOHANDLE`, `(unlisted) GET`, `(unlisted) INQUIRE`, `(unlisted) INQUIRE URIMAP`, `(unlisted) SET`, `(unlisted) SYNCPOINT NOHANDLE`, `(unparsed)`, `SOAPFAULT CREATE`.

Frontier context, not the denominator above: the whole CICS spec has 257 entries, 107 full, 0 engine-only and 150 refused by name.

## 3. Eras

Source: tests/fixtures/feature_inventory/<estate>.json (era_tags.py). Programs per era, with how many are at L2+ and L4+.

| Era | Programs | L2+ | L4+ |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 1 | 9 | 9 | 9 |
| 2 | 70 | 70 | 70 |
| 3 | 16 | 14 | 13 |
| 4 | 21 | 20 | 20 |
| untagged | 13 | 13 | 13 |

## 4. Core burn-down

Source: GitHub issues by scope:* label (progress_issues_cache.json), as of 2026-11-04T09:25:08Z.

- `scope:core`: 9 open, 210 closed.
- Milestone 28: 4 open, 108 closed.
- Last 7 days: 15 opened, 24 closed, net +9 closed.
- ETA (open / net closure rate): **7 days**.

## 5. Gap Atlas

Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.

- `scope:frontier`: 6 found in the last 7 days, 202 in total (76 open, 126 closed).
- Milestone 30 (Gap Atlas): 50 issues.
- `scope:sweep`: 4 open, 96 closed.
- `scope:infra`: 26 open, 247 closed.
