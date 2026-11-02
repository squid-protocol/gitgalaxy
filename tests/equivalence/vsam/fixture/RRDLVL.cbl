       IDENTIFICATION DIVISION.
       PROGRAM-ID. RRDLVL.
      * #4894 level fixture: ORGANIZATION IS RELATIVE (VSAM RRDS) --
      * sequential and dynamic access, every file status IBM tabulates
      * for relative files. expected.txt was written from IBM's
      * documentation (Enterprise COBOL for z/OS Language Reference:
      * relative files, READ / WRITE / REWRITE / DELETE / START, file
      * status key) before either runtime ran it (policy: level
      * estates first). Each step's comment cites the rule it tests.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SEQ-FILE ASSIGN TO RRDSSEQ
               ORGANIZATION IS RELATIVE
               ACCESS MODE IS SEQUENTIAL
               RELATIVE KEY IS SEQ-KEY
               FILE STATUS IS W-FS.
           SELECT DYN-FILE ASSIGN TO RRDSDYN
               ORGANIZATION IS RELATIVE
               ACCESS MODE IS DYNAMIC
               RELATIVE KEY IS DYN-KEY
               FILE STATUS IS W-FS.
           SELECT NON-FILE ASSIGN TO RRDSNONE
               ORGANIZATION IS RELATIVE
               ACCESS MODE IS SEQUENTIAL
               FILE STATUS IS W-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  SEQ-FILE.
       01  SEQ-REC               PIC X(12).
       FD  DYN-FILE.
       01  DYN-REC               PIC X(12).
       FD  NON-FILE.
       01  NON-REC               PIC X(12).
       WORKING-STORAGE SECTION.
       01  W-FS                  PIC XX.
       01  W-STEP                PIC 99 VALUE 0.
       01  W-OP                  PIC X(8).
       01  SEQ-KEY               PIC 9(4).
       01  DYN-KEY               PIC 9(4).
       PROCEDURE DIVISION.
       MAIN-PARA.
      * 01 OPEN OUTPUT of a relative file: successful, 00
           MOVE 'OPEN-OUT' TO W-OP
           OPEN OUTPUT SEQ-FILE
           PERFORM SHOW
      * 02 sequential WRITE: the record goes to the next slot and the
      *   RELATIVE KEY is set to its number (LRM, WRITE statement)
           MOVE 'WRITE   ' TO W-OP
           MOVE 'ALPHA' TO SEQ-REC
           WRITE SEQ-REC
           PERFORM SHOW-S
      * 03 next slot
           MOVE 'WRITE   ' TO W-OP
           MOVE 'BRAVO' TO SEQ-REC
           WRITE SEQ-REC
           PERFORM SHOW-S
      * 04 next slot
           MOVE 'WRITE   ' TO W-OP
           MOVE 'CHARLIE' TO SEQ-REC
           WRITE SEQ-REC
           PERFORM SHOW-S
      * 05 CLOSE of an open file: 00
           MOVE 'CLOSE   ' TO W-OP
           CLOSE SEQ-FILE
           PERFORM SHOW
      * 06 CLOSE of a file not open: 42 (Table: file status key)
           MOVE 'CLOSE   ' TO W-OP
           CLOSE SEQ-FILE
           PERFORM SHOW
      * 07 OPEN INPUT of an existing file: 00
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT SEQ-FILE
           PERFORM SHOW
      * 08 sequential READ: next existing record, RELATIVE KEY set to
      *   its number
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
           MOVE 'REWRITE ' TO W-OP
           REWRITE SEQ-REC
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
      * 12 no next record: AT END, 10
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           WRITE SEQ-REC
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE SEQ-FILE
           PERFORM SHOW
      * 16 OPEN I-O of an existing relative file: 00
           MOVE 'OPEN-I-O' TO W-OP
           OPEN I-O SEQ-FILE
           PERFORM SHOW
           MOVE 'REWRITE ' TO W-OP
           REWRITE SEQ-REC
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
      * 20 sequential DELETE after a successful READ removes that
      *   record: 00
           MOVE 'DELETE  ' TO W-OP
           DELETE SEQ-FILE RECORD
           PERFORM SHOW
           MOVE 'DELETE  ' TO W-OP
           DELETE SEQ-FILE RECORD
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
      * 23 sequential REWRITE after a successful READ replaces the
      *   record just read
           MOVE 'REWRITE ' TO W-OP
           MOVE 'CHARLIE-2' TO SEQ-REC
           REWRITE SEQ-REC
           PERFORM SHOW-S
           MOVE 'CLOSE   ' TO W-OP
           CLOSE SEQ-FILE
           PERFORM SHOW
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT SEQ-FILE
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
      * 27 the deleted slot 2 is skipped: a sequential READ returns the
      *   next EXISTING record
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW-S
           MOVE 'READ-NXT' TO W-OP
           READ SEQ-FILE NEXT RECORD
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE SEQ-FILE
           PERFORM SHOW
           MOVE 'OPEN-OUT' TO W-OP
           OPEN OUTPUT DYN-FILE
           PERFORM SHOW
      * 31 random / dynamic WRITE: the record goes to the slot named by
      *   the RELATIVE KEY
           MOVE 'WRITE   ' TO W-OP
           MOVE 5 TO DYN-KEY
           MOVE 'FIVE' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW-D
      * 32 slots need not be written in order
           MOVE 'WRITE   ' TO W-OP
           MOVE 2 TO DYN-KEY
           MOVE 'TWO' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW-D
           MOVE 'WRITE   ' TO W-OP
           MOVE 9 TO DYN-KEY
           MOVE 'NINE' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW-D
      * 34 WRITE to an occupied slot: duplicate key, 22
           MOVE 'WRITE   ' TO W-OP
           MOVE 5 TO DYN-KEY
           MOVE 'DUP' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DYN-FILE
           PERFORM SHOW
           MOVE 'OPEN-I-O' TO W-OP
           OPEN I-O DYN-FILE
           PERFORM SHOW
      * 37 dynamic READ without NEXT is a random READ of the slot named
      *   by the RELATIVE KEY
           MOVE 'READ-KEY' TO W-OP
           MOVE 2 TO DYN-KEY
           READ DYN-FILE RECORD
           PERFORM SHOW-D
      * 38 READ of an empty slot: invalid key, 23
           MOVE 'READ-KEY' TO W-OP
           MOVE 3 TO DYN-KEY
           READ DYN-FILE RECORD
           PERFORM SHOW
           MOVE 'READ-KEY' TO W-OP
           MOVE 5 TO DYN-KEY
           READ DYN-FILE RECORD
           PERFORM SHOW-D
      * 40 READ NEXT after a random READ returns the next record after
      *   the one read (skipping empty slots 6-8)
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW
      * 42 START KEY > 2: positions at the first existing slot above 2
           MOVE 'START-GT' TO W-OP
           MOVE 2 TO DYN-KEY
           START DYN-FILE KEY IS GREATER THAN DYN-KEY
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'START-EQ' TO W-OP
           MOVE 3 TO DYN-KEY
           START DYN-FILE KEY IS EQUAL TO DYN-KEY
           PERFORM SHOW
           MOVE 'START-GE' TO W-OP
           MOVE 3 TO DYN-KEY
           START DYN-FILE KEY IS NOT LESS THAN DYN-KEY
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'START-GT' TO W-OP
           MOVE 9 TO DYN-KEY
           START DYN-FILE KEY IS GREATER THAN DYN-KEY
           PERFORM SHOW
      * 48 random / dynamic REWRITE replaces the record in the slot
      *   named by the RELATIVE KEY, no prior READ needed
           MOVE 'REWRITE ' TO W-OP
           MOVE 5 TO DYN-KEY
           MOVE 'FIVE-R' TO DYN-REC
           REWRITE DYN-REC
           PERFORM SHOW-D
      * 49 REWRITE of an empty slot: invalid key, 23
           MOVE 'REWRITE ' TO W-OP
           MOVE 6 TO DYN-KEY
           MOVE 'SIX' TO DYN-REC
           REWRITE DYN-REC
           PERFORM SHOW
           MOVE 'DELETE  ' TO W-OP
           MOVE 2 TO DYN-KEY
           DELETE DYN-FILE RECORD
           PERFORM SHOW
           MOVE 'DELETE  ' TO W-OP
           MOVE 2 TO DYN-KEY
           DELETE DYN-FILE RECORD
           PERFORM SHOW
      * 52 a deleted slot can be written again
           MOVE 'WRITE   ' TO W-OP
           MOVE 2 TO DYN-KEY
           MOVE 'TWO-NEW' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW-D
           MOVE 'START-GE' TO W-OP
           MOVE 1 TO DYN-KEY
           START DYN-FILE KEY IS NOT LESS THAN DYN-KEY
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DYN-FILE NEXT RECORD
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DYN-FILE
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DYN-FILE
           PERFORM SHOW
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT DYN-FILE
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE 7 TO DYN-KEY
           MOVE 'SEVEN' TO DYN-REC
           WRITE DYN-REC
           PERFORM SHOW
           MOVE 'READ-KEY' TO W-OP
           MOVE 9 TO DYN-KEY
           READ DYN-FILE RECORD
           PERFORM SHOW-D
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT DYN-FILE
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DYN-FILE
           PERFORM SHOW
           MOVE 'READ-KEY' TO W-OP
           MOVE 9 TO DYN-KEY
           READ DYN-FILE RECORD
           PERFORM SHOW
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT NON-FILE
           PERFORM SHOW
           DISPLAY 'END RRDLVL'
           STOP RUN.
       SHOW.
           ADD 1 TO W-STEP
           DISPLAY W-STEP ' ' W-OP ' [' W-FS ']'.
       SHOW-S.
           PERFORM SHOW
           IF W-FS = '00'
               DISPLAY '   K=' SEQ-KEY ' ' SEQ-REC
           END-IF.
       SHOW-D.
           PERFORM SHOW
           IF W-FS = '00'
               DISPLAY '   K=' DYN-KEY ' ' DYN-REC
           END-IF.
