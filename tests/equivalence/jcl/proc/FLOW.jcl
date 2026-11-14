//*********************************************************************
//* #8413 slice 2: PROC resolution (symbolic parameters and defaults,
//* SET, EXEC PARM. / COND. overrides of a PROC step, a DD override, a
//* DD added to a PROC step, INCLUDE, JCLLIB ORDER) and
//* stepname.procstepname tests inside IF. The resolved step lists
//* and the run / bypass answers are in scenarios.json, written from
//* IBM's z/OS MVS JCL Reference (SA23-1385) before any evaluator ran
//* on them. Library members: libs/<library>/<member>.jcl.
//*********************************************************************
//SYMJOB   JOB (ACCT),'SYMBOLICS',CLASS=A,MSGCLASS=X
//CATP     PROC HLQ=PROD,SUF=DATA,PRM=ONE
//P1       EXEC PGM=PGMA,PARM='&PRM'
//IN       DD DSN=&HLQ..IN.&SUF,DISP=SHR
//P2       EXEC PGM=PGMB
//CTL      DD DSN=&HLQ..CTL,DISP=SHR
//         PEND
//S1       EXEC CATP
//S2       EXEC CATP,HLQ=TEST,PRM=TWO
//S3       EXEC PROC=CATP,SUF=NEW
// SET QUAL=PAYR
//D1       EXEC PGM=PGMC
//D1IN     DD DSN=&QUAL..FILE,DISP=SHR
// SET QUAL=BILL
//D2       EXEC PGM=PGMC
//D2IN     DD DSN=&QUAL..FILE,DISP=SHR
//*
//OVRJOB   JOB (ACCT),'OVERRIDES',CLASS=A,MSGCLASS=X
//BASE     PROC
//A1       EXEC PGM=PGMA,PARM='X1'
//SYSUT1   DD DSN=BASE.IN,DISP=SHR
//SYSUT2   DD DSN=BASE.OUT,DISP=(NEW,CATLG),UNIT=SYSDA
//A2       EXEC PGM=PGMB,PARM='Y1',COND=(4,LT,A1)
//SYSUT1   DD DSN=BASE.IN2,DISP=SHR
//         PEND
//O1       EXEC BASE
//O2       EXEC BASE,PARM.A2='Y2',COND.A2=(0,NE,A1)
//O3       EXEC BASE
//A1.SYSUT1 DD DSN=NEW.IN,DISP=SHR
//A2.EXTRA DD DSN=EXTRA.DD,DISP=SHR
//*
//LIBJOB   JOB (ACCT),'JCLLIB AB',CLASS=A,MSGCLASS=X
//PROCLIB  JCLLIB ORDER=(LIB.A,LIB.B)
//PRC3     PROC
//L3       EXEC PGM=INSTRM
//         PEND
//X1       EXEC PRC1
//X2       EXEC PRC2
//X3       EXEC PRC3
//X4       EXEC PGM=PGMH
// INCLUDE MEMBER=STDDDS
//*
//LIBJOB2  JOB (ACCT),'JCLLIB BA',CLASS=A,MSGCLASS=X
//PROCLIB  JCLLIB ORDER=(LIB.B,LIB.A)
//Y1       EXEC PRC1
//Y2       EXEC PRC3
//Y3       EXEC PGM=PGMH
// INCLUDE MEMBER=STDDDS
//*
//IFPJOB   JOB (ACCT),'IF PROC STEP',CLASS=A,MSGCLASS=X
//PP       PROC
//Q1       EXEC PGM=PGMA
//Q2       EXEC PGM=PGMB,COND=(4,LT,Q1)
//         PEND
//R1       EXEC PP
// IF (R1.Q1.RC = 0 & R1.Q2.RC <= 4) THEN
//R2       EXEC PGM=PGMC
// ELSE
//R3       EXEC PGM=PGMD
// ENDIF
// IF (R1.Q2.RUN = TRUE) THEN
//R4       EXEC PGM=PGME
// ENDIF
// IF (R1.Q1.ABENDCC = S0C7) THEN
//R5       EXEC PGM=PGMF
// ENDIF
//R6       EXEC PGM=PGMG,COND=(4,LT,R1.Q2)
