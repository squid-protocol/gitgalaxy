* DFHPCT: hand-written fixture (#5120, #5154), syntax per IBM CICS/VS System Programmer's Reference Manual
* SH20-1043-6 p.104-107, CICS TS for VSE/ESA R1 Resource Definition Guide SC33-1653-05 Appendix C p.347-351 &
* Appendix E p.365-368, and CICS for MVS/ESA V4R1 Migration Guide GC33-1162-04 ch.3. No IBM table text reproduced.
DFHPCT   CSECT
         DFHPCT TYPE=INITIAL,SUFFIX=01
         DFHPCT TYPE=ENTRY,TRANSID=BA01,PROGRAM=BANKINQ,TWASIZE=64
         DFHPCT TYPE=ENTRY,TRANSID=BA02,PROGRAM=BANKUPD
         DFHPCT TYPE=FINAL
         END
