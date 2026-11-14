//*********************************************************************
//* #8413 slice 1: IF / THEN / ELSE / ENDIF (RC, ABEND, ABENDCC, RUN,
//* NOT, nested IFs, IF around a PROC step, COND=EVEN / ONLY in the
//* same job). No program runs: each step's return code or abend is a
//* scenario input (scenarios.json); the expected run / bypass answers
//* there were written from IBM's z/OS MVS JCL Reference (SA23-1385)
//* before jcl_flow ran on them. Step programs are placeholders.
//*********************************************************************
//NESTJOB  JOB (ACCT),'IF NESTED',CLASS=A,MSGCLASS=X
//N1       EXEC PGM=PGMA
//N2       EXEC PGM=PGMB
// IF (N1.RC <= 4) THEN
//N3       EXEC PGM=PGMC
//  IF (N3.RC = 0) THEN
//N4       EXEC PGM=PGMD
//  ELSE
//N5       EXEC PGM=PGME
//  ENDIF
// ELSE
//N6       EXEC PGM=PGMF
// ENDIF
// IF (NOT N2.RC = 0 | N3.RUN = FALSE) THEN
//N7       EXEC PGM=PGMG
// ENDIF
// IF (N2.RC NG 4) THEN
//N8       EXEC PGM=PGMH
// ENDIF
//*
//ABNJOB   JOB (ACCT),'IF ABEND',CLASS=A,MSGCLASS=X
//A1       EXEC PGM=PGMA
//A2       EXEC PGM=PGMB
// IF (ABEND = TRUE) THEN
//A3       EXEC PGM=PGMC
// ELSE
//A4       EXEC PGM=PGMD
// ENDIF
// IF (A2.ABENDCC = S0C7) THEN
//A5       EXEC PGM=PGME
// ENDIF
// IF (A2.ABENDCC = U0100 | A1.ABENDCC = S806) THEN
//A6       EXEC PGM=PGMF
// ENDIF
// IF (ABEND = FALSE) THEN
//A7       EXEC PGM=PGMG
// ENDIF
//A8       EXEC PGM=PGMH,COND=EVEN
//A9       EXEC PGM=PGMI,COND=ONLY
//*
//PRCJOB   JOB (ACCT),'IF PROC STEP',CLASS=A,MSGCLASS=X
//B1       EXEC PGM=PGMA
// IF (B1.RC = 0) THEN
//B2       EXEC PROC=MYPROC
// ENDIF
// IF (B2.RUN = TRUE & RC < 8) THEN
//B3       EXEC PGM=PGMC
// ENDIF
//B4       EXEC PGM=PGMD,COND=EVEN
//*
//CMBJOB   JOB (ACCT),'IF COMBINED',CLASS=A,MSGCLASS=X
//C1       EXEC PGM=PGMA
//C2       EXEC PGM=PGMB
// IF ((C1.RC = 0 & C2.RC = 0) | C1.RC = 4) THEN
//C3       EXEC PGM=PGMC
// ENDIF
// IF (RC NL 8) THEN
//C4       EXEC PGM=PGMD
// ENDIF
// IF (C2.RC NE 0 | C2.ABEND = TRUE) THEN
//C6       EXEC PGM=PGMF
// ENDIF
//C5       EXEC PGM=PGME,COND=(8,LE)
//C7       EXEC PGM=PGMG,COND=ONLY
