      * CMQMDV stand-in (GitGalaxy-written, NOT IBM's member). The MQMD
      * message descriptor, version 1 only (MQMD_LENGTH_1, 324 bytes),
      * with the initial values IBM documents for it on z/OS (Encoding
      * MQENC_NATIVE = 785). Source: IBM MQ documentation, "MQMD -
      * Message descriptor" (fields, initial values). Shipped only with
      * the MQ model GitGalaxy runs it against (det cobolrt.mq,
      * tests/equivalence/mq/ggmq.c); see register W1.
        10 MQMD.
           15 MQMD-STRUCID          PIC X(4) VALUE 'MD  '.
           15 MQMD-VERSION          PIC S9(9) BINARY VALUE 1.
           15 MQMD-REPORT           PIC S9(9) BINARY VALUE 0.
           15 MQMD-MSGTYPE          PIC S9(9) BINARY VALUE 8.
           15 MQMD-EXPIRY           PIC S9(9) BINARY VALUE -1.
           15 MQMD-FEEDBACK         PIC S9(9) BINARY VALUE 0.
           15 MQMD-ENCODING         PIC S9(9) BINARY VALUE 785.
           15 MQMD-CODEDCHARSETID   PIC S9(9) BINARY VALUE 0.
           15 MQMD-FORMAT           PIC X(8) VALUE SPACES.
           15 MQMD-PRIORITY         PIC S9(9) BINARY VALUE -1.
           15 MQMD-PERSISTENCE      PIC S9(9) BINARY VALUE 2.
           15 MQMD-MSGID            PIC X(24) VALUE LOW-VALUES.
           15 MQMD-CORRELID         PIC X(24) VALUE LOW-VALUES.
           15 MQMD-BACKOUTCOUNT     PIC S9(9) BINARY VALUE 0.
           15 MQMD-REPLYTOQ         PIC X(48) VALUE SPACES.
           15 MQMD-REPLYTOQMGR      PIC X(48) VALUE SPACES.
           15 MQMD-USERIDENTIFIER   PIC X(12) VALUE SPACES.
           15 MQMD-ACCOUNTINGTOKEN  PIC X(32) VALUE LOW-VALUES.
           15 MQMD-APPLIDENTITYDATA PIC X(32) VALUE SPACES.
           15 MQMD-PUTAPPLTYPE      PIC S9(9) BINARY VALUE 0.
           15 MQMD-PUTAPPLNAME      PIC X(28) VALUE SPACES.
           15 MQMD-PUTDATE          PIC X(8) VALUE SPACES.
           15 MQMD-PUTTIME          PIC X(8) VALUE SPACES.
           15 MQMD-APPLORIGINDATA   PIC X(4) VALUE SPACES.
