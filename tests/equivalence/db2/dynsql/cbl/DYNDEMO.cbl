       IDENTIFICATION DIVISION.
       PROGRAM-ID. DYNDEMO.
      * #4269: dynamic SQL, a literal INSERT text run at once,
      * the statement text a string literal; Db2 answers it.
      * a PREPARE from a literal, then the prepared name run.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE GGDYN.DTAB TABLE
               ( ID                 INTEGER NOT NULL,
                 NAME               CHAR(10) NOT NULL
               ) END-EXEC.
       01  WS-ID                    PIC S9(9) COMP.
       01  WS-NAME                  PIC X(10).
       01  WS-CODE                  PIC -(9)9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC SQL
               EXECUTE IMMEDIATE
               'INSERT INTO GGDYN.DTAB VALUES (2, ''DYN'')'
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'A INSERT ' WS-CODE
           MOVE 2 TO WS-ID
           EXEC SQL
               SELECT NAME INTO :WS-NAME FROM GGDYN.DTAB
                   WHERE ID = :WS-ID
           END-EXEC
           DISPLAY 'B ROW ' WS-NAME
           EXEC SQL
               EXECUTE IMMEDIATE
               'INSERT INTO GGDYN.DTAB VALUES (3, ''IT''''S'')'
           END-EXEC
           MOVE 3 TO WS-ID
           EXEC SQL
               SELECT NAME INTO :WS-NAME FROM GGDYN.DTAB
                   WHERE ID = :WS-ID
           END-EXEC
           DISPLAY 'C QUOTE ' WS-NAME
           EXEC SQL
               EXECUTE IMMEDIATE
               'INSERT INTO GGDYN.DTAB VALUES (2, ''AGAIN'')'
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'D DUPLICATE ' WS-CODE
           EXEC SQL
               PREPARE S1 FROM
               'INSERT INTO GGDYN.DTAB VALUES (5, ''PREP'')'
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'F PREPARE ' WS-CODE
           EXEC SQL EXECUTE S1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'G EXECUTE ' WS-CODE
           EXEC SQL EXECUTE S1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'H AGAIN ' WS-CODE
           EXEC SQL WHENEVER SQLERROR GO TO ERR-PARA END-EXEC
           EXEC SQL
               EXECUTE IMMEDIATE
               'INSERT INTO GGDYN.NOPE VALUES (4, ''X'')'
           END-EXEC
           DISPLAY 'I NOT SKIPPED'.
       ERR-PARA.
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'I MISSING TABLE ' WS-CODE
           STOP RUN.
