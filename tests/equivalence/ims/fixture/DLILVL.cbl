       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLILVL.
      * #4893 level fixture: every modelled DL/I call and status code on
      * LVLDBD through PSB LVLPSB. Its expected output (expected.txt) was
      * written from IBM's documentation before either runtime ran it;
      * each step's comment cites the rule (register I1-I5).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W-STEP                PIC 99 VALUE 0.
       01  W-LEN                 PIC 99.
       01  W-KFB                 PIC X(10).
       01  W-IO                  PIC X(14).
       01  IOA                   PIC X(20).
       01  IOA-EMP REDEFINES IOA.
           05 IO-EMPNO           PIC X(4).
           05 IO-ENAME           PIC X(10).
           05 IO-SAL             PIC S9(5) COMP-3.
           05 FILLER             PIC X(3).
       01  F-GU                  PIC X(4) VALUE 'GU  '.
       01  F-GHU                 PIC X(4) VALUE 'GHU '.
       01  F-GN                  PIC X(4) VALUE 'GN  '.
       01  F-GNP                 PIC X(4) VALUE 'GNP '.
       01  F-ISRT                PIC X(4) VALUE 'ISRT'.
       01  F-REPL                PIC X(4) VALUE 'REPL'.
       01  F-DLET                PIC X(4) VALUE 'DLET'.
       01  F-BAD                 PIC X(4) VALUE 'XXXX'.
       01  S-DEPT                PIC X(9) VALUE 'DEPT     '.
       01  S-EMP                 PIC X(9) VALUE 'EMP      '.
       01  S-SKILL               PIC X(9) VALUE 'SKILL    '.
       01  S-NOSEG               PIC X(9) VALUE 'NOSEG    '.
       01  Q-DEPT.
           05 FILLER             PIC X(9) VALUE 'DEPT    ('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 Q-DEPT-OP          PIC X(2) VALUE 'EQ'.
           05 Q-DEPT-NO          PIC X(4).
           05 Q-DEPT-END         PIC X VALUE ')'.
       01  Q-EMP.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 Q-EMP-NO           PIC X(4).
           05 FILLER             PIC X VALUE ')'.
       01  Q-SAL.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'SAL'.
           05 FILLER             PIC X(2) VALUE '> '.
           05 Q-SAL-V            PIC S9(5) COMP-3.
           05 FILLER             PIC X VALUE ')'.
       01  Q-NAME.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'ENAME'.
           05 FILLER             PIC X(2) VALUE 'EQ'.
           05 Q-NAME-V           PIC X(10).
           05 FILLER             PIC X VALUE ')'.
       01  Q-NOFLD.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'NOFIELD'.
           05 FILLER             PIC X(2) VALUE 'EQ'.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE ')'.
       LINKAGE SECTION.
       01  PCB1.
           05 P1-DBD             PIC X(8).
           05 P1-LEVEL           PIC X(2).
           05 P1-STATUS          PIC X(2).
           05 P1-PROCOPT         PIC X(4).
           05 FILLER             PIC S9(5) COMP.
           05 P1-SEGNAME         PIC X(8).
           05 P1-KFBLEN          PIC S9(5) COMP.
           05 P1-NSENS           PIC S9(5) COMP.
           05 P1-KFB             PIC X(10).
       01  PCB2.
           05 P2-DBD             PIC X(8).
           05 P2-LEVEL           PIC X(2).
           05 P2-STATUS          PIC X(2).
           05 P2-PROCOPT         PIC X(4).
           05 FILLER             PIC S9(5) COMP.
           05 P2-SEGNAME         PIC X(8).
           05 P2-KFBLEN          PIC S9(5) COMP.
           05 P2-NSENS           PIC S9(5) COMP.
           05 P2-KFB             PIC X(10).
       PROCEDURE DIVISION.
       MAIN-PARA.
           ENTRY 'DLITCBL' USING PCB1 PCB2.
      * I4: the masks as IMS hands them over
           MOVE P1-NSENS TO W-LEN
           DISPLAY 'PCB1 ' P1-DBD ' ' P1-LEVEL ' [' P1-STATUS '] '
               P1-PROCOPT ' ' W-LEN
           MOVE P2-NSENS TO W-LEN
           DISPLAY 'PCB2 ' P2-DBD ' ' P2-LEVEL ' [' P2-STATUS '] '
               P2-PROCOPT ' ' W-LEN
           MOVE 'D200' TO Q-DEPT-NO
      * 01 GU qualified root (I1 blank)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT
           PERFORM SHOW1
      * 02 GNP under parentage D200: its first dependent
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
      * 03 GNP: the next dependent, a level down
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
      * 04 GNP: no more under D200: GE (I1); feedback the parent (I4)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
      * 05 GN DEPT after GNP's GE: the next root (I3)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA S-DEPT
           PERFORM SHOW1
      * 06 GN DEPT past the last root: GB (I1)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA S-DEPT
           PERFORM SHOW1
      * 07 GN after GB starts again at the first root (I3)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA S-DEPT
           PERFORM SHOW1
      * 08 unqualified GN down a level: blank
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
      * 09 down again: blank
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
      * 10 a twin: blank
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
      * 11 up a level: GA (I1)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
      * 12 another type, same level: GK (I1)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
      * 13 up to the next root: GA
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA
           PERFORM SHOW1
           MOVE 'D100' TO Q-DEPT-NO
           MOVE 'E002' TO Q-EMP-NO
      * 14 GU along a qualified path
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT Q-EMP
           PERFORM SHOW1
           MOVE +1500 TO Q-SAL-V
      * 15 GU on a P search field, > (I2)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT Q-SAL
           PERFORM SHOW1
           MOVE 'ZED' TO Q-NAME-V
      * 16 GU not found: GE, the deepest level satisfied (I4)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT Q-NAME
           PERFORM SHOW1
           MOVE 'E003' TO Q-EMP-NO
      * 17 an unqualified level is any occurrence
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q-EMP
           PERFORM SHOW1
      * 18 GNP SKILL under E003
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA S-SKILL
           PERFORM SHOW1
      * 19 none left: GE
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA S-SKILL
           PERFORM SHOW1
           MOVE 'D100' TO Q-DEPT-NO
      * 20 GU D100
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT
           PERFORM SHOW1
           MOVE 'E005EVE' TO IOA
           MOVE +5000 TO IO-SAL
      * 21 ISRT along a path: among its twins by key
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOA Q-DEPT S-EMP
           PERFORM SHOW1
      * 22 the same key again: II (I1)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOA Q-DEPT S-EMP
           PERFORM SHOW1
           MOVE 'D999' TO Q-DEPT-NO
      * 23 a parent not found: GE
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOA Q-DEPT S-EMP
           PERFORM SHOW1
           MOVE 'D150NEW' TO IOA
      * 24 ISRT a root
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 'D100' TO Q-DEPT-NO
           MOVE 'E001' TO Q-EMP-NO
      * 25 GHU, then REPL the held segment
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GHU PCB1 IOA Q-DEPT Q-EMP
           PERFORM SHOW1
           MOVE 'ALICIA' TO IO-ENAME
      * 26 REPL: blank
           CALL 'CBLTDLI' USING F-REPL PCB1 IOA
           PERFORM SHOW1
      * 27 REPL with no get-hold just before: DJ
           CALL 'CBLTDLI' USING F-REPL PCB1 IOA
           PERFORM SHOW1
           MOVE 'E002' TO Q-EMP-NO
      * 28 GHU E002
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GHU PCB1 IOA Q-DEPT Q-EMP
           PERFORM SHOW1
           MOVE 'E009' TO IO-EMPNO
      * 29 REPL that changed the key: DA
           CALL 'CBLTDLI' USING F-REPL PCB1 IOA
           PERFORM SHOW1
           MOVE 'E001' TO Q-EMP-NO
      * 30 GHU E001
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GHU PCB1 IOA Q-DEPT Q-EMP
           PERFORM SHOW1
      * 31 DLET: E001 and its skills
           CALL 'CBLTDLI' USING F-DLET PCB1 IOA
           PERFORM SHOW1
      * 32 E001 is gone: GE
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA Q-DEPT Q-EMP
           PERFORM SHOW1
           MOVE 'D777' TO IOA
      * 33 ISRT under PROCOPT=G: AM (I1)
           CALL 'CBLTDLI' USING F-ISRT PCB2 IOA S-DEPT
           PERFORM SHOW2
      * 34 GNP with no parentage: GP (I1)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB2 IOA
           PERFORM SHOW2
      * 35 an SSA naming no segment: AC (I1)
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB2 IOA S-NOSEG
           PERFORM SHOW2
      * 36 an undefined field: AK
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB2 IOA S-DEPT Q-NOFLD
           PERFORM SHOW2
           MOVE 'XX' TO Q-DEPT-OP
      * 37 an invalid operator: AJ
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB2 IOA Q-DEPT
           PERFORM SHOW2
           MOVE 'EQ' TO Q-DEPT-OP
           MOVE 'X' TO Q-DEPT-END
      * 38 no ')' to end the qualification: AJ
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB2 IOA Q-DEPT
           PERFORM SHOW2
           MOVE ')' TO Q-DEPT-END
      * 39 an invalid function: AD
           CALL 'CBLTDLI' USING F-BAD PCB2 IOA
           PERFORM SHOW2
      * 40 the whole database, as PCB 1 left it
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB2 IOA
           PERFORM SHOW2
           PERFORM UNTIL P2-STATUS = 'GB'
               MOVE SPACES TO IOA
               CALL 'CBLTDLI' USING F-GN PCB2 IOA
               PERFORM SHOW2
           END-PERFORM
           GOBACK.
       SHOW1.
           ADD 1 TO W-STEP
           MOVE P1-KFBLEN TO W-LEN
           MOVE SPACES TO W-KFB
           IF W-LEN > 0
               MOVE P1-KFB(1:W-LEN) TO W-KFB
           END-IF
           MOVE IOA(1:14) TO W-IO
           DISPLAY W-STEP ' 1 [' P1-STATUS '] ' P1-LEVEL ' '
               P1-SEGNAME ' '
               W-LEN ' ' W-KFB ' ' W-IO.
       SHOW2.
           ADD 1 TO W-STEP
           MOVE P2-KFBLEN TO W-LEN
           MOVE SPACES TO W-KFB
           IF W-LEN > 0
               MOVE P2-KFB(1:W-LEN) TO W-KFB
           END-IF
           MOVE IOA(1:14) TO W-IO
           DISPLAY W-STEP ' 2 [' P2-STATUS '] ' P2-LEVEL ' '
               P2-SEGNAME ' '
               W-LEN ' ' W-KFB ' ' W-IO.
