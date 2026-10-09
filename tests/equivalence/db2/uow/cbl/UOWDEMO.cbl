       IDENTIFICATION DIVISION.
       PROGRAM-ID. UOWDEMO.
      * #4269: EXEC SQL COMMIT / ROLLBACK end the step's Db2 unit of
      * work; cursors closed at COMMIT (not WITH HOLD) and ROLLBACK.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPFILE ASSIGN TO INPFILE
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  INPFILE RECORDING MODE F.
       01  INP-REC                  PIC X(10).
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE GGUOW.ACCT TABLE
               ( ID                 INTEGER NOT NULL,
                 BAL                DECIMAL(9, 2) NOT NULL
               ) END-EXEC.
       01  WS-FS                    PIC XX.
       01  WS-MODE                  PIC X.
       01  WS-ID                    PIC S9(9) COMP.
       01  WS-BAL                   PIC S9(7)V99 COMP-3.
       01  WS-N                     PIC S9(9) COMP.
       01  WS-CODE                  PIC -(9)9.
       01  WS-SHOW                  PIC -(7)9.99.
       01  WS-ABCODE                PIC S9(9) BINARY VALUE 999.
       01  WS-TIMING                PIC S9(9) BINARY VALUE 0.
           EXEC SQL DECLARE C1 CURSOR FOR
               SELECT ID FROM GGUOW.ACCT ORDER BY ID
           END-EXEC.
           EXEC SQL DECLARE C2 CURSOR WITH HOLD FOR
               SELECT ID FROM GGUOW.ACCT ORDER BY ID
           END-EXEC.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 'N' TO WS-MODE
           OPEN INPUT INPFILE
           READ INPFILE
               NOT AT END MOVE INP-REC(1:1) TO WS-MODE
           END-READ
           CLOSE INPFILE
      * A. a change committed
           MOVE 1 TO WS-ID
           MOVE 111.00 TO WS-BAL
           EXEC SQL
               UPDATE GGUOW.ACCT SET BAL = :WS-BAL WHERE ID = :WS-ID
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'A UPDATE ' WS-CODE
           EXEC SQL COMMIT END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'A COMMIT ' WS-CODE
      * B. two changes backed out
           MOVE 4 TO WS-ID
           MOVE 400.00 TO WS-BAL
           EXEC SQL
               INSERT INTO GGUOW.ACCT (ID, BAL) VALUES (:WS-ID, :WS-BAL)
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'B INSERT ' WS-CODE
           MOVE 2 TO WS-ID
           MOVE 222.00 TO WS-BAL
           EXEC SQL
               UPDATE GGUOW.ACCT SET BAL = :WS-BAL WHERE ID = :WS-ID
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'B UPDATE ' WS-CODE
           EXEC SQL ROLLBACK WORK END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'B ROLLBACK ' WS-CODE
      * C. what the unit of work left
           EXEC SQL
               SELECT COUNT(*) INTO :WS-N FROM GGUOW.ACCT
           END-EXEC
           MOVE WS-N TO WS-CODE
           DISPLAY 'C ROWS ' WS-CODE
           MOVE 2 TO WS-ID
           EXEC SQL
               SELECT BAL INTO :WS-BAL FROM GGUOW.ACCT WHERE ID = :WS-ID
           END-EXEC
           MOVE WS-BAL TO WS-SHOW
           DISPLAY 'C BAL 2 ' WS-SHOW
      * D. an error, then ROLLBACK: the committed row stays
           MOVE 1 TO WS-ID
           EXEC SQL
               INSERT INTO GGUOW.ACCT (ID, BAL) VALUES (:WS-ID, :WS-BAL)
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'D INSERT ' WS-CODE
           EXEC SQL ROLLBACK END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'D ROLLBACK ' WS-CODE
           EXEC SQL
               SELECT BAL INTO :WS-BAL FROM GGUOW.ACCT WHERE ID = :WS-ID
           END-EXEC
           MOVE WS-BAL TO WS-SHOW
           DISPLAY 'D BAL 1 ' WS-SHOW
      * E. COMMIT closes a cursor not declared WITH HOLD
           EXEC SQL OPEN C1 END-EXEC
           EXEC SQL FETCH C1 INTO :WS-ID END-EXEC
           MOVE WS-ID TO WS-CODE
           DISPLAY 'E FETCH ' WS-CODE
           EXEC SQL COMMIT WORK END-EXEC
           EXEC SQL FETCH C1 INTO :WS-ID END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'E FETCH AFTER COMMIT ' WS-CODE
           EXEC SQL CLOSE C1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'E CLOSE ' WS-CODE
      * F. a cursor WITH HOLD stays open across COMMIT
           EXEC SQL OPEN C2 END-EXEC
           EXEC SQL FETCH C2 INTO :WS-ID END-EXEC
           EXEC SQL COMMIT END-EXEC
           EXEC SQL FETCH C2 INTO :WS-ID END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'F FETCH AFTER COMMIT ' WS-CODE
           MOVE WS-ID TO WS-CODE
           DISPLAY 'F ROW ' WS-CODE
           EXEC SQL CLOSE C2 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'F CLOSE ' WS-CODE
      * G. ROLLBACK closes it all the same
           EXEC SQL OPEN C2 END-EXEC
           EXEC SQL FETCH C2 INTO :WS-ID END-EXEC
           EXEC SQL ROLLBACK END-EXEC
           EXEC SQL FETCH C2 INTO :WS-ID END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'G FETCH AFTER ROLLBACK ' WS-CODE
           EXEC SQL CLOSE C2 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'G CLOSE ' WS-CODE
      * I. a savepoint: the work after it backed out, before it kept
           MOVE 5 TO WS-ID
           MOVE 500.00 TO WS-BAL
           EXEC SQL
               INSERT INTO GGUOW.ACCT (ID, BAL) VALUES (:WS-ID, :WS-BAL)
           END-EXEC
           EXEC SQL
               SAVEPOINT SP1 ON ROLLBACK RETAIN CURSORS
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'I SAVEPOINT ' WS-CODE
           MOVE 6 TO WS-ID
           EXEC SQL
               INSERT INTO GGUOW.ACCT (ID, BAL) VALUES (:WS-ID, :WS-BAL)
           END-EXEC
           EXEC SQL ROLLBACK TO SAVEPOINT SP1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'I ROLLBACK TO ' WS-CODE
           EXEC SQL RELEASE SAVEPOINT SP1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'I RELEASE ' WS-CODE
           EXEC SQL ROLLBACK WORK TO SAVEPOINT SP1 END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'I ROLLBACK TO RELEASED ' WS-CODE
           EXEC SQL
               SELECT COUNT(*) INTO :WS-N FROM GGUOW.ACCT
           END-EXEC
           MOVE WS-N TO WS-CODE
           DISPLAY 'I ROWS ' WS-CODE
           EXEC SQL COMMIT END-EXEC
      * H. work left uncommitted: kept at a normal end, backed out
      *    by an abend
           MOVE 3 TO WS-ID
           EXEC SQL
               DELETE FROM GGUOW.ACCT WHERE ID = :WS-ID
           END-EXEC
           MOVE SQLCODE TO WS-CODE
           DISPLAY 'H DELETE ' WS-CODE
           IF WS-MODE = 'A'
               CALL 'CEE3ABD' USING WS-ABCODE WS-TIMING
           END-IF
           GOBACK.
