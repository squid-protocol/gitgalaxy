# Progress

Generated from main at `65a071b8f` by `tests/tools/progress_report.py` (#5280); do not edit. Every
denominator is fixed and every number names its source below. A level is an evidence level, never a bare
claim of correctness: the oracle is GnuCOBOL plus IBM documentation, not z/OS.

## 1. Burned-estate ladder

Fixed denominator: the 129 programs of the 6 burned estates. Source: docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch).

Reachable denominator: 126 programs (129 - 2 - 1). These programs stay in the fixed denominator and in the table; each is reported apart because its blocker is not a translator gap.

| Not reachable for a non-translator reason | Programs | Issue | Reason |
|---|---|---|---|
| source defect (source IBM rejects) | 2: `aws-mainframe-modernization-carddemo/app/cbl/CBEXPORT.cbl`, `aws-mainframe-modernization-carddemo/app/cbl/CBIMPORT.cbl` | #5866 | RECORD KEY names an item defined in WORKING-STORAGE, not in a record of the file; IBM requires it in a record description of that file (Enterprise COBOL Language Reference, RECORD KEY clause) |
| held by an owner ruling or z/OS calibration | 1: `dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl` | #5106 | Language Environment condition handlers (CEEHDLR) refused by name, owner ruling 2026-10-21 |

Entries that no longer hold (the program is above L0): dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epsmpmt.cbl, zecs/Source/ZECS002.asm.

| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 2 | 0 | 0 | 4 | 38 | 0 | 42 (95.5%) | 38 (86.4%) | 0 |
| `cics-async-api-credit-card-application-example` | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 10 (100.0%) | 10 (100.0%) | 0 |
| `cics-banking-sample-application-cbsa` | 31 | 0 | 0 | 0 | 1 | 30 | 0 | 31 (100.0%) | 30 (96.8%) | 0 |
| `cics-genapp` | 31 | 0 | 0 | 0 | 0 | 31 | 0 | 31 (100.0%) | 31 (100.0%) | 0 |
| `dbb-mortgage-application` | 6 | 1 | 0 | 0 | 0 | 5 | 0 | 5 (83.3%) | 5 (83.3%) | 0 |
| `zecs` | 7 | 0 | 0 | 3 | 0 | 4 | 0 | 7 (100.0%) | 4 (57.1%) | 0 |
| **Total** | 129 | 3 | 0 | 3 | 5 | 118 | 0 | 126 (97.7%) | 118 (91.5%) | 0 |

L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 translator
mutants caught (`definition_of_done.md`).

## 2. Components

| Component | Measure | Denominator | Source |
|---|---|---|---|
| Translator | 126 programs translated whole | 129 burned programs | docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch) |
| CICS commands | 60 modelled on both runtimes | 68 commands a burned program uses (7 unlisted or unparsed forms, counted as not modelled) | docs/language_status/cics_spec_status.json (cics_spec_status.py) |
| COBOL runtime rules | 87 MATCHED, 23 DIFFERS, 63 ASSUMED, 13 REFUSED; 0 measured on z/OS | 186 rules | docs/language_status/cobolrt_rules.json |
| Mutation | 3559 killed = 86.8% adjusted (68.0% raw) | 4100 adjusted, 5232 raw mutants over 59 ports | docs/language_status/mutation_scores.json |
| CICS crucible | 63 programs, 179 scenarios | pinned at `v0.10.0 (01e11fe6)` | tests/cics_crucible/coverage.json |
| Estate crucible | 61 of 63 horrors pass | pinned at `v0.5.0` | tests/estate_crucible/baseline.json |

CICS commands not modelled on both runtimes: `(unlisted) ASKTIME NOHANDLE`, `(unlisted) GET`, `(unlisted) INQUIRE`, `(unlisted) INQUIRE URIMAP`, `(unlisted) SET`, `(unlisted) SYNCPOINT NOHANDLE`, `(unparsed)`, `SOAPFAULT CREATE`.

Frontier context, not the denominator above: the whole CICS spec has 257 entries, 103 full, 2 engine-only and 152 refused by name.

## 3. Eras

Source: tests/fixtures/feature_inventory/<estate>.json (era_tags.py). Programs per era, with how many are at L2+ and L4+.

| Era | Programs | L2+ | L4+ |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 1 | 9 | 9 | 8 |
| 2 | 70 | 70 | 69 |
| 3 | 16 | 14 | 11 |
| 4 | 21 | 20 | 19 |
| untagged | 13 | 13 | 11 |

## 4. Core burn-down

Source: GitHub issues by scope:* label (progress_issues_cache.json), as of 2026-10-29T17:41:43Z.

- `scope:core`: 17 open, 192 closed.
- Milestone 28: 9 open, 100 closed.
- Last 7 days: 14 opened, 33 closed, net +19 closed.
- ETA (open / net closure rate): **6 days**.

## 5. Gap Atlas

Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.

- `scope:frontier`: 6 found in the last 7 days, 198 in total (83 open, 115 closed).
- Milestone 30 (Gap Atlas): 50 issues.
- `scope:sweep`: 9 open, 89 closed.
- `scope:infra`: 33 open, 230 closed.
