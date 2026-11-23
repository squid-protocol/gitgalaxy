      * AIB stand-in (GitGalaxy-written, NOT IBM's member).
      * The application interface block mask, as published in IBM IMS 15.4
      * Application Programming, "Specifying the AIB mask" (Table 36 and
      * the COBOL AIB Mask Example): 128 bytes through AIBRESV4, then the
      * ODBA-reserved tail the example declares. Field names, PIC and
      * USAGE only.
      * ASSUMED: that a program's COPY AIB names this layout; the manual
      * gives the mask as an example to code, not a member name. Used only
      * where the estate has no AIB of its own.
       01  AIB.
           02  AIBRID     PIC X(8).
           02  AIBRLEN    PIC 9(9) USAGE BINARY.
           02  AIBRSFUNC  PIC X(8).
           02  AIBRSNM1   PIC X(8).
           02  AIBRSNM2   PIC X(8).
           02  AIBRSNM3   PIC X(8).
           02  AIBOALEN   PIC 9(9) USAGE BINARY.
           02  AIBOAUSE   PIC 9(9) USAGE BINARY.
           02  AIBRESV2   PIC X(12).
           02  AIBRETRN   PIC 9(9) USAGE BINARY.
           02  AIBREASN   PIC 9(9) USAGE BINARY.
           02  AIBERRXT   PIC 9(9) USAGE BINARY.
           02  AIBRESA1   USAGE POINTER.
           02  AIBRESA2   USAGE POINTER.
           02  AIBRESA3   USAGE POINTER.
           02  AIBRESV4   PIC X(40).
           02  AIBRSAVE   OCCURS 18 TIMES USAGE POINTER.
           02  AIBRTOKN   OCCURS 6 TIMES USAGE POINTER.
           02  AIBRTOKC   PIC X(16).
           02  AIBRTOKV   PIC X(16).
           02  AIBRTOKA   OCCURS 2 TIMES PIC 9(9) USAGE BINARY.
