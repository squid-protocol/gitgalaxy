      * CMQTML stand-in (GitGalaxy-written, NOT IBM's member). The MQTM
      * trigger message (MQTM_LENGTH_1, 684 bytes) a triggered CICS
      * transaction RETRIEVEs, with the initial values IBM documents for
      * it. Source: IBM MQ documentation, "MQTM - Trigger message"
      * (fields, initial values). Shipped only with the MQ model
      * GitGalaxy runs it against (det cobolrt.mq,
      * tests/equivalence/mq/ggmq.c); see register W1.
        05 MQTM.
           10 MQTM-STRUCID          PIC X(4) VALUE 'TM  '.
           10 MQTM-VERSION          PIC S9(9) BINARY VALUE 1.
           10 MQTM-QNAME            PIC X(48) VALUE SPACES.
           10 MQTM-PROCESSNAME      PIC X(48) VALUE SPACES.
           10 MQTM-TRIGGERDATA      PIC X(64) VALUE SPACES.
           10 MQTM-APPLTYPE         PIC S9(9) BINARY VALUE 0.
           10 MQTM-APPLID           PIC X(256) VALUE SPACES.
           10 MQTM-ENVDATA          PIC X(128) VALUE SPACES.
           10 MQTM-USERDATA         PIC X(128) VALUE SPACES.
