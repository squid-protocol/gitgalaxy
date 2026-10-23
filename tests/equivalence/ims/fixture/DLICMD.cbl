       IDENTIFICATION DIVISION.
       PROGRAM-ID. DLICMD.
      * #5233 command-code fixture: F, L, P, C, D, N, Q, U, V and the null code - in SSAs on
      * LVLDBD through PSB LVLPSB. IBM: L takes the last twin of the
      * type under its parent, F the first (the default start of a GU);
      * on an ISRT with a unique sequence field both are ignored. P on a
      * GU sets parentage at the level of its SSA, so a GNP afterwards
      * walks every dependent of that segment, not of the lowest one
      * retrieved. D (a path call) hands back the D-coded segments and the
      * one found, one after another, in hierarchic order (Q30-Q39). Q
      * (enqueue) changes nothing with one program (Q40-Q45). U and V
      * take the current position as qualification (Q46-Q55). The
      * N (no replace) beside D on a get-hold: the REPL that follows replaces each segment the
      * path call returned except those coded N (Q56-Q70). D on an ISRT
      * before the last SSA is a path insert (Q71-Q82). The
      * test pins the expected output, written from IBM's documentation
      * before either runtime ran it.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W-Q                   PIC 99 VALUE 0.
       01  W-IO                  PIC X(14).
       01  IOA                   PIC X(20).
       01  IOP                   PIC X(60).
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
       01  C-DP.
           05 FILLER             PIC X(11) VALUE 'DEPT    *P '.
       01  C-EP.
           05 FILLER             PIC X(11) VALUE 'EMP     *P '.
       01  F-GNP                 PIC X(4) VALUE 'GNP '.
       01  F-GHU                 PIC X(4) VALUE 'GHU '.
       01  S-SKL.
           05 FILLER             PIC X(9) VALUE 'SKILL    '.
       01  C-DD.
           05 FILLER             PIC X(11) VALUE 'DEPT    *D '.
       01  C-ED.
           05 FILLER             PIC X(11) VALUE 'EMP     *D '.
       01  C-DDP.
           05 FILLER             PIC X(12) VALUE 'DEPT    *DP '.
       01  C-CDE.
           05 FILLER             PIC X(11) VALUE 'EMP     *CD'.
           05 FILLER             PIC X VALUE '('.
           05 FILLER             PIC X(8) VALUE 'D100E002'.
           05 FILLER             PIC X VALUE ')'.
       01  C-DDQ.
           05 FILLER             PIC X(11) VALUE 'DEPT    *D('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
           05 FILLER             PIC X VALUE ')'.
       01  C-DQP.
           05 FILLER             PIC X(11) VALUE 'DEPT    *P('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
           05 FILLER             PIC X VALUE ')'.
       01  C-DQ.
           05 FILLER             PIC X(11) VALUE 'DEPT    *-('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
           05 FILLER             PIC X VALUE ')'.
       01  C-DK.
           05 FILLER             PIC X(11) VALUE 'DEPT    *Q '.
       01  C-DQQ.
           05 FILLER             PIC X(11) VALUE 'DEPT    *Q('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
           05 FILLER             PIC X VALUE ')'.
       01  C-EK.
           05 FILLER             PIC X(11) VALUE 'EMP     *Q '.
       01  C-EKL.
           05 FILLER             PIC X(12) VALUE 'EMP     *QL '.
       01  S-PROJ.
           05 FILLER             PIC X(9) VALUE 'PROJ     '.
       01  C-DU.
           05 FILLER             PIC X(11) VALUE 'DEPT    *U '.
       01  C-DV.
           05 FILLER             PIC X(11) VALUE 'DEPT    *V '.
       01  C-EU.
           05 FILLER             PIC X(11) VALUE 'EMP     *U '.
       01  F-REPL                PIC X(4) VALUE 'REPL'.
       01  C-DDN.
           05 FILLER             PIC X(12) VALUE 'DEPT    *DN '.
       01  C-EDN.
           05 FILLER             PIC X(12) VALUE 'EMP     *DN '.
       01  C-EV.
           05 FILLER             PIC X(11) VALUE 'EMP     *V '.
       01  C-EQ2.
           05 FILLER             PIC X(11) VALUE 'EMP     *-('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E002'.
           05 FILLER             PIC X VALUE ')'.
       01  C-EQ3.
           05 FILLER             PIC X(11) VALUE 'EMP     *-('.
           05 FILLER             PIC X(8) VALUE 'EMPNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'E003'.
           05 FILLER             PIC X VALUE ')'.
       01  C-SK.
           05 FILLER             PIC X(11) VALUE 'SKILL   *Q '.
       01  C-CE2.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D100E002'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CS2.
           05 FILLER             PIC X(11) VALUE 'SKILL   *C('.
           05 FILLER             PIC X(10) VALUE 'D100E001S2'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CE9.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D100E009'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CE3.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D200E003'.
           05 FILLER             PIC X VALUE ')'.
       01  C-DQ9.
           05 FILLER             PIC X(11) VALUE 'DEPT    *-('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D999'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CN1.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D400E010'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CN2.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D100E011'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CN3.
           05 FILLER             PIC X(11) VALUE 'EMP     *C('.
           05 FILLER             PIC X(8) VALUE 'D200E030'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CN4.
           05 FILLER             PIC X(11) VALUE 'SKILL   *C('.
           05 FILLER             PIC X(10) VALUE 'D500E020S9'.
           05 FILLER             PIC X VALUE ')'.
       01  C-CN5.
           05 FILLER             PIC X(11) VALUE 'SKILL   *C('.
           05 FILLER             PIC X(10) VALUE 'D200E030S8'.
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
           MOVE 11 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DP S-EMP
           PERFORM SHOW1
           MOVE 12 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 13 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 14 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 15 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 16 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 17 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT C-EP
           PERFORM SHOW1
           MOVE 18 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 19 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 20 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 21 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DQP S-EMP
           PERFORM SHOW1
           MOVE 22 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 23 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 24 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 25 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CE2
           PERFORM SHOW1
           MOVE 26 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CS2
           PERFORM SHOW1
           MOVE 27 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA
           PERFORM SHOW1
           MOVE 28 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CE9
           PERFORM SHOW1
           MOVE 29 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CE3
           PERFORM SHOW1
           MOVE 30 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GU PCB1 IOP C-DD C-ED S-SKL
           PERFORM SHOWP
           MOVE 31 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GN PCB1 IOP C-ED S-SKL
           PERFORM SHOWP
           MOVE 32 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GU PCB1 IOP C-DD S-EMP
           PERFORM SHOWP
           MOVE 33 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GU PCB1 IOP C-DD
           PERFORM SHOWP
           MOVE 34 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GU PCB1 IOP C-DDQ C-ED S-SKL
           PERFORM SHOWP
           MOVE 35 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GU PCB1 IOP C-DDP S-EMP
           PERFORM SHOWP
           MOVE 36 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GNP PCB1 IOP C-ED S-SKL
           PERFORM SHOWP
           MOVE 37 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GNP PCB1 IOP C-ED S-SKL
           PERFORM SHOWP
           MOVE 38 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GNP PCB1 IOP C-ED S-SKL
           PERFORM SHOWP
           MOVE 39 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GHU PCB1 IOP C-DD S-EMP
           PERFORM SHOWP
           MOVE 40 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DK
           PERFORM SHOW1
           MOVE 41 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DQQ S-EMP
           PERFORM SHOW1
           MOVE 42 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA C-EK
           PERFORM SHOW1
           MOVE 43 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA C-SK
           PERFORM SHOW1
           MOVE 44 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GHU PCB1 IOA C-DQQ C-EK
           PERFORM SHOW1
           MOVE 45 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT C-EKL
           PERFORM SHOW1
           MOVE 46 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DU S-EMP
           PERFORM SHOW1
           MOVE 47 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DU C-EQ2
           PERFORM SHOW1
           MOVE 48 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DV C-EV
           PERFORM SHOW1
           MOVE 49 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT C-EU
           PERFORM SHOW1
           MOVE 50 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GN PCB1 IOA C-DU S-PROJ
           PERFORM SHOW1
           MOVE 51 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DV
           PERFORM SHOW1
           MOVE 52 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA S-EMP
           PERFORM SHOW1
           MOVE 53 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA S-SKL
           PERFORM SHOW1
           MOVE 54 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GNP PCB1 IOA C-EV S-SKL
           PERFORM SHOW1
           MOVE 55 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DU C-EQ3
           PERFORM SHOW1
           MOVE 56 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GHU PCB1 IOP C-DDN S-EMP
           PERFORM SHOWP
           MOVE 'ZZZZZ' TO IOP(5:5)
           MOVE 'XENIA' TO IOP(25:5)
           MOVE 57 TO W-Q
           CALL 'CBLTDLI' USING F-REPL PCB1 IOP
           PERFORM SHOWP
           MOVE 58 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT S-EMP
           PERFORM SHOW1
           MOVE 59 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 60 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GHU PCB1 IOP C-DD C-EDN
           PERFORM SHOWP
           MOVE 'ALPHA' TO IOP(5:5)
           MOVE 'QQQQQ' TO IOP(25:5)
           MOVE 61 TO W-Q
           CALL 'CBLTDLI' USING F-REPL PCB1 IOP
           PERFORM SHOWP
           MOVE 62 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 63 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT S-EMP
           PERFORM SHOW1
           MOVE 64 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GHU PCB1 IOP C-DDN S-EMP
           PERFORM SHOWP
           MOVE 'D999' TO IOP(1:4)
           MOVE 'NEWNM' TO IOP(25:5)
           MOVE 65 TO W-Q
           CALL 'CBLTDLI' USING F-REPL PCB1 IOP
           PERFORM SHOWP
           MOVE 66 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 67 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT S-EMP
           PERFORM SHOW1
           MOVE 68 TO W-Q
           MOVE SPACES TO IOP
           CALL 'CBLTDLI' USING F-GHU PCB1 IOP C-DD S-EMP
           PERFORM SHOWP
           MOVE 'E999' TO IOP(21:4)
           MOVE 69 TO W-Q
           CALL 'CBLTDLI' USING F-REPL PCB1 IOP
           PERFORM SHOWP
           MOVE 70 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT S-EMP
           PERFORM SHOW1
           MOVE 71 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'D400NEWDEPT' TO IOP(1:11)
           MOVE 'E010ZED' TO IOP(21:7)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DD S-EMP
           PERFORM SHOWS
           MOVE 72 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CN1
           PERFORM SHOW1
           MOVE 73 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'D100IGNORED' TO IOP(1:11)
           MOVE 'E011ABEL' TO IOP(21:8)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DD S-EMP
           PERFORM SHOWS
           MOVE 74 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA S-DEPT
           PERFORM SHOW1
           MOVE 75 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CN2
           PERFORM SHOW1
           MOVE 76 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'D100IGNORED' TO IOP(1:11)
           MOVE 'E011ABEL' TO IOP(21:8)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DD S-EMP
           PERFORM SHOWS
           MOVE 77 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'D500NEWDEP' TO IOP(1:10)
           MOVE 'E020DEE' TO IOP(21:7)
           MOVE 'S9TEST' TO IOP(41:6)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DD C-ED S-SKL
           PERFORM SHOWS
           MOVE 78 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CN4
           PERFORM SHOW1
           MOVE 79 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'E030CY' TO IOP(1:6)
           MOVE 'S8X' TO IOP(21:3)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DQ C-ED S-SKL
           PERFORM SHOWS
           MOVE 80 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CN3
           PERFORM SHOW1
           MOVE 81 TO W-Q
           MOVE SPACES TO IOA
           CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CN5
           PERFORM SHOW1
           MOVE 82 TO W-Q
           MOVE SPACES TO IOP
           MOVE 'E040' TO IOP(1:4)
           MOVE 'S7' TO IOP(21:2)
           CALL 'CBLTDLI' USING F-ISRT PCB1 IOP C-DQ9 C-ED S-SKL
           PERFORM SHOWS
           GOBACK.
       SHOWS.
           DISPLAY 'Q' W-Q ' [' P1-STATUS '] ' P1-SEGNAME.
       SHOWP.
           DISPLAY 'Q' W-Q ' [' P1-STATUS '] ' IOP(1:4) '/'
               IOP(21:4) '/' IOP(41:2).
       SHOW1.
           MOVE IOA(1:14) TO W-IO
           DISPLAY 'Q' W-Q ' [' P1-STATUS '] ' W-IO.
