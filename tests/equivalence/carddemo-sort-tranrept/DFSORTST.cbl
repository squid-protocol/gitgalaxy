       IDENTIFICATION DIVISION.
       PROGRAM-ID. DFSORTST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT I1-FILE ASSIGN TO SORTIN.
           SELECT O-FILE ASSIGN TO SORTOUT.
           SELECT S-FILE ASSIGN TO SORTWK01.
       DATA DIVISION.
       FILE SECTION.
       FD  I1-FILE.
       01  I1-REC PIC X(350).
       FD  O-FILE.
       01  O-REC PIC X(350).
       SD  S-FILE.
       01  S-REC.
           05 K1-X PIC X(16).
           05 K1 REDEFINES K1-X PIC S9(16).
           05 S-DATA PIC X(350).
       WORKING-STORAGE SECTION.
       01  W-EOF PIC X.
       01  W-REC PIC X(350).
       01  C1-R REDEFINES W-REC.
           05 FILLER PIC X(304).
           05 C1 PIC X(10).
       PROCEDURE DIVISION.
       MAIN-PARA.
           SORT S-FILE ON ASCENDING KEY K1
               INPUT PROCEDURE READ-ALL
               OUTPUT PROCEDURE WRITE-ALL
           GOBACK.
       WRITE-ALL.
           OPEN OUTPUT O-FILE
           MOVE 'N' TO W-EOF
           PERFORM UNTIL W-EOF = 'Y'
               RETURN S-FILE
                   AT END MOVE 'Y' TO W-EOF
                   NOT AT END
                       WRITE O-REC FROM S-DATA
               END-RETURN
           END-PERFORM
           CLOSE O-FILE.
       READ-ALL.
           OPEN INPUT I1-FILE
           MOVE 'N' TO W-EOF
           PERFORM UNTIL W-EOF = 'Y'
               READ I1-FILE INTO W-REC
                   AT END MOVE 'Y' TO W-EOF
                   NOT AT END IF ((C1 >= '2022-01-01') AND (C1 <=
               '2022-07-06'))
                       MOVE W-REC TO S-DATA
                       MOVE W-REC(263:16) TO K1-X
                       RELEASE S-REC
                   END-IF
               END-READ
           END-PERFORM
           CLOSE I1-FILE.
