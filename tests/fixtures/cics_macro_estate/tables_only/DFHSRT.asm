* DFHSRT: hand-written fixture (#5154), syntax per IBM CICS TS 5.3 DFHSRT TYPE=SYSTEM|USER
* [ibm.com/docs SSGMCP_5.3.0 macros/srt/system.html]. No IBM table text or sample is reproduced.
DFHSRT   CSECT
         DFHSRT TYPE=INITIAL,SUFFIX=01
         DFHSRT TYPE=SYSTEM,ABCODE=(0C1,0C4),RECOVER=YES
         DFHSRT TYPE=USER,ABCODE=(1234),RECOVER=YES
         DFHSRT TYPE=SYSTEM,ABCODE=0C7,RECOVER=NO
         DFHSRT TYPE=FINAL
         END
