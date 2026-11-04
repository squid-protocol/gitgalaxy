//*********************************************************************
//* #4891 level fixture: JCL step flow (EXEC COND, IF/THEN/ELSE/ENDIF).
//* No program runs: each step's return code or abend is a scenario
//* input (scenarios.json), and the expected run / bypass answers there
//* were written from IBM's z/OS MVS JCL Reference (SA23-1385) before
//* any evaluator existed. Step programs are placeholders.
//*********************************************************************
//CONDJOB  JOB (ACCT),'COND LEVEL',CLASS=A,MSGCLASS=X
//* IBM: a test is  code op RC; true bypasses the step. A test that
//* names a bypassed step is false. No stepname tests all earlier steps.
//S1       EXEC PGM=PGMA
//OUT      DD DSN=APP.LEVEL.WORK,DISP=(NEW,CATLG,DELETE)
//S2       EXEC PGM=PGMB,COND=(4,LT,S1)
//IN       DD DSN=APP.LEVEL.WORK,DISP=SHR
//S3       EXEC PGM=PGMC,COND=((8,LE,S1),(0,NE,S2))
//S4       EXEC PGM=PGMD,COND=(4,GT)
//S5       EXEC PGM=PGME,COND=EVEN
//S6       EXEC PGM=PGMF,COND=ONLY
//*
//EVNJOB   JOB (ACCT),'EVEN ONLY LEVEL',CLASS=A,MSGCLASS=X
//T1       EXEC PGM=PGMA
//T2       EXEC PGM=PGMB,COND=((4,LT,T1),EVEN)
//T3       EXEC PGM=PGMC,COND=((4,LT,T1),ONLY)
//*
//IFJOB    JOB (ACCT),'IF LEVEL',CLASS=A,MSGCLASS=X
//* IBM: RC is the highest RC of the steps that executed so far; a
//* stepname.RC of a step that did not execute makes the test false.
//I1       EXEC PGM=PGMA
// IF (I1.RC = 0) THEN
//I2       EXEC PGM=PGMB
// ELSE
//I3       EXEC PGM=PGMC
// ENDIF
// IF (RC > 4 | I2.RC = 4) THEN
//I4       EXEC PGM=PGMD
// ENDIF
// IF (ABEND = TRUE) THEN
//I5       EXEC PGM=PGME
// ENDIF
// IF (I3.RUN = FALSE) THEN
//I6       EXEC PGM=PGMF
// ENDIF
