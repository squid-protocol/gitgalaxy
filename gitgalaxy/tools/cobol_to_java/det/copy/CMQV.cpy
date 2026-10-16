      * CMQV stand-in (GitGalaxy-written, NOT IBM's member). Only the
      * MQI constants the MQ model gives a meaning to (register W1): any
      * other constant is not declared, so a program that names one does
      * not compile -- refused, never guessed. Values: IBM MQ
      * documentation, "Constants" (MQCC_*, MQRC_*, MQOO_*, MQGMO_*,
      * MQPMO_*, MQCO_*, MQMI_*, MQCI_*, MQFMT_*, MQCCSI_*, MQMT_*,
      * MQOT_*, MQPER_*). Shipped only with the MQ model GitGalaxy runs
      * it against (det cobolrt.mq, tests/equivalence/mq/ggmq.c).
        10 MQCC-OK                      PIC S9(9) BINARY VALUE 0.
        10 MQCC-WARNING                 PIC S9(9) BINARY VALUE 1.
        10 MQCC-FAILED                  PIC S9(9) BINARY VALUE 2.
        10 MQRC-NONE                    PIC S9(9) BINARY VALUE 0.
        10 MQRC-BUFFER-LENGTH-ERROR     PIC S9(9) BINARY VALUE 2005.
        10 MQRC-HOBJ-ERROR              PIC S9(9) BINARY VALUE 2019.
        10 MQRC-NO-MSG-AVAILABLE        PIC S9(9) BINARY VALUE 2033.
        10 MQRC-NOT-OPEN-FOR-INPUT      PIC S9(9) BINARY VALUE 2037.
        10 MQRC-NOT-OPEN-FOR-OUTPUT     PIC S9(9) BINARY VALUE 2039.
        10 MQRC-OPTIONS-ERROR           PIC S9(9) BINARY VALUE 2046.
        10 MQRC-TRUNCATED-MSG-ACCEPTED  PIC S9(9) BINARY VALUE 2079.
        10 MQRC-TRUNCATED-MSG-FAILED    PIC S9(9) BINARY VALUE 2080.
        10 MQRC-UNKNOWN-OBJECT-NAME     PIC S9(9) BINARY VALUE 2085.
        10 MQOO-INPUT-AS-Q-DEF          PIC S9(9) BINARY VALUE 1.
        10 MQOO-INPUT-SHARED            PIC S9(9) BINARY VALUE 2.
        10 MQOO-INPUT-EXCLUSIVE         PIC S9(9) BINARY VALUE 4.
        10 MQOO-OUTPUT                  PIC S9(9) BINARY VALUE 16.
        10 MQOO-SAVE-ALL-CONTEXT        PIC S9(9) BINARY VALUE 128.
        10 MQOO-PASS-IDENTITY-CONTEXT   PIC S9(9) BINARY VALUE 256.
        10 MQOO-PASS-ALL-CONTEXT        PIC S9(9) BINARY VALUE 512.
        10 MQOO-FAIL-IF-QUIESCING       PIC S9(9) BINARY VALUE 8192.
        10 MQGMO-NO-WAIT                PIC S9(9) BINARY VALUE 0.
        10 MQGMO-WAIT                   PIC S9(9) BINARY VALUE 1.
        10 MQGMO-SYNCPOINT              PIC S9(9) BINARY VALUE 2.
        10 MQGMO-NO-SYNCPOINT           PIC S9(9) BINARY VALUE 4.
        10 MQGMO-ACCEPT-TRUNCATED-MSG   PIC S9(9) BINARY VALUE 64.
        10 MQGMO-FAIL-IF-QUIESCING      PIC S9(9) BINARY VALUE 8192.
        10 MQGMO-CONVERT                PIC S9(9) BINARY VALUE 16384.
        10 MQPMO-SYNCPOINT              PIC S9(9) BINARY VALUE 2.
        10 MQPMO-NO-SYNCPOINT           PIC S9(9) BINARY VALUE 4.
        10 MQPMO-DEFAULT-CONTEXT        PIC S9(9) BINARY VALUE 32.
        10 MQPMO-FAIL-IF-QUIESCING      PIC S9(9) BINARY VALUE 8192.
        10 MQPMO-NO-CONTEXT             PIC S9(9) BINARY VALUE 16384.
        10 MQCO-NONE                    PIC S9(9) BINARY VALUE 0.
        10 MQMI-NONE                    PIC X(24) VALUE LOW-VALUES.
        10 MQCI-NONE                    PIC X(24) VALUE LOW-VALUES.
        10 MQFMT-NONE                   PIC X(8) VALUE SPACES.
        10 MQFMT-STRING                 PIC X(8) VALUE 'MQSTR   '.
        10 MQCCSI-Q-MGR                 PIC S9(9) BINARY VALUE 0.
        10 MQMT-REQUEST                 PIC S9(9) BINARY VALUE 1.
        10 MQMT-REPLY                   PIC S9(9) BINARY VALUE 2.
        10 MQMT-DATAGRAM                PIC S9(9) BINARY VALUE 8.
        10 MQOT-Q                       PIC S9(9) BINARY VALUE 1.
        10 MQPER-NOT-PERSISTENT         PIC S9(9) BINARY VALUE 0.
        10 MQPER-PERSISTENT             PIC S9(9) BINARY VALUE 1.
        10 MQPER-PERSISTENCE-AS-Q-DEF   PIC S9(9) BINARY VALUE 2.
