       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLICMD.
      * #5233 command-code fixture: F, L and the null code - in SSAs on
      * LVLDBD through PSB LVLPSB. IBM: L takes the last twin of the
      * type under its parent, F the first (the default start of a GU);
      * on an ISRT with a unique sequence field both are ignored. The
      * test pins the expected output, written from IBM's documentation
      * before either runtime ran it.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W-Q                   PIC 99 VALUE 0.
       01  W-IO                  PIC X(14).
       01  IOA                   PIC X(20).
       01  F-GU                  PIC X(4) VALUE 'GU  '.
       01  F-GN                  PIC X(4) VALUE 'GN  '.
       01  F-ISRT                PIC X(4) VALUE 'ISRT'.
       01  S-DEPT.
           05 FILLER             PIC X(9) VALUE 'DEPT     '.
       01  S-EMP.
           05 FILLER             PIC X(9) VALUE 'EMP      '.
       01  C-DL.
           05 FILLER             PIC X(11) VALUE 'DEPT    *L '.
       01  C-DF.
           05 FILLER             PIC X(11) VALUE 'DEPT    *F '.
       01  C-DN.
           05 FILLER             PIC X(11) VALUE 'DEPT    *- '.
       01  C-EL.
           05 FILLER             PIC X(11) VALUE 'EMP     *L '.
       01  C-EFL.
           05 FILLER             PIC X(12) VALUE 'EMP     *FL '.
       01  C-SKL.
           05 FILLER             PIC X(11) VALUE 'SKILL   *L '.
       01  C-EF.
           05 FILLER             PIC X(11) VALUE 'EMP     *F '.
       01  C-DQ.
           05 FILLER             PIC X(11) VALUE 'DEPT    *-('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
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
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL
           PERFORM SHOW1
           MOVE 2 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 3 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DF
           PERFORM SHOW1
           MOVE 4 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DN
           PERFORM SHOW1
           MOVE 5 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT C-EL
           PERFORM SHOW1
           MOVE 6 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DQ C-EL
           PERFORM SHOW1
           MOVE 7 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT C-EFL
           PERFORM SHOW1
           MOVE 8 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT S-EMP C-SKL
           PERFORM SHOW1
           MOVE 9 TO W-Q
           MOVE 'E004DAVE' TO IOA
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOA C-DQ C-EF
           PERFORM SHOW1
           MOVE 10 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DQ C-EL
           PERFORM SHOW1
           GOBACK.
       SHOW1.
           MOVE IOA(1:14) TO W-IO
           DISPLAY 'Q' W-Q ' [' P1-STATUS '] ' W-IO.
