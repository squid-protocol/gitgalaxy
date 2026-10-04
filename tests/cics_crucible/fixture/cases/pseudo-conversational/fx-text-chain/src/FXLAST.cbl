       IDENTIFICATION DIVISION.
       PROGRAM-ID. FXLAST.
      *---------------------------------------------------------------*
      * #3989 runner fixture: XCTLed to by FXCHAIN; says goodbye and  *
      * ends the conversation with a RETURN that names no TRANSID.    *
      *---------------------------------------------------------------*
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LINE               PIC X(20) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05  LK-COUNT          PIC 9(3).
           05  LK-NAME           PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
           STRING 'DONE ' DELIMITED BY SIZE
                  LK-NAME DELIMITED BY SPACE INTO WS-LINE
           EXEC CICS SEND TEXT FROM(WS-LINE) LENGTH(20) ERASE
           END-EXEC
           EXEC CICS RETURN END-EXEC.
