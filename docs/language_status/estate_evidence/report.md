# Estate evidence report

Rolled up from the per-program evidence records (#4048, #4054). A level is evidence, not a verdict: the oracle is GnuCOBOL plus gitgalaxy's CICS / LE / Db2 models (a crucible port: hand-written expected logs), not IBM z/OS. See docs/language_status/oracle_assumptions.md.

## Ladder

- **E0** no record
- **E1** recorded, not executed-equivalent or holes
- **E2** executed equivalent
- **E3** executed equivalent, full coverage
- **E4** executed equivalent, full coverage, mutants accounted for

## All reported estates

- Programs: 49; at E0 0, E1 6, E2 22, E3 21, E4 0; executed equivalent or above (E2+): 43/49 (87.8%).
- Coverage over the programs with a record: paragraphs 440/446 (98.7%), branch outcomes 1337/1465 (91.3%).
- Mutation: 49 program(s) measured, killed 2386/3389 (70.4%) raw (adjusted for equivalent / unreachable survivors: 2386/2726 (87.5%)); survivors case_gap 191, harness_gap 149, equivalent 454, unreachable 209, untriaged 0; open survivors 340.
- Holes (stub / ported_unproven methods): 4. Declared differences: 7.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 49).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 49 of 49 programs measured): 9112 (11813 code lines in all); in programs at E2+ 7251/9112 (79.6%), E3+ 862/9112 (9.5%), E4 0/9112 (0.0%); paragraph coverage weighted by lines 8984/9112 (98.6%).

## aws-mainframe-modernization-carddemo

- Programs: 23; at E0 0, E1 3, E2 19, E3 1, E4 0; executed equivalent or above (E2+): 20/23 (87.0%).
- Coverage over the programs with a record: paragraphs 343/344 (99.7%), branch outcomes 1200/1281 (93.7%).
- Mutation: 23 program(s) measured, killed 1651/2254 (73.2%) raw (adjusted for equivalent / unreachable survivors: 1651/1791 (92.2%)); survivors case_gap 133, harness_gap 7, equivalent 335, unreachable 128, untriaged 0; open survivors 140.
- Holes (stub / ported_unproven methods): 3. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 23).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 23 of 23 programs measured): 7281 (9221 code lines in all); in programs at E2+ 6260/7281 (86.0%), E3+ 140/7281 (1.9%), E4 0/7281 (0.0%); paragraph coverage weighted by lines 7266/7281 (99.8%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| COACTVWC | carddemo-acctview | 485 | E1 | 22 runs / 6 fault | gnucobol-models | 31/32 / 58/69 | 105/129, open 8 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COADM01C | carddemo-adminmenu | 153 | E1 | 30 runs / 5 fault | gnucobol-models | 8/8 / 20/26 | 63/95, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COBIL00C | carddemo-billpay | 363 | E2 | 30 runs / 13 fault | gnucobol-models | 16/16 / 46/48 | 66/86, open 4 | 0 | - | coverage short: 16/16 paragraphs, 46/48 branch outcomes |
| COCRDLIC | carddemo-cardlist | 849 | E2 | 31 runs / 3 fault | gnucobol-models | 36/36 / 135/149 | 75/94, open 7 | 0 | - | coverage short: 36/36 paragraphs, 135/149 branch outcomes |
| COCRDSLC | carddemo-cardview | 442 | E2 | 24 runs / 3 fault | gnucobol-models | 30/30 / 69/75 | 60/91, open 5 | 0 | - | coverage short: 30/30 paragraphs, 69/75 branch outcomes |
| CBTRN01C | carddemo-dailyval | 309 | E2 | 21 runs / 20 fault | gnucobol-models | 18/18 / 65/66 | 63/96, open 8 | 0 | - | coverage short: 18/18 paragraphs, 65/66 branch outcomes |
| CSUTLDTC | carddemo-dateutil | 51 | E2 | 1 runs / 0 fault | gnucobol-models | 2/2 / 4/10 | 145/195, open 0 | 0 | - | coverage short: 2/2 paragraphs, 4/10 branch outcomes |
| CBACT04C | carddemo-intcalc | 417 | E2 | 20 runs / 19 fault | gnucobol-models | 22/22 / 85/86 | 70/86, open 7 | 0 | - | coverage short: 22/22 paragraphs, 85/86 branch outcomes |
| COMEN01C | carddemo-menu | 178 | E2 | 15 runs / 2 fault | gnucobol-models | 7/7 / 29/33 | 86/136, open 7 | 0 | - | coverage short: 7/7 paragraphs, 29/33 branch outcomes |
| CBTRN02C | carddemo-posttran | 478 | E2 | 29 runs / 28 fault | gnucobol-models | 26/26 / 95/96 | 76/85, open 4 | 0 | - | coverage short: 26/26 paragraphs, 95/96 branch outcomes |
| CBACT02C | carddemo-readcard | 90 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 69/83, open 4 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CBCUS01C | carddemo-readcust | 91 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 63/74, open 7 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CBACT03C | carddemo-readxref | 91 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 69/83, open 8 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CORPT00C | carddemo-report | 383 | E1 | 28 runs / 1 fault | gnucobol-models | 10/10 / 52/59 | 58/87, open 2 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COSGN00C | carddemo-signon | 140 | E3 | 18 runs / 3 fault | gnucobol-models | 6/6 / 17/17 | 67/99, open 5 | 0 | - | mutation score stale: port, case, harness, oracle changed since it was judged (bcb4f6f82) |
| COTRN02C | carddemo-tranadd | 550 | E2 | 51 runs / 11 fault | gnucobol-models | 18/18 / 72/75 | 61/91, open 12 | 0 | - | coverage short: 18/18 paragraphs, 72/75 branch outcomes |
| COTRN00C | carddemo-tranlist | 479 | E2 | 33 runs / 4 fault | gnucobol-models | 16/16 / 96/101 | 64/91, open 15 | 0 | - | coverage short: 16/16 paragraphs, 96/101 branch outcomes |
| COTRN01C | carddemo-tranview | 187 | E2 | 20 runs / 2 fault | gnucobol-models | 9/9 / 23/24 | 67/100, open 0 | 0 | - | coverage short: 9/9 paragraphs, 23/24 branch outcomes |
| CBTRN03C | carddemo-trnrpt | 433 | E2 | 25 runs / 24 fault | gnucobol-models | 26/26 / 81/82 | 68/86, open 11 | 0 | - | coverage short: 26/26 paragraphs, 81/82 branch outcomes |
| COUSR01C | carddemo-useradd | 168 | E2 | 22 runs / 1 fault | gnucobol-models | 9/9 / 20/21 | 63/98, open 1 | 0 | - | coverage short: 9/9 paragraphs, 20/21 branch outcomes |
| COUSR03C | carddemo-userdel | 209 | E2 | 28 runs / 5 fault | gnucobol-models | 11/11 / 31/32 | 67/87, open 0 | 0 | - | coverage short: 11/11 paragraphs, 31/32 branch outcomes |
| COUSR00C | carddemo-userlist | 474 | E2 | 32 runs / 4 fault | gnucobol-models | 16/16 / 95/100 | 69/100, open 23 | 0 | - | coverage short: 16/16 paragraphs, 95/100 branch outcomes |
| COUSR02C | carddemo-userupd | 261 | E2 | 25 runs / 2 fault | gnucobol-models | 11/11 / 44/46 | 57/82, open 2 | 0 | - | coverage short: 11/11 paragraphs, 44/46 branch outcomes |

## cics-banking-sample-application-cbsa

- Programs: 2; at E0 0, E1 1, E2 1, E3 0, E4 0; executed equivalent or above (E2+): 1/2 (50.0%).
- Coverage over the programs with a record: paragraphs 29/32 (90.6%), branch outcomes 18/31 (58.1%).
- Mutation: 2 program(s) measured, killed 226/264 (85.6%) raw (adjusted for equivalent / unreachable survivors: 226/241 (93.8%)); survivors case_gap 15, harness_gap 0, equivalent 17, unreachable 6, untriaged 0; open survivors 15.
- Holes (stub / ported_unproven methods): 1. Declared differences: 1.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 2).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 2 of 2 programs measured): 642 (872 code lines in all); in programs at E2+ 118/642 (18.4%), E3+ 0/642 (0.0%), E4 0/642 (0.0%); paragraph coverage weighted by lines 579/642 (90.2%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| INQACC | cbsa-inqacc | 524 | E1 | 14 runs / 0 fault | gnucobol-models | 22/25 / 13/25 | 131/131, open 0 | 1 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| UPDACC | cbsa-updacc | 118 | E2 | 10 runs / 0 fault | gnucobol-models | 7/7 / 5/6 | 95/133, open 15 | 0 | - | coverage short: 7/7 paragraphs, 5/6 branch outcomes |

## cics-crucible

- Programs: 21; at E0 0, E1 0, E2 1, E3 20, E4 0; executed equivalent or above (E2+): 21/21 (100.0%).
- Coverage over the programs with a record: paragraphs 54/54 (100.0%), branch outcomes 93/94 (98.9%).
- Mutation: 21 program(s) measured, killed 319/476 (67.0%) raw (adjusted for equivalent / unreachable survivors: 319/354 (90.1%)); survivors case_gap 35, harness_gap 0, equivalent 88, unreachable 34, untriaged 0; open survivors 35.
- Holes (stub / ported_unproven methods): 0. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 21).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 21 of 21 programs measured): 780 (1109 code lines in all); in programs at E2+ 780/780 (100.0%), E3+ 722/780 (92.6%), E4 0/780 (0.0%); paragraph coverage weighted by lines 780/780 (100.0%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| CALINK | ca-link-lengths | 35 | E3 | 4 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 15/22, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| CASUB | ca-link-lengths | 17 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 16/24, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| CAXA | ca-xctl-versions | 26 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 3/3 | 16/21, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (0e2e05254) |
| CAXB | ca-xctl-versions | 32 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 6/6 | 20/23, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| GTSTART | gt-start-retrieve | 35 | E3 | 6 runs / 0 fault | crucible-expected-logs | 1/1 / 6/6 | 19/22, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (0e2e05254) |
| GTWORK | gt-start-retrieve | 22 | E3 | 5 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 20/21, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (0e2e05254) |
| GTSHOW | gt-terminal-coalesce | 21 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 17/23, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| GTTERM | gt-terminal-coalesce | 41 | E3 | 4 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 17/21, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| HCMAIN | hc-abend-link | 47 | E3 | 5 runs / 0 fault | crucible-expected-logs | 4/4 / 4/4 | 14/23, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (0e2e05254) |
| HCSUB | hc-abend-link | 29 | E3 | 3 runs / 0 fault | crucible-expected-logs | 2/2 / 3/3 | 18/24, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (0e2e05254) |
| HCQREAD | hc-perform-range | 64 | E3 | 4 runs / 0 fault | crucible-expected-logs | 8/8 / 0/0 | 14/21, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| HXATTR | hx-attr-bytes | 56 | E3 | 4 runs / 0 fault | crucible-expected-logs | 4/4 / 6/6 | 17/22, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| HXEXT | hx-extended-cursor | 47 | E3 | 3 runs / 0 fault | crucible-expected-logs | 3/3 / 6/6 | 20/23, open 0 | 0 | - | mutation score stale: harness changed since it was judged (0e2e05254) |
| PCDETL | pc-aid-menu | 15 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 15/24, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (9743bfb17) |
| PCMENU | pc-aid-menu | 52 | E3 | 4 runs / 0 fault | crucible-expected-logs | 4/4 / 9/9 | 16/24, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (9743bfb17) |
| PCIMMA | pc-return-immediate | 58 | E2 | 4 runs / 0 fault | crucible-expected-logs | 6/6 / 4/5 | 6/22, open 10 | 0 | - | coverage short: 6/6 paragraphs, 4/5 branch outcomes |
| PCIMMB | pc-return-immediate | 20 | E3 | 1 runs / 0 fault | crucible-expected-logs | 2/2 / 2/2 | 11/23, open 7 | 0 | - | mutation score stale: port, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCIMML | pc-return-immediate | 14 | E3 | 2 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 9/23, open 10 | 0 | - | mutation score stale: port, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCIMMS | pc-return-immediate | 10 | E3 | 1 runs / 0 fault | crucible-expected-logs | 1/1 / 0/0 | 8/24, open 8 | 0 | - | mutation score stale: port, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCCONF | pc-wizard | 79 | E3 | 5 runs / 0 fault | crucible-expected-logs | 5/5 / 14/14 | 15/23, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (9743bfb17) |
| PCWIZ | pc-wizard | 60 | E3 | 6 runs / 0 fault | crucible-expected-logs | 5/5 / 10/10 | 16/23, open 0 | 0 | - | mutation score stale: case, harness changed since it was judged (9743bfb17) |

## cics-genapp

- Programs: 3; at E0 0, E1 2, E2 1, E3 0, E4 0; executed equivalent or above (E2+): 1/3 (33.3%).
- Coverage over the programs with a record: paragraphs 14/16 (87.5%), branch outcomes 26/59 (44.1%).
- Mutation: 3 program(s) measured, killed 190/395 (48.1%) raw (adjusted for equivalent / unreachable survivors: 190/340 (55.9%)); survivors case_gap 8, harness_gap 142, equivalent 14, unreachable 41, untriaged 0; open survivors 150.
- Holes (stub / ported_unproven methods): 0. Declared differences: 6.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 3).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 3 of 3 programs measured): 409 (611 code lines in all); in programs at E2+ 93/409 (22.7%), E3+ 0/409 (0.0%), E4 0/409 (0.0%); paragraph coverage weighted by lines 359/409 (87.8%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| LGAPVS01 | genapp-lgapvs01 | 79 | E1 | 11 runs / 2 fault | gnucobol-models | 3/3 / 5/9 | 72/125, open 41 | 2 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:LGSTSQ |
| LGICDB01 | genapp-lgicdb01 | 93 | E2 | 12 runs / 0 fault | gnucobol-models | 3/4 / 4/12 | 51/130, open 56 | 2 | - | coverage short: 3/4 paragraphs, 4/12 branch outcomes |
| LGUPDB01 | genapp-lgupdb01 | 237 | E1 | 5 runs / 0 fault | gnucobol-models | 8/9 / 17/38 | 67/140, open 53 | 2 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:LGUPVS01 |
