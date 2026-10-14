* DFHFCT: hand-written fixture (#5120), syntax per IBM DFHFCT p.391-403
* [CICS TS for OS/390 R3 Resource Definition Guide SC33-1684-30, ch.13]. No IBM table text or sample is reproduced.
DFHFCT   CSECT
         DFHFCT TYPE=INITIAL,SUFFIX=01
         DFHFCT TYPE=FILE,ACCMETH=BDAM,FILE=ACCTDAT,                   X
               DSNAME=BANK.ACCT.DAM,RECFORM=(FIXED,BLOCKED),           X
               BLKSIZE=600,LRECL=300,KEYLEN=11,                        X
               SERVREQ=(READ,BROWSE,KEY)
* TYPE=DATASET,DATASET= is the retained pre-CICS/ESA spelling (RDG p.391)
         DFHFCT TYPE=DATASET,DATASET=CUSTDAT,ACCMETH=BDAM,             X
               DSNAME=BANK.CUST.DAM,RECFORM=(VARIABLE,BLOCKED),        X
               KEYLEN=16
         DFHFCT TYPE=FILE,FILE=MACONLY,DSNAME=BANK.MACRO.ONLY
         DFHFCT TYPE=REMOTE,FILE=RMTFIL,SYSIDNT=SYSB,KEYLEN=8,LRECL=80
         DFHFCT TYPE=FINAL
         END
