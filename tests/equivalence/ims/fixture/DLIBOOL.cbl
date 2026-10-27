       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLIBOOL.
      * #5233 boolean SSA fixture: qualification statements joined by
      * AND (& or *) and OR (+ or |) in one SSA, on LVLDBD through PSB
      * LVLPSB. IBM: statements joined by AND form a set; the SSA holds
      * when any set does. The test pins the expected output, written
      * from IBM's documentation before either runtime ran it.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W-Q                   PIC 9 VALUE 0.
       01  W-IO                  PIC X(14).
       01  IOA                   PIC X(20).
       01  F-GU                  PIC X(4) VALUE 'GU  '.
       01  F-GN                  PIC X(4) VALUE 'GN  '.
       01  S-DEPT                PIC X(9) VALUE 'DEPT     '.
       01  Q1.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'ENAME'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(10) VALUE 'ALICE'.
           05 FILLER             PIC X VALUE '|'.
           05 FILLER             PIC X(8) VALUE 'ENAME'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(10) VALUE 'CAROL'.
           05 FILLER             PIC X VALUE ')'.
       01  Q2.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E003'.
           05 FILLER             PIC X VALUE '+'.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE '*'.
           05 FILLER             PIC X(8) VALUE 'ENAME'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(10) VALUE 'BOB'.
           05 FILLER             PIC X VALUE ')'.
       01  Q3.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'SAL'.
           05 FILLER             PIC X(2) VALUE ' >'.
           05 FILLER             PIC S9(5) COMP-3 VALUE 1000.
           05 FILLER             PIC X VALUE '&'.
           05 FILLER             PIC X(8) VALUE 'SAL'.
           05 FILLER             PIC X(2) VALUE ' <'.
           05 FILLER             PIC S9(5) COMP-3 VALUE 3000.
           05 FILLER             PIC X VALUE ')'.
       01  Q4.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'ENAME'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(10) VALUE 'BOB'.
           05 FILLER             PIC X VALUE '&'.
           05 FILLER             PIC X(8) VALUE 'SAL'.
           05 FILLER             PIC X(2) VALUE ' >'.
           05 FILLER             PIC S9(5) COMP-3 VALUE 5000.
           05 FILLER             PIC X VALUE '+'.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E003'.
           05 FILLER             PIC X VALUE ')'.
       01  Q5.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE '?'.
       01  Q6.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE '&'.
           05 FILLER             PIC X(8) VALUE 'NOFIELD'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE ')'.
       01  Q7.
           05 FILLER             PIC X(9) VALUE 'EMP     ('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E001'.
           05 FILLER             PIC X VALUE '&'.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E002'.
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
           MOVE 1 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q1
           PERFORM SHOW1
           MOVE 1 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA Q1
           PERFORM SHOW1
           MOVE 2 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q2
           PERFORM SHOW1
           MOVE 3 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q3
           PERFORM SHOW1
           MOVE 4 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q4
           PERFORM SHOW1
           MOVE 5 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q5
           PERFORM SHOW1
           MOVE 6 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q6
           PERFORM SHOW1
           MOVE 7 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT Q7
           PERFORM SHOW1
           GOBACK.
       SHOW1.
           MOVE IOA(1:14) TO W-IO
           DISPLAY 'Q' W-Q ' [' P1-STATUS '] ' W-IO.
