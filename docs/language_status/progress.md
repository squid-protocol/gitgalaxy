# Progress

Generated from main at `d9b91b805` by `tests/tools/progress_report.py` (#5280); do not edit. Every
denominator is fixed and every number names its source below. A level is an evidence level, never a bare
claim of correctness: the oracle is GnuCOBOL plus IBM documentation, not z/OS.

## 1. Burned-estate ladder

Fixed denominator: the 129 programs of the 6 burned estates. Source: docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch).

Reachable denominator: 123 programs (129 - 2 - 2 - 2). These programs stay in the fixed denominator and in the table; each is reported apart because its blocker is not a translator gap.

| Not reachable for a non-translator reason | Programs | Issue | Reason |
|---|---|---|---|
| source defect (source IBM rejects) | 2: `aws-mainframe-modernization-carddemo/app/cbl/CBEXPORT.cbl`, `aws-mainframe-modernization-carddemo/app/cbl/CBIMPORT.cbl` | #5866 | RECORD KEY names an item defined in WORKING-STORAGE, not in a record of the file; IBM requires it in a record description of that file (Enterprise COBOL Language Reference, RECORD KEY clause) |
| refused whole: not COBOL | 2: `zecs/Source/ZECS002.asm`, `zecs/Source/ZECSNC.asm` | #5859 | CICS Assembler member; the translator is a COBOL translator |
| held by an owner ruling or z/OS calibration | 2: `dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl`, `dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epsmpmt.cbl` | #5106, #5867 | Language Environment condition handlers (CEEHDLR) refused by name, owner ruling 2026-10-21; floating-point power and FUNCTION ANNUITY need captured z/OS results (oracle_assumptions.md C6) |

| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 2 | 0 | 0 | 8 | 34 | 0 | 42 (95.5%) | 34 (77.3%) | 0 |
| `cics-async-api-credit-card-application-example` | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 10 (100.0%) | 10 (100.0%) | 0 |
| `cics-banking-sample-application-cbsa` | 31 | 0 | 0 | 1 | 11 | 19 | 0 | 31 (100.0%) | 19 (61.3%) | 0 |
| `cics-genapp` | 31 | 0 | 1 | 0 | 1 | 29 | 0 | 30 (96.8%) | 29 (93.5%) | 0 |
| `dbb-mortgage-application` | 6 | 2 | 2 | 1 | 0 | 1 | 0 | 2 (33.3%) | 1 (16.7%) | 0 |
| `zecs` | 7 | 2 | 0 | 1 | 1 | 3 | 0 | 5 (71.4%) | 3 (42.9%) | 0 |
| **Total** | 129 | 6 | 3 | 3 | 21 | 96 | 0 | 120 (93.0%) | 96 (74.4%) | 0 |

L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 translator
mutants caught (`definition_of_done.md`).

## 2. Components

| Component | Measure | Denominator | Source |
|---|---|---|---|
| Translator | 123 programs translated whole | 129 burned programs | docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch) |
| CICS commands | 60 modelled on both runtimes | 68 commands a burned program uses (7 unlisted or unparsed forms, counted as not modelled) | docs/language_status/cics_spec_status.json (cics_spec_status.py) |
| COBOL runtime rules | 87 MATCHED, 23 DIFFERS, 63 ASSUMED, 13 REFUSED; 0 measured on z/OS | 186 rules | docs/language_status/cobolrt_rules.json |
| Mutation | 3565 killed = 88.3% adjusted (68.5% raw) | 4039 adjusted, 5207 raw mutants over 59 ports | docs/language_status/mutation_scores.json |
| CICS crucible | 63 programs, 179 scenarios | pinned at `v0.10.0 (01e11fe6)` | tests/cics_crucible/coverage.json |
| Estate crucible | 60 of 60 horrors pass | pinned at `v0.4.0` | tests/estate_crucible/baseline.json |

CICS commands not modelled on both runtimes: `(unlisted) ASKTIME NOHANDLE`, `(unlisted) GET`, `(unlisted) INQUIRE`, `(unlisted) INQUIRE URIMAP`, `(unlisted) SET`, `(unlisted) SYNCPOINT NOHANDLE`, `(unparsed)`, `SOAPFAULT CREATE`.

Frontier context, not the denominator above: the whole CICS spec has 257 entries, 102 full, 2 engine-only and 153 refused by name.

## 3. Eras

Source: tests/fixtures/feature_inventory/<estate>.json (era_tags.py). Programs per era, with how many are at L2+ and L4+.

| Era | Programs | L2+ | L4+ |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 1 | 9 | 9 | 8 |
| 2 | 70 | 69 | 54 |
| 3 | 16 | 14 | 9 |
| 4 | 21 | 19 | 16 |
| untagged | 13 | 9 | 9 |

## 4. Core burn-down

Source: GitHub issues by scope:* label (progress_issues_cache.json), as of 2026-10-26T21:48:04Z.

- `scope:core`: 23 open, 177 closed.
- Milestone 28: 6 open, 97 closed.
- Last 7 days: 20 opened, 35 closed, net +15 closed.
- ETA (open / net closure rate): **11 days**.

## 5. Gap Atlas

Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.

- `scope:frontier`: 9 found in the last 7 days, 198 in total (87 open, 111 closed).
- Milestone 30 (Gap Atlas): 48 issues.
- `scope:sweep`: 8 open, 89 closed.
- `scope:infra`: 38 open, 218 closed.
