* DFHMCT: hand-written fixture (#5154), syntax per IBM CICS TS 5.4 DFHMCT TYPE=EMP
* [ibm.com/docs SSGMCP_5.4.0 macros/mct/emp.html]. No IBM table text or sample is reproduced.
DFHMCT   CSECT
         DFHMCT TYPE=INITIAL,SUFFIX=01
         DFHMCT TYPE=EMP,CLASS=PERFORM,ID=(PP,3),COUNT=(1,HITS),        X
               PERFORM=(ADDCNT(1,1))
         DFHMCT TYPE=EMP,CLASS=PERFORM,ID=BANK.180,CLOCK=(1,ELAPSED),   X
               PERFORM=(SCLOCK(1))
         DFHMCT TYPE=RECORD,CLASS=PERFORM
         DFHMCT TYPE=FINAL
         END
