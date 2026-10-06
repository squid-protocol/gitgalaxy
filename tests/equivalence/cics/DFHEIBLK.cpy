      * #3754: stand-in for the CICS EXEC interface block, EXTERNAL so
      * the harness driver and the translated program share it. Field
      * order and types follow the documented DFHEIBLK layout.
       01  DFHEIBLK EXTERNAL.
           05 EIBTIME   PIC S9(7) COMP-3.
           05 EIBDATE   PIC S9(7) COMP-3.
           05 EIBTRNID  PIC X(4).
           05 EIBTASKN  PIC S9(7) COMP-3.
           05 EIBTRMID  PIC X(4).
           05 DFHEIGDI  PIC S9(4) COMP.
           05 EIBCPOSN  PIC S9(4) COMP.
           05 EIBCALEN  PIC S9(4) COMP.
           05 EIBAID    PIC X(1).
           05 EIBFN     PIC X(2).
           05 EIBRCODE  PIC X(6).
           05 EIBDS     PIC X(8).
           05 EIBREQID  PIC X(8).
           05 EIBRSRCE  PIC X(8).
           05 EIBSYNC   PIC X.
           05 EIBFREE   PIC X.
           05 EIBRECV   PIC X.
           05 EIBSEND   PIC X.
           05 EIBATT    PIC X.
           05 EIBEOC    PIC X.
           05 EIBFMH    PIC X.
           05 EIBCOMPL  PIC X.
           05 EIBSIG    PIC X.
           05 EIBCONF   PIC X.
           05 EIBERR    PIC X.
           05 EIBERRCD  PIC X(4).
           05 EIBSYNRB  PIC X.
           05 EIBNODAT  PIC X.
           05 EIBRESP   PIC S9(8) COMP.
           05 EIBRESP2  PIC S9(8) COMP.
           05 EIBRLDBK  PIC X.
      * The stub runtime's side of each translated command:
      * tests/equivalence/cics/ggcics.c reads and writes it as a C
      * struct -- two native ints, then the names and option flags the
      * translator moves in, then an in-out length (#4005: RECEIVE's
      * LENGTH -- the most INTO takes, then the data's length), a
      * 16-byte resource name and two in-out numbers (#4002: a TS
      * queue, its ITEM and NUMITEMS), and the index of the label a
      * condition or abend exit transfers to (#4003: the translator's
      * GO TO ... DEPENDING ON GG-GOTO; -1 leaves the program).
       01  GG-CICS EXTERNAL.
           05 GG-RESP   PIC S9(9) COMP-5.
           05 GG-RESP2  PIC S9(9) COMP-5.
           05 GG-NAME1  PIC X(8).
           05 GG-NAME2  PIC X(8).
           05 GG-FLAGS  PIC X(40).
           05 GG-LEN    PIC S9(9) COMP-5.
           05 GG-QNAME  PIC X(16).
           05 GG-ITEM   PIC S9(9) COMP-5.
           05 GG-NUM    PIC S9(9) COMP-5.
           05 GG-GOTO   PIC S9(9) COMP-5.
      * #4270: a channel's name (CHANNEL in; ASSIGN CHANNEL out).
           05 GG-CHAN   PIC X(16).
      * #4270 slice 2: START AFTER / AT's HOURS, MINUTES, SECONDS
      * (-999999999: not given) and the data options of START /
      * RETRIEVE (RTRANSID, RTERMID, QUEUE; GG-FLAGS names which).
           05 GG-HOURS  PIC S9(9) COMP-5.
           05 GG-MINS   PIC S9(9) COMP-5.
           05 GG-SECS   PIC S9(9) COMP-5.
           05 GG-RTRAN  PIC X(4).
           05 GG-RTERM  PIC X(4).
           05 GG-RQUEUE PIC X(8).
      * ASKTIME / FORMATTIME (CardDemo's bill payment): the translator
      * computes them in COBOL from the task's clock (CURRENT-DATE is the
      * case's clock), ABSTIME being milliseconds since 00:00 on
      * 1 January 1900 (IBM CICS TS, EXEC CICS ASKTIME). Each program's
      * own scratch, not shared.
       01  GG-TIME.
           05 GG-MS     PIC S9(18) COMP-3.
           05 GG-REM    PIC S9(18) COMP-3.
           05 GG-DAYS   PIC S9(9) COMP-5.
           05 GG-YMD.
              10 GG-Y   PIC 9(4).
              10 GG-M   PIC 9(2).
              10 GG-D   PIC 9(2).
           05 GG-DATE8 REDEFINES GG-YMD PIC 9(8).
           05 GG-HMSC.
              10 GG-HH  PIC 9(2).
              10 GG-MI  PIC 9(2).
              10 GG-SS  PIC 9(2).
              10 GG-CS  PIC 9(2).
           05 GG-OUT    PIC X(10).
      * #4413: the address of the data a RECEIVE SET received (GGCRECS),
      * for the translator's SET ADDRESS OF ... TO GG-PTR.
       01  GG-PTR       USAGE POINTER.
