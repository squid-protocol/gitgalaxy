* DFHPCT: hand-written fixture (#5120), syntax per IBM DFHPCT (ASSUMED syntax; macro removed in CICS/ESA 4.1, GC33-1162-04 ch.3)
* [CICS TS for OS/390 R3 Resource Definition Guide SC33-1684-30, ch.13]. No IBM table text or sample is reproduced.
DFHPCT   CSECT
         DFHPCT TYPE=INITIAL,SUFFIX=01
         DFHPCT TYPE=ENTRY,TRANSID=BA01,PROGRAM=BANKINQ,TWASIZE=64
         DFHPCT TYPE=ENTRY,TRANSID=BA02,PROGRAM=BANKUPD
         DFHPCT TYPE=FINAL
         END
