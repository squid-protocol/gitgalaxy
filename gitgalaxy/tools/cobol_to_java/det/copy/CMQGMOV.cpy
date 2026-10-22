      * CMQGMOV stand-in (GitGalaxy-written, NOT IBM's member). The
      * MQGMO get-message options, version 1 only (MQGMO_LENGTH_1, 72
      * bytes), with the initial values IBM documents for it. Source:
      * IBM MQ documentation, "MQGMO - Get-message options" (fields,
      * initial values). Shipped only with the MQ model GitGalaxy runs
      * it against (det cobolrt.mq, tests/equivalence/mq/ggmq.c); see
      * register W1.
        10 MQGMO.
           15 MQGMO-STRUCID         PIC X(4) VALUE 'GMO '.
           15 MQGMO-VERSION         PIC S9(9) BINARY VALUE 1.
           15 MQGMO-OPTIONS         PIC S9(9) BINARY VALUE 0.
           15 MQGMO-WAITINTERVAL    PIC S9(9) BINARY VALUE 0.
           15 MQGMO-SIGNAL1         PIC S9(9) BINARY VALUE 0.
           15 MQGMO-SIGNAL2         PIC S9(9) BINARY VALUE 0.
           15 MQGMO-RESOLVEDQNAME   PIC X(48) VALUE SPACES.
