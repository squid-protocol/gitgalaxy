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
      * translator moves in.
       01  GG-CICS EXTERNAL.
           05 GG-RESP   PIC S9(9) COMP-5.
           05 GG-RESP2  PIC S9(9) COMP-5.
           05 GG-NAME1  PIC X(8).
           05 GG-NAME2  PIC X(8).
           05 GG-FLAGS  PIC X(40).
