      * BAQRINFO stand-in (GitGalaxy-written, NOT IBM's member).
      * BAQ-RESPONSE-INFO as published in IBM z/OS Connect "Developing
      * API requester applications" and "Handling errors from API
      * requester calls" (BAQRINFO copybook, Table 1 return codes).
      * Field names, PIC, USAGE and VALUE only.
      * ASSUMED: BAQ-REQUEST-INFO below holds only BAQ-REQUEST-INFO-COMP-LEVEL,
      * the one field those pages name. The real structure carries more
      * (security parameters for the compatibility levels 1 to 5), laid out
      * nowhere on those pages: a program that names one of them is refused
      * by name (the data name is not found), never guessed.
      * API-INFO and the request and response structures are generated for
      * the customer's API, not part of BAQRINFO: they stay clone members.
       01  BAQ-REQUEST-INFO.
           03  BAQ-REQUEST-INFO-COMP-LEVEL
                   PIC S9(9) COMP-5 SYNC VALUE 0.
       01  BAQ-RESPONSE-INFO.
           03  BAQ-RESPONSE-INFO-COMP-LEVEL
                   PIC S9(9) COMP-5 SYNC VALUE 0.
           03  BAQ-STUB-NAME               PIC X(8).
           03  BAQ-RETURN-CODE             PIC S9(9) COMP-5 SYNC.
               88  BAQ-SUCCESS             VALUE 0.
               88  BAQ-ERROR-IN-API        VALUE 1.
               88  BAQ-ERROR-IN-ZCEE       VALUE 2.
               88  BAQ-ERROR-IN-STUB       VALUE 3.
               88  BAQ-ERROR-NO-RESPONSE   VALUE 4.
           03  BAQ-STATUS-CODE             PIC S9(9) COMP-5 SYNC.
           03  BAQ-STATUS-MESSAGE          PIC X(1024).
           03  BAQ-STATUS-MESSAGE-LEN      PIC S9(9) COMP-5 SYNC.
