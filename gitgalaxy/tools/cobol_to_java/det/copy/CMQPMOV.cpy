      * CMQPMOV stand-in (GitGalaxy-written, NOT IBM's member). The
      * MQPMO put-message options, version 1 only (MQPMO_LENGTH_1, 128
      * bytes), with the initial values IBM documents for it. Source:
      * IBM MQ documentation, "MQPMO - Put-message options" (fields,
      * initial values). Shipped only with the MQ model GitGalaxy runs
      * it against (det cobolrt.mq, tests/equivalence/mq/ggmq.c); see
      * register W1.
        10 MQPMO.
           15 MQPMO-STRUCID         PIC X(4) VALUE 'PMO '.
           15 MQPMO-VERSION         PIC S9(9) BINARY VALUE 1.
           15 MQPMO-OPTIONS         PIC S9(9) BINARY VALUE 0.
           15 MQPMO-TIMEOUT         PIC S9(9) BINARY VALUE -1.
           15 MQPMO-CONTEXT         PIC S9(9) BINARY VALUE 0.
           15 MQPMO-KNOWNDESTCOUNT  PIC S9(9) BINARY VALUE 0.
           15 MQPMO-UNKNOWNDESTCOUNT PIC S9(9) BINARY VALUE 0.
           15 MQPMO-INVALIDDESTCOUNT PIC S9(9) BINARY VALUE 0.
           15 MQPMO-RESOLVEDQNAME   PIC X(48) VALUE SPACES.
           15 MQPMO-RESOLVEDQMGRNAME PIC X(48) VALUE SPACES.
