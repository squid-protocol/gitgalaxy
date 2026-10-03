       IDENTIFICATION DIVISION.
       PROGRAM-ID. FXTSQ.
      *---------------------------------------------------------------*
      * #3989 runner fixture: terminal RECEIVE (#4005) and TS queues   *
      * (#4002): reads a seeded item, appends a copy, reads it back   *
      * too short (LENGERR) and reads a queue that does not exist     *
      * (QIDERR), then shows what it saw.                             *
      *---------------------------------------------------------------*
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT              PIC X(10) VALUE SPACES.
       01  WS-INLEN              PIC S9(4) COMP VALUE 10.
       01  WS-ITEM               PIC X(8)  VALUE SPACES.
       01  WS-LEN                PIC S9(4) COMP VALUE 8.
       01  WS-SHORT              PIC X(3)  VALUE SPACES.
       01  WS-SLEN               PIC S9(4) COMP VALUE 3.
       01  WS-NUM                PIC S9(4) COMP VALUE 0.
       01  WS-RESP               PIC S9(8) COMP VALUE 0.
       01  WS-LINE.
           05  LN-INPUT          PIC X(6).
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-LEN            PIC 9.
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-NUM            PIC 9.
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-SHORT          PIC X(3).
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-SLEN           PIC 9.
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-RESP1          PIC 99.
           05  FILLER            PIC X     VALUE SPACE.
           05  LN-RESP2          PIC 99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN)
           END-EXEC
           EXEC CICS READQ TS QUEUE('FXQ') INTO(WS-ITEM)
                     LENGTH(WS-LEN) ITEM(1)
           END-EXEC
           EXEC CICS WRITEQ TS QUEUE('FXQ') FROM(WS-ITEM)
                     LENGTH(WS-LEN) ITEM(WS-NUM)
           END-EXEC
           EXEC CICS READQ TS QUEUE('FXQ') INTO(WS-SHORT)
                     LENGTH(WS-SLEN) ITEM(2) RESP(WS-RESP)
           END-EXEC
           MOVE WS-RESP TO LN-RESP1
           EXEC CICS READQ TS QUEUE('FXNONE') INTO(WS-ITEM)
                     LENGTH(WS-LEN) ITEM(1) RESP(WS-RESP)
           END-EXEC
           MOVE WS-RESP TO LN-RESP2
           MOVE WS-INPUT TO LN-INPUT
           MOVE WS-LEN TO LN-LEN
           MOVE WS-NUM TO LN-NUM
           MOVE WS-SHORT TO LN-SHORT
           MOVE WS-SLEN TO LN-SLEN
           EXEC CICS SEND TEXT FROM(WS-LINE) LENGTH(22) ERASE
           END-EXEC
           EXEC CICS RETURN END-EXEC.
