# Progress

Generated from main at `dec1539e2` by `tests/tools/progress_report.py` (#5280); do not edit. Every
denominator is fixed and every number names its source below. A level is an evidence level, never a bare
claim of correctness: the oracle is GnuCOBOL plus IBM documentation, not z/OS.

## 1. Burned-estate ladder

Fixed denominator: the 129 programs of the 6 burned estates. Source: docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch).

Reachable denominator: 125 programs (129 - 2 - 1 - 1). These programs stay in the fixed denominator and in the table; each is reported apart because its blocker is not a translator gap.

| Not reachable for a non-translator reason | Programs | Issue | Reason |
|---|---|---|---|
| source defect (source IBM rejects) | 2: `aws-mainframe-modernization-carddemo/app/cbl/CBEXPORT.cbl`, `aws-mainframe-modernization-carddemo/app/cbl/CBIMPORT.cbl` | #5866 | RECORD KEY names an item defined in WORKING-STORAGE, not in a record of the file; IBM requires it in a record description of that file (Enterprise COBOL Language Reference, RECORD KEY clause) |
| refused whole: not COBOL | 1: `zecs/Source/ZECS002.asm` | #5859 | CICS Assembler member; the HLASM front end refuses it at DC 08XL01'40' (slice 3 of #5859 lowers it) |
| held by an owner ruling or z/OS calibration | 1: `dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl` | #5106 | Language Environment condition handlers (CEEHDLR) refused by name, owner ruling 2026-10-21 |

Entries that no longer hold (the program is above L0): dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epsmpmt.cbl.

| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 2 | 0 | 0 | 4 | 38 | 0 | 42 (95.5%) | 38 (86.4%) | 0 |
| `cics-async-api-credit-card-application-example` | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 10 (100.0%) | 10 (100.0%) | 0 |
| `cics-banking-sample-application-cbsa` | 31 | 0 | 0 | 0 | 4 | 27 | 0 | 31 (100.0%) | 27 (87.1%) | 0 |
| `cics-genapp` | 31 | 0 | 1 | 0 | 0 | 30 | 0 | 30 (96.8%) | 30 (96.8%) | 0 |
| `dbb-mortgage-application` | 6 | 1 | 0 | 0 | 0 | 5 | 0 | 5 (83.3%) | 5 (83.3%) | 0 |
| `zecs` | 7 | 1 | 0 | 2 | 0 | 4 | 0 | 6 (85.7%) | 4 (57.1%) | 0 |
| **Total** | 129 | 4 | 1 | 2 | 8 | 114 | 0 | 124 (96.1%) | 114 (88.4%) | 0 |

L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 translator
mutants caught (`definition_of_done.md`).

## 2. Components

| Component | Measure | Denominator | Source |
|---|---|---|---|
| Translator | 125 programs translated whole | 129 burned programs | docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch) |
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
| 2 | 70 | 70 | 67 |
| 3 | 16 | 14 | 11 |
| 4 | 21 | 19 | 17 |
| untagged | 13 | 12 | 11 |

## 4. Core burn-down

Source: GitHub issues by scope:* label (progress_issues_cache.json), as of 2026-10-28T10:37:49Z.

- `scope:core`: 19 open, 186 closed.
- Milestone 28: 6 open, 98 closed.
- Last 7 days: 20 opened, 33 closed, net +13 closed.
- ETA (open / net closure rate): **10 days**.

## 5. Gap Atlas

Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.

- `scope:frontier`: 8 found in the last 7 days, 197 in total (84 open, 113 closed).
- Milestone 30 (Gap Atlas): 49 issues.
- `scope:sweep`: 8 open, 89 closed.
- `scope:infra`: 29 open, 227 closed.
