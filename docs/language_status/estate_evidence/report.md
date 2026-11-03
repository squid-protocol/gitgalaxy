# Estate evidence report

Rolled up from the per-program evidence records (#4048, #4054). A level is evidence, not a verdict: the oracle is GnuCOBOL plus gitgalaxy's CICS / LE / Db2 models (a crucible port: hand-written expected logs), not IBM z/OS. See docs/language_status/oracle_assumptions.md.

## Ladder

- **E0** no record
- **E1** recorded, not executed-equivalent or holes
- **E2** executed equivalent
- **E3** executed equivalent, full coverage (net of reviewed infeasible outcomes)
- **E4** executed equivalent, full coverage, mutants accounted for

## All reported estates

- Programs: 59; at E0 0, E1 5, E2 3, E3 51, E4 0; executed equivalent or above (E2+): 54/59 (91.5%).
- Coverage over the programs with a record: paragraphs 574/576 (99.7%), branch outcomes 1732/1821 (95.1%); net of 88 reviewed infeasible and 0 undefined-by-IBM outcome(s): 1732/1735 (99.8%).
- Mutation: 52 program(s) measured, killed 2868/4237 (67.7%) raw (adjusted for equivalent / unreachable survivors: 2868/3401 (84.3%)); survivors case_gap 388, harness_gap 144, equivalent 500, unreachable 336, untriaged 0; open survivors 532.
- Holes (stub / ported_unproven methods): 3. Declared differences: 12.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 52).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 57 of 59 programs measured): 11945 (15542 code lines in all); in programs at E2+ 10057/11945 (84.2%), E3+ 9852/11945 (82.5%), E4 0/11945 (0.0%); paragraph coverage weighted by lines 11913/11945 (99.7%).

## aws-mainframe-modernization-carddemo

- Programs: 30; at E0 0, E1 4, E2 0, E3 26, E4 0; executed equivalent or above (E2+): 26/30 (86.7%).
- Coverage over the programs with a record: paragraphs 462/463 (99.8%), branch outcomes 1503/1581 (95.1%); net of 79 reviewed infeasible and 0 undefined-by-IBM outcome(s): 1503/1503 (100.0%).
- Mutation: 23 program(s) measured, killed 2049/2737 (74.9%) raw (adjusted for equivalent / unreachable survivors: 2049/2132 (96.1%)); survivors case_gap 75, harness_gap 7, equivalent 380, unreachable 225, untriaged 0; open survivors 82.
- Holes (stub / ported_unproven methods): 3. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 23).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 28 of 30 programs measured): 9642 (12295 code lines in all); in programs at E2+ 8278/9642 (85.9%), E3+ 8278/9642 (85.9%), E4 0/9642 (0.0%); paragraph coverage weighted by lines 9631/9642 (99.9%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| COACTVWC | carddemo-acctview | 485 | E1 | 37 runs / 7 fault | gnucobol-models | 32/32 / 61/69 (net 32/32 / 61/61) | 119/137, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COADM01C | carddemo-adminmenu | 153 | E1 | 34 runs / 5 fault | gnucobol-models | 8/8 / 20/26 (net 8/8 / 20/20) | 63/95, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COBIL00C | carddemo-billpay | 363 | E3 | 35 runs / 13 fault | gnucobol-models | 16/16 / 46/48 (net 16/16 / 46/46) | 66/86, open 4 | 0 | - | mutation score stale: port, case, harness, oracle changed since it was judged (7470befa4) |
| COCRDLIC | carddemo-cardlist | 849 | E3 | 46 runs / 9 fault | gnucobol-models | 36/36 / 147/149 (net 36/36 / 147/147) | 82/94, open 0 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (6d3d283347618d109842b3e8a7bd55709b974e45) |
| COCRDSLC | carddemo-cardview | 442 | E3 | 25 runs / 3 fault | gnucobol-models | 30/30 / 69/75 (net 30/30 / 69/69) | 60/91, open 5 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (7470befa4) |
| CBPAUP0C | carddemo-cbpaup0c | 180 | E3 | 14 runs / 13 fault | gnucobol-models | 15/16 / 39/40 (net 15/15 / 39/39) | - | 0 | - | no mutation score recorded |
| CBSTM03A | carddemo-cbstm03a | 566 | E3 | 14 runs / 13 fault | gnucobol-models | 25/25 / 43/46 (net 25/25 / 43/43) | - | 0 | - | no mutation score recorded |
| COPAUA0C | carddemo-copaua0c | 607 | E3 | 26 runs / 7 fault | gnucobol-models | 41/41 / 66/71 (net 41/41 / 66/66) | - | 0 | - | no mutation score recorded |
| COPAUS0C | carddemo-copaus0c | 665 | E3 | 39 runs / 12 fault | gnucobol-models | 20/20 / 90/93 (net 20/20 / 90/90) | - | 0 | - | no mutation score recorded |
| COPAUS1C | carddemo-copaus1c | 343 | E1 | 35 runs / 14 fault | gnucobol-models | 15/15 / 50/50 | - | 0 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:COPAUS2C |
| CBTRN01C | carddemo-dailyval | 309 | E3 | 21 runs / 20 fault | gnucobol-models | 18/18 / 65/66 (net 18/18 / 65/65) | 63/96, open 8 | 0 | - | mutation score stale: harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| CSUTLDTC | carddemo-dateutil | 51 | E3 | 1 runs / 0 fault | gnucobol-models | 2/2 / 4/10 (net 2/2 / 4/4) | 197/260, open 0 | 0 | - | mutation score stale: port, case, harness, oracle changed since it was judged (69e7af7e3d5c2bf9e7169fb5c14fb0360bdb9d7d) |
| CBACT04C | carddemo-intcalc | 417 | E3 | 20 runs / 19 fault | gnucobol-models | 22/22 / 85/86 (net 22/22 / 85/85) | 70/86, open 7 | 0 | - | mutation score stale: port, harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| COMEN01C | carddemo-menu | 178 | E3 | 16 runs / 2 fault | gnucobol-models | 7/7 / 29/33 (net 7/7 / 29/29) | 87/139, open 0 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (06a436358ecf784524e7d13291ed0ade1d586821) |
| CBTRN02C | carddemo-posttran | 478 | E3 | 29 runs / 28 fault | gnucobol-models | 26/26 / 95/96 (net 26/26 / 95/95) | 76/85, open 4 | 0 | - | mutation score stale: harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| CBACT02C | carddemo-readcard | 90 | E3 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 (net 5/5 / 21/21) | 69/83, open 4 | 0 | - | mutation score stale: harness, oracle changed since it was judged (7470befa414a0c8dfd36f30e310267030a49af89) |
| CBCUS01C | carddemo-readcust | 91 | E3 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 (net 5/5 / 21/21) | 63/74, open 7 | 0 | - | mutation score stale: harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| CBACT03C | carddemo-readxref | 91 | E3 | 7 runs / 6 fault | gnucobol-models | 5/5 / 21/22 (net 5/5 / 21/21) | 69/83, open 8 | 0 | - | mutation score stale: harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| CORPT00C | carddemo-report | 383 | E1 | 30 runs / 2 fault | gnucobol-models | 10/10 / 52/59 (net 10/10 / 52/52) | 59/87, open 0 | 0 | - | 1 hole(s) in the port itself (stub or ported_unproven method) |
| COSGN00C | carddemo-signon | 140 | E3 | 22 runs / 5 fault | gnucobol-models | 6/6 / 17/17 | 67/99, open 5 | 0 | - | mutation score stale: port, case, harness, oracle changed since it was judged (bcb4f6f82) |
| DFSORTST | carddemo-sort-combtran | - | E3 | 3 runs / 2 fault | gnucobol-models | 1/1 / 0/0 | - | 0 | - | no mutation score recorded |
| DFSORTST | carddemo-sort-tranrept | - | E3 | 2 runs / 1 fault | gnucobol-models | 1/1 / 0/0 | - | 0 | - | no mutation score recorded |
| COTRN02C | carddemo-tranadd | 550 | E3 | 78 runs / 11 fault | gnucobol-models | 18/18 / 72/75 (net 18/18 / 72/72) | 70/91, open 3 | 0 | - | mutation score stale: port, harness, oracle changed since it was judged (51724c2b30114cad380308e36f6c99eb0b148bb0) |
| COTRN00C | carddemo-tranlist | 479 | E3 | 36 runs / 6 fault | gnucobol-models | 16/16 / 96/101 (net 16/16 / 96/96) | 66/91, open 13 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (7470befa4) |
| COTRN01C | carddemo-tranview | 187 | E3 | 25 runs / 4 fault | gnucobol-models | 9/9 / 23/24 (net 9/9 / 23/23) | 67/100, open 0 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (2721b9fc4fcec5dba0ab9277037ede4d07a84860) |
| CBTRN03C | carddemo-trnrpt | 433 | E3 | 25 runs / 24 fault | gnucobol-models | 26/26 / 81/82 (net 26/26 / 81/81) | 68/86, open 11 | 0 | - | mutation score stale: harness, oracle changed since it was judged (bd84708964b285f9101fcec387f64a84c9514cd7) |
| COUSR01C | carddemo-useradd | 168 | E3 | 25 runs / 3 fault | gnucobol-models | 9/9 / 20/21 (net 9/9 / 20/20) | 63/98, open 1 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (2721b9fc4fcec5dba0ab9277037ede4d07a84860) |
| COUSR03C | carddemo-userdel | 209 | E3 | 33 runs / 6 fault | gnucobol-models | 11/11 / 31/32 (net 11/11 / 31/31) | 67/87, open 0 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (2721b9fc4fcec5dba0ab9277037ede4d07a84860) |
| COUSR00C | carddemo-userlist | 474 | E3 | 72 runs / 16 fault | gnucobol-models | 16/16 / 95/100 (net 16/16 / 95/95) | 381/507, open 0 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (9a76472bab0c8f94bd0f65cab700136f035906fd) |
| COUSR02C | carddemo-userupd | 261 | E3 | 32 runs / 4 fault | gnucobol-models | 11/11 / 44/46 (net 11/11 / 44/44) | 57/82, open 2 | 0 | - | mutation score stale: case, harness, oracle changed since it was judged (7470befa4) |

## cics-banking-sample-application-cbsa

- Programs: 2; at E0 0, E1 1, E2 1, E3 0, E4 0; executed equivalent or above (E2+): 1/2 (50.0%).
- Coverage over the programs with a record: paragraphs 31/32 (96.9%), branch outcomes 29/31 (93.5%); net of 2 reviewed infeasible and 0 undefined-by-IBM outcome(s): 29/30 (96.7%).
- Mutation: 2 program(s) measured, killed 171/285 (60.0%) raw (adjusted for equivalent / unreachable survivors: 171/250 (68.4%)); survivors case_gap 72, harness_gap 7, equivalent 18, unreachable 17, untriaged 0; open survivors 79.
- Holes (stub / ported_unproven methods): 0. Declared differences: 0.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 2).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 2 of 2 programs measured): 642 (872 code lines in all); in programs at E2+ 118/642 (18.4%), E3+ 0/642 (0.0%), E4 0/642 (0.0%); paragraph coverage weighted by lines 621/642 (96.7%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| INQACC | cbsa-inqacc | 524 | E1 | 26 runs / 12 fault | gnucobol-models | 24/25 / 24/25 (net 24/24 / 24/24) | 68/146, open 72 | 0 | - | a program it LINKs or CALLs has holes or no executed-equivalent record: program:ABNDPROC |
| UPDACC | cbsa-updacc | 118 | E2 | 27 runs / 0 fault | gnucobol-models | 7/7 / 5/6 | 103/139, open 7 | 0 | - | coverage short: 7/7 paragraphs, 5/6 branch outcomes |

## cics-crucible

- Programs: 21; at E0 0, E1 0, E2 2, E3 19, E4 0; executed equivalent or above (E2+): 21/21 (100.0%).
- Coverage over the programs with a record: paragraphs 54/54 (100.0%), branch outcomes 96/98 (98.0%); net of 0 reviewed infeasible and 0 undefined-by-IBM outcome(s): 96/98 (98.0%).
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

- Programs: 6; at E0 0, E1 0, E2 0, E3 6, E4 0; executed equivalent or above (E2+): 6/6 (100.0%).
- Coverage over the programs with a record: paragraphs 27/27 (100.0%), branch outcomes 104/111 (93.7%); net of 7 reviewed infeasible and 0 undefined-by-IBM outcome(s): 104/104 (100.0%).
- Mutation: 6 program(s) measured, killed 329/739 (44.5%) raw (adjusted for equivalent / unreachable survivors: 329/665 (49.5%)); survivors case_gap 206, harness_gap 130, equivalent 14, unreachable 60, untriaged 0; open survivors 336.
- Holes (stub / ported_unproven methods): 0. Declared differences: 12.
- Approved and current: 0. Stale records: 0 (stale mutation scores: 6).
- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; 6 of 6 programs measured): 881 (1266 code lines in all); in programs at E2+ 881/881 (100.0%), E3+ 881/881 (100.0%), E4 0/881 (0.0%); paragraph coverage weighted by lines 881/881 (100.0%).

| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | what stops the next level |
|---|---|---|---|---|---|---|---|---|---|---|
| LGAPDB01 | genapp-lgapdb01 | 326 | E3 | 16 runs / 8 fault | gnucobol-models | 7/7 / 29/31 (net 7/7 / 29/29) | 58/137, open 71 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (7a30cd45ca654ad7f7a9fb85f2f8d185e37546b2) |
| LGAPVS01 | genapp-lgapvs01 | 79 | E3 | 13 runs / 4 fault | gnucobol-models | 3/3 / 10/11 (net 3/3 / 10/10) | 72/125, open 41 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (7a30cd45ca654ad7f7a9fb85f2f8d185e37546b2) |
| LGICDB01 | genapp-lgicdb01 | 93 | E3 | 18 runs / 4 fault | gnucobol-models | 4/4 / 11/12 (net 4/4 / 11/11) | 40/140, open 94 | 2 | - | mutation score stale: harness, oracle changed since it was judged (609d71d7cb799b8615eafae2f0f06a663a081181) |
| LGSTSQ | genapp-lgstsq | 53 | E3 | 8 runs / 0 fault | gnucobol-models | 1/1 / 4/6 (net 1/1 / 4/4) | 25/78, open 44 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (7c6a756d18e89e8fa13f32c215e240c6c44383cf) |
| LGUPDB01 | genapp-lgupdb01 | 237 | E3 | 22 runs / 12 fault | gnucobol-models | 9/9 / 38/38 | 68/140, open 52 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (cacb629caac85834ee75b1a6ddb2514c3ed930bd) |
| LGUPVS01 | genapp-lgupvs01 | 93 | E3 | 12 runs / 5 fault | gnucobol-models | 3/3 / 12/13 (net 3/3 / 12/12) | 66/119, open 34 | 2 | - | mutation score stale: port, case, harness, oracle changed since it was judged (7a30cd45ca654ad7f7a9fb85f2f8d185e37546b2) |
