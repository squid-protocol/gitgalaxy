# Progress

Generated from main at `60bb86294` by `tests/tools/progress_report.py` (#5280); do not edit. Every
denominator is fixed and every number names its source below. A level is an evidence level, never a bare
claim of correctness: the oracle is GnuCOBOL plus IBM documentation, not z/OS.

## 1. Burned-estate ladder

Fixed denominator: the 129 programs of the 6 burned estates. Source: docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch).

| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `aws-mainframe-modernization-carddemo` | 44 | 6 | 4 | 5 | 14 | 15 | 0 | 34 (77.3%) | 15 (34.1%) | 0 |
| `cics-async-api-credit-card-application-example` | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 10 (100.0%) | 10 (100.0%) | 0 |
| `cics-banking-sample-application-cbsa` | 31 | 0 | 0 | 13 | 12 | 6 | 0 | 31 (100.0%) | 6 (19.4%) | 0 |
| `cics-genapp` | 31 | 0 | 0 | 7 | 19 | 5 | 0 | 31 (100.0%) | 5 (16.1%) | 0 |
| `dbb-mortgage-application` | 6 | 2 | 2 | 1 | 0 | 1 | 0 | 2 (33.3%) | 1 (16.7%) | 0 |
| `zecs` | 7 | 3 | 1 | 1 | 1 | 1 | 0 | 3 (42.9%) | 1 (14.3%) | 0 |
| **Total** | 129 | 11 | 7 | 27 | 46 | 38 | 0 | 111 (86.0%) | 38 (29.5%) | 0 |

L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 translator
mutants caught (`definition_of_done.md`).

## 2. Components

| Component | Measure | Denominator | Source |
|---|---|---|---|
| Translator | 118 programs translated whole | 129 burned programs | docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch) |
| CICS commands | 60 modelled on both runtimes | 68 commands a burned program uses (7 unlisted or unparsed forms, counted as not modelled) | docs/language_status/cics_spec_status.json (cics_spec_status.py) |
| COBOL runtime rules | 84 MATCHED, 23 DIFFERS, 56 ASSUMED, 14 REFUSED; 0 measured on z/OS | 177 rules | docs/language_status/cobolrt_rules.json |
| Mutation | 2534 killed = 82.6% adjusted (66.3% raw) | 3066 adjusted, 3823 raw mutants over 53 ports | docs/language_status/mutation_scores.json |
| CICS crucible | 57 programs, 159 scenarios | pinned at `v0.9.0 (3ca75ae0)` | tests/cics_crucible/coverage.json |
| Estate crucible | 60 of 60 horrors pass | pinned at `v0.4.0` | tests/estate_crucible/baseline.json |

CICS commands not modelled on both runtimes: `(unlisted) ASKTIME NOHANDLE`, `(unlisted) GET`, `(unlisted) INQUIRE`, `(unlisted) INQUIRE URIMAP`, `(unlisted) SET`, `(unlisted) SYNCPOINT NOHANDLE`, `(unparsed)`, `SOAPFAULT CREATE`.

Frontier context, not the denominator above: the whole CICS spec has 257 entries, 100 full, 2 engine-only and 155 refused by name.

## 3. Eras

Source: tests/fixtures/feature_inventory/<estate>.json (era_tags.py). Programs per era, with how many are at L2+ and L4+.

| Era | Programs | L2+ | L4+ |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 1 | 9 | 5 | 0 |
| 2 | 70 | 67 | 21 |
| 3 | 16 | 12 | 0 |
| 4 | 21 | 18 | 9 |
| untagged | 13 | 9 | 8 |

## 4. Core burn-down

Source: GitHub issues by scope:* label (progress_issues_cache.json), as of 2026-10-21T04:10:20Z.

- `scope:core`: 29 open, 154 closed.
- Milestone 28: 13 open, 84 closed.
- Last 7 days: 43 opened, 54 closed, net +11 closed.
- ETA (open / net closure rate): **18 days**.

## 5. Gap Atlas

Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.

- `scope:frontier`: 17 found in the last 7 days, 191 in total (91 open, 100 closed).
- Milestone 30 (Gap Atlas): 42 issues.
- `scope:sweep`: 15 open, 78 closed.
- `scope:infra`: 54 open, 187 closed.
