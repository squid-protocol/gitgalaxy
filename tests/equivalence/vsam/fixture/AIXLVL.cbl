       IDENTIFICATION DIVISION.
       PROGRAM-ID. AIXLVL.
      * #4894 level fixture: an indexed file (VSAM KSDS) with an
      * ALTERNATE RECORD KEY, i.e. an alternate index and its path.
      * DUP-FILE allows duplicate alternate keys, UNQ-FILE does not.
      * expected.txt was written from IBM's rules (Enterprise COBOL
      * for z/OS Language Reference: ALTERNATE RECORD KEY clause,
      * READ / WRITE / REWRITE / DELETE / START, file status key
      * table 34) before either runtime ran it (policy: level
      * estates first). Duplicates of one alternate key are only
      * ever added in primary-key order, so the order IBM returns
      * them in (order of entry) and the primary-key order agree.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT DUP-FILE ASSIGN TO AIXDUP
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS D-PKEY
               ALTERNATE RECORD KEY IS D-AKEY WITH DUPLICATES
               FILE STATUS IS W-FS.
           SELECT UNQ-FILE ASSIGN TO AIXUNQ
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS U-PKEY
               ALTERNATE RECORD KEY IS U-AKEY
               FILE STATUS IS W-FS.
           SELECT NON-FILE ASSIGN TO AIXNONE
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS N-PKEY
               ALTERNATE RECORD KEY IS N-AKEY WITH DUPLICATES
               FILE STATUS IS W-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  DUP-FILE.
       01  DUP-REC.
           05  D-PKEY            PIC X(4).
           05  D-AKEY            PIC X(3).
           05  D-DATA            PIC X(5).
       FD  UNQ-FILE.
       01  UNQ-REC.
           05  U-PKEY            PIC X(4).
           05  U-AKEY            PIC X(3).
           05  U-DATA            PIC X(5).
       FD  NON-FILE.
       01  NON-REC.
           05  N-PKEY            PIC X(4).
           05  N-AKEY            PIC X(3).
           05  N-DATA            PIC X(5).
       WORKING-STORAGE SECTION.
       01  W-FS                  PIC XX.
       01  W-STEP                PIC 99 VALUE 0.
       01  W-OP                  PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
      * 01 OPEN OUTPUT: 00
           MOVE 'OPEN-OUT' TO W-OP
           OPEN OUTPUT DUP-FILE
           PERFORM SHOW
      * 02 WRITE, first record of alternate key RED: 00
           MOVE 'WRITE   ' TO W-OP
           MOVE '0001RED' TO DUP-REC(1:7)
           MOVE 'AAAAA' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0002BLU' TO DUP-REC(1:7)
           MOVE 'BBBBB' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
      * 04 WRITE whose alternate key duplicates one already in the
      *   file, DUPLICATES allowed: successful, 02
           MOVE 'WRITE   ' TO W-OP
           MOVE '0003RED' TO DUP-REC(1:7)
           MOVE 'CCCCC' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0004GRN' TO DUP-REC(1:7)
           MOVE 'DDDDD' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
      * 06 WRITE with a duplicate PRIME key: invalid key, 22
           MOVE 'WRITE   ' TO W-OP
           MOVE '0003GRN' TO DUP-REC(1:7)
           MOVE 'EEEEE' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0005RED' TO DUP-REC(1:7)
           MOVE 'FFFFF' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DUP-FILE
           PERFORM SHOW
           MOVE 'OPEN-I-O' TO W-OP
           OPEN I-O DUP-FILE
           PERFORM SHOW
      * 10 READ through the path: first record of the alternate key
      *   RED; the next record has the same alternate key, so 02
           MOVE 'READ-AIX' TO W-OP
           MOVE 'RED' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
      * 11 READ NEXT stays on the path, in order of entry: 02 while
      *   a duplicate follows
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
      * 12 the last of the RED duplicates: 00
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
      * 13 RED is the highest alternate key: AT END, 10
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
      * 14 READ through the path, a key with one record: 00
           MOVE 'READ-AIX' TO W-OP
           MOVE 'BLU' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
      * 15 READ through the path, no such alternate key: 23
           MOVE 'READ-AIX' TO W-OP
           MOVE 'ZZZ' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
      * 16 START on the alternate key, then READ NEXT on that path
           MOVE 'START-GE' TO W-OP
           MOVE 'C' TO D-AKEY
           START DUP-FILE KEY IS NOT LESS THAN D-AKEY
           PERFORM SHOW
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
      * 19 READ by the prime key: the key of reference is the prime
      *   key again, 00 whatever the duplicates
           MOVE 'READ-KEY' TO W-OP
           MOVE '0003' TO D-PKEY
           READ DUP-FILE RECORD KEY IS D-PKEY
           PERFORM SHOW-D
      * 20 REWRITE changing the alternate key to one that already
      *   exists, DUPLICATES allowed: 02
           MOVE 'REWRITE ' TO W-OP
           MOVE 'BLU' TO D-AKEY
           REWRITE DUP-REC
           PERFORM SHOW
      * 21 the path now holds 0002 and 0003 under BLU
           MOVE 'READ-AIX' TO W-OP
           MOVE 'BLU' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
           MOVE 'READ-NXT' TO W-OP
           READ DUP-FILE NEXT RECORD
           PERFORM SHOW-D
      * 23 DELETE by prime key removes the record from its path
           MOVE 'DELETE  ' TO W-OP
           MOVE '0001' TO D-PKEY
           DELETE DUP-FILE RECORD
           PERFORM SHOW
      * 24 RED now holds one record, 0005: 00
           MOVE 'READ-AIX' TO W-OP
           MOVE 'RED' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
           MOVE 'DELETE  ' TO W-OP
           MOVE '0005' TO D-PKEY
           DELETE DUP-FILE RECORD
           PERFORM SHOW
      * 26 the RED path is empty: 23
           MOVE 'READ-AIX' TO W-OP
           MOVE 'RED' TO D-AKEY
           READ DUP-FILE KEY IS D-AKEY
           PERFORM SHOW-D
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DUP-FILE
           PERFORM SHOW
      * 28 OPEN INPUT of a file with an alternate index: 00; WRITE
      *   to a file open INPUT: 48
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT DUP-FILE
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0006RED' TO DUP-REC(1:7)
           MOVE 'GGGGG' TO D-DATA
           WRITE DUP-REC
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE DUP-FILE
           PERFORM SHOW
      * 31 no DUPLICATES on the alternate key: a second record with
      *   the same alternate key is an invalid key, 22
           MOVE 'OPEN-OUT' TO W-OP
           OPEN OUTPUT UNQ-FILE
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0001RED' TO UNQ-REC(1:7)
           MOVE 'AAAAA' TO U-DATA
           WRITE UNQ-REC
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0002RED' TO UNQ-REC(1:7)
           MOVE 'BBBBB' TO U-DATA
           WRITE UNQ-REC
           PERFORM SHOW
           MOVE 'WRITE   ' TO W-OP
           MOVE '0002BLU' TO UNQ-REC(1:7)
           MOVE 'BBBBB' TO U-DATA
           WRITE UNQ-REC
           PERFORM SHOW
      * 35 reopen for reading: a READ needs INPUT or I-O (47 else)
           MOVE 'CLOSE   ' TO W-OP
           CLOSE UNQ-FILE
           PERFORM SHOW
           MOVE 'OPEN-I-O' TO W-OP
           OPEN I-O UNQ-FILE
           PERFORM SHOW
      * 37 a unique alternate key never gives 02: 00
           MOVE 'READ-AIX' TO W-OP
           MOVE 'RED' TO U-AKEY
           READ UNQ-FILE KEY IS U-AKEY
           PERFORM SHOW-U
      * 38 REWRITE that would duplicate a unique alternate key: 22
           MOVE 'REWRITE ' TO W-OP
           MOVE '0002' TO U-PKEY
           READ UNQ-FILE RECORD KEY IS U-PKEY
           MOVE 'RED' TO U-AKEY
           REWRITE UNQ-REC
           PERFORM SHOW
           MOVE 'CLOSE   ' TO W-OP
           CLOSE UNQ-FILE
           PERFORM SHOW
      * 40 OPEN INPUT of a file that does not exist: 35
           MOVE 'OPEN-IN ' TO W-OP
           OPEN INPUT NON-FILE
           PERFORM SHOW
           DISPLAY 'END AIXLVL'
           STOP RUN.
       SHOW.
           ADD 1 TO W-STEP
           DISPLAY W-STEP ' ' W-OP ' [' W-FS ']'.
       SHOW-D.
           PERFORM SHOW
           IF W-FS = '00' OR W-FS = '02'
               DISPLAY '   K=' D-PKEY ' ' D-AKEY ' ' D-DATA
           END-IF.
       SHOW-U.
           PERFORM SHOW
           IF W-FS = '00' OR W-FS = '02'
               DISPLAY '   K=' U-PKEY ' ' U-AKEY ' ' U-DATA
           END-IF.
