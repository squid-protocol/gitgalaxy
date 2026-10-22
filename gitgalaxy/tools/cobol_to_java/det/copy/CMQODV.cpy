      * CMQODV stand-in (GitGalaxy-written, NOT IBM's member). The MQOD
      * object descriptor, version 1 only (MQOD_LENGTH_1, 168 bytes),
      * with the initial values IBM documents for it. Source: IBM MQ
      * documentation, "MQOD - Object descriptor" (fields, initial
      * values). Shipped only with the MQ model GitGalaxy runs it
      * against (det cobolrt.mq, tests/equivalence/mq/ggmq.c); see
      * register W1.
        10 MQOD.
           15 MQOD-STRUCID          PIC X(4) VALUE 'OD  '.
           15 MQOD-VERSION          PIC S9(9) BINARY VALUE 1.
           15 MQOD-OBJECTTYPE       PIC S9(9) BINARY VALUE 1.
           15 MQOD-OBJECTNAME       PIC X(48) VALUE SPACES.
           15 MQOD-OBJECTQMGRNAME   PIC X(48) VALUE SPACES.
           15 MQOD-DYNAMICQNAME     PIC X(48) VALUE 'CSQ.*'.
           15 MQOD-ALTERNATEUSERID  PIC X(12) VALUE SPACES.
