       IDENTIFICATION DIVISION.
       PROGRAM-ID. FXCHAIN.
      *---------------------------------------------------------------*
      * #3989 runner fixture (not a crucible case): a visit counter   *
      * carried in the COMMAREA across RETURN TRANSID, then an XCTL   *
      * to FXLAST on the third visit. Only SEND TEXT, RETURN and      *
      * XCTL, so the stub runtime models every event it issues.       *
      *---------------------------------------------------------------*
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATE.
           05  WS-COUNT          PIC 9(3).
           05  WS-NAME           PIC X(8).
       01  WS-LINE               PIC X(20) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA           PIC X(11).
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF EIBCALEN = 0
               MOVE 1 TO WS-COUNT
               MOVE 'FIRST' TO WS-NAME
           ELSE
               MOVE DFHCOMMAREA TO WS-STATE
               ADD 1 TO WS-COUNT
           END-IF
           STRING 'VISIT ' WS-COUNT DELIMITED BY SIZE INTO WS-LINE
           EXEC CICS SEND TEXT FROM(WS-LINE) LENGTH(20) ERASE
           END-EXEC
           IF WS-COUNT < 3
               EXEC CICS RETURN TRANSID('FX01') COMMAREA(WS-STATE)
                         LENGTH(11)
               END-EXEC
           END-IF
           EXEC CICS XCTL PROGRAM('FXLAST') COMMAREA(WS-STATE)
                     LENGTH(11)
           END-EXEC.
