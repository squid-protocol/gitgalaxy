MACROASM CSECT
* A macro-level CICS program (era 0): no EXEC CICS
         USING DFHCSADS,R12
         DFHPC TYPE=LINK,                                              X
               PROGRAM=SUBPGM
         DFHFC TYPE=GET,DATASET=ACCT,                                  X
               TYPOPER=READ
         DFHPC TYPE=RETURN
         END
