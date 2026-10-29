# Readiness report (#4725)

Per burned estate: what translates whole today and the rules that would make more programs whole. Measured against
the charter in `definition_of_done.md`. Counts only; a level is an evidence level, never a bare "proven".

## aws-mainframe-modernization-carddemo

44 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 2 |
| L1 translated whole | 0 |
| L2 executed equivalent | 0 |
| L3 paragraph coverage | 4 |
| L4 branch coverage | 38 |
| L5 mutants accounted for | 0 |

- translated whole: 42 / 44 (95%); with holes: 2; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 42 / 44
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 5, era 2: 22, era 3: 15, era 4: 0, era none: 2

### Rules to land (1 gap classes; top 1, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|
| 1 | <name>: <name> is not defined in a record of file <name> | 2 | 0 | 2 | era 3: 2 |

### Proof blockers (42 programs translated whole, 38 with no proof gap; top 1 of 1 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|
| 1 | coverage: branch outcomes below the bar | 4 | 0 | 4 |

### Missing inputs

- assumed options awaiting customer confirmation: 19
- by estate_intake checklist section: 2: 10, 3: 3, 4: 5, 5: 1
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 25 | 25 |
| X31 | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | CICS | 21 | 21 |
| X14 | ASSUMED (REFUSED where IBM is silent) | CICS | 13 | 13 |
| X22 | ASSUMED (REFUSED where IBM is silent or the layout decides) | CICS | 13 | 13 |
| X3 | MATCHED | CICS | 9 | 9 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 8 | 8 |
| X52 | ASSUMED (REFUSED where IBM is silent) | CICS | 8 | 8 |
| X67 | REFUSED | CICS | 5 | 5 |
| X46 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X18 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X16 | MATCHED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X19 | ASSUMED (REFUSED where the harness cannot decide) | CICS | 1 | 1 |
| X34 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |

## cics-async-api-credit-card-application-example

10 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 0 |
| L1 translated whole | 0 |
| L2 executed equivalent | 0 |
| L3 paragraph coverage | 0 |
| L4 branch coverage | 10 |
| L5 mutants accounted for | 0 |

- translated whole: 10 / 10 (100%); with holes: 0; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 10 / 10
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 0, era 2: 0, era 3: 0, era 4: 7, era none: 3

### Rules to land (0 gap classes; top 0, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|

### Proof blockers (10 programs translated whole, 10 with no proof gap; top 0 of 0 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|

### Missing inputs

- assumed options awaiting customer confirmation: 23
- by estate_intake checklist section: 1: 1, 2: 11, 3: 3, 4: 6, 5: 2
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 10 | 10 |
| X17 | ASSUMED (REFUSED where IBM is silent) | CICS | 7 | 7 |
| X18 | ASSUMED (REFUSED where IBM is silent) | CICS | 7 | 7 |
| X15 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X19 | ASSUMED (REFUSED where the harness cannot decide) | CICS | 2 | 2 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 2 | 2 |

## cics-banking-sample-application-cbsa

31 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 0 |
| L1 translated whole | 0 |
| L2 executed equivalent | 0 |
| L3 paragraph coverage | 1 |
| L4 branch coverage | 30 |
| L5 mutants accounted for | 0 |

- translated whole: 31 / 31 (100%); with holes: 0; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 31 / 31
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 0, era 2: 22, era 3: 1, era 4: 6, era none: 2

### Rules to land (0 gap classes; top 0, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|

### Proof blockers (31 programs translated whole, 30 with no proof gap; top 1 of 1 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|
| 1 | coverage: branch outcomes below the bar | 1 | 0 | 1 |

### Missing inputs

- assumed options awaiting customer confirmation: 19
- by estate_intake checklist section: 2: 10, 3: 3, 4: 5, 5: 1
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 30 | 30 |
| X46 | ASSUMED (REFUSED where IBM is silent) | CICS | 27 | 27 |
| X19 | ASSUMED (REFUSED where the harness cannot decide) | CICS | 23 | 23 |
| X18 | ASSUMED (REFUSED where IBM is silent) | CICS | 10 | 10 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 9 | 9 |
| X31 | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | CICS | 9 | 9 |
| X15 | ASSUMED (REFUSED where IBM is silent) | CICS | 8 | 8 |
| X67 | REFUSED | CICS | 7 | 7 |
| X17 | ASSUMED (REFUSED where IBM is silent) | CICS | 6 | 6 |
| X26 | ASSUMED (REFUSED where IBM is silent) | CICS | 6 | 6 |
| X14 | ASSUMED (REFUSED where IBM is silent) | CICS | 5 | 5 |
| X22 | ASSUMED (REFUSED where IBM is silent or the layout decides) | CICS | 5 | 5 |
| X3 | MATCHED | CICS | 5 | 5 |
| X52 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X60 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X29 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |

## cics-genapp

31 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 0 |
| L1 translated whole | 0 |
| L2 executed equivalent | 0 |
| L3 paragraph coverage | 0 |
| L4 branch coverage | 31 |
| L5 mutants accounted for | 0 |

- translated whole: 31 / 31 (100%); with holes: 0; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 31 / 31
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 4, era 2: 24, era 3: 0, era 4: 3, era none: 0

### Rules to land (0 gap classes; top 0, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|

### Proof blockers (31 programs translated whole, 31 with no proof gap; top 0 of 0 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|

### Missing inputs

- assumed options awaiting customer confirmation: 18
- by estate_intake checklist section: 2: 10, 3: 3, 4: 4, 5: 1
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 31 | 31 |
| X46 | ASSUMED (REFUSED where IBM is silent) | CICS | 22 | 22 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 9 | 9 |
| X3 | MATCHED | CICS | 6 | 6 |
| X16 | MATCHED (REFUSED where IBM is silent) | CICS | 5 | 5 |
| X22 | ASSUMED (REFUSED where IBM is silent or the layout decides) | CICS | 5 | 5 |
| X31 | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | CICS | 5 | 5 |
| X14 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X15 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X19 | ASSUMED (REFUSED where the harness cannot decide) | CICS | 4 | 4 |
| X30 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X45 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X29 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X52 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X53 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X60 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X17 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X18 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X50 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |

## dbb-mortgage-application

6 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 1 |
| L1 translated whole | 0 |
| L2 executed equivalent | 0 |
| L3 paragraph coverage | 0 |
| L4 branch coverage | 5 |
| L5 mutants accounted for | 0 |

- translated whole: 5 / 6 (83%); with holes: 1; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 5 / 6
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 0, era 2: 2, era 3: 0, era 4: 1, era none: 3

### Rules to land (8 gap classes; top 8, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|
| 1 | <name> ADDRESS OF <name>: not an item of <name> or LINKAGE | 0 | 0 | 1 | - |
| 2 | CEEHDLR: registering an LE user condition handler is not modelled | 0 | 0 | 1 | - |
| 3 | CEEHDLU: unregistering an LE user condition handler is not modelled | 0 | 0 | 1 | - |
| 4 | EPSCSMRI: no service of its own, its translation is refused: epscsmrd.cbl:N: the PICTURE N (…) is not modelled | 0 | 0 | 1 | - |
| 5 | EPSCSMRO: no service of its own, its translation is refused: OS/VS COBOL BLL addressing: SERVICE LABEL (…): no | 0 | 0 | 1 | - |
| 6 | EXEC CICS GETMAIN without INITIMG: IBM gives acquired storage no default contents | 0 | 0 | 1 | - |
| 7 | EXEC CICS SOAPFAULT CREATE | 0 | 0 | 1 | - |
| 8 | SET TO ENTRY: procedure / function pointers are not modelled | 0 | 0 | 1 | - |

### Proof blockers (5 programs translated whole, 5 with no proof gap; top 0 of 0 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|

### Missing inputs

- assumed options awaiting customer confirmation: 20
- by estate_intake checklist section: 2: 10, 3: 3, 4: 6, 5: 1
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 3 | 3 |
| X31 | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | CICS | 2 | 2 |
| X17 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 1 | 1 |
| X42 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X47 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X52 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X65 | REFUSED | CICS | 1 | 1 |

## zecs

7 programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):

| level | programs at exactly this level |
|---|---|
| L0 inventoried | 0 |
| L1 translated whole | 0 |
| L2 executed equivalent | 3 |
| L3 paragraph coverage | 0 |
| L4 branch coverage | 4 |
| L5 mutants accounted for | 0 |

- translated whole: 7 / 7 (100%); with holes: 0; refused: 0
- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): 0
- executed equivalent (L2 and above): 7 / 7
- charter bars for L3 / L4: paragraphs 100.0%, branches 100.0%

Era evidence (programs by latest era a tell reaches):

era 0: 0, era 1: 0, era 2: 0, era 3: 0, era 4: 4, era none: 3

### Rules to land (0 gap classes; top 0, the `cics_census.py blockers` order)

| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |
|---|---|---|---|---|---|

### Proof blockers (7 programs translated whole, 4 with no proof gap; top 2 of 2 classes, `proof_blockers.py` statistics)

| rank | what stops the proof | alone | one gap away | touched |
|---|---|---|---|---|
| 1 | coverage: not measured | 2 | 0 | 2 |
| 2 | coverage: paragraphs below the bar | 1 | 0 | 1 |

### Missing inputs

- assumed options awaiting customer confirmation: 16
- by estate_intake checklist section: 1: 1, 2: 9, 3: 3, 4: 1, 5: 2
- missing copybooks: none

### Oracle caveats the estate relies on (upper bound where a program's reach is unmeasured)

| id | status | area | programs | named only |
|---|---|---|---|---|
| X27 | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | CICS | 5 | 5 |
| X32 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X35 | ASSUMED (REFUSED where IBM is silent) | CICS | 4 | 4 |
| X14 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X22 | ASSUMED (REFUSED where IBM is silent or the layout decides) | CICS | 3 | 3 |
| X33 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X36 | ASSUMED (REFUSED where IBM is silent) | CICS | 3 | 3 |
| X18 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X3 | MATCHED | CICS | 2 | 2 |
| X37 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X46 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X52 | ASSUMED (REFUSED where IBM is silent) | CICS | 2 | 2 |
| X15 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X19 | ASSUMED (REFUSED where the harness cannot decide) | CICS | 1 | 1 |
| X20 | MATCHED (REFUSED where the region cannot decide) | CICS | 1 | 1 |
| X30 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X34 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X38 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X45 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X47 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X53 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X60 | ASSUMED (REFUSED where IBM is silent) | CICS | 1 | 1 |
| X67 | REFUSED | CICS | 1 | 1 |
