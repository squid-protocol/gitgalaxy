---
description: "The porting loop proves a port by running it against the original, whoever wrote it -- the model, a person or the"
---
# Statement inventory: how much of a port a deterministic translator could write

The porting loop proves a port by running it against the original, whoever wrote it -- the model, a person or the
generator. So every statement the generator can translate deterministically is still proven program by program, and
leaves less for the model: the model's size limit (CardDemo's COACTUPC: a 155k-token prompt, and a port longer than
one answer) is a limit on what the *model* must write. This measures how much that is.

`tests/tools/statement_inventory.py` splits every PROCEDURE DIVISION statement of a set of programs (procedure
copybooks expanded, EXEC blocks whole) and buckets it by what translating it deterministically needs -- the cheapest
bucket that covers it:

- **R runtime-ready**: maps 1:1 onto a runtime the generator already emits (a supported EXEC CICS command, file
  I/O, DISPLAY, ACCEPT FROM DATE / TIME, a CALL of an estate program or a modelled LE service, GOBACK / EXIT /
  CONTINUE, a PERFORM of a paragraph).
- **S storage**: needs WORKING-STORAGE as bytes and COBOL's MOVE / comparison / arithmetic rules (built once).
- **F control flow**: GO TO, PERFORM ... THRU, NEXT SENTENCE lowered to Java (built once).
- **L library**: STRING, UNSTRING, INSPECT, SEARCH, SORT and intrinsic FUNCTIONs (built once).
- **H hole**: the model, or a modelling decision.

Measured on 2026-10-02 over the five corpora this repository proves against (regenerated with `python tests/tools/statement_inventory.py <corpus dirs> --md OUT`):

| corpus | programs | statements | R runtime-ready | S storage | F control flow | L library | H hole | deterministic (R+S+F+L) | programs with no hole |
|---|---|---|---|---|---|---|---|---|---|
| aws-mainframe-modernization-carddemo | 44 | 10176 | 25.1% | 66.4% | 4.9% | 2.6% | 0.9% | 99.1% | 28 |
| cics-banking-sample-application-cbsa | 31 | 6561 | 25.1% | 63.9% | 2.3% | 6.9% | 1.8% | 98.2% | 6 |
| cics-genapp | 31 | 2340 | 24.7% | 63.2% | 3.4% | 1.4% | 7.4% | 92.6% | 11 |
| zecs | 5 | 939 | 18.1% | 52.0% | 21.0% | 1.7% | 7.2% | 92.8% | 0 |
| zopeneditor-sample | 5 | 635 | 36.7% | 62.8% | 0.0% | 0.0% | 0.5% | 99.5% | 2 |
| **all** | 116 | 20651 | 25.1% | 64.5% | 4.5% | 3.7% | 2.2% | 97.8% | 47 |

## What it says

- **97.8% of 20,651 statements are deterministic** once storage (S), control flow (F) and the library (L) are
  built; 2.2% are holes. 47 of the 116 programs have none (43 on 2026-10-01).
- **The largest program has none.** COACTUPC (CardDemo's account update, 1,415 statements: 1,071 storage, 127 control
  flow, 93 library) -- the one too large for the single-shot porter -- is entirely deterministic, and its det port
  is proven ([det_port_design.md](det_port_design.md)).
- **What moved since 2026-10-01.** The runtime now models ASSIGN PROGRAM and INVOKINGPROG, GET COUNTER, DELAY and
  ENQ / DEQ, so those 156 statements left H for R.
- **The holes are mostly not judgment.** Of 453 hole statements: 57% are CICS commands the translator does not take
  yet (DEFINE / DELETE / QUERY COUNTER, RETURN IMMEDIATE, LINK SYNCONRETURN, containers, WEB, DOCUMENT) -- runtime
  work, deterministic like the rest; 20% are EXEC SQL and 13% DL/I and MQ; 8% (38 statements) are real judgment:
  pointers, ALTER, ENTRY, dynamic CALL.
- **EXEC SQL is counted as a hole by definition.** This tool buckets every EXEC SQL as H, but the det translator
  does translate embedded SQL (`gitgalaxy/tools/cobol_to_java/det/sql.py` onto the runtime's `DetSql`), and 17
  equivalence cases prove it against IBM Db2 Community Edition. DL/I and MQ have no model and stay holes.
- **The work is in S.** 64.5% of statements need COBOL's data semantics (9,028 MOVEs alone). That is a specified,
  finite rule set (IBM Enterprise COBOL Language Reference), testable construct by construct against GnuCOBOL.

Limits of the measurement: it classifies by statement form, not by every operand combination (a MOVE between two
edited items is harder than one between two PIC X items; both count as S); "deterministic" means a translator can
be written for it, not that one exists; programs whose source the corpora do not hold (assembler routines) are not
counted.

## Holes, by kind

| kind | statements | where |
|---|---|---|
| EXEC SQL | 92 | cics-banking-sample-application-cbsa 38, cics-genapp 34, aws-mainframe-modernization-carddemo 20 |
| EXEC CICS DELETE (translator refuses: DELETE COUNTER) | 37 | cics-genapp 37 |
| EXEC CICS DEFINE (translator refuses: DEFINE COUNTER) | 37 | cics-genapp 37 |
| EXEC CICS QUERY (translator refuses: QUERY COUNTER) | 36 | cics-genapp 36 |
| pointer (SET ADDRESS OF) | 27 | cics-genapp 15, zecs 7, aws-mainframe-modernization-carddemo 5 |
| EXEC DLI | 26 | aws-mainframe-modernization-carddemo 26 |
| EXEC CICS RETURN (translator refuses: RETURN IMMEDIATE) | 16 | cics-banking-sample-application-cbsa 16 |
| EXEC CICS LINK (translator refuses: LINK SYNCONRETURN) | 14 | cics-banking-sample-application-cbsa 14 |
| EXEC CICS WEB (translator refuses: WEB SEND) | 11 | zecs 11 |
| CALL CBLTDLI (no program, no model) | 9 | aws-mainframe-modernization-carddemo 9 |
| EXEC CICS SEND CONTROL (translator refuses: SEND CONTROL) | 8 | cics-banking-sample-application-cbsa 8 |
| EXEC CICS GET (translator refuses: GET CONTAINER) | 8 | cics-banking-sample-application-cbsa 6, cics-genapp 2 |
| CALL MQOPEN (no program, no model) | 7 | aws-mainframe-modernization-carddemo 7 |
| CALL MQCLOSE (no program, no model) | 7 | aws-mainframe-modernization-carddemo 7 |
| EXEC CICS BIF (translator refuses: BIF DEEDIT) | 7 | cics-banking-sample-application-cbsa 7 |
| EXEC CICS SET (translator refuses: SET TERMINAL) | 7 | cics-banking-sample-application-cbsa 7 |
| EXEC CICS WEB (translator refuses: WEB CONVERSE) | 7 | zecs 7 |
| EXEC CICS PUT (translator refuses: PUT CONTAINER) | 6 | cics-banking-sample-application-cbsa 6 |
| EXEC CICS DELETEQ TS (translator refuses: DELETEQ TS) | 6 | cics-genapp 6 |
| EXEC CICS DOCUMENT (translator refuses: DOCUMENT CREATE) | 6 | zecs 6 |
| EXEC CICS DOCUMENT (translator refuses: DOCUMENT RETRIEVE) | 5 | zecs 5 |
| CALL MQPUT (no program, no model) | 4 | aws-mainframe-modernization-carddemo 4 |
| ALTER | 4 | aws-mainframe-modernization-carddemo 4 |
| EXEC CICS INQUIRE TERMINAL(EIBTRMID) (translator refuses: INQUIRE TERMINAL) | 4 | cics-banking-sample-application-cbsa 4 |
| EXEC CICS WEB (translator refuses: WEB OPEN) | 4 | zecs 4 |
| EXEC CICS WEB (translator refuses: WEB CLOSE) | 4 | zecs 4 |
| EXEC CICS WEB (translator refuses: WEB PARSE) | 4 | zecs 4 |
| dynamic CALL (identifier) | 4 | zopeneditor-sample 3, zecs 1 |
| CALL MQGET (no program, no model) | 3 | aws-mainframe-modernization-carddemo 3 |
| ENTRY | 3 | aws-mainframe-modernization-carddemo 3 |
| EXEC CICS READ (translator refuses: READ GTEQ) | 3 | zecs 2, cics-genapp 1 |
| EXEC CICS INQUIRE URIMAP (translator refuses: INQUIRE URIMAP) | 3 | zecs 3 |
| EXEC CICS INQUIRE URIMAP(URI-MAP) (translator refuses: INQUIRE URIMAP) | 3 | zecs 3 |
| ACCEPT (SYSIN / console) | 2 | aws-mainframe-modernization-carddemo 2 |
| EXEC CICS READ (translator refuses: READ TOKEN) | 2 | cics-banking-sample-application-cbsa 2 |
| EXEC CICS DELETE (translator refuses: DELETE TOKEN) | 2 | cics-banking-sample-application-cbsa 2 |
| EXEC CICS ASSIGN STARTCODE(WS-STARTCODE) (translator refuses: ASSIGN STARTCODE) | 2 | cics-genapp 2 |
| EXEC CICS WEB (translator refuses: WEB RECEIVE) | 2 | zecs 2 |
| CALL MQPUT1 (no program, no model) | 1 | aws-mainframe-modernization-carddemo 1 |
| EXEC CICS FORMATTIME (translator refuses: FORMATTIME MILLISECONDS YYDDD) | 1 | aws-mainframe-modernization-carddemo 1 |

## Every statement kind

| bucket:kind | statements |
|---|---|
| S:MOVE | 9028 |
| S:IF | 2014 |
| R:PERFORM | 1659 |
| S:SET | 1146 |
| R:EXIT | 793 |
| R:DISPLAY | 572 |
| L:STRING | 512 |
| F:PERFORM THRU | 492 |
| F:GO TO | 433 |
| S:INITIALIZE | 414 |
| R:CONTINUE | 379 |
| S:EVALUATE | 275 |
| R:EXEC CICS LINK | 223 |
| S:ADD | 197 |
| S:COMPUTE | 189 |
| R:EXEC CICS RETURN | 180 |
| R:WRITE | 170 |
| R:EXEC CICS ASSIGN APPLID(ABND-APPLID) | 123 |
| R:EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) | 123 |
| H:EXEC SQL | 92 |
| R:EXEC CICS ABEND | 89 |
| R:EXEC CICS ASKTIME | 68 |
| R:EXEC CICS FORMATTIME | 65 |
| R:CLOSE | 60 |
| R:OPEN | 57 |
| L:INSPECT | 55 |
| R:GOBACK | 50 |
| S:SUBTRACT | 47 |
| R:EXEC CICS READ | 47 |
| R:EXEC CICS SYNCPOINT | 46 |
| L:intrinsic FUNCTION CURRENT-DATE | 43 |
| R:EXEC CICS SEND MAP | 43 |
| R:READ | 40 |
| H:EXEC CICS DELETE (translator refuses: DELETE COUNTER) | 37 |
| H:EXEC CICS DEFINE (translator refuses: DEFINE COUNTER) | 37 |
| H:EXEC CICS QUERY (translator refuses: QUERY COUNTER) | 36 |
| R:EXEC CICS XCTL | 33 |
| R:EXEC CICS SEND TEXT | 27 |
| H:pointer (SET ADDRESS OF) | 27 |
| H:EXEC DLI | 26 |
| L:intrinsic FUNCTION RANDOM) | 24 |
| R:ACCEPT FROM date/time | 22 |
| L:intrinsic FUNCTION LENGTH | 20 |
| R:EXEC CICS HANDLE ABEND | 20 |
| R:EXEC CICS DELAY | 19 |
| L:intrinsic FUNCTION NUMVAL | 18 |
| R:CALL of an estate program | 18 |
| R:EXEC CICS WRITEQ TS | 17 |
| H:EXEC CICS RETURN (translator refuses: RETURN IMMEDIATE) | 16 |
| L:UNSTRING | 15 |
| R:EXEC CICS REWRITE | 15 |
| L:intrinsic FUNCTION RANDOM | 15 |
| H:EXEC CICS LINK (translator refuses: LINK SYNCONRETURN) | 14 |
| L:intrinsic FUNCTION UPPER-CASE | 13 |
| L:intrinsic FUNCTION NUMVAL-C | 13 |
| R:CALL CEE3ABD (modelled) | 11 |
| R:EXEC CICS WRITE | 11 |
| H:EXEC CICS WEB (translator refuses: WEB SEND) | 11 |
| H:CALL CBLTDLI (no program, no model) | 9 |
| L:intrinsic FUNCTION TRIM | 8 |
| R:EXEC CICS STARTBR | 8 |
| R:EXEC CICS READPREV | 8 |
| R:EXEC CICS ENDBR | 8 |
| R:EXEC CICS DELETE | 8 |
| H:EXEC CICS SEND CONTROL (translator refuses: SEND CONTROL) | 8 |
| H:EXEC CICS GET (translator refuses: GET CONTAINER) | 8 |
| H:CALL MQOPEN (no program, no model) | 7 |
| H:CALL MQCLOSE (no program, no model) | 7 |
| R:EXEC CICS RECEIVE MAP(LIT-THISMAP) | 7 |
| L:intrinsic FUNCTION INTEGER-OF-DATE | 7 |
| H:EXEC CICS BIF (translator refuses: BIF DEEDIT) | 7 |
| H:EXEC CICS SET (translator refuses: SET TERMINAL) | 7 |
| R:EXEC CICS READQ TS | 7 |
| H:EXEC CICS WEB (translator refuses: WEB CONVERSE) | 7 |
| R:EXEC CICS WRITEQ TD | 6 |
| R:EXEC CICS SEND FROM | 6 |
| L:intrinsic FUNCTION TEST-NUMVAL-C | 6 |
| S:DIVIDE | 6 |
| R:EXEC CICS HANDLE CONDITION | 6 |
| L:intrinsic FUNCTION DATE-OF-INTEGER | 6 |
| H:EXEC CICS PUT (translator refuses: PUT CONTAINER) | 6 |
| H:EXEC CICS DELETEQ TS (translator refuses: DELETEQ TS) | 6 |
| H:EXEC CICS DOCUMENT (translator refuses: DOCUMENT CREATE) | 6 |
| R:EXEC CICS SEND MAP(CCARD-NEXT-MAP) | 5 |
| R:EXEC CICS ENQ | 5 |
| R:EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE) | 5 |
| R:EXEC CICS HANDLE AID | 5 |
| H:EXEC CICS DOCUMENT (translator refuses: DOCUMENT RETRIEVE) | 5 |
| R:EXEC CICS RETRIEVE | 4 |
| H:CALL MQPUT (no program, no model) | 4 |
| H:ALTER | 4 |
| F:NEXT SENTENCE | 4 |
| R:EXEC CICS READNEXT | 4 |
| H:EXEC CICS INQUIRE TERMINAL(EIBTRMID) (translator refuses: INQUIRE TERMINAL) | 4 |
| R:EXEC CICS DEQ | 4 |
| R:EXEC CICS RECEIVE INTO(WS-RECV) | 4 |
| H:EXEC CICS WEB (translator refuses: WEB OPEN) | 4 |
| H:EXEC CICS WEB (translator refuses: WEB CLOSE) | 4 |
| H:EXEC CICS WEB (translator refuses: WEB PARSE) | 4 |
| H:dynamic CALL (identifier) | 4 |
| H:CALL MQGET (no program, no model) | 3 |
| H:ENTRY | 3 |
| L:intrinsic FUNCTION TEST-NUMVAL | 3 |
| R:REWRITE | 3 |
| L:intrinsic FUNCTION REVERSE | 3 |
| R:EXEC CICS SEND MAP('BNK1CA') | 3 |
| R:EXEC CICS SEND MAP('BNK1ACC') | 3 |
| R:EXEC CICS SEND MAP('BNK1CC') | 3 |
| R:EXEC CICS SEND MAP('BNK1CD') | 3 |
| R:EXEC CICS SEND MAP('BNK1DA') | 3 |
| R:EXEC CICS SEND MAP('BNK1DC') | 3 |
| R:EXEC CICS SEND MAP('BNK1TF') | 3 |
| R:EXEC CICS SEND MAP('BNK1UA') | 3 |
| R:EXEC CICS SEND MAP('BNK1ME') | 3 |
| R:EXEC CICS ASSIGN INVOKINGPROG(WS-INVOKEPROG) | 3 |
| H:EXEC CICS READ (translator refuses: READ GTEQ) | 3 |
| H:EXEC CICS INQUIRE URIMAP (translator refuses: INQUIRE URIMAP) | 3 |
| H:EXEC CICS INQUIRE URIMAP(URI-MAP) (translator refuses: INQUIRE URIMAP) | 3 |
| R:EXEC CICS START | 3 |
| H:ACCEPT (SYSIN / console) | 2 |
| R:EXEC CICS SEND MAP('COPAU0A') | 2 |
| R:EXEC CICS SEND MAP('COPAU1A') | 2 |
| R:STOP | 2 |
| R:EXEC CICS SEND MAP(LIT-THISMAP) | 2 |
| R:EXEC CICS SEND MAP('CORPT0A') | 2 |
| R:EXEC CICS SEND MAP('COTRN0A') | 2 |
| R:EXEC CICS SEND MAP('COUSR0A') | 2 |
| R:CALL CEEDAYS (modelled) | 2 |
| H:EXEC CICS READ (translator refuses: READ TOKEN) | 2 |
| H:EXEC CICS DELETE (translator refuses: DELETE TOKEN) | 2 |
| R:EXEC CICS GET | 2 |
| R:EXEC CICS ASSIGN SYSID(WS-SYSID) | 2 |
| H:EXEC CICS ASSIGN STARTCODE(WS-STARTCODE) (translator refuses: ASSIGN STARTCODE) | 2 |
| R:EXEC CICS RECEIVE MAP('SSMAPC1') | 2 |
| R:EXEC CICS RECEIVE MAP('SSMAPP1') | 2 |
| R:EXEC CICS RECEIVE MAP('SSMAPP2') | 2 |
| R:EXEC CICS RECEIVE MAP('SSMAPP3') | 2 |
| H:EXEC CICS WEB (translator refuses: WEB RECEIVE) | 2 |
| H:CALL MQPUT1 (no program, no model) | 1 |
| H:EXEC CICS FORMATTIME (translator refuses: FORMATTIME MILLISECONDS YYDDD) | 1 |
| R:EXEC CICS RECEIVE MAP('COPAU0A') | 1 |
| L:SEARCH | 1 |
| R:EXEC CICS RECEIVE MAP('COPAU1A') | 1 |
| H:CALL COBDATFT (no program, no model) | 1 |
| L:intrinsic FUNCTION MOD | 1 |
| L:intrinsic FUNCTION LOWER-CASE | 1 |
| R:EXEC CICS SEND MAP('COADM1A') | 1 |
| R:EXEC CICS RECEIVE MAP('COADM1A') | 1 |
| R:EXEC CICS SEND MAP('COBIL0A') | 1 |
| R:EXEC CICS RECEIVE MAP('COBIL0A') | 1 |
| H:CALL MVSWAIT (no program, no model) | 1 |
| R:EXEC CICS INQUIRE PROGRAM(CDEMO-MENU-OPT-PGMNAME(WS-OPTION)) | 1 |
| R:EXEC CICS SEND MAP('COMEN1A') | 1 |
| R:EXEC CICS RECEIVE MAP('COMEN1A') | 1 |
| R:EXEC CICS RECEIVE MAP('CORPT0A') | 1 |
| R:EXEC CICS RECEIVE MAP('COSGN0A') | 1 |
| R:EXEC CICS SEND MAP('COSGN0A') | 1 |
| R:EXEC CICS ASSIGN APPLID(APPLIDO | 1 |
| R:EXEC CICS ASSIGN SYSID(SYSIDO | 1 |
| R:EXEC CICS RECEIVE MAP('COTRN0A') | 1 |
| R:EXEC CICS SEND MAP('COTRN1A') | 1 |
| R:EXEC CICS RECEIVE MAP('COTRN1A') | 1 |
| R:EXEC CICS SEND MAP('COTRN2A') | 1 |
| R:EXEC CICS RECEIVE MAP('COTRN2A') | 1 |
| R:EXEC CICS RECEIVE MAP('COUSR0A') | 1 |
| R:EXEC CICS SEND MAP('COUSR1A') | 1 |
| R:EXEC CICS RECEIVE MAP('COUSR1A') | 1 |
| R:EXEC CICS SEND MAP('COUSR2A') | 1 |
| R:EXEC CICS RECEIVE MAP('COUSR2A') | 1 |
| R:EXEC CICS SEND MAP('COUSR3A') | 1 |
| R:EXEC CICS RECEIVE MAP('COUSR3A') | 1 |
| H:CALL CEEGMT (no program, no model) | 1 |
| H:CALL CEEDATM (no program, no model) | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1CA') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1ACC') | 1 |
| R:EXEC CICS SEND MAP('BNK1CCM') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1CC') | 1 |
| R:EXEC CICS ASSIGN ABCODE(WS-ABCODE) | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1CD') | 1 |
| H:EXEC CICS INQUIRE ASSOCIATION(EIBTASKN) (translator refuses: INQUIRE ASSOCIATION) | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1DA') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1DC') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1TF') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1UA') | 1 |
| R:EXEC CICS RECEIVE MAP('BNK1ME') | 1 |
| H:EXEC CICS RUN (translator refuses: RUN TRANSID) | 1 |
| H:EXEC CICS FETCH (translator refuses: FETCH ANY) | 1 |
| H:CALL CEELOCT (no program, no model) | 1 |
| L:intrinsic FUNCTION INTEGER | 1 |
| H:EXEC CICS READ (translator refuses: READ GENERIC) | 1 |
| R:EXEC CICS ASSIGN SYSID(WRITE-MSG-SYSID) | 1 |
| R:EXEC CICS RECEIVE MAP('SSMAPP4') | 1 |
| R:EXEC CICS ASSIGN APPLID(WS-APPLID) | 1 |
| H:EXEC CICS START (translator refuses: START AFTER MINUTES) | 1 |
| R:EXEC CICS RECEIVE INTO | 1 |
| R:EXEC CICS ASSIGN APPLID(APPLID) | 1 |
| H:EXEC CICS WEB (translator refuses: WEB EXTRACT) | 1 |
| H:EXEC CICS INQUIRE PROGRAM(ETTL-PROGRAM) (translator refuses: INQUIRE PROGRAM STATUS) | 1 |
| H:EXEC CICS WEB (translator refuses: WEB READ) | 1 |
| R:EXEC CICS INQUIRE PROGRAM(LAT-PROGRAM) | 1 |
| S:MULTIPLY | 1 |
| H:EXEC CICS GETMAIN (translator refuses: GETMAIN SET) | 1 |
| H:EXEC CICS FREEMAIN (translator refuses: FREEMAIN DATAPOINTER) | 1 |
| H:EXEC CICS GET (translator refuses: GET DCOUNTER) | 1 |
| H:EXEC CICS WEB (translator refuses: WEB WRITE) | 1 |
| H:EXEC CICS DELETE (translator refuses: DELETE GENERIC) | 1 |
| H:EXEC CICS WRITE (translator refuses: WRITE OPERATOR) | 1 |
