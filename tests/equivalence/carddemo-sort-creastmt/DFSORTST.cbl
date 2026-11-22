       IDENTIFICATION DIVISION.
       PROGRAM-ID. DFSORTST.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       OBJECT-COMPUTER. GG
           PROGRAM COLLATING SEQUENCE IS EB.
       SPECIAL-NAMES.
           ALPHABET EB IS EBCDIC.
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
       01  O-REC PIC X(328).
       SD  S-FILE.
       01  S-REC PIC X(350).
       01  K1-R.
           05 FILLER PIC X(262).
           05 K1 PIC X(16).
           05 FILLER PIC X(72).
       01  K2-R.
           05 K2 PIC X(16).
           05 FILLER PIC X(334).
       WORKING-STORAGE SECTION.
       01  W-EOF PIC X.
       01  W-REC PIC X(350).
       01  W-OUT PIC X(328).
       PROCEDURE DIVISION.
       MAIN-PARA.
           SORT S-FILE ON ASCENDING KEY K1
               ON ASCENDING KEY K2
               USING I1-FILE
               OUTPUT PROCEDURE WRITE-ALL
           GOBACK.
       WRITE-ALL.
           OPEN OUTPUT O-FILE
           MOVE 'N' TO W-EOF
           PERFORM UNTIL W-EOF = 'Y'
               RETURN S-FILE INTO W-REC
                   AT END MOVE 'Y' TO W-EOF
                   NOT AT END
                       PERFORM BUILD-OUT
                       WRITE O-REC FROM W-OUT
               END-RETURN
           END-PERFORM
           CLOSE O-FILE.
       BUILD-OUT.
           MOVE W-REC(263:16) TO W-OUT(1:16)
           MOVE W-REC(1:262) TO W-OUT(17:262)
           MOVE W-REC(279:50) TO W-OUT(279:50).
