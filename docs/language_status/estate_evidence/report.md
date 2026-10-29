# Estate evidence report

Rolled up from the per-program evidence records (#4048, #4054). A level is evidence, not a verdict: the oracle is GnuCOBOL plus gitgalaxy's CICS / LE / Db2 models (a crucible port: hand-written expected logs), not IBM z/OS. See docs/language_status/oracle_assumptions.md.

## Ladder

- **E0** no record
- **E1** recorded, not executed-equivalent or holes
- **E2** executed equivalent
- **E3** executed equivalent, full coverage
- **E4** executed equivalent, full coverage, mutants accounted for

## All reported estates

- Programs: 57; at E0 0, E1 5, E2 31, E3 21, E4 0; executed equivalent or above (E2+): 52/57 (91.2%).
- Coverage over the programs with a record: paragraphs 572/574 (99.7%), branch outcomes 1731/1821 (95.1%).
- Mutation: 52 program(s) measured, killed 2868/4237 (67.7%) raw (adjusted for equivalent / unreachable survivors: 2868/3401 (84.3%)); survivors case_gap 388, harness_gap 144, equivalent 500, unreachable 336, untriaged 0; open survivors 532.
- Holes (stub / ported_unproven methods): 3. Declared differences: 12.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 52).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 57 of 57 programs measured): 11945 (15542 code lines in all); in programs at E2+ 10057/11945 (84.2%), E3+ 1070/11945 (9.0%), E4 0/11945 (0.0%); paragraph coverage weighted by lines 11913/11945 (99.7%).

## aws-mainframe-modernization-carddemo

- Programs: 28; at E0 0, E1 4, E2 23, E3 1, E4 0; executed equivalent or above (E2+): 24/28 (85.7%).
- Coverage over the programs with a record: paragraphs 460/461 (99.8%), branch outcomes 1502/1581 (95.0%).
- Mutation: 23 program(s) measured, killed 2049/2737 (74.9%) raw (adjusted for equivalent / unreachable survivors: 2049/2132 (96.1%)); survivors case_gap 75, harness_gap 7, equivalent 380, unreachable 225, untriaged 0; open survivors 82.
- Holes (stub / ported_unproven methods): 3. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 23).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 28 of 28 programs measured): 9642 (12295 code lines in all); in programs at E2+ 8278/9642 (85.9%), E3+ 140/9642 (1.5%), E4 0/9642 (0.0%); paragraph coverage weighted by lines 9631/9642 (99.9%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| COACTVWC | carddemo-acctview | 485 | E1 | 37 runs / 7 fault | gnucobol-models | 32/32 / 61/69 | 119/137, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COADM01C | carddemo-adminmenu | 153 | E1 | 34 runs / 5 fault | gnucobol-models | 8/8 / 20/26 | 63/95, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COBIL00C | carddemo-billpay | 363 | E2 | 35 runs / 13 fault | gnucobol-models | 16/16 / 46/48 | 66/86, open 4 | 0 | - | coverage short: 16/16 paragraphs, 46/48 branch outcomes |
| COCRDLIC | carddemo-cardlist | 849 | E2 | 46 runs / 9 fault | gnucobol-models | 36/36 / 147/149 | 82/94, open 0 | 0 | - | coverage short: 36/36 paragraphs, 147/149 branch outcomes |
| COCRDSLC | carddemo-cardview | 442 | E2 | 25 runs / 3 fault | gnucobol-models | 30/30 / 69/75 | 60/91, open 5 | 0 | - | coverage short: 30/30 paragraphs, 69/75 branch outcomes |
| CBPAUP0C | carddemo-cbpaup0c | 180 | E2 | 13 runs / 12 fault | gnucobol-models | 15/16 / 38/40 | - | 0 | - | coverage short: 15/16 paragraphs, 38/40 branch outcomes |
| CBSTM03A | carddemo-cbstm03a | 566 | E2 | 14 runs / 13 fault | gnucobol-models | 25/25 / 43/46 | - | 0 | - | coverage short: 25/25 paragraphs, 43/46 branch outcomes |
| COPAUA0C | carddemo-copaua0c | 607 | E2 | 26 runs / 7 fault | gnucobol-models | 41/41 / 66/71 | - | 0 | - | coverage short: 41/41 paragraphs, 66/71 branch outcomes |
| COPAUS0C | carddemo-copaus0c | 665 | E2 | 39 runs / 12 fault | gnucobol-models | 20/20 / 90/93 | - | 0 | - | coverage short: 20/20 paragraphs, 90/93 branch outcomes |
| COPAUS1C | carddemo-copaus1c | 343 | E1 | 35 runs / 14 fault | gnucobol-models | 15/15 / 50/50 | - | 0 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:COPAUS2C |
| CBTRN01C | carddemo-dailyval | 309 | E2 | 21 runs / 20 fault | gnucobol-models | 18/18 / 65/66 | 63/96, open 8 | 0 | - | coverage short: 18/18 paragraphs, 65/66 branch outcomes |
| CSUTLDTC | carddemo-dateutil | 51 | E2 | 1 runs / 0 fault | gnucobol-models | 2/2 / 4/10 | 197/260, open 0 | 0 | - | coverage short: 2/2 paragraphs, 4/10 branch outcomes |
| CBACT04C | carddemo-intcalc | 417 | E2 | 20 runs / 19 fault | gnucobol-models | 22/22 / 85/86 | 70/86, open 7 | 0 | - | coverage short: 22/22 paragraphs, 85/86 branch outcomes |
| COMEN01C | carddemo-menu | 178 | E2 | 16 runs / 2 fault | gnucobol-models | 7/7 / 29/33 | 87/139, open 0 | 0 | - | coverage short: 7/7 paragraphs, 29/33 branch outcomes |
| CBTRN02C | carddemo-posttran | 478 | E2 | 29 runs / 28 fault | gnucobol-models | 26/26 / 95/96 | 76/85, open 4 | 0 | - | coverage short: 26/26 paragraphs, 95/96 branch outcomes |
| CBACT02C | carddemo-readcard | 90 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 69/83, open 4 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CBCUS01C | carddemo-readcust | 91 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 63/74, open 7 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CBACT03C | carddemo-readxref | 91 | E2 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 | 69/83, open 8 | 0 | - | coverage short: 5/5 paragraphs, 21/22 branch outcomes |
| CORPT00C | carddemo-report | 383 | E1 | 30 runs / 2 fault | gnucobol-models | 10/10 / 52/59 | 59/87, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COSGN00C | carddemo-signon | 140 | E3 | 22 runs / 5 fault | gnucobol-models | 6/6 / 17/17 | 67/99, open 5 | 0 | - | mutation score stale: port, case, harness, oracle changed since it was judged (bcb4f6f82) |
| COTRN02C | carddemo-tranadd | 550 | E2 | 78 runs / 11 fault | gnucobol-models | 18/18 / 72/75 | 70/91, open 3 | 0 | - | coverage short: 18/18 paragraphs, 72/75 branch outcomes |
| COTRN00C | carddemo-tranlist | 479 | E2 | 36 runs / 6 fault | gnucobol-models | 16/16 / 96/101 | 66/91, open 13 | 0 | - | coverage short: 16/16 paragraphs, 96/101 branch outcomes |
| COTRN01C | carddemo-tranview | 187 | E2 | 25 runs / 4 fault | gnucobol-models | 9/9 / 23/24 | 67/100, open 0 | 0 | - | coverage short: 9/9 paragraphs, 23/24 branch outcomes |
| CBTRN03C | carddemo-trnrpt | 433 | E2 | 25 runs / 24 fault | gnucobol-models | 26/26 / 81/82 | 68/86, open 11 | 0 | - | coverage short: 26/26 paragraphs, 81/82 branch outcomes |
| COUSR01C | carddemo-useradd | 168 | E2 | 25 runs / 3 fault | gnucobol-models | 9/9 / 20/21 | 63/98, open 1 | 0 | - | coverage short: 9/9 paragraphs, 20/21 branch outcomes |
| COUSR03C | carddemo-userdel | 209 | E2 | 32 runs / 6 fault | gnucobol-models | 11/11 / 31/32 | 67/87, open 0 | 0 | - | coverage short: 11/11 paragraphs, 31/32 branch outcomes |
| COUSR00C | carddemo-userlist | 474 | E2 | 72 runs / 16 fault | gnucobol-models | 16/16 / 95/100 | 381/507, open 0 | 0 | - | coverage short: 16/16 paragraphs, 95/100 branch outcomes |
| COUSR02C | carddemo-userupd | 261 | E2 | 32 runs / 4 fault | gnucobol-models | 11/11 / 44/46 | 57/82, open 2 | 0 | - | coverage short: 11/11 paragraphs, 44/46 branch outcomes |

## cics-banking-sample-application-cbsa

- Programs: 2; at E0 0, E1 1, E2 1, E3 0, E4 0; executed equivalent or above (E2+): 1/2 (50.0%).
- Coverage over the programs with a record: paragraphs 31/32 (96.9%), branch outcomes 29/31 (93.5%).
- Mutation: 2 program(s) measured, killed 171/285 (60.0%) raw (adjusted for equivalent / unreachable survivors: 171/250 (68.4%)); survivors case_gap 72, harness_gap 7, equivalent 18, unreachable 17, untriaged 0; open survivors 79.
- Holes (stub / ported_unproven methods): 0. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 2).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 2 of 2 programs measured): 642 (872 code lines in all); in programs at E2+ 118/642 (18.4%), E3+ 0/642 (0.0%), E4 0/642 (0.0%); paragraph coverage weighted by lines 621/642 (96.7%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| INQACC | cbsa-inqacc | 524 | E1 | 26 runs / 12 fault | gnucobol-models | 24/25 / 24/25 | 68/146, open 72 | 0 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:ABNDPROC |
| UPDACC | cbsa-updacc | 118 | E2 | 27 runs / 0 fault | gnucobol-models | 7/7 / 5/6 | 103/139, open 7 | 0 | - | coverage short: 7/7 paragraphs, 5/6 branch outcomes |

## cics-crucible

- Programs: 21; at E0 0, E1 0, E2 2, E3 19, E4 0; executed equivalent or above (E2+): 21/21 (100.0%).
- Coverage over the programs with a record: paragraphs 54/54 (100.0%), branch outcomes 96/98 (98.0%).
- Mutation: 21 program(s) measured, killed 319/476 (67.0%) raw (adjusted for equivalent / unreachable survivors: 319/354 (90.1%)); survivors case_gap 35, harness_gap 0, equivalent 88, unreachable 34, untriaged 0; open survivors 35.
- Holes (stub / ported_unproven methods): 0. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 21).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 21 of 21 programs measured): 780 (1109 code lines in all); in programs at E2+ 780/780 (100.0%), E3+ 693/780 (88.8%), E4 0/780 (0.0%); paragraph coverage weighted by lines 780/780 (100.0%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| CALINK | ca-link-lengths | 35 | E3 | 4 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 15/22, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| CASUB | ca-link-lengths | 17 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 16/24, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| CAXA | ca-xctl-versions | 26 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 3/3 | 16/21, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (0e2e05254) |
| CAXB | ca-xctl-versions | 32 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 6/6 | 20/23, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| GTSTART | gt-start-retrieve | 35 | E3 | 6 runs / 0 fault | crucible-expected-logs | 1/1 / 6/6 | 19/22, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (0e2e05254) |
| GTWORK | gt-start-retrieve | 22 | E3 | 5 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 20/21, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (0e2e05254) |
| GTSHOW | gt-terminal-coalesce | 21 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 17/23, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| GTTERM | gt-terminal-coalesce | 41 | E3 | 4 runs / 0 fault | crucible-expected-logs | 1/1 / 4/4 | 17/21, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| HCMAIN | hc-abend-link | 47 | E3 | 5 runs / 0 fault | crucible-expected-logs | 4/4 / 4/4 | 14/23, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (0e2e05254) |
| HCSUB | hc-abend-link | 29 | E2 | 3 runs / 0 fault | crucible-expected-logs | 2/2 / 4/5 | 18/24, open 0 | 0 | - | coverage short: 2/2 paragraphs, 4/5 branch outcomes |
| HCQREAD | hc-perform-range | 64 | E3 | 4 runs / 0 fault | crucible-expected-logs | 8/8 / 0/0 | 14/21, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| HXATTR | hx-attr-bytes | 56 | E3 | 4 runs / 0 fault | crucible-expected-logs | 4/4 / 6/6 | 17/22, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| HXEXT | hx-extended-cursor | 47 | E3 | 3 runs / 0 fault | crucible-expected-logs | 3/3 / 6/6 | 20/23, open 0 | 0 | - | mutation score stale: corpus, harness changed since it was judged (0e2e05254) |
| PCDETL | pc-aid-menu | 15 | E3 | 3 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 15/24, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (9743bfb17) |
| PCMENU | pc-aid-menu | 52 | E3 | 4 runs / 0 fault | crucible-expected-logs | 4/4 / 9/9 | 16/24, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (9743bfb17) |
| PCIMMA | pc-return-immediate | 58 | E2 | 4 runs / 0 fault | crucible-expected-logs | 6/6 / 4/5 | 6/22, open 10 | 0 | - | coverage short: 6/6 paragraphs, 4/5 branch outcomes |
| PCIMMB | pc-return-immediate | 20 | E3 | 1 runs / 0 fault | crucible-expected-logs | 2/2 / 2/2 | 11/23, open 7 | 0 | - | mutation score stale: port, corpus, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCIMML | pc-return-immediate | 14 | E3 | 2 runs / 0 fault | crucible-expected-logs | 1/1 / 2/2 | 9/23, open 10 | 0 | - | mutation score stale: port, corpus, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCIMMS | pc-return-immediate | 10 | E3 | 1 runs / 0 fault | crucible-expected-logs | 1/1 / 0/0 | 8/24, open 8 | 0 | - | mutation score stale: port, corpus, harness changed since it was judged (ed188d3cb406da57b753e56b98ae9e75b6d2d2b0) |
| PCCONF | pc-wizard | 79 | E3 | 5 runs / 0 fault | crucible-expected-logs | 5/5 / 14/14 | 15/23, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (9743bfb17) |
| PCWIZ | pc-wizard | 60 | E3 | 6 runs / 0 fault | crucible-expected-logs | 5/5 / 10/10 | 16/23, open 0 | 0 | - | mutation score stale: case, corpus, harness changed since it was judged (9743bfb17) |

## cics-genapp

- Programs: 6; at E0 0, E1 0, E2 5, E3 1, E4 0; executed equivalent or above (E2+): 6/6 (100.0%).
- Coverage over the programs with a record: paragraphs 27/27 (100.0%), branch outcomes 104/111 (93.7%).
- Mutation: 6 program(s) measured, killed 329/739 (44.5%) raw (adjusted for equivalent / unreachable survivors: 329/665 (49.5%)); survivors case_gap 206, harness_gap 130, equivalent 14, unreachable 60, untriaged 0; open survivors 336.
- Holes (stub / ported_unproven methods): 0. Declared differences: 12.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 6).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 6 of 6 programs measured): 881 (1266 code lines in all); in programs at E2+ 881/881 (100.0%), E3+ 237/881 (26.9%), E4 0/881 (0.0%); paragraph coverage weighted by lines 881/881 (100.0%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| LGAPDB01 | genapp-lgapdb01 | 326 | E2 | 16 runs / 8 fault | gnucobol-models | 7/7 / 29/31 | 58/137, open 71 | 2 | - | coverage short: 7/7 paragraphs, 29/31 branch outcomes |
| LGAPVS01 | genapp-lgapvs01 | 79 | E2 | 13 runs / 4 fault | gnucobol-models | 3/3 / 10/11 | 72/125, open 41 | 2 | - | coverage short: 3/3 paragraphs, 10/11 branch outcomes |
| LGICDB01 | genapp-lgicdb01 | 93 | E2 | 18 runs / 4 fault | gnucobol-models | 4/4 / 11/12 | 40/140, open 94 | 2 | - | coverage short: 4/4 paragraphs, 11/12 branch outcomes |
| LGSTSQ | genapp-lgstsq | 53 | E2 | 8 runs / 0 fault | gnucobol-models | 1/1 / 4/6 | 25/78, open 44 | 2 | - | coverage short: 1/1 paragraphs, 4/6 branch outcomes |
| LGUPDB01 | genapp-lgupdb01 | 237 | E3 | 22 runs / 12 fault | gnucobol-models | 9/9 / 38/38 | 68/140, open 52 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (cacb629caac85834ee75b1a6ddb2514c3ed930bd) |
| LGUPVS01 | genapp-lgupvs01 | 93 | E2 | 12 runs / 5 fault | gnucobol-models | 3/3 / 12/13 | 66/119, open 34 | 2 | - | coverage short: 3/3 paragraphs, 12/13 branch outcomes |
