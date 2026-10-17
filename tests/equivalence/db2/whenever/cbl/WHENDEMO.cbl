       IDENTIFICATION DIVISION.
       PROGRAM-ID. WHENDEMO.
      * #4269: EXEC SQL WHENEVER SQLERROR / NOT FOUND / SQLWARNING,
      * GO TO and CONTINUE, in force until the next WHENEVER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE GGWHEN.WTAB TABLE
               ( ID                 INTEGER NOT NULL,
                 BAL                DECIMAL(9, 2) NOT NULL,
                 NAME               CHAR(10) NOT NULL
               ) END-EXEC.
       01  WS-ID                    PIC S9(9) COMP.
       01  WS-BAL                   PIC S9(7)V99 COMP-3.
       01  WS-SHORT                 PIC X(3).
       01  WS-NAME                  PIC X(10).
       01  WS-CODE                  PIC -(9)9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 5 TO WS-BAL
           MOVE 'XXXXXXXXXX' TO WS-NAME
           EXEC SQL WHENEVER SQLERROR GO TO ERR-PARA END-EXEC
           EXEC SQL WHENEVER NOT FOUND GO TO NF-PARA END-EXEC
           MOVE 1 TO WS-ID
           EXEC SQL
               SELECT BAL INTO :WS-BAL FROM GGWHEN.WTAB
                   WHERE ID = :WS-ID
           END-EXEC
           DISPLAY 'A FOUND'
           MOVE 9 TO WS-ID
           EXEC SQL
               SELECT BAL INTO :WS-BAL FROM GGWHEN.WTAB
                   WHERE ID = :WS-ID
           END-EXEC
           DISPLAY 'A NOT SKIPPED'.
       NF-PARA.
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'B NOT FOUND ' WS-CODE
           EXEC SQL WHENEVER NOT FOUND CONTINUE END-EXEC
           EXEC SQL
               SELECT BAL INTO :WS-BAL FROM GGWHEN.WTAB
                   WHERE ID = :WS-ID
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'B CONTINUE ' WS-CODE
           MOVE 1 TO WS-ID
           EXEC SQL
               INSERT INTO GGWHEN.WTAB (ID, BAL, NAME)
                   VALUES (:WS-ID, :WS-BAL, :WS-NAME)
           END-EXEC
           DISPLAY 'B NOT SKIPPED'.
       ERR-PARA.
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'C ERROR ' WS-CODE
           EXEC SQL WHENEVER SQLERROR CONTINUE END-EXEC
           EXEC SQL
               INSERT INTO GGWHEN.WTAB (ID, BAL, NAME)
                   VALUES (:WS-ID, :WS-BAL, :WS-NAME)
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'D CONTINUE ' WS-CODE
           EXEC SQL WHENEVER SQLWARNING GO TO WARN-PARA END-EXEC
           EXEC SQL
               SELECT NAME INTO :WS-SHORT FROM GGWHEN.WTAB
                   WHERE ID = :WS-ID
           END-EXEC
           DISPLAY 'E NOT SKIPPED'.
       WARN-PARA.
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'E WARNING ' WS-CODE ' ' WS-SHORT
           STOP RUN.
